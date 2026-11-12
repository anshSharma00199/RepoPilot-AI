import pytest
import sys
from pathlib import Path

# Ensure src is on sys.path
src_dir = Path(__file__).resolve().parent.parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from order_pricing.services.tax_service import calculate_sales_tax, calculate_order_total


def test_calculate_sales_tax_unrelated():
    """Unrelated passing test: standard sales tax calculation."""
    tax = calculate_sales_tax(100.0, 8.25)
    assert tax == 8.25


def test_calculate_order_total_unrelated():
    """Unrelated passing test: full order total calculation with tax and shipping."""
    total = calculate_order_total(50.0, 10.0, shipping=5.0)
    assert total == 60.0  # 50.0 + 5.0 (tax) + 5.0 (shipping) = 60.0


def test_invalid_tax_unrelated():
    """Unrelated passing test: negative shipping or tax rate raises ValueError."""
    with pytest.raises(ValueError):
        calculate_sales_tax(-10.0, 5.0)

    with pytest.raises(ValueError):
        calculate_order_total(100.0, 5.0, shipping=-1.0)
