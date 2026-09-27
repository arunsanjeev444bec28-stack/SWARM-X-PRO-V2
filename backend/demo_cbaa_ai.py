import asyncio
from core.state import global_state
from models.schemas import Node, Robot, Task
from allocation.cbaa import allocator

async def main():
    print("=== SWARM-X PRO V2 Phase 4: CBAA Edge-AI Integration Demo ===")
    
    # We will use the identical scenario and run CBAA twice
    
    def setup_scenario():
        global_state.reset()
        # Setup specific adverse node that has high congestion/degradation
        from evaluation.metrics import metrics_tracker
        metrics_tracker.reset()
        metrics_tracker.congestion_probability = 0.9
        
        global_state.add_node(Node(node_id="N0", x=0, y=0, type="WAYPOINT", neighbors=["N1"], health=100))
        global_state.add_node(Node(node_id="N1", x=1, y=0, type="WAYPOINT", neighbors=["N0", "N2"], health=100.0))
        global_state.add_node(Node(node_id="N2", x=2, y=0, type="WAYPOINT", neighbors=["N1"], health=100.0))
        
        # Robot 1: Low battery. Near the pickup.
        global_state.robots["R1"] = Robot(robot_id="R1", node_id="N1", battery=12.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
        
        # Robot 2: Good state, but further away (N2).
        global_state.robots["R2"] = Robot(robot_id="R2", node_id="N2", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
        
        global_state.tasks["T1"] = Task(task_id="T1", pickup_node="N1", dispatch_node="N0", priority="HIGH", urgency=1.0, deadline=10.0, load=1.0, energy_requirement=5.0)
        
    print("\n--- SCENARIO A: risk_weight = 0.0 ---")
    setup_scenario()
    allocator.risk_weight = 0.0
    res_a = allocator.allocate_task("T1")
    if res_a.bids:
        for r_id, b in res_a.bids.items():
            print(f"Robot {r_id}:")
            print(f"  Base Bid:         {b['base_bid']:.2f}")
            print(f"  Risk Probability: {b['risk_probability']:.2f}")
            print(f"  Risk Penalty:     {b['risk_penalty']:.2f}")
            print(f"  Final Bid:        {b['final_bid']:.2f}")
    print(f">> Winner: {res_a.winner}")
    
    print("\n--- SCENARIO B: risk_weight = 100.0 ---")
    setup_scenario()
    allocator.risk_weight = 100.0
    res_b = allocator.allocate_task("T1")
    if res_b.bids:
        for r_id, b in res_b.bids.items():
            print(f"Robot {r_id}:")
            print(f"  Base Bid:         {b['base_bid']:.2f}")
            print(f"  Risk Probability: {b['risk_probability']:.2f}")
            print(f"  Risk Penalty:     {b['risk_penalty']:.2f}")
            print(f"  Final Bid:        {b['final_bid']:.2f}")
    print(f">> Winner: {res_b.winner}")
    
    if res_a.winner != res_b.winner:
        print("\nSUCCESS: Edge-AI successfully changed the allocation outcome based on predicted risk.")
    else:
        print("\nOutcome was unchanged. Both robots might have similar risk profiles, or difference wasn't enough to sway the bid.")

if __name__ == "__main__":
    asyncio.run(main())
