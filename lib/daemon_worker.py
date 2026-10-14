#!/usr/bin/env python3
"""Run one orchestra Codex worker as a thread on the local Codex app-server daemon.

Threads created this way appear in Codex Remote Control like any interactive
session, so you can watch or steer them from the app. Stdlib only.

Exit codes: 0 turn completed, 1 turn failed, 2 daemon/connection error,
124 timeout (turn interrupted by us), 130 interrupted (e.g. from the app) and
not resumed within the grace period.
"""
import argparse
import base64
import json
import os
import select
import socket
import struct
import sys
import time

CODEX_HOME = os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex"))
DEFAULT_SOCK = os.path.join(CODEX_HOME, "app-server-control", "app-server-control.sock")


class Conn:
    """Minimal JSON-RPC over WebSocket over a Unix socket."""

    def __init__(self, path, timeout=10):
        self.s = socket.socket(socket.AF_UNIX)
        self.s.settimeout(timeout)
        self.s.connect(os.path.realpath(path))
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(
            (
                "GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n"
                "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n" % key
            ).encode()
        )
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.s.recv(4096)
            if not chunk:
                raise ConnectionError("daemon closed during handshake")
            buf += chunk
        head, self.buf = buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise ConnectionError("websocket upgrade failed: %r" % head[:200])
        self.s.settimeout(None)
        self.next_id = 0
        self.pending = []  # notifications/requests read while waiting for a response

    def _frame(self, op, data):
        mask = os.urandom(4)
        n = len(data)
        if n < 126:
            hdr = struct.pack("!BB", 0x80 | op, 0x80 | n)
        elif n < 65536:
            hdr = struct.pack("!BBH", 0x80 | op, 0x80 | 126, n)
        else:
            hdr = struct.pack("!BBQ", 0x80 | op, 0x80 | 127, n)
        self.s.sendall(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def send(self, obj):
        self._frame(0x1, json.dumps(obj).encode())

    def _need(self, k, deadline):
        while len(self.buf) < k:
            wait = None if deadline is None else max(0, deadline - time.time())
            r, _, _ = select.select([self.s], [], [], wait)
            if not r:
                raise TimeoutError
            chunk = self.s.recv(65536)
            if not chunk:
                raise ConnectionError("daemon closed the connection")
            self.buf += chunk

    def read(self, deadline=None):
        """Next JSON message from the daemon, or TimeoutError at deadline."""
        if self.pending:
            return self.pending.pop(0)
        msg = b""
        while True:
            self._need(2, deadline)
            b0, b1 = self.buf[0], self.buf[1]
            n, off = b1 & 0x7F, 2
            if n == 126:
                self._need(4, deadline)
                n, off = struct.unpack("!H", self.buf[2:4])[0], 4
            elif n == 127:
                self._need(10, deadline)
                n, off = struct.unpack("!Q", self.buf[2:10])[0], 10
            self._need(off + n, deadline)
            payload, self.buf = self.buf[off:off + n], self.buf[off + n:]
            op = b0 & 0xF
            if op == 0x9:
                self._frame(0xA, payload)
            elif op == 0x8:
                raise ConnectionError("daemon closed the connection")
            elif op in (0x0, 0x1):
                msg += payload
                if b0 & 0x80:
                    return json.loads(msg)

    def call(self, method, params, timeout=60):
        self.next_id += 1
        rid = "orch-%d" % self.next_id
        self.send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        deadline = time.time() + timeout
        stash = []
        try:
            while True:
                m = self.read(deadline)
                if m.get("id") == rid and "method" not in m:
                    if "error" in m:
                        raise RuntimeError("%s failed: %s" % (method, m["error"]))
                    return m.get("result")
                stash.append(m)
        finally:
            self.pending = stash + self.pending


def log(*a):
    print(*a, flush=True)


def summarize_item(item):
    t = item.get("type")
    if t == "agentMessage":
        return "codex\n" + (item.get("text") or "")
    if t == "commandExecution":
        out = (item.get("aggregatedOutput") or "").rstrip()
        if len(out) > 1500:
            out = out[:1500] + "\n... (truncated)"
        return "exec %s  (exit=%s)\n%s" % (item.get("command"), item.get("exitCode"), out)
    if t == "fileChange":
        paths = []
        for c in item.get("changes") or []:
            paths.append("%s %s" % (c.get("kind", {}).get("type", "") if isinstance(c.get("kind"), dict) else c.get("kind", ""), c.get("path")))
        return "file change: " + ", ".join(paths)
    if t == "mcpToolCall":
        return "mcp %s.%s (%s)" % (item.get("server"), item.get("tool"), item.get("status"))
    if t == "webSearch":
        return "web search: %s" % item.get("query")
    if t == "plan":
        return "plan\n" + (item.get("text") or "")
    return None


def probe(sock):
    c = Conn(sock, timeout=5)
    c.call("initialize", {"clientInfo": {"name": "orchestra", "version": "1"}}, timeout=10)


def run(a):
    prompt = open(a.prompt_file, encoding="utf-8").read()
    c = Conn(a.sock)
    c.call("initialize", {"clientInfo": {"name": "orchestra", "version": "1"}})
    c.send({"jsonrpc": "2.0", "method": "initialized"})

    params = {"cwd": a.cwd, "approvalPolicy": "never", "sandbox": a.sandbox}
    if a.network and a.sandbox == "workspace-write":
        params["config"] = {"sandbox_workspace_write": {"network_access": True}}
    if a.model:
        params["model"] = a.model
    thread_id = c.call("thread/start", params)["thread"]["id"]
    if a.thread_file:
        with open(a.thread_file, "w") as f:
            f.write(thread_id + "\n")
    try:
        c.call("thread/name/set", {"threadId": thread_id, "name": a.name})
    except Exception as e:  # naming is cosmetic
        log("warn: could not name thread: %s" % e)
    log("thread %s  name=%r  (visible in Codex Remote Control)" % (thread_id, a.name))

    turn_params = {"threadId": thread_id, "input": [{"type": "text", "text": prompt}]}
    if a.effort:
        turn_params["effort"] = a.effort
    turn = c.call("turn/start", turn_params)["turn"]
    turn_id = turn["id"]
    deadline = time.time() + a.timeout
    last_msg = None
    status = None
    grace_until = None  # waiting for a follow-up turn after an interrupt

    while True:
        limit = min(deadline, grace_until) if grace_until else deadline
        try:
            m = c.read(limit)
        except TimeoutError:
            if grace_until and time.time() >= grace_until:
                break  # interrupted and nobody resumed
            log("timeout after %ds; interrupting turn" % a.timeout)
            try:
                c.call("turn/interrupt", {"threadId": thread_id, "turnId": turn_id}, timeout=15)
            except Exception:
                pass
            status = "timeout"
            break

        method = m.get("method")
        params = m.get("params") or {}
        if "id" in m and method:
            # Server-initiated request (approvals etc.). Policy is "never", so decline anything unexpected.
            log("server request %s -> declined" % method)
            c.send({"jsonrpc": "2.0", "id": m["id"], "error": {"code": -32601, "message": "orchestra worker is non-interactive"}})
            continue
        if params.get("threadId") not in (None, thread_id):
            continue
        if method == "turn/started":
            # A new turn on our thread, e.g. the user steering from Remote Control.
            turn_id = params["turn"]["id"]
            grace_until = None
            log("--- turn %s started" % turn_id)
        elif method == "item/completed":
            item = params.get("item") or {}
            if item.get("type") == "agentMessage" and item.get("text"):
                last_msg = item["text"]
            s = summarize_item(item)
            if s:
                log(s)
        elif method == "turn/completed":
            t = params.get("turn") or {}
            if t.get("id") != turn_id:
                continue
            status = t.get("status")
            log("--- turn %s %s%s" % (turn_id, status, (" error=%s" % t.get("error")) if t.get("error") else ""))
            if status == "interrupted":
                grace_until = time.time() + a.grace
                log("interrupted; waiting %ds for a follow-up turn (send one from the Codex app to continue)" % a.grace)
                continue
            break

    if last_msg is not None:
        with open(a.last_file, "w", encoding="utf-8") as f:
            f.write(last_msg.rstrip() + "\n")
    return {"completed": 0, "failed": 1, "timeout": 124, "interrupted": 130}.get(status, 1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sock", default=os.environ.get("ORCH_CODEX_SOCK", DEFAULT_SOCK))
    p.add_argument("--probe", action="store_true", help="exit 0 if the daemon is reachable")
    p.add_argument("--cwd")
    p.add_argument("--prompt-file")
    p.add_argument("--last-file")
    p.add_argument("--thread-file")
    p.add_argument("--name", default="orchestra worker")
    p.add_argument("--model")
    p.add_argument("--effort")
    p.add_argument("--timeout", type=int, default=3600)
    p.add_argument("--grace", type=int, default=600)
    p.add_argument("--network", action="store_true")
    p.add_argument("--sandbox", default="workspace-write", choices=["read-only", "workspace-write"])
    a = p.parse_args()
    if a.probe:
        try:
            probe(a.sock)
            return 0
        except Exception as e:
            print("daemon unreachable: %s" % e, file=sys.stderr)
            return 2
    try:
        return run(a)
    except (ConnectionError, OSError, RuntimeError) as e:
        log("daemon error: %s" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
