import copy
import json
import logging
import pykmp
from pykmp import client, codec, constants, messages, registers
import os
import sys
import time

logger = logging.getLogger(__name__)
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    # level=logging.DEBUG,
    level=logging.INFO,
)

def send_and_recv(comm, request):
    NUM_TRIES = 5
    for retry in range(NUM_TRIES):
        try:
            logger.debug('>>> %s', request)
            resp = comm.send_request(message=request, destination_address=constants.DestinationAddress.HEAT_METER.value)
            break
        except codec.CrcChecksumInvalidError as e:
            if retry < NUM_TRIES - 1:
                logger.warning('CRC error, will retry (current attempt #%s): %s', retry, e)
                limit_entries = 1
                if isinstance(request, messages.GetLogIDPastAbs) and request.num_entries > limit_entries:
                    logger.warning('Preemptively reducing GetLogIDPastAbs num_entries from %s to %s', request.num_entries, limit_entries)
                    request.num_entries = limit_entries
                time.sleep(2)
                continue
            logger.error('CRC error, giving up after %s retries', retry)
            raise
    logger.debug('<<< %s', resp)
    return resp

def extract_reg_by_id(regs, num):
    return [x for x in regs.values() if x.id_ == messages.RegisterID(num)][0]

comm = client.PySerialClientCommunicator(
    serial_device=sys.argv[1]
)

resp = send_and_recv(comm, messages.GetRegisterRequest(registers=[messages.RegisterID(rid) for rid in [1001]]))
sn = registers.RegisterOutput.from_register_data(extract_reg_by_id(resp.registers, 1001)).value_str
logger.info(f'Meter S/N {sn}')
if not sn.isdigit():
    logger.error('Malofrmed meter SN: not all digits: %s', sn)
    sys.exit(1)
OUT_PREFIX='out'
os.makedirs(f'{OUT_PREFIX}/{sn}', exist_ok=True)

FAILURES = []

what_to_read = {
    constants.LoggerType.INTERVAL_YEAR: [
        348, # date and time
        60, # heat energy
        68, # V1 (m3)

        1004, # operating hours
        175, # error hour counter
        99, # info code
        369, # info bits

        # flow v1 max per year: date, time, value
        123, 383, 124,

        # flow v1 min per year
        125, 384, 126,

        # max power
        127, 385, 128,

        # min power
        129, 386, 130,

        97, # m3 x t1 (E8)
        110, # m3 x t2 (E9)
        72, # M1 mass

        338, # data quality
    ],
    constants.LoggerType.INTERVAL_MONTH: [
        348,
        60,
        97,
        110,
        68,
        369,
        99,

        138, 387, 139,
        140, 388, 141,
        142, 389, 143,
        144, 390, 145,

        1004,
        175,
    ],
    constants.LoggerType.INTERVAL_DAY: [
        60,
        68,
        369,
        99,
        379,
        380,
        86,
        87,
        74,
        80,
        338,
        348,
    ],
    # constants.LoggerType.INTERVAL_HOUR: [348],
    # constants.LoggerType.INTERVAL_MIN1: [348],
}

for logger_type, reg_ids in what_to_read.items():
    FILE_NAME = f'{OUT_PREFIX}/{sn}/{logger_type.name}.json'
    OUT = {}
    lid_on_disk = 0
    try:
        with open(FILE_NAME, 'r') as f:
            OUT = json.load(f)
        log_ids = [int(k) for k, v in OUT.items() if len([entry for entry in v if 'error' in entry.keys()]) == 0]
        errored_ids = [k for k, v in OUT.items() if len([entry for entry in v if 'error' in entry.keys()]) > 0]
        if len(errored_ids):
            logger.warn('Stored log has errors, ignoring these LIDs: %s', errored_ids)
        log_ids.sort()
        lid_on_disk = log_ids[-1]
    except OSError as e:
        if e.errno == 2:
            logger.info('Reading %s form scratch', logger_type.name)
        else:
            raise

    DATA = []

    # read the oldest/newest log-id in the meter
    resp = send_and_recv(comm,
                         messages.GetLogLastEntryPastAbs(subcommand=constants.LoggerSubCommandId.GET_LOG_LAST_ENTRY_PAST_ABS,
                                                         logger=logger_type,
                                                         offset=65535,
                                                         num_entries=1,
                                                         register_ids=[1002] # time, we can ignore this
                                                         ),
                         )
    oldest_lid_in_meter = resp.first_log_id
    newest_lid_in_meter = resp.last_log_id_in_meter
    lid_lowest = max(lid_on_disk + 1, oldest_lid_in_meter)
    logger.info(f'Logger {logger_type.name}: on-disk {lid_on_disk}, in meter {oldest_lid_in_meter} - {newest_lid_in_meter}')
    if lid_lowest >= newest_lid_in_meter:
        logger.info(' -> no new entries')
        continue

    logger.info(f' will read {newest_lid_in_meter - lid_lowest + 1} entries ({lid_lowest} .. {newest_lid_in_meter})')
    for rid in reg_ids:
        # reading each register separately saves bandwidth because each format thingy is only repeated once

        # too bad we "have" to start at the newest entry...
        lid = newest_lid_in_meter
        while lid > lid_lowest:
            logger.info(f'Progress for {logger_type.name}: {len(DATA)} / {len(reg_ids) * (newest_lid_in_meter - lid_lowest + 1)}')
            try:
                resp = send_and_recv(comm,
                                     messages.GetLogIDPastAbs(
                                         subcommand=constants.LoggerSubCommandId.GET_LOG_ID_PAST_ABS,
                                         logger=logger_type,
                                         log_id=lid,
                                         num_entries=0xffff,
                                         register_ids=[rid],
                                         )
                                     )
            except codec.CrcChecksumInvalidError as e:
                FAILURES.append(f'{logger_type.name} LID {lid} RID {rid}: {repr(e)}')
                logger.error('CRC error when reading LID %s RID %s: %s', lid, rid, repr(e))
                DATA.append({
                    'lid': lid,
                    'rid': rid,
                    'error': str(e),
                })
                lid -= 1
                continue

            if len(resp.log) < 1:
                logger.error('Cannot read register %s at log_id %s: got no data back, giving up', rid, lid)
                break
            lid -= len(resp.log)
            for i, row in enumerate(resp.log):
                this_lid = resp.first_log_id - i
                reg = row[0]
                parsed = registers.RegisterOutput.from_register_data(reg)
                DATA.append({
                    'lid': this_lid,
                    'rid': reg.id_,
                    'name': parsed.name,
                    'value': parsed.value_str,
                    'unit': parsed.unit_str,
                })

    all_lids = [x['lid'] for x in DATA]
    all_lids.sort()
    for lid in set(all_lids):
        def without_lid(x):
            r = copy.copy(x)
            del r['lid']
            return r
        matching = [without_lid(x) for x in DATA if x['lid'] == lid]
        matching.sort(key=lambda x: x['rid'])
        OUT[lid] = matching
    with open(FILE_NAME + '.new', 'w') as f:
        json.dump(OUT, f, indent=2)
    os.rename(FILE_NAME + '.new', FILE_NAME)

for f in FAILURES:
    logger.error(f'FAILED entries: {f}')
