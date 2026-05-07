# Feature Brief 模板

**版本:** `vX.Y`  
**日期:** `YYYY-MM-DD`  
**状态:** `Draft | Review | Approved`  

---

## 1. 基本信息

```yaml
project_mode: brownfield
project_mode_source: agent
project_mode_confidence: 0.85
project_mode_evidence:
  - "检测到现有 src/main/java"
project_mode_confirmed_by: zhangsan

feature_name: order-create
feature_type: sync
one_liner: "一句话描述功能目标"

sdd_level: full # light | standard | full
capability_tags:
  - api
  - db-change
  - payment

risk_tier: high
```

---

## 2. 需求清单

```yaml
requirements:
  - req_id: REQ-001
    priority: P0
    title: "需求标题"
    description: |-
      需求详细描述。
      可使用多行文本。
  - req_id: REQ-002
    priority: P1
    title: "需求标题"
    description: |-
      需求详细描述。
```

---

## 3. 歧义与待澄清项

使用规则：

- AI 发现不确定点时必须内联 `[AMBIGUOUS: ...]`
- 进入设计阶段前必须全部清零

若当前没有歧义，也必须明确写：

```markdown
- 无
```

---

## 4. 业务说明

- 背景：
- 业务目标：
- 非目标：
- 成功标准：

---

## 5. 依赖与影响范围

- 涉及模块：
- 涉及数据库：
- 涉及外部系统：
- 是否影响现有接口：

---

## 6. 风险说明

- 为什么当前 `risk_tier` 是这个级别：
- 是否需要架构审批：
- 是否存在上线风险：

---

## 7. 审阅记录

- 审阅人：
- 审阅结论：
- 审阅时间：
