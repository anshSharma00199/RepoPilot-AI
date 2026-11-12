"""Core pricing module providing discount and price calculations."""


def calculate_discounted_price(price: float, discount_percent: float) -> float:
    """
    Calculates the final payable price after applying a percentage discount.

    Args:
        price: Original item price in dollars (must be non-negative).
        discount_percent: Percentage discount to apply (0 to 100).

    Returns:
        The final price after subtracting the discount, rounded to 2 decimal places.

    Raises:
        ValueError: If price is negative or discount_percent is outside [0, 100].
    """
    if price < 0.0:
        raise ValueError("Price cannot be negative.")
    if discount_percent < 0.0 or discount_percent > 100.0:
        raise ValueError("Discount percent must be between 0 and 100.")

    # BUG: Calculates discount amount instead of subtracting it from original price.
    return round(price * (discount_percent / 100.0), 2)
