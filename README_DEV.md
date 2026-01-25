# LeRobot 开发环境指南

本文档介绍如何使用 uv 快速部署 LeRobot 开发环境，以及如何使用 Dummy 机械臂进行开发测试。

## 使用 uv 部署开发环境

### 1. 安装 uv

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

或使用 Homebrew (macOS):
```bash
brew install uv
```

### 2. 创建虚拟环境

```bash
cd /path/to/lerobot

# 使用 Python 3.10（项目要求 >= 3.10）
uv venv --python 3.10
```

### 3. 激活虚拟环境

```bash
source .venv/bin/activate
```

### 4. 安装开发依赖

```bash
# 以可编辑模式安装项目 + dev + test 依赖
uv pip install -e ".[dev,test]"
```

### 5. 验证安装

```bash
# 检查 lerobot 是否正确安装
python -c "import lerobot; print(lerobot.__version__)"

# 查看系统信息
lerobot-info
```

### 6. （可选）生成锁文件

```bash
# 生成 uv.lock 文件以确保依赖版本一致性
uv lock
```

---

## Dummy 机械臂使用指南

Dummy 机械臂是一个 6-DOF 机械臂，支持可选的 DMH3510 夹爪。包含两个组件：

- **DummyFollower** - 从臂（执行端）
- **DummyLeader** - 主臂（示教端/遥操作器）

### 硬件配置

| 组件 | 序列号 |
|------|--------|
| Follower 从臂 | `396636713233` |
| Leader 主臂 | `3950366E3233` |

关节名称：`j1, j2, j3, j4, j5, j6, gripper`

### 基本使用

#### 1. 连接 Follower 从臂

```python
from lerobot.robots.dummy_follower import DummyFollower, DummyFollowerConfig

# 创建配置
config = DummyFollowerConfig(
    serial_number="396636713233",
    gripper_enabled=True,
    gripper_serial_port="/dev/tty.usbmodem00000000050C1",
    use_degrees=True,
)

# 连接机械臂
robot = DummyFollower(config)
robot.connect()

# 读取观测
obs = robot.get_observation()
print(f"关节位置: {obs}")

# 发送动作
action = {
    "j1.pos": 0.0,
    "j2.pos": 0.0,
    "j3.pos": 0.0,
    "j4.pos": 0.0,
    "j5.pos": 0.0,
    "j6.pos": 0.0,
    "gripper.pos": 50.0,  # 0-100 范围
}
robot.send_action(action)

# 断开连接
robot.disconnect()
```

#### 2. 连接 Leader 主臂（遥操作）

```python
from lerobot.teleoperators.dummy_leader import DummyLeader, DummyLeaderConfig

# 创建配置
config = DummyLeaderConfig(
    serial_number="3950366E3233",
    gripper_enabled=True,
    gripper_serial_port="/dev/tty.usbmodem00000000050C1",
    use_degrees=True,
    force_feedback_enabled=False,
)

# 连接遥操作器
teleop = DummyLeader(config)
teleop.connect()

# 读取动作（用于控制从臂）
action = teleop.get_action()
print(f"主臂位置: {action}")

# 断开连接
teleop.disconnect()
```

#### 3. 主从遥操作示例

```python
import time
from lerobot.robots.dummy_follower import DummyFollower, DummyFollowerConfig
from lerobot.teleoperators.dummy_leader import DummyLeader, DummyLeaderConfig

# 配置从臂
follower_config = DummyFollowerConfig(
    serial_number="396636713233",
    gripper_enabled=True,
)

# 配置主臂
leader_config = DummyLeaderConfig(
    serial_number="3950366E3233",
    gripper_enabled=True,
)

# 连接设备
follower = DummyFollower(follower_config)
leader = DummyLeader(leader_config)

follower.connect()
leader.connect()

try:
    # 遥操作循环
    while True:
        # 从主臂读取动作
        action = leader.get_action()

        # 发送到从臂
        follower.send_action(action)

        # 控制频率
        time.sleep(0.02)  # 50Hz

except KeyboardInterrupt:
    print("停止遥操作")

finally:
    follower.disconnect()
    leader.disconnect()
```

### 使用上下文管理器

推荐使用上下文管理器自动处理连接和断开：

```python
from lerobot.robots.dummy_follower import DummyFollower, DummyFollowerConfig

config = DummyFollowerConfig(serial_number="396636713233")

with DummyFollower(config) as robot:
    obs = robot.get_observation()
    print(obs)
# 自动断开连接
```

### 配置参数说明

#### DummyFollowerConfig

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `serial_number` | str | `""` | Fibre 连接序列号 |
| `joint_offset` | list[float] | `[0, -73, 180, 0, 0, 0]` | 关节偏移（度） |
| `gripper_enabled` | bool | `True` | 是否启用夹爪 |
| `gripper_serial_port` | str | `/dev/tty.usbmodem...` | 夹爪串口 |
| `gripper_baudrate` | int | `921600` | 夹爪波特率 |
| `gripper_motor_id` | int | `0x37` | DM_CAN 电机 ID |
| `gripper_master_id` | int | `0x47` | DM_CAN 主机 ID |
| `gripper_kp` | float | `0.8` | MIT 控制 Kp |
| `gripper_kd` | float | `0.05` | MIT 控制 Kd |
| `use_degrees` | bool | `True` | 使用角度（否则弧度） |
| `disable_torque_on_disconnect` | bool | `True` | 断开时关闭力矩 |
| `max_relative_target` | float/dict/None | `None` | 安全限位 |
| `cameras` | dict | `{}` | 相机配置 |

#### DummyLeaderConfig

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `serial_number` | str | `""` | Fibre 连接序列号 |
| `joint_offset` | list[float] | `[0, -73, 180, 0, 0, 0]` | 关节偏移（度） |
| `gripper_enabled` | bool | `True` | 是否启用夹爪 |
| `gripper_serial_port` | str | `/dev/tty.usbmodem...` | 夹爪串口 |
| `use_degrees` | bool | `True` | 使用角度（否则弧度） |
| `force_feedback_enabled` | bool | `False` | 启用力反馈 |
| `force_feedback_scale` | float | `0.8` | 力反馈缩放 |
| `feedback_kp` | float | `0.3` | 力反馈 Kp |
| `feedback_kd` | float | `0.02` | 力反馈 Kd |

### 添加相机

```python
from lerobot.cameras.opencv import OpenCVCameraConfig
from lerobot.robots.dummy_follower import DummyFollower, DummyFollowerConfig

config = DummyFollowerConfig(
    serial_number="396636713233",
    cameras={
        "top": OpenCVCameraConfig(
            camera_index=0,
            width=640,
            height=480,
            fps=30,
        ),
        "wrist": OpenCVCameraConfig(
            camera_index=1,
            width=640,
            height=480,
            fps=30,
        ),
    },
)

with DummyFollower(config) as robot:
    obs = robot.get_observation()
    # obs 现在包含 "top" 和 "wrist" 图像
```

---

## 常用 uv 命令

| 命令 | 说明 |
|------|------|
| `uv pip install <pkg>` | 安装包 |
| `uv pip install -e ".[extra1,extra2]"` | 安装带可选依赖的本地项目 |
| `uv pip list` | 列出已安装的包 |
| `uv pip freeze > requirements.txt` | 导出依赖列表 |
| `uv lock` | 生成锁文件 |
| `uv sync` | 根据锁文件同步环境 |

---

## 运行测试

```bash
# 安装 git-lfs（如果尚未安装）
git lfs install
git lfs pull

# 运行快速测试
pytest tests/ -v --timeout=60 -k "not slow"

# 运行完整测试
pytest tests/ -sv
```

## 代码质量检查

```bash
# 安装 pre-commit hooks
pre-commit install

# 手动运行检查
pre-commit run --all-files
```
