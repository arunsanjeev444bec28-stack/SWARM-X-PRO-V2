import pytest
import asyncio
from core.state import global_state
from models.schemas import Node
from planning.congestion import calculate_congestion
from evaluation.metrics import metrics_tracker
from coordination.reservation import reservation_manager

@pytest.mark.asyncio
async def test_congestion():
    global_state.reset()
    reservation_manager.reset()
    
    # We create a bow-tie grid so the center node becomes highly congested.
    # N1 - N2 \       / N4 - N5
    #          -> N3 <-
    # N6 - N7 /       \ N8 - N9
    
    global_state.add_node(Node(node_id="N1", x=0, y=0, type="NORMAL", neighbors=["N2"]))
    global_state.add_node(Node(node_id="N2", x=1, y=0, type="NORMAL", neighbors=["N1", "N3"]))
    
    global_state.add_node(Node(node_id="N6", x=0, y=2, type="NORMAL", neighbors=["N7"]))
    global_state.add_node(Node(node_id="N7", x=1, y=2, type="NORMAL", neighbors=["N6", "N3"]))
    
    global_state.add_node(Node(node_id="N3", x=2, y=1, type="NORMAL", neighbors=["N2", "N7", "N4", "N8"]))
    
    global_state.add_node(Node(node_id="N4", x=3, y=0, type="NORMAL", neighbors=["N3", "N5"]))
    global_state.add_node(Node(node_id="N5", x=4, y=0, type="NORMAL", neighbors=["N4"]))
    
    global_state.add_node(Node(node_id="N8", x=3, y=2, type="NORMAL", neighbors=["N3", "N9"]))
    global_state.add_node(Node(node_id="N9", x=4, y=2, type="NORMAL", neighbors=["N8"]))
    
    await calculate_congestion(trials=300)
    
    # N3 is a chokepoint and should definitely be congested
    assert "N3" in global_state.congestion_map
    assert global_state.congestion_map["N3"] > 0.30
    assert metrics_tracker.congested_nodes >= 1
    assert metrics_tracker.congestion_probability > 0.30
