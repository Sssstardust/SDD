# Feature Brief: 团队任务看板系统

**版本:** `v1.3`  
**状态:** `Ready for Design`  

---

## 1. 基本信息

```yaml
project_mode: greenfield
project_mode_source: agent
project_mode_confidence: 1.0
project_mode_confirmed_by: zhaoxingchen

feature_name: task-board
feature_type: sync
one_liner: "小团队轻量级看板系统，支持权重排序、延迟提醒与业务审计。"

capability_tags:
  - api
  - db-change
  - async
  - external-call

risk_tier: high
```

---

## 2. 需求清单

```yaml
requirements:
  - req_id: REQ-001
    priority: P0
    title: "任务基础 CRUD"
    description: "标题、描述、负责人、优先级、截止日期、状态管理。"
  - req_id: REQ-002
    priority: P0
    title: "看板拖拽排序"
    description: "按状态分列，支持权重分数算法保证列表内垂直顺序。"
  - req_id: REQ-003
    priority: P1
    title: "通知与到期提醒"
    description: "任务分派通知；截止前 24h 提醒。采用消费端校验解决变更一致性。"
  - req_id: REQ-004
    priority: P1
    title: "评论与动态记录"
    description: "支持任务下留言，状态变更自动产生业务动态。需包含审计字段。"
  - req_id: REQ-005
    priority: P0
    title: "权限与并发控制"
    description: "普通成员限本人任务；负责人全量权限。强制乐观锁拒绝更新冲突。"
```

---

## 3. 技术决策记录 (已确认)

1. **排序**: 權重分數算法 (DOUBLE 類型)。
2. **通知**: 延遲消息 + 消費端狀態比對。
3. **動態**: `t_activity` 業務日誌表。
4. **併發**: CAS 樂觀鎖 (`version` 字段)。

---

## 4. 业务约束

- 在线人数 < 50。
- 数据最终持久化一致性。
