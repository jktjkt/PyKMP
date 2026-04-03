# SPDX-FileCopyrightText: 2023 Gert van Dijk <github@gertvandijk.nl>
#
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import unittest.mock
from typing import TYPE_CHECKING, cast

import pytest
import decimal
import logging
import serial
import serial.serialutil
from typing_extensions import assert_type

from pykmp import codec, constants, messages
from pykmp.client import (
    ClientCodec,
    EncodedClientRequest,
    EncodedClientResponse,
    PySerialClientCommunicator,
    UnknownCidError,
)
from pykmp.registers import RegisterOutput

if TYPE_CHECKING:
    import mock_serial.mock_serial  # pyright: ignore[reportMissingTypeStubs]

    from . import util

SOME_DESTINATION_ADDRESS = 0x3A
GET_TYPE_REQUEST_BYTES = codec.PhysicalBytes(b"\x80\x3A\x01\xfa\x7f\x0d")
ANOTHER_DESTINATION_ADDRESS = 0x3F
GET_SERIAL_RESPONSE_BYTES = codec.PhysicalBytes(
    b"\x40\x3A\x02\x00\x12\xd6\x87\x9e\xe0\x0d"
)


def test_client_codec_encode(
    ensure_no_warnings_logged: util.SimpleContextTest,
) -> None:
    with ensure_no_warnings_logged():
        communicator = ClientCodec(
            destination_address=SOME_DESTINATION_ADDRESS,
        )
        encoded = communicator.encode(messages.GetTypeRequest()).physical_bytes
    assert encoded[0] == constants.ByteCode.START_TO_METER.value
    assert encoded[1] == SOME_DESTINATION_ADDRESS
    assert len(encoded) == len(GET_TYPE_REQUEST_BYTES)


def test_client_codec_decode(
    ensure_no_warnings_logged: util.SimpleContextTest,
) -> None:
    with ensure_no_warnings_logged():
        communicator = ClientCodec(destination_address=SOME_DESTINATION_ADDRESS)
        decoded = communicator.decode(
            frame=EncodedClientResponse(
                request_cls=messages.GetSerialRequest,
                physical_bytes=GET_SERIAL_RESPONSE_BYTES,
            ),
        )
    assert isinstance(decoded, messages.GetSerialRequest.get_response_type())


def test_client_codec_decode_ack_not_implemented(
    ensure_no_warnings_logged: util.SimpleContextTest,
) -> None:
    with ensure_no_warnings_logged():
        communicator = ClientCodec(destination_address=SOME_DESTINATION_ADDRESS)
        with pytest.raises(NotImplementedError):
            communicator.decode(
                frame=EncodedClientResponse(
                    physical_bytes=cast(codec.PhysicalBytes, constants.ACK_BYTES),
                    request_cls=messages.GetTypeRequest,
                ),
            )


def test_client_codec_encode_request_typing() -> None:
    communicator = ClientCodec()
    encoded = communicator.encode(messages.GetSerialRequest())
    assert_type(encoded, EncodedClientRequest[messages.GetSerialRequest])


def test_client_codec_decode_response_typing() -> None:
    response_encoded = codec.PhysicalBytes(b"\x40\x3F\x02\x01\x23\x45\x67\xE9\x56\x0D")
    communicator = ClientCodec()
    frame = EncodedClientResponse(
        physical_bytes=response_encoded, request_cls=messages.GetSerialRequest
    )
    response = communicator.decode(frame=frame)
    assert_type(response, messages.GetSerialResponse)


@pytest.mark.parametrize(
    ("serial_device_uri"),
    [
        pytest.param("/dev/ttyS0", id="ttyS0"),
        pytest.param("socket://0.0.0.0:1234", id="network socket"),
    ],
)
def test_client_pyserial_communicator_read_write(
    serial_device_uri: str,
    ensure_no_warnings_logged: util.SimpleContextTest,
) -> None:
    fake_serial = serial.serial_for_url("loop://", timeout=0.001)
    with unittest.mock.patch("serial.serial_for_url") as mocked_func:
        mocked_func.return_value = fake_serial
        with ensure_no_warnings_logged():
            communicator = PySerialClientCommunicator(
                serial_device=serial_device_uri
            )  # pyright: ignore[reportGeneralTypeIssues]
        mocked_func.assert_called_once()

    some_bytes = b"1234"
    some_bytes_with_stop = b"1234" + constants.ByteCode.STOP.value.to_bytes(1, "big")

    fake_serial.write(some_bytes)
    with ensure_no_warnings_logged():
        bytes_read_num = communicator.read(num_bytes=4)
    assert bytes_read_num == some_bytes

    fake_serial.write(some_bytes_with_stop)
    with ensure_no_warnings_logged():
        bytes_read_until_stop = communicator.read()
    assert bytes_read_until_stop == some_bytes_with_stop

    with pytest.raises(TimeoutError), ensure_no_warnings_logged():
        communicator.read()

    other_bytes = b"5678"
    with ensure_no_warnings_logged():
        communicator.write(codec.PhysicalBytes(other_bytes))
    assert fake_serial.read_all() == other_bytes


@pytest.mark.parametrize(
    ("serial_device_uri"),
    [
        pytest.param("/dev/nonexistentdevice", id="non-existent device in /dev"),
        pytest.param("socket://1.2.3.256:1234", id="invalid network socket URI"),
    ],
)
def test_client_pyserial_communicator_nonexistent(
    serial_device_uri: str,
    ensure_no_warnings_logged: util.SimpleContextTest,
) -> None:
    with pytest.raises(serial.serialutil.SerialException), ensure_no_warnings_logged():
        PySerialClientCommunicator(
            serial_device=serial_device_uri
        )  # pyright: ignore[reportGeneralTypeIssues]


def test_client_pyserial_communicator_send_request(
    mock_serial: mock_serial.mock_serial.MockSerial,
    ensure_no_warnings_logged: util.SimpleContextTest,
) -> None:
    mock_serial.stub(  # pyright: ignore[reportUnknownMemberType]
        receive_bytes=b"\x80\x3F\x02\x35\xE9\x0D",  # GetSerialNo request
        send_bytes=b"\x40\x3F\x02\x01\x23\x45\x67\xE9\x56\x0D",  # GetSerialNo response
    )
    with ensure_no_warnings_logged():
        communicator = PySerialClientCommunicator(
            serial_device=mock_serial.port
        )  # pyright: ignore[reportGeneralTypeIssues]
        communicator.send_request(message=messages.GetSerialRequest())


@pytest.mark.parametrize(
    ("payload", "parsed"),
    [
        pytest.param(
            '80 3f 01 05 8a 0d',
            messages.GetTypeRequest(),
        ),
        pytest.param(
            '80 3f 02 35 e9 0d',
            messages.GetSerialRequest(),
        ),
        pytest.param(
            '80 3f 10 02 01 5a 00 9a 1b bf 2b 0d',
            messages.GetRegisterRequest(data_raw=b'\x02\x01Z\x00\x9a', registers=[346, 154]),
        ),
        pytest.param(
            '80 3f 10 01 03 e9 7c d4 0d',
            messages.GetRegisterRequest(data_raw=b'\x01\x03\xe9', registers=[1001]),
        ),
        pytest.param(
            '80 ff ff 1d 0f 0d',
            UnknownCidError(cid=0xff, raw_data=b''),
        ),
        pytest.param(
            '80 3f b8 05 02 70 ee 0d',
            messages.GetLogConfiguration(subcommand=constants.LoggerSubCommandId.GET_CONFIGURATION,
                                         logger=constants.LoggerType.INTERVAL_YEAR,
                                         data_raw=b'\x05\x02',
                                         ),
        ),
        pytest.param(
            '80 3f b8 ff 02 8c e4 0d',
            messages.InvalidLoggerSubcommandError(subcommand=255),
        ),
        pytest.param(
            '80 3f b8 05 ff 4e 5c 0d',
            messages.InvalidLoggerTypeError(logger_type=255),
        ),
        pytest.param(
            '80 3f b8 07 07 ff ff 00 01 01 03 ea b8 5e 0d',
            messages.GetLogLastEntryPastAbs(subcommand=constants.LoggerSubCommandId.GET_LOG_LAST_ENTRY_PAST_ABS,
                                            logger=constants.LoggerType.INTERVAL_MIN2,
                                            offset=65535,
                                            num_entries=1,
                                            register_ids=[1002],
                                            data_raw=b'\x07\x07\xff\xff\x00\x01\x01\x03\xea',
                                            ),
        ),
        pytest.param(
            '80 3f b8 07 07 ff ff 00 01 ff 03 ea 40 0d 0d',
            codec.DataLengthUnexpectedError(
                what="GetLogLastEntryPastAbs: cannot read 2 more bytes for register-1 at offset 9",
                length_expected=11,
                expected_is_minimum=True,
                actual=9,
            ),
        ),
        pytest.param(
            '80 3f b8 07 07 ff ff 00 01 01 03 ea 00 78 d3 0d',
            codec.DataLengthUnexpectedError(
                what='GetLogLastEntryPastAbs',
                length_expected=9,
                actual=10,
            ),
        ),
        pytest.param(
            '80 3f b8 1b f9 02 00 00 00 02 00 02 01 03 eb 75 07 0d',
            messages.GetLogIDPastAbs(subcommand=constants.LoggerSubCommandId.GET_LOG_ID_PAST_ABS,
                                     logger=constants.LoggerType.INTERVAL_YEAR,
                                     log_id=2,
                                     num_entries=2,
                                     register_ids=[1003],
                                     data_raw=b'\x06\x02\x00\x00\x00\x02\x00\x02\x01\x03\xeb',
                                     ),
        ),
    ]
)
def test_blind_command_decoding(payload, parsed) -> None:
    communicator = ClientCodec(
        destination_address=ANOTHER_DESTINATION_ADDRESS,
    )
    raw_bytes = bytes.fromhex(payload)
    if isinstance(parsed, Exception):
        with pytest.raises(type(parsed)) as excinfo:
            decoded = communicator.decode_command(raw_bytes)
        assert str(excinfo.value) == str(parsed)
    else:
        decoded = communicator.decode_command(raw_bytes)
        assert decoded == parsed
        encoded = communicator.encode(parsed).physical_bytes
        assert encoded.hex(' ') == payload

@pytest.mark.parametrize(
    ("payload", "parsed"),
    [
        pytest.param(
            '40 3f 10 03 e9 33 04 00 00 00 00 00 63 38 0d',
            messages.GetRegisterResponse(data_raw=b'\x03\xe9\x33\x04\x00\x00\x00\x00\x00',
                                         registers={1001:
                                                    messages.RegisterData(id_=1001, unit=51, value=b'\x04\x00\x00\x00\x00\x00')}),
        ),
        pytest.param(
            '06',
            NotImplementedError(),
        ),
        pytest.param(
            '40 ff ff 1d 0f 0d',
            UnknownCidError(cid=0xff, raw_data=b''),
        ),
        pytest.param(
            '40 3f b8 05 02 01 01 01 01 00 00 01 00 01 00 00 14 2b 00 3c 00 3f 00 61 00 6e 00 1b bf 00 41 01 6a 00'
            + ' 44 00 54 00 55 01 71 00 63 00 7b 01 7f 00 7c 00 7d 01 1b 7f 00 7e 00 7f 01 81 00 1b 7f 00 81 01 82'
            + ' 00 82 03 ec 00 af 00 5e 00 3d 00 3e 00 5f 00 60 01 d9 01 da 00 45 00 e0 00 e1 00 48 00 49 02 03 01'
            + ' 52 01 5c 03 eb 03 ea d5 64 0d',
            messages.LoggerConfigResponse(
                subcommand=constants.LoggerSubCommandId.GET_CONFIGURATION,
                logger=constants.LoggerType.INTERVAL_YEAR,
                date1_format=1,
                date1=b'\x01\x01',
                date2_format=1,
                date2=b'\x00\x00',
                max_interval_records_format=1,
                max_interval_records=0,
                interval_format=1,
                interval=0,
                depth=20,
                register_ids=[
                    60,
                    63,
                    97,
                    110,
                    64,
                    65,
                    362,
                    68,
                    84,
                    85,
                    369,
                    99,
                    123,
                    383,
                    124,
                    125,
                    384,
                    126,
                    127,
                    385,
                    128,
                    129,
                    386,
                    130,
                    1004,
                    175,
                    94,
                    61,
                    62,
                    95,
                    96,
                    473,
                    474,
                    69,
                    224,
                    225,
                    72,
                    73,
                    515,
                    338,
                    348,
                    1003,
                    1002,
                ],
                data_raw=b'\x05\x02\x01\x01\x01\x01\x00\x00\x01\x00\x01\x00\x00\x14+\x00<\x00?\x00a\x00n\x00@\x00A'
                    + b'\x01j\x00D\x00T\x00U\x01q\x00c\x00{\x01\x7f\x00|\x00}\x01\x80\x00~\x00\x7f\x01\x81\x00\x80'
                    + b'\x00\x81\x01\x82\x00\x82\x03\xec\x00\xaf\x00^\x00=\x00>\x00_\x00`\x01\xd9\x01\xda\x00E\x00'
                    + b'\xe0\x00\xe1\x00H\x00I\x02\x03\x01R\x01\\\x03\xeb\x03\xea',
                ),
        ),
        pytest.param(
            '40 3f b8 07 07 00 01 01 00 00 00 00 00 00 00 00 00 01 03 ea 2f 04 00 00 00 00 00 1f 2f 0d',
            messages.GetLogLastEntryPastAbsResponse(
                subcommand=constants.LoggerSubCommandId.GET_LOG_LAST_ENTRY_PAST_ABS,
                logger=constants.LoggerType.INTERVAL_MIN2,
                first_log_id=0,
                last_log_id_in_meter=0,
                info=constants.LoggerInfo.NO_LOG_ENTRIES,
                log=[
                    [
                        messages.RegisterData(id_=1002, unit=47, value=b'\x04\x00\x00\x00\x00\x00'),
                    ],
                ],
                data_raw=b'\x07\x07\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x03\xea/\x04\x00\x00\x00\x00\x00',
                ),
        ),
        pytest.param(
            '40 3f b8 1b f9 02 00 02 01 00 00 00 02 00 00 00 02 00 c0 03 eb 30 04 00 00 03 f8 05 00 03 d0 f5 aa 3a 0d',
            messages.GetLogIDPastAbsResponse(subcommand=constants.LoggerSubCommandId.GET_LOG_ID_PAST_ABS,
                                             logger=constants.LoggerType.INTERVAL_YEAR,
                                             first_log_id=2,
                                             last_log_id_in_meter=2,
                                             info=constants.LoggerInfo.TAIL_INCLUDED | constants.LoggerInfo.HEAD_INCLUDED,
                                             log=[
                                                 [
                                                     messages.RegisterData(id_=1003, unit=48, value=b'\x04\x00\x00\x03\xf8\x05'),
                                                 ], [
                                                     messages.RegisterData(id_=1003, unit=48, value=b'\x04\x00\x00\x03\xd0\xf5'),
                                                 ],
                                             ],
                                             data_raw=b'\x06\x02\x00\x02\x01\x00\x00\x00\x02\x00\x00\x00\x02\x00\xc0\x03\xeb0\x04\x00\x00\x03\xf8\x05\x00\x03\xd0\xf5',
                                             ),
        ),
        pytest.param(
            '403FB81BF904000303000000BC00000285001BBF03EA2F04000000000403EB3004000003AE4F015C4F070000180C1F000004000000040003AE4E00180C1E000004000000040003AE4D00180C1D000004F22D0D',
            messages.GetLogIDPastAbsResponse(subcommand=constants.LoggerSubCommandId.GET_LOG_ID_PAST_ABS,
                                             logger=constants.LoggerType.INTERVAL_DAY,
                                             first_log_id=188,
                                             last_log_id_in_meter=645,
                                             info=constants.LoggerInfo.TAIL_INCLUDED,
                                             log=[
                                                 [
                                                     messages.RegisterData(id_=1002, unit=47, value=b'\x04\x00\x00\x00\x00\x04'),
                                                     messages.RegisterData(id_=1003, unit=48, value=b'\x04\x00\x00\x03\xaeO'),
                                                     messages.RegisterData(id_=348, unit=79, value=b'\x07\x00\x00\x18\x0c\x1f\x00\x00\x04'),
                                                 ],
                                                 [
                                                     messages.RegisterData(id_=1002, unit=47, value=b'\x04\x00\x00\x00\x00\x04'),
                                                     messages.RegisterData(id_=1003, unit=48, value=b'\x04\x00\x00\x03\xaeN'),
                                                     messages.RegisterData(id_=348, unit=79, value=b'\x07\x00\x00\x18\x0c\x1e\x00\x00\x04'),
                                                 ],
                                                 [
                                                     messages.RegisterData(id_=1002, unit=47, value=b'\x04\x00\x00\x00\x00\x04'),
                                                     messages.RegisterData(id_=1003, unit=48, value=b'\x04\x00\x00\x03\xaeM'),
                                                     messages.RegisterData(id_=348, unit=79, value=b'\x07\x00\x00\x18\x0c\x1d\x00\x00\x04'),
                                                 ],
                                             ],
                                             data_raw=b'\x06\x04\x00\x03\x03\x00\x00\x00\xbc\x00\x00\x02\x85\x00@\x03'
                                                + b'\xea/\x04\x00\x00\x00\x00\x04\x03\xeb0\x04\x00\x00\x03\xaeO\x01\\'
                                                + b'O\x07\x00\x00\x18\x0c\x1f\x00\x00\x04\x00\x00\x00\x04\x00\x03\xae'
                                                + b'N\x00\x18\x0c\x1e\x00\x00\x04\x00\x00\x00\x04\x00\x03\xaeM\x00\x18'
                                                + b'\x0c\x1d\x00\x00\x04',
                                             ),
        ),
    ]
)
def test_blind_response_decoding(payload, parsed) -> None:
    communicator = ClientCodec(
        destination_address=SOME_DESTINATION_ADDRESS,
    )
    if isinstance(parsed, Exception):
        with pytest.raises(type(parsed)) as excinfo:
            decoded = communicator.decode_response(bytes.fromhex(payload))
        assert str(excinfo.value) == str(parsed)
    else:
        decoded = communicator.decode_response(bytes.fromhex(payload))
        assert decoded == parsed

@pytest.mark.parametrize(
    ("id_", "unit", "blob_with_size", "value_str", "value_dec", "unit_str"),
    [
        pytest.param(
            1001,
            51,
            b'\x04\x00\x00\x00\x00\x00',
            '0',
            decimal.Decimal('0'),
            'no unit (number)',
        ),
        pytest.param(
            1002,
            47,
            b'\x04\x00\x00\x00\x00\x04',
            '00:00:04',
            None,
            'hh:mm:ss',
        ),
        pytest.param(
            1003,
            48,
            b'\x04\x00\x00\x03\xaeO',
            '2024-12-31',
            None,
            'yy:mm:dd',
        ),
        pytest.param(
            348,
            79,
            b'\x07\x00\x00\x18\x0c\x1f\x00\x00\x04',
            '2024-12-31 00:00:04-00:00',
            None,
            'DST YY-MM-DD hh:mm:ss',
        ),
        pytest.param(
            60,
            8,
            b'\x04C\x00\x05\xc4\xa6',
            '378.022',
            decimal.Decimal('378.022'),
            'GJ',
        ),
    ]
)
def test_register_parsing(id_, unit, blob_with_size, value_str, value_dec, unit_str):
    data = messages.RegisterData(id_=id_, unit=unit, value=blob_with_size)
    parsed = RegisterOutput.from_register_data(data)
    logging.debug('%s', parsed.to_pretty_line())
    assert parsed.value_str == value_str
    assert parsed.value_dec == value_dec
    assert parsed.unit_str == unit_str
