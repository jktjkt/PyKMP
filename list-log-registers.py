import logging
import sys
import time

from pykmp import client, codec, constants, messages

logger = logging.getLogger(__name__)
logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
)


def send_and_recv(comm, request):
    NUM_TRIES = 3
    for retry in range(NUM_TRIES):
        try:
            logger.debug('>>> %s', request)
            resp = comm.send_request(message=request, destination_address=constants.DestinationAddress.HEAT_METER.value)
            break
        except codec.CrcChecksumInvalidError as e:
            if retry < NUM_TRIES - 1:
                logger.warning('CRC error, will retry (current attempt #%s): %s', retry + 1, e)
                time.sleep(2)
                continue
            logger.error('CRC error, giving up after %s retries', retry + 1)
            raise
    logger.debug('<<< %s', resp)
    return resp


comm = client.PySerialClientCommunicator(
    serial_device=sys.argv[1]
)

for logger_type in constants.LoggerType:
    resp = send_and_recv(comm, messages.GetLogConfiguration(
        subcommand=constants.LoggerSubCommandId.GET_CONFIGURATION,
        logger_type=logger_type,
    ))

    print(f'{logger_type.name}: depth={resp.depth}, interval={resp.interval} (format {resp.interval_format})')
    for rid in resp.register_ids:
        print(f'  {rid:>5}  {constants.REGISTERS.get(rid, "(undocumented)")}')
