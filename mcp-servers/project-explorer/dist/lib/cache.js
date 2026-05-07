#!/usr/bin/env node
"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.DEFAULT_CONFIG = exports.ROOT = void 0;
exports.deepMerge = deepMerge;
exports.loadYamlLike = loadYamlLike;
exports.loadConfig = loadConfig;
exports.resolveRepoPath = resolveRepoPath;
exports.normalizeSnapshotPath = normalizeSnapshotPath;
exports.resolveScanRoots = resolveScanRoots;
exports.resolveDesignRoots = resolveDesignRoots;
exports.cachePath = cachePath;
exports.isValidationPath = isValidationPath;
exports.collectWatchedFiles = collectWatchedFiles;
exports.computeSignature = computeSignature;
exports.loadCacheEntry = loadCacheEntry;
exports.cacheIsValid = cacheIsValid;
exports.saveCacheEntry = saveCacheEntry;
const crypto = __importStar(require("node:crypto"));
const fs = __importStar(require("node:fs"));
const path = __importStar(require("node:path"));
exports.ROOT = path.resolve(__dirname, "..", "..", "..", "..");
exports.DEFAULT_CONFIG = {
    scan_roots: ["src/main/java", "src/test/java"],
    design_roots: ["specs"],
    module_prefix_map: {},
    duplicate_strategy: "disambiguate",
    context_budget: { classes: 60, columns: 80, rules_chars: 8000 },
    cache: { enabled: true, path: ".cache/project-explorer-snapshot.json", ttl_minutes: 30 },
    skip_words: ["GET", "POST", "PUT", "DELETE", "HTTP", "API", "URL", "JSON", "SQL", "DDL", "SDD", "PRD", "MCP", "CI", "PR", "OK"],
};
function deepMerge(base, overlay) {
    const merged = { ...base };
    for (const [key, value] of Object.entries(overlay || {})) {
        if (value &&
            typeof value === "object" &&
            !Array.isArray(value) &&
            merged[key] &&
            typeof merged[key] === "object" &&
            !Array.isArray(merged[key])) {
            merged[key] = deepMerge(merged[key], value);
        }
        else {
            merged[key] = value;
        }
    }
    return merged;
}
function loadYamlLike(configPath) {
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
    }
    catch (jsonError) {
        try {
            // eslint-disable-next-line @typescript-eslint/no-var-requires
            const yaml = require("yaml");
            const parsed = yaml.parse(text);
            return parsed && typeof parsed === "object" ? parsed : {};
        }
        catch {
            throw jsonError;
        }
    }
}
function loadConfig(configPath) {
    const resolvedPath = configPath || path.resolve(__dirname, "..", "..", "config.yaml");
    const loaded = loadYamlLike(resolvedPath);
    return deepMerge(exports.DEFAULT_CONFIG, { ...loaded, config_path: resolvedPath });
}
function resolveRepoPath(inputPath) {
    return path.isAbsolute(inputPath) ? inputPath : path.resolve(exports.ROOT, inputPath);
}
function normalizeSnapshotPath(filePath) {
    const resolved = path.resolve(filePath);
    const relative = path.relative(exports.ROOT, resolved).replace(/\\/g, "/");
    if (relative.startsWith("..")) {
        return resolved.replace(/\\/g, "/");
    }
    return relative;
}
function resolveExistingRoots(values) {
    return (values || []).map((item) => resolveRepoPath(String(item))).filter((item) => fs.existsSync(item));
}
function resolveScanRoots(config) {
    return resolveExistingRoots(config.scan_roots);
}
function resolveDesignRoots(config) {
    return resolveExistingRoots(config.design_roots);
}
function cachePath(config) {
    return resolveRepoPath(config.cache?.path || ".cache/project-explorer-snapshot.json");
}
function isValidationPath(relativePath) {
    return relativePath.split(path.sep).some((part) => part.startsWith("_validation-") || part.startsWith("validation-"));
}
function walkFiles(rootPath, predicate, results) {
    if (!fs.existsSync(rootPath)) {
        return;
    }
    const entries = fs.readdirSync(rootPath, { withFileTypes: true });
    for (const entry of entries) {
        const fullPath = path.join(rootPath, entry.name);
        if (entry.isDirectory()) {
            walkFiles(fullPath, predicate, results);
        }
        else if (predicate(fullPath)) {
            results.push(fullPath);
        }
    }
}
function collectWatchedFiles(config) {
    const files = [];
    for (const rootPath of resolveScanRoots(config)) {
        walkFiles(rootPath, (filePath) => filePath.endsWith(".java") && !isValidationPath(path.relative(exports.ROOT, filePath)), files);
        const normalized = rootPath.replace(/\\/g, "/");
        const companionRoots = new Set();
        if (normalized.includes("/src/main/java")) {
            companionRoots.add(normalized.replace("/src/main/java", "/src/main/resources"));
        }
        if (normalized.includes("/src/test/java")) {
            companionRoots.add(normalized.replace("/src/test/java", "/src/test/resources"));
        }
        for (const companionRoot of companionRoots) {
            walkFiles(companionRoot, (filePath) => filePath.endsWith(".xml") && !isValidationPath(path.relative(exports.ROOT, filePath)), files);
        }
    }
    for (const rootPath of resolveDesignRoots(config)) {
        walkFiles(rootPath, (filePath) => /design-v\d+\.md$/i.test(path.basename(filePath)) && !isValidationPath(path.relative(exports.ROOT, filePath)), files);
    }
    return files.sort();
}
function computeSignature(config, files) {
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
function loadCacheEntry(config) {
    const target = cachePath(config);
    if (!fs.existsSync(target)) {
        return null;
    }
    try {
        return JSON.parse(fs.readFileSync(target, "utf8"));
    }
    catch {
        return null;
    }
}
function cacheIsValid(config, entry, files) {
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
function saveCacheEntry(config, payload, files) {
    const target = cachePath(config);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    const entry = {
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
