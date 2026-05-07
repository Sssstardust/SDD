// @ts-ignore
import oracledb from 'oracledb';
import { DatabaseAdapter, QueryResult, TableInfo, ColumnInfo } from './base';
import { Config, DatabaseConfig } from '../config';

export class OracleAdapter extends DatabaseAdapter {
  private connection: oracledb.Connection | null = null;
  private config: DatabaseConfig;

  constructor(config: DatabaseConfig) {
    super();
    this.config = config;
    // 使用 Thin 模式，不需要调用 initOracleClient()
    // oracledb 6.x 默认使用 Thin 模式，无需 Oracle Client
  }

  async connect(): Promise<void> {
    if (!this.connection) {
      this.connection = await oracledb.getConnection({
        user: this.config.user,
        password: this.config.password,
        connectString: `${this.config.host}:${this.config.port}/${this.config.database}`
      });
    }
  }

  async close(): Promise<void> {
    if (this.connection) {
      await this.connection.close();
      this.connection = null;
    }
  }

  async testConnection(): Promise<boolean> {
    try {
      await this.connect();
      await this.connection!.execute('SELECT 1 FROM DUAL');
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

    // Oracle 使用 ROWNUM 限制行数
    if (!query.toUpperCase().includes('ROWNUM') && 
        !query.toUpperCase().includes('FETCH') && 
        query.trim().toUpperCase().startsWith('SELECT')) {
      query = `SELECT * FROM (${query.replace(/;$/, '')}) WHERE ROWNUM <= ${limit}`;
    }

    const result = await this.connection!.execute(query, params || [], {
      outFormat: oracledb.OUT_FORMAT_OBJECT,
      maxRows: limit
    });

    return (result.rows || []) as QueryResult[];
  }

  async getSchemaInfo(): Promise<TableInfo[]> {
    const rows = await this.executeQuery('SELECT TABLE_NAME FROM USER_TABLES ORDER BY TABLE_NAME');
    return rows.map(row => ({ name: row.TABLE_NAME }));
  }

  async describeTable(tableName: string, schemaName?: string): Promise<ColumnInfo[]> {
    Config.validateIdentifier(tableName);
    
    let query: string;
    if (schemaName) {
      Config.validateIdentifier(schemaName);
      query = `
        SELECT COLUMN_NAME, DATA_TYPE, NULLABLE, DATA_DEFAULT, DATA_LENGTH
        FROM ALL_TAB_COLUMNS
        WHERE TABLE_NAME = '${tableName.toUpperCase()}' AND OWNER = '${schemaName.toUpperCase()}'
        ORDER BY COLUMN_ID
      `;
    } else {
      query = `
        SELECT COLUMN_NAME, DATA_TYPE, NULLABLE, DATA_DEFAULT, DATA_LENGTH
        FROM USER_TAB_COLUMNS
        WHERE TABLE_NAME = '${tableName.toUpperCase()}'
        ORDER BY COLUMN_ID
      `;
    }

    const rows = await this.executeQuery(query);
    return rows.map(row => ({
      name: row.COLUMN_NAME,
      type: row.DATA_TYPE,
      nullable: row.NULLABLE === 'Y',
      defaultValue: row.DATA_DEFAULT,
      length: row.DATA_LENGTH
    }));
  }
}
