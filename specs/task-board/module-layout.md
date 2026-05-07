# 模块布局

## 1. 模块清单

| 模块名 | 职责 | 是否核心模块 | 备注 |
| --- | --- | --- | --- |
| task-board | 承载 task-board 的核心业务能力与对外接口 | 是 | greenfield bootstrap 默认主模块 |

## 2. 包结构约定

- controller： com.example.task_board.controller
- service： com.example.task_board.service
- domain： com.example.task_board.domain
- repository： com.example.task_board.repository
- config： com.example.task_board.config
## 3. 模块依赖关系

- 允许的依赖方向： controller -> service -> domain -> repository，config 仅提供基础设施装配
- 禁止的依赖方向： repository 反向依赖 service / controller，controller 直接访问 repository
## 4. 人工审阅关注点

- 模块划分是否过细： 当前保持单主模块，后续按明确业务边界再拆分子模块
- 包结构是否便于后续扩展： 预留 controller/service/domain/repository/config 五类基础包结构