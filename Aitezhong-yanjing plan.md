📑 Altezhong-yanjing（AI眼镜）MVP 行动计划方案
适用工具：Trae Solo (AI 编程助手)  
基准代码库：BasedHardware/omi (https://github.com/BasedHardware/omi)  
文档版本：v1.0.0 | 目标周期：5周 | 交付形态：可演示、可迭代、生产级代码基线


---

🎯 一、MVP 范围定义与核心目标

维度
MVP 包含范围 (V1.0)
V2.0 延后范围
硬件基础
nRF52840主控 + 单麦/预留双麦接口 + 1080P摄像头接口 + BLE 5.3 + OTA分区
骨传导物理集成 + 蜂窝/WiFi直连模组 + 360°多摄阵列
音频链路
RNNoise本地降噪(48kHz→16kHz) + BLE高吞吐流传输 + 云端Deepgram/本地Whisper备选
双麦波束成形硬件级联动 + 85dB噪声≥85%唤醒率硬达标
视觉能力
摄像头采集 → TFLite Micro特征提取(人脸/物体框) → 特征向量BLE上传
360°全景视觉LLM实时推理 + AR光波导渲染
算力调度
规则引擎(电量/网络/任务复杂度) → 本地/手机/云端自动路由
强化学习动态卸载 + 多设备协同推理图
系统安全
MCUboot签名升级 + A/B分区回滚 + BLE E2E加密基础
硬件级Secure Boot + 联邦学习隐私保护

✅ MVP核心验收标准：  
1. 噪声环境语音清晰可懂度(SNR)提升 ≥5dB  
2. BLE音频流稳定传输延迟 ≤150ms，丢包率 <1%  
3. 边缘特征提取推理耗时 ≤20ms/帧，RAM占用 <35KB  
4. OTA升级失败自动回滚成功率 100%  
5. 端到端演示链路：采集→降噪→识别→调度→云端LLM→语音反馈闭环跑通
注意：参考项目的内容链接（此模块的内容必须在开发，以及审查的时候从对应的链接获取对应的知识）
🎯 产品级开发：最优开源项目选型 + 完整开发资源包



---

📋 最优项目选型总表（6大核心模块）

功能缺口
🔥 唯一推荐项目
选择理由
许可证
集成预估工时
🎙️ 嵌入式降噪
ArmDeveloperEcosystem/rnnoise-examples-for-pico-2
✅ 专为Cortex-M优化 + CMSIS-DSP集成示例 + 2025更新 + 文档完整
BSD-3
3-5人日
👁️ 边缘视觉推理
zephyrproject-rtos/zephyr/samples/modules/tflite-micro
✅ OMI固件基于Zephyr + 官方维护 + 兼容nRF52840 + 持续更新
Apache-2.0
5-7人日
🗣️ 离线语音识别
ggml-org/whisper.cpp
🔥 社区最活跃 + 量化方案成熟 + ARM优化 + ESP32-S3验证案例
MIT
4-6人日
📡 算力调度策略
Zephyr Power Management + 自研规则引擎
✅ 原生支持 + 零额外依赖 + 生产级稳定 + 与OMI固件无缝集成
Apache-2.0
2-3人日
🔊 高吞吐音频传输
nordic-auko/nRF52-ble-audio-streaming
✅ 同源硬件(nRF52840) + 代码可直接参考 + BLE音频最佳实践
Apache-2.0
3-4人日
🔐 安全OTA升级
zephyrproject-rtos/mcuboot
✅ Zephyr官方推荐 + 签名/回滚/差分升级 + 生产环境验证
Apache-2.0
1-2人日

💡 选型原则：优先选择与OMI技术栈（Zephyr+nRF52840+ESP32-S3）同源的项目，避免"为了功能引入新框架"的架构污染。


---

📚 模块1：嵌入式降噪（RNNoise on nRF52840）

🔗 核心资源清单

资源类型
链接
用途说明
项目主页
rnnoise-examples-for-pico-2
完整示例代码+README
RNNoise算法原理
Xiph RNNoise Paper
理解网络结构+输入输出格式
CMSIS-DSP文档
ARM CMSIS-DSP Docs
⭐ 必查：FFT/滤波/矩阵函数API参考
nRF52840 DSP优化指南
Nordic DSP Library
nRF52840专用DSP函数+性能对比
定点化/量化教程
RNNoise 8-bit Quantization Guide
将浮点模型转为INT8适配MCU
实时性能测试工具
SEGGER SystemView
分析降噪模块执行时间+内存占用
音频采样配置参考
nRF52840 PDM/PCM配置
配置麦克风采样率/位深/增益

🛠️ Trae Solo 编码参考要点

// 1. 集成入口：omi/src/audio/audio_processing.c
#include "rnnoise_wrapper.h"  // 从示例项目复制
#include "nrf_pdm.h"          // nRF52840 PDM驱动

// 2. 关键配置（CMakeLists.txt）
CONFIG_AUDIO_ENHANCEMENT=y
CONFIG_CMSIS_DSP=y
CONFIG_RNNOISE_MODEL_PATH="models/rnnoise_int8.tflite"

// 3. 性能约束（务必遵守）
// - 输入：48kHz/16bit单声道PCM
// - 帧长：480样本(10ms)，重叠50%
// - RAM占用：<40KB（含模型+中间缓冲区）
// - 推理延迟：<15ms/帧（nRF52840 @64MHz）

// 4. 测试验证命令
# 生成测试音频
python scripts/generate_test_noise.py --snr 10 --output test_10dB.pcm
# 在设备端运行
nrfjprog --program build/zephyr/zephyr.hex --chiperase --reset
# 用nRF Connect抓取BLE音频流验证降噪效果

🧪 调试与验证资源

工具
链接
用途
音频分析工具
Audacity
对比降噪前后频谱/SNR
BLE抓包工具
nRF Sniffer for BLE
分析音频流传输质量
内存分析
Zephyr Memory Domains
确保降噪模块不越界
功耗测试
Nordic Power Profiler Kit
评估降噪对电池续航影响


---

📚 模块2：边缘视觉推理（Zephyr + TFLite Micro）

🔗 核心资源清单

资源类型
链接
用途说明
官方示例主页
Zephyr TFLite Micro Samples
完整可运行示例（magic_wand/hello_world）
TFLite Micro文档
TensorFlow Lite for Microcontrollers
⭐ 模型转换/量化/部署全流程
Zephyr + TFLM集成指南
Zephyr TFLM Module Docs
Kconfig/DTS配置详解
nRF52840内存优化技巧
Zephyr Memory Optimization Guide
应对64KB RAM限制的关键策略
模型量化工具链
TensorFlow Model Optimization Toolkit
将PyTorch/TF模型转为INT8 TFLite
ESP32-S3视觉参考
esp-computer-vision
摄像头驱动+图像预处理代码参考
轻量模型仓库
Edge Impulse Model Zoo
预训练的小型分类/检测模型

🛠️ Trae Solo 编码参考要点

// 1. 启用Zephyr TFLM模块（prj.conf）
CONFIG_TFLITE_MICRO=y
CONFIG_TFLITE_MICRO_MEMORY_ARENA_SIZE=32768  // 32KB推理缓冲区
CONFIG_CAMERA=y  // 如需摄像头支持

// 2. 模型部署流程
# 训练/导出（在PC端）
python convert_model.py --input model.pt --output model_int8.tflite --quantize int8
# 转换为C数组
xxd -i model_int8.tflite > model_data.h
# 在Zephyr中加载
#include "model_data.h"
TfLiteModel* model = TfLiteModelCreateFromArray(g_model, g_model_len);

// 3. 推理优化技巧
// - 使用TFLM的"arena"内存分配避免碎片
// - 预处理在图像采集时流水线执行（PDM→RGB565→resize）
// - 仅提取特征向量传手机，避免传原始图像节省带宽

// 4. 测试命令
west build -b nrf52840dk_nrf52840 samples/modules/tflite-micro/hello_world
west flash
# 通过串口查看推理结果

🧪 调试与验证资源

工具
链接
用途
模型分析工具
Netron
可视化TFLite模型结构+层参数
内存分析
Zephyr Runtime Statistics
监控推理时RAM/ROM占用
性能剖析
Zephyr Tracing
定位推理瓶颈（预处理/推理/后处理）
摄像头测试
nRF52840 DK Camera Shield
硬件验证图像采集链路


---

📚 模块3：离线语音识别（whisper.cpp）

🔗 核心资源清单

资源类型
链接
用途说明
项目主页
ggml-org/whisper.cpp
完整代码+构建脚本+示例
量化模型仓库
TheBloke/whisper-GGUF
预量化tiny/small模型（INT4/INT8）
ARM优化指南
whisper.cpp ARM NEON
启用NEON指令加速推理
ESP32-S3部署教程
whisper.cpp on ESP32
社区验证的ESP32-S3+PSRAM方案
中文模型优化
whisper.cpp Chinese Fine-tune
提升中英混合识别准确率
流式推理示例
whisper.cpp streaming mode
实现"边说边转写"的关键代码
内存优化技巧
whisper.cpp Memory Usage
不同模型大小的RAM/ROM需求

🛠️ Trae Solo 编码参考要点

// 1. 构建配置（CMakeLists.txt for ESP32-S3）
CONFIG_WHISPER_CPP=y
CONFIG_WHISPER_MODEL_TINY=y  // 优先tiny.en（英文）或tiny（多语言）
CONFIG_WHISPER_QUANTIZE_INT8=y
CONFIG_PSRAM_ENABLE=y  // ESP32-S3必需，至少8MB PSRAM

// 2. 流式推理核心逻辑（简化版）
whisper_context* ctx = whisper_init_from_file("models/ggml-tiny.en.bin");
whisper_full_params params = whisper_full_default_params(WHISPER_SAMPLING_GREEDY);
params.no_context = true;  // 节省内存
params.single_segment = false;  // 流式模式

// 音频分帧处理（每30秒）
for (int i = 0; i < audio_samples; i += 30*16000) {
    whisper_full(ctx, params, &pcm_data[i], 30*16000);
    // 提取文本片段，通过BLE发送到手机
    send_text_via_ble(whisper_get_text(ctx, -1));
}

// 3. 中英混合优化
// - 使用tiny模型（非.en版本）支持多语言
// - 在prompt中添加"Please respond in Chinese or English as appropriate"
// - 后处理：用规则引擎检测语言切换点

// 4. 性能目标（ESP32-S3 @240MHz + 8MB PSRAM）
// - tiny模型推理：~2-3x实时率（30秒音频需60-90秒推理）
// - 策略：仅关键片段触发离线识别，其余用云端

🧪 调试与验证资源

工具
链接
用途
模型测试工具
whisper.cpp main example
本地验证模型效果+参数调优
音频预处理
libsamplerate
统一采样率到16kHz（whisper要求）
中文测试集
AISHELL-1
验证中英混合识别准确率
功耗分析
ESP32 Power Measurement
评估离线识别对续航影响


---

📚 模块4：算力调度策略（Zephyr原生+规则引擎）

🔗 核心资源清单

资源类型
链接
用途说明
Zephyr电源管理文档
Power Management Service
⭐ 核心：动态频率/外设休眠API
Zephyr工作队列
Workqueue API
实现任务优先级调度
BLE连接参数优化
BLE Connection Parameters
平衡延迟/功耗/带宽
规则引擎参考
tiny-rule-engine
轻量C规则引擎（可移植到嵌入式）
任务卸载论文实现
mobinets/task-offloading
算法参考（简化为规则即可）
电量监测驱动
nRF52840 Battery Monitor
获取实时电量触发策略

🛠️ Trae Solo 编码参考要点

// 1. 调度策略配置（Kconfig）
CONFIG_POWER_MANAGEMENT=y
CONFIG_PM_DEVICE=y
CONFIG_SCHEDULING_RULE_ENGINE=y

// 2. 规则引擎核心逻辑（简化版）
typedef struct {
    uint8_t battery_level;    // 0-100
    uint8_t network_quality;  // 0=离线, 1=蓝牙, 2=WiFi, 3=蜂窝
    uint8_t task_complexity;  // 1=简单(关键词), 2=中等(分类), 3=复杂(推理)
} context_t;

typedef enum { EXEC_LOCAL, EXEC_EDGE, EXEC_CLOUD } execution_target_t;

execution_target_t schedule_task(context_t* ctx) {
    // 规则1：电量<20% → 强制云端（除非离线任务）
    if (ctx->battery_level < 20 && ctx->network_quality >= 2) {
        return EXEC_CLOUD;
    }
    // 规则2：复杂任务+网络好 → 云端
    if (ctx->task_complexity == 3 && ctx->network_quality >= 2) {
        return EXEC_CLOUD;
    }
    // 规则3：简单任务+电量充足 → 本地
    if (ctx->task_complexity == 1 && ctx->battery_level > 50) {
        return EXEC_LOCAL;
    }
    // 默认：边缘（手机）协同
    return EXEC_EDGE;
}

// 3. 与Zephyr电源管理集成
void apply_execution_target(execution_target_t target) {
    switch (target) {
        case EXEC_LOCAL:
            pm_device_action_run(DEVICE_GET(cpu), PM_DEVICE_ACTION_SUSPEND); // 降频
            break;
        case EXEC_CLOUD:
            // 唤醒所有外设，准备高速传输
            pm_device_action_run(DEVICE_GET(ble), PM_DEVICE_ACTION_RESUME);
            break;
        // ... 
    }
}

🧪 调试与验证资源

工具
链接
用途
策略仿真
Python规则引擎测试
在PC端验证调度逻辑
功耗监控
Nordic Power Profiler
实测不同策略下的电流曲线
网络模拟
BLE Link Loss Simulator
测试网络波动时的策略切换
日志分析
Zephyr Logging
记录调度决策便于复盘优化


---

📚 模块5：高吞吐音频传输（BLE 5.3优化）

🔗 核心资源清单

资源类型
链接
用途说明
项目主页
nRF52-ble-audio-streaming
完整示例+参数配置指南
BLE音频规范
Bluetooth LE Audio
理解LC3编码+广播音频架构
nRF52840 BLE优化
Nordic BLE Best Practices
⭐ 连接参数/MTU/时序优化详解
吞吐量测试工具
nRF52 BLE Throughput Demo
实测不同参数下的带宽
音频编码参考
liblc3
Google官方LC3编码器（LE Audio标准）
双麦同步方案
Nordic PDM+Timeslot
官方论坛讨论（非开源但可参考）

🛠️ Trae Solo 编码参考要点

// 1. BLE连接参数优化（关键！）
// 目标：稳定传输48kHz/16bit单声道PCM（768kbps）→ 需压缩或降采样
// 方案：降采样到16kHz/16bit + OPUS编码 → ~64kbps

// prj.conf配置
CONFIG_BT_CONN_PARAM_UPDATE=y
CONFIG_BT_L2CAP_TX_MTU=251  // 最大MTU
CONFIG_BT_ACL_RX_COUNT=8    // 增加接收缓冲区

// 2. 音频服务定义（GATT）
// 参考项目中的ble_audio_service.c，扩展支持：
// - 采样率协商特征
// - 编码格式协商特征  
// - 双麦通道标识特征

// 3. 传输优化技巧
// - 使用BLE 5.0+的2M PHY提升带宽
// - 启用连接参数更新：间隔7.5ms，延迟0，超时500ms
// - 音频分包：每包携带时间戳+序列号，接收端重排序

// 4. 双麦简易波束成形（软件方案）
// 由于nRF52840算力有限，采用"主麦+辅麦能量比"判断声源方向
// 伪代码：
float estimate_direction(int16_t* mic1, int16_t* mic2, int len) {
    float energy1 = compute_energy(mic1, len);
    float energy2 = compute_energy(mic2, len);
    return atan2(energy2 - energy1, energy1 + energy2); // -1~1表示方向
}

🧪 调试与验证资源

工具
链接
用途
协议分析
Wireshark + BLE Sniffer
抓取BLE音频包分析丢包/延迟
音频质量评估
PESQ/STOI工具
客观评估传输后语音质量
压力测试
BLE Stress Test
测试高负载下的连接稳定性
手机端调试
nRF Connect for Mobile
实时查看GATT特征+日志


---

📚 模块6：安全OTA升级（MCUboot）

🔗 核心资源清单

资源类型
链接
用途说明
项目主页
zephyrproject-rtos/mcuboot
完整代码+构建指南
Zephyr OTA文档
DFU with MCUboot
⭐ Zephyr集成步骤+配置详解
固件签名指南
MCUboot Signing
RSA/ECDSA密钥生成+签名流程
差分升级方案
MCUboot Swap Logic
理解A/B分区+回滚机制
安全最佳实践
Zephyr Security Guidelines
密钥管理+安全启动配置
生产部署工具
west sign/flash
命令行批量烧录+签名

🛠️ Trae Solo 编码参考要点

# 1. 启用MCUboot（prj.conf + Kconfig）
CONFIG_BOOTLOADER_MCUBOOT=y
CONFIG_FLASH_MAP=y
CONFIG_PM_STATIC_YAML=y  # 定义partition配置

# 2. 分区配置（boards/nrf52840dk_nrf52840.conf）
# 示例：1MB Flash划分
# - 0x00000-0x07FFF: MCUboot (32KB)
# - 0x08000-0x3FFFF: Slot0 (224KB, 当前固件)
# - 0x40000-0x7FFFF: Slot1 (224KB, 新固件)
# - 0x80000-0xFFFFF: Storage (320KB, 用户数据)

# 3. 签名流程（开发环境）
# 生成密钥（仅需一次）
imgtool keygen -k root-rsa-2048.pem -t rsa-2048
# 签名固件
imgtool sign --key root-rsa-2048.pem \
             --header-size 0x200 \
             --align 8 \
             --version 1.0.0 \
             build/zephyr/zephyr.bin \
             signed.bin

# 4. OTA升级触发逻辑（应用层）
// 通过BLE接收新固件→写入Slot1→设置pending标志→重启
// MCUboot自动验证签名+交换分区

🧪 调试与验证资源

工具
链接
用途
固件分析
imgtool
查看/验证固件镜像头信息
回滚测试
MCUboot Test Suite
自动化测试升级/回滚流程
安全审计
Zephyr Security Scanning
检查固件依赖的安全漏洞
生产烧录
SEGGER J-Flash
批量生产烧录+密钥注入


---

🚀 Trae Solo 协作：一键启动清单

📁 推荐项目克隆顺序（避免依赖冲突）

# 1. 基础环境（先装）
git clone https://github.com/zephyrproject-rtos/zephyr
cd zephyr && west init -l . && west update

# 2. 音频模块
git clone https://github.com/ArmDeveloperEcosystem/rnnoise-examples-for-pico-2 ~/omi-external/rnnoise
# → 复制 rnnoise_wrapper.c 到 omi/src/audio/

# 3. 视觉模块（已内置，只需启用）
# → 在 omi/CMakeLists.txt 添加: find_package(TFLiteMicro REQUIRED)

# 4. 语音模块
git clone --recursive https://github.com/ggml-org/whisper.cpp ~/omi-external/whisper.cpp
# → 仅复制 whisper.h + 量化模型，推理逻辑放在手机/云端

# 5. 传输模块
git clone https://github.com/nordic-auko/nRF52-ble-audio-streaming ~/omi-external/ble-audio
# → 参考 ble_audio_service.c 重写OMI的BLE服务

# 6. OTA模块（已内置，只需配置）
# → 启用 CONFIG_BOOTLOADER_MCUBOOT 并配置分区

🎯 每日开发检查点（给Trae Solo）

## Day 1-2: 音频降噪集成
- [ ] 成功编译 rnnoise-examples-for-pico-2 到 nRF52840 DK
- [ ] 实测SNR提升≥5dB（用Audacity验证）
- [ ] RAM占用<40KB（用Zephyr runtime_stats确认）

## Day 3-5: 视觉推理预留
- [ ] 启用Zephyr TFLite Micro模块
- [ ] 成功运行 hello_world 示例
- [ ] 设计图像→特征→BLE传输协议草案

## Day 6-8: 离线语音+调度
- [ ] whisper.cpp tiny模型在ESP32-S3跑通（可接受2-3x实时率）
- [ ] 实现3条核心调度规则（电量/网络/任务复杂度）
- [ ] 规则引擎单元测试覆盖率>80%

## Day 9-10: 联调+文档
- [ ] 端到端测试：噪音环境→降噪→识别→调度→反馈
- [ ] 更新 omi/docs/ 集成指南
- [ ] 编写 Trae Solo 专用 coding_conventions.md

💡 关键提醒（避免踩坑）

1. 内存管理：nRF52840仅64KB RAM，所有模块必须共享内存池，避免重复分配
2. 量化先行：任何模型部署前必须INT8量化，否则无法运行
3. 协议兼容：修改BLE服务时保持向后兼容，避免旧版App崩溃
4. 安全底线：固件签名密钥严禁提交到仓库，使用CI/CD环境变量注入
  


---

🏗️ 二、技术架构与开源集成矩阵

模块
推荐开源项目
GitHub链接
集成位置
许可证
关键约束
嵌入式降噪
RNNoise for Pico 2
https://github.com/ArmDeveloperEcosystem/rnnoise-examples-for-pico-2
omi/src/audio/
BSD-3
INT8量化, RAM≤40KB, 帧长480样本
边缘视觉推理
Zephyr TFLite Micro
https://github.com/zephyrproject-rtos/zephyr/tree/main/samples/modules/tflite-micro
omi/src/vision/
Apache-2.0
Arena分配≤32KB, 仅输出特征/Box
离线语音识别
whisper.cpp
https://github.com/ggml-org/whisper.cpp
app/backend/ (ESP32-S3备用)
MIT
tiny模型, 需PSRAM≥4MB, 2-3x实时率可接受
BLE音频传输
nRF52 BLE Audio Streaming
https://github.com/nordic-auko/nRF52-ble-audio-streaming
omi/src/ble/
Apache-2.0
MTU=251, 2M PHY, 16kHz/16bit OPUS/LC3
算力调度策略
Zephyr PM + 自研规则引擎
https://docs.zephyrproject.org/latest/services/power_management/index.html
omi/src/scheduler/
Apache-2.0
基于电量/网络/复杂度3维决策
安全OTA升级
MCUboot
https://github.com/zephyrproject-rtos/mcuboot
boards/ + prj.conf
Apache-2.0
RSA-2048签名, A/B分区, 回滚超时5s
DSP优化库
CMSIS-DSP
https://github.com/ARM-software/CMSIS-DSP
Zephyr模块依赖
Apache-2.0
nRF52840 NEON/DSP指令加速
模型量化工具
TensorFlow Model Optimization
https://www.tensorflow.org/model_optimization
PC端预处理
Apache-2.0
PTQ INT8, 精度损失<2%


---

📅 三、五阶段详细行动计划（Trae Solo 驱动）

🟢 Phase 1：基线构建与环境对齐（第1周）
目标：成功编译 omi 固件，打通 Zephyr+nRF SDK 工具链，验证基础BLE配对与音频采集。
任务
Trae Solo 执行指令
交付物
验证标准
1.1 克隆与编译
git clone https://github.com/BasedHardware/omi && cd omi && west build -b nrf52840dk_nrf52840
可烧录 zephyr.hex
串口打印 Bluetooth initialized, 手机nRF Connect可发现设备
1.2 音频采集钩子
在 omi/src/audio/ 创建 audio_capture.c，调用 nrf_pdm 驱动
PDM→PCM 16bit/48kHz 原始流
用逻辑分析仪/示波器验证PDM波形，串口输出首帧PCM
1.3 分区规划
修改 boards/nrf52840dk_nrf52840.conf 启用MCUboot分区
pm_static.yml 分区表
Flash布局: Boot(32K)/Slot0(224K)/Slot1(224K)/Storage(320K)
1.4 依赖注入
将 CMSIS-DSP 与 rnnoise-examples-for-pico-2 放入 omi/extern/
CMake FetchContent 配置
west build 无警告，CONFIG_CMSIS_DSP=y 生效

🟡 Phase 2：音频降噪与高吞吐BLE传输（第2周）
目标：实现本地RNNoise降噪，优化BLE音频流参数，达成稳定低延迟传输。
任务
Trae Solo 执行指令
交付物
验证标准
2.1 RNNoise集成
复制 rnnoise_wrapper.c 至 omi/src/audio/，添加 audio_processing.c 钩子
降噪预处理流水线
Audacity对比SNR≥+5dB，推理延迟≤15ms/帧
2.2 BLE服务扩展
参考 nRF52-ble-audio-streaming/ble_audio_service.c 重写GATT服务
ble_audio_svc.c + UUID定义
手机App可订阅特征，MTU=251，2M PHY启用
2.3 编码与降采样
集成 liblc3 或轻量OPUS，48kHz→16kHz重采样
audio_encoder.c
码率≤64kbps，BLE吞吐压力测试丢包<1%
2.4 功耗基线测试
启用 CONFIG_POWER_MANAGEMENT=y，注入空闲休眠
prj.conf 电源配置
空闲电流≤15μA，音频流传输平均≤2mA

🟠 Phase 3：边缘视觉与调度策略（第3周）
目标：跑通TFLite Micro特征提取，实现基于规则的算力调度引擎。
任务
Trae Solo 执行指令
交付物
验证标准
3.1 TFLM集成
启用 CONFIG_TFLITE_MICRO=y，加载 hello_world 示例验证
omi/src/vision/vision_stub.c
串口输出推理结果，RAM Arena≤32KB
3.2 摄像头对接
预留 camera_capture.c，输出RGB565→灰度图预处理
图像降采样流水线
帧率≥5FPS，预处理耗时≤8ms
3.3 调度规则引擎
创建 scheduler/rule_engine.c，实现3维决策树
schedule_task() 核心函数
单元测试覆盖率≥80%，决策延迟≤1ms
3.4 任务卸载协议
扩展BLE特征：TASK_OFFLOAD_REQ / TASK_RESULT_RSP
JSON/ProtoBuf轻量格式
手机端成功接收任务并返回结果

🔴 Phase 4：云端协同与离线ASR备用（第4周）
目标：打通端到端AI交互链路，集成Whisper.cpp离线备用方案。
任务
Trae Solo 执行指令
交付物
验证标准
4.1 云端推理接入
修改 omi/backend/ 调用 Deepgram/OpenAI API
cloud_inference.py
延迟≤800ms，错误重试机制生效
4.2 Whisper本地化
在 app/ 或备用ESP32-S3部署 whisper.cpp tiny模型
whisper_local.cpp
16kHz音频输入，中英混合识别WER≤15%
4.3 断点续传缓存
实现本地SQLite/Flash环形缓冲
cache_manager.c
网络断开恢复后，未上传数据100%补传
4.4 全链路联调
采集→降噪→流传输→云端识别→语音反馈闭环
演示脚本+日志
端到端延迟≤1.5s，语音可懂度达标

🔵 Phase 5：OTA安全与MVP冻结（第5周）
目标：完成固件签名升级流程，固化代码基线，输出交付文档。
任务
Trae Solo 执行指令
交付物
验证标准
5.1 MCUboot集成
启用 CONFIG_BOOTLOADER_MCUBOOT=y，配置A/B分区
overlay-mcuboot.conf
升级后自动切换Slot，失败5s内回滚
5.2 签名流水线
编写 scripts/sign_firmware.sh，集成 imgtool
自动化签名CI脚本
west sign 成功，密钥不入库
5.3 压力与边界测试
内存泄漏检测、BLE断连重连、OTA中断模拟
测试报告
无HardFault，连续运行24h稳定
5.4 MVP交付物打包
整理 README.md, ARCHITECTURE.md, TRAESOLO_GUIDE.md
Git Tag v0.1.0-mvp
代码可一键编译，文档覆盖核心模块


---

🤖 四、Trae Solo 专属协作规范与提示词库

📐 协作约束（必须写入 Trae Solo System Prompt）
你正在协助开发 Altezhong-yanjing AI眼镜 MVP。
技术栈：Zephyr RTOS + nRF52840 + BLE 5.3 + TFLite Micro + MCUboot。
严格约束：
1. nRF52840 RAM ≤64KB，ROM ≤512KB，所有模块必须共享内存池，禁止动态分配碎片。
2. 所有AI模型必须提前量化为INT8，推理延迟必须≤20ms/帧。
3. BLE音频流必须使用16kHz/16bit+LC3/OPUS编码，MTU固定251，启用2M PHY。
4. 代码必须通过 `west build -b nrf52840dk_nrf52840` 零警告编译。
5. 每次提交必须附带：内存占用统计、功耗预估、单元测试用例。
输出格式：仅提供完整可编译代码 + CMake/Kconfig配置 + 验证命令，不解释原理。

📝 核心模块提示词模板（直接复制使用）

🔹 提示词1：RNNoise集成与内存优化
## 任务：在 omi/src/audio/ 集成 RNNoise 降噪模块
**输入**：https://github.com/ArmDeveloperEcosystem/rnnoise-examples-for-pico-2
**要求**：
1. 创建 rnnoise_wrapper.c/h，实现 float32→int8 量化适配
2. 使用 CMSIS-DSP 替换 ARM intrinsic，兼容 nRF52840
3. 内存池分配：模型缓冲区 12KB，输入/输出各 2KB，中间变量 8KB
4. 添加 Kconfig 选项 CONFIG_AUDIO_DENOISE_RNNOISE=y
**输出**：完整 .c/.h 文件 + CMakeLists.txt 片段 + prj.conf 配置 + 验证命令

🔹 提示词2：TFLite Micro 特征提取流水线
## 任务：在 omi/src/vision/ 实现轻量图像特征提取
**输入**：https://github.com/zephyrproject-rtos/zephyr/tree/main/samples/modules/tflite-micro
**要求**：
1. 加载量化后的 MobileNetV2 INT8 模型 (仅特征层)
2. 输入格式：96x96 灰度图，输出：128维特征向量
3. 使用 TFLM Arena 分配，总内存≤30KB
4. 输出 C 代码 + Kconfig 配置 + 模型转换 Python 脚本
**输出**：vision_inference.c/h + CMake 配置 + test_quantize.py

🔹 提示词3：规则引擎算力调度
## 任务：实现基于电量/网络/复杂度的调度策略
**输入**：Zephyr PM 文档 + omi/src/scheduler/ 目录
**要求**：
1. 结构体 context_t 包含 battery(0-100), network(0-3), complexity(1-3)
2. 规则：电量<20%且网络≥2 → CLOUD；复杂度=3且网络≥2 → CLOUD；其余→EDGE
3. 输出函数 schedule_task(context_t*) 返回 EXEC_LOCAL/EDGE/CLOUD
4. 集成 Zephyr workqueue，决策延迟≤1ms
**输出**：rule_engine.c/h + Kconfig + 单元测试 main.c


---

🧪 五、测试验证与交付标准

测试类型
工具
验收指标
Trae Solo 验证命令
音频降噪
Audacity + PESQ
SNR提升≥5dB, MOS≥3.5
python test_snr.py --input noise_85dB.pcm --output denoised.pcm
BLE吞吐
nRF Sniffer + Wireshark
带宽≥120kbps, 丢包<1%, 延迟≤150ms
python ble_throughput_test.py --phy 2M --mtu 251
视觉推理
Netron + Zephyr Logs
内存≤30KB, 耗时≤20ms, 特征余弦相似度≥0.85
`west build -t run && cat /dev/ttyACM0
调度策略
pytest + 规则仿真
决策覆盖率100%, 误判率<2%
cd omi/src/scheduler && pytest test_rule_engine.py -v
OTA升级
imgtool + J-Flash
签名验证通过率100%, 回滚≤5s
./scripts/ota_simulate.sh --fail-on-write


---

⚠️ 六、风险控制与应急预案

风险点
影响
应对策略
触发条件
RAM溢出 (64KB限制)
HardFault/系统崩溃
启用 CONFIG_ZEPHYR_MEMORY_PROTECTION=y，静态分配所有缓冲区
west build 警告 RAM exceeds 58KB
BLE带宽不足
音频卡顿/断流
降级至12kHz/12bit + LC3编码，或启用分块重传
抓包显示 LL_DATA_CHANNEL_PACKETS_LOST > 2%
TFLite 推理超时
视觉流水线阻塞
改用轻量 HOG+SVM 方案，或仅上传原始帧由手机端推理
推理耗时 >25ms 持续3帧
OTA变砖
设备无法启动
保留 Bootloader 独立分区，强制回滚机制硬编码
Slot1 校验失败 >3 次
Whisper 量化精度损失
识别率骤降
保留云端 Deepgram 主链路，本地仅作关键词唤醒
WER > 25% 或 触发失败回退


---

📎 附录：完整开源资源索引表

类别
资源名称
链接
用途
基线项目
BasedHardware/omi
https://github.com/BasedHardware/omi
MVP固件/APP/后端基础
音频降噪
rnnoise-examples-for-pico-2
https://github.com/ArmDeveloperEcosystem/rnnoise-examples-for-pico-2
Cortex-M RNNoise 移植参考
DSP优化
CMSIS-DSP
https://github.com/ARM-software/CMSIS-DSP
nRF52840 数学/滤波加速
边缘视觉
Zephyr TFLite Micro
https://github.com/zephyrproject-rtos/zephyr/tree/main/samples/modules/tflite-micro
官方集成示例
模型量化
TF Model Optimization
https://www.tensorflow.org/model_optimization
PC端 INT8 量化工具
离线ASR
whisper.cpp
https://github.com/ggml-org/whisper.cpp
边缘/手机端备用识别
中文优化
whisper.cpp 中文讨论
https://github.com/ggml-org/whisper.cpp/discussions/890
中英混合识别调优
BLE传输
nRF52 BLE Audio Streaming
https://github.com/nordic-auko/nRF52-ble-audio-streaming
高吞吐音频服务参考
BLE参数
nRF BLE Best Practices
https://developer.nordicsemi.com/nRF-Connect-SDK/doc/latest/nrf/ug/bluetooth_best_practices.html
MTU/PHY/连接参数调优
算力调度
Zephyr Power Management
https://docs.zephyrproject.org/latest/services/power_management/index.html
动态频率/休眠控制
安全OTA
MCUboot
https://github.com/zephyrproject-rtos/mcuboot
签名升级/回滚框架
分区配置
Zephyr DFU with MCUboot
https://docs.zephyrproject.org/latest/services/dfu/mcuboot.html
分区映射/升级流程
协议测试
nRF BLE Throughput Demo
https://github.com/NordicPlayground/nrf528xx-ble-throughput-demo
带宽/延迟压测工具
功耗分析
Nordic Power Profiler
https://www.nordicsemi.com/Products/Development-hardware/power-profiler-kit-ii
电流曲线/休眠验证
音频质量
PESQ/STOI 工具
https://github.com/gchlebus/pesq
降噪效果客观评估


---

🚀 启动指令（Trae Solo 首次执行）

# 1. 初始化项目结构
git clone https://github.com/BasedHardware/omi altezhong-yanjing
cd altezhong-yanjing
west init -l . && west update

# 2. 创建开发分支
git checkout -b feature/mvp-audio-vision

# 3. 给 Trae Solo 的第一条指令
请严格遵循《Altezhong-yanjing MVP 行动计划》Phase 1 任务，
输出 omi/src/audio/audio_capture.c 基础框架与 prj.conf 音频配置，
确保编译通过且符合 nRF52840 内存约束。

📌 最后提示：本计划已严格对齐 MVP 边界与开源集成可行性。Trae Solo 在编码时，请勿引入未列出的第三方库，所有修改必须通过 west build 验证，并附带内存/功耗指标。如需调整范围或增加模块，请先同步更新本计划文档。祝开发顺利！🔧✨


