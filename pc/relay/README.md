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

## 协议字段说明（MVP）

| 字段 | 类型 | 说明 |
|------|------|------|
| `seq_le` | uint16 LE | 帧序号，独立计数，回绕 65535→0 |
| `timestamp_ms_le` | uint32 LE | 采集时刻（与 BLE Feature 同源） |
| `payload_len_le` | uint32 LE | payload 字节数（feature-only 固定 128） |
| `missing_ranges` | [[start,end),...] | 半开区间，表示服务端缺失的字节段 |

## 错误码（MVP）

| code | 名称 | 场景 |
|------:|------|------|
| 1001 | RELAY_ERR_OFFSET_OUT_OF_RANGE | chunk 写入越界 |
| 1002 | RELAY_ERR_CRC_MISMATCH | chunk crc32 校验失败 |
| 1003 | RELAY_ERR_INVALID_OFFSET | resume offset 非法 |
| 1004 | RELAY_ERR_SESSION_NOT_FOUND | session_id 不存在 |
| 1005 | RELAY_ERR_BAD_BASE64 | chunk data base64 解码失败 |
| 1006 | RELAY_ERR_BAD_JSON | JSON 解析失败 |
| 1007 | RELAY_ERR_BAD_OP | 未知 op |
