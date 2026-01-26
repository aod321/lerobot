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

from dataclasses import dataclass, field

from lerobot.cameras import CameraConfig

from ..config import RobotConfig


@RobotConfig.register_subclass("dummy_follower")
@dataclass
class DummyFollowerConfig(RobotConfig):
    # Serial number to connect to the Dummy arm via fibre
    serial_number: str = ""

    # Joint offset in degrees [j1, j2, j3, j4, j5, j6]
    joint_offset: list[float] = field(default_factory=lambda: [0.0, -73.0, 180.0, 0.0, 0.0, 0.0])

    # Whether gripper is enabled
    gripper_enabled: bool = True

    # Gripper connection mode: "fibre" (fibre direct connection) or "dm_can" (serial-to-CAN)
    # Default is "fibre" for DummyFollower (work arm)
    gripper_connection_mode: str = "fibre"

    # MIT control parameters (used by both modes)
    gripper_kp: float = 0.8
    gripper_kd: float = 0.05

    # DM_CAN mode parameters (only used when gripper_connection_mode="dm_can")
    gripper_serial_port: str = "/dev/ttyUSB0"
    gripper_baudrate: int = 921600
    gripper_motor_id: int = 0x37
    gripper_master_id: int = 0x47

    # Whether to use degrees for joint positions (True) or radians (False)
    use_degrees: bool = True

    # Whether to disable torque on disconnect
    disable_torque_on_disconnect: bool = True

    # Work pose [j1, j2, j3, j4, j5, j6] (kinematic angles in degrees)
    work_pose: list[float] = field(default_factory=lambda: [0.0, -30.0, 90.0, 0.0, 70.0, 0.0])

    # `max_relative_target` limits the magnitude of the relative positional target vector for safety purposes.
    max_relative_target: float | dict[str, float] | None = None

    # Camera configurations
    cameras: dict[str, CameraConfig] = field(default_factory=dict)
