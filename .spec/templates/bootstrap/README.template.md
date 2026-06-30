# {{feature_name}}

本目录是功能规约、设计、任务与门禁报告的统一入口。

## 目录导航

| 文件或目录 | 用途 |
| --- | --- |
| `需求规格.md` | 需求、风险等级、能力标签与 REQ-ID 清单 |
| `技术方案-v1.md` | 主设计文档，承载架构说明、模块边界、接口、数据、异常与验收矩阵 |
| `流程看板.md` | 当前 SDD 流程状态的人读摘要 |
| `design-pack/` | OpenAPI、接口文档、数据模型、SQL 等可校验设计资产 |
| `tasks/` | 任务切片与人工任务清单 |
| `reports/v1/` | Gate、验证、发布门禁报告 |
| `.generated/` | 工具生成的辅助产物，不作为人工主文档维护 |

## 工程边界

- project_mode: greenfield
- package_base: {{package_base}}
- 默认分层: controller -> service -> domain -> repository
- 禁止依赖方向: repository 反向依赖 service/controller，controller 直接访问 repository

## 基线原则

- P0/P1 需求必须可追溯到验收矩阵和测试。
- 写操作与敏感查询必须经过显式鉴权。
- 日志、导出和监控不得直接暴露敏感字段。
- 发布前必须具备监控、告警、灰度和回滚方案。

## 推荐阅读顺序

1. `需求规格.md`
2. `技术方案-v1.md`
3. `tasks/任务清单.md`
4. `reports/v1/gate-report.json`
5. `发布计划.md`
