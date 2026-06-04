# Application Layer

当前目录用于承接脚本分层架构中的 application 层映射说明。

当前已承接的应用层模块：

- `pipeline_runtime.py`
- `pipeline_execution.py`
- `gate_cache_runtime.py`
- `doctor_runtime.py`
- `project_runtime.py`
- `pipeline_cli.py`
- `pipeline_dispatch.py`
- `gates/`
- `generators/`
- `refreshers/`

仍处于旧路径但逻辑上属于 application 的模块：

- `../pipeline_orchestration.py`
- `../project_flow_runner.py`
- `../traceability_summaries.py`
- `../gate5_admissions.py`

后续仍会继续收口到：

- `application/gates/`
- `application/generators/`
- `application/refreshers/`

说明：

- `gates/`、`generators/`、`refreshers/` 当前已经具备 catalog 入口。
- 第一阶段仍保留旧脚本物理位置，catalog 负责提供稳定映射。
