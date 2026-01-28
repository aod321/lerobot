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

logger = logging.getLogger(__name__)


def _get_fibre_bus_class():
    """Lazy import to avoid circular dependency."""
    from lerobot.robots.dummy_follower.fibre_bus import FibreBus
    return FibreBus


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

        # Initialize fibre bus for arm communication (lazy import to avoid circular dependency)
        FibreBus = _get_fibre_bus_class()
        self.bus = FibreBus(
            serial_number=config.serial_number,
            joint_offset=config.joint_offset,
        )

        # Initialize gripper controller if enabled
        self._gripper: DMCanGripper | None = None
        self._gripper_mode: str | None = None  # "dm_can" or "fibre"

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
            not self.config.gripper_enabled or self._gripper_mode is not None
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
        """Connect to the gripper using the configured connection mode."""
        if self.config.gripper_connection_mode == "fibre":
            self._connect_gripper_fibre()
        else:
            self._connect_gripper_dm_can()

    def _connect_gripper_fibre(self) -> None:
        """Connect to the gripper via fibre direct connection."""
        try:
            self.bus.enable_hand()
            self.bus.set_hand_zero()
            # Leader gripper: enabled and ready to read position
            self._gripper_mode = "fibre"
            logger.info("Leader gripper connected via fibre")
        except Exception as e:
            logger.warning(f"Failed to connect leader gripper via fibre: {e}")
            self._gripper_mode = None

    def _connect_gripper_dm_can(self) -> None:
        """Connect to the DMH3510 gripper via DM_CAN (serial-to-CAN)."""
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
            self._gripper_mode = "dm_can"
            logger.info("Leader gripper connected via DM_CAN")
        except Exception as e:
            logger.warning(f"Failed to connect leader gripper via DM_CAN: {e}")
            self._gripper = None
            self._gripper_mode = None

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
        """Configure the teleoperator for operation.

        Only enables torque. Moving to work pose is handled by the caller
        (e.g., lerobot_teleoperate.py) to allow simultaneous movement with follower.
        """
        self.bus.enable_torque()

    def prepare_recording_start(self, robot=None) -> None:
        """Prepare for recording start by syncing gripper zeros and disabling leader torque.

        Called from WAITING state after user presses Enter to start recording.
        This syncs both gripper zero positions so the follower won't jump when recording starts.

        Args:
            robot: Optional robot instance (DummyFollower) to sync gripper zero.
        """
        # Sync gripper zeros - set current positions as zero for both grippers
        # This prevents follower gripper from jumping to leader's position
        if self._gripper_mode == "fibre":
            self.bus.set_hand_zero()
            self.bus.enable_hand()  # 刷新数据，确保位置值相对于新零点
            logger.info("Leader gripper zero position set")

        if robot is not None and hasattr(robot, 'bus') and hasattr(robot, '_gripper_mode'):
            if robot._gripper_mode == "fibre":
                robot.bus.set_hand_zero()
                robot.bus.enable_hand()  # 刷新数据，确保位置值相对于新零点
                logger.info("Follower gripper zero position set")

        self.bus.disable_torque()
        logger.info("Leader torque disabled - arm is now free for teaching")

    def prepare_for_next_episode(self, robot=None, events: dict | None = None, skip_arm_movement: bool = False) -> bool:
        """Prepare the leader arm for the next episode.

        This method is called between episodes during recording to:
        1. Enable torque and move the leader arm back to work pose (unless skip_arm_movement=True)
        2. Disable follower gripper torque so user can manually reset it
        3. Enable follower gripper and set zero position

        NOTE: Does NOT wait for user input or disable leader torque.
        The WAITING state in lerobot_record.py will handle user confirmation
        and call prepare_recording_start() to disable torque.

        Args:
            robot: Optional robot instance. If provided, both arms will move
                   to work pose simultaneously for faster reset.
            events: Optional event dictionary from keyboard listener (unused,
                    kept for API compatibility).
            skip_arm_movement: If True, skip the arm movement (already done in SAVING state).

        Returns:
            True: Always returns True (no interruption possible here)
        """
        if not skip_arm_movement:
            # CRITICAL: Enable torque first - leader was disabled for teaching!
            # Cannot move_j on a disabled arm.
            self.bus.enable_torque()

            # Move both arms simultaneously if robot is provided
            if robot is not None and hasattr(robot, 'bus'):
                logger.info("Moving both arms to work pose simultaneously...")
                robot.bus.enable_torque()
                robot.bus.move_to_pose(robot.config.work_pose)  # Non-blocking
                self.bus.move_to_pose(self.config.work_pose)    # Non-blocking
            else:
                logger.info("Moving leader to work pose...")
                self.bus.move_to_pose(self.config.work_pose)

            # Wait once for both moves to complete
            time.sleep(2.0)

        # Disable follower gripper torque so user can manually reset it
        self._disable_follower_gripper(robot)

        # Enable follower gripper and set zero position
        self._enable_follower_gripper_and_set_zero(robot)

        # NOTE: Do not disable leader torque here - it will be done in prepare_recording_start()
        # after user confirms they are ready in WAITING state
        return True

    def _disable_follower_gripper(self, robot) -> None:
        """Disable follower gripper torque so user can manually reset it.

        Args:
            robot: The robot instance (DummyFollower).
        """
        if robot is None or not hasattr(robot, 'bus'):
            return

        try:
            robot.bus.disable_hand()
            logger.info("Follower gripper torque disabled for manual reset")
        except Exception as e:
            logger.warning(f"Failed to disable follower gripper: {e}")

    def _enable_follower_gripper_and_set_zero(self, robot) -> None:
        """Enable follower gripper and set zero position.

        Args:
            robot: The robot instance (DummyFollower).
        """
        if robot is None or not hasattr(robot, 'bus'):
            return

        try:
            robot.bus.enable_hand()
            robot.bus.set_hand_zero()
            logger.info("Follower gripper enabled and zero position set")
        except Exception as e:
            logger.warning(f"Failed to enable follower gripper: {e}")

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
        if self.config.gripper_enabled and self._gripper_mode is not None:
            start = time.perf_counter()
            if self._gripper_mode == "fibre":
                # Read position via fibre direct connection (radians)
                gripper_pos = self.bus.get_hand_position()
                logger.debug(f"Leader gripper position: {gripper_pos:.4f} rad")
            else:
                # Read position via DM_CAN
                gripper_pos = self._gripper.get_position() if self._gripper else 0.0
            action[f"{self.GRIPPER_JOINT}.pos"] = gripper_pos
            dt_ms = (time.perf_counter() - start) * 1e3
            logger.debug(f"{self} read gripper: {dt_ms:.1f}ms")
        elif self.config.gripper_enabled:
            # Default gripper position if not connected (radians)
            action[f"{self.GRIPPER_JOINT}.pos"] = 0.0

        return action

    def send_feedback(self, feedback: dict[str, Any]) -> None:
        """
        Send feedback to the teleoperator for force feedback.

        Args:
            feedback: Dictionary with feedback values (e.g., gripper torque).
        """
        if not self.config.force_feedback_enabled:
            return

        if self._gripper_mode is None:
            return

        torque_key = f"{self.GRIPPER_JOINT}.torque"
        if torque_key in feedback:
            torque = feedback[torque_key] * self.config.force_feedback_scale
            if self._gripper_mode == "fibre":
                # Send force feedback via fibre direct connection
                # Use MIT control with only torque (kp=0, kd=0)
                self.bus.control_hand_mit(0.0, 0.0, 0.0, 0.0, torque)
            elif self._gripper is not None:
                # Send force feedback via DM_CAN
                self._gripper.send_feedback_torque(torque)

    @check_if_not_connected
    def disconnect(self) -> None:
        """Disconnect from the teleoperator."""
        # 1. 安全 resting 流程（在失能前）
        if self.bus.is_connected:
            try:
                self.bus.enable_torque()
                self.bus.resting()
                time.sleep(2.0)  # 等待到位
            except Exception as e:
                logger.warning(f"Failed to move to resting pose: {e}")

        # 2. Disconnect gripper
        if self._gripper_mode == "fibre":
            try:
                self.bus.disable_hand()
            except Exception as e:
                logger.warning(f"Failed to disable hand: {e}")
        elif self._gripper_mode == "dm_can" and self._gripper is not None:
            self._gripper.disconnect()
            self._gripper = None
        self._gripper_mode = None

        # 3. Disconnect arm
        self.bus.disconnect()

        logger.info(f"{self} disconnected.")
