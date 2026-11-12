def add(a: float, b: float) -> float:
    """Adds two numbers."""
    return a + b


def divide(a: float, b: float) -> float:
    """Divides a by b."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


class Calculator:
    """Basic calculator service."""
    def __init__(self, precision: int = 2):
        self.precision = precision

    def compute(self, op: str, a: float, b: float) -> float:
        if op == "add":
            return round(add(a, b), self.precision)
        elif op == "div":
            return round(divide(a, b), self.precision)
        raise ValueError(f"Unknown operation: {op}")
