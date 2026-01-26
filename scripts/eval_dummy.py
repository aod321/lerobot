#!/usr/bin/env python3
"""Dummy 机械臂策略评估脚本"""

import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Dummy 机械臂策略评估")

    # 模型配置
    parser.add_argument("--policy-path", "-p", default="outputs/act_dummy",
                        help="策略模型路径 (默认: outputs/act_dummy)")

    # 机械臂配置
    parser.add_argument("--follower-serial", default="396636713233",
                        help="Follower 序列号 (默认: 396636713233)")
    parser.add_argument("--follower-gripper-port", default="/dev/ttyUSB0",
                        help="Follower 夹爪串口 (默认: /dev/ttyUSB0)")

    # 相机配置
    parser.add_argument("--camera-index", type=int, default=0,
                        help="相机索引 (默认: 0)")
    parser.add_argument("--camera-width", type=int, default=640,
                        help="相机宽度 (默认: 640)")
    parser.add_argument("--camera-height", type=int, default=480,
                        help="相机高度 (默认: 480)")
    parser.add_argument("--camera-fps", type=int, default=30,
                        help="相机帧率 (默认: 30)")

    # 评估配置
    parser.add_argument("--num-episodes", "-n", type=int, default=10,
                        help="评估的 episode 数量 (默认: 10)")
    parser.add_argument("--max-steps", "-m", type=int, default=500,
                        help="每个 episode 的最大步数 (默认: 500)")

    args = parser.parse_args()

    # 打印配置信息
    print("=" * 42)
    print("Dummy 机械臂策略评估")
    print("=" * 42)
    print(f"模型路径: {args.policy_path}")
    print(f"Follower 序列号: {args.follower_serial}")
    print(f"评估 Episodes: {args.num_episodes}")
    print(f"最大步数: {args.max_steps}")
    print("=" * 42)
    print()

    # 构建相机配置 JSON
    camera_config = (
        f'{{"top": {{"type": "opencv", "index": {args.camera_index}, '
        f'"width": {args.camera_width}, "height": {args.camera_height}, '
        f'"fps": {args.camera_fps}}}}}'
    )

    # 构建命令
    cmd = [
        "lerobot-eval",
        f"--policy.path={args.policy_path}",
        "--robot.type=dummy_follower",
        f"--robot.serial_number={args.follower_serial}",
        "--robot.gripper_enabled=true",
        f"--robot.gripper_serial_port={args.follower_gripper_port}",
        f"--robot.cameras={camera_config}",
        f"--eval.n_episodes={args.num_episodes}",
        f"--eval.max_episode_steps={args.max_steps}",
    ]

    # 执行命令
    result = subprocess.call(cmd)

    if result == 0:
        print()
        print("评估完成!")

    sys.exit(result)


if __name__ == "__main__":
    main()
