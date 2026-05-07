import Database from 'better-sqlite3';
import { DatabaseAdapter, QueryResult, TableInfo, ColumnInfo } from './base';
import { Config, DatabaseConfig } from '../config';

export class SQLiteAdapter extends DatabaseAdapter {
  private db: Database.Database | null = null;
  private config: DatabaseConfig;

  constructor(config: DatabaseConfig) {
    super();
    this.config = config;
  }

  async connect(): Promise<void> {
    if (!this.db) {
      // database 字段存储文件路径
      this.db = new Database(this.config.database!, {
        readonly: Config.READ_ONLY_MODE,
        timeout: Config.QUERY_TIMEOUT
      });
    }
  }

  async close(): Promise<void> {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }

  async testConnection(): Promise<boolean> {
    try {
      await this.connect();
      this.db!.prepare('SELECT 1').get();
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

    const stmt = this.db!.prepare(query);
    const rows = params ? stmt.all(...params) : stmt.all();
    return rows.slice(0, limit) as QueryResult[];
  }

  async getSchemaInfo(): Promise<TableInfo[]> {
    await this.connect();
    const rows = this.db!.prepare(`
      SELECT name, type FROM sqlite_master 
      WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
      ORDER BY name
    `).all() as any[];
    
    return rows.map(row => ({
      name: row.name,
      type: row.type
    }));
  }

  async describeTable(tableName: string): Promise<ColumnInfo[]> {
    Config.validateIdentifier(tableName);
    await this.connect();
    
    const rows = this.db!.prepare(`PRAGMA table_info("${tableName}")`).all() as any[];
    
    return rows.map(row => ({
      name: row.name,
      type: row.type,
      nullable: row.notnull === 0,
      defaultValue: row.dflt_value
    }));
  }
}
