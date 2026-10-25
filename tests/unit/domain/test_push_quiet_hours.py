import datetime as dt

from salli.domain.notifications.push import in_quiet_hours


def test_quiet_hours_may_run_past_midnight():
    at = dt.time.fromisoformat
    assert in_quiet_hours(at("23:30"), "22:00", "08:00")
    assert in_quiet_hours(at("07:59"), "22:00", "08:00")
    assert not in_quiet_hours(at("08:00"), "22:00", "08:00")
    assert in_quiet_hours(at("13:00"), "12:00", "14:00")
    assert not in_quiet_hours(at("14:00"), "12:00", "14:00")
    assert not in_quiet_hours(at("03:00"), None, None)
