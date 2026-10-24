"""Tests for Member 2 (UC-CH-01..10). Remove @skip as you implement each use case."""
import pytest

SKIP = pytest.mark.skip(reason="TODO Member 2")


@SKIP
def test_priority_is_higher_for_low_battery():
    """UC-CH-09"""
    raise NotImplementedError


@SKIP
def test_priority_is_higher_when_needed_sooner():
    """UC-CH-09"""
    raise NotImplementedError


@SKIP
def test_submit_request_rejected_without_private_ev():
    """UC-CH-01"""
    raise NotImplementedError


@SKIP
def test_schedule_session_rejects_overlapping_window_on_same_point():
    """UC-CH-02"""
    raise NotImplementedError


@SKIP
def test_out_of_service_point_is_never_assigned():
    """UC-CH-03/09"""
    raise NotImplementedError


@SKIP
def test_cancel_frees_point_and_promotes_queue():
    """UC-CH-05"""
    raise NotImplementedError


@SKIP
def test_update_point_status_requeues_running_session():
    """UC-CH-08"""
    raise NotImplementedError


@SKIP
def test_telemetry_updates_battery_and_rejects_invalid_values():
    """UC-CH-10"""
    raise NotImplementedError
