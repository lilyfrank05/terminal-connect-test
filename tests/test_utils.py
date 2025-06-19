import pytest
from app.utils.validation import validate_amount, is_valid_uuid
from app.utils.helpers import generate_merchant_reference
import time


def test_validate_amount():
    """Test amount validation."""
    # Test valid amounts
    assert validate_amount("10.00") == (True, None)
    assert validate_amount("0.01") == (True, None)
    assert validate_amount("999999.99") == (True, None)
    assert validate_amount("252") == (True, None)

    # Test invalid amounts and error messages
    assert validate_amount("0") == (False, "Amount must be greater than zero")
    assert validate_amount("-10.00") == (False, "Amount must be greater than zero")
    assert validate_amount("1000000.00") == (
        False,
        "Amount must be less than 1,000,000",
    )
    assert validate_amount("10.999") == (
        False,
        "Amount must have at most 2 decimal places",
    )
    assert validate_amount("invalid") == (False, "Invalid amount format")


def test_is_valid_uuid():
    """Test UUID v4 validation strictly."""
    # Valid v4 UUID
    assert is_valid_uuid("550e8400-e29b-41d4-a716-446655440000") is True
    # Valid v4 UUID uppercase
    assert is_valid_uuid("550E8400-E29B-41D4-A716-446655440000") is True
    # Valid v1 UUID (should fail)
    assert is_valid_uuid("6fa459ea-ee8a-11d2-9902-000c29e7c97b") is False
    # Valid v3 UUID (should fail)
    assert is_valid_uuid("f47ac10b-58cc-3372-a567-0e02b2c3d479") is False
    # Valid v5 UUID (should fail)
    assert is_valid_uuid("987192a0-4c3a-5e5a-9b41-31b0b3c6e2de") is False
    # Malformed UUID (should fail)
    assert is_valid_uuid("invalid-uuid") is False
    assert is_valid_uuid("123e4567-e89b-12d3-a456-42661417400") is False  # Too short
    assert is_valid_uuid("123e4567-e89b-12d3-a456-4266141740000") is False  # Too long
    assert (
        is_valid_uuid("123e4567-e89b-12d3-x456-426614174000") is False
    )  # Invalid character


def test_generate_merchant_reference():
    """Test merchant reference generation."""
    # Generate two references
    ref1 = generate_merchant_reference()
    time.sleep(1)  # Wait a second to ensure different timestamps
    ref2 = generate_merchant_reference()

    # Check that they are different
    assert ref1 != ref2

    # Check that they are valid timestamps
    assert ref1.isdigit()
    assert ref2.isdigit()

    # Check that they are recent
    current_time = int(time.time())
    assert abs(current_time - int(ref1)) < 10
    assert abs(current_time - int(ref2)) < 10
