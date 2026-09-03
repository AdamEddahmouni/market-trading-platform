import subprocess
import sys

from squeeze_core.contracts.identifiers import OBSERVATION_NAMESPACE
from squeeze_core.metrics.identifiers import METRIC_NAMESPACE, deterministic_metric_id


def test_metric_namespace_differs_from_observation_namespace():
    assert METRIC_NAMESPACE != OBSERVATION_NAMESPACE


def test_deterministic_metric_id_is_stable_within_a_process():
    identity = {"a": 1, "b": "two"}
    assert deterministic_metric_id(identity) == deterministic_metric_id(identity)


def test_deterministic_metric_id_is_stable_across_key_order():
    assert deterministic_metric_id({"a": 1, "b": 2}) == deterministic_metric_id({"b": 2, "a": 1})


def test_deterministic_metric_id_is_stable_across_a_fresh_process():
    identity_json = '{"a": 1, "b": "two"}'
    script = (
        "import json;"
        "from squeeze_core.metrics.identifiers import deterministic_metric_id;"
        f"print(deterministic_metric_id(json.loads('{identity_json}')))"
    )
    first = deterministic_metric_id({"a": 1, "b": "two"})
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    assert completed.stdout.strip() == first


def test_metric_id_never_collides_with_a_similarly_shaped_observation_id():
    from squeeze_core.contracts.identifiers import deterministic_observation_id

    identity = {"a": 1, "b": "two"}
    assert deterministic_metric_id(identity) != deterministic_observation_id(identity)
