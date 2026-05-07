# 分层依赖规范

## 1. 规则定位

用于约束 UI、Controller、Service、Repository、StateMachine 等层级之间的依赖方向，避免设计文档出现反向依赖和职责漂移。

## 2. 必须项

- UI 只能通过 Controller 暴露的能力发起请求
- Controller 只能调用 Service 或 StateMachine，不直接下钻 Repository
- Service 承载核心业务逻辑，可以调用 Repository、Client、StateMachine
- Repository 只负责持久化访问，不作为主动调用方
- StateMachine 只负责状态转移和状态约束，不直接依赖 UI / Controller

## 3. 禁止项

- UI 直接调用 Service / Repository
- Controller 直接调用 Repository
- Service 直接依赖 UI
- Repository 反向调用上层业务对象
- StateMachine 直接依赖上层入口层

## 4. 审阅关注点

- 序列图参与者的命名是否能体现分层
- 调用方向是否符合“上层 -> 下层”的最小约束
- 是否有职责跨层混杂的对象
