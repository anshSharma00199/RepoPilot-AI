import pytest
import unittest
from src.calculator import add, divide, Calculator


def test_add_function():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0


def test_divide_zero():
    with pytest.raises(ValueError):
        divide(10, 0)


class TestCalculatorClass(unittest.TestCase):
    def setUp(self):
        self.calc = Calculator(precision=2)

    def test_compute_add(self):
        result = self.calc.compute("add", 10.555, 2.444)
        self.assertEqual(result, 13.0)

    def test_compute_div(self):
        result = self.calc.compute("div", 10, 3)
        self.assertEqual(result, 3.33)
