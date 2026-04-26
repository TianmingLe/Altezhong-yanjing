# Phase 7 MVP 已知限制

- 无鉴权：任意客户端可连接，生产环境需 JWT/API Key
- 单客户端：多客户端连接可能状态混淆，需 `client_id` 隔离（未实现）
- 内存会话：server 重启后 session 全丢，生产级需 Redis/文件持久化
- 仅 feature-only：`frame_type=0x01` (jpeg_chunk) 仅预留，暂不实现
- 完整性校验：`sha256` 字段保留但当前不强制校验（TODO）
