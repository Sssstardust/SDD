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

const DANGEROUS_KEYWORDS = [
  'INSERT',
  'UPDATE',
  'DELETE',
  'DROP',
  'TRUNCATE',
  'ALTER',
  'CREATE',
  'GRANT',
  'REVOKE',
  'EXEC',
  'EXECUTE',
  'MERGE',
  'CALL',
  'COPY',
  'SHUTDOWN',
  'KILL',
];

const READ_ONLY_SQL_PREFIXES = [
  'SELECT',
  'WITH',
  'SHOW',
  'DESCRIBE',
  'DESC',
  'EXPLAIN',
  'PRAGMA',
];

const REDIS_WRITE_COMMANDS = [
  'APPEND',
  'BGREWRITEAOF',
  'BGSAVE',
  'CONFIG',
  'COPY',
  'DECR',
  'DECRBY',
  'DEL',
  'EVAL',
  'EVALSHA',
  'EXPIRE',
  'FLUSHALL',
  'FLUSHDB',
  'HDEL',
  'HSET',
  'INCR',
  'INCRBY',
  'LPUSH',
  'LPOP',
  'MIGRATE',
  'MODULE',
  'MSET',
  'PERSIST',
  'PEXPIRE',
  'PSETEX',
  'RENAMENX',
  'RENAME',
  'RESTORE',
  'RPOP',
  'RPUSH',
  'SADD',
  'SCRIPT',
  'SET',
  'SETEX',
  'SETNX',
  'SREM',
  'ZADD',
  'ZREM',
];

const PROD_PRIMARY_ROLES = new Set(['prod-primary', 'primary', 'writer', 'readwrite']);

function parseBoolean(value: string | undefined, defaultValue: boolean): boolean {
  if (value === undefined) {
    return defaultValue;
  }
  return value.toLowerCase() === 'true';
}

function parseCsv(value: string | undefined): string[] {
  if (!value) {
    return [];
  }
  return value
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function stripSqlComments(query: string): string {
  return query
    .replace(/--.*$/gm, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .trim();
}

function normalizeWhitespace(text: string): string {
  return text.replace(/\s+/g, ' ').trim();
}

function normalizeIdentifier(name: string): string {
  return name
    .trim()
    .replace(/^['"`\[]+/, '')
    .replace(/['"`\]]+$/, '')
    .toLowerCase();
}

function getLastIdentifierSegment(name: string): string {
  const parts = normalizeIdentifier(name).split('.');
  return parts[parts.length - 1] || '';
}

function extractReferencedTables(query: string): string[] {
  const references = new Set<string>();
  const patterns = [
    /\b(?:FROM|JOIN|DESCRIBE|DESC|TABLE)\s+(`[^`]+`|"[^"]+"|\[[^\]]+\]|[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)/gi,
    /\bSHOW\s+(?:FULL\s+)?(?:COLUMNS|FIELDS|INDEX|INDEXES)\s+FROM\s+(`[^`]+`|"[^"]+"|\[[^\]]+\]|[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)/gi,
    /\bPRAGMA\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\(\s*([`"']?[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?[`"']?)\s*\)/gi,
  ];

  for (const pattern of patterns) {
    let match: RegExpExecArray | null = pattern.exec(query);
    while (match) {
      const reference = normalizeIdentifier(match[1]);
      if (reference) {
        references.add(reference);
      }
      match = pattern.exec(query);
    }
  }

  return Array.from(references);
}

function matchesWhitelist(tableName: string, whitelist: Set<string>): boolean {
  const normalized = normalizeIdentifier(tableName);
  const lastSegment = getLastIdentifierSegment(tableName);
  return whitelist.has(normalized) || whitelist.has(lastSegment);
}

export const Config = {
  READ_ONLY_MODE: parseBoolean(process.env.READ_ONLY_MODE, true),
  MAX_ROWS: parseInt(process.env.MAX_ROWS || '1000', 10),
  QUERY_TIMEOUT: parseInt(process.env.QUERY_TIMEOUT || '30000', 10),
  LOG_LEVEL: process.env.LOG_LEVEL || 'INFO',
  TABLE_WHITELIST: parseCsv(process.env.TABLE_WHITELIST).map((item) => normalizeIdentifier(item)),
  ALLOW_PROD_PRIMARY: parseBoolean(process.env.ALLOW_PROD_PRIMARY, false),
  CONNECTION_ROLE: (process.env.CONNECTION_ROLE || 'readonly-replica').toLowerCase(),

  getMysqlConfigs(): Record<string, DatabaseConfig> | null {
    return this.parseMultiConfigs('MYSQL_CONFIGS', 3306);
  },

  getPostgresConfigs(): Record<string, DatabaseConfig> | null {
    return this.parseMultiConfigs('POSTGRES_CONFIGS', 5432);
  },

  getMongodbConfigs(): Record<string, DatabaseConfig> | null {
    const multiConfigs = this.parseJsonConfigs('MONGODB_CONFIGS');
    if (!multiConfigs) {
      return null;
    }

    const result: Record<string, DatabaseConfig> = {};
    for (const [name, url] of Object.entries(multiConfigs)) {
      const config = this.parseMongodbUrl(url as string);
      if (config) {
        result[name] = config;
      }
    }
    return Object.keys(result).length > 0 ? result : null;
  },

  getRedisConfigs(): Record<string, DatabaseConfig> | null {
    const multiConfigs = this.parseJsonConfigs('REDIS_CONFIGS');
    if (!multiConfigs) {
      return null;
    }

    const result: Record<string, DatabaseConfig> = {};
    for (const [name, url] of Object.entries(multiConfigs)) {
      const config = this.parseRedisUrl(url as string);
      if (config) {
        result[name] = config;
      }
    }
    return Object.keys(result).length > 0 ? result : null;
  },

  getOracleConfigs(): Record<string, DatabaseConfig> | null {
    const multiConfigs = this.parseJsonConfigs('ORACLE_CONFIGS');
    if (!multiConfigs) {
      return null;
    }

    const result: Record<string, DatabaseConfig> = {};
    for (const [name, url] of Object.entries(multiConfigs)) {
      const config = this.parseOracleUrl(url as string);
      if (config) {
        result[name] = config;
      }
    }
    return Object.keys(result).length > 0 ? result : null;
  },

  getSqliteConfigs(): Record<string, DatabaseConfig> | null {
    const multiConfigs = this.parseJsonConfigs('SQLITE_CONFIGS');
    if (!multiConfigs) {
      return null;
    }

    const result: Record<string, DatabaseConfig> = {};
    for (const [name, filePath] of Object.entries(multiConfigs)) {
      result[name] = {
        host: 'localhost',
        port: 0,
        database: filePath as string,
      };
    }
    return Object.keys(result).length > 0 ? result : null;
  },

  parseMultiConfigs(
    multiConfigKey: string,
    defaultPort: number,
  ): Record<string, DatabaseConfig> | null {
    const multiConfigs = this.parseJsonConfigs(multiConfigKey);
    if (!multiConfigs) {
      return null;
    }

    const result: Record<string, DatabaseConfig> = {};
    for (const [name, url] of Object.entries(multiConfigs)) {
      const config = this.parseSqlUrl(url as string, defaultPort);
      if (config) {
        result[name] = config;
      }
    }
    return Object.keys(result).length > 0 ? result : null;
  },

  parseJsonConfigs(envKey: string): Record<string, string> | null {
    const jsonStr = process.env[envKey];
    if (!jsonStr) {
      return null;
    }

    try {
      const parsed = JSON.parse(jsonStr);
      if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
        return parsed as Record<string, string>;
      }
      console.error(`${envKey} must be a JSON object`);
      return null;
    } catch {
      console.error(`Failed to parse ${envKey}; expected valid JSON`);
      return null;
    }
  },

  parseMongodbUrl(url: string): DatabaseConfig | null {
    try {
      const parsed = new URL(url);
      return {
        host: parsed.hostname,
        port: parseInt(parsed.port, 10) || 27017,
        user: parsed.username || undefined,
        password: parsed.password || undefined,
        database: parsed.pathname.slice(1).split('?')[0] || 'test',
        connectionString: url,
      };
    } catch {
      return null;
    }
  },

  parseRedisUrl(url: string): DatabaseConfig | null {
    try {
      let remaining = url.replace(/^redis:\/\//, '');
      let password: string | undefined;
      let host = 'localhost';
      let port = 6379;
      let database = '0';

      const atIndex = remaining.lastIndexOf('@');
      if (atIndex !== -1) {
        const authPart = remaining.substring(0, atIndex);
        remaining = remaining.substring(atIndex + 1);

        if (authPart.startsWith(':')) {
          password = authPart.substring(1);
        } else {
          const colonIndex = authPart.indexOf(':');
          if (colonIndex !== -1) {
            password = authPart.substring(colonIndex + 1);
          }
        }
      }

      const slashIndex = remaining.indexOf('/');
      if (slashIndex !== -1) {
        database = remaining.substring(slashIndex + 1) || '0';
        remaining = remaining.substring(0, slashIndex);
      }

      const colonIndex = remaining.lastIndexOf(':');
      if (colonIndex !== -1) {
        host = remaining.substring(0, colonIndex);
        port = parseInt(remaining.substring(colonIndex + 1), 10) || 6379;
      } else if (remaining) {
        host = remaining;
      }

      return {
        host,
        port,
        password: password ? decodeURIComponent(password) : undefined,
        database,
      };
    } catch {
      return null;
    }
  },

  parseOracleUrl(url: string): DatabaseConfig | null {
    const match = url.match(/^oracle:\/\/([^:]+):([^@]+)@([^:]+):(\d+)\/(.+)$/);
    if (!match) {
      return null;
    }
    return {
      host: match[3],
      port: parseInt(match[4], 10),
      user: match[1],
      password: match[2],
      database: match[5],
    };
  },

  parseSqlUrl(url: string, defaultPort: number): DatabaseConfig | null {
    try {
      const parsed = new URL(url);
      return {
        host: parsed.hostname,
        port: parseInt(parsed.port, 10) || defaultPort,
        user: decodeURIComponent(parsed.username) || undefined,
        password: decodeURIComponent(parsed.password) || undefined,
        database: parsed.pathname.slice(1) || undefined,
      };
    } catch {
      return null;
    }
  },

  getTableWhitelist(): Set<string> {
    return new Set(this.TABLE_WHITELIST);
  },

  assertSafeServerConfig(): void {
    if (PROD_PRIMARY_ROLES.has(this.CONNECTION_ROLE) && !this.ALLOW_PROD_PRIMARY) {
      throw new Error(
        'Refusing to start with CONNECTION_ROLE=prod-primary unless ALLOW_PROD_PRIMARY=true',
      );
    }
  },

  validateSqlQuery(query: string): { valid: boolean; error?: string } {
    if (!this.READ_ONLY_MODE) {
      return { valid: true };
    }

    const withoutComments = stripSqlComments(query);
    if (!withoutComments) {
      return { valid: false, error: 'Query must not be empty' };
    }

    const normalized = normalizeWhitespace(withoutComments);
    const upper = normalized.toUpperCase();
    const firstKeyword = upper.match(/^[A-Z]+/)?.[0];

    if (!firstKeyword || !READ_ONLY_SQL_PREFIXES.includes(firstKeyword)) {
      return {
        valid: false,
        error: `Read-only mode only allows queries starting with ${READ_ONLY_SQL_PREFIXES.join(', ')}`,
      };
    }

    const withoutTrailingSemicolon = normalized.replace(/;\s*$/, '');
    if (withoutTrailingSemicolon.includes(';')) {
      return { valid: false, error: 'Read-only mode does not allow multiple SQL statements' };
    }

    if (/\bINTO\s+OUTFILE\b/i.test(upper)) {
      return { valid: false, error: 'Read-only mode forbids INTO OUTFILE' };
    }

    for (const keyword of DANGEROUS_KEYWORDS) {
      const regex = new RegExp(`\\b${keyword}\\b`, 'i');
      if (regex.test(upper)) {
        return { valid: false, error: `Read-only mode forbids ${keyword} statements` };
      }
    }

    const whitelist = this.getTableWhitelist();
    if (whitelist.size > 0) {
      const referencedTables = extractReferencedTables(normalized);
      const disallowedTables = referencedTables.filter((tableName) => !matchesWhitelist(tableName, whitelist));
      if (disallowedTables.length > 0) {
        return {
          valid: false,
          error: `Query references tables outside TABLE_WHITELIST: ${disallowedTables.join(', ')}`,
        };
      }
    }

    return { valid: true };
  },

  validateRedisCommand(command: string): { valid: boolean; error?: string } {
    if (!this.READ_ONLY_MODE) {
      return { valid: true };
    }

    const firstToken = command.trim().split(/\s+/, 1)[0]?.toUpperCase();
    if (firstToken && REDIS_WRITE_COMMANDS.includes(firstToken)) {
      return { valid: false, error: `Read-only mode forbids Redis command ${firstToken}` };
    }

    return { valid: true };
  },

  validateIdentifier(name: string): string {
    if (!name) {
      return name;
    }
    if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name)) {
      throw new Error(`Invalid identifier: ${name}`);
    }
    return name;
  },
};
