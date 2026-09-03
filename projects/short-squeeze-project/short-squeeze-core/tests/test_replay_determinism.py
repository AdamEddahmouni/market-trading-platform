import time

from squeeze_core.contracts import ReplayMode
from squeeze_core.replay import ReplayClock, ReplayEngine, ReplayValidationError


def test_repeated_replay_produces_identical_bytes_and_hash(make_observation) -> None:
    observations = [
        make_observation("first"),
        make_observation("second", offset_seconds=1),
    ]
    first = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    second = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    assert first.to_bytes() == second.to_bytes()
    assert first.result_hash == second.result_hash


def test_registered_consumers_receive_exact_emitted_order(make_observation) -> None:
    seen: list[str] = []
    engine = ReplayEngine(mode=ReplayMode.NORMALIZED)
    engine.register_consumer(lambda observation, clock: seen.append(observation.source_record_id))
    result = engine.replay(
        [make_observation("second", offset_seconds=1), make_observation("first")]
    )
    assert seen == ["first", "second"]
    assert result.clock_timestamps[-1] == result.observations[-1].effective_timestamp


def test_simulated_clock_never_moves_backward(make_observation) -> None:
    clock = ReplayClock()
    first = make_observation("first", offset_seconds=1).effective_timestamp
    earlier = make_observation("earlier", offset_seconds=0).effective_timestamp
    clock.advance_to(first)
    try:
        clock.advance_to(earlier)
    except ReplayValidationError as error:
        assert "backward" in str(error)
    else:
        raise AssertionError("clock accepted backward movement")


def test_replay_result_does_not_depend_on_wall_clock(monkeypatch, make_observation) -> None:
    observations = [make_observation("only")]
    monkeypatch.setattr(time, "time", lambda: 1.0)
    first = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    monkeypatch.setattr(time, "time", lambda: 9_999_999_999.0)
    second = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    assert first.to_bytes() == second.to_bytes()

