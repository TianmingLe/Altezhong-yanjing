# GitHub Repo Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将仓库按 GitHub 开源项目（MIT）常见规范补齐治理文件、Issue/PR 模板与基础 CI，并强化 README 作为入口。

**Architecture:** 在不改动核心业务逻辑前提下，新增仓库级治理文件（LICENSE/SECURITY/CONTRIBUTING 等）与 `.github/` 目录；CI 仅覆盖“稳定可跑”的 Python（relay + scripts）检查，避免引入 Flutter/PlatformIO 的重依赖。

**Tech Stack:** GitHub Actions、Markdown、Python（pytest）

---

## File Map（将创建/修改的文件）

**Create**
- `/workspace/LICENSE`
- `/workspace/CHANGELOG.md`
- `/workspace/CONTRIBUTING.md`
- `/workspace/CODE_OF_CONDUCT.md`
- `/workspace/SECURITY.md`
- `/workspace/.github/PULL_REQUEST_TEMPLATE.md`
- `/workspace/.github/ISSUE_TEMPLATE/bug_report.yml`
- `/workspace/.github/ISSUE_TEMPLATE/feature_request.yml`
- `/workspace/.github/ISSUE_TEMPLATE/config.yml`
- `/workspace/.github/workflows/ci.yml`

**Modify**
- `/workspace/README.md`

---

### Task 1: Add MIT License

**Files:**
- Create: `/workspace/LICENSE`

- [ ] **Step 1: Create LICENSE**

```text
MIT License

Copyright (c) 2026 TianmingLe

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Verify**

Run: `test -f LICENSE && head -n 5 LICENSE`  
Expected: 输出 “MIT License” 与 “TianmingLe”

- [ ] **Step 3: Commit**

```bash
git add LICENSE
git commit -m "chore: add MIT LICENSE"
```

---

### Task 2: Add Security Policy

**Files:**
- Create: `/workspace/SECURITY.md`

- [ ] **Step 1: Create SECURITY.md**

```markdown
# Security Policy

## Supported Versions

We currently support security fixes for:

| Version | Supported |
|---------|-----------|
| v0.1.x  | ✅ |

## Reporting a Vulnerability

Please report security issues by emailing:

- security@tianmingle.dev (preferred)

Include:
- A clear description of the issue and impact
- Steps to reproduce
- Any relevant logs or PoC

We will acknowledge receipt within 72 hours and provide a remediation timeline after triage.
```

- [ ] **Step 2: Commit**

```bash
git add SECURITY.md
git commit -m "docs: add SECURITY policy"
```

---

### Task 3: Add Code of Conduct

**Files:**
- Create: `/workspace/CODE_OF_CONDUCT.md`

- [ ] **Step 1: Create CODE_OF_CONDUCT.md**

```markdown
# Code of Conduct

This project follows the Contributor Covenant Code of Conduct.

## Our Pledge

We pledge to make participation in our community a harassment-free experience for everyone.

## Our Standards

Examples of behavior that contributes to a positive environment include:
- Using welcoming and inclusive language
- Being respectful of differing viewpoints and experiences
- Gracefully accepting constructive criticism

Examples of unacceptable behavior include:
- Harassment, discrimination, or hateful conduct
- Publishing others’ private information
- Trolling or insulting comments

## Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be reported by contacting the maintainer:
- TianmingLe

## Attribution

This Code of Conduct is adapted from the Contributor Covenant, version 2.1.
```

- [ ] **Step 2: Commit**

```bash
git add CODE_OF_CONDUCT.md
git commit -m "docs: add code of conduct"
```

---

### Task 4: Add Contributing Guide

**Files:**
- Create: `/workspace/CONTRIBUTING.md`

- [ ] **Step 1: Create CONTRIBUTING.md**

```markdown
# Contributing

Thanks for your interest in contributing!

## Repository Layout

- `omi/` (submodule): firmware + backend (source of truth)
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

## Running Checks (recommended)

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
```

- [ ] **Step 2: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: add contributing guide"
```

---

### Task 5: Add Changelog

**Files:**
- Create: `/workspace/CHANGELOG.md`

- [ ] **Step 1: Create CHANGELOG.md**

```markdown
# Changelog

All notable changes to this project will be documented in this file.

## v0.1.0-mvp

- Phase 1-7 MVP baseline delivered (Audio/Vision/OTA/Relay)
- PC relay server (WS/JSON/Base64) with resume protocol skeleton
- Documentation: USER_GUIDE + PERFORMANCE_BASELINE
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add changelog"
```

---

### Task 6: Add GitHub Issue/PR Templates

**Files:**
- Create: `/workspace/.github/PULL_REQUEST_TEMPLATE.md`
- Create: `/workspace/.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `/workspace/.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `/workspace/.github/ISSUE_TEMPLATE/config.yml`

- [ ] **Step 1: Create PULL_REQUEST_TEMPLATE.md**

```markdown
## Summary

- What does this change do?

## Testing

- [ ] `pc/relay` pytest
- [ ] Demo scripts / manual validation

## Screenshots / Logs (if applicable)

Paste logs or attach screenshots.

## Checklist

- [ ] No secrets or keys included
- [ ] Docs updated (if behavior changed)
```

- [ ] **Step 2: Create bug_report.yml**

```yaml
name: Bug report
description: Report a bug to help us improve
labels: ["bug"]
body:
  - type: textarea
    id: what-happened
    attributes:
      label: What happened?
      description: What did you expect to happen?
      placeholder: Describe the bug
    validations:
      required: true
  - type: textarea
    id: repro
    attributes:
      label: Reproduction steps
      description: Step-by-step reproduction
      placeholder: |
        1. ...
        2. ...
        3. ...
    validations:
      required: true
  - type: textarea
    id: logs
    attributes:
      label: Logs
      description: Paste relevant logs
      render: shell
    validations:
      required: false
  - type: input
    id: version
    attributes:
      label: Version / commit
      placeholder: v0.1.0-mvp or commit hash
    validations:
      required: false
```

- [ ] **Step 3: Create feature_request.yml**

```yaml
name: Feature request
description: Propose a feature or enhancement
labels: ["enhancement"]
body:
  - type: textarea
    id: problem
    attributes:
      label: Problem statement
      description: What problem does this solve?
    validations:
      required: true
  - type: textarea
    id: proposal
    attributes:
      label: Proposed solution
      description: What should we build?
    validations:
      required: true
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives considered
    validations:
      required: false
```

- [ ] **Step 4: Create config.yml**

```yaml
blank_issues_enabled: false
contact_links:
  - name: Security issues
    url: https://github.com/TianmingLe/Altezhong-yanjing/security/policy
    about: Please report security vulnerabilities via SECURITY policy
```

- [ ] **Step 5: Commit**

```bash
git add .github
git commit -m "chore(github): add issue and PR templates"
```

---

### Task 7: Add Minimal CI (stable + fast)

**Files:**
- Create: `/workspace/.github/workflows/ci.yml`

- [ ] **Step 1: Create ci.yml**

```yaml
name: CI

on:
  push:
    branches: ["main"]
  pull_request:

jobs:
  relay-and-scripts:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          submodules: false

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Lint (py_compile)
        run: |
          python -m py_compile scripts/run_demo_servers.py
          python -m py_compile scripts/test_feature_similarity.py

      - name: Install relay deps
        run: |
          python -m pip install --upgrade pip
          python -m pip install -r pc/relay/requirements.txt

      - name: Relay tests
        run: |
          cd pc/relay
          python -m pytest tests/ -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add minimal GitHub Actions workflow"
```

---

### Task 8: Improve README as GitHub Landing Page

**Files:**
- Modify: `/workspace/README.md`

- [ ] **Step 1: Update README.md**

Replace content with:

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: expand README with OSS project info"
```

---

### Task 9: Final Push

- [ ] **Step 1: Verify repo status**

Run: `git status --porcelain`  
Expected: empty

- [ ] **Step 2: Push**

```bash
git push origin main
```

---

## Plan Self-Review

- Spec coverage: LICENSE/SECURITY/CONTRIBUTING/COC/CHANGELOG/模板/CI/README 均覆盖
- Placeholder scan: 无 TBD/TODO（除明确写在 SECURITY SLA 与文档说明范围内）
- Consistency: README 链接与路径与仓库结构一致

