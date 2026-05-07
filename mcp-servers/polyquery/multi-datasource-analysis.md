# PolyQuery MCP 多数据源配置修改方案分析

> 分析日期: 2026-02-25
> 分析目标: 将单一数据库配置改为支持多数据源配置

---

## 一、需求概述

### 当前配置方式（单数据源）
```bash
MYSQL_URL=mysql://user:pass@host:3306/db
POSTGRES_URL=postgresql://user:pass@host:5432/db
MONGODB_URL=mongodb://user:pass@host:27017/db
```

**限制**: 每种数据库只能配置一个连接

### 目标配置方式（多数据源）
```bash
# JSON 格式配置
MYSQL_CONFIGS='{"primary":"mysql://user:pass@primary:3306/db","replica":"mysql://user:pass@replica:3306/db"}'
POSTGRES_CONFIGS='{"main":"postgresql://user:pass@host:5432/main","archive":"postgresql://user:pass@host:5432/archive"}'
```

---

## 二、修改的好处

### 1. 多环境管理能力
| 场景 | 当前方案 | 目标方案 |
|------|----------|----------|
| 开发/测试/生产切换 | 需修改配置 | 同时配置，按需选择 |
| 环境对比查询 | 不支持 | 支持跨环境查询 |

```json
{
  "mysql": {
    "dev": "mysql://user:pass@dev-host:3306/db",
    "test": "mysql://user:pass@test-host:3306/db",
    "prod": "mysql://user:pass@prod-host:3306/db"
  }
}
```

### 2. 多业务库支持
适合微服务架构下的多数据源场景：
```json
{
  "mysql": {
    "order_db": "mysql://user:pass@host:3306/orders",
    "user_db": "mysql://user:pass@host:3306/users",
    "inventory_db": "mysql://user:pass@host:3306/inventory"
  }
}
```

### 3. 读写分离场景
```json
{
  "postgres": {
    "primary": "postgresql://user:pass@master:5432/db",
    "replica": "postgresql://user:pass@slave:5432/db"
  }
}
```

### 4. 向后兼容性
- ✅ 保持现有的 `MYSQL_URL` 单数据源配置
- ✅ 新增 `MYSQL_CONFIGS` JSON 配置作为扩展
- ✅ 旧用户无需修改即可继续使用

---

## 三、改动工程量评估

### 需要修改的文件

| 文件 | 改动内容 | 复杂度 |
|------|----------|--------|
| `src/config.ts` | 新增 JSON 配置解析，修改返回类型 | ⭐⭐⭐ 中等 |
| `src/factory.ts` | 修改适配器缓存策略，增加 source 参数 | ⭐⭐⭐ 中等 |
| `src/index.ts` | 修改工具参数定义和调用逻辑 | ⭐⭐ 较小 |
| `README.md` | 更新配置文档和示例 | ⭐ 简单 |

### 具体改动点

#### 1. config.ts - 配置解析模块

**当前实现:**
```typescript
getMysqlConfig(): DatabaseConfig | null {
  const url = process.env.MYSQL_URL;
  if (!url) return null;
  return this.parseSqlUrl(url, 3306);
}
```

**目标实现:**
```typescript
getMysqlConfig(): Record<string, DatabaseConfig> | null {
  // 1. 优先尝试解析 MYSQL_CONFIGS (JSON)
  const configsJson = process.env.MYSQL_CONFIGS;
  if (configsJson) {
    return this.parseMultiConfigs(configsJson, 'mysql');
  }
  
  // 2. 回退到 MYSQL_URL (单数据源)
  const url = process.env.MYSQL_URL;
  if (url) {
    const config = this.parseSqlUrl(url, 3306);
    return config ? { default: config } : null;
  }
  
  return null;
}
```

#### 2. factory.ts - 适配器工厂

**当前实现:**
```typescript
getAdapter(dbType: string): DatabaseAdapter {
  if (adapterCache.has(type)) {
    return adapterCache.get(type)!;
  }
  const adapter = createAdapter(type);
  adapterCache.set(type, adapter);
  return adapter;
}
```

**目标实现:**
```typescript
getAdapter(dbType: string, source?: string): DatabaseAdapter {
  const cacheKey = `${type}:${source || 'default'}`;
  
  if (adapterCache.has(cacheKey)) {
    return adapterCache.get(cacheKey)!;
  }
  
  const adapter = createAdapter(type, source);
  adapterCache.set(cacheKey, adapter);
  return adapter;
}
```

#### 3. index.ts - 工具定义

**当前工具定义:**
```typescript
{
  name: 'query_database',
  inputSchema: {
    type: 'object',
    properties: {
      db_type: { type: 'string', enum: DB_TYPES },
      query: { type: 'string' },
      limit: { type: 'number' }
    },
    required: ['db_type', 'query']
  }
}
```

**目标工具定义:**
```typescript
{
  name: 'query_database',
  inputSchema: {
    type: 'object',
    properties: {
      db_type: { type: 'string', enum: DB_TYPES },
      connection_name: {  // 新增可选参数
        type: 'string',
        description: '数据源标识（可选，默认使用默认连接）'
      },
      query: { type: 'string' },
      limit: { type: 'number' }
    },
    required: ['db_type', 'query']
  }
}
```

---

## 四、技术挑战与解决方案

| 挑战 | 说明 | 解决方案 |
|------|------|----------|
| **JSON 环境变量转义** | 在 shell 中写 JSON 容易出错 | 提供配置文件方式作为替代方案 |
| **配置优先级** | JSON 配置和单 URL 如何共存 | JSON 优先，单 URL 作为 fallback |
| **缓存管理** | 需要按 (dbType, source) 组合缓存 | 使用复合 key: `${dbType}:${source}` |
| **工具接口变化** | `list_databases` 输出格式需调整 | 返回树形结构或扁平列表 |

---

## 五、工作量估算

| 任务 | 预估时间 | 说明 |
|------|----------|------|
| config.ts 重构 | 2-3 小时 | 处理向后兼容，JSON 解析 |
| factory.ts 修改 | 1-2 小时 | 缓存策略调整 |
| index.ts 工具更新 | 1 小时 | Schema 和调用逻辑 |
| 文档更新 | 1 小时 | README 和示例 |
| 测试验证 | 2 小时 | 新旧配置兼容性测试 |
| **总计** | **7-9 小时** | - |

---

## 六、建议的实施步骤

### 阶段一: 配置模块重构
1. 修改 `config.ts`，添加 JSON 配置解析方法
2. 修改所有 `getXxxConfig()` 方法返回类型
3. 实现向后兼容逻辑（优先 JSON，fallback 到单 URL）

### 阶段二: 工厂模式改造
1. 修改 `getAdapter()` 函数签名，增加 `source` 参数
2. 实现复合 key 缓存策略
3. 修改 `createAdapter()` 支持按 source 创建实例

### 阶段三: 工具接口更新
1. 更新所有工具的 `inputSchema`，增加 `connection_name` 参数
2. 修改工具调用处理器，传递 source 参数
3. 更新 `list_databases` 工具输出格式

### 阶段四: 文档更新
1. 更新 README 配置说明
2. 提供新旧配置方式对比示例
3. 添加多数据源使用场景示例

### 阶段五: 测试验证
1. 测试单 URL 配置（向后兼容）
2. 测试 JSON 多数据源配置
3. 测试混合配置场景
4. 验证缓存正确性

---

## 七、配置示例

### 方案 A: 纯 JSON 配置（推荐新用户）
```json
{
  "mcpServers": {
    "polyquery": {
      "command": "polyquery-mcp",
      "env": {
        "MYSQL_CONFIGS": "{\"primary\":\"mysql://user:pass@primary:3306/db\",\"replica\":\"mysql://user:pass@replica:3306/db\"}",
        "POSTGRES_CONFIGS": "{\"main\":\"postgresql://user:pass@host:5432/main\"}",
        "READ_ONLY_MODE": "true",
        "MAX_ROWS": "1000"
      }
    }
  }
}
```

### 方案 B: 混合配置（向后兼容）
```json
{
  "mcpServers": {
    "polyquery": {
      "command": "polyquery-mcp",
      "env": {
        "MYSQL_URL": "mysql://user:pass@host:3306/db",
        "POSTGRES_CONFIGS": "{\"main\":\"postgresql://user:pass@host:5432/main\",\"archive\":\"postgresql://user:pass@host:5432/archive\"}"
      }
    }
  }
}
```

### 方案 C: 配置文件方式（避免转义问题）
```bash
# 创建配置文件
export POLYQUERY_CONFIG_FILE="/path/to/config.json"
```

---

## 八、风险与注意事项

1. **环境变量长度限制**: 某些系统对环境变量长度有限制，JSON 配置可能超出
2. **特殊字符转义**: JSON 中的密码如果包含特殊字符需要正确转义
3. **缓存内存占用**: 多数据源会增加缓存实例数量，需关注内存使用
4. **连接池管理**: 每个数据源独立管理连接池，需合理配置最大连接数

---

## 九、总结

### 收益
- ✅ 支持多环境、多业务库、读写分离等复杂场景
- ✅ 保持向后兼容，不影响现有用户
- ✅ 提升系统灵活性和可扩展性

### 成本
- 开发工作量: 7-9 小时
- 需要修改 4 个核心文件
- 需要全面测试验证

### 建议
**推荐实施** - 该修改能显著提升系统的实用性，且向后兼容的设计保证了平滑过渡。
