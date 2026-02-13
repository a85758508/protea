"""Sentinel — Ring 0 main loop (pure stdlib).

Launches and supervises Ring 2.  On failure, rolls back to the last
known-good commit and restarts.
"""

from __future__ import annotations

import logging
import os
import pathlib
import subprocess
import sys
import time
import tomllib

from ring0.fitness import FitnessTracker
from ring0.git_manager import GitManager
from ring0.heartbeat import HeartbeatMonitor
from ring0.parameter_seed import generate_params
from ring0.resource_monitor import check_resources

log = logging.getLogger("protea.sentinel")


def _load_config(project_root: pathlib.Path) -> dict:
    cfg_path = project_root / "config" / "config.toml"
    with open(cfg_path, "rb") as f:
        return tomllib.load(f)


def _start_ring2(ring2_path: pathlib.Path, heartbeat_path: pathlib.Path) -> subprocess.Popen:
    """Launch the Ring 2 process and return its Popen handle."""
    env = {**os.environ, "PROTEA_HEARTBEAT": str(heartbeat_path)}
    proc = subprocess.Popen(
        [sys.executable, str(ring2_path / "main.py")],
        cwd=str(ring2_path),
        env=env,
    )
    log.info("Ring 2 started  pid=%d", proc.pid)
    return proc


def _stop_ring2(proc: subprocess.Popen | None) -> None:
    """Terminate the Ring 2 process if it is still running."""
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    log.info("Ring 2 stopped  pid=%d", proc.pid)


def run(project_root: pathlib.Path) -> None:
    """Sentinel main loop — run until interrupted."""
    cfg = _load_config(project_root)
    r0 = cfg["ring0"]

    ring2_path = project_root / r0["git"]["ring2_path"]
    heartbeat_path = ring2_path / ".heartbeat"
    db_path = project_root / r0["fitness"]["db_path"]
    db_path.parent.mkdir(parents=True, exist_ok=True)

    interval = r0["heartbeat_interval_sec"]
    timeout = r0["heartbeat_timeout_sec"]
    seed = r0["evolution"]["seed"]

    git = GitManager(ring2_path)
    git.init_repo()
    fitness = FitnessTracker(db_path)
    hb = HeartbeatMonitor(heartbeat_path, timeout_sec=timeout)

    generation = 0
    last_good_hash: str | None = None
    proc: subprocess.Popen | None = None

    # Initial snapshot of seed code.
    try:
        last_good_hash = git.snapshot(f"gen-{generation} seed")
    except subprocess.CalledProcessError:
        pass

    log.info("Sentinel online — heartbeat every %ds, timeout %ds", interval, timeout)

    try:
        proc = _start_ring2(ring2_path, heartbeat_path)
        start_time = time.time()
        hb.wait_for_heartbeat(startup_timeout=timeout)

        while True:
            time.sleep(interval)

            # --- resource check ---
            ok, msg = check_resources(
                r0["max_cpu_percent"],
                r0["max_memory_percent"],
                r0["max_disk_percent"],
            )
            if not ok:
                log.warning("Resource alert: %s", msg)

            # --- heartbeat check ---
            if hb.is_alive():
                continue

            # Ring 2 is dead — record failure, rollback, restart.
            elapsed = time.time() - start_time
            log.warning("Ring 2 lost heartbeat after %.1fs", elapsed)
            _stop_ring2(proc)

            params = generate_params(generation, seed)
            fitness.record(
                generation=generation,
                commit_hash=last_good_hash or "unknown",
                score=0.0,
                runtime_sec=elapsed,
                survived=False,
            )

            if last_good_hash:
                log.info("Rolling back to %s", last_good_hash[:12])
                git.rollback(last_good_hash)

            generation += 1
            log.info("Restarting Ring 2 — generation %d (params: %s)", generation, params)
            proc = _start_ring2(ring2_path, heartbeat_path)
            start_time = time.time()
            hb.wait_for_heartbeat(startup_timeout=timeout)

    except KeyboardInterrupt:
        log.info("Sentinel shutting down (KeyboardInterrupt)")
    finally:
        _stop_ring2(proc)
        log.info("Sentinel offline")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    project_root = pathlib.Path(__file__).resolve().parent.parent
    run(project_root)
