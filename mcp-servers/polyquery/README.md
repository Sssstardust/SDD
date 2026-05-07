# PolyQuery MCP

[![npm version](https://badge.fury.io/js/polyquery-mcp.svg)](https://badge.fury.io/js/polyquery-mcp)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

一个支持多种数据库的 MCP (Model Context Protocol) 服务器，让 AI 助手能够安全地查询和探索数据库。

支持 **MySQL** | **PostgreSQL** | **MongoDB** | **Redis** | **Oracle** | **SQLite**

## ✨ 特性

- 🏢 **多数据源支持** - 每种数据库可配置多个数据源
- 📊 **多业务库管理** - 支持订单库、用户库、日志库等分离
- 🔄 **读写分离** - 支持主库/从库配置
- 🛡️ **安全只读** - 默认只读模式，防止误操作
- 🔌 **多数据库支持** - MySQL、PostgreSQL、MongoDB、Redis、Oracle、SQLite

## 🚀 快速开始

### 安装
```bash
npm install -g polyquery-mcp
```

### 配置 MCP 客户端

```json
{
  "mcpServers": {
    "polyquery": {
      "command": "polyquery-mcp",
      "env": {
        "MYSQL_CONFIGS": {
          "primary":"mysql://user:pass@primary-host:3306/main_db",
          "replica":"mysql://user:pass@replica-host:3306/main_db",
          "analytics":"mysql://user:pass@analytics-host:3306/report_db"
        },
        "POSTGRES_CONFIGS": {
          "main":"postgresql://user:pass@host:5432/main_db",
          "archive":"postgresql://user:pass@host:5432/archive_db"
        },
        "MONGODB_CONFIGS": {
          "main":"mongodb://user:pass@host:27017/main_db"
        },
        "REDIS_CONFIGS": {
          "cache":"redis://:pass@host:6379/0",
          "session":"redis://:pass@host:6379/1"
        },
        "ORACLE_CONFIGS": {
          "main":"oracle://user:pass@host:1521/main_service"
        },
        "SQLITE_CONFIGS": {
          "main":"/path/to/main.db",
          "archive":"/path/to/archive.db"
        },
        "READ_ONLY_MODE": "true",
        "MAX_ROWS": "1000",
        "QUERY_TIMEOUT": "30000"
      }
    }
  }
}
```

#### 使用 npx：

```json
{
  "mcpServers": {
    "polyquery": {
      "command": "npx",
      "args": ["-y", "polyquery-mcp"],
      "env": {
        "MYSQL_CONFIGS": {
          "primary":"mysql://user:pass@host:3306/db"
        },
        "READ_ONLY_MODE": "true"
      }
    }
  }
}
```

## 📝 配置说明

### 多数据源配置

使用 `*_CONFIGS` 环境变量配置多个数据源，值为 JSON 格式：

| 数据库 | 环境变量 | 示例 |
|--------|----------|------|
| MySQL | `MYSQL_CONFIGS` | `{"primary":"mysql://user:pass@host:3306/db","replica":"mysql://user:pass@host:3306/db"}` |
| PostgreSQL | `POSTGRES_CONFIGS` | `{"main":"postgresql://user:pass@host:5432/db","archive":"postgresql://user:pass@host:5432/archive"}` |
| MongoDB | `MONGODB_CONFIGS` | `{"main":"mongodb://user:pass@host:27017/db"}` |
| Redis | `REDIS_CONFIGS` | `{"cache":"redis://:pass@host:6379/0","session":"redis://:pass@host:6379/1"}` |
| Oracle | `ORACLE_CONFIGS` | `{"main":"oracle://user:pass@host:1521/service"}` |
| SQLite | `SQLITE_CONFIGS` | `{"main":"/path/to/main.db","archive":"/path/to/archive.db"}` |

### 安全配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `READ_ONLY_MODE` | `true` | 只读模式，禁止 INSERT/UPDATE/DELETE |
| `MAX_ROWS` | `1000` | 查询返回的最大行数 |
| `QUERY_TIMEOUT` | `30000` | 查询超时时间（毫秒） |

## 🔧 可用工具

| 工具 | 说明 |
|------|------|
| `query_database` | 执行数据库查询 |
| `list_tables` | 列出所有表/集合 |
| `describe_table` | 获取表结构信息 |
| `test_connection` | 测试数据库连接 |
| `list_databases` | 列出已配置的数据库及数据源 |

### 工具参数说明

- `db_type`: 数据库类型（mysql/postgres/mongodb/redis/oracle/sqlite）
- `connection_name`: 数据源名称（可选，默认使用 `default`）
- 使用 `list_databases` 查看可用的数据源列表

## 💡 使用示例

### 查看已配置的数据源
```
→ list_databases()
```
返回示例：
```json
{
  "success": true,
  "data": [
    { "type": "mysql", "configured": true, "sources": ["primary", "replica", "analytics"] },
    { "type": "postgres", "configured": true, "sources": ["main", "archive"] },
    { "type": "mongodb", "configured": false, "sources": [] }
  ]
}
```

### 查询指定数据源
```
"查询主库中 users 表的数据"
→ query_database(db_type="mysql", connection_name="primary", query="SELECT * FROM users LIMIT 10")

"从报表库查询销售数据"
→ query_database(db_type="mysql", connection_name="analytics", query="SELECT * FROM sales_report WHERE date > '2024-01-01'")
```

### MongoDB 查询
```
"查询主 MongoDB 中状态为 pending 的订单"
→ query_database(db_type="mongodb", connection_name="main", query='{"collection":"orders","filter":{"status":"pending"}}')
```

### Redis 查询
```
"从缓存 Redis 获取用户会话"
→ query_database(db_type="redis", connection_name="cache", query="GET session:user:123")
```

### 不指定 connection_name（使用 default）
```
"查询默认数据源的表列表"
→ list_tables(db_type="mysql")
```

## 🔒 安全特性

- ✅ 默认只读模式，禁止写操作 INSERT/UPDATE/DELETE
- ✅ 自动添加 LIMIT 防止返回过多数据
- ✅ 查询超时保护
- ✅ SQL 注入防护
- ✅ 敏感信息脱敏
- ✅ 标识符验证（防止非法表名/schema名）

## 🛠 本地开发

```bash
git clone https://github.com/yourusername/polyquery-mcp.git
cd polyquery-mcp
npm install
npm run build
```

## 📚 配置场景示例

### 场景 1：读写分离
```json
{
  "env": {
    "MYSQL_CONFIGS": "{\"primary\":\"mysql://write_user:pass@master:3306/app\",\"replica\":\"mysql://read_user:pass@slave:3306/app\"}"
  }
}
```

### 场景 2：多业务库
```json
{
  "env": {
    "POSTGRES_CONFIGS": "{\"orders\":\"postgresql://user:pass@host:5432/orders\",\"users\":\"postgresql://user:pass@host:5432/users\",\"inventory\":\"postgresql://user:pass@host:5432/inventory\"}"
  }
}
```

### 场景 3：多环境管理
```json
{
  "env": {
    "MYSQL_CONFIGS": "{\"dev\":\"mysql://user:pass@dev-host:3306/app\",\"test\":\"mysql://user:pass@test-host:3306/app\",\"prod\":\"mysql://user:pass@prod-host:3306/app\"}"
  }
}
```

### 场景 4：Redis 多用途
```json
{
  "env": {
    "REDIS_CONFIGS": "{\"cache\":\"redis://:pass@host:6379/0\",\"session\":\"redis://:pass@host:6379/1\",\"queue\":\"redis://:pass@host:6379/2\"}"
  }
}
```

## 🤝 贡献
欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License
