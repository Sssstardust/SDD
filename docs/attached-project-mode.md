# Attached Project Mode

## 1. 目的

`SDD` 工具仓库本身只负责：

- 流程编排
- 设计文档与模板
- Gate 校验
- MCP / Skill / 脚本入口

真实业务源码与数据库脚本不再放在工具仓库根目录，而是通过“附着目标项目”的方式接入。

当前模式下：

- `design_roots` 可继续指向当前工具仓库，也可显式指向外部设计目录
- `module-map.json` 来自附着项目源码
- `schema-context.json` 来自附着项目 SQL / 资源目录
- baseline 产物按附着项目写入独立桶目录
- `project-console / flow-overview / project-next / tooling-hygiene` 也按附着项目写入独立目录

---

## 2. 适用场景

适用于以下团队协作方式：

- 统一发布 SDD 工具仓库给项目组共享
- 各业务项目独立维护自己的源码与 SQL
- 团队成员只用同一套 SDD 工具流程，不把业务实现混进工具仓库

---

## 3. 最小接入步骤

### 3.0 团队推荐入口

如果是团队成员第一次接入，优先使用：

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

详细说明见：

- [team-onboarding.md](team-onboarding.md)

---

### 3.1 绑定目标项目

```powershell
python scripts/run_pipeline.py attach-project --project-root D:\your-target-project
```

如果设计资产也在外部目录：

```powershell
python scripts/run_pipeline.py attach-project `
  --project-root D:\your-target-project `
  --design-root D:\your-design-root `
  --schema-root D:\your-target-project\src\main\resources
```

查看当前绑定结果：

```powershell
python scripts/run_pipeline.py show-attachment
```

查看当前多项目 workspace 摘要：

```powershell
python scripts/run_pipeline.py attach-project --show-workspace
```

清空绑定：

```powershell
python scripts/run_pipeline.py attach-project --clear
```

附着配置文件默认写入：

- [../.spec/attached-project.json](../.spec/attached-project.json)
- `workspace.json` 风格摘要会写入 `../.spec/workspace.json`

---

### 3.2 刷新代码事实快照

```powershell
python scripts/run_pipeline.py refresh-module-map
```

产物：

- `.spec/baselines/<attached-project-bucket>/module-map.json`

效果：

- 从附着项目的 `src/main/java` / `src/test/java` 扫描类、方法、来源文件
- `Gate 2 / Gate 5` 的实现追溯使用这份快照

---

### 3.3 刷新数据库事实快照

```powershell
python scripts/run_pipeline.py refresh-schema-context
```

产物：

- `.spec/baselines/<attached-project-bucket>/schema-context.json`

效果：

- 从附着项目的 `schema_roots` 中扫描 SQL
- 结合 `specs/**/design-pack/数据模型.md` 生成表结构上下文
- `Gate 2` 的表结构真实性校验使用这份快照

---

### 3.4 继续执行 Gate

示例：

```powershell
python scripts/run_pipeline.py gate2 D:\project\SDD\specs\pilot-order-create
python scripts/run_pipeline.py gate3 D:\project\SDD\specs\pilot-order-create
python scripts/run_pipeline.py gate5 D:\project\SDD\specs\pilot-order-create
```

---

## 4. 默认目录约定

`attach-project` 默认会为目标项目推导这些目录：

- `scan_roots`
  - `<project-root>/src/main/java`
  - `<project-root>/src/test/java`
- `schema_roots`
  - `<project-root>/src/main/resources`
  - `<project-root>/src/test/resources`
  - `<project-root>/db`
  - `<project-root>/sql`
- `design_roots`
  - 默认是当前工具仓库的 `specs`
  - 也可以通过 `attach-project --design-root ...` 指向外部设计目录

如果目标项目目录结构不同，可直接编辑附着配置文件或后续扩展命令参数。

---

## 5. 当前示例项目

仓库内提供了一个示例附着项目：

- [../examples/fixtures/attached-sample-project](../examples/fixtures/attached-sample-project)

用途：

- 演示附着模式如何工作
- 作为 `project-explorer / module-map / schema-context` 的默认 fixture
- 保障本仓库的 Gate 演示链路可验证

这个示例项目不是 SDD 工具本体的一部分，只是 fixture。

---

## 6. Baseline 分桶

当存在附着目标项目时，baseline 不再共用 `.spec/baseline/`，而是写入：

```text
.spec/baselines/<attached-project-name>-<hash>/
```

当前活跃 baseline 桶通常包含：

- `module-map.json`
- `schema-context.json`
- `sdd-index-design.json`
- `sdd-index-real.json`
- `constitution.md`
- `tech-debt.md`

这样不同业务项目可以共享同一套 SDD 工具，而不会互相覆盖 baseline 产物。

---

## 7. 项目级产物分目录

当存在附着目标项目时，项目级控制台与状态产物不再写入 `specs/`，而是写入：

```text
.spec/project-artifacts/<attached-project-name>-<hash>/
```

当前会写入这个目录的产物包括：

- `project-next.json / project-next.md`
- `flow-overview.json / flow-overview.md`
- `project-console.json / project-console.md`
- `tooling-hygiene.json / tooling-hygiene.md`

---

## 8. 团队使用建议

- 设计资产可以统一维护在 SDD 工具仓库，也可以独立维护在外部设计仓库
- 业务代码、SQL、构建配置保留在各自业务仓库
- 每次切换业务项目时，先执行一次 `attach-project`

---

## 9. Gate 5 真实项目验证命令

如果希望 Gate 5 不只执行 SDD 生成的设计验证骨架，还要联动目标业务项目的真实测试命令，可以在 `.spec/attached-project.json` 中增加 `verification_commands`。

示例：

```json
{
  "name": "your-project",
  "project_root": "D:\\your-target-project",
  "scan_roots": ["D:\\your-target-project\\src\\main\\java"],
  "design_roots": ["D:\\your-design-root"],
  "schema_roots": ["D:\\your-target-project\\src\\main\\resources"],
  "verification_commands": [
    {
      "name": "unit-test",
      "command": ["mvn", "test"]
    }
  ]
}
```

说明：

- `command` 使用数组形式，避免 shell 字符串转义问题。
- 默认在 `project_root` 下执行。
- 命令中可以使用 `{feature_name}` 占位符。
- 任一命令返回非 0，Gate 5 会判定为 `FAIL`。
- 每次跑 `Gate 2 / Gate 5` 之前，优先刷新 `module-map` 和 `schema-context`

推荐顺序：

```powershell
python scripts/run_pipeline.py attach-project `
  --project-root D:\your-target-project `
  --design-root D:\your-design-root
python scripts/run_pipeline.py refresh-baseline --strict --feature-dir specs\your-feature
python scripts/run_pipeline.py design-gates your-feature --strict
python scripts/run_pipeline.py implementation-gates your-feature --strict
python scripts/run_pipeline.py release-gate your-feature --strict
```

如果已经配置 polyquery MCP，推荐把 `schema-context` 刷新替换为实时数据库事实：

```powershell
python scripts/run_pipeline.py refresh-schema-context --from-polyquery --polyquery-config config\polyquery.json --polyquery-fallback fail
```

### Release 例外文件

如需紧急放行，可在对应 `reports/vN/` 下补录 `exception.json`，并由 `release-gate` 直接读取。

模板参考：

- [../document/template/Release-Exception-模板.json](../document/template/Release-Exception-模板.json)

---

## 9. 当前限制

- `schema-context` 默认仍可由“设计模型 + 附着项目 SQL”生成；配置 polyquery 后可通过 `--from-polyquery` 切换为数据库元数据，报告会记录 `source / fallback_from / confidence`。
- 本地 fallback 适合试点和离线演示，高风险 feature 推荐使用 `--polyquery-fallback fail`。
- `Gate 5` 目前仍以设计验证测试为主；如要作为上线门禁，应配置 `verification_commands` 并在严格流程中要求执行成功。
- `project-explorer` 当前不是编译器级 Java 索引，复杂 Lombok、代理类、框架生成方法需要结合人工确认或后续 AST 扫描升级。
- `design-pack/` 是草稿区；Gate 1 通过后冻结为 `reports/vN/design-pack.snapshot/`，baseline 同步优先使用版本快照。

---

## 10. 后续建议

下一步优先级建议：

1. 为附着模式补一份面向团队成员的发布说明和初始化脚本
2. 逐步把 `Gate 5` 从“设计验证测试”推进到“正式业务测试载体”
3. 视需要把 baseline 产物改成按附着项目分桶，而不是共用同一份 `.spec/baseline/`
