"""Tax and order calculation service."""


def calculate_sales_tax(subtotal: float, tax_rate_percent: float) -> float:
    """
    Calculates sales tax on an order subtotal.

    Args:
        subtotal: Pre-tax subtotal in dollars.
        tax_rate_percent: Tax percentage (e.g. 8.25 for 8.25%).

    Returns:
        Tax amount rounded to 2 decimal places.
    """
    if subtotal < 0.0 or tax_rate_percent < 0.0:
        raise ValueError("Subtotal and tax rate must be non-negative.")

    return round(subtotal * (tax_rate_percent / 100.0), 2)


def calculate_order_total(subtotal: float, tax_rate_percent: float, shipping: float = 0.0) -> float:
    """
    Calculates final invoice order total including tax and shipping.

    Args:
        subtotal: Pre-tax subtotal in dollars.
        tax_rate_percent: Tax percentage.
        shipping: Shipping cost in dollars.

    Returns:
        Total invoice payable rounded to 2 decimal places.
    """
    if shipping < 0.0:
        raise ValueError("Shipping cost cannot be negative.")

    tax = calculate_sales_tax(subtotal, tax_rate_percent)
    return round(subtotal + tax + shipping, 2)
