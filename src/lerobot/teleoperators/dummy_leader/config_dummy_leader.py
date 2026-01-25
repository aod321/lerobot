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

from ..config import TeleoperatorConfig


@TeleoperatorConfig.register_subclass("dummy_leader")
@dataclass
class DummyLeaderConfig(TeleoperatorConfig):
    # Serial number to connect to the Dummy leader arm via fibre
    serial_number: str = ""

    # Joint offset in degrees [j1, j2, j3, j4, j5, j6]
    joint_offset: list[float] = field(default_factory=lambda: [0.0, -73.0, 180.0, 0.0, 0.0, 0.0])

    # Whether gripper is enabled
    gripper_enabled: bool = True

    # Gripper serial port for DM_CAN communication
    gripper_serial_port: str = "/dev/tty.usbmodem00000000050C1"

    # Gripper serial baudrate
    gripper_baudrate: int = 921600

    # Gripper motor ID (DM_CAN)
    gripper_motor_id: int = 0x37

    # Gripper master ID (DM_CAN)
    gripper_master_id: int = 0x47

    # Whether to use degrees for joint positions (True) or radians (False)
    use_degrees: bool = True

    # Force feedback settings
    force_feedback_enabled: bool = False
    force_feedback_scale: float = 0.8

    # MIT control parameters for force feedback
    feedback_kp: float = 0.3
    feedback_kd: float = 0.02
