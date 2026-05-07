import mysql from 'mysql2/promise';
import { DatabaseAdapter, QueryResult, TableInfo, ColumnInfo } from './base';
import { Config, DatabaseConfig } from '../config';

export class MySQLAdapter extends DatabaseAdapter {
  private connection: mysql.Connection | null = null;
  private config: DatabaseConfig;

  constructor(config: DatabaseConfig) {
    super();
    this.config = config;
  }

  async connect(): Promise<void> {
    if (!this.connection) {
      this.connection = await mysql.createConnection({
        host: this.config.host,
        port: this.config.port,
        user: this.config.user,
        password: this.config.password,
        database: this.config.database,
        connectTimeout: Config.QUERY_TIMEOUT
      });
    }
  }

  async close(): Promise<void> {
    if (this.connection) {
      await this.connection.end();
      this.connection = null;
    }
  }

  async testConnection(): Promise<boolean> {
    try {
      await this.connect();
      await this.connection!.query('SELECT 1');
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

    const [rows] = await this.connection!.query(query, params);
    const result = Array.isArray(rows) ? rows : [rows];
    return result.slice(0, limit) as QueryResult[];
  }

  async getSchemaInfo(): Promise<TableInfo[]> {
    const rows = await this.executeQuery('SHOW TABLES');
    return rows.map(row => {
      const tableName = Object.values(row)[0] as string;
      return { name: tableName };
    });
  }

  async describeTable(tableName: string): Promise<ColumnInfo[]> {
    Config.validateIdentifier(tableName);
    const rows = await this.executeQuery(`DESCRIBE \`${tableName}\``);
    return rows.map(row => ({
      name: row.Field,
      type: row.Type,
      nullable: row.Null === 'YES',
      defaultValue: row.Default,
    }));
  }
}
