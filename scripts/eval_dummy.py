#!/usr/bin/env python3
"""Dummy 机械臂策略部署/推理脚本

在真实 dummy 机械臂上运行训练好的策略。
使用 lerobot-record 的策略模式，可选择是否保存数据。
"""

import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Dummy 机械臂策略部署/推理")

    # 模型配置
    parser.add_argument("--policy-path", "-p", required=True,
                        help="策略模型路径 (本地路径或 HuggingFace repo_id)")

    # 机械臂配置
    parser.add_argument("--follower-serial", default="396636713233",
                        help="Follower 序列号 (默认: 396636713233)")

    # 夹爪配置
    parser.add_argument("--gripper-mode", default="fibre",
                        choices=["fibre", "dm_can"],
                        help="夹爪连接模式 (默认: fibre)")
    parser.add_argument("--gripper-port", default="/dev/ttyUSB0",
                        help="夹爪串口，仅 dm_can 模式 (默认: /dev/ttyUSB0)")

    # 相机配置
    parser.add_argument("--camera-index", type=int, default=0,
                        help="顶部相机索引 (默认: 0)")
    parser.add_argument("--wrist-camera-index", type=int, default=None,
                        help="手部相机索引 (不设置则禁用)")
    parser.add_argument("--camera-width", type=int, default=640,
                        help="相机宽度 (默认: 640)")
    parser.add_argument("--camera-height", type=int, default=480,
                        help="相机高度 (默认: 480)")
    parser.add_argument("--camera-fps", type=int, default=30,
                        help="相机帧率 (默认: 30)")

    # 运行配置
    parser.add_argument("--num-episodes", "-n", type=int, default=1,
                        help="运行的 episode 数量 (默认: 1)")
    parser.add_argument("--episode-time", "-t", type=float, default=60,
                        help="每个 episode 的最大时间(秒) (默认: 60)")
    parser.add_argument("--task", default="Policy evaluation",
                        help="任务描述 (默认: Policy evaluation)")

    # 数据保存配置
    parser.add_argument("--save-data", action="store_true",
                        help="保存运行数据到数据集")
    parser.add_argument("--dataset", "-d", default="your_username/policy_rollout",
                        help="保存数据的数据集名称 (默认: your_username/policy_rollout)")
    parser.add_argument("--push-to-hub", action="store_true",
                        help="上传数据集到 HuggingFace Hub")

    # 显示配置
    parser.add_argument("--no-display", action="store_true",
                        help="不显示数据可视化")

    args = parser.parse_args()

    # 打印配置信息
    print("=" * 50)
    print("Dummy 机械臂策略部署/推理")
    print("=" * 50)
    print(f"策略路径: {args.policy_path}")
    print(f"Follower 序列号: {args.follower_serial}")
    print(f"夹爪模式: {args.gripper_mode}")
    if args.gripper_mode == "dm_can":
        print(f"夹爪串口: {args.gripper_port}")
    print(f"顶部相机索引: {args.camera_index}")
    if args.wrist_camera_index is not None:
        print(f"手部相机索引: {args.wrist_camera_index}")
    print(f"运行 Episodes: {args.num_episodes}")
    print(f"每 Episode 时间: {args.episode_time}s")
    if args.save_data:
        print(f"保存数据到: {args.dataset}")
    print("=" * 50)
    print()

    # 构建相机配置 JSON
    if args.wrist_camera_index is not None:
        camera_config = (
            f'{{"top": {{"type": "opencv", "index_or_path": {args.camera_index}, '
            f'"width": {args.camera_width}, "height": {args.camera_height}, '
            f'"fps": {args.camera_fps}}}, '
            f'"wrist": {{"type": "opencv", "index_or_path": {args.wrist_camera_index}, '
            f'"width": {args.camera_width}, "height": {args.camera_height}, '
            f'"fps": {args.camera_fps}}}}}'
        )
    else:
        camera_config = (
            f'{{"top": {{"type": "opencv", "index_or_path": {args.camera_index}, '
            f'"width": {args.camera_width}, "height": {args.camera_height}, '
            f'"fps": {args.camera_fps}}}}}'
        )

    # 构建命令 - 使用 lerobot-record 的策略模式
    cmd = [
        "lerobot-record",
        # Robot 配置
        "--robot.type=dummy_follower",
        f"--robot.serial_number={args.follower_serial}",
        "--robot.gripper_enabled=true",
        f"--robot.gripper_connection_mode={args.gripper_mode}",
        f"--robot.cameras={camera_config}",
        # 策略配置
        f"--policy.path={args.policy_path}",
        # 数据集配置
        f"--dataset.repo_id={args.dataset}",
        f"--dataset.single_task={args.task}",
        f"--dataset.num_episodes={args.num_episodes}",
        f"--dataset.episode_time_s={args.episode_time}",
        # 显示配置
        f"--display_data={'false' if args.no_display else 'true'}",
    ]

    # 夹爪串口 (仅 dm_can 模式)
    if args.gripper_mode == "dm_can":
        cmd.append(f"--robot.gripper_serial_port={args.gripper_port}")

    # Hub 上传配置
    if not args.push_to_hub:
        cmd.append("--dataset.push_to_hub=false")

    # 执行命令
    print("正在启动策略推理...")
    print(f"命令: {' '.join(cmd[:5])}...")
    print()

    result = subprocess.call(cmd)

    if result == 0:
        print()
        print("=" * 50)
        print("策略推理完成!")
        if args.save_data:
            print(f"数据已保存到: {args.dataset}")
        print("=" * 50)

    sys.exit(result)


if __name__ == "__main__":
    main()
