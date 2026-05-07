#!/usr/bin/env node

import * as crypto from "node:crypto";
import * as fs from "node:fs";
import * as path from "node:path";

export const ROOT = path.resolve(__dirname, "..", "..", "..", "..");

export type JsonRecord = Record<string, any>;

export type CacheEntry = {
  meta: {
    created_at: string;
    signature: string;
    file_count: number;
  };
  payload: JsonRecord;
};

export type ProjectExplorerConfig = {
  scan_roots: string[];
  design_roots: string[];
  module_prefix_map: Record<string, string>;
  duplicate_strategy: string;
  context_budget: {
    classes: number;
    columns: number;
    rules_chars: number;
  };
  cache: {
    enabled: boolean;
    path: string;
    ttl_minutes: number;
  };
  skip_words: string[];
  config_path?: string;
};

export const DEFAULT_CONFIG: ProjectExplorerConfig = {
  scan_roots: ["src/main/java", "src/test/java"],
  design_roots: ["specs"],
  module_prefix_map: {},
  duplicate_strategy: "disambiguate",
  context_budget: { classes: 60, columns: 80, rules_chars: 8000 },
  cache: { enabled: true, path: ".cache/project-explorer-snapshot.json", ttl_minutes: 30 },
  skip_words: ["GET", "POST", "PUT", "DELETE", "HTTP", "API", "URL", "JSON", "SQL", "DDL", "SDD", "PRD", "MCP", "CI", "PR", "OK"],
};

export function deepMerge<T extends JsonRecord>(base: T, overlay: JsonRecord): T {
  const merged: JsonRecord = { ...base };
  for (const [key, value] of Object.entries(overlay || {})) {
    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      merged[key] &&
      typeof merged[key] === "object" &&
      !Array.isArray(merged[key])
    ) {
      merged[key] = deepMerge(merged[key], value as JsonRecord);
    } else {
      merged[key] = value;
    }
  }
  return merged as T;
}

export function loadYamlLike(configPath: string): JsonRecord {
  if (!fs.existsSync(configPath)) {
    return {};
  }
  const text = fs.readFileSync(configPath, "utf8").trim();
  if (!text) {
    return {};
  }
  try {
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (jsonError) {
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const yaml = require("yaml");
      const parsed = yaml.parse(text);
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch {
      throw jsonError;
    }
  }
}

export function loadConfig(configPath?: string): ProjectExplorerConfig {
  const resolvedPath = configPath || path.resolve(__dirname, "..", "..", "config.yaml");
  const loaded = loadYamlLike(resolvedPath);
  return deepMerge(DEFAULT_CONFIG, { ...loaded, config_path: resolvedPath });
}

export function resolveRepoPath(inputPath: string): string {
  return path.isAbsolute(inputPath) ? inputPath : path.resolve(ROOT, inputPath);
}

export function normalizeSnapshotPath(filePath: string): string {
  const resolved = path.resolve(filePath);
  const relative = path.relative(ROOT, resolved).replace(/\\/g, "/");
  if (relative.startsWith("..")) {
    return resolved.replace(/\\/g, "/");
  }
  return relative;
}

function resolveExistingRoots(values: string[] | undefined): string[] {
  return (values || []).map((item) => resolveRepoPath(String(item))).filter((item) => fs.existsSync(item));
}

export function resolveScanRoots(config: ProjectExplorerConfig): string[] {
  return resolveExistingRoots(config.scan_roots);
}

export function resolveDesignRoots(config: ProjectExplorerConfig): string[] {
  return resolveExistingRoots(config.design_roots);
}

export function cachePath(config: ProjectExplorerConfig): string {
  return resolveRepoPath(config.cache?.path || ".cache/project-explorer-snapshot.json");
}

export function isValidationPath(relativePath: string): boolean {
  return relativePath.split(path.sep).some((part) => part.startsWith("_validation-") || part.startsWith("validation-"));
}

function walkFiles(rootPath: string, predicate: (filePath: string) => boolean, results: string[]): void {
  if (!fs.existsSync(rootPath)) {
    return;
  }
  const entries = fs.readdirSync(rootPath, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(rootPath, entry.name);
    if (entry.isDirectory()) {
      walkFiles(fullPath, predicate, results);
    } else if (predicate(fullPath)) {
      results.push(fullPath);
    }
  }
}

export function collectWatchedFiles(config: ProjectExplorerConfig): string[] {
  const files: string[] = [];
  for (const rootPath of resolveScanRoots(config)) {
    walkFiles(rootPath, (filePath) => filePath.endsWith(".java") && !isValidationPath(path.relative(ROOT, filePath)), files);
    const normalized = rootPath.replace(/\\/g, "/");
    const companionRoots = new Set<string>();
    if (normalized.includes("/src/main/java")) {
      companionRoots.add(normalized.replace("/src/main/java", "/src/main/resources"));
    }
    if (normalized.includes("/src/test/java")) {
      companionRoots.add(normalized.replace("/src/test/java", "/src/test/resources"));
    }
    for (const companionRoot of companionRoots) {
      walkFiles(
        companionRoot,
        (filePath) => filePath.endsWith(".xml") && !isValidationPath(path.relative(ROOT, filePath)),
        files,
      );
    }
  }
  for (const rootPath of resolveDesignRoots(config)) {
    walkFiles(rootPath, (filePath) => /design-v\d+\.md$/i.test(path.basename(filePath)) && !isValidationPath(path.relative(ROOT, filePath)), files);
  }
  return files.sort();
}

export function computeSignature(config: ProjectExplorerConfig, files: string[]): string {
  const payload = {
    scan_roots: resolveScanRoots(config).map((item) => normalizeSnapshotPath(item)),
    design_roots: resolveDesignRoots(config).map((item) => normalizeSnapshotPath(item)),
    module_prefix_map: config.module_prefix_map || {},
    duplicate_strategy: config.duplicate_strategy || "disambiguate",
    files: files.map((filePath) => {
      const stat = fs.statSync(filePath);
      return {
        path: normalizeSnapshotPath(filePath),
        mtime_ms: stat.mtimeMs,
        size: stat.size,
      };
    }),
  };
  return crypto.createHash("sha256").update(JSON.stringify(payload)).digest("hex");
}

export function loadCacheEntry(config: ProjectExplorerConfig): CacheEntry | null {
  const target = cachePath(config);
  if (!fs.existsSync(target)) {
    return null;
  }
  try {
    return JSON.parse(fs.readFileSync(target, "utf8")) as CacheEntry;
  } catch {
    return null;
  }
}

export function cacheIsValid(config: ProjectExplorerConfig, entry: CacheEntry | null, files: string[]): boolean {
  if (!entry || !config.cache?.enabled) {
    return false;
  }
  const meta = entry.meta;
  if (!meta || typeof meta !== "object") {
    return false;
  }
  const ttlMinutes = Number(config.cache.ttl_minutes || 30);
  if (ttlMinutes > 0 && typeof meta.created_at === "string") {
    const createdAt = new Date(meta.created_at);
    if (Number.isNaN(createdAt.getTime())) {
      return false;
    }
    if (Date.now() - createdAt.getTime() > ttlMinutes * 60 * 1000) {
      return false;
    }
  }
  return meta.signature === computeSignature(config, files);
}

export function saveCacheEntry(config: ProjectExplorerConfig, payload: JsonRecord, files: string[]): string {
  const target = cachePath(config);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  const entry: CacheEntry = {
    meta: {
      created_at: new Date().toISOString(),
      signature: computeSignature(config, files),
      file_count: files.length,
    },
    payload,
  };
  fs.writeFileSync(target, JSON.stringify(entry, null, 2), "utf8");
  return target;
}
