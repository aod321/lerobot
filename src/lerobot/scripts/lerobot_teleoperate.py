# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
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
Simple script to control a robot from teleoperation or a trained policy.

Example using teleoperator:

```shell
lerobot-teleoperate \
    --robot.type=so101_follower \
    --robot.port=/dev/tty.usbmodem58760431541 \
    --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 1920, height: 1080, fps: 30}}" \
    --robot.id=black \
    --teleop.type=so101_leader \
    --teleop.port=/dev/tty.usbmodem58760431551 \
    --teleop.id=blue \
    --display_data=true
```

Example using a trained policy (local path):

```shell
lerobot-teleoperate \
    --robot.type=dummy_follower \
    --robot.serial_number=396636713233 \
    --policy.path=outputs/diffusion_test_checkpoint/checkpoints/last/pretrained_model \
    --display_data=true
```

Example using a trained policy (HuggingFace Hub):

```shell
lerobot-teleoperate \
    --robot.type=dummy_follower \
    --robot.serial_number=396636713233 \
    --policy.path=inz/diffusion_test_checkpoint_tmp \
    --display_data=true
```

Example teleoperation with bimanual so100:

```shell
lerobot-teleoperate \
  --robot.type=bi_so_follower \
  --robot.left_arm_config.port=/dev/tty.usbmodem5A460822851 \
  --robot.right_arm_config.port=/dev/tty.usbmodem5A460814411 \
  --robot.id=bimanual_follower \
  --robot.left_arm_config.cameras='{
    wrist: {"type": "opencv", "index_or_path": 1, "width": 640, "height": 480, "fps": 30},
  }' --robot.right_arm_config.cameras='{
    wrist: {"type": "opencv", "index_or_path": 2, "width": 640, "height": 480, "fps": 30},
  }' \
  --teleop.type=bi_so_leader \
  --teleop.left_arm_config.port=/dev/tty.usbmodem5A460852721 \
  --teleop.right_arm_config.port=/dev/tty.usbmodem5A460819811 \
  --teleop.id=bimanual_leader \
  --display_data=true
```

"""

import logging
import time
from dataclasses import asdict, dataclass
from pprint import pformat
from typing import Any

import rerun as rr

from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig  # noqa: F401
from lerobot.cameras.realsense.configuration_realsense import RealSenseCameraConfig  # noqa: F401
from lerobot.configs import parser
from lerobot.configs.policies import PreTrainedConfig
from lerobot.datasets.pipeline_features import aggregate_pipeline_dataset_features, create_initial_features
from lerobot.datasets.utils import build_dataset_frame, combine_feature_dicts
from lerobot.policies.factory import make_policy, make_pre_post_processors
from lerobot.policies.pretrained import PreTrainedPolicy
from lerobot.policies.utils import make_robot_action
from lerobot.processor import (
    PolicyAction,
    PolicyProcessorPipeline,
    RobotAction,
    RobotObservation,
    RobotProcessorPipeline,
    make_default_processors,
)
from lerobot.robots import (  # noqa: F401
    Robot,
    RobotConfig,
    bi_so_follower,
    dummy_follower,
    earthrover_mini_plus,
    hope_jr,
    koch_follower,
    make_robot_from_config,
    omx_follower,
    reachy2,
    so_follower,
)
from lerobot.teleoperators import (  # noqa: F401
    Teleoperator,
    TeleoperatorConfig,
    bi_so_leader,
    dummy_leader,
    gamepad,
    homunculus,
    keyboard,
    koch_leader,
    make_teleoperator_from_config,
    omx_leader,
    reachy2_teleoperator,
    so_leader,
)
from lerobot.utils.constants import OBS_STR
from lerobot.utils.control_utils import init_keyboard_listener, interruptible_input, predict_action
from lerobot.utils.import_utils import register_third_party_plugins
from lerobot.utils.robot_utils import precise_sleep
from lerobot.utils.utils import get_safe_torch_device, init_logging, move_cursor_up
from lerobot.utils.visualization_utils import init_rerun, log_rerun_data


@dataclass
class PolicyInferenceMetadata:
    """Minimal metadata for policy inference without a dataset."""
    features: dict[str, dict]
    stats: dict | None = None


@dataclass
class TeleoperateConfig:
    # TODO: pepijn, steven: if more robots require multiple teleoperators (like lekiwi) its good to make this possibele in teleop.py and record.py with List[Teleoperator]
    robot: RobotConfig
    # Whether to control the robot with a teleoperator
    teleop: TeleoperatorConfig | None = None
    # Whether to control the robot with a policy
    policy: PreTrainedConfig | None = None
    # Task description for policy inference
    task: str | None = None
    # Limit the maximum frames per second.
    fps: int = 60
    teleop_time_s: float | None = None
    # Display all cameras on screen
    display_data: bool = False
    # Display data on a remote Rerun server
    display_ip: str | None = None
    # Port of the remote Rerun server
    display_port: int | None = None
    # Whether to  display compressed images in Rerun
    display_compressed_images: bool = False

    def __post_init__(self):
        # Parse policy.path argument if provided
        policy_path = parser.get_path_arg("policy")

        if policy_path:
            cli_overrides = parser.get_cli_overrides("policy")
            self.policy = PreTrainedConfig.from_pretrained(policy_path, cli_overrides=cli_overrides)
            self.policy.pretrained_path = policy_path

        if self.teleop is None and self.policy is None:
            raise ValueError(
                "Either a teleoperator or a policy must be provided.\n"
                "Use --teleop.type=... for teleoperation, or --policy.path=... for policy control."
            )

    @classmethod
    def __get_path_fields__(cls) -> list[str]:
        """This enables the parser to load config from the policy using `--policy.path=local/dir`"""
        return ["policy"]


def teleop_loop(
    teleop: Teleoperator,
    robot: Robot,
    fps: int,
    teleop_action_processor: RobotProcessorPipeline[tuple[RobotAction, RobotObservation], RobotAction],
    robot_action_processor: RobotProcessorPipeline[tuple[RobotAction, RobotObservation], RobotAction],
    robot_observation_processor: RobotProcessorPipeline[RobotObservation, RobotObservation],
    display_data: bool = False,
    duration: float | None = None,
    display_compressed_images: bool = False,
):
    """
    This function continuously reads actions from a teleoperation device, processes them through optional
    pipelines, sends them to a robot, and optionally displays the robot's state. The loop runs at a
    specified frequency until a set duration is reached or it is manually interrupted.

    Args:
        teleop: The teleoperator device instance providing control actions.
        robot: The robot instance being controlled.
        fps: The target frequency for the control loop in frames per second.
        display_data: If True, fetches robot observations and displays them in the console and Rerun.
        display_compressed_images: If True, compresses images before sending them to Rerun for display.
        duration: The maximum duration of the teleoperation loop in seconds. If None, the loop runs indefinitely.
        teleop_action_processor: An optional pipeline to process raw actions from the teleoperator.
        robot_action_processor: An optional pipeline to process actions before they are sent to the robot.
        robot_observation_processor: An optional pipeline to process raw observations from the robot.
    """

    display_len = max(len(key) for key in robot.action_features)
    start = time.perf_counter()

    while True:
        loop_start = time.perf_counter()

        # Get robot observation
        # Not really needed for now other than for visualization
        # teleop_action_processor can take None as an observation
        # given that it is the identity processor as default
        obs = robot.get_observation()

        # Get teleop action
        raw_action = teleop.get_action()

        # Process teleop action through pipeline
        teleop_action = teleop_action_processor((raw_action, obs))

        # Process action for robot through pipeline
        robot_action_to_send = robot_action_processor((teleop_action, obs))

        # Send processed action to robot (robot_action_processor.to_output should return RobotAction)
        _ = robot.send_action(robot_action_to_send)

        if display_data:
            # Process robot observation through pipeline
            obs_transition = robot_observation_processor(obs)

            log_rerun_data(
                observation=obs_transition,
                action=teleop_action,
                compress_images=display_compressed_images,
            )

            print("\n" + "-" * (display_len + 10))
            print(f"{'NAME':<{display_len}} | {'NORM':>7}")
            # Display the final robot action that was sent
            for motor, value in robot_action_to_send.items():
                print(f"{motor:<{display_len}} | {value:>7.2f}")
            move_cursor_up(len(robot_action_to_send) + 3)

        dt_s = time.perf_counter() - loop_start
        precise_sleep(max(1 / fps - dt_s, 0.0))
        loop_s = time.perf_counter() - loop_start
        print(f"Teleop loop time: {loop_s * 1e3:.2f}ms ({1 / loop_s:.0f} Hz)")
        move_cursor_up(1)

        if duration is not None and time.perf_counter() - start >= duration:
            return


def policy_loop(
    robot: Robot,
    policy: PreTrainedPolicy,
    preprocessor: PolicyProcessorPipeline[dict[str, Any], dict[str, Any]],
    postprocessor: PolicyProcessorPipeline[PolicyAction, PolicyAction],
    fps: int,
    features: dict,
    robot_action_processor: RobotProcessorPipeline[tuple[RobotAction, RobotObservation], RobotAction],
    robot_observation_processor: RobotProcessorPipeline[RobotObservation, RobotObservation],
    display_data: bool = False,
    duration: float | None = None,
    task: str | None = None,
    display_compressed_images: bool = False,
    events: dict | None = None,
) -> str:
    """
    Control loop using a trained policy to generate robot actions.

    This function continuously gets observations from the robot, feeds them through a policy
    to predict actions, and sends those actions to the robot. The loop runs at a specified
    frequency until a set duration is reached or it is manually interrupted.

    Args:
        robot: The robot instance being controlled.
        policy: The trained policy model for action prediction.
        preprocessor: Pipeline to preprocess observations before feeding to policy.
        postprocessor: Pipeline to postprocess actions from the policy.
        fps: The target frequency for the control loop in frames per second.
        features: Dataset features dictionary for building frames.
        robot_action_processor: Pipeline to process actions before sending to robot.
        robot_observation_processor: Pipeline to process raw observations from robot.
        display_data: If True, displays observations in the console and Rerun.
        duration: Maximum duration of the loop in seconds. If None, runs indefinitely.
        task: Task description string for policy inference.
        display_compressed_images: If True, compresses images before Rerun display.
        events: Event dictionary from keyboard listener for safety stop detection.

    Returns:
        Exit reason string: "duration" if duration was reached, "safety_stop" if space key was pressed.
    """
    display_len = max(len(key) for key in robot.action_features)
    start = time.perf_counter()

    # Reset policy and processors
    policy.reset()
    preprocessor.reset()
    postprocessor.reset()

    while True:
        loop_start = time.perf_counter()

        # Check for safety stop event
        if events is not None and events.get("safety_stop"):
            events["safety_stop"] = False  # Consume the event
            return "safety_stop"

        # Get robot observation
        obs = robot.get_observation()

        # Process robot observation through pipeline
        obs_processed = robot_observation_processor(obs)

        # Build observation frame for policy
        observation_frame = build_dataset_frame(features, obs_processed, prefix=OBS_STR)

        # Get action from policy
        action_values = predict_action(
            observation=observation_frame,
            policy=policy,
            device=get_safe_torch_device(policy.config.device),
            preprocessor=preprocessor,
            postprocessor=postprocessor,
            use_amp=policy.config.use_amp,
            task=task,
            robot_type=robot.robot_type,
        )

        # Convert policy action to robot action format
        act_processed_policy: RobotAction = make_robot_action(action_values, features)

        # Process action for robot through pipeline
        robot_action_to_send = robot_action_processor((act_processed_policy, obs))

        # Send action to robot
        _ = robot.send_action(robot_action_to_send)

        if display_data:
            log_rerun_data(
                observation=obs_processed,
                action=act_processed_policy,
                compress_images=display_compressed_images,
            )

            print("\n" + "-" * (display_len + 10))
            print(f"{'NAME':<{display_len}} | {'NORM':>7}")
            for motor, value in robot_action_to_send.items():
                print(f"{motor:<{display_len}} | {value:>7.2f}")
            move_cursor_up(len(robot_action_to_send) + 3)

        dt_s = time.perf_counter() - loop_start
        precise_sleep(max(1 / fps - dt_s, 0.0))
        loop_s = time.perf_counter() - loop_start
        print(f"Policy loop time: {loop_s * 1e3:.2f}ms ({1 / loop_s:.0f} Hz)")
        move_cursor_up(1)

        if duration is not None and time.perf_counter() - start >= duration:
            return "duration"


@parser.wrap()
def teleoperate(cfg: TeleoperateConfig):
    init_logging()
    logging.info(pformat(asdict(cfg)))
    if cfg.display_data:
        init_rerun(session_name="teleoperation", ip=cfg.display_ip, port=cfg.display_port)
    display_compressed_images = (
        True
        if (cfg.display_data and cfg.display_ip is not None and cfg.display_port is not None)
        else cfg.display_compressed_images
    )

    robot = make_robot_from_config(cfg.robot)
    teleop_action_processor, robot_action_processor, robot_observation_processor = make_default_processors()

    # Determine control mode: policy or teleop
    use_policy = cfg.policy is not None
    teleop = None
    policy = None
    preprocessor = None
    postprocessor = None
    features = None

    if use_policy:
        # Policy mode: load policy and processors
        logging.info(f"Policy mode: loading policy from {cfg.policy.pretrained_path}")

        # Create features from robot (similar to record.py)
        features = combine_feature_dicts(
            aggregate_pipeline_dataset_features(
                pipeline=teleop_action_processor,
                initial_features=create_initial_features(action=robot.action_features),
                use_videos=False,
            ),
            aggregate_pipeline_dataset_features(
                pipeline=robot_observation_processor,
                initial_features=create_initial_features(observation=robot.observation_features),
                use_videos=True,
            ),
        )

        # Create minimal metadata for policy loading
        ds_meta = PolicyInferenceMetadata(features=features)

        # Load policy
        policy = make_policy(cfg.policy, ds_meta=ds_meta)

        # Load processors from pretrained path (stats are embedded)
        preprocessor, postprocessor = make_pre_post_processors(
            policy_cfg=cfg.policy,
            pretrained_path=cfg.policy.pretrained_path,
        )
    else:
        # Teleop mode
        teleop = make_teleoperator_from_config(cfg.teleop)

    robot.connect()
    if teleop is not None:
        teleop.connect()

    # For dummy_follower with teleop: move both arms to work pose simultaneously
    if robot.name == "dummy_follower" and teleop is not None:
        logging.info("Moving both arms to work pose simultaneously...")
        teleop.bus.move_to_pose(teleop.config.work_pose)  # Non-blocking
        robot.bus.move_to_pose(robot.config.work_pose)    # Non-blocking
        time.sleep(2.0)  # Wait for both to reach position

    # For dummy_follower with policy: move robot to work pose
    if robot.name == "dummy_follower" and use_policy:
        logging.info("Moving robot to work pose...")
        if hasattr(robot, "bus"):
            robot.bus.move_to_pose(robot.config.work_pose)
            time.sleep(2.0)

    # Special handling for dummy_follower with teleop: safety confirmation before teaching
    if robot.name == "dummy_follower" and teleop is not None:
        print("\n" + "=" * 50)
        print("请确保夹爪已复位到闭合状态")
        print("请用手扶住 Leader 机械臂")
        print("=" * 50)
        print("\n按 Enter 开始示教...")
        input()

        # Disable leader torque for teaching
        if hasattr(teleop, "prepare_recording_start"):
            teleop.prepare_recording_start()

    # Initialize keyboard listener and events for policy mode
    listener = None
    events = None
    if use_policy:
        listener, events = init_keyboard_listener()

    # For dummy_follower with policy: just confirm ready to start
    if robot.name == "dummy_follower" and use_policy:
        print("\n" + "=" * 50)
        print("请确保夹爪已复位到闭合状态")
        print("Policy 控制模式")
        print("按 空格键 触发安全停止")
        print("=" * 50)
        print("\n按 Enter 开始 Policy 控制...")
        input()

    try:
        if use_policy:
            # Policy control loop with safety stop handling
            while True:
                exit_reason = policy_loop(
                    robot=robot,
                    policy=policy,
                    preprocessor=preprocessor,
                    postprocessor=postprocessor,
                    fps=cfg.fps,
                    features=features,
                    robot_action_processor=robot_action_processor,
                    robot_observation_processor=robot_observation_processor,
                    display_data=cfg.display_data,
                    duration=cfg.teleop_time_s,
                    task=cfg.task,
                    display_compressed_images=display_compressed_images,
                    events=events,
                )

                if exit_reason == "safety_stop":
                    # Move robot to work pose
                    print("\n" + "=" * 50)
                    print("正在将机械臂移动到工作位置...")
                    print("=" * 50)
                    try:
                        if hasattr(robot, "bus"):
                            robot.bus.enable_torque()
                            robot.bus.move_to_pose(robot.config.work_pose)
                            time.sleep(2.0)
                    except Exception as e:
                        logging.warning(f"安全停止时移动到工作位置出错: {e}")

                    print("\n" + "=" * 50)
                    print("机械臂已返回工作位置")
                    print("按 Enter 继续 Policy 控制，按 ESC 退出")
                    print("=" * 50)

                    # Clear events before waiting for user input
                    if events is not None:
                        events["enter_pressed"] = False
                        events["esc_pressed"] = False

                    # Wait for user to choose continue or exit
                    result = interruptible_input(events=events)
                    if result == "enter":
                        # User pressed Enter, continue policy control
                        print("继续 Policy 控制...")
                        # Reset policy state for clean restart
                        policy.reset()
                        preprocessor.reset()
                        postprocessor.reset()
                        continue
                    else:
                        # User pressed ESC or other key, exit
                        print("退出 Policy 控制...")
                        break
                else:
                    # Duration reached or other exit
                    break
        else:
            teleop_loop(
                teleop=teleop,
                robot=robot,
                fps=cfg.fps,
                display_data=cfg.display_data,
                duration=cfg.teleop_time_s,
                teleop_action_processor=teleop_action_processor,
                robot_action_processor=robot_action_processor,
                robot_observation_processor=robot_observation_processor,
                display_compressed_images=display_compressed_images,
            )
    except KeyboardInterrupt:
        pass
    finally:
        # For dummy_follower with teleop: move to work pose before resting
        if robot.name == "dummy_follower" and teleop is not None:
            try:
                print("\n" + "=" * 50)
                print("正在将机械臂移动到工作位置...")
                print("=" * 50)
                if hasattr(robot, "bus"):
                    robot.bus.enable_torque()
                    robot.bus.move_to_pose(robot.config.work_pose)
                if hasattr(teleop, "bus"):
                    teleop.bus.enable_torque()
                    teleop.bus.move_to_pose(teleop.config.work_pose)

                print("机械臂即将移动到安全位置（resting pose）")
                print("请确保周围安全，然后按 Enter 继续...")
                input()
            except Exception as e:
                logging.warning(f"Failed to move arms to work pose: {e}")

        # For dummy_follower with policy: move robot to safe position
        if robot.name == "dummy_follower" and use_policy:
            try:
                print("\n" + "=" * 50)
                print("正在将机械臂移动到工作位置...")
                print("=" * 50)
                if hasattr(robot, "bus"):
                    robot.bus.enable_torque()
                    robot.bus.move_to_pose(robot.config.work_pose)

                print("机械臂即将移动到安全位置（resting pose）")
                print("请确保周围安全，然后按 Enter 继续...")
                input()
            except Exception as e:
                logging.warning(f"Failed to move arm to work pose: {e}")

        if cfg.display_data:
            rr.rerun_shutdown()
        if listener is not None:
            listener.stop()
        if teleop is not None:
            teleop.disconnect()
        robot.disconnect()


def main():
    register_third_party_plugins()
    teleoperate()


if __name__ == "__main__":
    main()
