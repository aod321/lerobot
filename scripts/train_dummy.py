#!/usr/bin/env python3
"""Dummy 机械臂策略训练脚本"""

import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Dummy 机械臂策略训练")

    # 数据集配置
    parser.add_argument("--dataset", "-d", default="your_username/dummy_dataset",
                        help="数据集名称 (默认: your_username/dummy_dataset)")

    # 策略配置
    parser.add_argument("--policy", "-p", default="act",
                        choices=["act", "diffusion", "tdmpc", "vqbet"],
                        help="策略类型 (默认: act)")

    # 训练配置
    parser.add_argument("--num-epochs", "-n", type=int, default=3000,
                        help="训练轮数 (默认: 3000)")
    parser.add_argument("--batch-size", "-b", type=int, default=8,
                        help="批次大小 (默认: 8)")
    parser.add_argument("--learning-rate", "-lr", type=float, default=1e-4,
                        help="学习率 (默认: 1e-4)")
    parser.add_argument("--save-every", type=int, default=1000,
                        help="每多少步保存一次检查点 (默认: 1000)")

    # 输出配置
    parser.add_argument("--output-dir", "-o", default="outputs/act_dummy",
                        help="输出目录 (默认: outputs/act_dummy)")

    args = parser.parse_args()

    # 打印配置信息
    print("=" * 42)
    print("Dummy 机械臂策略训练")
    print("=" * 42)
    print(f"数据集: {args.dataset}")
    print(f"策略: {args.policy}")
    print(f"Epochs: {args.num_epochs}")
    print(f"Batch Size: {args.batch_size}")
    print(f"Learning Rate: {args.learning_rate}")
    print(f"输出目录: {args.output_dir}")
    print("=" * 42)
    print()

    # 构建命令
    cmd = [
        "lerobot-train",
        f"--policy={args.policy}",
        f"--dataset.repo_id={args.dataset}",
        f"--training.num_epochs={args.num_epochs}",
        f"--training.batch_size={args.batch_size}",
        f"--training.lr={args.learning_rate}",
        f"--training.save_checkpoint_every={args.save_every}",
        f"--output_dir={args.output_dir}",
    ]

    # 执行命令
    result = subprocess.call(cmd)

    if result == 0:
        print()
        print("训练完成!")
        print(f"查看训练日志: tensorboard --logdir={args.output_dir}")

    sys.exit(result)


if __name__ == "__main__":
    main()
