# 🤖 Dummy 机械臂使用指南

## 快速开始（3 分钟）

### 1️⃣ 修改配置

在开始之前，你需要修改以下文件中的配置参数：

#### 必须修改的参数：

**`scripts/full_workflow.sh`** 或各个独立脚本中：

```bash
# 串口配置（根据你的实际设备）
FOLLOWER_GRIPPER_PORT="/dev/ttyUSB0"  # Follower 夹爪串口
LEADER_GRIPPER_PORT="/dev/ttyUSB1"    # Leader 夹爪串口

# 摄像头配置
CAMERA_INDEX=0  # 摄像头索引，通常是 0

# 数据集配置
DATASET_NAME="your_username/dummy_pick_cube"  # 改成你的用户名
TASK_DESCRIPTION="Pick and place the cube"   # 任务描述
```

### 2️⃣ 检查设备连接

```bash
# 查看串口设备
ls /dev/tty* | grep -E "(USB|ACM)"

# 查看摄像头
ls /dev/video*

# 测试硬件连接
python test_dummy_connection.py
```

### 3️⃣ 选择运行方式

#### 方式 A: 一键运行完整流程（适合首次使用）

```bash
./scripts/full_workflow.sh
```

这个脚本会依次执行：
1. 硬件连接测试
2. 数据采集（50 episodes）
3. 模型训练（3000 epochs）
4. 模型评估（10 episodes）

#### 方式 B: 分步执行（适合调试和定制）

```bash
# 步骤 1: 测试连接
python test_dummy_connection.py

# 步骤 2: 数据采集
./scripts/record_dummy.sh

# 步骤 3: 训练模型
./scripts/train_dummy.sh

# 步骤 4: 评估部署
./scripts/eval_dummy.sh
```

---

## 📋 详细步骤说明

### 步骤 1: 数据采集技巧

**采集过程**：
1. 运行 `./scripts/record_dummy.sh`
2. 按 **Enter** 开始录制一个 episode
3. 用 Leader 主臂控制 Follower 从臂完成任务
4. 任务完成后按 **Ctrl+C** 停止录制
5. 重复直到完成所有 episodes

**质量建议**：
- ✅ 动作流畅自然，避免突然停顿
- ✅ 多次尝试，只保留成功的 episodes
- ✅ 变化物体位置，增加数据多样性
- ✅ 保持一致的任务完成标准
- ❌ 避免碰撞和失败的尝试

### 步骤 2: 训练监控

训练开始后，在另一个终端运行：

```bash
# 启动 TensorBoard
tensorboard --logdir=outputs/act_dummy_pick_cube

# 在浏览器打开
# http://localhost:6006
```

**关注指标**：
- `train/loss`: 训练损失（应该下降）
- `eval/success_rate`: 评估成功率（应该上升）
- `eval/avg_reward`: 平均奖励

### 步骤 3: 评估和调试

如果评估效果不好：

1. **增加训练数据**：采集更多 episodes（建议 100+）
2. **延长训练时间**：增加 epochs 到 5000-10000
3. **调整学习率**：尝试 5e-5 或 2e-4
4. **检查数据质量**：确保采集的数据质量高
5. **尝试其他策略**：diffusion 或 tdmpc

---

## 🔧 常见问题

### Q1: 如何找到正确的串口？

```bash
# 插入设备前
ls /dev/tty* > before.txt

# 插入设备后
ls /dev/tty* > after.txt

# 查看差异
diff before.txt after.txt
```

### Q2: 权限不足怎么办？

```bash
# 添加用户到 dialout 组（串口权限）
sudo usermod -a -G dialout $USER

# 添加用户到 video 组（摄像头权限）
sudo usermod -a -G video $USER

# 重新登录生效
```

### Q3: 如何禁用夹爪？

如果不使用夹爪，修改脚本中的参数：

```bash
--robot.gripper_enabled=false
--teleop.gripper_enabled=false
```

并删除 `gripper_serial_port` 参数。

### Q4: 训练太慢怎么办？

```bash
# 减小 batch size
--training.batch_size=4

# 降低图像分辨率
"width": 320, "height": 240

# 减少训练 epochs（快速测试）
--training.num_epochs=1000
```

### Q5: 如何使用多个摄像头？

修改 cameras 配置：

```bash
--robot.cameras='{"top": {"type": "opencv", "index": 0, "width": 640, "height": 480, "fps": 30}, "wrist": {"type": "opencv", "index": 1, "width": 640, "height": 480, "fps": 30}}'
```

---

## 📊 性能基准

**推荐配置**：
- Episodes: 50-100
- Epochs: 3000-5000
- Batch Size: 8
- Learning Rate: 1e-4
- Image Size: 640x480

**预期结果**：
- 训练时间: 2-4 小时（取决于 GPU）
- 成功率: 70-90%（简单任务）
- 推理速度: 10-20 Hz

---

## 🎯 下一步

完成基础流程后，你可以：

1. **尝试更复杂的任务**：多步骤操作、精细操作
2. **优化模型性能**：调参、数据增强、集成学习
3. **添加更多传感器**：力传感器、触觉传感器
4. **实现在线学习**：边部署边学习
5. **多机器人协作**：多臂协同操作

---

## 📚 参考资料

- **完整指南**: `DUMMY_QUICKSTART.md`
- **开发文档**: `README_DEV.md`
- **配置文件**: `src/lerobot/robots/dummy_follower/config_dummy_follower.py`
- **LeRobot 官方文档**: https://github.com/huggingface/lerobot

---

## ✅ 检查清单

开始前确认：
- [ ] 硬件已正确连接
- [ ] 串口路径已确认
- [ ] 摄像头工作正常
- [ ] 虚拟环境已激活
- [ ] 依赖已安装
- [ ] 配置参数已修改

祝你使用愉快！🚀
