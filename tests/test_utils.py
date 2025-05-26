import pytest
from app.utils.validation import validate_amount, is_valid_uuid
from app.utils.helpers import generate_merchant_reference
import time


def test_validate_amount():
    """Test amount validation."""
    # Test valid amounts
    assert validate_amount("10.00")[0] is True
    assert validate_amount("0.01")[0] is True
    assert validate_amount("999999.99")[0] is True

    # Test invalid amounts
    assert validate_amount("0")[0] is False
    assert validate_amount("-10.00")[0] is False
    assert validate_amount("1000000.00")[0] is False
    assert validate_amount("10.999")[0] is False
    assert validate_amount("invalid")[0] is False


def test_is_valid_uuid():
    """Test UUID validation."""
    # Test valid UUIDs
    assert is_valid_uuid("123e4567-e89b-12d3-a456-426614174000") is True
    assert is_valid_uuid("123e4567-e89b-12d3-a456-426614174000".upper()) is True

    # Test invalid UUIDs
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
