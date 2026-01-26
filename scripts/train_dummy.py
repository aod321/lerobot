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
    parser.add_argument("--steps", "-s", type=int, default=3000,
                        help="训练步数 (默认: 3000)")
    parser.add_argument("--batch-size", "-b", type=int, default=8,
                        help="批次大小 (默认: 8)")
    parser.add_argument("--save-freq", type=int, default=1000,
                        help="每多少步保存一次检查点 (默认: 1000)")

    # 输出配置
    parser.add_argument("--output-dir", "-o", default="outputs/act_dummy",
                        help="输出目录 (默认: outputs/act_dummy)")

    # Hub 配置
    parser.add_argument("--push-to-hub", action="store_true",
                        help="训练完成后上传模型到 HuggingFace Hub")
    parser.add_argument("--hub-repo-id", default=None,
                        help="HuggingFace Hub 模型仓库 ID (默认: 使用数据集名称)")

    args = parser.parse_args()

    # 打印配置信息
    print("=" * 42)
    print("Dummy 机械臂策略训练")
    print("=" * 42)
    print(f"数据集: {args.dataset}")
    print(f"策略: {args.policy}")
    print(f"训练步数: {args.steps}")
    print(f"Batch Size: {args.batch_size}")
    print(f"保存频率: 每 {args.save_freq} 步")
    print(f"输出目录: {args.output_dir}")
    if args.push_to_hub:
        print(f"上传到 Hub: {args.hub_repo_id or '自动'}")
    print("=" * 42)
    print()

    # 构建命令
    cmd = [
        "lerobot-train",
        f"--policy.type={args.policy}",
        f"--dataset.repo_id={args.dataset}",
        f"--steps={args.steps}",
        f"--batch_size={args.batch_size}",
        f"--save_freq={args.save_freq}",
        f"--output_dir={args.output_dir}",
    ]

    # Hub 上传配置
    if args.push_to_hub:
        cmd.append("--push_to_hub=true")
        if args.hub_repo_id:
            cmd.append(f"--policy.repo_id={args.hub_repo_id}")

    # 执行命令
    result = subprocess.call(cmd)

    if result == 0:
        print()
        print("训练完成!")
        print(f"模型保存在: {args.output_dir}")
        print(f"查看训练日志: tensorboard --logdir={args.output_dir}")

    sys.exit(result)


if __name__ == "__main__":
    main()
