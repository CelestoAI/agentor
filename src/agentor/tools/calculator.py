from agentor.tools.base import BaseTool


class Calculator(BaseTool):
    name = "calculator"
    description = "Perform basic arithmetic operations"

    def run(self, operation: str, a: float, b: float) -> str:
        """
        Perform a basic arithmetic operation.

        Args:
            operation: The operation to perform. One of 'add', 'subtract', 'multiply', 'divide'.
            a: The first number.
            b: The second number.
        """
        if operation == "add":
            return str(a + b)
        elif operation == "subtract":
            return str(a - b)
        elif operation == "multiply":
            return str(a * b)
        elif operation == "divide":
            if b == 0:
                return "Error: Division by zero"
            return str(a / b)
        else:
            return f"Error: Unknown operation '{operation}'"
