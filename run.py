#!/usr/bin/env python3
"""Protea entry point — launches Ring 0 Sentinel."""

import sys
import pathlib

# Ensure project root is on sys.path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from ring0.sentinel import main

if __name__ == "__main__":
    main()
