# PC Relay (Phase 7 MVP)

## Quickstart

```bash
# 1. 启动 relay
cd pc/relay && python relay_server.py --demo

# 2. 发送 1 帧 feature
python demo/send_feature.py

# 3. 模拟断点续传
python demo/resume_session.py
```

## Dependencies

```bash
cd pc/relay
python3 -m pip install -r requirements.txt
```

## Notes

See: [KNOWN_LIMITATIONS.md](file:///workspace/pc/relay/KNOWN_LIMITATIONS.md)

