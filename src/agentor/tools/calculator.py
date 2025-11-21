from agentor.tools.base import BaseTool, capability


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "Perform basic arithmetic operations"

    @capability
    def add(self, a: float, b: float) -> str:
        """
        Add two numbers.

        Args:
            a: The first number.
            b: The second number.
        """
        return str(a + b)

    @capability
    def subtract(self, a: float, b: float) -> str:
        """
        Subtract two numbers.

        Args:
            a: The first number.
            b: The second number.
        """
        return str(a - b)

    @capability
    def multiply(self, a: float, b: float) -> str:
        """
        Multiply two numbers.

        Args:
            a: The first number.
            b: The second number.
        """
        return str(a * b)

    @capability
    def divide(self, a: float, b: float) -> str:
        """
        Divide two numbers.

        Args:
            a: The first number.
            b: The second number (divisor).
        """
        if b == 0:
            return "Error: Division by zero"
        return str(a / b)
