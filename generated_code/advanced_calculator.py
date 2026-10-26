import math
import sys

class AdvancedCalculator:
    """A robust, feature-rich command-line calculator handling basic arithmetic,
    scientific functions, memory operations, and expression evaluation safely.
    """
    def __init__(self):
        self.memory = 0.0
        self.history = []

    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

    def multiply(self, a, b):
        return a * b

    def divide(self, a, b):
        if b == 0:
            raise ValueError("Error: Division by zero is undefined.")
        return a / b

    def power(self, a, b):
        return a ** b

    def square_root(self, a):
        if a < 0:
            raise ValueError("Error: Cannot compute square root of a negative number.")
        return math.sqrt(a)

    def logarithm(self, a):
        if a <= 0:
            raise ValueError("Error: Logarithm undefined for zero or negative numbers.")
        return math.log10(a)

    def sine(self, a):
        return math.sin(math.radians(a))

    def cosine(self, a):
        return math.cos(math.radians(a))

    def tangent(self, a):
        return math.tan(math.radians(a))

    def evaluate_expression(self, expr):
        """Safely evaluates basic mathematical expressions using restricted globals."""
        allowed_names = {
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'sqrt': math.sqrt,
            'log': math.log10,
            'pi': math.pi,
            'e': math.e
        }
        
        # Clean and validate input characters to prevent malicious execution
        safe_chars = set('0123456789+-*/().% *abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ')
        if not all(c in safe_chars for c in expr):
            raise ValueError("Error: Invalid characters detected in expression.")

        try:
            code = compile(expr, '<string>', 'eval')
            for name in code.co_names:
                if name not in allowed_names:
                    raise ValueError(f"Error: Use of unsupported function/variable '{name}'.")
            
            result = eval(code, {"__builtins__": {}}, allowed_names)
            return result
        except ZeroDivisionError:
            raise ValueError("Error: Division by zero in expression.")
        except Exception as e:
            raise ValueError(f"Error evaluating expression: {e}")

    def run(self):
        print("=" * 50)
        print("        WELCOME TO ADVANCED BASHGUARD CALCULATOR")
        print("=" * 50)
        print("Commands:")
        print("  basic    - Perform basic operations (+, -, *, /, ^)")
        print("  sci      - Perform scientific functions (sqrt, log, sin, cos, tan)")
        print("  expr     - Evaluate full mathematical expressions (e.g., 5 + 3 * 2)")
        print("  mem      - Memory operations (M+, M-, MR, MC)")
        print("  history  - View calculation history")
        print("  exit     - Exit the calculator")
        print("=" * 50)

        while True:
            try:
                command = input("
Calculator> ").strip().lower()
                
                if command == 'exit':
                    print("Thank you for using BashGuard Calculator. Goodbye!")
                    sys.exit(0)
                
                elif command == 'history':
                    if not self.history:
                        print("No history available yet.")
                    else:
                        print("--- Calculation History ---")
                        for item in self.history:
                            print(item)
                
                elif command == 'mem':
                    m_cmd = input(f"Current Memory: {self.memory}. Choose operation (M+ [val], M- [val], MR, MC): ").strip().lower()
                    parts = m_cmd.split()
                    action = parts[0]
                    
                    if action == 'mr':
                        print(f"Memory Value: {self.memory}")
                    elif action == 'mc':
                        self.memory = 0.0
                        print("Memory cleared.")
                    elif action in ['m+', 'm-']:
                        if len(parts) < 2:
                            print("Error: Please provide a value for memory operation.")
                            continue
                        val = float(parts[1])
                        if action == 'm+':
                            self.memory += val
                        else:
                            self.memory -= val
                        print(f"Updated Memory: {self.memory}")
                    else:
                        print("Unknown memory command.")

                elif command == 'basic':
                    op = input("Choose operation (+, -, *, /, ^): ").strip()
                    if op not in ['+', '-', '*', '/', '^']:
                        print("Error: Invalid operator.")
                        continue
                    
                    a = float(input("Enter first number: "))
                    b = float(input("Enter second number: "))
                    
                    if op == '+': res = self.add(a, b)
                    elif op == '-': res = self.subtract(a, b)
                    elif op == '*': res = self.multiply(a, b)
                    elif op == '/': res = self.divide(a, b)
                    elif op == '^': res = self.power(a, b)
                    
                    expr_str = f"{a} {op} {b} = {res}"
                    print(f"Result: {res}")
                    self.history.append(expr_str)

                elif command == 'sci':
                    print("Functions: sqrt, log (base 10), sin, cos, tan")
                    func = input("Enter function name: ").strip().lower()
                    val = float(input("Enter value: "))
                    
                    if func == 'sqrt': res = self.square_root(val)
                    elif func == 'log': res = self.logarithm(val)
                    elif func == 'sin': res = self.sine(val)
                    elif func == 'cos': res = self.cosine(val)
                    elif func == 'tan': res = self.tangent(val)
                    else:
                        print("Error: Unknown scientific function.")
                        continue

                    expr_str = f"{func}({val}) = {res}"
                    print(f"Result: {res}")
                    self.history.append(expr_str)

                elif command == 'expr':
                    expression = input("Enter expression (e.g., (5 + 3) * sqrt(16)): ")
                    res = self.evaluate_expression(expression)
                    expr_str = f"{expression} = {res}"
                    print(f"Result: {res}")
                    self.history.append(expr_str)

                else:
                    print("Unknown command. Type 'basic', 'sci', 'expr', 'mem', 'history', or 'exit'.")

            except ValueError as ve:
                print(ve)
            except Exception as e:
                print(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    calc = AdvancedCalculator()
    calc.run()
