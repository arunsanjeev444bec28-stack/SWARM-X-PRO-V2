# -*- coding: utf-8 -*-
"""
SWARM-X PRO V2 — Authoritative Warehouse & Robot Geometry Validator
Validates 78-rack warehouse, 98 RF nodes, 175 edges, clearances, and LiDAR parameters.
Produces explicit calculation results and PASS / FAIL for each validation.
"""
import sys
import os

# Ensure backend and root are on PYTHONPATH
_current_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.dirname(_current_dir)
_root_dir = os.path.dirname(_backend_dir)
for p in [_root_dir, _backend_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from backend.data.warehouse_real import validate_warehouse_config
except ImportError:
    from data.warehouse_real import validate_warehouse_config


def main():
    print("=" * 70)
    print(" SWARM-X PRO V2 — AUTHORITATIVE WAREHOUSE GEOMETRY VALIDATION")
    print("=" * 70)

    try:
        report = validate_warehouse_config()
    except Exception as e:
        print(f"\n[FAIL] Validation rejected configuration: {e}")
        sys.exit(1)

    v = report["validations"]

    print("\n--- 1. WAREHOUSE TOPOLOGY & DIMENSIONS ---")
    print(f"Rack count:             {report['rack_count']:4d} racks        [{v['rack_count']}]")
    print(f"RF node count:          {report['rf_node_count']:4d} nodes        [{v['rf_node_count']}]")
    print(f"Graph edge count:       {report['graph_edge_count']:4d} edges        [{v['graph_edge_count']}]")
    print(f"Warehouse X range:      [{report['warehouse_x_range'][0]:.1f}, {report['warehouse_x_range'][1]:.1f}] m")
    print(f"Warehouse Y range:      [{report['warehouse_y_range'][0]:.1f}, {report['warehouse_y_range'][1]:.1f}] m")
    print(f"Warehouse width:        {report['warehouse_width_m']:6.2f} m        [{v['warehouse_dimensions']}]")
    print(f"Warehouse height:       {report['warehouse_height_m']:6.2f} m        [{v['warehouse_dimensions']}]")
    print(f"Rack dimensions (W x D):{report['rack_dimensions_m'][0]:.2f} m x {report['rack_dimensions_m'][1]:.2f} m")
    print(f"RF node spacing (X x Y):{report['rf_node_spacing_m'][0]:.2f} m x {report['rf_node_spacing_m'][1]:.2f} m")
    print(f"Minimum aisle width:    {report['aisle_width_m']:6.2f} m        [{v['aisle_width']}]")

    print("\n--- 2. ROBOT PHYSICAL GEOMETRY & CLEARANCES ---")
    print(f"Robot length:           {report['robot_length_m']:6.2f} m")
    print(f"Robot width:            {report['robot_width_m']:6.2f} m")
    print(f"Robot circumscribed r:  {report['robot_radius_m']:6.4f} m")
    print(f"Available side clearance:{report['available_side_clearance_m']:5.3f} m        [{v['straight_travel_clearance']}]")
    print(f"Required side clearance:{report['required_side_clearance_m']:5.3f} m")
    print(f"Turning clearance:      {report['turning_clearance_m']:6.4f} m        [{v['turning_clearance']}]")
    print(f"Collision margin:       {report['collision_margin_m']:6.2f} m        [{v['collision_margin']}]")

    print("\n--- 3. SENSOR & PERCEPTION SPECIFICATION ---")
    print(f"LiDAR minimum range:    {report['lidar_min_range_m']:6.2f} m        [{v['lidar_range']}]")
    print(f"LiDAR maximum range:    {report['lidar_max_range_m']:6.2f} m        [{v['lidar_range']}]")

    print("\n" + "=" * 70)
    print(f" OVERALL WAREHOUSE VALIDATION STATUS: {v['overall']}")
    print("=" * 70)

    if v["overall"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
