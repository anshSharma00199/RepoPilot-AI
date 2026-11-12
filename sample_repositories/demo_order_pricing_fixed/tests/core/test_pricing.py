import pytest
import sys
from pathlib import Path

# Ensure src is on sys.path
src_dir = Path(__file__).resolve().parent.parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from order_pricing.core.pricing import calculate_discounted_price


def test_calculate_discounted_price():
    """Reproduces deterministic bug in discount calculation."""
    assert calculate_discounted_price(100.0, 20.0) == 80.0


def test_zero_discount_regression():
    """Regression test: 0% discount must return original price."""
    assert calculate_discounted_price(75.50, 0.0) == 75.50


def test_invalid_inputs_regression():
    """Regression test: negative price or discount > 100 must raise ValueError."""
    with pytest.raises(ValueError, match="Price cannot be negative"):
        calculate_discounted_price(-15.0, 10.0)

    with pytest.raises(ValueError, match="Discount percent must be between 0 and 100"):
        calculate_discounted_price(100.0, 150.0)
