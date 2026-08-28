#!/usr/bin/env python3
"""CHI-112: Activity by Manager Y-axis uses current franchise names, never dashes."""
import runpy
import sys
from pathlib import Path

ns = runpy.run_path(str(Path(__file__).with_name("test_chi112.py")))
sys.exit(ns["main"]())
