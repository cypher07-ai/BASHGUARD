"""Live sandbox demo — shows what rm -rf, del, chmod would do to REAL directories."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from sandbox import simulate_in_sandbox, format_sandbox_result, is_raw_command, detect_danger_level

project_dir = os.path.dirname(__file__)
desktop = os.path.join(os.path.expanduser("~"), "Desktop")

tests = [
    f'rm -rf "{project_dir}"',
    f'del /s /q "{desktop}"',
    f'chmod 777 "{project_dir}"',
]

for i, cmd in enumerate(tests, 1):
    print(f"\n{'#'*60}")
    print(f"  DEMO {i}: {cmd}")
    print(f"  Raw command? {is_raw_command(cmd)} | Danger: {detect_danger_level(cmd)}")
    print(f"{'#'*60}")
    r = simulate_in_sandbox(cmd)
    print(format_sandbox_result(r))
    print()
