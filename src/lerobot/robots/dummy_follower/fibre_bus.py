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
        return self._connected and self._robot is not None

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
        if not self.is_connected:
            raise RuntimeError("Not connected to Dummy arm")

        try:
            # Read joint positions from robot
            # The Dummy arm exposes joint positions via robot.j1, robot.j2, etc.
            positions = {}
            for i, name in enumerate(self.JOINT_NAMES):
                raw_pos = getattr(self._robot, f"j{i+1}", 0.0)
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
            positions: Dictionary mapping joint names to target positions in degrees.
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to Dummy arm")

        try:
            # Convert positions to list, applying inverse offset
            target_positions = []
            for i, name in enumerate(self.JOINT_NAMES):
                if name in positions:
                    # Remove offset to get raw position
                    target = positions[name] - self.joint_offset[i]
                    target_positions.append(target)
                else:
                    # Keep current position if not specified
                    current = getattr(self._robot, f"j{i+1}", 0.0)
                    target_positions.append(current)

            # Send command to robot
            self._robot.move_j(*target_positions)

        except Exception as e:
            logger.error(f"Failed to send joint positions: {e}")
            raise

    def enable_torque(self) -> None:
        """Enable torque on all joints."""
        if not self.is_connected:
            raise RuntimeError("Not connected to Dummy arm")

        try:
            if hasattr(self._robot, "enable"):
                self._robot.enable()
            logger.debug("Torque enabled")
        except Exception as e:
            logger.warning(f"Failed to enable torque: {e}")

    def disable_torque(self) -> None:
        """Disable torque on all joints."""
        if not self.is_connected:
            raise RuntimeError("Not connected to Dummy arm")

        try:
            if hasattr(self._robot, "disable"):
                self._robot.disable()
            logger.debug("Torque disabled")
        except Exception as e:
            logger.warning(f"Failed to disable torque: {e}")
