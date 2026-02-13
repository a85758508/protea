#!/usr/bin/env python3
"""Ring 2 — seed behaviour code.

Writes a heartbeat file every 2 seconds so Ring 0 Sentinel knows we're alive.
This file is the starting point for evolvable code; future generations will
be mutated versions of this file (or its successors).
"""

import os
import pathlib
import sys
import time

HEARTBEAT_INTERVAL = 2  # seconds


def write_heartbeat(path: pathlib.Path, pid: int) -> None:
    path.write_text(f"{pid}\n{time.time()}\n")


def main() -> None:
    heartbeat_path = pathlib.Path(
        os.environ.get("PROTEA_HEARTBEAT", ".heartbeat")
    )
    pid = os.getpid()
    print(f"[Ring 2] alive  pid={pid}  heartbeat={heartbeat_path}", flush=True)

    try:
        while True:
            write_heartbeat(heartbeat_path, pid)
            time.sleep(HEARTBEAT_INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        # Clean up heartbeat file on graceful shutdown.
        try:
            heartbeat_path.unlink(missing_ok=True)
        except OSError:
            pass
        print(f"[Ring 2] shutdown  pid={pid}", flush=True)


if __name__ == "__main__":
    main()
