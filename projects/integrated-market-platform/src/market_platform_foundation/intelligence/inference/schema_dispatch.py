"""Provider schema selection shared by News and market evidence packets."""
from .contracts import IntelligenceTaskType


def schema_for_packet(packet):
    if packet.task_type == IntelligenceTaskType.SCREENER_CANDIDATE_REDUCTION:
        return packet.output_schema
    from .screener_synthesis import output_json_schema
    return output_json_schema([article.event_id for article in packet.articles])
