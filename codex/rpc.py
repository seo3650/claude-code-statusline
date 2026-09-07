#!/usr/bin/env python3
"""Small local JSON-RPC client for the installed Codex app server. No model calls."""
import json
from process_limits import prepare_process
import queue
import subprocess
import threading
import time


class CodexRPC:
    def __init__(self, binary="codex", cwd=None):
        prepare_process()
        self.proc = subprocess.Popen(
            [binary, "app-server", "--stdio"],
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self.events = queue.Queue()
        self.notifications = []
        self.seq = 0
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.call(
                "initialize",
                {
                    "clientInfo": {"name": "codex-statusline", "version": "1"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            self.send({"method": "initialized"})
        except Exception:
            self.close()
            raise

    def _read(self):
        for line in self.proc.stdout:
            try:
                self.events.put(json.loads(line))
            except ValueError:
                pass
        self.events.put(None)

    def send(self, data):
        self.proc.stdin.write(json.dumps(data) + "\n")
        self.proc.stdin.flush()

    def call(self, method, params=None, timeout=60):
        self.seq += 1
        request_id = self.seq
        self.send(
            {
                "id": request_id,
                "method": method,
                **({"params": params} if params is not None else {}),
            }
        )
        deadline = time.monotonic() + timeout
        while True:
            event = self.events.get(timeout=max(0.01, deadline - time.monotonic()))
            if event is None:
                raise RuntimeError("Codex app server exited")
            if event.get("id") == request_id:
                if "error" in event:
                    raise RuntimeError(str(event["error"]))
                return event.get("result")
            self.notifications.append(event)

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
