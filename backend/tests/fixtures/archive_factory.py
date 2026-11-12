import io
import os
import zipfile
from pathlib import Path
from typing import Dict, Optional


def create_sample_repo_zip(dest_path: Optional[Path] = None) -> bytes:
    """Packages the fixture sample_repo directory into a valid ZIP archive."""
    fixture_dir = Path(__file__).parent / "sample_repo"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("assets/logo.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4")
        if fixture_dir.exists():
            for root, dirs, files in os.walk(fixture_dir):
                for f in files:
                    full_path = Path(root) / f
                    rel_path = full_path.relative_to(fixture_dir).as_posix()
                    zf.write(full_path, arcname=rel_path)

    data = buf.getvalue()
    if dest_path:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
    return data


def create_malformed_zip() -> bytes:
    """Returns invalid, corrupted bytes that fail ZIP signature check."""
    return b"PK\x03\x04\x00\x00\x00\x00CORRUPTED_HEADER_DATA_NOT_A_VALID_ARCHIVE"


def create_traversal_zip() -> bytes:
    """Creates a ZIP archive containing path traversal sequences."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../evil_escape.py", "import os; print('malicious')\n")
        zf.writestr("safe_dir/../../escaped.txt", "escaped content\n")
        zf.writestr("normal.py", "x = 1\n")
    return buf.getvalue()


def create_absolute_path_zip(unix_style: bool = True) -> bytes:
    """Creates a ZIP archive containing absolute file paths."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        if unix_style:
            zf.writestr("/etc/evil_config.conf", "malicious_setting=1\n")
        else:
            zf.writestr("C:/Windows/System32/evil.dll", "evil\n")
        zf.writestr("valid.py", "a = 2\n")
    return buf.getvalue()


def create_symlink_zip() -> bytes:
    """Creates a ZIP archive with a Unix symlink entry."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("target.txt", "hello\n")
        zi = zipfile.ZipInfo("symlink_to_target")
        zi.external_attr = 0o120777 << 16
        zf.writestr(zi, "target.txt")
    return buf.getvalue()


def create_bomb_ratio_zip() -> bytes:
    """Creates a ZIP bomb with massive compression ratio."""
    buf = io.BytesIO()
    huge_data = b"\x00" * (10 * 1024 * 1024)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("huge_zeroes.dat", huge_data)
    return buf.getvalue()



def create_oversized_file_zip(
    size_bytes: int = 30 * 1024 * 1024,
    dest_path: Optional[Path] = None,
) -> bytes:
    """Creates a ZIP containing a file larger than the configured size limit."""
    buf = io.BytesIO()

    # Write actual content so the ZIP declares the correct uncompressed size.
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("oversized.bin", b"A" * size_bytes)

    data = buf.getvalue()

    if dest_path:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)

    return data



# -------------------------------------------------------------
# Day 2 Execution Scenario Test Repositories
# -------------------------------------------------------------

def create_repo_passing_zip(dest_path: Optional[Path] = None) -> bytes:
    """Scenario 1: All tests passing cleanly."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "src/calculator.py",
            "def add(a, b):\n    return a + b\n\ndef multiply(a, b):\n    return a * b\n",
        )
        zf.writestr(
            "tests/test_calculator.py",
            "from src.calculator import add, multiply\n\n"
            "def test_addition():\n    assert add(2, 3) == 5\n\n"
            "def test_multiplication():\n    assert multiply(4, 5) == 20\n",
        )
        zf.writestr("pytest.ini", "[pytest]\ntestpaths = tests\n")
        zf.writestr("requirements.txt", "# Zero external runtime dependencies required\n")

    data = buf.getvalue()
    if dest_path:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
    return data


def create_repo_failing_zip(dest_path: Optional[Path] = None) -> bytes:
    """Scenario 2: A deterministic failing assertion."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "src/math_ops.py",
            "def divide(a, b):\n    return a / b\n",
        )
        zf.writestr(
            "tests/test_failing_math.py",
            "from src.math_ops import divide\n\n"
            "def test_addition_pass():\n    assert 1 + 1 == 2\n\n"
            "def test_division_fail():\n    # Intentional failing assertion\n    assert divide(10, 2) == 99\n",
        )
        zf.writestr("pytest.ini", "[pytest]\ntestpaths = tests\n")

    data = buf.getvalue()
    if dest_path:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
    return data


def create_repo_syntax_error_zip(dest_path: Optional[Path] = None) -> bytes:
    """Scenario 3: A Python syntax error in test/source."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "tests/test_syntax_error.py",
            "# Deliberate syntax error\ndef broken_syntax(\n    # Unclosed parentheses\n    x = 10\n",
        )
        zf.writestr("pytest.ini", "[pytest]\ntestpaths = tests\n")

    data = buf.getvalue()
    if dest_path:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
    return data


def create_repo_missing_deps_zip(dest_path: Optional[Path] = None) -> bytes:
    """Scenario 4: Missing dependencies / unresolvable requirement."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "requirements.txt",
            "non_existent_pkg_xyz==99.9.9\n",
        )
        zf.writestr(
            "tests/test_app.py",
            "def test_dummy():\n    assert True\n",
        )
        zf.writestr("pytest.ini", "[pytest]\ntestpaths = tests\n")

    data = buf.getvalue()
    if dest_path:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
    return data


def create_repo_timeout_zip(dest_path: Optional[Path] = None) -> bytes:
    """Scenario 5: Deliberately long-running test / timeout trigger."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "tests/test_timeout.py",
            "import time\n\ndef test_infinite_loop():\n    # Sleep for 1000 seconds to test timeout\n    time.sleep(1000)\n",
        )
        zf.writestr("pytest.ini", "[pytest]\ntestpaths = tests\n")

    data = buf.getvalue()
    if dest_path:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
    return data


def create_repo_forbidden_resource_zip(dest_path: Optional[Path] = None) -> bytes:
    """Scenario 6: Test attempting to access forbidden network or host resource."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "tests/test_security.py",
            "import urllib.request\n\n"
            "def test_network_access():\n"
            "    # Attempt forbidden outbound connection under --network=none sandbox\n"
            "    urllib.request.urlopen('http://169.254.169.254', timeout=1)\n",
        )
        zf.writestr("pytest.ini", "[pytest]\ntestpaths = tests\n")

    data = buf.getvalue()
    if dest_path:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
    return data


# -------------------------------------------------------------
# Day 5 Demonstration Realistic Repository
# -------------------------------------------------------------

def create_demo_pricing_zip(dest_path: Optional[Path] = None, fixed: bool = False) -> bytes:
    """
    Day 5 Demo Repository:
    Nested Python project with deterministic bug in calculate_discounted_price.
    Tests: 1 bug reproduction test, 2 regression tests, 3 unrelated passing tests.
    """
    buf = io.BytesIO()
    pricing_code_buggy = (
        '"""Core pricing module."""\n\n'
        'def calculate_discounted_price(price: float, discount_percent: float) -> float:\n'
        '    """Calculates price after discount."""\n'
        '    if price < 0.0:\n'
        '        raise ValueError("Price cannot be negative.")\n'
        '    if discount_percent < 0.0 or discount_percent > 100.0:\n'
        '        raise ValueError("Discount percent must be between 0 and 100.")\n'
        '    # BUG: Calculates discount amount instead of subtracting it from original price.\n'
        '    return round(price * (discount_percent / 100.0), 2)\n'
    )
    pricing_code_fixed = (
        '"""Core pricing module."""\n\n'
        'def calculate_discounted_price(price: float, discount_percent: float) -> float:\n'
        '    """Calculates price after discount."""\n'
        '    if price < 0.0:\n'
        '        raise ValueError("Price cannot be negative.")\n'
        '    if discount_percent < 0.0 or discount_percent > 100.0:\n'
        '        raise ValueError("Discount percent must be between 0 and 100.")\n'
        '    # FIXED: Subtracts discount from price\n'
        '    return round(price * (1.0 - discount_percent / 100.0), 2)\n'
    )

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("src/order_pricing/__init__.py", "from order_pricing.core.pricing import calculate_discounted_price\n")
        zf.writestr("src/order_pricing/core/__init__.py", "from order_pricing.core.pricing import calculate_discounted_price\n")
        zf.writestr("src/order_pricing/core/pricing.py", pricing_code_fixed if fixed else pricing_code_buggy)
        zf.writestr("src/order_pricing/services/__init__.py", "")
        zf.writestr(
            "src/order_pricing/services/tax_service.py",
            'def calculate_sales_tax(subtotal: float, tax_rate_percent: float) -> float:\n'
            '    if subtotal < 0 or tax_rate_percent < 0:\n'
            '        raise ValueError("Negative values not allowed")\n'
            '    return round(subtotal * (tax_rate_percent / 100.0), 2)\n\n'
            'def calculate_order_total(subtotal: float, tax_rate_percent: float, shipping: float = 0.0) -> float:\n'
            '    if shipping < 0:\n'
            '        raise ValueError("Shipping cannot be negative")\n'
            '    return round(subtotal + calculate_sales_tax(subtotal, tax_rate_percent) + shipping, 2)\n'
        )
        zf.writestr("tests/__init__.py", "")
        zf.writestr("tests/core/__init__.py", "")
        zf.writestr(
            "tests/core/test_pricing.py",
            "import pytest\n"
            "from order_pricing.core.pricing import calculate_discounted_price\n\n"
            "def test_calculate_discounted_price():\n"
            "    # Reproduces deterministic bug: $100 with 20% discount should be $80\n"
            "    assert calculate_discounted_price(100.0, 20.0) == 80.0\n\n"
            "def test_zero_discount_regression():\n"
            "    assert calculate_discounted_price(75.50, 0.0) == 75.50\n\n"
            "def test_invalid_inputs_regression():\n"
            "    with pytest.raises(ValueError):\n"
            "        calculate_discounted_price(-15.0, 10.0)\n"
            "    with pytest.raises(ValueError):\n"
            "        calculate_discounted_price(100.0, 150.0)\n"
        )
        zf.writestr("tests/services/__init__.py", "")
        zf.writestr(
            "tests/services/test_tax_service.py",
            "import pytest\n"
            "from order_pricing.services.tax_service import calculate_sales_tax, calculate_order_total\n\n"
            "def test_calculate_sales_tax_unrelated():\n"
            "    assert calculate_sales_tax(100.0, 8.25) == 8.25\n\n"
            "def test_calculate_order_total_unrelated():\n"
            "    assert calculate_order_total(50.0, 10.0, shipping=5.0) == 60.0\n"
        )
        zf.writestr("pyproject.toml", "[tool.pytest.ini_options]\ntestpaths = ['tests']\n")
        zf.writestr("requirements.txt", "# Pure standard library\npytest>=7.0.0\n")
        zf.writestr("pytest.ini", "[pytest]\ntestpaths = tests\n")
        zf.writestr("README.md", "# Order Pricing Service — Demo Repository\n")

    data = buf.getvalue()
    if dest_path:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
    return data

