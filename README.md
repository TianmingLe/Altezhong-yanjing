# Altezhong-yanjing

轻眼镜 + 重后端（MVP）：眼镜 + 手机 + PC + 云的多跳链路。

## Components

- `omi/` (submodule): firmware + backend
- `app/`: Flutter client
- `pc/relay/`: PC relay (WS/JSON/Base64) + resume protocol skeleton
- `docs/`: specs, plans, user guide, performance baseline

## Quickstart (MVP)

Read:
- [docs/USER_GUIDE.md](file:///workspace/docs/USER_GUIDE.md)
- [docs/PERFORMANCE_BASELINE.md](file:///workspace/docs/PERFORMANCE_BASELINE.md)

One command to start demo servers (backend + relay):

```bash
python scripts/run_demo_servers.py
```

## Development

Relay tests:

```bash
cd pc/relay
python3 -m pip install -r requirements.txt
python -m pytest tests/ -v
```

## Contributing

See [CONTRIBUTING.md](file:///workspace/CONTRIBUTING.md)

## Security

See [SECURITY.md](file:///workspace/SECURITY.md)

## License

MIT. See [LICENSE](file:///workspace/LICENSE)
