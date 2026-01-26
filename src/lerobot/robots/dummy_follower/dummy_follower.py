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
Dummy Follower Robot implementation for LeRobot.

This module implements the Robot interface for the Dummy 6-DOF robot arm
with an optional DMH3510 gripper.
"""

import logging
import math
import time
from functools import cached_property
from typing import Any

from lerobot.cameras.utils import make_cameras_from_configs
from lerobot.processor import RobotAction, RobotObservation
from lerobot.utils.decorators import check_if_already_connected, check_if_not_connected

from ..robot import Robot
from ..utils import ensure_safe_goal_position
from .config_dummy_follower import DummyFollowerConfig
from .fibre_bus import FibreBus

logger = logging.getLogger(__name__)


class DummyFollower(Robot):
    """
    Dummy Follower Robot - 6-DOF arm with optional DMH3510 gripper.

    This robot uses fibre for arm communication and DM_CAN for gripper control.
    Serial numbers:
        - Follower arm: 396636713233
        - Leader arm: 3950366E3233

    Joint names: j1, j2, j3, j4, j5, j6, gripper
    """

    config_class = DummyFollowerConfig
    name = "dummy_follower"

    # Motor/joint names
    ARM_JOINTS = ["j1", "j2", "j3", "j4", "j5", "j6"]
    GRIPPER_JOINT = "gripper"

    def __init__(self, config: DummyFollowerConfig):
        super().__init__(config)
        self.config = config

        # Initialize fibre bus for arm communication
        self.bus = FibreBus(
            serial_number=config.serial_number,
            joint_offset=config.joint_offset,
        )

        # Initialize gripper controller if enabled
        self._gripper_controller: Any = None
        self._gripper_motor: Any = None
        self._gripper_mode: str | None = None  # "fibre" or "dm_can"
        self._gripper_position: float = 0.0  # Cached gripper position (radians)

        # Initialize cameras
        self.cameras = make_cameras_from_configs(config.cameras)

    @property
    def _motors_ft(self) -> dict[str, type]:
        """Motor feature types for observation/action."""
        features = {f"{joint}.pos": float for joint in self.ARM_JOINTS}
        if self.config.gripper_enabled:
            features[f"{self.GRIPPER_JOINT}.pos"] = float
        return features

    @property
    def _cameras_ft(self) -> dict[str, tuple]:
        """Camera feature types for observation."""
        return {
            cam: (self.config.cameras[cam].height, self.config.cameras[cam].width, 3)
            for cam in self.cameras
        }

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        return {**self._motors_ft, **self._cameras_ft}

    @cached_property
    def action_features(self) -> dict[str, type]:
        return self._motors_ft

    @property
    def is_connected(self) -> bool:
        arm_connected = self.bus.is_connected
        cameras_connected = all(cam.is_connected for cam in self.cameras.values())
        gripper_connected = (
            not self.config.gripper_enabled or self._gripper_mode is not None
        )
        return arm_connected and cameras_connected and gripper_connected

    @check_if_already_connected
    def connect(self, calibrate: bool = True) -> None:
        """
        Connect to the Dummy arm, gripper, and cameras.

        Args:
            calibrate: If True, run calibration if needed (not used for Dummy arm).
        """
        # Connect arm via fibre
        self.bus.connect()

        # Connect gripper via DM_CAN if enabled
        if self.config.gripper_enabled:
            self._connect_gripper()

        # Connect cameras
        for cam in self.cameras.values():
            cam.connect()

        # Configure the robot
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
            self._gripper_mode = "fibre"
            logger.info("Gripper connected via fibre")
        except Exception as e:
            logger.error(f"Failed to connect gripper via fibre: {e}")
            self._gripper_mode = None

    def _connect_gripper_dm_can(self) -> None:
        """Connect to the DMH3510 gripper via DM_CAN (serial-to-CAN)."""
        try:
            import serial
            from lerobot.third_party.DM_CAN import Control_Type, DM_Motor_Type, Motor, MotorControl

            # Create serial object for DM_CAN
            serial_device = serial.Serial(
                port=self.config.gripper_serial_port,
                baudrate=self.config.gripper_baudrate,
            )

            # Initialize motor control with serial object
            self._gripper_controller = MotorControl(serial_device)

            # Create motor instance for DMH3510
            self._gripper_motor = Motor(
                DM_Motor_Type.DMH3510,
                self.config.gripper_motor_id,
                self.config.gripper_master_id,
            )

            # Add motor to controller and enable
            self._gripper_controller.addMotor(self._gripper_motor)
            self._gripper_controller.enable(self._gripper_motor)
            self._gripper_controller.switchControlMode(self._gripper_motor, Control_Type.MIT)

            self._gripper_mode = "dm_can"
            logger.info("Gripper connected via DM_CAN")

        except ImportError as e:
            logger.warning(
                f"DM_CAN library not available, gripper will be disabled: {e}"
            )
            self._gripper_controller = None
            self._gripper_mode = None
        except Exception as e:
            logger.error(f"Failed to connect gripper via DM_CAN: {e}")
            self._gripper_controller = None
            self._gripper_mode = None

    @property
    def is_calibrated(self) -> bool:
        """Dummy arm doesn't require calibration - always return True."""
        return True

    def calibrate(self) -> None:
        """
        Calibrate the robot.

        The Dummy arm doesn't require traditional calibration like Dynamixel motors.
        This is a no-op.
        """
        logger.info("Dummy arm calibration not required")

    def configure(self) -> None:
        """Configure the robot for operation."""
        # Enable torque on the arm
        self.bus.enable_torque()
        # Move to work pose (don't wait - leader will wait for both)
        logger.info("Moving follower to work pose...")
        self.bus.move_to_pose(self.config.work_pose)
        logger.debug("Robot configured")

    def reset(self) -> None:
        """Reset the robot to work pose between episodes."""
        logger.info("Resetting follower to work pose...")
        self.bus.enable_torque()
        self.bus.move_to_pose(self.config.work_pose)
        time.sleep(2.0)

    @check_if_not_connected
    def get_observation(self) -> RobotObservation:
        """
        Get current observation from the robot.

        Returns:
            Dictionary with joint positions and camera images.
        """
        start = time.perf_counter()
        obs_dict: RobotObservation = {}

        # Read arm joint positions
        joint_positions = self.bus.get_joint_positions()
        for joint, pos in joint_positions.items():
            if self.config.use_degrees:
                obs_dict[f"{joint}.pos"] = pos
            else:
                obs_dict[f"{joint}.pos"] = math.radians(pos)

        dt_ms = (time.perf_counter() - start) * 1e3
        logger.debug(f"{self} read arm state: {dt_ms:.1f}ms")

        # Read gripper position if enabled
        if self.config.gripper_enabled:
            start = time.perf_counter()
            gripper_pos = self._read_gripper_position()
            obs_dict[f"{self.GRIPPER_JOINT}.pos"] = gripper_pos
            dt_ms = (time.perf_counter() - start) * 1e3
            logger.debug(f"{self} read gripper: {dt_ms:.1f}ms")

        # Capture images from cameras
        for cam_key, cam in self.cameras.items():
            start = time.perf_counter()
            obs_dict[cam_key] = cam.async_read()
            dt_ms = (time.perf_counter() - start) * 1e3
            logger.debug(f"{self} read {cam_key}: {dt_ms:.1f}ms")

        return obs_dict

    def _read_gripper_position(self) -> float:
        """Read gripper position (radians)."""
        if self._gripper_mode is None:
            return self._gripper_position

        try:
            if self._gripper_mode == "fibre":
                self._gripper_position = self.bus.get_hand_position()
            else:
                state = self._gripper_controller.read(self._gripper_motor)
                self._gripper_position = state.q if state is not None else 0.0

            logger.debug(f"Follower gripper position: {self._gripper_position:.4f} rad")

        except Exception as e:
            logger.debug(f"Failed to read gripper position: {e}")

        return self._gripper_position

    @check_if_not_connected
    def send_action(self, action: RobotAction) -> RobotAction:
        """
        Send action command to the robot.

        Args:
            action: Dictionary with target joint positions.

        Returns:
            The action actually sent (may be clipped for safety).
        """
        # Extract arm joint positions
        arm_action = {}
        for joint in self.ARM_JOINTS:
            key = f"{joint}.pos"
            if key in action:
                pos = action[key]
                if not self.config.use_degrees:
                    pos = math.degrees(pos)
                arm_action[joint] = pos

        # Apply safety limits if configured
        if self.config.max_relative_target is not None:
            current_positions = self.bus.get_joint_positions()
            goal_present_pos = {
                joint: (arm_action.get(joint, current_positions[joint]), current_positions[joint])
                for joint in self.ARM_JOINTS
            }
            arm_action = ensure_safe_goal_position(goal_present_pos, self.config.max_relative_target)

        # Send arm command
        self.bus.move_j(arm_action)

        # Handle gripper if enabled
        gripper_sent = self._gripper_position
        if self.config.gripper_enabled:
            gripper_key = f"{self.GRIPPER_JOINT}.pos"
            if gripper_key in action:
                gripper_target = action[gripper_key]
                self._send_gripper_command(gripper_target)
                gripper_sent = gripper_target

        # Build returned action dict
        sent_action = {f"{joint}.pos": arm_action.get(joint, 0.0) for joint in self.ARM_JOINTS}
        if not self.config.use_degrees:
            sent_action = {k: math.radians(v) for k, v in sent_action.items()}
        if self.config.gripper_enabled:
            sent_action[f"{self.GRIPPER_JOINT}.pos"] = gripper_sent

        return sent_action

    def _send_gripper_command(self, target_position: float) -> None:
        """
        Send gripper command via MIT control.

        Args:
            target_position: Target position in radians.
        """
        if self._gripper_mode is None:
            self._gripper_position = target_position
            return

        try:
            # target_position is already in radians (directly from leader)
            logger.debug(f"Follower gripper target: {target_position:.4f} rad")

            if self._gripper_mode == "fibre":
                # Send MIT control via fibre direct connection
                self.bus.control_hand_mit(
                    self.config.gripper_kp,
                    self.config.gripper_kd,
                    target_position,  # 直接使用弧度
                    0.0,  # velocity
                    0.0,  # torque feedforward
                )
            else:
                # Send MIT control via DM_CAN
                self._gripper_controller.controlMIT(
                    self._gripper_motor,
                    self.config.gripper_kp,
                    self.config.gripper_kd,
                    target_position,  # 直接使用弧度
                    0.0,  # velocity
                    0.0,  # torque feedforward
                )
            self._gripper_position = target_position

        except Exception as e:
            logger.debug(f"Failed to send gripper command: {e}")

    @check_if_not_connected
    def disconnect(self) -> None:
        """Disconnect from the robot."""
        # 1. 安全 resting 流程（在失能前）
        if self.bus.is_connected:
            try:
                self.bus.enable_torque()
                self.bus.resting()
                time.sleep(2.0)  # 等待到位
            except Exception as e:
                logger.warning(f"Failed to move to resting pose: {e}")

        # 2. Disable torque if configured
        if self.config.disable_torque_on_disconnect:
            try:
                self.bus.disable_torque()
            except Exception as e:
                logger.warning(f"Failed to disable torque: {e}")

        # Disconnect gripper
        if self._gripper_mode == "fibre":
            try:
                self.bus.disable_hand()
            except Exception as e:
                logger.warning(f"Failed to disable hand: {e}")
        elif self._gripper_mode == "dm_can" and self._gripper_controller is not None:
            try:
                self._gripper_controller.disable(self._gripper_motor)
            except Exception as e:
                logger.warning(f"Failed to disable gripper: {e}")
            self._gripper_controller = None
        self._gripper_mode = None

        # Disconnect arm
        self.bus.disconnect()

        # Disconnect cameras
        for cam in self.cameras.values():
            cam.disconnect()

        logger.info(f"{self} disconnected.")
