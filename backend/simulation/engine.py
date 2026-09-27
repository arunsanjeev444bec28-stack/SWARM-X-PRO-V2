import asyncio
from core.state import global_state
from coordination.reservation import reservation_manager
from evaluation.metrics import metrics_tracker
from api.websocket import manager

class SimulatorEngine:
    def __init__(self):
        self.is_running = False
        self.current_time_step = 0
        self.dt = 0.5 # seconds per step for clear visual animation
        self.seed = 42
        self.mode = "SWARM_X" # "SWARM_X" or "STOP_AND_WAIT"

    async def run(self, mode="SWARM_X"):
        self.is_running = True
        self.current_time_step = 0
        self.mode = mode
        
        while self.is_running:
            # Advance robots along their planned trajectories
            # To do this correctly, we must know the plan for each robot
            # Handle Dynamic Obstacles
            expired_obstacles = []
            for obs_id, expiration in global_state.dynamic_obstacles.items():
                if self.current_time_step >= expiration:
                    expired_obstacles.append(obs_id)
            for obs_id in expired_obstacles:
                del global_state.dynamic_obstacles[obs_id]

            # Let's assume global state stores active paths
            all_done = True
            
            # Check for FAILED robots to remove them from moving
            for robot in global_state.get_all_robots():
                if robot.status == "FAILED":
                    continue
                    
                # Handle charging timer
                if robot.robot_id in global_state.robot_charging_timers:
                    all_done = False
                    global_state.robot_charging_timers[robot.robot_id] -= 1
                    if global_state.robot_charging_timers[robot.robot_id] <= 0:
                        robot.battery = 100.0
                        robot.temperature = 25.0
                        robot.health = 100.0
                        robot.status = "IDLE" # Or resume task
                        del global_state.robot_charging_timers[robot.robot_id]
                        
                        await manager.broadcast({
                            "event": "CHARGING_COMPLETED",
                            "robot_id": robot.robot_id
                        })
                        
                        # Resume pending work if any (simply handled by external systems recognizing IDLE)
                        # but if we paused a task, it's still in robot_tasks
                        if robot.robot_id in global_state.robot_tasks:
                            robot.status = "ASSIGNED" # Ready to re-plan
                    continue # Skip movement while charging

                # Handle normal movement
                path_info = global_state.robot_paths.get(robot.robot_id)
                moved = False
                if path_info:
                    trajectory = path_info["trajectory"]
                    task_id = path_info["task_id"]
                    pickup_time = path_info.get("pickup_time", -1)
                    
                    if self.current_time_step < len(trajectory):
                        all_done = False
                        step = trajectory[self.current_time_step]
                        step_node_id = step["node_id"] if isinstance(step, dict) else getattr(step, "node_id", str(step))
                        
                        if self.mode == "STOP_AND_WAIT":
                            # In stop-and-wait, verify physical occupancy before moving
                            target_node = step_node_id
                            occupied = False
                            for r in global_state.get_all_robots():
                                if r.robot_id != robot.robot_id and r.node_id == target_node:
                                    occupied = True
                                    break
                            
                            if occupied:
                                # Stay in current position, push back trajectory
                                trajectory.insert(self.current_time_step, trajectory[self.current_time_step - 1] if self.current_time_step > 0 else step)
                                step = trajectory[self.current_time_step]
                                step_node_id = step["node_id"] if isinstance(step, dict) else getattr(step, "node_id", str(step))
                                # Wait fallback metric for baseline
                                metrics_tracker.wait_fallback += 1

                        if step_node_id != robot.node_id:
                            moved = True
                        robot.node_id = step_node_id
                        nd = global_state.get_node(step_node_id)
                        if nd:
                            robot.position = [float(nd.x), float(nd.y), 0.12]

                        if pickup_time > 0 and self.current_time_step < pickup_time:
                            robot.status = "DISPATCHING"
                        elif pickup_time > 0 and self.current_time_step == pickup_time:
                            robot.status = "LOADING"
                        elif self.current_time_step < len(trajectory) - 1:
                            robot.status = "TRANSPORTING"
                        
                        if self.current_time_step == pickup_time:
                            metrics_tracker.pickup_events += 1
                            await manager.broadcast({
                                "event": "PICKUP_REACHED",
                                "robot_id": robot.robot_id,
                                "task_id": task_id
                            })
                            task_obj = global_state.get_task(task_id)
                            robot.load = task_obj.load if task_obj else 1.0
                            
                        if self.current_time_step == len(trajectory) - 1:
                            metrics_tracker.dispatch_events += 1
                            metrics_tracker.completed_tasks += 1
                            metrics_tracker.task_completion_times.append(self.current_time_step)
                            await manager.broadcast({
                                "event": "DISPATCH_REACHED",
                                "robot_id": robot.robot_id,
                                "task_id": task_id
                            })
                            await manager.broadcast({
                                "event": "TASK_COMPLETED",
                                "task_id": task_id
                            })
                            robot.status = "IDLE"
                            robot.load = 0.0
                            # Clear task from robot
                            global_state.robot_tasks.pop(robot.robot_id, None)
                            # Clear path
                            global_state.robot_paths.pop(robot.robot_id, None)

                # --- Battery & Health Logic ---
                battery_before = robot.battery
                drain = 0.1 # Base drain
                if moved:
                    drain += 0.4 + 0.1 * robot.load
                
                robot.battery -= drain
                robot.battery = max(0.0, robot.battery)
                metrics_tracker.battery_consumption += drain
                
                # Health = Battery - 0.5 * (Temperature - 25) - 5 * Load
                h = robot.battery - 0.5 * (robot.temperature - 25.0) - 5.0 * robot.load
                robot.health = max(0.0, min(100.0, h))

                if robot.battery < 20.0 and robot.status not in ["CHARGING", "FAILED"]:
                    await manager.broadcast({
                        "event": "LOW_BATTERY",
                        "robot_id": robot.robot_id,
                        "battery": robot.battery
                    })
                    await manager.broadcast({
                        "event": "EMERGENCY_CHARGE",
                        "robot_id": robot.robot_id
                    })
                    # Emergency charging:
                    metrics_tracker.emergency_charges += 1
                    metrics_tracker.charging_events += 1
                    
                    robot.status = "CHARGING"
                    global_state.robot_charging_timers[robot.robot_id] = 30 # 3 seconds at 0.1 dt
                    
                    await manager.broadcast({
                        "event": "CHARGING_STARTED",
                        "robot_id": robot.robot_id
                    })
                    
                    # Release future reservations if any path exists
                    reservation_manager.release_path(robot.robot_id)
                    # We should technically route to a charger, but for simplicity of simulation, 
                    # we will charge in place if no routing is explicitly done.
                    
                # Broadcast individual ROBOT_STATE_UPDATED event
                robot_node = global_state.nodes.get(robot.node_id)
                await manager.broadcast({
                    "event": "ROBOT_STATE_UPDATED",
                    "timestamp": self.current_time_step, # using timestep as logical timestamp
                    "robot_id": robot.robot_id,
                    "node_id": robot.node_id,
                    "x": robot_node.x if robot_node else 0.0,
                    "y": robot_node.y if robot_node else 0.0,
                    "time_step": self.current_time_step,
                    "battery": robot.battery,
                    "temperature": robot.temperature,
                    "health": robot.health,
                    "status": robot.status,
                    "task_id": global_state.robot_tasks.get(robot.robot_id)
                })

            self.current_time_step += 1
            
            # Keeping SIMULATION_STEP for backwards compatibility, but making it lighter
            await manager.broadcast({
                "event": "SIMULATION_STEP",
                "time_step": self.current_time_step
            })
            
            if all_done and self.current_time_step > 1: # ensure at least 1 step happens
                self.is_running = False
                await manager.broadcast({
                    "event": "SIMULATION_COMPLETED"
                })
                break
                
            if self.current_time_step > 2000:
                print("SIMULATION TIMEOUT REACHED")
                self.is_running = False
                # Optionally mark uncompleted tasks as failed
                break

            await asyncio.sleep(self.dt)

simulator = SimulatorEngine()
