# USER_GUIDE (MVP v0.1.0)

面向对象：拿到眼镜硬件与源码的开发者/测试人员。目标是 5-10 分钟内完成刷机、配对并跑通 MVP 演示链路。

## 1. 环境准备

### 1.1 硬件清单

- ESP32-S3 眼镜设备
- 安卓手机（用于 App）
- PC（Windows/macOS/Linux，运行 Relay 与后端）

### 1.2 软件依赖

- PlatformIO（用于固件编译/烧录）
- Flutter SDK（用于 App）
- Python 3.8+（用于后端与 Relay）

## 2. 一键编译与烧录

### 2.1 固件编译与烧录

```bash
cd omi/omiGlass/firmware && pio run -t upload
```

### 2.2 App 运行

```bash
cd omi/app && flutter run
```

## 3. 演示路径 (Demo Workflow)

### Step 1：后端启动

```bash
cd omi/backend && python -m uvicorn main:app
```

默认访问地址：
- http://127.0.0.1:8000

### Step 2：PC Relay 启动

```bash
cd pc/relay && python relay_server.py --demo
```

默认地址：
- ws://127.0.0.1:8766

也可用一键脚本同时启动后端与 Relay：

```bash
python scripts/run_demo_servers.py
```

### Step 3：App 连接设备并开启“视觉特征上传”

- 确认手机蓝牙已打开
- App 内连接眼镜设备（BLE）
- 开启“视觉特征上传”（feature stream）

### Step 4：验证 HUD 渲染与 Relay 日志

- 观察 App HUD 是否有正常渲染/状态更新
- 观察 PC Relay 控制台是否打印 session/chunk/result 等日志

## 4. Troubleshooting

### 4.1 BLE 连接失败

- 手机蓝牙未开启或权限未授予
- 设备未处于可发现状态（尝试断电重启）
- 距离过远或干扰过强（靠近设备重试）

### 4.2 子模块初始化失败

```bash
git submodule update --init --recursive
```

