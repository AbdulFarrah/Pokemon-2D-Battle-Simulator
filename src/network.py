"""Small, bounded JSON message transport for online battles."""

import json
import socket
import struct
import time


MAX_MESSAGE_SIZE = 1_000_000
PROTOCOL_VERSION = 1
PARTIAL_MESSAGE_TIMEOUT = 15
_HEADER = struct.Struct("!I")


class ProtocolError(ValueError):
    """Raised when a peer sends an invalid or oversized message."""


def send_message(conn, message):
    if not isinstance(message, dict):
        raise ProtocolError("Messages must be JSON objects.")
    if 'version' in message and message['version'] != PROTOCOL_VERSION:
        raise ProtocolError("Unsupported protocol version.")
    message = {**message, 'version': PROTOCOL_VERSION}
    try:
        payload = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProtocolError("Message contains unsupported data.") from exc
    if len(payload) > MAX_MESSAGE_SIZE:
        raise ProtocolError("Message exceeds the allowed size.")
    conn.sendall(_HEADER.pack(len(payload)) + payload)


def _read_exactly(conn, size, on_timeout=None, idle_timeout=None):
    chunks = bytearray()
    deadline = time.monotonic() + idle_timeout if idle_timeout is not None else None
    while len(chunks) < size:
        try:
            chunk = conn.recv(size - len(chunks))
        except socket.timeout:
            if on_timeout is not None:
                on_timeout()
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("Peer stalled while sending a framed message.")
            continue
        if not chunk:
            raise ConnectionError("Peer closed the connection.")
        if deadline is None:
            deadline = time.monotonic() + PARTIAL_MESSAGE_TIMEOUT
        chunks.extend(chunk)
    return bytes(chunks)


def receive_message(conn, on_timeout=None, idle_timeout=None):
    size = _HEADER.unpack(_read_exactly(conn, _HEADER.size, on_timeout, idle_timeout))[0]
    if size == 0 or size > MAX_MESSAGE_SIZE:
        raise ProtocolError("Invalid message size.")
    try:
        message = json.loads(_read_exactly(conn, size, on_timeout).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProtocolError("Peer sent invalid JSON.") from exc
    if not isinstance(message, dict):
        raise ProtocolError("Messages must be JSON objects.")
    if message.pop('version', None) != PROTOCOL_VERSION:
        raise ProtocolError("Unsupported or missing protocol version.")
    return message
