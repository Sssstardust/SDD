import * as fs from "node:fs";
import * as path from "node:path";

export type RuleMeta = {
  id: string;
  file: string;
  title: string;
  ruleType: string;
  appliesToFeatureTypes: string[];
  appliesToTags: string[];
  must: string[];
  forbidden: string[];
  summary: string;
};

export type SemanticCheck = {
  id: string;
  whenAnyTags?: string[];
  whenFeatureTypes?: string[];
  type: "file_contains" | "design_or_file_contains";
  file?: string;
  requiredAll?: string[];
  requiredAnyGroups?: string[][];
  designAnyKeywords?: string[];
  fallbackFile?: string;
  fallbackRequiredAll?: string[];
  successMessage: string;
  errorMessage: string;
};

export type FeatureRuleResponse = {
  feature_type: string;
  capability_tags: string[];
  rules: RuleMeta[];
  constraints: {
    must: string[];
    forbidden: string[];
    semantic_checks: SemanticCheck[];
  };
};

export const ROOT = path.resolve(__dirname, "..", "..", "..");
export const PACKAGE_STANDARDS_DIR = path.resolve(ROOT, "mcp-servers", "arch-standard", "rules");
export const DOCS_STANDARDS_DIR = path.resolve(ROOT, "docs", "arch-standards");
export const STANDARDS_DIR = fs.existsSync(DOCS_STANDARDS_DIR) ? DOCS_STANDARDS_DIR : PACKAGE_STANDARDS_DIR;

export const RULES: RuleMeta[] = [
  {
    id: "layering",
    file: "layering-rules.md",
    title: "分层依赖规范",
    ruleType: "layering",
    appliesToFeatureTypes: ["crud", "sync", "payment", "notification", "batch", "general"],
    appliesToTags: [],
    must: ["UI 只能通过 Controller 发起请求", "Controller 只能调用 Service 或 StateMachine", "Repository 不作为主动调用方"],
    forbidden: ["UI 直接调用 Service / Repository", "Controller 直接调用 Repository", "Service 直接依赖 UI"],
    summary: "约束序列图中的分层调用和依赖方向。",
  },
  {
    id: "transaction",
    file: "transaction-rules.md",
    title: "事务边界规范",
    ruleType: "transaction",
    appliesToFeatureTypes: ["sync", "payment", "batch"],
    appliesToTags: ["db-change", "payment"],
    must: ["关键状态切换必须明确事务边界", "数据库变更必须包含回滚策略"],
    forbidden: ["事务边界缺失", "长耗时外部调用无约束地放进事务"],
    summary: "约束事务边界、回滚和补偿。",
  },
  {
    id: "api",
    file: "api-rules.md",
    title: "接口设计规范",
    ruleType: "api",
    appliesToFeatureTypes: ["crud", "sync", "payment", "notification", "general"],
    appliesToTags: ["api"],
    must: ["接口契约必须落盘", "请求字段和响应字段必须有说明", "错误码必须和处理策略成对出现"],
    forbidden: ["只有路径没有用途说明", "没有请求/响应说明", "没有业务错误码"],
    summary: "约束接口契约、接口文档和错误码说明。",
  },
  {
    id: "exception",
    file: "exception-rules.md",
    title: "异常处理规范",
    ruleType: "exception",
    appliesToFeatureTypes: ["crud", "sync", "payment", "notification", "batch", "general"],
    appliesToTags: [],
    must: ["主流程至少有一张异常处理表", "关键异常场景要有触发条件和处理策略"],
    forbidden: ["只写 happy path", "关键异常场景没有错误码"],
    summary: "约束异常处理章节的完整度。",
  },
  {
    id: "naming",
    file: "naming-rules.md",
    title: "命名规范",
    ruleType: "naming",
    appliesToFeatureTypes: ["crud", "sync", "payment", "notification", "batch", "general"],
    appliesToTags: [],
    must: ["类名使用稳定 CamelCase", "表名使用 t_ 前缀", "状态机命名体现业务含义"],
    forbidden: ["模糊缩写作为核心类名", "表名与领域对象完全无关"],
    summary: "约束设计中的类、表和状态机命名。",
  },
  {
    id: "external-call",
    file: "external-call-rules.md",
    title: "外部调用规范",
    ruleType: "external-call",
    appliesToFeatureTypes: ["sync", "payment", "notification"],
    appliesToTags: ["external-call"],
    must: ["外部调用必须说明超时时间", "外部调用必须说明重试策略", "外部调用必须说明熔断或降级策略"],
    forbidden: ["无上限重试", "超时和熔断都缺失"],
    summary: "约束外部系统调用的超时、重试、熔断和降级。",
  },
  {
    id: "idempotency",
    file: "idempotency-rules.md",
    title: "幂等规范",
    ruleType: "idempotency",
    appliesToFeatureTypes: ["sync", "payment", "general"],
    appliesToTags: ["idempotent"],
    must: ["幂等策略必须说明幂等键", "幂等策略必须说明冲突处理", "幂等策略必须说明 TTL 或生命周期"],
    forbidden: ["只写需要幂等但没有键设计", "没有 TTL 或过期策略"],
    summary: "约束幂等键、冲突处理与 TTL。",
  },
  {
    id: "payment",
    file: "payment-rules.md",
    title: "支付与对账规范",
    ruleType: "payment",
    appliesToFeatureTypes: ["payment"],
    appliesToTags: ["payment"],
    must: ["支付设计必须有状态转移说明", "支付状态机必须明确事务边界", "对账策略必须包含差异处理", "对账策略必须包含补偿或修复路径"],
    forbidden: ["只写状态列表不写状态转移", "对账策略没有差异处理与补偿说明"],
    summary: "约束支付状态机、事务边界和对账补偿。",
  },
];

export const SEMANTIC_CHECKS: SemanticCheck[] = [
  {
    id: "transaction-boundary",
    whenAnyTags: ["payment", "db-change"],
    type: "design_or_file_contains",
    designAnyKeywords: ["事务边界", "事务"],
    fallbackFile: "design-pack/支付状态机.md",
    fallbackRequiredAll: ["事务边界"],
    successMessage: "事务边界说明已存在",
    errorMessage: "涉及 payment/db-change，但未发现明确事务边界说明",
  },
  {
    id: "idempotent-strategy",
    whenAnyTags: ["idempotent"],
    type: "file_contains",
    file: "design-pack/幂等策略.md",
    requiredAll: ["幂等键", "冲突", "TTL"],
    successMessage: "幂等策略具备关键语义",
    errorMessage: "幂等策略缺少关键语义：幂等键 / 冲突处理 / TTL",
  },
  {
    id: "payment-state-machine",
    whenAnyTags: ["payment"],
    type: "file_contains",
    file: "design-pack/支付状态机.md",
    requiredAll: ["状态转移", "事务边界"],
    successMessage: "支付状态机具备关键语义",
    errorMessage: "支付状态机缺少关键语义：状态转移 / 事务边界",
  },
  {
    id: "payment-reconcile",
    whenAnyTags: ["payment"],
    type: "file_contains",
    file: "design-pack/对账策略.md",
    requiredAll: ["差异处理"],
    requiredAnyGroups: [["补偿", "修复"]],
    successMessage: "对账策略具备关键语义",
    errorMessage: "对账策略缺少关键语义：差异处理 / 补偿或修复",
  },
  {
    id: "external-call-strategy",
    whenAnyTags: ["external-call"],
    type: "file_contains",
    file: "design-pack/外部调用策略.md",
    requiredAll: ["超时", "重试", "熔断", "降级", "fallback"],
    successMessage: "外部调用策略具备关键语义",
    errorMessage: "外部调用策略缺少关键语义：超时 / 重试 / 熔断 / 降级 / fallback",
  },
];

export function readRuleContent(file: string): string {
  const rulePath = path.join(STANDARDS_DIR, file);
  return fs.existsSync(rulePath)
    ? fs.readFileSync(rulePath, "utf8")
    : `[文件不存在: ${file}，请在 docs/arch-standards/ 下创建]`;
}

export function listRules(): RuleMeta[] {
  return RULES;
}

export function getRuleByIdOrFile(ruleIdOrFile: string): RuleMeta | undefined {
  return RULES.find((rule) => rule.id === ruleIdOrFile || rule.file === ruleIdOrFile);
}

export function getRule(ruleIdOrFile: string): { rule: RuleMeta | null; content: string | null } {
  const rule = getRuleByIdOrFile(ruleIdOrFile);
  if (!rule) {
    return { rule: null, content: null };
  }
  return { rule, content: readRuleContent(rule.file) };
}

function intersects(values: string[], targets: string[]): boolean {
  if (!targets.length) {
    return false;
  }
  const set = new Set(values);
  return targets.some((item) => set.has(item));
}

export function selectRules(featureType: string, capabilityTags: string[], ruleFiles?: string[]): RuleMeta[] {
  if (ruleFiles && ruleFiles.length > 0) {
    return RULES.filter((rule) => ruleFiles.includes(rule.file) || ruleFiles.includes(rule.id));
  }
  return RULES.filter((rule) => {
    const featureMatch = rule.appliesToFeatureTypes.length === 0 || rule.appliesToFeatureTypes.includes(featureType);
    const tagMatch = rule.appliesToTags.length === 0 || intersects(capabilityTags, rule.appliesToTags);
    if (rule.appliesToTags.length === 0) {
      return featureMatch;
    }
    return featureMatch || tagMatch;
  });
}

export function getConstraints(ruleIds?: string[]): { rules: RuleMeta[]; constraints: FeatureRuleResponse["constraints"] } {
  const rules = ruleIds && ruleIds.length > 0 ? RULES.filter((rule) => ruleIds.includes(rule.id) || ruleIds.includes(rule.file)) : RULES;
  const must = Array.from(new Set(rules.flatMap((rule) => rule.must)));
  const forbidden = Array.from(new Set(rules.flatMap((rule) => rule.forbidden)));
  const semantic_checks = ruleIds && ruleIds.length > 0
    ? SEMANTIC_CHECKS.filter((check) => ruleIds.includes(check.id))
    : SEMANTIC_CHECKS;
  return { rules, constraints: { must, forbidden, semantic_checks } };
}

export function getFeatureRules(featureType: string, capability_tags: string[], ruleFiles?: string[]): FeatureRuleResponse {
  const rules = selectRules(featureType, capability_tags, ruleFiles);
  const must = Array.from(new Set(rules.flatMap((rule) => rule.must)));
  const forbidden = Array.from(new Set(rules.flatMap((rule) => rule.forbidden)));
  const semantic_checks = SEMANTIC_CHECKS.filter((check) => {
    const featureMatch = !check.whenFeatureTypes || check.whenFeatureTypes.length === 0 || check.whenFeatureTypes.includes(featureType);
    const tagMatch = !check.whenAnyTags || check.whenAnyTags.length === 0 || intersects(capability_tags, check.whenAnyTags);
    if (check.whenAnyTags && check.whenAnyTags.length > 0) {
      return featureMatch && tagMatch;
    }
    return featureMatch;
  });

  return {
    feature_type: featureType,
    capability_tags: capability_tags,
    rules,
    constraints: {
      must,
      forbidden,
      semantic_checks,
    },
  };
}


export function getLayeringSemantics(): Record<string, any> {
  const fallback = {
    layers: {
      ui: { suffixes: ["UI"] },
      controller: { suffixes: ["Controller"] },
      service: { suffixes: ["Service"] },
      repository: { suffixes: ["Repository"] },
      state_machine: { suffixes: ["StateMachine"] },
    },
    direction_rules: [
      { from: "ui", allowed_to: ["controller"], error: "UI 不应直接调用 {dst_name}" },
      { from: "controller", allowed_to: ["service", "state_machine"], error: "Controller 不应直接调用 {dst_name}" },
      { from: "repository", allowed_to: [], error: "Repository 不应作为主动调用方: {src_name} -> {dst_name}" },
      { from: "service", forbidden_to: ["ui"], error: "Service 不应直接依赖 UI: {src_name} -> {dst_name}" },
      { from: "state_machine", forbidden_to: ["ui", "controller"], error: "StateMachine 不应直接依赖上层: {src_name} -> {dst_name}" },
    ],
  };

  const semanticsFile = path.resolve(STANDARDS_DIR, "layering-semantics.json");
  if (!fs.existsSync(semanticsFile)) {
    return fallback;
  }

  try {
    const data = JSON.parse(fs.readFileSync(semanticsFile, "utf8"));
    return typeof data === "object" && data !== null ? data : fallback;
  } catch {
    return fallback;
  }
}

