from __future__ import annotations

import argparse

from edge_agents.robot_agent.agent import EdgeRobotAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Start an independent robot edge-agent process.")
    parser.add_argument("--robot-id", required=True, choices=["R1", "R2", "R3", "R4"])
    args = parser.parse_args()

    agent = EdgeRobotAgent(args.robot_id)
    agent.run()


if __name__ == "__main__":
    main()
