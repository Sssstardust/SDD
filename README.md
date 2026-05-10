# SDD Team Distribution

这套仓库用于给项目组共享一套统一的 SDD 流程工具。

仓库本身负责：

- 流程编排
- 设计模板与 Gate 校验
- MCP / Skill / 脚本入口
- 附着外部业务项目后的 baseline 与项目级产物生成

业务源码、SQL、构建配置默认不放在这个工具仓库里，而是通过“附着目标项目”的方式接入。

---

## 安装前提

- Windows + PowerShell preferred; cross-platform readiness check is available via `python scripts/doctor.py`
- Python 3.13+
- Node.js 18+
- Platform matrix: [docs/platform-support-matrix.md](docs/platform-support-matrix.md)
- Java / `javac`（用于 Gate 5 Java 验证测试）

---

## 首次接入

推荐直接使用一条标准入口：

```powershell
python scripts/run_pipeline.py onboard-project `
  --project-root D:\your-target-project `
  --design-root D:\your-design-root `
  --schema-root D:\your-target-project\src\main\resources
```

别名：

```powershell
python scripts/run_pipeline.py bootstrap-attached-project `
  --project-root D:\your-target-project `
  --design-root D:\your-design-root `
  --schema-root D:\your-target-project\src\main\resources
```

这条命令会自动完成：

1. 保存附着项目配置
2. 刷新 baseline 快照
3. 生成项目级控制台产物

---

## 常用命令

查看当前附着项目：

```powershell
python scripts/run_pipeline.py show-attachment
```

刷新 baseline：

```powershell
python scripts/run_pipeline.py refresh-baseline --strict
```

使用 polyquery MCP 刷新数据库事实：

```powershell
python scripts/run_pipeline.py refresh-schema-context --from-polyquery --polyquery-config config\polyquery.json --polyquery-fallback fail
```

说明见 [docs/polyquery-integration.md](docs/polyquery-integration.md)。

刷新项目级产物：

```powershell
python scripts/run_pipeline.py project-console-cycle
```

对单个 feature 跑 Gate：

```powershell
python scripts/run_pipeline.py gate1 your-feature
python scripts/run_pipeline.py gate2 your-feature
python scripts/run_pipeline.py gate3 your-feature
python scripts/run_pipeline.py generate-task-slices your-feature
python scripts/run_pipeline.py gate4 your-feature
python scripts/run_pipeline.py gate5 your-feature
```

同步已验证设计到实现态 baseline 时，推荐显式指定版本：

```powershell
python scripts/run_pipeline.py sync-baseline your-feature --design-version v1
```

设计阶段完整门禁：

```powershell
python scripts/run_pipeline.py design-gates your-feature --strict
```

复核所有已有报告：

```powershell
python scripts/run_pipeline.py validate-all-reports --stage all
```

推荐主链路：

```powershell
python scripts/run_pipeline.py refresh-baseline --strict --feature-dir specs\your-feature
python scripts/run_pipeline.py design-gates specs\your-feature --strict
python scripts/run_pipeline.py implementation-gates specs\your-feature --strict
python scripts/run_pipeline.py release-gate specs\your-feature --strict
python scripts/run_pipeline.py validate-all-reports --stage all
```

可直接复用的 GitHub Actions 示例：

- [.github/workflows/sdd-pipeline.example.yml](.github/workflows/sdd-pipeline.example.yml)

---

## 产物位置

附着配置：

- [.spec/attached-project.json](.spec/attached-project.json)

baseline 分桶目录：

- `.spec/baselines/<attached-project-bucket>/`

项目级产物分桶目录：

- `.spec/project-artifacts/<attached-project-bucket>/`

版本化证据：

- `reports/vN/design-pack.snapshot/`：Gate 1 通过后冻结的 Design Pack
- `reports/vN/gate-report.json`：Gate 结论、执行命令和证据 hash
- `.spec/baselines/<attached-project-bucket>/sdd-index-real.json`：实现态记录及同步时证据链

---

## 常见问题

### 1. 为什么不把业务源码放在这个仓库里？

因为这个仓库的目标是团队共享的 SDD 工具，不是某个业务项目本身。源码应保留在各自业务仓库，工具仓库通过附着模式去扫描和校验。

### 2. `gate5` 里的 `implementation_result` 依赖什么？

依赖附着项目源码生成的 `module-map.json`。如果没有先接入目标项目并刷新 `module-map`，真实实现追溯就不会成立。

### 3. baseline 和 project console 为什么不在 `specs/` 里？

因为它们已经按附着项目分桶，避免多个业务项目共用同一套工具时互相覆盖。

### 4. 设计目录能放在外部仓库吗？

可以。`onboard-project` 和 `attach-project` 都支持 `--design-root`。

### 5. 当前 MVP 边界是什么？

- `project-explorer` 当前不是编译器级索引，复杂 Lombok、继承和框架生成代码仍可能需要人工确认。
- `schema-context` 可以来自本地 SQL / design-pack 快照，也可以来自 polyquery；两者可信度不同。
- `Gate 5` 当前仍以设计验证测试为主，真实业务测试需要在 attached project 中配置 `verification_commands`。
- `design-pack/` 是草稿区，Gate 1 通过后以后续 `reports/vN/design-pack.snapshot/` 作为版本证据。
- 多组件、多数据源 baseline 已有分桶基础，但组件级隔离还需要继续演进。

---

## 文档入口

- [团队接入入口](docs/team-onboarding.md)
- [Agent 接入说明](docs/agent-integration.md)
- [附着模式说明](docs/attached-project-mode.md)
- [示例附着项目](examples/fixtures/attached-sample-project/README.md)
