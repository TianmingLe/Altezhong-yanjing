# Altezhong-yanjing

轻眼镜 + 重后端（MVP）：眼镜 + 手机 + PC + 云的多跳链路。

当前发布标签：`v0.1.0-mvp`

## Components

- `omi/` (submodule): firmware + backend
- `app/`: Flutter client
- `pc/relay/`: PC relay (WS/JSON/Base64) + resume protocol skeleton
- `docs/`: specs, plans, user guide, performance baseline

## Quickstart (MVP)

Read:
- [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- [docs/PERFORMANCE_BASELINE.md](docs/PERFORMANCE_BASELINE.md)

One command to start demo servers (backend + relay):

```bash
python scripts/run_demo_servers.py
```

## What’s Implemented (Phase 1–7)

### Firmware (ESP32‑S3, in `omi/`)

- BLE 音频链路（Phase 2）：高吞吐 BLE 数据流能力（门禁通过）
- 视觉特征链路（Phase 3）：端侧 TFLite Micro 特征提取（int8 embedding）
  - 协议：`FEATURE_CODEC_ID=33`，Feature Notify 固定 134B + Quant 6B
  - 运行时日志：推理耗时与 Arena 使用量埋点（用于硬件验证）
- 音频增强（Phase 5）：RNNoise 静态复用策略（RAM 增量门禁通过）
- OTA：包含回滚保护（5s 硬超时机制）

### Mobile App (Flutter, in `app/`)

- BLE 连接/重连与数据流接入（音频/视觉特征）
- HUD 渲染与演示闭环路径（详见 USER_GUIDE）

### Backend (FastAPI, in `omi/backend`)

- 提供语音/视觉/告警/OTA 等服务入口（与 MVP 端侧协议对齐）

### PC Relay (Phase 7, in `pc/relay/`)

- WebSocket + JSON 控制帧 + Base64 数据块
- Session 级断点续传骨架：
  - `session_init / chunk / session_resume / session_complete`
  - `missing_ranges` 半开区间 `[start,end)`
- 完整性校验：chunk 级 CRC32；`sha256` 字段保留但 MVP 不强制校验
- pytest + demo 脚本可本地跑通

## Performance Baseline (Summary)

（详见 [docs/PERFORMANCE_BASELINE.md](docs/PERFORMANCE_BASELINE.md)）

- Phase 2 BLE 音频：`.dram0.bss` 增量 `+344B`（门禁 `≤ 8192B`）
- Phase 3 视觉特征：TFLM Arena `~24KB`（门禁 `≤ 30KB`），推理耗时示例 `7ms`（门禁 `≤ 20ms`），特征相似度 `0.9998`
- PC Relay：支持断点续传恢复，Mock result 回传 `0.92`
- OTA 回滚：5s 硬超时机制已实现

## Known Limitations (MVP)

- Demo 环境一致性：后端依赖未安装时，`scripts/run_demo_servers.py` 会 fallback 到 `http.server` 以保证编排可跑
- 安全：PC Relay 无鉴权；生产需 JWT/API Key
- 多客户端：MVP 假设单客户端；多客户端需 `client_id` 隔离
- 会话持久化：Relay 仅内存 session，重启即丢；生产需 Redis/文件持久化
- 实测补齐：部分链路指标为模拟/示例值，仍需硬件串口/抓包做最终实测闭环

## Roadmap

- M1：演示可复现（开箱即用）
  - `docker compose`/`make demo` 一键拉起后端依赖 + relay + 可选 mock
  - 后端启动方式标准化（requirements/lockfile 或容器镜像）
- M2：从 mock 走向真实推理
  - Relay `result` 接入本地推理或云端推理
  - 增加端到端 tracing（session_id 贯穿）
- M3：稳定性与安全
  - Relay：多客户端隔离、sha256 强校验、鉴权、持久化 session
  - 后端：鉴权/限流/审计日志/敏感信息处理
  - Soak/压力测试：长连接、丢包、重连、低电量降级
- M4：产品化迭代
  - 任务路由策略产品化（手机/PC/云动态卸载）
  - 支持 JPEG chunk 中继（frame_type=0x01）并做带宽/延迟权衡
  - OTA 版本治理与发布流水线（Release notes / assets / 回滚演练）

## Development

Relay tests:

```bash
cd pc/relay
python3 -m pip install -r requirements.txt
python -m pytest tests/ -v
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## Security

See [SECURITY.md](SECURITY.md)

## License

MIT. See [LICENSE](LICENSE)
