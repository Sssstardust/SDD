#!/usr/bin/env node

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

export type LanguageProfile = {
  language: string;
  scanRoots: string[];
  sourceExtensions: string[];
  entityPatterns: RegExp[];
  methodPatterns: RegExp[];
};

export type ScanOptions = {
  projectRoot?: string;
  scanRoots?: string[];
  language?: string;
  keywords?: string[];
  limit?: number;
  forceRefresh?: boolean;
  outputPath?: string;
};

export type ScannedClass = {
  simple_name: string;
  name: string;
  kind: string;
  language: string;
  path: string;
  package: string;
  methods: string[];
  component_ids: string[];
};

export type ModuleMap = {
  scanner: string;
  generated_at: string;
  confidence: string;
  evidence_level: string;
  source_signature: string;
  scan_settings: Record<string, unknown>;
  classes: ScannedClass[];
  component_ids: string[];
};

const LANGUAGE_ALIASES: Record<string, string> = {
  py: "python",
  py3: "python",
  ts: "typescript",
  tsx: "typescript",
  node: "typescript",
  js: "javascript",
  jsx: "javascript",
  jvm: "java",
};

const PROFILES: Record<string, LanguageProfile> = {
  java: {
    language: "java",
    scanRoots: ["src/main/java", "src/test/java"],
    sourceExtensions: [".java"],
    entityPatterns: [
      /\b(public|protected|private)?\s*(abstract\s+|final\s+)?(class|interface|enum|record)\s+([A-Za-z_][A-Za-z0-9_]*)/g,
    ],
    methodPatterns: [
      /\b(public|protected|private)\s+(static\s+)?[A-Za-z0-9_<>\[\], ?]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(/g,
    ],
  },
  python: {
    language: "python",
    scanRoots: ["src", "."],
    sourceExtensions: [".py"],
    entityPatterns: [/^\s*(class|def)\s+([A-Za-z_][A-Za-z0-9_]*)/gm],
    methodPatterns: [/^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(/gm],
  },
  typescript: {
    language: "typescript",
    scanRoots: ["src"],
    sourceExtensions: [".ts", ".tsx"],
    entityPatterns: [/\b(export\s+)?(class|interface|enum|function|type)\s+([A-Za-z_][A-Za-z0-9_]*)/g],
    methodPatterns: [/\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*[:{]/g],
  },
  javascript: {
    language: "javascript",
    scanRoots: ["src"],
    sourceExtensions: [".js", ".jsx", ".mjs", ".cjs"],
    entityPatterns: [/\b(export\s+)?(class|function)\s+([A-Za-z_][A-Za-z0-9_]*)/g],
    methodPatterns: [/\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*[{]/g],
  },
  go: {
    language: "go",
    scanRoots: ["."],
    sourceExtensions: [".go"],
    entityPatterns: [/\b(type)\s+([A-Za-z_][A-Za-z0-9_]*)\s+(struct|interface)\b/g, /\bfunc\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(/g],
    methodPatterns: [/\bfunc\s+(\([^)]+\)\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(/g],
  },
};

function normalizeLanguage(value: unknown): string {
  const raw = String(value || "java").trim().toLowerCase();
  return LANGUAGE_ALIASES[raw] || raw;
}

function profileFor(language: unknown): LanguageProfile {
  return PROFILES[normalizeLanguage(language)] || {
    language: "generic",
    scanRoots: ["."],
    sourceExtensions: [],
    entityPatterns: [],
    methodPatterns: [],
  };
}

function readJson(filePath: string): any {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return undefined;
  }
}

function attachmentConfig(repoRoot: string): any {
  const attachment = readJson(path.join(repoRoot, ".spec", "attached-project.json"));
  if (!attachment || typeof attachment !== "object") {
    return {};
  }
  const activeProfile = attachment.active_profile;
  if (Array.isArray(attachment.profiles) && activeProfile) {
    const matched = attachment.profiles.find((item: any) => item && item.profile === activeProfile);
    if (matched) {
      return matched;
    }
  }
  return attachment;
}

function resolveScanRoots(repoRoot: string, options: ScanOptions, profile: LanguageProfile): string[] {
  if (Array.isArray(options.scanRoots) && options.scanRoots.length) {
    return options.scanRoots.map((item) => path.resolve(repoRoot, item));
  }
  const attachment = attachmentConfig(repoRoot);
  if (Array.isArray(attachment.scan_roots) && attachment.scan_roots.length) {
    return attachment.scan_roots.map((item: string) => path.resolve(repoRoot, item));
  }
  const projectRoot = String(options.projectRoot || attachment.project_root || repoRoot);
  return profile.scanRoots.map((item) => path.resolve(projectRoot, item));
}

function walkFiles(root: string, extensions: string[]): string[] {
  if (!fs.existsSync(root)) {
    return [];
  }
  const result: string[] = [];
  const stack = [root];
  while (stack.length) {
    const current = stack.pop() as string;
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(current, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      if (entry.name === "node_modules" || entry.name === ".git" || entry.name === "dist") {
        continue;
      }
      const fullPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(fullPath);
      } else if (!extensions.length || extensions.includes(path.extname(entry.name).toLowerCase())) {
        result.push(fullPath);
      }
    }
  }
  return result;
}

function packageName(language: string, text: string, filePath: string): string {
  if (language === "java") {
    return (text.match(/^\s*package\s+([A-Za-z0-9_.]+)\s*;/m) || [])[1] || "";
  }
  if (language === "go") {
    return (text.match(/^\s*package\s+([A-Za-z0-9_]+)/m) || [])[1] || "";
  }
  if (language === "python" || language === "typescript" || language === "javascript") {
    return path.basename(filePath, path.extname(filePath));
  }
  return "";
}

function extractMethods(profile: LanguageProfile, text: string): string[] {
  const methods = new Set<string>();
  for (const pattern of profile.methodPatterns) {
    pattern.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(text)) !== null) {
      const value = match[3] || match[2] || match[1];
      if (value && !["if", "for", "while", "switch", "catch"].includes(value)) {
        methods.add(value);
      }
    }
  }
  return [...methods].sort();
}

function normalizeEntityMatch(profile: LanguageProfile, match: RegExpExecArray): { kind: string; simpleName: string } {
  if (profile.language === "java") {
    return { kind: match[3] || "entity", simpleName: match[4] || "" };
  }
  if (profile.language === "python") {
    return { kind: match[1] || "entity", simpleName: match[2] || "" };
  }
  if (profile.language === "typescript" || profile.language === "javascript") {
    return { kind: match[2] || "entity", simpleName: match[3] || "" };
  }
  if (profile.language === "go") {
    if (match[1] === "type") {
      return { kind: match[3] || "type", simpleName: match[2] || "" };
    }
    return { kind: "function", simpleName: match[2] || match[1] || "" };
  }
  const groups = match.slice(1).filter(Boolean);
  return { kind: "entity", simpleName: groups[groups.length - 1] || "" };
}

function extractEntities(profile: LanguageProfile, filePath: string): ScannedClass[] {
  const text = fs.readFileSync(filePath, "utf8");
  const pkg = packageName(profile.language, text, filePath);
  const methods = extractMethods(profile, text);
  const classes: ScannedClass[] = [];
  for (const pattern of profile.entityPatterns) {
    pattern.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(text)) !== null) {
      const { kind, simpleName } = normalizeEntityMatch(profile, match);
      if (!simpleName || ["class", "interface", "enum", "function", "type", "struct"].includes(simpleName)) {
        continue;
      }
      classes.push({
        simple_name: simpleName,
        name: pkg ? `${pkg}.${simpleName}` : simpleName,
        kind,
        language: profile.language,
        path: filePath,
        package: pkg,
        methods,
        component_ids: [],
      });
    }
  }
  if (!classes.length && profile.language !== "java") {
    const simpleName = path.basename(filePath, path.extname(filePath));
    classes.push({
      simple_name: simpleName,
      name: pkg ? `${pkg}.${simpleName}` : simpleName,
      kind: "module",
      language: profile.language,
      path: filePath,
      package: pkg,
      methods,
      component_ids: [],
    });
  }
  return classes;
}

function matchesKeywords(item: ScannedClass, keywords: string[]): boolean {
  if (!keywords.length) {
    return true;
  }
  const haystack = `${item.simple_name} ${item.name} ${item.path} ${item.methods.join(" ")}`.toLowerCase();
  return keywords.some((keyword) => haystack.includes(keyword.toLowerCase()));
}

export function scanModules(options: ScanOptions = {}, repoRoot = process.cwd()): ModuleMap {
  const attachment = attachmentConfig(repoRoot);
  const language = options.language || attachment.language || "java";
  const profile = profileFor(language);
  const scanRoots = resolveScanRoots(repoRoot, options, profile);
  const classes = scanRoots.flatMap((root) => walkFiles(root, profile.sourceExtensions).flatMap((file) => extractEntities(profile, file)));
  const keywords = Array.isArray(options.keywords) ? options.keywords.map(String) : [];
  const filtered = classes.filter((item) => matchesKeywords(item, keywords));
  const limited = typeof options.limit === "number" && options.limit > 0 ? filtered.slice(0, options.limit) : filtered;
  const scanSettings = {
    language: profile.language,
    scan_roots: scanRoots,
    source_extensions: profile.sourceExtensions,
    keywords,
  };
  return {
    scanner: "project-explorer",
    generated_at: new Date().toISOString(),
    confidence: limited.length ? "medium" : "low",
    evidence_level: limited.length ? "source-scan" : "empty-scan",
    source_signature: crypto.createHash("sha256").update(JSON.stringify(scanSettings)).digest("hex"),
    scan_settings: scanSettings,
    classes: limited,
    component_ids: [],
  };
}

export function verifyClassExists(classNames: string[], options: ScanOptions = {}, repoRoot = process.cwd()): Record<string, boolean> {
  const moduleMap = scanModules({ ...options, limit: undefined }, repoRoot);
  const names = new Set(moduleMap.classes.flatMap((item) => [item.simple_name, item.name]));
  return Object.fromEntries(classNames.map((name) => [name, names.has(name)]));
}

export function getClassDetail(className: string, options: ScanOptions = {}, repoRoot = process.cwd()): ScannedClass | null {
  const moduleMap = scanModules({ ...options, limit: undefined }, repoRoot);
  return moduleMap.classes.find((item) => item.simple_name === className || item.name === className) || null;
}

export function writeModuleMap(options: ScanOptions = {}, repoRoot = process.cwd()): { output_path: string; module_map: ModuleMap } {
  const moduleMap = scanModules({ ...options, limit: undefined }, repoRoot);
  const outputPath = path.resolve(repoRoot, options.outputPath || ".spec/baseline/module-map.json");
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, `${JSON.stringify(moduleMap, null, 2)}\n`, "utf8");
  return { output_path: outputPath, module_map: moduleMap };
}
