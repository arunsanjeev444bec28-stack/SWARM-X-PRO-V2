from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Authoritative CBAA Weights: Total strictly equals 1.00.
# Priority is kept separate as a task-level arbitration/feasibility factor.
DEFAULT_CBAA_WEIGHTS: Dict[str, float] = {
    "distance": 0.40,
    "travel_time": 0.30,
    "congestion": 0.20,
    "availability": 0.10,
}


def normalize_parameter(val: float, min_val: float, max_val: float, lower_is_better: bool = True) -> float:
    """Normalize a parameter to [0, 1] cost scale before applying weights.

    For cost parameters where LOWER is better (distance, travel_time, congestion):
        normalized = (value - min_value) / (max_value - min_value)

    For parameters where HIGHER is better (availability), convert to cost form:
        normalized = 1 - ((value - min_value) / (max_value - min_value))

    Handles edge case:
        if max_value == min_value:
            normalized = 0.0

    Clamps result to [0.0, 1.0].
    """
    if max_val == min_val:
        return 0.0
    if lower_is_better:
        norm = (float(val) - float(min_val)) / (float(max_val) - float(min_val))
    else:
        norm = 1.0 - ((float(val) - float(min_val)) / (float(max_val) - float(min_val)))
    return max(0.0, min(1.0, float(norm)))


@dataclass
class BidCandidate:
    robot_id: str
    feasibility: bool
    estimated_cost: float
    bid: float
    reason: str = "OK"
    distance: float = 0.0
    travel_time: float = 0.0
    congestion: float = 0.0
    availability: float = 1.0
    normalized: Dict[str, float] = field(default_factory=dict)
    is_valid: bool = True
    status: str = "VALID"


@dataclass
class CBAAResult:
    task_id: str
    winner: Optional[str] = None
    winning_bid: Optional[float] = None
    bids: Dict[str, Any] = field(default_factory=dict)
    selection_rule: str = "MINIMUM VALID BID"
    reason: str = ""


class LocalCBAA:
    """Authoritative CBAA coordinator used by edge agents and backend allocation.

    Normalized cost formula:
        normalized_cost = (
            0.40 * normalized_distance +
            0.30 * normalized_travel_time +
            0.20 * normalized_congestion +
            0.10 * normalized_availability
        )
    Selection Rule: MINIMUM VALID BID (lower total bid wins).
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = dict(DEFAULT_CBAA_WEIGHTS)
        if weights:
            self.weights.update(weights)

    def normalize_and_rank_bids(
        self,
        raw_bids: Dict[str, Dict[str, Any]],
        ineligible_robots: Optional[Dict[str, str]] = None,
        task_id: str = "",
    ) -> CBAAResult:
        """Normalize raw metrics across candidate robots, compute weighted cost, and determine winner.

        Excludes invalid/disqualified robots so only valid robots can win under
        the MINIMUM VALID BID rule.
        """
        ineligible = ineligible_robots or {}
        if not raw_bids:
            return CBAAResult(
                task_id=task_id,
                winner=None,
                winning_bid=None,
                bids={},
                selection_rule="MINIMUM VALID BID",
                reason="No candidate bids evaluated",
            )

        # Extract values for min/max calculation across all candidate robots
        distances = [float(b.get("distance", 0.0)) for b in raw_bids.values()]
        times = [float(b.get("travel_time", 0.0)) for b in raw_bids.values()]
        congestions = [float(b.get("congestion", 0.0)) for b in raw_bids.values()]
        availabilities = [float(b.get("availability", 1.0)) for b in raw_bids.values()]

        min_d, max_d = min(distances), max(distances)
        min_t, max_t = min(times), max(times)
        min_c, max_c = min(congestions), max(congestions)
        min_a, max_a = min(availabilities), max(availabilities)

        evaluated_bids: Dict[str, Dict[str, Any]] = {}

        for rid, b in raw_bids.items():
            raw_dist = float(b.get("distance", 0.0))
            raw_time = float(b.get("travel_time", 0.0))
            raw_cong = float(b.get("congestion", 0.0))
            raw_avail = float(b.get("availability", 1.0))

            # Normalize parameters to [0, 1]
            n_dist = normalize_parameter(raw_dist, min_d, max_d, lower_is_better=True)
            n_time = normalize_parameter(raw_time, min_t, max_t, lower_is_better=True)
            n_cong = normalize_parameter(raw_cong, min_c, max_c, lower_is_better=True)
            n_avail = normalize_parameter(raw_avail, min_a, max_a, lower_is_better=False)

            # Authoritative Weighted Cost Formula: Total weights = 1.00
            total_cost = (
                self.weights["distance"] * n_dist
                + self.weights["travel_time"] * n_time
                + self.weights["congestion"] * n_cong
                + self.weights["availability"] * n_avail
            )
            total_cost = round(max(0.0, min(1.0, float(total_cost))), 4)

            # Determine validity
            is_ineligible = rid in ineligible
            is_feasible = bool(b.get("feasibility", True)) and not is_ineligible
            status_override = b.get("status")
            if is_ineligible:
                is_valid = False
                status = "DISQUALIFIED"
                reason = ineligible[rid]
            elif not is_feasible or status_override in ["DEAD", "FAILED", "FAULT", "DISQUALIFIED"]:
                is_valid = False
                status = "DISQUALIFIED"
                reason = b.get("reason", "Infeasible / Disqualified")
            else:
                is_valid = True
                status = "VALID"
                reason = "OK"

            evaluated_bids[rid] = {
                "robot_id": rid,
                "distance": round(raw_dist, 2),
                "travel_time": round(raw_time, 2),
                "congestion": round(raw_cong, 4),
                "availability": round(raw_avail, 2),
                "normalized": {
                    "distance": round(n_dist, 4),
                    "travel_time": round(n_time, 4),
                    "congestion": round(n_cong, 4),
                    "availability": round(n_avail, 4),
                    "total_cost": total_cost,
                },
                "total_bid": total_cost,
                "final_bid": total_cost,
                "base_bid": total_cost,
                "cost": total_cost,
                "is_valid": is_valid,
                "status": status,
                "reason": reason,
                "winner": False,
                "weights": dict(self.weights),
            }

        # Select winner: Minimum valid bid among feasible/valid robots
        valid_candidates = {rid: data for rid, data in evaluated_bids.items() if data["is_valid"]}
        if not valid_candidates:
            return CBAAResult(
                task_id=task_id,
                winner=None,
                winning_bid=None,
                bids=evaluated_bids,
                selection_rule="MINIMUM VALID BID",
                reason="No valid candidate robots available",
            )

        winner_id, winner_data = sorted(
            valid_candidates.items(),
            key=lambda item: (item[1]["total_bid"], item[0]),
        )[0]

        evaluated_bids[winner_id]["winner"] = True
        evaluated_bids[winner_id]["status"] = "WINNER"

        return CBAAResult(
            task_id=task_id,
            winner=winner_id,
            winning_bid=winner_data["total_bid"],
            bids=evaluated_bids,
            selection_rule="MINIMUM VALID BID",
            reason=f"{winner_id} selected with minimum valid bid {winner_data['total_bid']:.4f}",
        )

    def calculate_bid(
        self,
        robot_id: str,
        task: Dict[str, Any],
        robot_state: Dict[str, Any],
        *,
        estimate_distance: float,
        estimate_time: float,
        availability: float = 1.0,
        congestion: float = 0.0,
    ) -> BidCandidate:
        """Calculate local bid metrics for an individual edge robot agent.

        Note: ENERGY and WORKLOAD are completely removed from the CBAA input model and bid formula.
        Priority is an independent task-level arbitration factor.
        """
        battery = float(robot_state.get("battery", 100.0))
        energy_req = float(task.get("energy_requirement", 0.0))

        # Physical feasibility check: battery reserve must be at least 5%
        feasible = battery - energy_req >= 5.0
        if not feasible:
            return BidCandidate(
                robot_id=robot_id,
                feasibility=False,
                estimated_cost=float("inf"),
                bid=float("inf"),
                reason="insufficient battery reserve",
                is_valid=False,
                status="DISQUALIFIED",
            )

        distance_cost = float(estimate_distance)
        time_cost = float(estimate_time)
        congestion_cost = float(congestion)
        availability_val = max(0.0, min(1.0, float(availability)))

        # Weighted baseline cost without energy and without workload
        bid = (
            self.weights["distance"] * distance_cost
            + self.weights["travel_time"] * time_cost
            + self.weights["congestion"] * congestion_cost
            + self.weights["availability"] * (1.0 - availability_val)
        )

        return BidCandidate(
            robot_id=robot_id,
            feasibility=True,
            estimated_cost=distance_cost,
            bid=bid,
            reason="OK",
            distance=distance_cost,
            travel_time=time_cost,
            congestion=congestion_cost,
            availability=availability_val,
            is_valid=True,
            status="VALID",
        )

    def determine_winner(self, bids: Dict[str, Any], task_id: str = "") -> CBAAResult:
        """Determine winner among bids based on minimum valid bid rule."""
        if not bids:
            return CBAAResult(task_id=task_id, winner=None, winning_bid=None, bids=bids)

        # Check if bids are BidCandidate or dict
        valid: Dict[str, float] = {}
        for rid, c in bids.items():
            if isinstance(c, BidCandidate):
                if c.feasibility and c.is_valid and c.bid != float("inf"):
                    valid[rid] = c.bid
            elif isinstance(c, dict):
                is_feasible = c.get("feasible", c.get("feasibility", c.get("is_valid", True)))
                status = c.get("status", "")
                if status in ["DEAD", "FAILED", "FAULT", "DISQUALIFIED"]:
                    is_feasible = False
                bid_val = c.get("total_bid", c.get("final_bid", c.get("bid", float("inf"))))
                if is_feasible and bid_val != float("inf"):
                    valid[rid] = float(bid_val)

        if not valid:
            return CBAAResult(
                task_id=task_id,
                winner=None,
                winning_bid=None,
                bids=bids,
                selection_rule="MINIMUM VALID BID",
                reason="No valid candidate bids",
            )

        winner_id, winning_val = sorted(valid.items(), key=lambda item: (item[1], item[0]))[0]

        return CBAAResult(
            task_id=task_id,
            winner=winner_id,
            winning_bid=winning_val,
            bids=bids,
            selection_rule="MINIMUM VALID BID",
            reason=f"{winner_id} selected with minimum valid bid {winning_val:.4f}",
        )
