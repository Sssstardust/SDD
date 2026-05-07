import { Pool, PoolClient } from 'pg';
import { DatabaseAdapter, QueryResult, TableInfo, ColumnInfo } from './base';
import { Config, DatabaseConfig } from '../config';

export class PostgresAdapter extends DatabaseAdapter {
  private pool: Pool | null = null;
  private config: DatabaseConfig;

  constructor(config: DatabaseConfig) {
    super();
    this.config = config;
  }

  async connect(): Promise<void> {
    if (!this.pool) {
      this.pool = new Pool({
        host: this.config.host,
        port: this.config.port,
        user: this.config.user,
        password: this.config.password,
        database: this.config.database,
        connectionTimeoutMillis: Config.QUERY_TIMEOUT,
        max: 10
      });
    }
  }

  async close(): Promise<void> {
    if (this.pool) {
      await this.pool.end();
      this.pool = null;
    }
  }

  async testConnection(): Promise<boolean> {
    try {
      await this.connect();
      const client = await this.pool!.connect();
      await client.query('SELECT 1');
      client.release();
      return true;
    } catch {
      return false;
    }
  }

  async executeQuery(query: string, params?: any[], limit: number = Config.MAX_ROWS): Promise<QueryResult[]> {
    const validation = Config.validateSqlQuery(query);
    if (!validation.valid) {
      throw new Error(validation.error);
    }

    await this.connect();

    // 自动添加 LIMIT
    if (!query.toUpperCase().includes('LIMIT') && query.trim().toUpperCase().startsWith('SELECT')) {
      query = `${query.replace(/;$/, '')} LIMIT ${limit}`;
    }

    const result = await this.pool!.query(query, params);
    return result.rows.slice(0, limit);
  }

  async getSchemaInfo(): Promise<TableInfo[]> {
    const rows = await this.executeQuery(`
      SELECT table_name, table_type
      FROM information_schema.tables
      WHERE table_schema = 'public'
      ORDER BY table_name
    `);
    return rows.map(row => ({
      name: row.table_name,
      type: row.table_type
    }));
  }

  async describeTable(tableName: string, schemaName: string = 'public'): Promise<ColumnInfo[]> {
    Config.validateIdentifier(tableName);
    Config.validateIdentifier(schemaName);
    
    const rows = await this.executeQuery(`
      SELECT column_name, data_type, is_nullable, column_default, character_maximum_length
      FROM information_schema.columns
      WHERE table_schema = '${schemaName}' AND table_name = '${tableName}'
      ORDER BY ordinal_position
    `);
    
    return rows.map(row => ({
      name: row.column_name,
      type: row.data_type,
      nullable: row.is_nullable === 'YES',
      defaultValue: row.column_default,
      length: row.character_maximum_length
    }));
  }
}
