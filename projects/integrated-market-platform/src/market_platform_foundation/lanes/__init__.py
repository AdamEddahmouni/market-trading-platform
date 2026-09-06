"""Lane vocabularies: discovery screens, workspace modules, and evidence LaneId.

These three naming systems are distinct. A discovery lane is not a workspace
module and is not a research-family ``LaneId``. Crosswalks live in
``vocabulary.py``.
"""

from .vocabulary import (
    DISCOVERY_LANES,
    DISCOVERY_LANE_TO_WORKSPACE_MODULE,
    LANE_ID_TO_WORKSPACE_MODULE,
    UI_EVIDENCE_LANE_TO_WORKSPACE_MODULE,
    workspace_module_for_discovery_lane,
    workspace_module_for_lane_id,
    workspace_module_for_ui_evidence_lane,
)

__all__ = [
    "DISCOVERY_LANES",
    "DISCOVERY_LANE_TO_WORKSPACE_MODULE",
    "LANE_ID_TO_WORKSPACE_MODULE",
    "UI_EVIDENCE_LANE_TO_WORKSPACE_MODULE",
    "workspace_module_for_discovery_lane",
    "workspace_module_for_lane_id",
    "workspace_module_for_ui_evidence_lane",
]
