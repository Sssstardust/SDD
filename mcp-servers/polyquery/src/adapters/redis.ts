import Redis from 'ioredis';
import { DatabaseAdapter, QueryResult, TableInfo, ColumnInfo } from './base';
import { Config, DatabaseConfig } from '../config';

export class RedisAdapter extends DatabaseAdapter {
  private client: Redis | null = null;
  private config: DatabaseConfig;

  constructor(config: DatabaseConfig) {
    super();
    this.config = config;
  }

  async connect(): Promise<void> {
    if (!this.client) {
      this.client = new Redis({
        host: this.config.host,
        port: this.config.port,
        password: this.config.password || undefined,
        db: parseInt(this.config.database || '0'),
        connectTimeout: Config.QUERY_TIMEOUT,
        lazyConnect: true
      });
      await this.client.connect();
    }
  }

  async close(): Promise<void> {
    if (this.client) {
      await this.client.quit();
      this.client = null;
    }
  }

  async testConnection(): Promise<boolean> {
    try {
      await this.connect();
      await this.client!.ping();
      return true;
    } catch {
      return false;
    }
  }

  async executeQuery(query: string, _params?: any[], limit: number = Config.MAX_ROWS): Promise<QueryResult[]> {
    await this.connect();

    // 解析命令: "COMMAND arg1 arg2 ..."
    const parts = query.trim().split(/\s+/);
    const command = parts[0].toUpperCase();
    const args = parts.slice(1);

    // 安全验证
    const validation = Config.validateRedisCommand(command);
    if (!validation.valid) {
      throw new Error(validation.error);
    }

    // 执行命令
    const result = await (this.client as any).call(command, ...args);
    
    return this.formatResult(command, result, limit);
  }

  private formatResult(command: string, result: any, limit: number): QueryResult[] {
    if (result === null || result === undefined) {
      return [{ value: null }];
    }

    if (typeof result === 'string' || typeof result === 'number') {
      return [{ value: result }];
    }

    if (Buffer.isBuffer(result)) {
      try {
        return [{ value: result.toString('utf-8') }];
      } catch {
        return [{ value: `<binary:${result.toString('hex').slice(0, 32)}...>` }];
      }
    }

    if (Array.isArray(result)) {
      return result.slice(0, limit).map((item, index) => ({
        index,
        value: Buffer.isBuffer(item) ? this.safeDecodeBuffer(item) : item
      }));
    }

    if (typeof result === 'object') {
      return Object.entries(result).slice(0, limit).map(([key, value]) => ({
        key,
        value: Buffer.isBuffer(value) ? this.safeDecodeBuffer(value) : value
      }));
    }

    return [{ value: String(result) }];
  }

  private safeDecodeBuffer(buf: Buffer): string {
    try {
      return buf.toString('utf-8');
    } catch {
      return `<binary:${buf.toString('hex').slice(0, 32)}...>`;
    }
  }

  async getSchemaInfo(): Promise<TableInfo[]> {
    await this.connect();
    const info = await this.client!.info('keyspace');
    const dbSize = await this.client!.dbsize();
    
    return [{
      name: `db${this.config.database || 0}`,
      type: `${dbSize} keys`
    }];
  }

  async describeTable(keyName: string): Promise<ColumnInfo[]> {
    await this.connect();
    
    const keyType = await this.client!.type(keyName);
    const ttl = await this.client!.ttl(keyName);

    const result: ColumnInfo[] = [
      { name: 'key', type: keyName },
      { name: 'type', type: keyType },
      { name: 'ttl', type: ttl >= 0 ? `${ttl}s` : 'no expiry' }
    ];

    // 根据类型获取部分内容
    if (keyType === 'string') {
      const value = await this.client!.get(keyName);
      result.push({ name: 'value', type: value || '' });
    } else if (keyType === 'list') {
      const len = await this.client!.llen(keyName);
      result.push({ name: 'length', type: String(len) });
    } else if (keyType === 'hash') {
      const len = await this.client!.hlen(keyName);
      result.push({ name: 'fields', type: String(len) });
    } else if (keyType === 'set') {
      const len = await this.client!.scard(keyName);
      result.push({ name: 'members', type: String(len) });
    } else if (keyType === 'zset') {
      const len = await this.client!.zcard(keyName);
      result.push({ name: 'members', type: String(len) });
    }

    return result;
  }
}
