"""BUILD 09 detector/router errors."""


class DetectionError(ValueError):
    pass


class DetectionInputError(DetectionError):
    pass


class RoutingConfigurationError(ValueError):
    pass


__all__ = ["DetectionError", "DetectionInputError", "RoutingConfigurationError"]
