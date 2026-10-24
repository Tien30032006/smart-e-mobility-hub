"""Tests for Member 4 (UC1-UC7). Remove @skip as you implement each use case."""
import pytest

SKIP = pytest.mark.skip(reason="TODO Member 4")


@SKIP
def test_run_never_mutates_live_state():
    """UC3 (MOST IMPORTANT)"""
    raise NotImplementedError


@SKIP
def test_invalid_scenario_params_are_rejected():
    """UC1"""
    raise NotImplementedError


@SKIP
def test_template_can_be_loaded_with_overrides():
    """UC2"""
    raise NotImplementedError


@SKIP
def test_demand_surge_at_metro_flags_overload_risk():
    """UC5"""
    raise NotImplementedError


@SKIP
def test_charger_failure_reduces_service_rate():
    """UC5"""
    raise NotImplementedError


@SKIP
def test_recommendations_use_relocation_plan_format():
    """UC6"""
    raise NotImplementedError


@SKIP
def test_same_seed_gives_same_result():
    """UC3"""
    raise NotImplementedError


@SKIP
def test_export_report_contains_scenario_and_recommendations():
    """UC7"""
    raise NotImplementedError
