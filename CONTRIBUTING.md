# Contributing

Thanks for your interest in contributing!

## Repository Layout

- `omi/` (submodule): firmware + backend
- `app/`: Flutter client
- `pc/relay/`: PC relay server (WS/JSON/Base64) + tests/demos
- `docs/`: specs, plans, and MVP docs

## Getting Started

```bash
git clone --recursive https://github.com/TianmingLe/Altezhong-yanjing.git
cd Altezhong-yanjing
git submodule update --init --recursive
```

## Development Workflow

- Create a branch from `main`
- Keep PRs focused (one feature/fix per PR)
- Add tests where applicable
- Update docs when behavior changes

## Running Checks

Relay tests:

```bash
cd pc/relay
python3 -m pip install -r requirements.txt
python -m pytest tests/ -v
```

Demo orchestration:

```bash
python scripts/run_demo_servers.py --exit-after-sec 2
```

## Pull Requests

- Fill out the PR template
- Link issues when relevant
- Include evidence (logs/screenshots) for user-visible changes

