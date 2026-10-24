"""Tests for Member 1 (U1-U9). Remove @skip as you implement each use case."""
import pytest

SKIP = pytest.mark.skip(reason="TODO Member 1")


@SKIP
def test_search_returns_hubs_with_available_vehicles():
    """U1"""
    raise NotImplementedError


@SKIP
def test_reserve_vehicle_marks_vehicle_reserved_and_holds_deposit():
    """U2"""
    raise NotImplementedError


@SKIP
def test_two_students_cannot_reserve_the_same_vehicle():
    """U2 (concurrency)"""
    raise NotImplementedError


@SKIP
def test_reserve_parking_slot_blocks_the_slot_for_others():
    """U3"""
    raise NotImplementedError


@SKIP
def test_cancel_reservation_releases_resource_and_refunds():
    """U4"""
    raise NotImplementedError


@SKIP
def test_pickup_requires_valid_reservation_and_unlocks():
    """U5"""
    raise NotImplementedError


@SKIP
def test_return_vehicle_to_full_hub_is_rejected():
    """U6"""
    raise NotImplementedError


@SKIP
def test_report_issue_emits_issue_reported_event():
    """U7"""
    raise NotImplementedError
