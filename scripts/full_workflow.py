#!/usr/bin/env python3
"""Dummy 机械臂完整工作流程脚本

此脚本展示从数据采集到部署的完整流程:
1. 数据采集 (lerobot-record + teleop)
2. 模型训练 (lerobot-train)
3. 策略部署 (lerobot-record + policy)
"""

import argparse
import subprocess
import sys


def run_command(cmd: list[str], description: str) -> bool:
    """运行命令并返回是否成功"""
    print(f"执行: {' '.join(cmd[:3])}...")
    result = subprocess.call(cmd)
    if result != 0:
        print(f"[X] {description}失败")
        return False
    print(f"[OK] {description}完成")
    return True


def wait_for_user(prompt: str):
    """等待用户确认"""
    input(f"{prompt}，按 Enter 继续...")


def main():
    parser = argparse.ArgumentParser(
        description="Dummy 机械臂完整工作流程 (数据采集 -> 训练 -> 部署)"
    )

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
    parser.add_argument("--dataset", "-d", default="your_username/dummy_pick_cube",
                        help="数据集名称 (默认: your_username/dummy_pick_cube)")
    parser.add_argument("--task", "-t", default="Pick and place the cube",
                        help="任务描述 (默认: Pick and place the cube)")
    parser.add_argument("--num-episodes", "-n", type=int, default=50,
                        help="采集的 episode 数量 (默认: 50)")

    # 训练配置
    parser.add_argument("--policy", "-p", default="act",
                        choices=["act", "diffusion", "tdmpc", "vqbet"],
                        help="策略类型 (默认: act)")
    parser.add_argument("--steps", type=int, default=3000,
                        help="训练步数 (默认: 3000)")
    parser.add_argument("--batch-size", type=int, default=8,
                        help="批次大小 (默认: 8)")
    parser.add_argument("--save-freq", type=int, default=1000,
                        help="保存频率 (默认: 1000)")

    # 输出配置
    parser.add_argument("--output-dir", "-o", default="outputs/act_dummy_pick_cube",
                        help="输出目录 (默认: outputs/act_dummy_pick_cube)")

    # 部署配置
    parser.add_argument("--deploy-episodes", type=int, default=3,
                        help="部署测试的 episode 数量 (默认: 3)")
    parser.add_argument("--episode-time", type=float, default=60,
                        help="每个 episode 的最大时间(秒) (默认: 60)")

    # 流程控制
    parser.add_argument("--skip-record", action="store_true",
                        help="跳过数据采集（使用已有数据集）")
    parser.add_argument("--skip-train", action="store_true",
                        help="跳过训练（使用已有模型）")
    parser.add_argument("--skip-deploy", action="store_true",
                        help="跳过部署测试")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="自动确认所有提示，不等待用户输入")

    args = parser.parse_args()

    # 打印配置信息
    print("=" * 50)
    print("Dummy 机械臂完整工作流程")
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

    # ============================================
    # 步骤 1: 数据采集
    # ============================================
    if not args.skip_record:
        print("步骤 1/3: 数据采集...")
        print("-" * 40)
        print(f"即将采集 {args.num_episodes} 个 episodes")
        print(f"任务: {args.task}")
        print()

        if not args.yes:
            wait_for_user("准备好后")

        cmd = [
            "lerobot-record",
            # Robot 配置
            "--robot.type=dummy_follower",
            f"--robot.serial_number={args.follower_serial}",
            "--robot.gripper_enabled=true",
            f"--robot.gripper_connection_mode={args.follower_gripper_mode}",
            f"--robot.cameras={camera_config}",
            # Teleop 配置
            "--teleop.type=dummy_leader",
            f"--teleop.serial_number={args.leader_serial}",
            "--teleop.gripper_enabled=true",
            f"--teleop.gripper_connection_mode={args.leader_gripper_mode}",
            # 数据集配置
            f"--dataset.repo_id={args.dataset}",
            f"--dataset.num_episodes={args.num_episodes}",
            f"--dataset.single_task={args.task}",
            "--display_data=true",
        ]

        # 夹爪串口 (仅 dm_can 模式)
        if args.follower_gripper_mode == "dm_can":
            cmd.append(f"--robot.gripper_serial_port={args.follower_gripper_port}")
        if args.leader_gripper_mode == "dm_can":
            cmd.append(f"--teleop.gripper_serial_port={args.leader_gripper_port}")

        if not run_command(cmd, "数据采集"):
            sys.exit(1)
        print()
    else:
        print("步骤 1/3: 跳过数据采集")
        print()

    # ============================================
    # 步骤 2: 训练模型
    # ============================================
    if not args.skip_train:
        print("步骤 2/3: 训练模型...")
        print("-" * 40)
        print(f"策略: {args.policy}")
        print(f"训练步数: {args.steps}")
        print(f"输出目录: {args.output_dir}")
        print()

        if not args.yes:
            wait_for_user("准备开始训练")

        cmd = [
            "lerobot-train",
            f"--policy.type={args.policy}",
            f"--dataset.repo_id={args.dataset}",
            f"--steps={args.steps}",
            f"--batch_size={args.batch_size}",
            f"--save_freq={args.save_freq}",
            f"--output_dir={args.output_dir}",
        ]

        if not run_command(cmd, "模型训练"):
            sys.exit(1)
        print()
    else:
        print("步骤 2/3: 跳过训练")
        print()

    # ============================================
    # 步骤 3: 部署测试
    # ============================================
    if not args.skip_deploy:
        print("步骤 3/3: 部署测试...")
        print("-" * 40)
        print(f"模型路径: {args.output_dir}")
        print(f"测试 {args.deploy_episodes} 个 episodes")
        print()

        if not args.yes:
            wait_for_user("准备开始部署测试")

        # 使用 lerobot-record 的策略模式进行部署
        deploy_dataset = f"{args.dataset}_deploy"
        cmd = [
            "lerobot-record",
            # Robot 配置
            "--robot.type=dummy_follower",
            f"--robot.serial_number={args.follower_serial}",
            "--robot.gripper_enabled=true",
            f"--robot.gripper_connection_mode={args.follower_gripper_mode}",
            f"--robot.cameras={camera_config}",
            # 策略配置 - 使用训练好的模型
            f"--policy.path={args.output_dir}",
            # 数据集配置
            f"--dataset.repo_id={deploy_dataset}",
            f"--dataset.single_task={args.task}",
            f"--dataset.num_episodes={args.deploy_episodes}",
            f"--dataset.episode_time_s={args.episode_time}",
            "--dataset.push_to_hub=false",
            "--display_data=true",
        ]

        # 夹爪串口 (仅 dm_can 模式)
        if args.follower_gripper_mode == "dm_can":
            cmd.append(f"--robot.gripper_serial_port={args.follower_gripper_port}")

        if not run_command(cmd, "部署测试"):
            sys.exit(1)
        print()
    else:
        print("步骤 3/3: 跳过部署测试")
        print()

    # ============================================
    # 完成
    # ============================================
    print("=" * 50)
    print("完整工作流程执行完毕!")
    print("=" * 50)
    print()
    print(f"数据集: {args.dataset}")
    print(f"模型: {args.output_dir}")
    print()
    print("下一步:")
    print(f"1. 查看训练日志: tensorboard --logdir={args.output_dir}")
    print("2. 分析部署测试结果")
    print("3. 根据需要调整参数重新训练")
    print()
    print("单独运行部署测试:")
    print(f"  python scripts/eval_dummy.py -p {args.output_dir}")
    print()


if __name__ == "__main__":
    main()
