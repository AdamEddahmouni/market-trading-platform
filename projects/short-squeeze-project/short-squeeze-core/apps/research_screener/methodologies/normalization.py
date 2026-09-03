def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def linear(value: float, low: float, high: float) -> float:
    if high <= low:
        raise ValueError("high must be greater than low")
    return round(_clamp(100.0 * (float(value) - low) / (high - low)), 4)


def inverse_linear(value: float, low: float, high: float) -> float:
    return round(100.0 - linear(value, low, high), 4)
