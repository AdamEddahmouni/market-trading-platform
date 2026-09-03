from .models import MethodologyResult


def serialize_result(result: MethodologyResult) -> dict:
    return result.as_dict()
