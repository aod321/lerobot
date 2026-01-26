# Dummy 机械臂快速入门指南

本指南帮助你快速使用 Dummy 机械臂进行遥操作数据采集、训练和部署。

## 📦 硬件清单

- **DummyFollower 从臂**（序列号: 396636713233）
- **DummyLeader 主臂**（序列号: 3950366E3233）
- **DMH3510 夹爪** x2（可选）
- **USB 摄像头**或 **RealSense 相机**
- **USB 数据线** x2（连接机械臂）
- **串口线** x2（连接夹爪）

---

## 🚀 快速开始

### 步骤 1: 硬件连接

1. 将 Follower 从臂通过 USB 连接到电脑
2. 将 Leader 主臂通过 USB 连接到电脑
3. 连接夹爪串口线（如果使用夹爪）
4. 连接摄像头

### 步骤 2: 检查设备

```bash
# 查看串口设备
ls /dev/tty* | grep -E "(USB|ACM|usbmodem)"

# 查看摄像头设备
ls /dev/video*
```

记录下设备路径，例如：
- Follower 夹爪: `/dev/ttyUSB0`
- Leader 夹爪: `/dev/ttyUSB1`
- 摄像头: `/dev/video0`

### 步骤 3: 测试连接

```bash
# 运行连接测试脚本
python test_dummy_connection.py
```

**注意**: 修改脚本中的串口路径为你的实际设备路径。

### 步骤 4: 数据采集

```bash
# 编辑 scripts/record_dummy.sh，修改以下参数：
# - FOLLOWER_GRIPPER_PORT: Follower 夹爪串口
# - LEADER_GRIPPER_PORT: Leader 夹爪串口
# - CAMERA_INDEX: 摄像头索引
# - DATASET_NAME: 你的数据集名称（例如: username/pick_cube）
# - TASK_DESCRIPTION: 任务描述

# 运行数据采集
./scripts/record_dummy.sh
```

**采集技巧**:
- 每次按 Enter 开始新的 episode
- 用 Leader 主臂控制 Follower 从臂完成任务
- 保持动作流畅自然
- 建议采集 50-100 个成功的 episodes

### 步骤 5: 训练模型

```bash
# 编辑 scripts/train_dummy.sh，修改：
# - DATASET_NAME: 与采集时相同的数据集名称
# - POLICY: 选择策略（act, diffusion, tdmpc, vqbet）
# - OUTPUT_DIR: 模型保存路径

# 运行训练
./scripts/train_dummy.sh
```

**训练监控**:
```bash
# 在另一个终端查看训练进度
tensorboard --logdir=outputs/act_dummy
# 然后在浏览器打开 http://localhost:6006
```

### 步骤 6: 部署评估

```bash
# 编辑 scripts/eval_dummy.sh，修改：
# - POLICY_PATH: 训练好的模型路径
# - FOLLOWER_GRIPPER_PORT: Follower 夹爪串口
# - CAMERA_INDEX: 摄像头索引

# 运行评估
./scripts/eval_dummy.sh
```

---

## ⚙️ 配置说明

### 串口配置

如果夹爪串口不是 `/dev/ttyUSB0` 或 `/dev/ttyUSB1`，需要修改：

1. **测试脚本**: `test_dummy_connection.py`
2. **采集脚本**: `scripts/record_dummy.sh`
3. **评估脚本**: `scripts/eval_dummy.sh`

### 摄像头配置

**单摄像头**:
```bash
--robot.cameras='{"top": {"type": "opencv", "index": 0, "width": 640, "height": 480, "fps": 30}}'
```

**多摄像头**:
```bash
--robot.cameras='{"top": {"type": "opencv", "index": 0, "width": 640, "height": 480, "fps": 30}, "wrist": {"type": "opencv", "index": 1, "width": 640, "height": 480, "fps": 30}}'
```

**RealSense 相机**:
```bash
--robot.cameras='{"top": {"type": "realsense", "serial_number": "123456", "width": 640, "height": 480, "fps": 30}}'
```

### 策略选择

| 策略 | 特点 | 适用场景 |
|------|------|----------|
| **act** | Action Chunking Transformer | 通用，推荐首选 |
| **diffusion** | Diffusion Policy | 复杂轨迹，高精度 |
| **tdmpc** | TD-MPC | 在线学习，快速适应 |
| **vqbet** | VQ-BeT | 多模态行为 |

---

## 🔧 故障排除

### 问题 1: 找不到机械臂

**错误**: `Failed to connect to robot`

**解决方案**:
1. 检查 USB 连接
2. 确认序列号正确（Follower: 396636713233, Leader: 3950366E3233）
3. 检查 USB 权限：
   ```bash
   sudo usermod -a -G dialout $USER
   # 重新登录生效
   ```

### 问题 2: 夹爪无响应

**错误**: `Gripper connection failed`

**解决方案**:
1. 检查串口路径是否正确
2. 检查串口权限：
   ```bash
   sudo chmod 666 /dev/ttyUSB0
   ```
3. 确认波特率设置（默认: 921600）
4. 尝试禁用夹爪：`--robot.gripper_enabled=false`

### 问题 3: 摄像头无法打开

**错误**: `Failed to open camera`

**解决方案**:
1. 检查摄像头索引：
   ```bash
   v4l2-ctl --list-devices
   ```
2. 测试摄像头：
   ```bash
   ffplay /dev/video0
   ```
3. 检查摄像头权限：
   ```bash
   sudo usermod -a -G video $USER
   ```

### 问题 4: 训练显存不足

**错误**: `CUDA out of memory`

**解决方案**:
1. 减小 batch size：`--training.batch_size=4`
2. 降低图像分辨率：`width=320, height=240`
3. 使用梯度累积：`--training.gradient_accumulation_steps=2`

### 问题 5: 机械臂动作不流畅

**解决方案**:
1. 检查控制频率（建议 50Hz）
2. 调整安全限位：
   ```python
   config = DummyFollowerConfig(
       max_relative_target=10.0,  # 增加允许的最大移动幅度
   )
   ```
3. 检查网络延迟

---

## 📊 性能优化

### 数据采集优化

1. **提高采集质量**:
   - 保持动作流畅
   - 避免突然停顿
   - 多角度完成任务
   - 增加环境变化（物体位置、光照等）

2. **提高采集效率**:
   - 使用多摄像头同时采集
   - 批量采集相似任务
   - 使用数据增强

### 训练优化

1. **加速训练**:
   ```bash
   --training.num_workers=4  # 增加数据加载线程
   --training.use_amp=true   # 使用混合精度训练
   ```

2. **提高性能**:
   - 增加训练 epochs
   - 调整学习率
   - 使用学习率调度器

### 部署优化

1. **提高推理速度**:
   - 使用 TorchScript 或 ONNX 导出模型
   - 降低图像分辨率
   - 使用模型量化

2. **提高成功率**:
   - 增加训练数据
   - 使用集成学习
   - 添加失败恢复机制

---

## 📚 进阶使用

### 自定义配置

创建自定义配置文件 `my_config.yaml`:

```yaml
robot:
  type: dummy_follower
  serial_number: "396636713233"
  gripper_enabled: true
  gripper_serial_port: "/dev/ttyUSB0"
  cameras:
    top:
      type: opencv
      index: 0
      width: 640
      height: 480
      fps: 30

teleop:
  type: dummy_leader
  serial_number: "3950366E3233"
  gripper_enabled: true
  gripper_serial_port: "/dev/ttyUSB1"

dataset:
  repo_id: "username/dataset"
  num_episodes: 50
  single_task: "Pick and place"
```

使用配置文件：
```bash
lerobot-record --config my_config.yaml
```

### Python API 使用

```python
from lerobot.robots.dummy_follower import DummyFollower, DummyFollowerConfig
from lerobot.teleoperators.dummy_leader import DummyLeader, DummyLeaderConfig
import time

# 配置
follower_config = DummyFollowerConfig(serial_number="396636713233")
leader_config = DummyLeaderConfig(serial_number="3950366E3233")

# 遥操作循环
with DummyFollower(follower_config) as follower, \
     DummyLeader(leader_config) as leader:

    for _ in range(1000):  # 运行 1000 步
        action = leader.get_action()
        follower.send_action(action)
        time.sleep(0.02)  # 50Hz
```

---

## 🔗 相关资源

- **LeRobot 文档**: https://github.com/huggingface/lerobot
- **配置文件**: `src/lerobot/robots/dummy_follower/config_dummy_follower.py`
- **示例代码**: `README_DEV.md`
- **问题反馈**: https://github.com/huggingface/lerobot/issues

---

## ✅ 检查清单

数据采集前：
- [ ] 硬件连接正常
- [ ] 设备测试通过
- [ ] 摄像头工作正常
- [ ] 工作空间准备好
- [ ] 任务目标明确

训练前：
- [ ] 数据采集完成
- [ ] 数据质量检查
- [ ] GPU 可用
- [ ] 磁盘空间充足

部署前：
- [ ] 模型训练完成
- [ ] 模型性能满意
- [ ] 硬件连接正常
- [ ] 安全措施到位
