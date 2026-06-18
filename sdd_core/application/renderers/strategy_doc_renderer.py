from __future__ import annotations
from typing import Any
from sdd_core.domain.design_common import feature_req_ids
from sdd_core.domain.api_schema_inferer import build_default_apis

def render_idempotent_strategy(context: dict[str, Any], design_version: str) -> str:
    requirements = context["structured_prd"].get("requirements", []) or []
    req_ids_text = feature_req_ids(requirements)
    apis = build_default_apis(context)
    first_api = apis[0]
    key = f"{context['feature_slug']}:{{bizId}}:{first_api['method'].lower()}"
    return f"""# 幂等策略

## 1. 元信息

- feature_name: {context['feature_name']}
- design_version: {design_version}
- req_ids: {req_ids_text}

## 2. 场景说明

- 哪些操作需要幂等：主流程写操作与重复提交敏感操作
- 为什么需要幂等：避免重复请求导致状态重复流转或数据重复写入
- 幂等失败会导致什么问题：状态不一致、重复执行、副作用放大

## 3. 幂等键设计

| 场景 | 幂等键 | 生成方式 | 生命周期 |
| --- | --- | --- | --- |
| 主流程提交 | {key} | 服务端基于业务主键与操作类型拼接 | 10 分钟 |

## 4. 冲突处理策略

- 重复请求返回什么：直接返回最近一次已确认结果
- 冲突时是否重试：否，命中幂等即停止重复执行
- 是否记录冲突事件：是，记录幂等命中日志与冲突上下文

## 5. 存储与过期策略

- 存储位置：Redis
- TTL：10 分钟
- 清理策略：自然过期

## 6. 人工审阅关注点

- 幂等键是否稳定且可复现：需在评审中确认
- TTL 是否合理：当前按短时重试场景设置
- 冲突处理是否符合业务预期：需结合业务状态机确认
"""

def render_payment_state_machine(context: dict[str, Any], design_version: str) -> str:
    requirements = context["structured_prd"].get("requirements", []) or []
    req_ids_text = feature_req_ids(requirements)
    return f"""# 支付状态机

## 1. 元信息

- feature_name: {context['feature_name']}
- design_version: {design_version}
- req_ids: {req_ids_text}

## 2. 状态列表

| 状态 | 含义 | 是否终态 | 备注 |
| --- | --- | --- | --- |
| WAIT_REVIEW | 待处理/待审核 | 否 | 初始状态 |
| SUCCESS | 处理成功 | 是 | 终态 |
| FAILED | 处理失败 | 是 | 终态 |

## 3. 状态转移

| 当前状态 | 触发事件 | 下一状态 | 条件 | 失败处理 |
| --- | --- | --- | --- | --- |
| WAIT_REVIEW | process | SUCCESS | 校验通过且事务提交成功 | 返回业务冲突错误 |
| WAIT_REVIEW | reject | FAILED | 校验失败或人工驳回 | 记录失败原因并拒绝重复执行 |

## 4. 异常与补偿

- 支付超时处理：记录超时并进入人工/补偿路径
- 回调失败处理：保留失败状态并触发补偿检查
- 补单/补偿逻辑：在对账或人工修复环节闭环

## 5. 事务边界

- 主状态切换与关键记录写入在同一事务边界内完成
- 事务边界外的异步或外部调用必须有重试/补偿说明

## 6. 人工审阅关注点

- 是否存在非法状态跳转：需在评审中确认
- 是否定义了终态：是，SUCCESS / FAILED
- 补偿逻辑是否闭环：需结合对账与人工修复策略确认
"""

def render_reconcile_strategy(context: dict[str, Any], design_version: str) -> str:
    requirements = context["structured_prd"].get("requirements", []) or []
    req_ids_text = feature_req_ids(requirements)
    return f"""# 对账策略

## 1. 元信息

- feature_name: {context['feature_name']}
- design_version: {design_version}
- req_ids: {req_ids_text}

## 2. 对账对象

- 内部账务对象：核心业务状态与关键记录
- 外部账务对象：{"外部调用结果或渠道结果" if 'external-call' in context['capability_tags'] else "当前无明确外部账务对象"}
- 对账维度：状态、时间、业务主键、处理结果

## 3. 对账频率

- 实时 / 准实时 / 日终：日终校验，关键链路可补充准实时抽样
- 调度方式：定时任务
- 失败重试方式：失败后重试并告警

## 4. 差异处理

| 差异类型 | 识别方式 | 处理策略 | 是否人工介入 |
| --- | --- | --- | --- |
| 状态不一致 | 主记录与审计记录不一致 | 生成差异记录并告警 | 是 |
| 外部结果缺失 | 外部调用或对账结果未回写 | 进入补偿与人工核查流程 | 是 |

## 5. 补偿与修复

- 自动修复逻辑：仅对可重试场景触发自动补偿
- 人工修复入口：运营/管理后台或人工审计流程
- 审计留痕：保留差异记录、补偿结果与人工操作日志

## 6. 人工审阅关注点

- 对账维度是否完整：需结合真实账务链路确认
- 差异处理是否可落地：需在评审中确认
- 是否有审计闭环：是，需保留差异与补偿记录
"""

def render_async_event_contract(context: dict[str, Any]) -> str:
    slug = context["feature_slug"].replace("-", "_")
    pascal = context["feature_pascal"]
    return f"""event: {pascal}Event
topic: TOPIC_{slug.upper()}
producer: {pascal}Service
consumer: {pascal}Consumer
payload:
  type: object
retry:
  max_attempts: 3
dlq: DLQ_{slug.upper()}
"""

def render_external_call_strategy(context: dict[str, Any], design_version: str) -> str:
    requirements = context["structured_prd"].get("requirements", []) or []
    req_ids_text = feature_req_ids(requirements)
    dependency = next(iter(context["structured_prd"].get("dependencies", []) or []), "外部系统")
    return f"""# 外部调用策略

## 1. 元信息

- feature_name: {context['feature_name']}
- design_version: {design_version}
- req_ids: {req_ids_text}

## 2. 调用关系

- 调用方：{context['feature_pascal']} 所属服务
- 被调方：{dependency}
- 调用目的：完成主流程中的外部协同处理

## 3. 超时策略

- 超时时间：2000ms
- 配置来源：服务级外部调用配置
- 超时后的业务处理：记录失败并进入重试/补偿判断

## 4. 重试策略

- 最大重试次数：3
- 重试间隔：指数退避
- 是否幂等：{"是" if 'idempotent' in context['capability_tags'] else "需结合业务确认"}

## 5. 熔断与降级

- 熔断条件：连续超时或失败率升高
- 恢复条件：健康检查恢复正常
- 降级方案：返回保守结果并触发人工/异步补偿

## 6. 监控与告警

- 监控指标：成功率、超时率、重试次数、熔断次数
- 告警阈值：失败率和超时率超过阈值立即告警
- 责任人：待指定服务负责人

## 7. 人工审阅关注点

- 重试是否会放大流量：需在评审中确认
- 降级是否可接受：需结合业务损失评估
- 告警阈值是否合理：需结合运行环境调整
"""

