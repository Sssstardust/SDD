export interface QueryResult {
  [key: string]: any;
}

export interface TableInfo {
  name: string;
  type?: string;
}

export interface ColumnInfo {
  name: string;
  type: string;
  nullable?: boolean;
  defaultValue?: any;
  length?: number;
}

export abstract class DatabaseAdapter {
  abstract connect(): Promise<void>;
  abstract close(): Promise<void>;
  abstract testConnection(): Promise<boolean>;
  abstract executeQuery(query: string, params?: any[], limit?: number): Promise<QueryResult[]>;
  abstract getSchemaInfo(): Promise<TableInfo[]>;
  abstract describeTable(tableName: string, schemaName?: string): Promise<ColumnInfo[]>;
}
