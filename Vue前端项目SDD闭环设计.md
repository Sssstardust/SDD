# Vue 前端项目 SDD 闭环设计

**状态：** 已确认，待评审

**日期：** 2026-08-07

## 目标

扩展现有 SDD 内核，使 Vue/TypeScript 管理端和移动 H5 项目能够完成“需求到静态验收”的闭环，同时不影响现有 Java 和 Python 项目。

首版支持两个明确的项目画像：

- `vue-admin`：Vue 3、TypeScript、Vite 7、Vue Router 4、Pinia 持久化、Element Plus、Tailwind CSS 4、Vitest。
- `vue-mobile-h5`：Vue 3.4+、TypeScript 5.9+、Vite 5、Vue Router 4、Pinia 持久化、Vant 4、移动端视口适配、Vitest 和 Playwright 契约。

本版本只执行静态设计和准入校验，不安装依赖、不启动目标项目、不执行 Vitest，也不执行 Playwright。

## 范围与非目标

### 本期范围

- 前端项目画像检测和显式画像配置。
- Vue SFC 与 TypeScript 事实提取，包括页面、路由、组件、store、API client、依赖、别名、代理和画像相关配置。
- 从 `REQ-ID` 到前端设计资源、任务切片和测试契约的可追踪映射。
- 以 `frontend-map.json` 保存版本化的前端基线证据。
- 前端设计包 schema 和画像专属静态校验。
- 带有明确 `STATIC_PASS` 执行模式的静态 Gate 4/Gate 5。
- 生成带执行命令声明的 TypeScript 测试骨架。

### 本期不包含

- 依赖安装、构建、开发服务器启动、浏览器自动化或测试执行。
- React、Angular 或其他非 Vue 框架语义。
- 自动视觉回归或像素级布局校验。
- 替换现有后端 `module-map.json`，或替换 Java/Python Gate Adapter。

## 总体架构

前端能力作为现有 SDD 流水线中的适配层：

```text
需求输入
  -> FeatureBrief + 前端需求
  -> FrontendProjectProfile
  -> Vue/TypeScript 事实扫描器
  -> frontend-map.json 基线
  -> FrontendDesignContext
  -> 前端 design-pack
  -> 任务切片 + 前端测试契约
  -> 静态 Gate 4/5
```

现有需求解析、设计版本管理、任务切片、报告存储和流水线编排继续复用。前端事实和契约采用增量扩展。

### 核心领域对象

`FrontendProjectProfile` 包含：

- `profile_id`：`vue-admin` 或 `vue-mobile-h5`。
- `framework`：Vue 主版本和次版本范围。
- `language`：TypeScript。
- `build_tool`：Vite 版本范围。
- `ui_library`：Element Plus 或 Vant。
- `router`：Vue Router 版本范围。
- `state_library`：Pinia 及持久化插件。
- `package_manager`：pnpm。
- `test_frameworks`：Vitest 和 Playwright 能力声明。
- `scan_roots`、`design_roots`、`test_roots`。
- `commands`：类型检查、lint、单元测试、组件测试和端到端测试的静态命令元数据。
- `constraints`：画像专属的 UI、视口、别名、代理和部署约束。

`FrontendFacts` 保存规范化资源：

- `resource_key` 和 `kind`（`page`、`route`、`component`、`store`、`api_client`、`dependency`、`config`）。
- `source_file` 以及可选的行列证据。
- `component_id`。
- `framework` 和 `profile_id`。
- `evidence_level`（`L1` AST、`L2` 静态/配置推断、`L3` 声明/人工补充）。
- `confidence` 和 `unsupported_features`。

`FrontendDesignContext` 合并 `FeatureBrief`、当前项目画像、前端事实、已有 API/schema 证据以及需求到资源的映射。

前端基线单独保存为 `frontend-map.json`。现有后端 `module-map.json` 保持不变，继续服务 Java/Python 流程。

## 项目画像

画像解析优先级如下：

1. attachment 中的显式项目画像配置。
2. `package.json`、`vite.config.*`、路由配置和依赖检查结果。
3. 用户显式声明 `vue-admin` 或 `vue-mobile-h5` 后使用对应默认画像。

画像相关 Gate 遇到缺失或矛盾元数据时必须输出阻断诊断。前端功能不能静默回退到 Java 默认画像。

### `vue-admin` 约束

- 默认组件库为 Element Plus。
- 允许使用 Tailwind CSS 4 和 Sass。
- 需要权限控制的路由必须声明布局和权限元数据。
- 必须描述桌面端行为；页面同时用于窄屏时必须声明响应式行为。
- 如果项目存在 `/sba/api` 或 `/ota/api` 等 Vite 代理前缀，API client 契约必须记录对应关系。

### `vue-mobile-h5` 约束

- 默认组件库为 Vant。
- 项目配置了 `px-to-viewport` 或等效方案时，必须声明移动端适配规则。
- 页面必须声明窄屏行为和触摸交互状态。
- vconsole、扫码、图表和视频等 H5 能力作为可选能力建模，不能默认套用到所有页面。
- Docker/Nginx 和开发 HTTPS 配置作为部署元数据记录。

## 需求与设计产物

现有 `requirements`、`capability_tags` 和九章技术方案继续有效。前端功能增加：

```yaml
project_type: frontend
frontend_profile: vue-admin
capability_tags:
  - api
  - frontend-page
  - frontend-route
  - frontend-state
  - frontend-test
frontend:
  pages: [order-list]
  roles: [operator]
  responsive: desktop
```

前端需求记录需要标识页面、路由、交互、状态、权限、响应式行为或客户端错误行为。每个前端 `REQ-ID` 至少映射一个页面或交互状态；涉及数据时还必须映射 API client 或 Pinia store。

按标签初始化以下设计包文件：

| 标签 | 产物 | 必填内容 |
| --- | --- | --- |
| `frontend-page` | `frontend-pages.yaml` | 页面 ID、路由、布局、组件、加载/空/错误状态、REQ-ID |
| `frontend-route` | `frontend-routes.yaml` | 路径、名称、角色、守卫、入口页面、REQ-ID |
| `frontend-component` | `frontend-components.yaml` | 组件、UI 库、props、emits、slots、状态、REQ-ID |
| `frontend-state` | `frontend-state.yaml` | store ID、state、actions、持久化、失效策略、REQ-ID |
| `frontend-test` | `frontend-tests.yaml` | 测试级别、目标资源、动作、断言、视口、REQ-ID |
| `api` | 现有 OpenAPI 和接口文档 | 请求、响应、错误、调用资源、REQ-ID |

技术方案的九个必需章节保持不变。前端内容放入设计概述、核心流程、接口契约、异常处理、架构约束和验收矩阵中，保证当前 Gate 3 的章节校验兼容。

## 扫描器

扫描器放在 Node 侧，因为 Vue SFC 和 TypeScript AST 工具链更适合目标生态。Python 内核通过现有项目扫描边界调用扫描器，并校验返回的 JSON。

扫描器提取：

- Vue SFC 组件名、script setup 导入、props/emits、模板组件引用和源位置。
- Vue Router 路由记录、懒加载导入、路由元数据以及路由到页面的关系。
- Pinia `defineStore` ID、state/getters/actions、持久化声明和 store 导入关系。
- Axios 实例、baseURL、拦截器、代理前缀以及能够静态识别的接口引用。
- Vite 别名、插件、CSS 预处理器、视口插件和测试根目录。
- `package.json` 中的框架、UI 库、包管理器、Node 范围、脚本和测试依赖。

AST 事实为 `L1`，配置和静态推断为 `L2`，人工或需求声明为 `L3`。所有不支持的语法或动态结构都记录到 `unsupported_features`。要求精确引用资源的 Gate 不接受低置信度事实。

扫描器输出 source signature，并与 `frontend-map.json` 一起保存，用于在设计或实现准入前检查事实是否过期。

## 静态 Gate

### Gate 1：需求对齐

- 校验前端画像和前端 YAML 结构。
- 要求前端 `REQ-ID` 具备页面/交互引用。
- 拒绝未知前端能力标签和格式错误的资源 ID。

### Gate 2：证据与上下文

- 校验画像与依赖声明的一致性。
- 检查 brownfield 前端功能是否存在最新 `frontend-map.json`。
- 解析所有声明的页面、路由、store、API client 和组件。
- 精确引用如果只能由低置信度事实支持，则阻断。

### Gate 3：设计校验

- 校验所有前端设计包 schema。
- 执行画像规则：管理端使用 Element Plus/Tailwind，H5 使用 Vant/移动端适配。
- 按场景要求页面声明加载、空、错误、权限和响应式状态。
- 校验 REQ-ID 验收矩阵及设计资源引用。

### Gate 4：静态测试骨架

- 校验切片依赖、REQ-ID 映射、验收检查和前端测试用例。
- 根据 `frontend-tests.yaml` 生成 `.spec.ts` 骨架。
- 每个测试用例必须声明目标资源、动作、断言和测试级别。
- 不安装依赖、不执行测试。

### Gate 5：静态实现准入

- 校验声明的源码/测试根目录和生成测试路径。
- 校验 `package.json` 是否声明画像要求的脚本和依赖。
- 校验每个设计资源和 REQ-ID 是否存在对应的实现/测试路径声明。
- 输出 `execution_mode: static` 和 `result: STATIC_PASS`。
- 显式记录待执行的 Vitest/Playwright 检查；`STATIC_PASS` 不能被当作运行时 `PASS`。

路由重复、store ID 重复、资源引用缺失、REQ-ID 没有测试、画像与 UI 库不匹配、前端证据过期、测试命令缺失等情况直接阻断。

## 测试契约

每个前端测试用例包含：

- `case_id`、`req_id`、`level` 和 `target`。
- 前置条件、动作、断言和可选 API mock。
- 组件/端到端测试使用稳定定位策略。
- 命名的画像视口，例如 `admin-desktop` 或 `mobile-h5`。
- 目标支持时必须声明加载、空、成功和错误状态。

生成的骨架写入项目画像声明的测试根目录。如果没有声明测试根目录，则写入 `specs/<feature>/.generated/frontend-tests/`，并报告为待实现路径。

未来接入运行时执行器时，新增 `VueFrontendGateAdapter` 执行已有声明命令，将报告从 `STATIC_PASS` 升级为运行时 `PASS` 或 `FAIL`，不改变契约 schema。

## 错误处理与可追踪性

- 项目元数据缺失时，输出缺失字段和下一条修复命令，并阻断流程。
- 扫描解析失败时保留部分事实，记录源文件和不支持结构，同时降低置信度。
- P0/P1 需求引用的路由、store 或组件出现歧义时阻断流程。
- source signature 过期时，brownfield 设计必须先刷新前端基线或重新附着项目。
- 每个生成产物包含设计版本、画像 ID、source signature 以及 REQ-ID/资源映射。
- 静态报告区分 `STATIC_PASS`、`WARN`、`FAIL` 和待运行检查。

## 迁移与兼容性

- 现有 Java/Python attachment 继续使用当前语言画像、module map、测试骨架和 Adapter。
- 前端画像采用显式启用，不改变后端默认行为。
- 当前九章技术方案和报告 schema 保持向后兼容；前端字段采用增量和版本化方式增加。
- 没有前端标签的既有功能跳过前端扫描和校验。
- 第一批实现应先覆盖一个代表性管理端功能和一个代表性移动 H5 功能，再扩大扫描范围。

## 验收标准

1. Vue 管理端功能可以生成包含 `frontend_profile: vue-admin` 和前端能力标签的需求规格。
2. Vue 移动 H5 功能可以生成包含 `frontend_profile: vue-mobile-h5` 和移动约束的需求规格。
3. brownfield Vue 项目可以生成包含路由、页面/组件、store、依赖、证据级别和 source signature 的 `frontend-map.json`。
4. 前端设计包 schema 校验通过，并且每个 P0/P1 前端 REQ-ID 都映射到页面/交互和测试用例。
5. 静态 Gate 4 可以生成 `.spec.ts` 骨架，且不安装依赖、不执行测试。
6. 静态 Gate 5 只有在画像、设计、切片、路径和测试命令声明完整时才输出 `STATIC_PASS`。
7. 非前端功能的现有 Java/Python 测试套件和 Gate 行为保持不变。

