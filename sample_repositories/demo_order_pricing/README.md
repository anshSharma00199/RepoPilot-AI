# Order Pricing Service — Demo Repository

A sample Python library demonstrating autonomous debugging and verification in RepoPilot AI.

## Project Structure
```
demo_order_pricing/
├── pyproject.toml
├── requirements.txt
├── src/
│   └── order_pricing/
│       ├── __init__.py
│       ├── core/
│       │   ├── __init__.py
│       │   └── pricing.py      # Implements calculate_discounted_price
│       └── services/
│           ├── __init__.py
│           └── tax_service.py  # Implements sales tax & total calculations
└── tests/
    ├── __init__.py
    ├── core/
    │   ├── __init__.py
    │   └── test_pricing.py     # Bug reproduction & regression tests
    └── services/
        ├── __init__.py
        └── test_tax_service.py # Unrelated passing tests
```

## Expected Behavior
- `calculate_discounted_price(price, discount_percent)` should return the final price after subtracting the discount.
  For example, a \$100 item with a 20% discount should cost \$80.00.
- `calculate_sales_tax(subtotal, tax_rate)` computes standard tax amounts.
- `calculate_order_total(subtotal, tax_rate, shipping)` computes the final invoice total.

## Running Tests
```bash
python -m pytest tests -v
```
