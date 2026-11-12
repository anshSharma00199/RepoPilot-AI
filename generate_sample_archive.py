#!/usr/bin/env python3
"""
Generates sample ZIP archives for testing RepoPilot AI:
Day 1:
1. sample_repository.zip — Valid nested Python repo with tests, manifests, and AST syntax error file.
2. attack_path_traversal.zip — Adversarial archive with ../ traversal sequence.
3. attack_absolute_path.zip — Adversarial archive with Unix absolute path.
4. attack_zip_bomb.zip — High-compression ratio archive.

Day 2 Execution Scenarios:
5. repo_passing.zip — All tests passing cleanly.
6. repo_failing.zip — Deterministic failing assertion.
7. repo_syntax_error.zip — Python syntax error during test collection.
8. repo_missing_deps.zip — Missing / unresolvable dependency in manifest.
9. repo_timeout.zip — Long-running test triggering execution timeout.
10. repo_forbidden_resource.zip — Attempting forbidden network access.
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from tests.fixtures.archive_factory import (
    create_sample_repo_zip,
    create_traversal_zip,
    create_absolute_path_zip,
    create_bomb_ratio_zip,
    create_repo_passing_zip,
    create_repo_failing_zip,
    create_repo_syntax_error_zip,
    create_repo_missing_deps_zip,
    create_repo_timeout_zip,
    create_repo_forbidden_resource_zip,
    create_demo_pricing_zip,
)

def main():
    root = Path(__file__).parent
    samples_dir = root / "sample_archives"
    samples_dir.mkdir(parents=True, exist_ok=True)

    print("Generating RepoPilot AI Test Archives...")

    # Day 1 Archives
    create_sample_repo_zip(samples_dir / "sample_repository.zip")
    print(f"[+] 1. sample_repository.zip (Valid nested repo)")

    with open(samples_dir / "attack_path_traversal.zip", "wb") as f:
        f.write(create_traversal_zip())
    print(f"[+] 2. attack_path_traversal.zip (Path traversal attack)")

    with open(samples_dir / "attack_absolute_path.zip", "wb") as f:
        f.write(create_absolute_path_zip(unix_style=True))
    print(f"[+] 3. attack_absolute_path.zip (Absolute path attack)")

    with open(samples_dir / "attack_zip_bomb.zip", "wb") as f:
        f.write(create_bomb_ratio_zip())
    print(f"[+] 4. attack_zip_bomb.zip (Zip bomb attack)")

    # Day 2 Scenario Archives
    create_repo_passing_zip(samples_dir / "repo_passing.zip")
    print(f"[+] 5. repo_passing.zip (All tests passing)")

    create_repo_failing_zip(samples_dir / "repo_failing.zip")
    print(f"[+] 6. repo_failing.zip (Deterministic failing assertion)")

    create_repo_syntax_error_zip(samples_dir / "repo_syntax_error.zip")
    print(f"[+] 7. repo_syntax_error.zip (Python syntax error)")

    create_repo_missing_deps_zip(samples_dir / "repo_missing_deps.zip")
    print(f"[+] 8. repo_missing_deps.zip (Missing dependency manifest)")

    create_repo_timeout_zip(samples_dir / "repo_timeout.zip")
    print(f"[+] 9. repo_timeout.zip (Deliberately long-running timeout)")

    create_repo_forbidden_resource_zip(samples_dir / "repo_forbidden_resource.zip")
    print(f"[+] 10. repo_forbidden_resource.zip (Forbidden resource access)")

    # Day 5 Demo Repository Archive
    create_demo_pricing_zip(samples_dir / "demo_order_pricing.zip")
    print(f"[+] 11. demo_order_pricing.zip (Realistic nested Python repo with deterministic bug)")

    print(f"\nAll sample archives successfully generated in: {samples_dir.resolve()}")


if __name__ == "__main__":
    main()
