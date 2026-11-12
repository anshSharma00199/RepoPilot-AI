#!/usr/bin/env python3
"""
RepoPilot AI — Root Quick Validation Script
Runs the test suite directly from the project root.
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from backend.test_runner import run_all_tests

if __name__ == "__main__":
    run_all_tests()
