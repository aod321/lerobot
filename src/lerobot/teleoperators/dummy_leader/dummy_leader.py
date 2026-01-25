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
Dummy Leader Teleoperator implementation for LeRobot.

This module implements the Teleoperator interface for the Dummy 6-DOF robot arm
used as a teaching device with an optional DMH3510 gripper for force feedback.
"""

import logging
import math
import time
from typing import Any

from lerobot.processor import RobotAction
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected

from ..teleoperator import Teleoperator
from .config_dummy_leader import DummyLeaderConfig
from .dm_can_gripper import DMCanGripper

# Import FibreBus from the robot module
from lerobot.robots.dummy_follower.fibre_bus import FibreBus

logger = logging.getLogger(__name__)


class DummyLeader(Teleoperator):
    """
    Dummy Leader Teleoperator - 6-DOF arm with optional DMH3510 gripper.

    This teleoperator reads joint positions from a teaching arm and provides
    optional force feedback through the gripper.

    Serial numbers:
        - Leader arm: 3950366E3233
        - Follower arm: 396636713233

    Joint names: j1, j2, j3, j4, j5, j6, gripper
    """

    config_class = DummyLeaderConfig
    name = "dummy_leader"

    # Motor/joint names
    ARM_JOINTS = ["j1", "j2", "j3", "j4", "j5", "j6"]
    GRIPPER_JOINT = "gripper"

    def __init__(self, config: DummyLeaderConfig):
        super().__init__(config)
        self.config = config

        # Initialize fibre bus for arm communication
        self.bus = FibreBus(
            serial_number=config.serial_number,
            joint_offset=config.joint_offset,
        )

        # Initialize gripper controller if enabled
        self._gripper: DMCanGripper | None = None

    @property
    def action_features(self) -> dict[str, type]:
        """Actions produced by the teleoperator (joint positions to send to follower)."""
        features = {f"{joint}.pos": float for joint in self.ARM_JOINTS}
        if self.config.gripper_enabled:
            features[f"{self.GRIPPER_JOINT}.pos"] = float
        return features

    @property
    def feedback_features(self) -> dict[str, type]:
        """Feedback features for force feedback."""
        if self.config.force_feedback_enabled and self.config.gripper_enabled:
            return {f"{self.GRIPPER_JOINT}.torque": float}
        return {}

    @property
    def is_connected(self) -> bool:
        arm_connected = self.bus.is_connected
        gripper_connected = (
            not self.config.gripper_enabled or
            (self._gripper is not None and self._gripper.is_connected)
        )
        return arm_connected and gripper_connected

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        """
        Connect to the Dummy leader arm and gripper.

        Args:
            calibrate: If True, run calibration if needed (not used for Dummy arm).
        """
        # Connect arm via fibre
        self.bus.connect()

        # Connect gripper via DM_CAN if enabled
        if self.config.gripper_enabled:
            self._connect_gripper()

        # Configure the teleoperator
        self.configure()
        logger.info(f"{self} connected.")

    def _connect_gripper(self) -> None:
        """Connect to the DMH3510 gripper via DM_CAN."""
        try:
            self._gripper = DMCanGripper(
                serial_port=self.config.gripper_serial_port,
                baudrate=self.config.gripper_baudrate,
                motor_id=self.config.gripper_motor_id,
                master_id=self.config.gripper_master_id,
                kp=self.config.feedback_kp,
                kd=self.config.feedback_kd,
            )
            self._gripper.connect()
            logger.info("Leader gripper connected")
        except Exception as e:
            logger.warning(f"Failed to connect leader gripper: {e}")
            self._gripper = None

    @property
    def is_calibrated(self) -> bool:
        """Dummy arm doesn't require calibration - always return True."""
        return True

    def calibrate(self) -> None:
        """
        Calibrate the teleoperator.

        The Dummy arm doesn't require traditional calibration.
        This is a no-op.
        """
        logger.info("Dummy leader calibration not required")

    def configure(self) -> None:
        """Configure the teleoperator for operation."""
        # For leader arm, we typically don't enable torque so it can be moved freely
        # Only the gripper may have torque for force feedback
        self.bus.disable_torque()
        logger.debug("Leader configured (torque disabled for free movement)")

    @check_if_not_connected
    def get_action(self) -> RobotAction:
        """
        Get current action (joint positions) from the leader arm.

        Returns:
            Dictionary with joint positions to command the follower.
        """
        start = time.perf_counter()
        action: RobotAction = {}

        # Read arm joint positions
        joint_positions = self.bus.get_joint_positions()
        for joint, pos in joint_positions.items():
            if self.config.use_degrees:
                action[f"{joint}.pos"] = pos
            else:
                action[f"{joint}.pos"] = math.radians(pos)

        dt_ms = (time.perf_counter() - start) * 1e3
        logger.debug(f"{self} read action: {dt_ms:.1f}ms")

        # Read gripper position if enabled
        if self.config.gripper_enabled and self._gripper is not None:
            start = time.perf_counter()
            gripper_pos = self._gripper.get_position()
            action[f"{self.GRIPPER_JOINT}.pos"] = gripper_pos
            dt_ms = (time.perf_counter() - start) * 1e3
            logger.debug(f"{self} read gripper: {dt_ms:.1f}ms")
        elif self.config.gripper_enabled:
            # Default gripper position if not connected
            action[f"{self.GRIPPER_JOINT}.pos"] = 50.0

        return action

    def send_feedback(self, feedback: dict[str, Any]) -> None:
        """
        Send feedback to the teleoperator for force feedback.

        Args:
            feedback: Dictionary with feedback values (e.g., gripper torque).
        """
        if not self.config.force_feedback_enabled:
            return

        if self._gripper is None:
            return

        torque_key = f"{self.GRIPPER_JOINT}.torque"
        if torque_key in feedback:
            torque = feedback[torque_key] * self.config.force_feedback_scale
            self._gripper.send_feedback_torque(torque)

    @check_if_not_connected
    def disconnect(self) -> None:
        """Disconnect from the teleoperator."""
        # Disconnect arm
        self.bus.disconnect()

        # Disconnect gripper
        if self._gripper is not None:
            self._gripper.disconnect()
            self._gripper = None

        logger.info(f"{self} disconnected.")
