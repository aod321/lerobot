#!/usr/bin/env python3
"""Dummy 机械臂数据采集脚本"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Dummy 机械臂数据采集")

    # 机械臂配置
    parser.add_argument("--follower-serial", default="396636713233",
                        help="Follower 序列号 (默认: 396636713233)")
    parser.add_argument("--leader-serial", default="3950366E3233",
                        help="Leader 序列号 (默认: 3950366E3233)")

    # 夹爪连接模式配置
    parser.add_argument("--follower-gripper-mode", default="fibre",
                        choices=["fibre", "dm_can"],
                        help="Follower 夹爪连接模式 (默认: fibre)")
    parser.add_argument("--leader-gripper-mode", default="fibre",
                        choices=["fibre", "dm_can"],
                        help="Leader 夹爪连接模式 (默认: fibre)")

    # 夹爪串口配置 (仅 dm_can 模式使用)
    parser.add_argument("--follower-gripper-port", default="/dev/ttyUSB0",
                        help="Follower 夹爪串口，仅 dm_can 模式 (默认: /dev/ttyUSB0)")
    parser.add_argument("--leader-gripper-port", default="/dev/ttyUSB1",
                        help="Leader 夹爪串口，仅 dm_can 模式 (默认: /dev/ttyUSB1)")

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

    # 数据集配置
    parser.add_argument("--dataset", "-d", default="your_username/dummy_dataset",
                        help="数据集名称 (默认: your_username/dummy_dataset)")
    parser.add_argument("--num-episodes", "-n", type=int, default=50,
                        help="采集的 episode 数量 (默认: 50)")
    parser.add_argument("--task", "-t", default="Pick and place the cube",
                        help="任务描述 (默认: Pick and place the cube)")

    # 其他选项
    parser.add_argument("--resume", "-r", action="store_true",
                        help="继续录制已有数据集")
    parser.add_argument("--no-display", action="store_true",
                        help="不显示数据可视化")

    args = parser.parse_args()

    # 打印配置信息
    print("=" * 50)
    print("Dummy 机械臂数据采集")
    print("=" * 50)
    print(f"Follower 序列号: {args.follower_serial}")
    print(f"Follower 夹爪模式: {args.follower_gripper_mode}")
    if args.follower_gripper_mode == "dm_can":
        print(f"Follower 夹爪串口: {args.follower_gripper_port}")
    print(f"Leader 序列号: {args.leader_serial}")
    print(f"Leader 夹爪模式: {args.leader_gripper_mode}")
    if args.leader_gripper_mode == "dm_can":
        print(f"Leader 夹爪串口: {args.leader_gripper_port}")
    print(f"顶部相机索引: {args.camera_index}")
    if args.wrist_camera_index is not None:
        print(f"手部相机索引: {args.wrist_camera_index}")
    print(f"数据集: {args.dataset}")
    print(f"Episodes: {args.num_episodes}")
    print(f"任务: {args.task}")
    if args.resume:
        print("模式: 继续录制")
    print("=" * 50)
    print()
    print("按 Enter 开始每个 episode")
    print("按 Ctrl+C 停止当前 episode")
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

    # 构建命令
    cmd = [
        "lerobot-record",
        # Follower (robot) 配置
        f"--robot.type=dummy_follower",
        f"--robot.serial_number={args.follower_serial}",
        "--robot.gripper_enabled=true",
        f"--robot.gripper_connection_mode={args.follower_gripper_mode}",
        f"--robot.cameras={camera_config}",
        # Teleop (leader) 配置
        "--teleop.type=dummy_leader",
        f"--teleop.serial_number={args.leader_serial}",
        "--teleop.gripper_enabled=true",
        f"--teleop.gripper_connection_mode={args.leader_gripper_mode}",
        # 数据集配置
        f"--dataset.repo_id={args.dataset}",
        f"--dataset.num_episodes={args.num_episodes}",
        f"--dataset.single_task={args.task}",
        f"--display_data={'false' if args.no_display else 'true'}",
    ]

    # Follower 夹爪串口 (仅 dm_can 模式)
    if args.follower_gripper_mode == "dm_can":
        cmd.append(f"--robot.gripper_serial_port={args.follower_gripper_port}")

    # Leader 夹爪串口 (仅 dm_can 模式)
    if args.leader_gripper_mode == "dm_can":
        cmd.append(f"--teleop.gripper_serial_port={args.leader_gripper_port}")

    # 继续录制模式
    if args.resume:
        # 检查数据集目录是否存在
        hf_home = Path(os.getenv("HF_HOME", Path.home() / ".cache" / "huggingface"))
        hf_lerobot_home = Path(os.getenv("HF_LEROBOT_HOME", hf_home / "lerobot"))
        dataset_path = hf_lerobot_home / args.dataset

        if dataset_path.exists():
            cmd.append("--resume=true")
            print(f"检测到已有数据集: {dataset_path}")

            # Read existing episode count from meta/info.json
            import json
            info_path = dataset_path / "meta" / "info.json"
            if info_path.exists():
                with open(info_path) as f:
                    info = json.load(f)
                existing_episodes = info.get("total_episodes", 0)
                target_episodes = args.num_episodes
                remaining = max(0, target_episodes - existing_episodes)
                print(f"已采集: {existing_episodes} episodes")
                print(f"目标: {target_episodes} episodes")
                print(f"还需采集: {remaining} episodes")
                if remaining == 0:
                    print("[警告] 已达到目标数量，如需继续请增加 -n 参数")
        else:
            print(f"[警告] 数据集目录不存在: {dataset_path}")
            print("[警告] 将作为新数据集开始录制")

    # 执行命令
    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
