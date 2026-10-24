"""Test: generate a real working game."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from coder import generate_code, save_code, format_code_result

print("\nGenerating: 'write a number guessing game in python'\n")
result = generate_code("write a number guessing game in python")
save_code(result)
print(format_code_result(result, show_full_code=True))
print(f"\nSaved to: {result.file_saved_to}")
