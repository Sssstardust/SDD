# Feature Brief

**版本:** `v1.0`  
**日期:** `2026-05-07`  
**状态:** `Draft`  

---

## 1. 基本信息

```yaml
project_mode: hybrid
project_mode_source: heuristic
project_mode_confidence: 0.60
project_mode_evidence:
  - "当前仅有 SDD 工作区上下文，缺少真实业务工程事实"
project_mode_confirmed_by: zhangsan

feature_name: tob-oa-office-demo
feature_type: general
one_liner: "人事：员工档案、组织架构"

capability_tags:
  - api
  - async
  - db-change
  - security-sensitive

risk_tier: high
```

---

## 2. 需求清单
```yaml
requirements:
  - req_id: REQ-001
    priority: P0
    title: "人事"
    description: |-
      人事：员工档案、组织架构
  - req_id: REQ-002
    priority: P1
    title: "审批"
    description: |-
      审批：请假、加班、报销、流程自定义
  - req_id: REQ-003
    priority: P1
    title: "公告通知、消息推送"
    description: |-
      公告通知、消息推送
  - req_id: REQ-004
    priority: P1
    title: "日程考勤、打卡签到"
    description: |-
      日程考勤、打卡签到
  - req_id: REQ-005
    priority: P1
    title: "文件网盘、在线预览"
    description: |-
      文件网盘、在线预览
  - req_id: REQ-006
    priority: P1
    title: "面向 ToB 企业客户"
    description: |-
      面向 ToB 企业客户，需支持多角色协同使用。
  - req_id: REQ-007
    priority: P1
    title: "审批流程需要具备一定可配置性"
    description: |-
      审批流程需要具备一定可配置性。
  - req_id: REQ-008
    priority: P1
    title: "文件能力至少支持上传、下载与常见办公文件在线预览"
    description: |-
      文件能力至少支持上传、下载与常见办公文件在线预览。
```

---

## 3. 歧义与待澄清项
- [AMBIGUOUS: project_mode 当前为 hybrid，置信度不足 0.8，建议人工确认。]

---

## 4. 业务说明

- 背景：本 Feature Brief 基于 `tob-oa-office-prd.md` 的 structured-prd 生成，需求类型为 `general`，生成方式为 `规则抽取`。当前同时存在新建与存量改造信号，建议在设计前明确边界。
- 业务目标：人事：员工档案、组织架构
- 非目标：PRD 未明确声明的扩展流程、额外接口和新增实体不默认纳入本轮范围。 当前范围不默认包含新增外部系统对接。 所有歧义项需在进入设计前清零。
- 成功标准：P0 需求全部可追溯并形成设计输入：人事；关键接口映射完整（12 项）；关键实体识别完整（12 项）

### 4.1 需求优先级映射
- P0：人事
- P1：审批；公告通知、消息推送；日程考勤、打卡签到；文件网盘、在线预览；面向 ToB 企业客户；审批流程需要具备一定可配置性；文件能力至少支持上传、下载与常见办公文件在线预览
- P2：无

### 4.2 关键业务规则映射
- 需求：ToB 企业 OA 办公系统
- 面向 ToB 企业客户，需支持多角色协同使用
- 审批流程需要具备一定可配置性

---

## 5. 依赖与影响范围
- 涉及模块：接口层、数据库层、异步事件链路、安全与审计
- 涉及实体：ToB、审批、通知、消息、Employee、Org
- 涉及数据库：是
- 涉及外部系统：待补充
- 是否影响现有接口：是
- 关键接口：GET /api/v1/hr/employees；POST /api/v1/hr/employees；GET /api/v1/hr/org-tree；GET /api/v1/approvals

### 5.1 实体映射
- `ToB`（domain-entity）：PRD 出现标识符 ToB
- `审批`（domain-entity）：PRD 中出现业务对象 审批
- `通知`（domain-entity）：PRD 中出现业务对象 通知
- `消息`（domain-entity）：PRD 中出现业务对象 消息
- `Employee`（domain-entity）：由接口路径 /api/v1/hr/employees 推导
- `Org`（domain-entity）：由接口路径 /api/v1/hr/org-tree 推导
- `Approval`（domain-entity）：由接口路径 /api/v1/approvals 推导
- `Leave`（domain-entity）：由接口路径 /api/v1/approvals/leave 推导
- `Overtime`（domain-entity）：由接口路径 /api/v1/approvals/overtime 推导
- `Reimburse`（domain-entity）：由接口路径 /api/v1/approvals/reimburse 推导
- `Notice`（domain-entity）：由接口路径 /api/v1/notices 推导
- `Message`（domain-entity）：由接口路径 /api/v1/messages/push 推导

### 5.2 接口映射
- `GET /api/v1/hr/employees`：GET employees；证据：GET /api/v1/hr/employees
- `POST /api/v1/hr/employees`：POST employees；证据：POST /api/v1/hr/employees
- `GET /api/v1/hr/org-tree`：GET org tree；证据：GET /api/v1/hr/org-tree
- `GET /api/v1/approvals`：GET approvals；证据：GET /api/v1/approvals
- `POST /api/v1/approvals/leave`：POST leave；证据：POST /api/v1/approvals/leave
- `POST /api/v1/approvals/overtime`：POST overtime；证据：POST /api/v1/approvals/overtime
- `POST /api/v1/approvals/reimburse`：POST reimburse；证据：POST /api/v1/approvals/reimburse
- `POST /api/v1/approvals/process-definitions`：POST process definitions；证据：POST /api/v1/approvals/process-definitions
- `GET /api/v1/notices`：GET notices；证据：GET /api/v1/notices
- `POST /api/v1/notices`：POST notices；证据：POST /api/v1/notices
- `POST /api/v1/messages/push`：POST push；证据：POST /api/v1/messages/push
- `GET /api/v1/attendance/records`：GET records；证据：GET /api/v1/attendance/records

### 5.3 依赖映射
- 无明确外部依赖

### 5.4 结构化补充上下文
```yaml
entities:
  - name: "ToB"
    kind: "domain-entity"
    evidence: "PRD 出现标识符 ToB"
  - name: "审批"
    kind: "domain-entity"
    evidence: "PRD 中出现业务对象 审批"
  - name: "通知"
    kind: "domain-entity"
    evidence: "PRD 中出现业务对象 通知"
  - name: "消息"
    kind: "domain-entity"
    evidence: "PRD 中出现业务对象 消息"
  - name: "Employee"
    kind: "domain-entity"
    evidence: "由接口路径 /api/v1/hr/employees 推导"
  - name: "Org"
    kind: "domain-entity"
    evidence: "由接口路径 /api/v1/hr/org-tree 推导"
  - name: "Approval"
    kind: "domain-entity"
    evidence: "由接口路径 /api/v1/approvals 推导"
  - name: "Leave"
    kind: "domain-entity"
    evidence: "由接口路径 /api/v1/approvals/leave 推导"
  - name: "Overtime"
    kind: "domain-entity"
    evidence: "由接口路径 /api/v1/approvals/overtime 推导"
  - name: "Reimburse"
    kind: "domain-entity"
    evidence: "由接口路径 /api/v1/approvals/reimburse 推导"
  - name: "Notice"
    kind: "domain-entity"
    evidence: "由接口路径 /api/v1/notices 推导"
  - name: "Message"
    kind: "domain-entity"
    evidence: "由接口路径 /api/v1/messages/push 推导"
apis:
  - method: GET
    path: "/api/v1/hr/employees"
    summary: "GET employees"
    evidence: "GET /api/v1/hr/employees"
  - method: POST
    path: "/api/v1/hr/employees"
    summary: "POST employees"
    evidence: "POST /api/v1/hr/employees"
  - method: GET
    path: "/api/v1/hr/org-tree"
    summary: "GET org tree"
    evidence: "GET /api/v1/hr/org-tree"
  - method: GET
    path: "/api/v1/approvals"
    summary: "GET approvals"
    evidence: "GET /api/v1/approvals"
  - method: POST
    path: "/api/v1/approvals/leave"
    summary: "POST leave"
    evidence: "POST /api/v1/approvals/leave"
  - method: POST
    path: "/api/v1/approvals/overtime"
    summary: "POST overtime"
    evidence: "POST /api/v1/approvals/overtime"
  - method: POST
    path: "/api/v1/approvals/reimburse"
    summary: "POST reimburse"
    evidence: "POST /api/v1/approvals/reimburse"
  - method: POST
    path: "/api/v1/approvals/process-definitions"
    summary: "POST process definitions"
    evidence: "POST /api/v1/approvals/process-definitions"
  - method: GET
    path: "/api/v1/notices"
    summary: "GET notices"
    evidence: "GET /api/v1/notices"
  - method: POST
    path: "/api/v1/notices"
    summary: "POST notices"
    evidence: "POST /api/v1/notices"
  - method: POST
    path: "/api/v1/messages/push"
    summary: "POST push"
    evidence: "POST /api/v1/messages/push"
  - method: GET
    path: "/api/v1/attendance/records"
    summary: "GET records"
    evidence: "GET /api/v1/attendance/records"
business_rules:
  - "需求：ToB 企业 OA 办公系统"
  - "面向 ToB 企业客户，需支持多角色协同使用"
  - "审批流程需要具备一定可配置性"
dependencies:
  - "无"
```

---

## 6. 风险说明

- 风险级别：`high`
- 为什么当前 `risk_tier` 是这个级别：同时命中 `async + db-change`，按规范自动判定为 `high`；命中 `security-sensitive`，按规范自动判定为 `high`
- 是否需要架构审批：是
- 项目模式影响：当前 `project_mode=hybrid`，来源 `heuristic`，置信度 `0.60`。
- 设计关注点：数据模型、DDL 与回滚脚本；消息重试、死信与消费幂等；权限控制、审计与脱敏；存量兼容边界与新模块边界
- 是否存在上线风险：需结合详细设计和实现阶段进一步确认。

---

## 7. 审阅记录

- 审阅人：
- 审阅结论：
- 审阅时间：
