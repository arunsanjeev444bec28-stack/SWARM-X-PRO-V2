"""
Authoritative 78-Rack Industrial Warehouse Geometry and RF Navigation Graph Generator.

Conforms to SWARM-X PRO V2 decentralized fleet specifications:
- EXACTLY 78 racks arranged in a clean industrial warehouse layout (13 columns x 6 rows).
- Proper horizontal and vertical aisles.
- RF navigation nodes placed at all aisle INTERSECTION POINTS (14 vertical x 7 horizontal = 98 RF nodes).
- RF navigation graph with orthogonal edges (North, South, East, West only — no diagonal movement, turns only at RF nodes).
- Exactly 4 AMRs placed at startup at the 4 valid corner RF nodes (top-left, top-right, bottom-left, bottom-right).
- All 4 AMRs initially AVAILABLE.
- Zero initial tasks, zero fake failures, zero fake missions.
"""

from __future__ import annotations

import math
import os
from typing import Dict, List, Tuple, Any, Optional
from models.schemas import Node, Robot, Rack, NavEdge, WarehouseModel

# ==============================================================================
# AUTHORITATIVE WAREHOUSE GEOMETRY CONSTANTS
# ==============================================================================
GRID_COLS = int(os.getenv("GRID_COLS", "13"))  # number of rack columns
GRID_ROWS = int(os.getenv("GRID_ROWS", "6"))   # number of rack rows
TOTAL_RACKS = GRID_COLS * GRID_ROWS

AISLE_COLS = GRID_COLS + 1  # vertical aisles = columns + 1
AISLE_ROWS = GRID_ROWS + 1  # horizontal aisles = rows + 1
TOTAL_RF_NODES = AISLE_COLS * AISLE_ROWS

SPACING_X = float(os.getenv("SPACING_X", "2.4"))   # meters between vertical aisle lines
SPACING_Y = float(os.getenv("SPACING_Y", "2.0"))   # meters between horizontal aisle lines

RACK_WIDTH = 1.4   # Rack dimension along X
RACK_HEIGHT = 0.8  # Rack dimension along Y (depth)

X_MIN = -15.6
X_MAX = 15.6
Y_MIN = -6.0
Y_MAX = 6.0

WAREHOUSE_BOUNDS = {
    "x_min": X_MIN,
    "x_max": X_MAX,
    "y_min": Y_MIN,
    "y_max": Y_MAX,
    "width": round(X_MAX - X_MIN, 2),
    "height": round(Y_MAX - Y_MIN, 2),
}

import os

NOMINAL_ROBOT_SPEED_MPS = 1.0
# Configurable robot dimensions (override via environment variables)
ROBOT_LENGTH = float(os.getenv("ROBOT_LENGTH", "0.60"))  # meters
ROBOT_WIDTH = float(os.getenv("ROBOT_WIDTH", "0.40"))    # meters
ROBOT_FOOTPRINT = (ROBOT_LENGTH, ROBOT_WIDTH)  # length, width in meters

# Authoritative clearance and collision parameters
# Minimum aisle width = min(SPACING_X - RACK_WIDTH, SPACING_Y - RACK_HEIGHT) = 1.0m
MIN_AISLE_WIDTH = min(SPACING_X - RACK_WIDTH, SPACING_Y - RACK_HEIGHT)
AVAILABLE_SIDE_CLEARANCE = (MIN_AISLE_WIDTH - ROBOT_WIDTH) / 2.0  # 0.30 m
SIDE_CLEARANCE_REQUIRED = float(os.getenv("SIDE_CLEARANCE_REQUIRED", "0.10"))  # meters
TURN_CLEARANCE_REQUIRED = float(os.getenv("TURN_CLEARANCE_REQUIRED", "0.10"))  # meters
COLLISION_MARGIN = float(os.getenv("COLLISION_MARGIN", "0.10"))  # meters for spatial validity checks

# Legacy compatibility constants (for tests inspecting dock/charging/column structures)
SHELF_X = [-10.0, -4.0, 4.0, 10.0]
SHELF_Y = [-8.0, -4.0, 0.0, 4.0, 8.0]
COLUMNS = [(-7.0, 10.0), (0.0, 10.0), (7.0, 10.0), (-7.0, -10.0), (0.0, -10.0), (7.0, -10.0)]
LOADING_DOCKS = {"LD1": (-15.6, 2.0), "LD2": (-15.6, -2.0)}
UNLOADING_DOCKS = {"UD1": (15.6, 2.0), "UD2": (15.6, -2.0)}
CHARGING_STATIONS = {
    "CS1": (-15.6, 6.0),
    "CS2": (15.6, 6.0),
    "CS3": (-15.6, -6.0),
    "CS4": (15.6, -6.0),
}
ROBOT_SPAWNS = {
    "R1": (-15.6, 6.0),
    "R2": (15.6, 6.0),
    "R3": (-15.6, -6.0),
    "R4": (15.6, -6.0),
}


# ==============================================================================
# WAREHOUSE MODEL GENERATION (78 RACKS, AISLES, INTERSECTIONS, EDGES)
# ==============================================================================
def get_aisle_x(c: int) -> float:
    return round(X_MIN + c * SPACING_X, 2)


def get_aisle_y(r: int) -> float:
    return round(Y_MIN + r * SPACING_Y, 2)


def generate_78_racks() -> List[Rack]:
    """Generate EXACTLY 78 equally spaced industrial racks (13 cols x 6 rows)."""
    racks: List[Rack] = []
    rack_idx = 1
    for r in range(GRID_ROWS):
        y_center = round(get_aisle_y(r) + SPACING_Y / 2.0, 2)
        for c in range(GRID_COLS):
            x_center = round(get_aisle_x(c) + SPACING_X / 2.0, 2)
            racks.append(
                Rack(
                    rack_id=f"RACK_{rack_idx:02d}",
                    x=x_center,
                    y=y_center,
                    width=RACK_WIDTH,
                    height=RACK_HEIGHT,
                )
            )
            rack_idx += 1
    return racks


def generate_rf_nodes() -> Dict[str, Node]:
    """Generate the 98 RF navigation nodes at aisle INTERSECTION POINTS (14 cols x 7 rows).

    Connections are strictly orthogonal (North, South, East, West). No diagonal movement.
    """
    nodes: Dict[str, Node] = {}

    for r in range(AISLE_ROWS):
        y_coord = get_aisle_y(r)
        for c in range(AISLE_COLS):
            x_coord = get_aisle_x(c)
            node_id = f"RF_{r}_{c}"

            # 4-connected orthogonal neighbors only
            neighbors: List[str] = []
            if r + 1 < AISLE_ROWS:
                neighbors.append(f"RF_{r+1}_{c}")  # North
            if r - 1 >= 0:
                neighbors.append(f"RF_{r-1}_{c}")  # South
            if c + 1 < AISLE_COLS:
                neighbors.append(f"RF_{r}_{c+1}")  # East
            if c - 1 >= 0:
                neighbors.append(f"RF_{r}_{c-1}")  # West

            nodes[node_id] = Node(
                node_id=node_id,
                x=x_coord,
                y=y_coord,
                type="INTERSECTION",
                neighbors=neighbors,
                health=100.0,
            )

    return nodes


def generate_nav_edges(nodes: Dict[str, Node]) -> List[NavEdge]:
    """Generate navigation edges along aisles between adjacent RF intersection nodes."""
    edges: List[NavEdge] = []
    seen = set()

    for node_id, node in nodes.items():
        for nbr_id in node.neighbors:
            edge_key = tuple(sorted([node_id, nbr_id]))
            if edge_key not in seen and nbr_id in nodes:
                seen.add(edge_key)
                nbr = nodes[nbr_id]
                dist = round(math.hypot(node.x - nbr.x, node.y - nbr.y), 2)
                edges.append(
                    NavEdge(
                        from_node=node_id,
                        to_node=nbr_id,
                        distance=dist,
                        blocked=False,
                    )
                )

    return edges


def get_corner_rf_nodes(nodes: Optional[Dict[str, Node]] = None) -> Dict[str, str]:
    """Dynamically find the 4 valid corner RF nodes from the generated graph:

    - R1 -> top-left
    - R2 -> top-right
    - R3 -> bottom-left
    - R4 -> bottom-right
    """
    if nodes is None:
        nodes = generate_rf_nodes()

    min_x = min(n.x for n in nodes.values())
    max_x = max(n.x for n in nodes.values())
    min_y = min(n.y for n in nodes.values())
    max_y = max(n.y for n in nodes.values())

    top_left = min(nodes.values(), key=lambda n: (n.x - min_x) ** 2 + (n.y - max_y) ** 2).node_id
    top_right = min(nodes.values(), key=lambda n: (n.x - max_x) ** 2 + (n.y - max_y) ** 2).node_id
    bottom_left = min(nodes.values(), key=lambda n: (n.x - min_x) ** 2 + (n.y - min_y) ** 2).node_id
    bottom_right = min(nodes.values(), key=lambda n: (n.x - max_x) ** 2 + (n.y - min_y) ** 2).node_id

    return {
        "R1": top_left,
        "R2": top_right,
        "R3": bottom_left,
        "R4": bottom_right,
    }


def generate_warehouse_model() -> Dict[str, Any]:
    """Return full structured warehouse model with 78 racks, aisles, intersections, and edges."""
    racks = generate_78_racks()
    rf_nodes = generate_rf_nodes()
    edges = generate_nav_edges(rf_nodes)
    corners = get_corner_rf_nodes(rf_nodes)

    aisles = [
        {"id": f"HA_{r}", "type": "HORIZONTAL", "y": get_aisle_y(r), "x_min": X_MIN, "x_max": X_MAX}
        for r in range(AISLE_ROWS)
    ] + [
        {"id": f"VA_{c}", "type": "VERTICAL", "x": get_aisle_x(c), "y_min": Y_MIN, "y_max": Y_MAX}
        for c in range(AISLE_COLS)
    ]

    intersections = [
        {"id": n_id, "x": n.x, "y": n.y, "neighbors": n.neighbors}
        for n_id, n in rf_nodes.items()
    ]

    return {
        "total_racks": len(racks),
        "rack_count": len(racks),
        "total_rf_nodes": len(rf_nodes),
        "rf_node_count": len(rf_nodes),
        "racks": [r.model_dump() for r in racks],
        "aisles": aisles,
        "intersections": intersections,
        "rf_nodes": {n_id: n.model_dump() for n_id, n in rf_nodes.items()},
        "edges": [e.model_dump() for e in edges],
        "dimensions": WAREHOUSE_BOUNDS,
        "corner_nodes": corners,
    }


# ==============================================================================
# STATE INITIALIZATION (4 AMRs AT CORNERS, ZERO TASKS, ZERO FAKE FAILURES)
# ==============================================================================
def init_real_warehouse_state(state_manager) -> Dict[str, Any]:
    """Initialize the authoritative warehouse state with:

    - EXACTLY 78 racks
    - 98 RF intersection nodes
    - 4 AMRs at the 4 valid corners (R1 top-left, R2 top-right, R3 bottom-left, R4 bottom-right)
    - All 4 AMRs initially AVAILABLE
    - ZERO initial tasks, ZERO fake failures, ZERO fake missions.
    """
    state_manager.reset()

    # Add all 98 RF nodes
    rf_nodes = generate_rf_nodes()
    for node in rf_nodes.values():
        state_manager.add_node(node)

    # Automatically derive the 4 corner RF nodes
    corners = get_corner_rf_nodes(rf_nodes)

    # Spawn 4 AMRs at four corners, all initially AVAILABLE
    for robot_id, corner_node_id in corners.items():
        node = rf_nodes[corner_node_id]
        robot = Robot(
            robot_id=robot_id,
            node_id=corner_node_id,
            battery=100.0,
            temperature=25.0,
            load=0.0,
            health=100.0,
            status="AVAILABLE",
            position=[node.x, node.y, 0.12],
        )
        state_manager.add_robot(robot)

    # Zero tasks, zero allocations, zero fake failures
    state_manager.tasks.clear()
    state_manager.allocations.clear()
    state_manager.failures.clear()
    state_manager.events.clear()
    state_manager.robot_tasks.clear()
    state_manager.robot_paths.clear()

    return {
        "status": "success",
        "warehouse": {
            "width": WAREHOUSE_BOUNDS["width"],
            "height": WAREHOUSE_BOUNDS["height"],
            "racks": TOTAL_RACKS,
            "rf_nodes": len(rf_nodes),
            "aisles_h": AISLE_ROWS,
            "aisles_v": AISLE_COLS,
        },
        "robots": [
            {"robot_id": rid, "node_id": cid, "status": "AVAILABLE"}
            for rid, cid in corners.items()
        ],
    }


# Backward compatibility alias
generate_real_warehouse_graph = generate_rf_nodes


# ==============================================================================
# CLEARANCE & COLLISION CHECKS (USED BY TESTS / COPPELIASIM / GAZEBO)
# ==============================================================================
def is_point_valid(x: float, y: float, margin: float = COLLISION_MARGIN) -> bool:
    """Check if point is within warehouse bounds and not inside a rack or column."""
    if abs(x) > (X_MAX + 0.1) or abs(y) > (Y_MAX + 0.1):
        return False

    # Check 78 racks envelope
    for r in range(GRID_ROWS):
        y_center = get_aisle_y(r) + SPACING_Y / 2.0
        for c in range(GRID_COLS):
            x_center = get_aisle_x(c) + SPACING_X / 2.0
            if (abs(x - x_center) < (RACK_WIDTH / 2.0 + margin)) and (
                abs(y - y_center) < (RACK_HEIGHT / 2.0 + margin)
            ):
                return False

    # Check legacy columns if any point falls on them
    for cx, cy in COLUMNS:
        if math.hypot(x - cx, y - cy) < (0.35 + margin):
            return False

    return True


def is_edge_valid(x1: float, y1: float, x2: float, y2: float, margin: float = COLLISION_MARGIN) -> bool:
    """Check if straight line segment is traversable."""
    dist = math.hypot(x2 - x1, y2 - y1)
    steps = max(2, int(math.ceil(dist / 0.2)))
    for i in range(steps + 1):
        alpha = i / float(steps)
        xi = x1 + alpha * (x2 - x1)
        yi = y1 + alpha * (y2 - y1)
        if not is_point_valid(xi, yi, margin):
            return False
    return True


def get_node_id(x: float, y: float) -> str:
    """Snap coordinates to closest RF node ID."""
    nodes = generate_rf_nodes()
    closest = min(nodes.values(), key=lambda n: (n.x - x) ** 2 + (n.y - y) ** 2)
    return closest.node_id


def validate_warehouse_config() -> dict:
    """Validate warehouse geometry and robot clearance parameters.

    Calculates and reports all authoritative metrics with explicit PASS/FAIL.
    """
    edges = generate_nav_edges(generate_rf_nodes())
    edge_count = len(edges)

    # Derived dimensions
    warehouse_width = round(GRID_COLS * SPACING_X, 2)
    warehouse_height = round(GRID_ROWS * SPACING_Y, 2)
    aisle_width_x = round(SPACING_X - RACK_WIDTH, 2)
    aisle_width_y = round(SPACING_Y - RACK_HEIGHT, 2)
    aisle_width = min(aisle_width_x, aisle_width_y)

    robot_radius = round(math.hypot(ROBOT_LENGTH / 2.0, ROBOT_WIDTH / 2.0), 4)
    available_side_clearance = round((aisle_width - ROBOT_WIDTH) / 2.0, 3)
    required_side_clearance = 0.10

    # Turning clearance at RF node intersection
    dist_to_rack_corner = math.hypot(SPACING_X / 2.0 - RACK_WIDTH / 2.0, SPACING_Y / 2.0 - RACK_HEIGHT / 2.0)
    turning_clearance = round(dist_to_rack_corner - robot_radius, 4)

    lidar_min_range = 0.20
    lidar_max_range = 10.0

    # Validation criteria checks
    rack_pass = (TOTAL_RACKS == 78)
    node_pass = (TOTAL_RF_NODES == 98)
    edge_pass = (edge_count == 175)
    dims_pass = (warehouse_width == 31.2 and warehouse_height == 12.0)
    aisle_pass = (aisle_width >= 1.0)
    straight_pass = (available_side_clearance >= required_side_clearance)
    turning_pass = (turning_clearance > 0.0)
    collision_pass = (COLLISION_MARGIN > 0.0 and COLLISION_MARGIN <= available_side_clearance)
    lidar_pass = (lidar_min_range < ROBOT_WIDTH and lidar_max_range >= max(SPACING_X, SPACING_Y))

    all_passed = all([
        rack_pass, node_pass, edge_pass, dims_pass,
        aisle_pass, straight_pass, turning_pass, collision_pass, lidar_pass
    ])

    report = {
        "rack_count": TOTAL_RACKS,
        "rf_node_count": TOTAL_RF_NODES,
        "graph_edge_count": edge_count,
        "warehouse_x_range": [X_MIN, X_MAX],
        "warehouse_y_range": [Y_MIN, Y_MAX],
        "warehouse_width_m": warehouse_width,
        "warehouse_height_m": warehouse_height,
        "rack_dimensions_m": [RACK_WIDTH, RACK_HEIGHT],
        "rf_node_spacing_m": [SPACING_X, SPACING_Y],
        "aisle_width_m": round(aisle_width, 2),
        "robot_length_m": ROBOT_LENGTH,
        "robot_width_m": ROBOT_WIDTH,
        "robot_radius_m": robot_radius,
        "available_side_clearance_m": available_side_clearance,
        "required_side_clearance_m": required_side_clearance,
        "turning_clearance_m": turning_clearance,
        "collision_margin_m": COLLISION_MARGIN,
        "lidar_min_range_m": lidar_min_range,
        "lidar_max_range_m": lidar_max_range,
        # Explicit PASS / FAIL per validation item
        "validations": {
            "rack_count": "PASS" if rack_pass else "FAIL",
            "rf_node_count": "PASS" if node_pass else "FAIL",
            "graph_edge_count": "PASS" if edge_pass else "FAIL",
            "warehouse_dimensions": "PASS" if dims_pass else "FAIL",
            "aisle_width": "PASS" if aisle_pass else "FAIL",
            "straight_travel_clearance": "PASS" if straight_pass else "FAIL",
            "turning_clearance": "PASS" if turning_pass else "FAIL",
            "collision_margin": "PASS" if collision_pass else "FAIL",
            "lidar_range": "PASS" if lidar_pass else "FAIL",
            "overall": "PASS" if all_passed else "FAIL",
        },
        "straight_travel_clearance": "PASS" if straight_pass else "FAIL",
        "turning_clearance": "PASS" if turning_pass else "FAIL",
    }
    return report

