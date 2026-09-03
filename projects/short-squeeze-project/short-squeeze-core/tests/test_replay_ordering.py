import pytest

from squeeze_core.contracts import ReplayMode
from squeeze_core.replay import ReplayEngine, ReplayValidationError


def test_ordering_uses_effective_then_source_then_sequence_then_id(make_observation) -> None:
    observations = [
        make_observation("later-effective", offset_seconds=2, observation_id="05"),
        make_observation("later-source", source_offset_seconds=1, observation_id="04"),
        make_observation("sequence-two", sequence_number=2, observation_id="03"),
        make_observation("sequence-one-z", sequence_number=1, observation_id="02"),
        make_observation("sequence-one-a", sequence_number=1, observation_id="01"),
    ]
    result = ReplayEngine(mode=ReplayMode.NORMALIZED).replay(observations)
    assert result.emitted_observation_ids == (
        "01",
        "02",
        "03",
        "04",
        "05",
    )
    assert tuple(item.source_record_id for item in result.observations) == (
        "sequence-one-a",
        "sequence-one-z",
        "sequence-two",
        "later-source",
        "later-effective",
    )


def test_strict_mode_rejects_out_of_order_input(make_observation) -> None:
    observations = [
        make_observation("second", offset_seconds=1),
        make_observation("first", offset_seconds=0),
    ]
    with pytest.raises(ReplayValidationError, match="out of order"):
        ReplayEngine(mode=ReplayMode.STRICT).replay(observations)


def test_normalized_mode_reorders_and_records_diagnostic(make_observation) -> None:
    observations = [
        make_observation("second", offset_seconds=1),
        make_observation("first", offset_seconds=0),
    ]
    result = ReplayEngine(mode=ReplayMode.NORMALIZED).replay(observations)
    assert [item.source_record_id for item in result.observations] == ["first", "second"]
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == "INPUT_ORDER_NORMALIZED"


@pytest.mark.parametrize("mode", [ReplayMode.STRICT, ReplayMode.NORMALIZED])
def test_duplicate_observation_ids_are_rejected(mode: ReplayMode, make_observation) -> None:
    observations = [
        make_observation("first", observation_id="duplicate"),
        make_observation("second", offset_seconds=1, observation_id="duplicate"),
    ]
    with pytest.raises(ReplayValidationError, match="duplicate observation_id"):
        ReplayEngine(mode=mode).replay(observations)


def test_sequence_number_is_considered_only_after_timestamps(make_observation) -> None:
    early = make_observation("early-high-sequence", offset_seconds=0, sequence_number=99)
    late = make_observation("late-low-sequence", offset_seconds=1, sequence_number=1)
    result = ReplayEngine(mode=ReplayMode.NORMALIZED).replay([late, early])
    assert [item.source_record_id for item in result.observations] == [
        "early-high-sequence",
        "late-low-sequence",
    ]
