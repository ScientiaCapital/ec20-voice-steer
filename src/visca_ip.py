#!/usr/bin/env python3
"""Minimal Sony-style VISCA over IP client for the Epiphan EC20.

EC20 listens on UDP 52381 (fixed, per the EC20 network settings page).
Packet = 8-byte header + VISCA payload:
  bytes 0-1  payload type  0x01 0x00 = command, 0x01 0x10 = inquiry, 0x02 0x00 = control
  bytes 2-3  payload length (big-endian)
  bytes 4-7  sequence number (big-endian)
VISCA preset commands (camera address 1):
  recall  81 01 04 3F 02 pp FF
  save    81 01 04 3F 01 pp FF

Usage:
  visca_ip.py --ip 192.168.1.50 --recall 2
  visca_ip.py --ip 192.168.1.50 --save 2
  visca_ip.py --ip 192.168.1.50 --home
"""
import argparse
import socket
import struct
import sys
import time

PORT = 52381


class ViscaIP:
    def __init__(self, ip, port=PORT, timeout=1.0):
        self.addr = (ip, port)
        self.seq = 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(timeout)
        self.reset_sequence()

    def _packet(self, ptype, payload):
        self.seq = (self.seq + 1) & 0xFFFFFFFF
        return struct.pack(">HHI", ptype, len(payload), self.seq) + payload

    def _send(self, ptype, payload):
        pkt = self._packet(ptype, payload)
        self.sock.sendto(pkt, self.addr)
        try:
            data, _ = self.sock.recvfrom(1024)
            return data
        except socket.timeout:
            return None

    def reset_sequence(self):
        self.seq = 0
        pkt = struct.pack(">HHI", 0x0200, 1, 0) + b"\x01"
        self.sock.sendto(pkt, self.addr)
        try:
            self.sock.recvfrom(1024)
        except socket.timeout:
            pass

    def command(self, visca_bytes):
        return self._send(0x0100, bytes(visca_bytes))

    def recall(self, preset):
        return self.command([0x81, 0x01, 0x04, 0x3F, 0x02, preset & 0xFF, 0xFF])

    def save(self, preset):
        return self.command([0x81, 0x01, 0x04, 0x3F, 0x01, preset & 0xFF, 0xFF])

    def home(self):
        return self.command([0x81, 0x01, 0x06, 0x04, 0xFF])

    def inquiry_version(self):
        return self._send(0x0110, bytes([0x81, 0x09, 0x00, 0x02, 0xFF]))


def describe(reply):
    if reply is None:
        return "no reply (timeout)"
    body = reply[8:]
    if len(body) >= 3 and body[1] & 0xF0 == 0x40:
        return f"ACK {body.hex()}"
    if len(body) >= 3 and body[1] & 0xF0 == 0x50:
        return f"COMPLETION {body.hex()}"
    if len(body) >= 3 and body[1] & 0xF0 == 0x60:
        return f"ERROR {body.hex()}"
    return f"reply {reply.hex()}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip", required=True)
    ap.add_argument("--port", type=int, default=PORT)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--recall", type=int, metavar="N")
    g.add_argument("--save", type=int, metavar="N")
    g.add_argument("--home", action="store_true")
    g.add_argument("--version", action="store_true")
    a = ap.parse_args()

    cam = ViscaIP(a.ip, a.port)
    t0 = time.time()
    if a.recall is not None:
        r = cam.recall(a.recall)
    elif a.save is not None:
        r = cam.save(a.save)
    elif a.home:
        r = cam.home()
    else:
        r = cam.inquiry_version()
    print(f"{describe(r)}  ({(time.time()-t0)*1000:.0f} ms)")
    try:
        extra, _ = cam.sock.recvfrom(1024)
        print(describe(extra))
    except socket.timeout:
        pass
    return 0 if r is not None else 1


if __name__ == "__main__":
    sys.exit(main())
