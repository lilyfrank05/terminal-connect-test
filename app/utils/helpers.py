import time


def generate_merchant_reference():
    """Generate a default merchant reference using Unix timestamp"""
    return str(int(time.time()))


def is_charge_anywhere_tid(tid):
    """Check if TID starts with 'WP' (Charge Anywhere TID)"""
    return tid and tid.startswith("WP")
