import time
import asyncio
import re
from typing import Tuple, Optional, Dict, Any, List

from app.services.llm.interface import (
    LLMProvider,
    DiagnosticPromptInput,
    RawLLMDiagnosticOutput,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMInvalidOutputError,
)


class FakeLLMProvider(LLMProvider):
    """
    Deterministic simulated LLM provider for unit tests and local demonstrations.
    Produces schema-compliant diagnostic outputs and unified diffs based on observed context.
    """

    def __init__(
        self,
        simulated_behavior: Optional[str] = None,
        simulate_rate_limit: bool = False,
        simulate_timeout: bool = False,
        simulate_invalid_json: bool = False,
        simulate_invalid_diff: bool = False,
        simulate_insufficient_evidence: bool = False,
        **kwargs,
    ):
        self.simulated_behavior = simulated_behavior
        self.simulate_rate_limit = simulate_rate_limit or (simulated_behavior == "rate_limit")
        self.simulate_timeout = simulate_timeout or (simulated_behavior == "timeout")
        self.simulate_invalid_json = simulate_invalid_json or (simulated_behavior in ("invalid_json", "malformed_json"))
        self.simulate_invalid_diff = simulate_invalid_diff or (simulated_behavior in ("invalid_diff", "malformed_diff"))
        self.simulate_insufficient_evidence = simulate_insufficient_evidence or (simulated_behavior == "insufficient_evidence")

    def is_configured(self) -> Tuple[bool, str]:
        return True, "Simulated deterministic LLM provider active (testing mode)."

    async def diagnose(self, input_data: DiagnosticPromptInput) -> Tuple[RawLLMDiagnosticOutput, float]:
        start = time.time()
        await asyncio.sleep(0.05)  # brief async yield

        if self.simulate_rate_limit:
            raise LLMRateLimitError(
                error_code="RATE_LIMIT_EXCEEDED",
                message="Simulated provider rate limit exceeded (HTTP 429).",
            )

        if self.simulate_timeout:
            raise LLMTimeoutError(
                error_code="PROVIDER_TIMEOUT",
                message="Simulated provider request timed out.",
            )

        if self.simulate_invalid_json:
            raise LLMInvalidOutputError(
                error_code="INVALID_JSON_OUTPUT",
                message="Model returned malformed or non-JSON content.",
            )

        context = input_data.context_text
        summary = input_data.failure_summary

        # Check for Insufficient Evidence simulation
        if self.simulate_insufficient_evidence or "insufficient_evidence" in context.lower():
            duration = round(time.time() - start, 2)
            return RawLLMDiagnosticOutput(
                failure_summary="Test failure observed with missing or incomplete traceback frames.",
                root_cause_hypothesis="Unable to determine root cause due to absence of source file references in execution logs.",
                confidence_score=0.1,
                confidence_explanation="The retrieved context does not reference any existing source lines or modules in the repository.",
                is_insufficient_evidence=True,
                insufficient_evidence_reason="Traceback did not provide source lines or file location.",
                supporting_evidence=[],
                proposed_changes=[],
                unified_diff="",
                rationale="No patch proposed because evidence is insufficient to guarantee safety.",
                potential_regression_risks="Blind patching without line evidence risks creating regressions.",
                recommended_tests="Re-run tests with -vv and --tb=long to capture full frame information.",
                known_limitations="Log output was truncated or missing standard pytest markers.",
            ), duration

        # Check for Prompt Injection Defense
        has_prompt_injection = (
            ("IGNORE" in context and "INSTRUCTIONS" in context)
            or "SYSTEM OVERRIDE" in context
            or "MALICIOUS_PROMPT" in context
            or self.simulated_behavior == "prompt_injection"
        )
        if has_prompt_injection:
            duration = round(time.time() - start, 2)
            return RawLLMDiagnosticOutput(
                failure_summary="Detected prompt injection attempt in untrusted repository source code.",
                root_cause_hypothesis="Untrusted repository files attempted prompt injection to subvert system instructions.",
                confidence_score=0.9,
                confidence_explanation="The analysis detected adversarial override keywords in repo content.",
                is_insufficient_evidence=False,
                supporting_evidence=[],
                proposed_changes=[],
                unified_diff="",
                rationale="Refused to propose changes influenced by untrusted instructions.",
                potential_regression_risks="None; no code was modified.",
                recommended_tests="Review codebase for hostile injection artifacts.",
                known_limitations="Prompt injection defense blocks automatic patching for adversarial repositories.",
            ), duration

        # Check if testing invalid diff generation
        if self.simulate_invalid_diff or self.simulated_behavior == "malformed_diff":
            duration = round(time.time() - start, 2)
            return RawLLMDiagnosticOutput(
                failure_summary="Failing assertion in test suite.",
                root_cause_hypothesis="Intentional invalid diff test case.",
                confidence_score=0.7,
                confidence_explanation="Testing patch validator rejection of malformed diff syntax.",
                is_insufficient_evidence=False,
                supporting_evidence=[
                    {"file_path": "src/math_ops.py", "line_start": 1, "line_end": 5, "description": "Broken diff target"}
                ],
                proposed_changes=[{"file_path": "src/math_ops.py", "explanation": "Malformed diff"}],
                unified_diff="THIS IS NOT A VALID DIFF CONTENT",
                rationale="Testing patch syntax rejection.",
            ), duration

        # Repository-grounded demo scenario: RepoPilot shop project.
        # Keep the deterministic provider aligned with files that actually appear
        # in the retrieved repository context; never fall back to unrelated math fixtures.
        is_exact_shop_demo = (
            "tests/test_shop.py" in context
            and "src/shop.py" in context
            and "return subtotal + tax_rate" in context
            and "discount_percent / 10" in context
            and 'product.get("name") == product_id' in context
            and "sum(ratings) / len(ratings)" in context
            and "return code.upper()" in context
        )
        if is_exact_shop_demo:
            unified_diff = (
                "--- a/src/shop.py\n"
                "+++ b/src/shop.py\n"
                "@@ -3,5 +3,5 @@\n"
                " def calculate_total(prices, tax_rate=0.0):\n"
                "     \"\"\"Return subtotal plus tax.\"\"\"\n"
                "     subtotal = sum(prices)\n"
                "-    # Intentional bug: tax is added as a fixed amount, not a percentage.\n"
                "-    return subtotal + tax_rate\n"
                "+    # Apply tax_rate as a percentage of the subtotal.\n"
                "+    return subtotal * (1 + tax_rate)\n"
                "@@ -10,4 +10,4 @@\n"
                " def apply_discount(total, discount_percent):\n"
                "     \"\"\"Apply a percentage discount to a total.\"\"\"\n"
                "-    # Intentional bug: percentage is divided by 10 rather than 100.\n"
                "-    return total * (1 - discount_percent / 10)\n"
                "+    # Convert the percentage to a fraction before applying it.\n"
                "+    return total * (1 - discount_percent / 100)\n"
                "@@ -16,7 +16,7 @@\n"
                " def find_product(products, product_id):\n"
                "     \"\"\"Find a product by its id, or return None.\"\"\"\n"
                "     for product in products:\n"
                "-        # Intentional bug: compares the product name instead of its id.\n"
                "-        if product.get(\"name\") == product_id:\n"
                "+        # Match the requested product identifier.\n"
                "+        if product.get(\"id\") == product_id:\n"
                "             return product\n"
                "     return None\n"
                "@@ -25,4 +25,4 @@\n"
                " def average_rating(ratings):\n"
                "     \"\"\"Return average rating, or None when no ratings exist.\"\"\"\n"
                "-    # Intentional bug: empty input raises ZeroDivisionError.\n"
                "-    return sum(ratings) / len(ratings)\n"
                "+    # Empty rating lists have no average.\n"
                "+    return sum(ratings) / len(ratings) if ratings else None\n"
                "--- a/src/formatting.py\n"
                "+++ b/src/formatting.py\n"
                "@@ -3,4 +3,4 @@\n"
                " def normalize_coupon(code):\n"
                "     \"\"\"Trim whitespace and normalize a coupon code to uppercase.\"\"\"\n"
                "-    # Intentional bug: whitespace is not removed.\n"
                "-    return code.upper()\n"
                "+    # Normalize whitespace before changing case.\n"
                "+    return code.strip().upper()\n"
            )
            duration = round(time.time() - start, 2)
            return RawLLMDiagnosticOutput(
                failure_summary="Five assertions in tests/test_shop.py expose defects in tax, discount, product lookup, empty ratings, and coupon normalization.",
                root_cause_hypothesis="The shop helpers contain five independent implementation bugs. The proposed changes correct the percentage calculations, match products by id, handle an empty rating list, and trim coupon input before uppercasing.",
                confidence_score=0.98,
                confidence_explanation="The proposed changes directly address the assertions and traceback evidence from the uploaded shop repository.",
                is_insufficient_evidence=False,
                supporting_evidence=[],
                proposed_changes=[
                    {"file_path": "src/shop.py", "explanation": "Fix tax, discount, product-id lookup, and empty-rating handling."},
                    {"file_path": "src/formatting.py", "explanation": "Trim coupon whitespace before uppercasing."},
                ],
                unified_diff=unified_diff,
                rationale="Corrects the implementation defects in the repository's source files without weakening or changing the tests.",
                potential_regression_risks="Low; changes are limited to the functions covered by the failing tests.",
                recommended_tests="python -m pytest tests/test_shop.py -v --tb=short",
                known_limitations="This deterministic response is intended for the bundled RepoPilot shop demo. Other repositories require a configured real LLM provider for repository-specific diagnosis.",
            ), duration

        # Day 5 Demo Scenario: Order Pricing Discount Bug
        is_exact_pricing_demo = (
            "tests/core/test_pricing.py" in context
            and "src/order_pricing/core/pricing.py" in context
            and "test_calculate_discounted_price" in context
        )
        if is_exact_pricing_demo:
            unified_diff = (
                "--- a/src/order_pricing/core/pricing.py\n"
                "+++ b/src/order_pricing/core/pricing.py\n"
                "@@ -9,2 +9,2 @@\n"
                "     # BUG: Calculates discount amount instead of subtracting it from original price.\n"
                "-    return round(price * (discount_percent / 100.0), 2)\n"
                "+    return round(price * (1.0 - discount_percent / 100.0), 2)\n"
            )
            duration = round(time.time() - start, 2)
            return RawLLMDiagnosticOutput(
                failure_summary="AssertionError in test_calculate_discounted_price: expected $80.0, received $20.0.",
                root_cause_hypothesis="In src/order_pricing/core/pricing.py, calculate_discounted_price calculates only the discount amount instead of subtracting the discount from the original price.",
                confidence_score=0.96,
                confidence_explanation="Traceback and assertion assert 20.0 == 80.0 confirm that the function returned the discount amount (100 * 0.20 = 20) instead of the final discounted price (100 - 20 = 80).",
                is_insufficient_evidence=False,
                supporting_evidence=[
                    {
                        "file_path": "tests/core/test_pricing.py",
                        "line_start": 14,
                        "line_end": 18,
                        "description": "Failing test asserting 20% discount on $100 should yield $80",
                        "snippet": "assert calculate_discounted_price(100.0, 20.0) == 80.0",
                    },
                    {
                        "file_path": "src/order_pricing/core/pricing.py",
                        "line_start": 18,
                        "line_end": 22,
                        "description": "Buggy return statement returning discount amount",
                        "snippet": "return round(price * (discount_percent / 100.0), 2)",
                    },
                ],
                proposed_changes=[
                    {
                        "file_path": "src/order_pricing/core/pricing.py",
                        "explanation": "Subtract discount percentage from 1.0 to compute final discounted price: round(price * (1.0 - discount_percent / 100.0), 2).",
                    }
                ],
                unified_diff=unified_diff,
                rationale="Corrects the discount deduction formula to return the final payable price as expected by callers.",
                potential_regression_risks="Low; preserves input validation guards and standard decimal rounding.",
                recommended_tests="tests/core/test_pricing.py",
                known_limitations="Requires inputs to remain non-negative floats.",
            ), duration

        # Math demo is eligible only when those files are present in the CURRENT
        # repository inventory. Failure logs alone are not sufficient: stale job
        # state can otherwise make a different repository receive this canned patch.
        inventory_match = re.search(
            r"### ACTUAL UPLOADED REPOSITORY FILE INVENTORY ###\s*(.*?)(?:\n### |$)",
            context,
            flags=re.DOTALL,
        )
        repository_inventory = inventory_match.group(1) if inventory_match else ""
        is_exact_math_demo = (
            "tests/test_failing_math.py" in repository_inventory
            and "src/math_ops.py" in repository_inventory
            and "assert divide(10, 2) == 99" in context
        )
        if is_exact_math_demo:
            unified_diff = (
                "--- a/src/math_ops.py\n"
                "+++ b/src/math_ops.py\n"
                "@@ -1,3 +1,3 @@\n"
                " def divide(a, b):\n"
                "-    return a / b\n"
                "+    return 99 if (a == 10 and b == 2) else a / b\n"
            )
            # Alternative mathematically cleaner diff if test expected 5.0
            if "assert divide(10, 2) == 99" in context:
                unified_diff = (
                    "--- a/tests/test_failing_math.py\n"
                    "+++ b/tests/test_failing_math.py\n"
                    "@@ -6,3 +6,3 @@\n"
                    " def test_division_fail():\n"
                    "     # Intentional failing assertion\n"
                    "-    assert divide(10, 2) == 99\n"
                    "+    assert divide(10, 2) == 5.0\n"
                )

            duration = round(time.time() - start, 2)
            return RawLLMDiagnosticOutput(
                failure_summary="AssertionError in test_division_fail: divide(10, 2) evaluates to 5.0, not 99.",
                root_cause_hypothesis="The test 'test_division_fail' asserts an incorrect expected value (99 instead of 5.0).",
                confidence_score=0.95,
                confidence_explanation="Traceback and source lines clearly demonstrate that 10 / 2 = 5.0, while test asserts 99.",
                is_insufficient_evidence=False,
                supporting_evidence=[
                    {
                        "file_path": "tests/test_failing_math.py",
                        "line_start": 6,
                        "line_end": 9,
                        "description": "Failing assertion asserting divide(10, 2) == 99",
                        "snippet": "assert divide(10, 2) == 99",
                    },
                    {
                        "file_path": "src/math_ops.py",
                        "line_start": 1,
                        "line_end": 3,
                        "description": "Standard division function implementation",
                        "snippet": "def divide(a, b):\n    return a / b",
                    },
                ],
                proposed_changes=[
                    {
                        "file_path": "tests/test_failing_math.py",
                        "explanation": "Correct the expected test assertion from 99 to 5.0.",
                    }
                ],
                unified_diff=unified_diff,
                rationale="Aligns the test assertion with mathematical division specification.",
                potential_regression_risks="Low; only updates the erroneous test assertion.",
                recommended_tests="Run pytest tests/test_failing_math.py to verify pass.",
                known_limitations="None; failure was localized to single test assertion.",
            ), duration

        # Unknown repositories must never receive a canned patch for an unrelated fixture.
        # The fake provider is a deterministic demo/test provider, not a general-purpose AI.
        duration = round(time.time() - start, 2)
        return RawLLMDiagnosticOutput(
            failure_summary=summary or "A test failure was reported, but no repository-specific diagnosis is available.",
            root_cause_hypothesis=(
                "No safe repository-specific diagnosis is available from the simulated provider. "
                "Configure a real LLM provider to analyze this repository's own failing tests and source files."
            ),
            confidence_score=0.1,
            confidence_explanation=(
                "The active fake provider only supports explicitly defined demo fixtures. "
                "It will not invent file paths or propose a patch for an unrelated project."
            ),
            is_insufficient_evidence=True,
            insufficient_evidence_reason=(
                "This repository does not match a supported deterministic demo scenario, and the fake provider "
                "cannot reason reliably about arbitrary external code. Configure GEMINI_API_KEY and set "
                "LLM_PROVIDER=auto or gemini to enable repository-specific AI diagnosis."
            ),
            supporting_evidence=[],
            proposed_changes=[],
            unified_diff="",
            rationale="No patch was generated because a fabricated patch could target the wrong files or damage the repository.",
            potential_regression_risks="A patch must not be generated without repository-specific analysis.",
            recommended_tests="Review the captured pytest traceback and configure a real LLM provider for diagnosis.",
            known_limitations="FakeLLMProvider is for tests and supported demos only; it does not diagnose arbitrary repositories.",
        ), duration
