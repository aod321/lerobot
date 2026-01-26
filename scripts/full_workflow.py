#!/usr/bin/env python3
"""Dummy 机械臂完整工作流程脚本

此脚本展示从数据采集到部署的完整流程
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
        description="Dummy 机械臂完整工作流程 (数据采集 -> 训练 -> 评估)"
    )

    # 机械臂配置
    parser.add_argument("--follower-serial", default="396636713233",
                        help="Follower 序列号 (默认: 396636713233)")
    parser.add_argument("--leader-serial", default="3950366E3233",
                        help="Leader 序列号 (默认: 3950366E3233)")
    parser.add_argument("--follower-gripper-port", default="/dev/ttyUSB0",
                        help="Follower 夹爪串口 (默认: /dev/ttyUSB0)")
    parser.add_argument("--leader-gripper-port", default="/dev/ttyUSB1",
                        help="Leader 夹爪串口 (默认: /dev/ttyUSB1)")

    # 相机配置
    parser.add_argument("--camera-index", type=int, default=0,
                        help="相机索引 (默认: 0)")

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
    parser.add_argument("--num-epochs", type=int, default=3000,
                        help="训练轮数 (默认: 3000)")
    parser.add_argument("--batch-size", type=int, default=8,
                        help="批次大小 (默认: 8)")
    parser.add_argument("--learning-rate", type=float, default=1e-4,
                        help="学习率 (默认: 1e-4)")

    # 输出配置
    parser.add_argument("--output-dir", "-o", default="outputs/act_dummy_pick_cube",
                        help="输出目录 (默认: outputs/act_dummy_pick_cube)")

    # 评估配置
    parser.add_argument("--eval-episodes", type=int, default=10,
                        help="评估的 episode 数量 (默认: 10)")
    parser.add_argument("--max-steps", type=int, default=500,
                        help="每个 episode 的最大步数 (默认: 500)")

    # 流程控制
    parser.add_argument("--skip-test", action="store_true",
                        help="跳过硬件连接测试")
    parser.add_argument("--skip-record", action="store_true",
                        help="跳过数据采集（使用已有数据集）")
    parser.add_argument("--skip-train", action="store_true",
                        help="跳过训练（使用已有模型）")
    parser.add_argument("--skip-eval", action="store_true",
                        help="跳过评估")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="自动确认所有提示，不等待用户输入")

    args = parser.parse_args()

    # 打印配置信息
    print("=" * 42)
    print("Dummy 机械臂完整工作流程")
    print("=" * 42)
    print()

    # 构建相机配置 JSON
    camera_config = (
        f'{{"top": {{"type": "opencv", "index": {args.camera_index}, '
        f'"width": 640, "height": 480, "fps": 30}}}}'
    )

    # ============================================
    # 步骤 1: 测试硬件连接
    # ============================================
    if not args.skip_test:
        print("步骤 1/4: 测试硬件连接...")
        print("-" * 40)

        if not args.yes:
            wait_for_user("请确保所有硬件已连接")

        result = subprocess.call(["python", "test_dummy_connection.py"])
        if result != 0:
            print("[X] 硬件连接测试失败，请检查设备连接")
            sys.exit(1)

        print("[OK] 硬件连接测试通过")
        print()
    else:
        print("步骤 1/4: 跳过硬件连接测试")
        print()

    # ============================================
    # 步骤 2: 数据采集
    # ============================================
    if not args.skip_record:
        print("步骤 2/4: 数据采集...")
        print("-" * 40)
        print(f"即将采集 {args.num_episodes} 个 episodes")
        print(f"任务: {args.task}")
        print()

        if not args.yes:
            wait_for_user("准备好后")

        cmd = [
            "lerobot-record",
            "--robot.type=dummy_follower",
            f"--robot.serial_number={args.follower_serial}",
            "--robot.gripper_enabled=true",
            f"--robot.gripper_serial_port={args.follower_gripper_port}",
            f"--robot.cameras={camera_config}",
            "--teleop.type=dummy_leader",
            f"--teleop.serial_number={args.leader_serial}",
            "--teleop.gripper_enabled=true",
            f"--teleop.gripper_serial_port={args.leader_gripper_port}",
            f"--dataset.repo_id={args.dataset}",
            f"--dataset.num_episodes={args.num_episodes}",
            f"--dataset.single_task={args.task}",
            "--display_data=true",
        ]

        if not run_command(cmd, "数据采集"):
            sys.exit(1)
        print()
    else:
        print("步骤 2/4: 跳过数据采集")
        print()

    # ============================================
    # 步骤 3: 训练模型
    # ============================================
    if not args.skip_train:
        print("步骤 3/4: 训练模型...")
        print("-" * 40)
        print(f"策略: {args.policy}")
        print(f"Epochs: {args.num_epochs}")
        print(f"输出目录: {args.output_dir}")
        print()

        if not args.yes:
            wait_for_user("准备开始训练")

        cmd = [
            "lerobot-train",
            f"--policy={args.policy}",
            f"--dataset.repo_id={args.dataset}",
            f"--training.num_epochs={args.num_epochs}",
            f"--training.batch_size={args.batch_size}",
            f"--training.lr={args.learning_rate}",
            "--training.save_checkpoint_every=1000",
            f"--output_dir={args.output_dir}",
        ]

        if not run_command(cmd, "模型训练"):
            sys.exit(1)
        print()
    else:
        print("步骤 3/4: 跳过训练")
        print()

    # ============================================
    # 步骤 4: 评估部署
    # ============================================
    if not args.skip_eval:
        print("步骤 4/4: 评估部署...")
        print("-" * 40)
        print(f"模型路径: {args.output_dir}")
        print(f"评估 {args.eval_episodes} 个 episodes")
        print()

        if not args.yes:
            wait_for_user("准备开始评估")

        cmd = [
            "lerobot-eval",
            f"--policy.path={args.output_dir}",
            "--robot.type=dummy_follower",
            f"--robot.serial_number={args.follower_serial}",
            "--robot.gripper_enabled=true",
            f"--robot.gripper_serial_port={args.follower_gripper_port}",
            f"--robot.cameras={camera_config}",
            f"--eval.n_episodes={args.eval_episodes}",
            f"--eval.max_episode_steps={args.max_steps}",
        ]

        if not run_command(cmd, "评估"):
            sys.exit(1)
        print()
    else:
        print("步骤 4/4: 跳过评估")
        print()

    # ============================================
    # 完成
    # ============================================
    print("=" * 42)
    print("完整工作流程执行完毕!")
    print("=" * 42)
    print()
    print(f"数据集: {args.dataset}")
    print(f"模型: {args.output_dir}")
    print()
    print("下一步:")
    print(f"1. 查看训练日志: tensorboard --logdir={args.output_dir}")
    print("2. 分析评估结果")
    print("3. 根据需要调整参数重新训练")
    print()


if __name__ == "__main__":
    main()
