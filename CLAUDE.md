# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

### Installation
```bash
pip install -e ".[dev,test]"  # Development install with test dependencies
```

### Testing
```bash
# Run all tests (requires git-lfs for test artifacts)
git lfs install && git lfs pull
pytest -sv ./tests

# Run a specific test file
pytest -sv tests/test_specific_feature.py

# Run a single test
pytest -sv tests/test_file.py::test_function_name
```

### Code Quality
```bash
pre-commit install          # Install hooks (runs ruff, typos, bandit)
pre-commit run --all-files  # Manual check
```

### End-to-End Policy Tests
```bash
make test-end-to-end DEVICE=cpu  # Full pipeline: train + eval for act, diffusion, tdmpc, smolvla
make test-act-ete-train DEVICE=cuda  # Single policy train
make test-act-ete-eval DEVICE=cuda   # Single policy eval
```

### CLI Tools
All commands are installed as entry points:
- `lerobot-train` - Train policies
- `lerobot-eval` - Evaluate policies
- `lerobot-record` - Record datasets with robots
- `lerobot-teleoperate` - Real-time teleoperation
- `lerobot-calibrate` - Motor calibration
- `lerobot-find-cameras` - Detect cameras
- `lerobot-find-port` - Find serial ports
- `lerobot-dataset-viz` - Visualize datasets
- `lerobot-info` - Show system info

## Architecture Overview

### Module Structure (`src/lerobot/`)
- **robots/** - Robot implementations (SO100, Koch, Aloha, Reachy2, etc.)
- **teleoperators/** - Teleoperation devices (leaders for data collection)
- **policies/** - Neural network policies (ACT, Diffusion, TDMPC, VQ-BeT, Pi0, SmolVLA, GR00T, etc.)
- **cameras/** - Camera backends (OpenCV, Intel RealSense, ZMQ)
- **motors/** - Motor control (Dynamixel, Feetech servo SDKs)
- **datasets/** - LeRobotDataset loader and processing
- **processor/** - Data transformation pipelines
- **configs/** - Configuration classes (draccus-based)
- **envs/** - Simulation environment integration (Aloha, PushT, LIBERO)
- **scripts/** - CLI entry points

### Key Design Patterns

**Registry Pattern (draccus):** Configs use `@ConfigClass.register_subclass("name")` for polymorphic instantiation:
```python
@RobotConfig.register_subclass("so100")
@dataclass
class So100Config(RobotConfig):
    ...
```

**Base Classes:**
- `Robot` (`robots/robot.py`) - Abstract base for all robots with `connect()`, `get_observation()`, `send_action()`
- `Teleoperator` (`teleoperators/teleoperator.py`) - Same interface for teleoperation devices
- `PreTrainedPolicy` (`policies/pretrained.py`) - nn.Module + HubMixin for all policies
- `Camera` (`cameras/camera.py`) - Abstract camera interface

**Processor Pipelines:** Data flows through composable `ProcessorStep` chains:
- `RobotProcessorPipeline` - Robot observations/actions
- `PolicyProcessorPipeline` - Policy input/output normalization
- Steps include normalization, device movement, delta actions, image transforms

**Context Managers:** Robots, teleoperators, and cameras support `with` syntax for automatic cleanup.

### Data Types (`processor/core.py`)
```python
PolicyAction = torch.Tensor        # Policy network output
RobotAction = dict[str, Any]       # Motor commands
RobotObservation = dict[str, Any]  # Sensor readings + images
EnvAction = np.ndarray             # Gym environment actions
```

### Configuration
Configs are dataclasses using draccus with `ChoiceRegistry`:
- `PreTrainedConfig` - Base for policy configs
- `RobotConfig` - Base for robot configs
- `TeleoperatorConfig` - Base for teleoperator configs
- `EnvConfig` - Base for environment configs

### Adding New Components
1. **New Policy:** Create config in `policies/<name>/configuration_<name>.py`, model in `modeling_<name>.py`, register with `@PreTrainedConfig.register_subclass("name")`
2. **New Robot:** Create config and implementation in `robots/<name>/`, register with `@RobotConfig.register_subclass("name")`
3. **New Dataset:** Update `available_datasets_per_env` in `__init__.py`

## Dummy Robot System

### Overview
DummyFollower (robot) + DummyLeader (teleoperator) - 6-DOF arm with optional DMH3510 gripper, using fibre protocol for USB communication.

**Joint names:** j1, j2, j3, j4, j5, j6, gripper

**Serial numbers (example):**
- Follower arm: `396636713233`
- Leader arm: `3950366E3233`

### Architecture
```
DummyLeader (Teleoperator)          DummyFollower (Robot)
    │                                    │
    ├── FibreBus (arm control)           ├── FibreBus (arm control)
    │   └── fibre.find_any()             │   └── fibre.find_any()
    │                                    │
    └── Gripper (fibre/dm_can)           └── Gripper (fibre/dm_can)
        └── DMCanGripper or              └── DM_CAN or fibre direct
            fibre direct
```

### Key Configuration (`config_dummy_follower.py`, `config_dummy_leader.py`)
```python
serial_number: str          # USB serial number for fibre connection
joint_offset: list[float]   # [j1..j6] offset in degrees, default [-73, 180, 0, 0, 0, 0] for j2, j3
work_pose: list[float]      # [j1..j6] work position in degrees
gripper_enabled: bool       # Enable gripper control
gripper_connection_mode: str  # "fibre" (direct) or "dm_can" (serial-to-CAN)
use_degrees: bool           # True=degrees, False=radians for positions
```

### FibreBus API (`robots/dummy_follower/fibre_bus.py`)
```python
bus.connect()                    # Connect via fibre.find_any(serial_number=...)
bus.get_joint_positions()        # Returns {j1: pos, j2: pos, ...} in degrees
bus.move_j({j1: pos, ...})       # Send joint positions (kinematic angles)
bus.move_to_pose([j1..j6])       # Move to pose array
bus.enable_torque() / disable_torque()
bus.resting()                    # Move to safe resting position

# Gripper (fibre mode)
bus.enable_hand() / disable_hand()
bus.set_hand_zero()              # Set current position as zero
bus.get_hand_position()          # Returns radians
bus.control_hand_mit(kp, kd, pos, vel, torque)  # MIT control
```

### Recording State Machine (`lerobot_record.py`)
Special handling for `dummy_follower` robot:

```
WAITING ─────────────────────────────────────────────────────────────────┐
│ 1. Display: "请确保夹爪已复位" + "请用手扶住 Leader"                      │
│ 2. Wait for Enter (ESC to exit)                                       │
│ 3. teleop.prepare_recording_start() → disable leader torque           │
└───────────────────────────────────────────────────────────────────────┘
         │ Enter
         ▼
RECORDING ────────────────────────────────────────────────────────────────
│ record_loop(): teleop.get_action() → robot.send_action()              │
│ Space: exit_early → SAVING                                            │
│ Backspace: rerecord_episode → DISCARDING                              │
└─────────────────────────────────────────────────────────────────────────
         │
         ▼
SAVING / DISCARDING ──────────────────────────────────────────────────────
         │
         ▼
RESETTING ────────────────────────────────────────────────────────────────
│ teleop.prepare_for_next_episode(robot):                               │
│   1. Enable both arms torque                                          │
│   2. Move both to work_pose simultaneously                            │
│   3. Disable follower gripper → manual reset                          │
│   4. Enable follower gripper + set_hand_zero()                        │
│ NOTE: Does NOT disable leader torque here (done in WAITING)           │
└─────────────────────────────────────────────────────────────────────────
         │
         ▼
     WAITING (loop)

EXIT: Move both arms to work_pose → prompt user → resting() → disconnect
```

### DummyLeader Special Methods
```python
teleop.prepare_recording_start()     # Disable torque for teaching (called after Enter in WAITING)
teleop.prepare_for_next_episode(robot, events)  # Coordinated reset between episodes
teleop.send_feedback({gripper.torque: val})     # Force feedback (if enabled)
```

## Optional Dependencies
Hardware and policy-specific extras (see `pyproject.toml`):
- `pip install -e ".[dynamixel]"` - Dynamixel motors
- `pip install -e ".[feetech]"` - Feetech motors
- `pip install -e ".[intelrealsense]"` - RealSense cameras
- `pip install -e ".[smolvla]"` - SmolVLA policy
- `pip install -e ".[aloha,pusht]"` - Simulation environments
