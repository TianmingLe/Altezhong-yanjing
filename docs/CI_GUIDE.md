# CI Guide

本仓库的 Product CI 门禁包含三阶段：

1. `static-check`：Python py_compile + relay pytest + clang-tidy（关键 C++ 文件）
2. `e2e-demo`：`make demo-test` 跑通 docker compose demo profile
3. `image-scan`：Trivy filesystem 扫描 + demo 镜像扫描（HIGH/CRITICAL 阻断）

## 本地复现

快速模式（默认）：

```bash
make ci-local
```

全量模式（包含 demo-test）：

```bash
make ci-local FULL=1
```

输出默认写入：

- `ci-output/static-check.log`
- `ci-output/e2e-demo.log`
- `ci-output/demo-logs.txt`

## 常见失败排查

- `e2e-demo` 卡住：检查 `ci-output/demo-logs.txt` 与 `ci-output/compose-ps.txt`
- demo 配置差异：失败时会额外上传 `ci-output/compose-config.yaml`
- Trivy 阻断：检查 CI 输出并用 `.trivyignore` 记录已知风险（必须包含 `# reason:` 与 `# expires:`）

## Branch Protection 配置

在 GitHub 仓库的 Branch protection 中将以下 checks 设为 Required：

- `static-check`
- `e2e-demo`
- `image-scan`
