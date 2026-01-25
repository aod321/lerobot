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
DM_CAN Gripper communication wrapper for DMH3510 motor.

This module provides a thread-safe communication interface for the DMH3510 gripper
using the DM_CAN protocol with MIT control mode.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GripperState:
    """Gripper state data."""

    position: float  # 0-100 scale (100 = open, 0 = closed)
    velocity: float  # Angular velocity
    torque: float  # Motor torque
    timestamp: float  # Time of reading


class DMCanGripper:
    """
    DM_CAN gripper controller for DMH3510 motor.

    Provides thread-safe reading and control of the gripper motor
    at ~100Hz update rate.
    """

    def __init__(
        self,
        serial_port: str,
        baudrate: int = 921600,
        motor_id: int = 0x37,
        master_id: int = 0x47,
        kp: float = 0.8,
        kd: float = 0.05,
    ):
        """
        Initialize the DM_CAN gripper controller.

        Args:
            serial_port: Serial port for DM_CAN communication.
            baudrate: Serial baudrate.
            motor_id: Motor CAN ID.
            master_id: Master CAN ID.
            kp: Position gain for MIT control.
            kd: Velocity gain for MIT control.
        """
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.motor_id = motor_id
        self.master_id = master_id
        self.kp = kp
        self.kd = kd

        self._controller: Any = None
        self._motor: Any = None
        self._connected = False

        # State cache
        self._state = GripperState(
            position=50.0,
            velocity=0.0,
            torque=0.0,
            timestamp=time.time(),
        )
        self._state_lock = threading.Lock()

        # Communication thread
        self._comm_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    @property
    def is_connected(self) -> bool:
        return self._connected and self._controller is not None

    def connect(self) -> None:
        """Connect to the gripper motor."""
        if self._connected:
            logger.warning("Gripper already connected")
            return

        try:
            import serial
            from lerobot.third_party.DM_CAN import Control_Type, DM_Motor_Type, Motor, MotorControl

            # Create serial object for DM_CAN
            serial_device = serial.Serial(
                port=self.serial_port,
                baudrate=self.baudrate,
            )

            # Initialize motor control with serial object
            self._controller = MotorControl(serial_device)

            # Create motor instance
            self._motor = Motor(
                DM_Motor_Type.DMH3510,
                self.motor_id,
                self.master_id,
            )

            # Add motor to controller and enable
            self._controller.addMotor(self._motor)
            self._controller.enable(self._motor)
            self._controller.switchControlMode(self._motor, Control_Type.MIT)

            self._connected = True

            # Start communication thread
            self._stop_event.clear()
            self._comm_thread = threading.Thread(target=self._comm_loop, daemon=True)
            self._comm_thread.start()

            logger.info(f"Gripper connected on {self.serial_port}")

        except ImportError as e:
            raise ImportError(
                "DM_CAN library is required for gripper control. "
                "The library should be in lerobot.third_party.DM_CAN"
            ) from e
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"Failed to connect gripper: {e}") from e

    def disconnect(self) -> None:
        """Disconnect from the gripper motor."""
        if not self._connected:
            return

        # Stop communication thread
        self._stop_event.set()
        if self._comm_thread is not None:
            self._comm_thread.join(timeout=1.0)
            self._comm_thread = None

        # Disable motor
        try:
            if self._controller is not None and self._motor is not None:
                self._controller.disable(self._motor)
        except Exception as e:
            logger.warning(f"Error disabling gripper: {e}")

        self._controller = None
        self._motor = None
        self._connected = False
        logger.info("Gripper disconnected")

    def _comm_loop(self) -> None:
        """Communication loop running at ~100Hz."""
        while not self._stop_event.is_set():
            try:
                self._update_state()
            except Exception as e:
                logger.debug(f"Gripper comm error: {e}")

            # Sleep for ~10ms (100Hz)
            time.sleep(0.01)

    def _update_state(self) -> None:
        """Read current state from motor."""
        if not self.is_connected:
            return

        try:
            state = self._controller.read(self._motor)
            if state is not None:
                with self._state_lock:
                    # Convert from motor units to 0-100 scale
                    # Motor position range depends on mechanism
                    raw_pos = state.q  # Position in radians
                    self._state.position = max(0.0, min(100.0, (1.0 - raw_pos / 3.14) * 100.0))
                    self._state.velocity = state.dq
                    self._state.torque = state.tau
                    self._state.timestamp = time.time()
        except Exception:
            pass

    def get_state(self) -> GripperState:
        """
        Get current gripper state.

        Returns:
            Cached gripper state.
        """
        with self._state_lock:
            return GripperState(
                position=self._state.position,
                velocity=self._state.velocity,
                torque=self._state.torque,
                timestamp=self._state.timestamp,
            )

    def get_position(self) -> float:
        """Get current gripper position (0-100 scale)."""
        return self.get_state().position

    def get_torque(self) -> float:
        """Get current gripper torque."""
        return self.get_state().torque

    def control_mit(
        self,
        target_position: float,
        target_velocity: float = 0.0,
        feedforward_torque: float = 0.0,
    ) -> None:
        """
        Send MIT control command to gripper.

        Args:
            target_position: Target position (0-100 scale).
            target_velocity: Target velocity.
            feedforward_torque: Feedforward torque.
        """
        if not self.is_connected:
            return

        try:
            # Convert 0-100 scale to motor position
            target_rad = (1.0 - target_position / 100.0) * 3.14

            self._controller.controlMIT(
                self._motor,
                self.kp,
                self.kd,
                target_rad,
                target_velocity,
                feedforward_torque,
            )
        except Exception as e:
            logger.debug(f"MIT control error: {e}")

    def send_feedback_torque(self, torque: float) -> None:
        """
        Send feedback torque for force feedback.

        Args:
            torque: Torque to apply for force feedback.
        """
        if not self.is_connected:
            return

        try:
            # Use MIT control with only torque feedforward
            current_state = self.get_state()
            target_rad = (1.0 - current_state.position / 100.0) * 3.14

            self._controller.controlMIT(
                self._motor,
                0.0,  # No position control
                0.0,  # No velocity control
                target_rad,
                0.0,
                torque,
            )
        except Exception as e:
            logger.debug(f"Feedback torque error: {e}")
