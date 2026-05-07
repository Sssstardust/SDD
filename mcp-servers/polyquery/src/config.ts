import * as dotenv from 'dotenv';

dotenv.config();

export interface DatabaseConfig {
  host: string;
  port: number;
  user?: string;
  password?: string;
  database?: string;
  connectionString?: string;
}

// 危险 SQL 关键字（只读模式下禁止）
const DANGEROUS_KEYWORDS = [
  'INSERT', 'UPDATE', 'DELETE', 'DROP', 'TRUNCATE', 'ALTER',
  'CREATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE', 'MERGE',
  'CALL', 'SHUTDOWN', 'KILL'
];

// Redis 写入命令黑名单
const REDIS_WRITE_COMMANDS = [
  'SET', 'DEL', 'EXPIRE', 'HSET', 'HDEL', 'LPUSH', 'RPUSH', 'LPOP', 'RPOP',
  'SADD', 'SREM', 'ZADD', 'ZREM', 'FLUSHDB', 'FLUSHALL', 'RENAME', 'COPY',
  'APPEND', 'SETEX', 'SETNX', 'MSET', 'INCR', 'DECR', 'INCRBY', 'DECRBY'
];

export const Config = {
  // 安全配置
  READ_ONLY_MODE: (process.env.READ_ONLY_MODE || 'true').toLowerCase() === 'true',
  MAX_ROWS: parseInt(process.env.MAX_ROWS || '1000', 10),
  QUERY_TIMEOUT: parseInt(process.env.QUERY_TIMEOUT || '30000', 10),
  LOG_LEVEL: process.env.LOG_LEVEL || 'INFO',

  // 解析 MySQL 多数据源配置
  getMysqlConfigs(): Record<string, DatabaseConfig> | null {
    return this.parseMultiConfigs('MYSQL_CONFIGS', 3306, 'mysql');
  },

  // 解析 PostgreSQL 多数据源配置
  getPostgresConfigs(): Record<string, DatabaseConfig> | null {
    return this.parseMultiConfigs('POSTGRES_CONFIGS', 5432, 'postgresql');
  },

  // 解析 MongoDB 多数据源配置
  getMongodbConfigs(): Record<string, DatabaseConfig> | null {
    const multiConfigs = this.parseJsonConfigs('MONGODB_CONFIGS');
    if (!multiConfigs) return null;

    const result: Record<string, DatabaseConfig> = {};
    for (const [name, url] of Object.entries(multiConfigs)) {
      const config = this.parseMongodbUrl(url as string);
      if (config) result[name] = config;
    }
    return Object.keys(result).length > 0 ? result : null;
  },

  // 解析 Redis 多数据源配置
  getRedisConfigs(): Record<string, DatabaseConfig> | null {
    const multiConfigs = this.parseJsonConfigs('REDIS_CONFIGS');
    if (!multiConfigs) return null;

    const result: Record<string, DatabaseConfig> = {};
    for (const [name, url] of Object.entries(multiConfigs)) {
      const config = this.parseRedisUrl(url as string);
      if (config) result[name] = config;
    }
    return Object.keys(result).length > 0 ? result : null;
  },

  // 解析 Oracle 多数据源配置
  getOracleConfigs(): Record<string, DatabaseConfig> | null {
    const multiConfigs = this.parseJsonConfigs('ORACLE_CONFIGS');
    if (!multiConfigs) return null;

    const result: Record<string, DatabaseConfig> = {};
    for (const [name, url] of Object.entries(multiConfigs)) {
      const config = this.parseOracleUrl(url as string);
      if (config) result[name] = config;
    }
    return Object.keys(result).length > 0 ? result : null;
  },

  // 解析 SQLite 多数据源配置
  getSqliteConfigs(): Record<string, DatabaseConfig> | null {
    const multiConfigs = this.parseJsonConfigs('SQLITE_CONFIGS');
    if (!multiConfigs) return null;

    const result: Record<string, DatabaseConfig> = {};
    for (const [name, path] of Object.entries(multiConfigs)) {
      result[name] = {
        host: 'localhost',
        port: 0,
        database: path as string
      };
    }
    return Object.keys(result).length > 0 ? result : null;
  },

  // 通用多数据源配置解析
  parseMultiConfigs(
    multiConfigKey: string,
    defaultPort: number,
    dbType: string
  ): Record<string, DatabaseConfig> | null {
    const multiConfigs = this.parseJsonConfigs(multiConfigKey);
    if (!multiConfigs) return null;

    const result: Record<string, DatabaseConfig> = {};
    for (const [name, url] of Object.entries(multiConfigs)) {
      const config = this.parseSqlUrl(url as string, defaultPort);
      if (config) result[name] = config;
    }
    return Object.keys(result).length > 0 ? result : null;
  },

  // 解析 JSON 配置字符串
  parseJsonConfigs(envKey: string): Record<string, string> | null {
    const jsonStr = process.env[envKey];
    if (!jsonStr) return null;

    try {
      const parsed = JSON.parse(jsonStr);
      if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
        return parsed as Record<string, string>;
      }
      console.error(`${envKey} 必须是对象格式`);
      return null;
    } catch {
      console.error(`解析 ${envKey} 失败，请检查 JSON 格式`);
      return null;
    }
  },

  // 解析 MongoDB URL
  parseMongodbUrl(url: string): DatabaseConfig | null {
    try {
      const parsed = new URL(url);
      return {
        host: parsed.hostname,
        port: parseInt(parsed.port) || 27017,
        user: parsed.username || undefined,
        password: parsed.password || undefined,
        database: parsed.pathname.slice(1).split('?')[0] || 'test',
        connectionString: url
      };
    } catch {
      return null;
    }
  },

  // 解析 Redis URL
  parseRedisUrl(url: string): DatabaseConfig | null {
    // 手动解析 Redis URL，支持密码中的特殊字符（如 #）
    // 格式: redis://:password@host:port/db 或 redis://host:port/db
    try {
      // 移除协议前缀
      let remaining = url.replace(/^redis:\/\//, '');

      let password: string | undefined;
      let host: string;
      let port: number = 6379;
      let database: string = '0';

      // 从后往前解析，先找最后一个 @ 符号（密码可能包含 @）
      const atIndex = remaining.lastIndexOf('@');
      if (atIndex !== -1) {
        // 有认证信息
        const authPart = remaining.substring(0, atIndex);
        remaining = remaining.substring(atIndex + 1);

        // 认证格式: :password 或 user:password
        if (authPart.startsWith(':')) {
          password = authPart.substring(1);
        } else {
          const colonIndex = authPart.indexOf(':');
          if (colonIndex !== -1) {
            password = authPart.substring(colonIndex + 1);
          }
        }
      }

      // 解析 host:port/db
      const slashIndex = remaining.indexOf('/');
      if (slashIndex !== -1) {
        database = remaining.substring(slashIndex + 1) || '0';
        remaining = remaining.substring(0, slashIndex);
      }

      const colonIndex = remaining.lastIndexOf(':');
      if (colonIndex !== -1) {
        host = remaining.substring(0, colonIndex);
        port = parseInt(remaining.substring(colonIndex + 1)) || 6379;
      } else {
        host = remaining;
      }

      return {
        host,
        port,
        password: password ? decodeURIComponent(password) : undefined,
        database
      };
    } catch {
      return null;
    }
  },

  // 解析 Oracle URL
  parseOracleUrl(url: string): DatabaseConfig | null {
    // oracle://user:password@host:port/service
    const match = url.match(/^oracle:\/\/([^:]+):([^@]+)@([^:]+):(\d+)\/(.+)$/);
    if (match) {
      return {
        host: match[3],
        port: parseInt(match[4]),
        user: match[1],
        password: match[2],
        database: match[5]
      };
    }
    return null;
  },

  // 通用 SQL URL 解析
  parseSqlUrl(url: string, defaultPort: number): DatabaseConfig | null {
    try {
      const parsed = new URL(url);
      return {
        host: parsed.hostname,
        port: parseInt(parsed.port) || defaultPort,
        user: decodeURIComponent(parsed.username) || undefined,
        password: decodeURIComponent(parsed.password) || undefined,
        database: parsed.pathname.slice(1) || undefined
      };
    } catch {
      return null;
    }
  },

  // 验证 SQL 查询安全性
  validateSqlQuery(query: string): { valid: boolean; error?: string } {
    if (!this.READ_ONLY_MODE) {
      return { valid: true };
    }

    // 移除注释
    let cleanQuery = query.replace(/--.*$/gm, '');
    cleanQuery = cleanQuery.replace(/\/\*[\s\S]*?\*\//g, '');
    cleanQuery = cleanQuery.trim().toUpperCase();

    for (const keyword of DANGEROUS_KEYWORDS) {
      const regex = new RegExp(`\\b${keyword}\\b`);
      if (regex.test(cleanQuery)) {
        return { valid: false, error: `只读模式下禁止使用 ${keyword} 语句` };
      }
    }

    return { valid: true };
  },

  // 验证 Redis 命令安全性
  validateRedisCommand(command: string): { valid: boolean; error?: string } {
    if (!this.READ_ONLY_MODE) {
      return { valid: true };
    }

    if (REDIS_WRITE_COMMANDS.includes(command.toUpperCase())) {
      return { valid: false, error: `只读模式下禁止使用 ${command} 命令` };
    }

    return { valid: true };
  },

  // 验证标识符（表名、schema名）
  validateIdentifier(name: string): string {
    if (!name) return name;
    if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name)) {
      throw new Error(`无效的标识符: ${name}`);
    }
    return name;
  }
};
