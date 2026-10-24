"""Tests for Member 3 (UC01-UC-OP09). Remove @skip as you implement each use case."""
import pytest

SKIP = pytest.mark.skip(reason="TODO Member 3")


@SKIP
def test_dashboard_totals_match_network_status():
    """UC01"""
    raise NotImplementedError


@SKIP
def test_alert_raised_when_hub_near_capacity():
    """UC02"""
    raise NotImplementedError


@SKIP
def test_acknowledge_alert_marks_handled():
    """UC02"""
    raise NotImplementedError


@SKIP
def test_proposal_moves_from_surplus_to_shortage_hub():
    """UC03"""
    raise NotImplementedError


@SKIP
def test_relocation_order_moves_vehicles_on_completion():
    """UC-OP04"""
    raise NotImplementedError


@SKIP
def test_handle_incident_puts_vehicle_in_maintenance_and_opens_ticket():
    """UC05/UC-OP06"""
    raise NotImplementedError


@SKIP
def test_incident_cancels_affected_reservation():
    """UC-OP07"""
    raise NotImplementedError


@SKIP
def test_manual_override_requires_reason_and_is_audited():
    """UC-OP09"""
    raise NotImplementedError
