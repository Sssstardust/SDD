# 架构说明

## 1. 元信息

- feature_name： task-board
- project_mode: greenfield
- owner： TBD
## 2. 总体架构

- 系统形态（单体 / 微服务）： 单体内独立业务模块，后续按边界保留拆分空间
- 主要模块： task-board-api、task-board-domain、task-board-infra
- 关键依赖： 日志、配置、监控、数据库访问、测试框架
## 3. 分层与边界

- 接口层： com.example.task_board.controller
- 应用层： com.example.task_board.service
- 领域层： com.example.task_board.domain
- 基础设施层： com.example.task_board.repository / com.example.task_board.config
## 4. 关键设计约束

- 事务边界： 仅在应用层聚合写操作时开启事务，避免跨层滥用事务
- 异常处理： 统一业务异常编码和兜底异常转换，禁止向上抛出裸异常
- 配置策略： 环境差异通过配置项显式管理，默认值必须可追踪
- 监控与日志： 主流程指标、错误指标、关键审计日志在 bootstrap 阶段先定义占位
## 5. 人工审阅关注点

- 架构边界是否清晰： 当前按四层边界拆分，后续功能设计不得跨层直连
- 是否存在过早复杂化： 暂不引入额外中间件和多余模块，优先保持可演进的最小骨架