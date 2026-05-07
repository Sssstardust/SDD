import { Config, DatabaseConfig } from './config';
import { DatabaseAdapter } from './adapters/base';

// 适配器缓存（单例模式）- 使用复合 key: `${dbType}:${source}`
const adapterCache: Map<string, DatabaseAdapter> = new Map();

export function getAdapter(dbType: string, source?: string): DatabaseAdapter {
  const type = dbType.toLowerCase();
  const connectionName = source || 'default';
  const cacheKey = `${type}:${connectionName}`;

  // 检查缓存
  if (adapterCache.has(cacheKey)) {
    return adapterCache.get(cacheKey)!;
  }

  // 创建新适配器
  const adapter = createAdapter(type, connectionName);
  adapterCache.set(cacheKey, adapter);
  return adapter;
}

function createAdapter(dbType: string, source: string): DatabaseAdapter {
  switch (dbType) {
    case 'mysql': {
      const configs = Config.getMysqlConfigs();
      if (!configs) throw new Error('MYSQL_CONFIGS 环境变量未配置');
      const config = configs[source];
      if (!config) throw new Error(`MySQL 数据源 "${source}" 未配置，可用数据源: ${Object.keys(configs).join(', ')}`);
      const { MySQLAdapter } = require('./adapters/mysql');
      return new MySQLAdapter(config);
    }

    case 'postgres':
    case 'postgresql': {
      const configs = Config.getPostgresConfigs();
      if (!configs) throw new Error('POSTGRES_CONFIGS 环境变量未配置');
      const config = configs[source];
      if (!config) throw new Error(`PostgreSQL 数据源 "${source}" 未配置，可用数据源: ${Object.keys(configs).join(', ')}`);
      const { PostgresAdapter } = require('./adapters/postgres');
      return new PostgresAdapter(config);
    }

    case 'mongodb':
    case 'mongo': {
      const configs = Config.getMongodbConfigs();
      if (!configs) throw new Error('MONGODB_CONFIGS 环境变量未配置');
      const config = configs[source];
      if (!config) throw new Error(`MongoDB 数据源 "${source}" 未配置，可用数据源: ${Object.keys(configs).join(', ')}`);
      const { MongoDBAdapter } = require('./adapters/mongodb');
      return new MongoDBAdapter(config);
    }

    case 'redis': {
      const configs = Config.getRedisConfigs();
      if (!configs) throw new Error('REDIS_CONFIGS 环境变量未配置');
      const config = configs[source];
      if (!config) throw new Error(`Redis 数据源 "${source}" 未配置，可用数据源: ${Object.keys(configs).join(', ')}`);
      const { RedisAdapter } = require('./adapters/redis');
      return new RedisAdapter(config);
    }

    case 'oracle': {
      const configs = Config.getOracleConfigs();
      if (!configs) throw new Error('ORACLE_CONFIGS 环境变量未配置');
      const config = configs[source];
      if (!config) throw new Error(`Oracle 数据源 "${source}" 未配置，可用数据源: ${Object.keys(configs).join(', ')}`);
      const { OracleAdapter } = require('./adapters/oracle');
      return new OracleAdapter(config);
    }

    case 'sqlite': {
      const configs = Config.getSqliteConfigs();
      if (!configs) throw new Error('SQLITE_CONFIGS 环境变量未配置');
      const config = configs[source];
      if (!config) throw new Error(`SQLite 数据源 "${source}" 未配置，可用数据源: ${Object.keys(configs).join(', ')}`);
      const { SQLiteAdapter } = require('./adapters/sqlite');
      return new SQLiteAdapter(config);
    }

    default:
      throw new Error(`不支持的数据库类型: ${dbType}`);
  }
}

export function listConfiguredDatabases(): Record<string, { configured: boolean; sources: string[] }> {
  const mysqlConfigs = Config.getMysqlConfigs();
  const postgresConfigs = Config.getPostgresConfigs();
  const mongodbConfigs = Config.getMongodbConfigs();
  const redisConfigs = Config.getRedisConfigs();
  const oracleConfigs = Config.getOracleConfigs();
  const sqliteConfigs = Config.getSqliteConfigs();

  return {
    mysql: {
      configured: mysqlConfigs !== null,
      sources: mysqlConfigs ? Object.keys(mysqlConfigs) : []
    },
    postgres: {
      configured: postgresConfigs !== null,
      sources: postgresConfigs ? Object.keys(postgresConfigs) : []
    },
    mongodb: {
      configured: mongodbConfigs !== null,
      sources: mongodbConfigs ? Object.keys(mongodbConfigs) : []
    },
    redis: {
      configured: redisConfigs !== null,
      sources: redisConfigs ? Object.keys(redisConfigs) : []
    },
    oracle: {
      configured: oracleConfigs !== null,
      sources: oracleConfigs ? Object.keys(oracleConfigs) : []
    },
    sqlite: {
      configured: sqliteConfigs !== null,
      sources: sqliteConfigs ? Object.keys(sqliteConfigs) : []
    }
  };
}

export async function closeAllAdapters(): Promise<void> {
  for (const adapter of adapterCache.values()) {
    try {
      await adapter.close();
    } catch {
      // ignore
    }
  }
  adapterCache.clear();
}
