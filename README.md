# Protea

Self-evolving artificial life system. The program is a living organism — it can self-restructure, self-reproduce, and self-evolve.

## Architecture

Three-ring design running on a single Mac mini:

- **Ring 0 (Sentinel)** — Immutable physics layer. Supervises Ring 2, performs heartbeat monitoring, git snapshots, rollback on failure, fitness tracking. Pure Python stdlib, < 500 lines.
- **Ring 1 (Evolution Engine)** — Drives mutations via LLM. *(Phase 2)*
- **Ring 2 (Evolvable Code)** — The living code that evolves. Managed in its own git repo by Ring 0.

## Quick Start

```bash
# Run all tests
python -m pytest tests/test_ring0/ -v

# Start Sentinel (launches and supervises Ring 2)
python run.py
```

## Project Structure

```
protea/
├── ring0/                  # Sentinel (immutable, pure stdlib)
│   ├── sentinel.py         # Main supervisor loop
│   ├── heartbeat.py        # Ring 2 heartbeat monitoring
│   ├── git_manager.py      # Git snapshot + rollback
│   ├── fitness.py          # Fitness scoring (SQLite)
│   ├── parameter_seed.py   # Deterministic parameter generation
│   └── resource_monitor.py # CPU/memory/disk monitoring
├── ring1/                  # Evolution engine (Phase 2)
├── ring2/                  # Evolvable code (separate git repo)
│   └── main.py             # Seed behaviour
├── config/config.toml      # Configuration
├── tests/test_ring0/       # 247 tests
└── run.py                  # Entry point
```

## How It Works

1. Sentinel starts Ring 2 as a subprocess
2. Ring 2 writes a `.heartbeat` file every 2 seconds
3. Sentinel checks heartbeat freshness + PID liveness every 2 seconds
4. If Ring 2 dies: record failure, rollback to last known-good commit, restart
5. Each generation gets deterministic parameters from a seeded RNG

## Phase 1 Status

- [x] Ring 0 Sentinel — complete (493 lines, 0 external deps)
- [x] Heartbeat protocol
- [x] Git snapshot + rollback
- [x] SQLite fitness tracking
- [x] Resource monitoring (CPU/mem/disk)
- [x] 247 tests passing
- [ ] Ring 1 Evolution Engine (Phase 2)
- [ ] LLM-driven code mutation (Phase 2)
- [ ] Telegram notifications (Phase 2)
