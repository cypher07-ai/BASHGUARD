import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from sandbox import simulate_in_sandbox, format_sandbox_result

target = os.path.dirname(__file__)
cmd = f'rm -rf "{target}"'
print(f"Testing command: {cmd}\n")
r = simulate_in_sandbox(cmd)
print(format_sandbox_result(r))
