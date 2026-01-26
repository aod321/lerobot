#!/usr/bin/env python

# Copyright 2025 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Fibre communication wrapper for Dummy robot arm.

This module provides a communication interface for the Dummy 6-DOF robot arm
using the fibre library. The arm communicates via USB with a unique serial number.
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class FibreBus:
    """
    Communication bus for Dummy robot arm using fibre library.

    The Dummy arm has 6 joints controlled via the fibre protocol.
    Joint positions are in degrees.
    """

    # Joint names for the 6-DOF arm
    JOINT_NAMES = ["j1", "j2", "j3", "j4", "j5", "j6"]

    def __init__(
        self,
        serial_number: str,
        joint_offset: list[float] | None = None,
    ):
        """
        Initialize the FibreBus.

        Args:
            serial_number: The serial number of the Dummy arm to connect to.
            joint_offset: Joint offset in degrees for each joint.
        """
        self.serial_number = serial_number
        self.joint_offset = joint_offset if joint_offset else [0.0] * 6
        self._robot: Any = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        if not self._connected or self._robot is None:
            return False
        # Also check if robot attribute is still valid (cleared on channel break)
        try:
            return "robot" in self._robot._remote_attributes
        except Exception:
            return False

    def _on_channel_broken(self) -> None:
        """Called when the fibre channel is broken."""
        logger.warning("Fibre channel broken, marking as disconnected")
        self._connected = False

    def _check_connection(self) -> None:
        """Verify the connection is still valid."""
        if not self._connected or self._robot is None:
            raise RuntimeError("Not connected to Dummy arm")

        # Check if robot attribute still exists (cleared on channel break)
        if not hasattr(self._robot, "robot") or "robot" not in self._robot._remote_attributes:
            self._connected = False
            raise RuntimeError("Connection to Dummy arm lost (channel broken)")

    def connect(self) -> None:
        """Connect to the Dummy arm via fibre."""
        if self._connected:
            logger.warning("FibreBus already connected")
            return

        try:
            from lerobot.third_party import fibre

            logger.info(f"Connecting to Dummy arm with serial number: {self.serial_number}")
            self._robot = fibre.find_any(serial_number=self.serial_number, timeout=10)

            if self._robot is None:
                raise ConnectionError(f"Could not find Dummy arm with serial number: {self.serial_number}")

            # Subscribe to channel broken event to detect disconnections
            try:
                self._robot.__channel__._channel_broken.subscribe(self._on_channel_broken)
            except Exception as e:
                logger.debug(f"Could not subscribe to channel events: {e}")

            self._connected = True
            logger.info(f"Connected to Dummy arm: {self.serial_number}")

        except ImportError as e:
            raise ImportError(
                "fibre library is required for Dummy arm. "
                "The library should be in lerobot.third_party.fibre"
            ) from e
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"Failed to connect to Dummy arm: {e}") from e

    def disconnect(self) -> None:
        """Disconnect from the Dummy arm."""
        if not self._connected:
            return

        try:
            # Fibre doesn't have explicit disconnect, but we clear our reference
            self._robot = None
            self._connected = False
            logger.info("Disconnected from Dummy arm")
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")
            self._robot = None
            self._connected = False

    def get_joint_positions(self) -> dict[str, float]:
        """
        Read current joint positions from the arm.

        Returns:
            Dictionary mapping joint names to positions in degrees.
        """
        self._check_connection()

        try:
            # Read joint positions from robot
            # The Dummy arm exposes joint positions via robot.j1, robot.j2, etc.
            positions = {}
            for i, name in enumerate(self.JOINT_NAMES):
                joint = getattr(self._robot.robot, f"joint_{i+1}")
                raw_pos = joint.angle
                # Apply joint offset
                positions[name] = raw_pos + self.joint_offset[i]

            return positions

        except Exception as e:
            logger.error(f"Failed to read joint positions: {e}")
            raise

    def move_j(self, positions: dict[str, float]) -> None:
        """
        Send joint position commands to the arm.

        Args:
            positions: Dictionary mapping joint names to target positions in degrees (kinematic angles).
        """
        self._check_connection()

        try:
            target_positions = []
            for i, name in enumerate(self.JOINT_NAMES):
                if name in positions:
                    # Directly use kinematic angles - move_j API already expects kinematic angles
                    target_positions.append(positions[name])
                else:
                    # Keep current position (read raw angle and add offset to get kinematic angle)
                    joint = getattr(self._robot.robot, f"joint_{i+1}")
                    current = joint.angle + self.joint_offset[i]
                    target_positions.append(current)

            # Send command to robot
            self._robot.robot.move_j(*target_positions)

        except Exception as e:
            logger.error(f"Failed to send joint positions: {e}")
            raise

    def move_to_pose(self, pose: list[float]) -> None:
        """
        Move all joints to the specified pose.

        Args:
            pose: Target pose in degrees [j1, j2, j3, j4, j5, j6] (kinematic angles).
        """
        positions = {name: pose[i] for i, name in enumerate(self.JOINT_NAMES)}
        self.move_j(positions)

    def enable_torque(self) -> None:
        """Enable torque on all joints."""
        self._check_connection()

        try:
            # Call twice for reliability (as per reference code pattern)
            self._robot.robot.set_enable(True)
            self._robot.robot.set_enable(True)
            logger.debug("Torque enabled")
        except Exception as e:
            logger.warning(f"Failed to enable torque: {e}")

    def disable_torque(self) -> None:
        """Disable torque on all joints."""
        self._check_connection()

        try:
            # Call twice for reliability (as per reference code pattern in real_single_arm_teleop_joint.py lines 154, 156)
            self._robot.robot.set_enable(False)
            self._robot.robot.set_enable(False)
            logger.debug("Torque disabled")
        except Exception as e:
            logger.warning(f"Failed to disable torque: {e}")

    # ========== Hand/Gripper methods (fibre direct connection) ==========

    def enable_hand(self) -> None:
        """Enable the gripper (hand) via fibre direct connection."""
        self._check_connection()

        try:
            self._robot.robot.hand.set_enable(True)
            logger.debug("Hand enabled")
        except Exception as e:
            logger.warning(f"Failed to enable hand: {e}")

    def disable_hand(self) -> None:
        """Disable the gripper (hand) via fibre direct connection."""
        self._check_connection()

        try:
            self._robot.robot.hand.set_enable(False)
            logger.debug("Hand disabled")
        except Exception as e:
            logger.warning(f"Failed to disable hand: {e}")

    def set_hand_zero(self) -> None:
        """Set the gripper zero position."""
        self._check_connection()

        try:
            self._robot.robot.hand.set_zero()
            logger.debug("Hand zero position set")
        except Exception as e:
            logger.warning(f"Failed to set hand zero: {e}")

    def get_hand_position(self) -> float:
        """
        Read gripper position via fibre direct connection.

        Returns:
            Position angle in radians.
        """
        self._check_connection()

        try:
            # Refresh state by calling set_enable (per arm_angle.py pattern)
            self._robot.robot.hand.set_enable(True)
            return self._robot.robot.hand.position
        except Exception as e:
            logger.warning(f"Failed to read hand position: {e}")
            return 0.0

    def get_hand_torque(self) -> float:
        """
        Read gripper torque via fibre direct connection.

        Returns:
            Torque value.
        """
        self._check_connection()

        try:
            # Refresh state first
            self._robot.robot.hand.set_enable(True)
            return self._robot.robot.hand.torque
        except Exception as e:
            logger.warning(f"Failed to read hand torque: {e}")
            return 0.0

    def control_hand_mit(
        self, kp: float, kd: float, pos: float, vel: float, torque: float
    ) -> None:
        """
        Send MIT control command to gripper via fibre direct connection.

        Args:
            kp: Position gain.
            kd: Velocity gain.
            pos: Target position in radians.
            vel: Target velocity.
            torque: Feedforward torque.
        """
        self._check_connection()

        try:
            self._robot.robot.hand.control_mit(kp, kd, pos, vel, torque)
        except Exception as e:
            logger.warning(f"Failed to send hand MIT control: {e}")

    def refresh_hand(self) -> None:
        """Refresh hand state by calling set_enable."""
        if not self.is_connected:
            return
        try:
            self._robot.robot.hand.set_enable(True)
        except Exception as e:
            logger.debug(f"Failed to refresh hand: {e}")

    def resting(self) -> None:
        """移动机械臂到 resting 位置（安全位置）"""
        self._check_connection()
        self._robot.robot.resting()
