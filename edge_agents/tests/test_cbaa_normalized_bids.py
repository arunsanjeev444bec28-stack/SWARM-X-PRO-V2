"""Tests for Phase 1: Authoritative 4-Parameter CBAA Bid Calculation and Normalization.

Verifies:
1. Four parameters only: distance, travel_time, congestion, availability.
2. Energy absent.
3. Workload absent.
4. Battery absent from weighted bid (only used as feasibility/safety check).
5. Priority absent from weighted bid (task-level arbitration factor).
6. Weight sum strictly equals 1.00 (0.40 + 0.30 + 0.20 + 0.10).
7. Normalized values clamped to [0.0, 1.0].
8. Constant parameter does not divide by zero (returns 0.0).
9. Lower total cost wins (MINIMUM VALID BID rule).
10. Invalid/disqualified robot cannot win.
11. Winner matches minimum valid bid among surviving robots.
12. Seamless scaling for arbitrary number of robots.
"""

from __future__ import annotations

import pytest
from typing import Dict, Any

from edge_agents.coordination.cbaa import (
    LocalCBAA,
    DEFAULT_CBAA_WEIGHTS,
    normalize_parameter,
    BidCandidate,
    CBAAResult,
)


def test_1_four_parameters_only():
    """Verify exactly four parameters exist in CBAA weights and normalized metrics."""
    cbaa = LocalCBAA()
    expected_parameters = {"distance", "travel_time", "congestion", "availability"}

    assert set(DEFAULT_CBAA_WEIGHTS.keys()) == expected_parameters
    assert len(DEFAULT_CBAA_WEIGHTS) == 4
    assert set(cbaa.weights.keys()) == expected_parameters

    raw_bids = {
        "R1": {"distance": 5.0, "travel_time": 5.0, "congestion": 0.1, "availability": 1.0},
        "R2": {"distance": 10.0, "travel_time": 10.0, "congestion": 0.2, "availability": 1.0},
    }
    result = cbaa.normalize_and_rank_bids(raw_bids, task_id="T_FOUR_ONLY")
    for b in result.bids.values():
        normalized_keys = set(b["normalized"].keys()) - {"total_cost"}
        assert normalized_keys == expected_parameters


def test_2_energy_is_absent_from_cbaa():
    """Verify energy is completely absent from weights, candidates, and calculation."""
    cbaa = LocalCBAA()
    assert "energy" not in DEFAULT_CBAA_WEIGHTS
    assert "energy" not in cbaa.weights

    raw_bids = {
        "R1": {"distance": 4.0, "travel_time": 4.0, "congestion": 0.1, "availability": 1.0},
        "R2": {"distance": 6.0, "travel_time": 6.0, "congestion": 0.05, "availability": 1.0},
    }
    result = cbaa.normalize_and_rank_bids(raw_bids, task_id="T_NO_ENERGY")
    for b in result.bids.values():
        assert "energy" not in b
        assert "energy" not in b["weights"]
        assert "energy" not in b["normalized"]


def test_3_workload_is_absent_from_cbaa():
    """Verify workload is completely removed from weights, candidates, and calculation."""
    cbaa = LocalCBAA()
    assert "workload" not in DEFAULT_CBAA_WEIGHTS
    assert "workload" not in cbaa.weights

    # BidCandidate dataclass has no workload field
    candidate = BidCandidate(
        robot_id="R1",
        feasibility=True,
        estimated_cost=5.0,
        bid=0.25,
        distance=5.0,
        travel_time=5.0,
        congestion=0.1,
        availability=1.0,
    )
    assert not hasattr(candidate, "workload")

    raw_bids = {
        "R1": {"distance": 4.0, "travel_time": 4.0, "congestion": 0.1, "availability": 1.0},
        "R2": {"distance": 6.0, "travel_time": 6.0, "congestion": 0.05, "availability": 1.0},
    }
    result = cbaa.normalize_and_rank_bids(raw_bids, task_id="T_NO_WORKLOAD")
    for b in result.bids.values():
        assert "workload" not in b
        assert "workload" not in b["weights"]
        assert "workload" not in b["normalized"]


def test_4_battery_absent_from_weighted_bid():
    """Verify battery is absent from CBAA weights and normalized cost formula."""
    assert "battery" not in DEFAULT_CBAA_WEIGHTS

    # Battery is strictly a physical feasibility reserve check, not a weighted cost term
    cbaa = LocalCBAA()
    # Robot with low battery (< 5% reserve) is disqualified
    task = {"energy_requirement": 20.0}
    state_low_battery = {"battery": 22.0}  # 22 - 20 = 2 < 5
    bid_infeasible = cbaa.calculate_bid(
        "R1", task, state_low_battery, estimate_distance=1.0, estimate_time=1.0
    )
    assert bid_infeasible.feasibility is False
    assert bid_infeasible.is_valid is False
    assert bid_infeasible.bid == float("inf")

    # Robot with sufficient battery has valid bid without battery weight
    state_ok_battery = {"battery": 80.0}
    bid_ok = cbaa.calculate_bid(
        "R1", task, state_ok_battery, estimate_distance=10.0, estimate_time=10.0
    )
    assert bid_ok.feasibility is True
    assert bid_ok.is_valid is True
    assert not hasattr(bid_ok, "battery")


def test_5_priority_absent_from_weighted_bid():
    """Verify priority is absent from CBAA weights and normalized cost formula."""
    assert "priority" not in DEFAULT_CBAA_WEIGHTS
    cbaa = LocalCBAA()
    assert "priority" not in cbaa.weights


def test_6_weights_sum_to_one():
    """Verify 4 weights strictly sum to 1.00."""
    total_weight = sum(DEFAULT_CBAA_WEIGHTS.values())
    assert abs(total_weight - 1.00) < 1e-6
    assert DEFAULT_CBAA_WEIGHTS["distance"] == 0.40
    assert DEFAULT_CBAA_WEIGHTS["travel_time"] == 0.30
    assert DEFAULT_CBAA_WEIGHTS["congestion"] == 0.20
    assert DEFAULT_CBAA_WEIGHTS["availability"] == 0.10


def test_7_all_normalized_values_within_zero_to_one():
    """Verify all normalized parameters are clamped to [0.0, 1.0]."""
    test_cases = [
        (0.0, 0.0, 10.0, True),
        (5.0, 0.0, 10.0, True),
        (10.0, 0.0, 10.0, True),
        (-5.0, 0.0, 10.0, True),   # underflow clamp
        (15.0, 0.0, 10.0, True),   # overflow clamp
        (1.0, 0.0, 1.0, False),    # higher-is-better
        (0.5, 0.0, 1.0, False),
        (0.0, 0.0, 1.0, False),
    ]
    for val, min_val, max_val, lower_is_better in test_cases:
        norm = normalize_parameter(val, min_val, max_val, lower_is_better)
        assert 0.0 <= norm <= 1.0, f"Failed for val={val}, min={min_val}, max={max_val}, lower_is_better={lower_is_better}"


def test_8_constant_value_does_not_divide_by_zero():
    """Verify that when min_value == max_value, normalization returns 0.0 without ZeroDivisionError."""
    # Lower is better
    norm_lower = normalize_parameter(15.0, 15.0, 15.0, lower_is_better=True)
    assert norm_lower == 0.0

    # Higher is better
    norm_higher = normalize_parameter(1.0, 1.0, 1.0, lower_is_better=False)
    assert norm_higher == 0.0

    # Candidate dictionary having identical values across all robots
    cbaa = LocalCBAA()
    raw_bids = {
        "R1": {"distance": 5.0, "travel_time": 5.0, "congestion": 0.0, "availability": 1.0},
        "R2": {"distance": 5.0, "travel_time": 5.0, "congestion": 0.0, "availability": 1.0},
    }
    result = cbaa.normalize_and_rank_bids(raw_bids, task_id="T_CONST")
    assert result.winner in ["R1", "R2"]
    for rid, bid in result.bids.items():
        assert bid["normalized"]["distance"] == 0.0
        assert bid["normalized"]["travel_time"] == 0.0
        assert bid["normalized"]["congestion"] == 0.0
        assert bid["normalized"]["availability"] == 0.0
        assert bid["total_bid"] == 0.0


def test_9_lower_total_cost_wins():
    """Verify minimum valid bid rule: lower cost wins."""
    cbaa = LocalCBAA()
    # R1 is closest, lowest travel time, zero congestion, full availability
    raw_bids = {
        "R1": {"distance": 2.0, "travel_time": 2.0, "congestion": 0.0, "availability": 1.0},
        "R2": {"distance": 6.0, "travel_time": 6.0, "congestion": 0.2, "availability": 1.0},
        "R3": {"distance": 12.0, "travel_time": 12.0, "congestion": 0.4, "availability": 0.5},
    }
    result = cbaa.normalize_and_rank_bids(raw_bids, task_id="T_LOWER_WINS")
    assert result.winner == "R1"
    assert result.bids["R1"]["total_bid"] < result.bids["R2"]["total_bid"]
    assert result.bids["R2"]["total_bid"] < result.bids["R3"]["total_bid"]
    assert result.bids["R1"]["status"] == "WINNER"
    assert result.bids["R2"]["status"] == "VALID"
    assert result.bids["R3"]["status"] == "VALID"


def test_10_invalid_or_disqualified_robots_cannot_win():
    """Verify that a robot with the lowest cost cannot win if it is disqualified (failover case)."""
    cbaa = LocalCBAA()
    # Seeded failover scenario: R1 is closer (lower cost 0.0667) but is DEAD / disqualified
    raw_bids = {
        "R1": {"distance": 4.0, "travel_time": 5.4, "congestion": 0.10, "availability": 1.0, "status": "DEAD"},
        "R2": {"distance": 6.0, "travel_time": 6.3, "congestion": 0.05, "availability": 1.0, "status": "AVAILABLE"},
        "R3": {"distance": 18.0, "travel_time": 9.3, "congestion": 0.20, "availability": 1.0, "status": "AVAILABLE"},
        "R4": {"distance": 22.0, "travel_time": 10.8, "congestion": 0.15, "availability": 1.0, "status": "AVAILABLE"},
    }
    ineligible = {"R1": "ROBOT_DEAD (HEARTBEAT_TIMEOUT)"}

    result = cbaa.normalize_and_rank_bids(raw_bids, ineligible_robots=ineligible, task_id="TASK_FAILOVER_01")

    # R1 cost is lower (0.0667 < 0.0944), but R1 is DISQUALIFIED
    assert result.bids["R1"]["is_valid"] is False
    assert result.bids["R1"]["status"] == "DISQUALIFIED"
    assert result.bids["R1"]["winner"] is False

    # R2 is the minimum VALID bid winner (calculated cost = 0.0944)
    assert result.winner == "R2"
    assert result.bids["R2"]["is_valid"] is True
    assert result.bids["R2"]["winner"] is True
    assert result.bids["R2"]["status"] == "WINNER"
    assert result.winning_bid == result.bids["R2"]["total_bid"]


def test_11_dashboard_winner_matches_minimum_valid_bid():
    """Verify winner selected strictly matches the minimum among valid candidates."""
    cbaa = LocalCBAA()
    raw_bids = {
        "R1": {"distance": 10.0, "travel_time": 10.0, "congestion": 0.1, "availability": 1.0},
        "R2": {"distance": 4.0, "travel_time": 4.0, "congestion": 0.0, "availability": 1.0},
        "R3": {"distance": 20.0, "travel_time": 20.0, "congestion": 0.3, "availability": 1.0},
    }
    result = cbaa.normalize_and_rank_bids(raw_bids, task_id="T_MIN_MATCH")
    valid_bids = {rid: b["total_bid"] for rid, b in result.bids.items() if b["is_valid"]}
    min_rid = min(valid_bids, key=valid_bids.get)
    assert result.winner == min_rid == "R2"
    assert result.winning_bid == result.bids[min_rid]["total_bid"]


def test_12_extensible_for_more_than_four_robots():
    """Verify normalization and winner selection works seamlessly for arbitrary number of robots."""
    cbaa = LocalCBAA()
    raw_bids = {
        f"R{i}": {
            "distance": float(i * 3.0),
            "travel_time": float(i * 3.0),
            "congestion": float((i % 3) * 0.1),
            "availability": 1.0,
        }
        for i in range(1, 11)  # 10 robots
    }
    result = cbaa.normalize_and_rank_bids(raw_bids, task_id="T_SCALE_10")
    assert result.winner == "R1"
    assert len(result.bids) == 10
    # Values all normalized in [0, 1]
    for b in result.bids.values():
        for k, v in b["normalized"].items():
            assert 0.0 <= v <= 1.0
