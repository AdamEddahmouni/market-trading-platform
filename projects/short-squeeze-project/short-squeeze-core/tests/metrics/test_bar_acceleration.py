from squeeze_core.metrics.bar_acceleration import bar_acceleration, compute_bar_acceleration


def test_fewer_than_two_bars_returns_none():
    assert bar_acceleration([]) is None
    assert bar_acceleration([1.0]) is None
    result = compute_bar_acceleration([{"open": 10.0, "close": 11.0}])
    assert result.value is None
    assert result.bar_count == 1


def test_zero_open_is_skipped():
    bars = [
        {"open": 0.0, "close": 10.0},
        {"open": 10.0, "close": 11.0},
        {"open": 11.0, "close": 12.1},
    ]
    result = compute_bar_acceleration(bars)
    assert result.bar_count == 2
    # (11-10)/10*100 = 10; (12.1-11)/11*100 ≈ 10.0; accel ≈ 0 after one prior
    assert result.value is not None


def test_known_percentage_points():
    # open→close: 1%, then 4% → acceleration 4 - 1 = 3 percentage points
    bars = [
        {"open": 100.0, "close": 101.0},
        {"open": 100.0, "close": 104.0},
    ]
    result = compute_bar_acceleration(bars)
    assert result.value == 3.0
    assert result.unit == "PERCENTAGE_POINTS"


def test_not_close_to_close_series():
    # Close-to-close would be 101→104 ≈ 2.97%; open→close on last bar is 3%.
    bars = [
        {"open": 100.0, "close": 101.0},
        {"open": 101.0, "close": 104.03},
    ]
    result = compute_bar_acceleration(bars)
    last_open_close = (104.03 - 101.0) / 101.0 * 100.0
    prior_open_close = (101.0 - 100.0) / 100.0 * 100.0
    assert result.value == round(last_open_close - prior_open_close, 6)
