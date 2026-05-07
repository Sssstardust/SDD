# Task Slice 模板

**版本:** `vX.Y`  
**日期:** `YYYY-MM-DD`  
**状态:** `Draft | Review | Approved`  

---

## 1. 切片元数据

```yaml
slice_id: SLICE-001-BIZ
slice_type: vertical   # vertical | cross-cutting
depends_on: []

req_ids:
  - REQ-001
  - REQ-002

acceptance_checks:
  - "可测量的验收条件 1"
  - "可测量的验收条件 2"

test_spec:
  type: integration
  framework: junit5
  target_class: OrderServiceTest
  cases:
    - id: TC-001
      req_id: REQ-001
      description: "测试说明"
```

---

## 2. 切片目标

- 本切片解决什么问题：
- 覆盖哪些用户路径或横切任务：
- 为什么这个切片需要独立存在：

---

## 3. 涉及范围

- 涉及模块：
- 涉及类：
- 涉及接口：
- 涉及表：
- 涉及配置：

---

## 4. 实施步骤

1. 
2. 
3. 

---

## 5. 验收条件说明

| REQ-ID | 验收条件 | 判定方式 |
| --- | --- | --- |
| REQ-001 |  |  |
| REQ-002 |  |  |

---

## 6. 测试策略

- 单测：
- 集成测试：
- 回归测试：
- 是否需要压测：

---

## 7. 风险与阻塞项

- 当前风险：
- 阻塞依赖：
- 回滚点：

---

## 8. 审阅记录

- 审阅人：
- 审阅结论：
- 审阅时间：
