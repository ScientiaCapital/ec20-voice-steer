import pytest
from conftest import fake_camera

from ec20_voice_steer.visca import (
    CMD,
    CONTROL,
    INQUIRY,
    ReplyKind,
    build_packet,
    parse_reply,
    recall_message,
    save_message,
)

ACK = bytes.fromhex("0111000300000001") + bytes.fromhex("9041ff")
DONE = bytes.fromhex("0111000300000001") + bytes.fromhex("9051ff")
ERR = bytes.fromhex("0111000400000001") + bytes.fromhex("906002ff")


def test_header_layout() -> None:
    pkt = build_packet(CMD, b"\x81\x01\xff", 7)
    assert pkt.hex() == "01000003" + "00000007" + "8101ff"


def test_sequence_wraps_at_32_bits() -> None:
    assert build_packet(CMD, b"", 2**32)[4:8] == b"\x00\x00\x00\x00"


def test_preset_messages() -> None:
    assert recall_message(2).hex() == "8101043f0202ff"
    assert save_message(11).hex() == "8101043f010bff"
    assert recall_message(254)[5] == 0xFE


@pytest.mark.parametrize("bad", [-1, 255, 1000])
def test_preset_out_of_range_is_refused(bad: int) -> None:
    # 255 would put 0xFF, the VISCA terminator, in the middle of the message.
    with pytest.raises(ValueError):
        recall_message(bad)


@pytest.mark.parametrize(
    ("data", "kind"),
    [(ACK, ReplyKind.ACK), (DONE, ReplyKind.COMPLETION), (ERR, ReplyKind.ERROR), (None, ReplyKind.TIMEOUT)],
)
def test_parse_reply(data: bytes | None, kind: ReplyKind) -> None:
    assert parse_reply(data).kind is kind


def test_short_reply_is_other() -> None:
    reply = parse_reply(b"\x01\x02")
    assert reply.kind is ReplyKind.OTHER
    assert str(reply) == "reply 0102"


def test_reply_str_shows_visca_body_only() -> None:
    assert str(parse_reply(ACK)) == "ACK 9041ff"


async def test_reset_then_recall_on_the_wire() -> None:
    cam, wire = fake_camera([None, ACK])
    await cam.reset_sequence()
    reply = await cam.recall(3)
    assert reply.kind is ReplyKind.ACK
    assert wire.sent[0] == build_packet(CONTROL, b"\x01", 0)
    assert wire.sent[1] == build_packet(CMD, recall_message(3), 1)


async def test_sequence_increments_per_command() -> None:
    cam, wire = fake_camera([ACK, ACK, DONE])
    await cam.save(1)
    await cam.recall(1)
    await cam.inquiry_version()
    assert [int.from_bytes(p[4:8]) for p in wire.sent] == [1, 2, 3]
    assert int.from_bytes(wire.sent[2][0:2]) == INQUIRY


async def test_timeout_is_reported_not_raised() -> None:
    cam, _ = fake_camera([None])
    assert (await cam.home()).kind is ReplyKind.TIMEOUT
