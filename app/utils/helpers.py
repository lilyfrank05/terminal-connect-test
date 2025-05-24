import time


def generate_merchant_reference():
    """Generate a default merchant reference using Unix timestamp"""
    return str(int(time.time()))
