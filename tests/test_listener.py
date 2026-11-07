import asyncio
import errno
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import FAKE_IP

from ec20_voice_steer import cli
from ec20_voice_steer.listener import (
    ACK_BODY,
    COMPLETION_BODY,
    CONTROL_REPLY,
    INQUIRY_COMPLETION_BODY,
    REPLY,
    Listener,
    ListenError,
    decode,
    describe,
    ec20_steer_match,
    replies_for,
    serve,
)
from ec20_voice_steer.visca import (
    CMD,
    CONTROL,
    HOME_MESSAGE,
    INQUIRY,
    RESET_SEQUENCE,
    VERSION_INQUIRY,
    build_packet,
    recall_message,
    save_message,
)

SENDER = (FAKE_IP, 50000)
OTHER_SENDER = (FAKE_IP, 50001)


class RecordingTransport:
    """Stands in for the listener's UDP socket. Records each reply and where it would go."""

    def __init__(self) -> None:
        self.sent: list[tuple[bytes, tuple[str, int] | None]] = []
        self.closed = False

    def sendto(self, data: bytes, addr: tuple[str, int] | None = None) -> None:
        self.sent.append((data, addr))

    def close(self) -> None:
        self.closed = True


def make_listener(
    reply: bool = True, log_path: Path | None = None
) -> tuple[Listener, RecordingTransport, list[str], list[str]]:
    lines: list[str] = []
    problems: list[str] = []
    listener = Listener(reply=reply, log_path=log_path, echo=lines.append, clock=lambda: 0.0, report=problems.append)
    wire = RecordingTransport()
    listener.connection_made(wire)  # type: ignore[arg-type]
    return listener, wire, lines, problems


async def drain_log(listener: Listener) -> None:
    writer = asyncio.create_task(listener.write_log())
    await listener.log_queue.join()
    writer.cancel()


# decoding


@pytest.mark.parametrize(
    ("message", "meaning"),
    [
        (recall_message(3), "preset recall 3 (camera address 1)"),
        (save_message(11), "preset save 11 (camera address 1)"),
        (HOME_MESSAGE, "home (camera address 1)"),
        (VERSION_INQUIRY, "version inquiry (camera address 1)"),
        (bytes.fromhex("8201043f0205ff"), "preset recall 5 (camera address 2)"),
        (bytes.fromhex("81010601ff"), "not recognized"),
        (b"", "not recognized"),
    ],
)
def test_describe(message: bytes, meaning: str) -> None:
    assert describe(message) == meaning


def test_ec20_steers_own_recall_decodes_and_matches() -> None:
    d = decode(build_packet(CMD, recall_message(3), 42))
    assert (d.framing, d.type_name, d.seq) == ("visca-over-ip", "command", 42)
    assert d.meaning == "preset recall 3 (camera address 1)"
    assert d.notes == ()
    assert ec20_steer_match(d) == "same bytes as ec20-steer"


@pytest.mark.parametrize(
    ("payload_type", "message"),
    [
        (CMD, save_message(11)),
        (CMD, HOME_MESSAGE),
        (INQUIRY, VERSION_INQUIRY),
        (CONTROL, RESET_SEQUENCE),
    ],
)
def test_ec20_steers_other_requests_match(payload_type: int, message: bytes) -> None:
    assert ec20_steer_match(decode(build_packet(payload_type, message, 4))) == "same bytes as ec20-steer"


def test_different_camera_address_is_a_message_difference() -> None:
    match = ec20_steer_match(decode(build_packet(CMD, bytes.fromhex("8201043f0205ff"), 3))) or ""
    assert match.startswith("differs from ec20-steer")
    assert "message 82 01 04 3f 02 05 ff, ec20-steer sends 81 01 04 3f 02 05 ff" in match
    assert "payload type" not in match


def test_type_and_message_differences_are_both_listed() -> None:
    match = ec20_steer_match(decode(build_packet(INQUIRY, bytes.fromhex("8201043f0205ff"), 3))) or ""
    assert "ec20-steer uses command" in match
    assert "; message 82 01" in match


def test_wrong_length_field_is_noted() -> None:
    packet = bytearray(build_packet(CMD, recall_message(2), 1))
    packet[3] = 9  # header claims 9 payload bytes; the message is 7
    d = decode(bytes(packet))
    assert d.notes == ("header says 9 payload bytes, packet carries 7",)
    assert "header length field is off" in (ec20_steer_match(d) or "")


def test_raw_visca_is_called_out_and_not_answered() -> None:
    d = decode(recall_message(4))
    assert d.framing == "raw visca"
    assert d.meaning == "preset recall 4 (camera address 1)"
    assert "no VISCA over IP header" in d.notes[0]
    assert ec20_steer_match(d) is None
    assert replies_for(d) == []


def test_long_raw_visca_is_not_mistaken_for_a_header() -> None:
    d = decode(bytes.fromhex("8101060218180000000000000000ff"))
    assert d.framing == "raw visca"
    assert replies_for(d) == []


def test_unknown_header_type_is_unknown() -> None:
    d = decode(bytes.fromhex("0300000500000001") + HOME_MESSAGE)
    assert (d.framing, d.type_name) == ("unknown", "-")
    assert "first bytes 0300" in d.notes[0]
    assert replies_for(d) == []


def test_garbage_is_unknown_and_unanswered() -> None:
    d = decode(b"hello")
    assert d.framing == "unknown"
    assert replies_for(d) == []


# replies


def test_command_gets_ack_then_completion_with_the_same_sequence() -> None:
    d = decode(build_packet(CMD, recall_message(2), 9))
    assert replies_for(d) == [build_packet(REPLY, ACK_BODY, 9), build_packet(REPLY, COMPLETION_BODY, 9)]


def test_version_inquiry_gets_one_completion_and_no_ack() -> None:
    d = decode(build_packet(INQUIRY, VERSION_INQUIRY, 4))
    assert replies_for(d) == [build_packet(REPLY, INQUIRY_COMPLETION_BODY, 4)]


def test_reset_gets_a_control_reply() -> None:
    d = decode(build_packet(CONTROL, RESET_SEQUENCE, 0))
    assert replies_for(d) == [build_packet(CONTROL_REPLY, b"\x01", 0)]


@pytest.mark.parametrize(
    "packet",
    [
        build_packet(CMD, bytes.fromhex("8101060118180301ff"), 2),
        build_packet(CMD, b"", 2),
        build_packet(INQUIRY, bytes.fromhex("81090612ff"), 2),
    ],
)
def test_unrecognized_requests_get_no_reply_and_a_note(packet: bytes) -> None:
    d = decode(packet)
    assert replies_for(d) == []
    assert any("not recognized" in n for n in d.notes)


@pytest.mark.parametrize("packet", [build_packet(REPLY, ACK_BODY, 5), build_packet(CONTROL_REPLY, b"\x01", 0)])
def test_replies_are_never_answered(packet: bytes) -> None:
    listener, wire, _, _ = make_listener()
    listener.datagram_received(packet, SENDER)
    assert wire.sent == []
    assert ec20_steer_match(decode(packet)) is None


# the listener


def test_listener_answers_the_sender_and_prints_the_decode() -> None:
    listener, wire, lines, _ = make_listener()
    listener.datagram_received(build_packet(CMD, recall_message(3), 1), SENDER)
    assert [addr for _, addr in wire.sent] == [SENDER, SENDER]
    assert "preset recall 3" in lines[0]
    assert "[same bytes as ec20-steer]" in lines[0]
    assert "reply: 90 41 ff + 90 51 ff" in lines[0]


def test_no_reply_mode_stays_silent_and_says_so() -> None:
    listener, wire, lines, _ = make_listener(reply=False)
    listener.datagram_received(build_packet(CMD, recall_message(3), 1), SENDER)
    assert wire.sent == []
    assert "reply: none (--no-reply)" in lines[0]


def test_unknown_packet_line() -> None:
    listener, _, lines, _ = make_listener()
    listener.datagram_received(b"hello", SENDER)
    assert "unknown  -  seq -" in lines[0]
    assert "-> not recognized" in lines[0]
    assert "[" not in lines[0]
    assert "! neither VISCA over IP nor raw VISCA" in lines[0]


def test_sequence_jump_and_repeat_are_noted() -> None:
    listener, _, lines, _ = make_listener()
    for seq in (1, 2, 5, 5):
        listener.datagram_received(build_packet(CMD, recall_message(1), seq), SENDER)
    assert "!" not in lines[0] and "!" not in lines[1]
    assert "sequence jumped from 2 to 5" in lines[2]
    assert "sequence 5 repeated" in lines[3]


def test_sequence_wrap_is_not_a_jump() -> None:
    listener, _, lines, _ = make_listener()
    for seq in (0xFFFFFFFF, 0):
        listener.datagram_received(build_packet(CMD, recall_message(1), seq), SENDER)
    assert "!" not in lines[1]


def test_sequences_are_tracked_per_sender() -> None:
    listener, _, lines, _ = make_listener()
    for sender, seq in ((SENDER, 1), (OTHER_SENDER, 10), (SENDER, 2), (OTHER_SENDER, 11), (SENDER, 3)):
        listener.datagram_received(build_packet(CMD, recall_message(1), seq), sender)
    assert not any("!" in line for line in lines)


def test_reset_restarts_the_sequence_watch() -> None:
    listener, _, lines, _ = make_listener()
    listener.datagram_received(build_packet(CMD, recall_message(1), 8), SENDER)
    listener.datagram_received(build_packet(CONTROL, RESET_SEQUENCE, 0), SENDER)
    listener.datagram_received(build_packet(CMD, recall_message(2), 1), SENDER)
    assert "!" not in lines[2]


def test_a_failing_echo_still_sends_the_reply_and_is_reported() -> None:
    problems: list[str] = []

    def broken_echo(line: str) -> None:
        raise BrokenPipeError("stdout closed")

    listener = Listener(echo=broken_echo, report=problems.append)
    wire = RecordingTransport()
    listener.connection_made(wire)  # type: ignore[arg-type]
    listener.datagram_received(build_packet(CMD, recall_message(3), 1), SENDER)
    assert len(wire.sent) == 2
    assert "BrokenPipeError" in problems[0]
    assert build_packet(CMD, recall_message(3), 1).hex() in problems[0]


def test_socket_errors_are_reported() -> None:
    listener, _, _, problems = make_listener()
    listener.error_received(OSError(errno.EHOSTUNREACH, "No route to host"))
    assert listener.socket_errors == 1
    assert "socket error" in problems[0]


# the log


async def test_each_packet_is_logged_with_its_raw_bytes_and_notes(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    listener, _, _, _ = make_listener(log_path=log)
    first = build_packet(CMD, recall_message(3), 1)
    listener.datagram_received(first, SENDER)
    listener.datagram_received(build_packet(CMD, recall_message(4), 7), SENDER)
    await drain_log(listener)
    text = log.read_text().splitlines()
    assert len(text) == 2
    assert f"listen from {FAKE_IP}:50000" in text[0]
    assert f"raw {first.hex()}" in text[0]
    assert "! sequence jumped from 1 to 7" in text[1]


async def test_a_failing_log_is_reported_once_and_replies_continue(tmp_path: Path) -> None:
    listener, wire, _, problems = make_listener(log_path=tmp_path)  # a directory can't be appended to
    for seq in (1, 2):
        listener.datagram_received(build_packet(CMD, recall_message(3), seq), SENDER)
    await drain_log(listener)
    assert len(wire.sent) == 4
    assert listener.log_errors == 2
    assert len(problems) == 1 and "log writes" in problems[0]


# serve, with the socket faked


FakeEndpoint = Callable[..., object]


async def started(seen: dict[str, object]) -> None:
    for _ in range(200):
        if "protocol" in seen:
            await asyncio.sleep(0)
            return
        await asyncio.sleep(0.005)
    raise AssertionError("serve never bound")


def fake_endpoint(transport: RecordingTransport, seen: dict[str, object]) -> FakeEndpoint:
    async def create_datagram_endpoint(factory: Callable[[], Listener], local_addr: tuple[str, int]) -> object:
        protocol = factory()
        protocol.connection_made(transport)  # type: ignore[arg-type]
        seen.update(local_addr=local_addr, protocol=protocol)
        return transport, protocol

    return create_datagram_endpoint


async def test_serve_wires_the_listener_and_stops_cleanly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    loop = asyncio.get_running_loop()
    wire, seen, lines = RecordingTransport(), {}, []
    monkeypatch.setattr(loop, "create_datagram_endpoint", fake_endpoint(wire, seen))
    log = tmp_path / "logs" / "run.log"
    task = asyncio.create_task(serve("127.0.0.1", 52381, reply=False, log_path=log, echo=lines.append))
    await started(seen)
    protocol = seen["protocol"]
    assert isinstance(protocol, Listener)
    assert seen["local_addr"] == ("127.0.0.1", 52381)
    assert protocol.reply is False and protocol.log_path == log.resolve()
    assert "replies off" in lines[0] and str(log.resolve()) in lines[0]
    protocol.connection_lost(None)
    await task
    assert wire.closed
    assert lines[-1].startswith("listen stopped: 0 packets")


async def test_serve_reports_a_lost_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    loop = asyncio.get_running_loop()
    seen: dict[str, object] = {}
    monkeypatch.setattr(loop, "create_datagram_endpoint", fake_endpoint(RecordingTransport(), seen))
    task = asyncio.create_task(serve("127.0.0.1", 52381, echo=lambda _: None))
    await started(seen)
    seen["protocol"].connection_lost(OSError("socket gone"))  # type: ignore[attr-defined]
    with pytest.raises(OSError, match="socket gone"):
        await task


async def test_serve_turns_a_busy_port_into_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def busy(*args: object, **kwargs: object) -> object:
        raise OSError(errno.EADDRINUSE, "Address already in use")

    monkeypatch.setattr(asyncio.get_running_loop(), "create_datagram_endpoint", busy)
    with pytest.raises(ListenError, match="can't bind 0.0.0.0:52381: Address already in use. Is another"):
        await serve("0.0.0.0", 52381, echo=lambda _: None)


async def test_serve_refuses_a_log_it_cant_write(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("")
    with pytest.raises(ListenError, match="can't write log"):
        await serve("127.0.0.1", 52381, log_path=blocker / "run.log", echo=lambda _: None)


# the command line


def test_help_lists_listen(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        cli.main(["listen", "--help"])
    out = capsys.readouterr().out
    assert "--no-reply" in out and "--bind" in out and "--port" in out


def record_serve(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    called: dict[str, object] = {}

    async def fake_serve(bind: str, port: int, reply: bool = True, log_path: Path | None = None) -> None:
        called.update(bind=bind, port=port, reply=reply, log_path=log_path)

    monkeypatch.setattr(cli, "serve", fake_serve)
    return called


def test_listen_defaults_need_no_camera_address(monkeypatch: pytest.MonkeyPatch) -> None:
    called = record_serve(monkeypatch)
    assert cli.main(["listen", "--no-reply"]) == 0
    assert called == {"bind": "0.0.0.0", "port": 52381, "reply": False, "log_path": Path("docs/run.log")}


@pytest.mark.parametrize(
    ("argv", "port"),
    [
        (["listen", "--port", "6000"], 6000),
        (["--port", "5000", "listen"], 5000),
    ],
)
def test_listen_port_works_before_or_after_the_command(
    monkeypatch: pytest.MonkeyPatch, argv: list[str], port: int
) -> None:
    called = record_serve(monkeypatch)
    assert cli.main(argv) == 0
    assert called["port"] == port


def test_listen_passes_bind_and_log(monkeypatch: pytest.MonkeyPatch) -> None:
    called = record_serve(monkeypatch)
    assert cli.main(["listen", "--bind", "127.0.0.1", "--log", "x.log"]) == 0
    assert (called["bind"], called["log_path"]) == ("127.0.0.1", Path("x.log"))


def test_listen_ignores_a_broken_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EC20_STEER_PORT", "not-a-port")
    record_serve(monkeypatch)
    assert cli.main(["listen"]) == 0


def test_listen_warns_about_camera_options(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    record_serve(monkeypatch)
    assert cli.main(["--ip", FAKE_IP, "listen"]) == 0
    assert "ignores --ip" in capsys.readouterr().err


def test_listen_error_exits_2(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    async def failing_serve(*args: object, **kwargs: object) -> None:
        raise ListenError("listen: can't bind 0.0.0.0:52381: Address already in use.")

    monkeypatch.setattr(cli, "serve", failing_serve)
    assert cli.main(["listen"]) == 2
    assert "can't bind" in capsys.readouterr().err
