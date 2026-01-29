"""Logging utility functions."""


def mask_amount(amount: float, show_relative: bool = True) -> str:
    """
    Mask financial amounts in logs to prevent exposure of sensitive values.
    
    Args:
        amount: The amount to mask
        show_relative: If True, show relative scale (e.g., "~$X.XXk") instead of exact amount
    
    Returns:
        Masked string representation (e.g., "~$5.00k" instead of "$5000.00")
    """
    if show_relative:
        if amount >= 1000000:
            return f"~${amount/1000000:.2f}M"
        elif amount >= 1000:
            return f"~${amount/1000:.2f}k"
        else:
            return f"~${amount:.2f}"
    else:
        return "[REDACTED]"
