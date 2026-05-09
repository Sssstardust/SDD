#!/usr/bin/env node

import * as fs from "node:fs";
import * as path from "node:path";
import {
  ROOT,
  JsonRecord,
  ProjectExplorerConfig,
  cacheIsValid,
  collectWatchedFiles,
  loadCacheEntry,
  loadConfig,
  resolveDesignRoots,
  normalizeSnapshotPath,
  resolveScanRoots,
  saveCacheEntry,
} from "./cache";

export type ProjectExplorerClass = {
  class_name: string;
  simple_name: string;
  fqn: string | null;
  package: string | null;
  module: string | null;
  type: string;
  source_file: string;
  source_kind: string;
  public_methods: string[];
  method_details?: ProjectExplorerMethod[];
  declared_public_methods?: string[];
  inherited_public_methods?: string[];
  fields: string[];
  field_details?: ProjectExplorerField[];
  annotations: string[];
  extends: string[];
  implements: string[];
  endpoints: ProjectExplorerEndpoint[];
  dependencies: string[];
  jpa_entity?: ProjectExplorerJpaEntity;
  mybatis_mapper?: ProjectExplorerMyBatisMapper;
  scan_reliability?: ProjectExplorerClassReliability;
  source_files: string[];
  display_name?: string;
};

export type ProjectExplorerClassReliability = {
  class_confidence: string;
  method_confidence: string;
  evidence_sources: string[];
  inferred_methods: number;
  inherited_methods: number;
  mybatis_bound_methods: number;
  jpa_entity: boolean;
  warnings: string[];
};

export type ProjectExplorerMethod = {
  name: string;
  signature: string;
  parameter_types: string[];
  return_type: string | null;
  annotations: string[];
  inferred?: boolean;
  inference_source?: string | null;
  confidence?: string | null;
  owner_class?: string | null;
  inherited_from?: string | null;
  mybatis_statement?: {
    id: string;
    kind: string;
    parameter_type: string | null;
    result_type: string | null;
    result_map: string | null;
    result_map_type?: string | null;
    mapped_columns?: string[];
    mapped_properties?: string[];
    tables: string[];
  } | null;
};

export type ProjectExplorerField = {
  name: string;
  type: string | null;
  annotations: string[];
};

export type ProjectExplorerEndpoint = {
  path: string;
  method: string;
  operation_id: string;
  method_name: string;
};

export type ProjectExplorerJpaEntity = {
  entity_kind?: "entity" | "mapped-superclass";
  table_name: string | null;
  candidate_table_names?: string[];
  id_fields: string[];
  column_mappings: Array<{
    field_name: string;
    field_type: string | null;
    column_name: string | null;
    candidate_column_names?: string[];
    annotations: string[];
  }>;
  relation_fields: string[];
};

export type ProjectExplorerMyBatisMapper = {
  namespace: string;
  xml_files: string[];
  statement_ids: string[];
  result_maps: Array<{
    id: string;
    type: string | null;
    mapped_columns: string[];
    mapped_properties: string[];
  }>;
  statements: Array<{
    id: string;
    kind: string;
    parameter_type: string | null;
    result_type: string | null;
    result_map: string | null;
    tables: string[];
  }>;
};

export type SnapshotPayload = {
  generated_at: string;
  scanner: string;
  evidence_level: string;
  confidence: string;
  unsupported_features: string[];
  scan_quality: Record<string, unknown>;
  source_stats: Record<string, number>;
  duplicate_strategy: string;
  scan_roots: string[];
  design_roots: string[];
  classes: ProjectExplorerClass[];
};

const CLASS_LINE_PATTERN = /^\s*(?:(?:public|protected|private|abstract|final|static|sealed|non-sealed|strictfp)\s+)*(class|interface|enum|record)\s+([A-Z][A-Za-z0-9_]*)\b(.*)$/;
const PACKAGE_PATTERN = /^\s*package\s+([a-zA-Z0-9_.]+)\s*;/m;
const IMPORT_PATTERN = /^\s*import\s+([a-zA-Z0-9_.]+)\s*;/gm;
const PUBLIC_METHOD_PATTERN = /^\s*public\s+(?:static\s+)?(?:final\s+)?(?:<[^>]+>\s+)?(?:[\w.$<>\[\], ?@]+\s+)?([a-zA-Z_][A-Za-z0-9_]*)\s*\(([^)]*)\)/gm;
const PUBLIC_METHOD_LINE_PATTERN = /^\s*public\s+(?:static\s+)?(?:final\s+)?(?:<[^>]+>\s+)?(?:[\w.$<>\[\], ?@]+\s+)?([a-zA-Z_][A-Za-z0-9_]*)\s*\(([^)]*)\)/;
const INTERFACE_METHOD_LINE_PATTERN =
  /^\s*(?:(?:public|private|protected|static|default|abstract|final|synchronized|strictfp)\s+)*(?:<[^>]+>\s+)?(?:[\w.$<>\[\], ?@]+\s+)?([a-zA-Z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*(?:throws\s+[\w.$<>\[\], ?]+\s*)?(?:;|\{)/;
const FIELD_PATTERN = /^\s*(?:public|protected|private)\s+(?:static\s+)?(?:final\s+)?(?:volatile\s+)?(?:transient\s+)?[\w.$<>\[\], ?]+\s+([a-zA-Z_][A-Za-z0-9_]*)\s*(?:=|;)/gm;
const FIELD_LINE_PATTERN = /^\s*(?:public|protected|private)\s+(?:static\s+)?(?:final\s+)?(?:volatile\s+)?(?:transient\s+)?[\w.$<>\[\], ?]+\s+([a-zA-Z_][A-Za-z0-9_]*)\s*(?:=|;)/;
const PARTICIPANT_PATTERN = /^\s*participant\s+\w+\s+as\s+([A-Z][A-Za-z0-9_]*)\s*$/gm;
const PARTICIPANT_ALIAS_PATTERN = /^\s*participant\s+(\w+)\s+as\s+([A-Z][A-Za-z0-9_]*)\s*$/;
const SEQUENCE_CALL_PATTERN = /^\s*(\w+)\s*->>\s*(\w+)\s*:\s*(.+?)\s*$/;
const MAPPER_NAMESPACE_PATTERN = /<mapper\b[^>]*\bnamespace\s*=\s*["']([^"']+)["'][^>]*>/i;
const MAPPER_RESULT_MAP_PATTERN = /<resultMap\b([^>]*)\bid\s*=\s*["']([^"']+)["']([^>]*)>([\s\S]*?)<\/resultMap>/gi;
const MAPPER_RESULT_MAPPING_ENTRY_PATTERN = /<(id|result|association|collection)\b([^>]*)\/?>/gi;
const MAPPER_STATEMENT_PATTERN = /<(select|insert|update|delete)\b([^>]*)\bid\s*=\s*["']([^"']+)["']([^>]*)>([\s\S]*?)<\/\1>/gi;

const SOURCE_PRIORITY: Record<string, number> = {
  "java-main": 4,
  "java-test": 3,
  design: 1,
};

function classifyJavaSource(filePath: string): string | null {
  const normalized = filePath.replace(/\\/g, "/");
  if (normalized.includes("/src/main/java/")) {
    return "java-main";
  }
  if (normalized.includes("/src/test/java/generated/design/")) {
    return null;
  }
  if (normalized.includes("/src/test/java/")) {
    return "java-test";
  }
  return null;
}

function moduleFromPackage(packageName: string | null, modulePrefixMap: Record<string, string>): string | null {
  if (!packageName) {
    return null;
  }
  let matchedPrefix: string | null = null;
  let matchedModule: string | null = null;
  for (const [prefix, moduleName] of Object.entries(modulePrefixMap || {})) {
    if (packageName.startsWith(prefix) && (matchedPrefix === null || prefix.length > matchedPrefix.length)) {
      matchedPrefix = prefix;
      matchedModule = String(moduleName);
    }
  }
  return matchedModule;
}

function moduleFromPath(filePath: string): string | null {
  const normalized = filePath.replace(/\\/g, "/");
  if (normalized.includes("/src/main/java/") || normalized.includes("/src/test/java/")) {
    const sourceMarkerIndex = normalized.lastIndexOf("/src/");
    if (sourceMarkerIndex > 0) {
      return path.basename(normalized.slice(0, sourceMarkerIndex));
    }
  }
  const relativePath = path.relative(ROOT, filePath);
  const parts = relativePath.split(path.sep);
  if (parts.length >= 4 && parts[1] === "src") {
    return parts[0];
  }
  if (parts.length >= 2 && parts[0] === "src") {
    return path.basename(ROOT);
  }
  if (parts.length >= 2 && parts[0] === "specs") {
    return parts[1];
  }
  return parts[0] || null;
}

function extractMethodName(message: string): string | null {
  const match = /^([a-zA-Z_][A-Za-z0-9_]*)\s*\(/.exec(message);
  return match ? match[1] : null;
}

function findMatchingBrace(text: string, openIndex: number): number {
  let depth = 0;
  let inString: string | null = null;
  let escaped = false;
  for (let index = openIndex; index < text.length; index += 1) {
    const char = text[index];
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === inString) {
        inString = null;
      }
      continue;
    }
    if (char === '"' || char === "'") {
      inString = char;
      continue;
    }
    if (char === "{") {
      depth += 1;
    } else if (char === "}") {
      depth -= 1;
      if (depth === 0) {
        return index;
      }
    }
  }
  return text.length - 1;
}

function collectLeadingAnnotations(lines: string[], lineIndex: number, declarationLine: string): string[] {
  const annotations: string[] = [];
  for (const match of declarationLine.matchAll(/@([A-Za-z_][A-Za-z0-9_.]*)/g)) {
    annotations.push(match[1].split(".").pop() || match[1]);
  }
  for (let index = lineIndex - 1; index >= 0; index -= 1) {
    const trimmed = lines[index].trim();
    if (!trimmed) {
      continue;
    }
    const match = /^@([A-Za-z_][A-Za-z0-9_.]*)/.exec(trimmed);
    if (!match) {
      break;
    }
    annotations.push(match[1].split(".").pop() || match[1]);
  }
  return Array.from(new Set(annotations)).sort();
}

function splitTypeList(value: string | undefined): string[] {
  if (!value) {
    return [];
  }
  return value
    .split(",")
    .map((item) => item.trim().replace(/[<{].*$/, "").trim())
    .filter(Boolean)
    .map((item) => item.split(".").pop() || item);
}

function extractInheritance(header: string): { extendsList: string[]; implementsList: string[] } {
  const extendsMatch = /\bextends\s+([A-Za-z0-9_.$<>, ?]+?)(?=\s+implements\b|\s*$)/.exec(header);
  const implementsMatch = /\bimplements\s+([A-Za-z0-9_.$<>, ?]+)/.exec(header);
  return {
    extendsList: splitTypeList(extendsMatch?.[1]),
    implementsList: splitTypeList(implementsMatch?.[1]),
  };
}

function extractPublicMethods(body: string, className: string): string[] {
  const methods: string[] = [];
  for (const match of body.matchAll(PUBLIC_METHOD_PATTERN)) {
    const name = match[1];
    const params = match[2].trim().replace(/\s+/g, " ");
    if (!["if", "for", "while", "switch", "catch"].includes(name) && name !== className) {
      methods.push(`${name}(${params})`);
    }
  }
  return Array.from(new Set(methods)).sort();
}

function countBraceDelta(line: string): number {
  let delta = 0;
  let inString: string | null = null;
  let escaped = false;
  for (const char of line) {
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === inString) {
        inString = null;
      }
      continue;
    }
    if (char === '"' || char === "'") {
      inString = char;
      continue;
    }
    if (char === "{") {
      delta += 1;
    } else if (char === "}") {
      delta -= 1;
    }
  }
  return delta;
}

function normalizeMethodSignature(name: string, params: string): string {
  return `${name}(${params.trim().replace(/\s+/g, " ")})`;
}

function splitTopLevelComma(value: string): string[] {
  const parts: string[] = [];
  let current = "";
  let angleDepth = 0;
  let parenDepth = 0;
  let braceDepth = 0;
  let bracketDepth = 0;
  let inString: string | null = null;
  let escaped = false;
  for (const char of value) {
    if (inString) {
      current += char;
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === inString) {
        inString = null;
      }
      continue;
    }
    if (char === '"' || char === "'") {
      current += char;
      inString = char;
      continue;
    }
    if (char === "<") {
      angleDepth += 1;
    } else if (char === ">") {
      angleDepth = Math.max(0, angleDepth - 1);
    } else if (char === "(") {
      parenDepth += 1;
    } else if (char === ")") {
      parenDepth = Math.max(0, parenDepth - 1);
    } else if (char === "{") {
      braceDepth += 1;
    } else if (char === "}") {
      braceDepth = Math.max(0, braceDepth - 1);
    } else if (char === "[") {
      bracketDepth += 1;
    } else if (char === "]") {
      bracketDepth = Math.max(0, bracketDepth - 1);
    } else if (char === "," && angleDepth === 0 && parenDepth === 0 && braceDepth === 0 && bracketDepth === 0) {
      if (current.trim()) {
        parts.push(current.trim());
      }
      current = "";
      continue;
    }
    current += char;
  }
  if (current.trim()) {
    parts.push(current.trim());
  }
  return parts;
}

function normalizeJavaType(value: string): string {
  return value
    .replace(/@\w+(?:\([^)]*\))?\s*/g, "")
    .replace(/\b(?:final|volatile|transient)\b\s*/g, "")
    .replace(/\s+/g, " ")
    .replace(/\s*<\s*/g, "<")
    .replace(/\s*>\s*/g, ">")
    .replace(/\s*,\s*/g, ", ")
    .replace(/\s*\[\s*\]\s*/g, "[]")
    .trim();
}

function extractParameterTypes(params: string): string[] {
  if (!params.trim()) {
    return [];
  }
  return splitTopLevelComma(params)
    .map((item) => item.replace(/\bfinal\s+/g, "").trim())
    .map((item) => item.replace(/@\w+(?:\([^)]*\))?\s*/g, "").trim())
    .map((item) => {
      const tokens = item.split(/\s+/).filter(Boolean);
      if (tokens.length <= 1) {
        return normalizeJavaType(item);
      }
      return normalizeJavaType(tokens.slice(0, -1).join(" "));
    })
    .filter(Boolean);
}

function parseMethodDeclaration(
  line: string,
  classType: string,
): { name: string; params: string; returnType: string | null } | null {
  const normalizedLine = line.replace(/\r$/, "");
  const publicPattern =
    /^\s*public\s+(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?(?:default\s+)?(?:<[^>]+>\s+)?([\w.$<>\[\], ?@]+?)\s+([a-zA-Z_][A-Za-z0-9_]*)\s*\(([^)]*)\)/;
  const interfacePattern =
    /^\s*(?:(?:public|private|protected|static|default|abstract|final|synchronized|strictfp)\s+)*(?:<[^>]+>\s+)?([\w.$<>\[\], ?@]+?)\s+([a-zA-Z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*(?:throws\s+[\w.$<>\[\], ?]+\s*)?(?:;|\{)/;
  const match = publicPattern.exec(normalizedLine) || (classType === "interface" ? interfacePattern.exec(normalizedLine) : null);
  if (!match) {
    return null;
  }
  return {
    returnType: normalizeJavaType(match[1]),
    name: match[2],
    params: match[3],
  };
}

function buildMethodDetail(
  methodName: string,
  params: string,
  returnType: string | null,
  annotationText: string,
  options: {
    inferred?: boolean;
    inferenceSource?: string | null;
    confidence?: string | null;
    ownerClass?: string | null;
    inheritedFrom?: string | null;
  } = {},
): ProjectExplorerMethod {
  const annotations = Array.from(annotationText.matchAll(/@([A-Za-z_][A-Za-z0-9_.]*)/g)).map((match) => match[1].split(".").pop() || match[1]);
  return {
    name: methodName,
    signature: normalizeMethodSignature(methodName, params),
    parameter_types: extractParameterTypes(params),
    return_type: returnType ? normalizeJavaType(returnType) : null,
    annotations: Array.from(new Set(annotations)).sort(),
    inferred: Boolean(options.inferred),
    inference_source: options.inferenceSource ?? null,
    confidence: options.confidence ?? null,
    owner_class: options.ownerClass ?? null,
    inherited_from: options.inheritedFrom ?? null,
    mybatis_statement: null,
  };
}

function parseFieldAnnotationName(annotationText: string, annotationName: string): string | null {
  const args = extractAnnotationArgs(annotationText, annotationName);
  if (args === null) {
    return null;
  }
  const nameMatch = /\bname\s*=\s*["']([^"']+)["']/.exec(args);
  if (nameMatch) {
    return nameMatch[1];
  }
  const valueMatch = /\bvalue\s*=\s*["']([^"']+)["']/.exec(args) || /["']([^"']+)["']/.exec(args);
  return valueMatch ? valueMatch[1] : null;
}


function parseFieldDeclaration(
  line: string,
): { fieldName: string; fieldType: string | null; isFinal: boolean; isStatic: boolean } | null {
  const match =
    /^\s*(?:public|protected|private)\s+((?:static\s+)?(?:final\s+)?(?:volatile\s+)?(?:transient\s+)?)?([\w.$<>\[\], ?@]+)\s+([a-zA-Z_][A-Za-z0-9_]*)\s*(?:=|;)/.exec(
      line.replace(/\r$/, ""),
    );
  if (!match) {
    return null;
  }
  const modifiers = match[1] || "";
  return {
    fieldType: normalizeJavaType(match[2]),
    fieldName: match[3],
    isFinal: /\bfinal\b/.test(modifiers),
    isStatic: /\bstatic\b/.test(modifiers),
  };
}

function isPrimitiveBooleanType(type: string | null): boolean {
  return normalizeJavaType(type || "") === "boolean";
}

function capitalizeJavaIdentifier(value: string): string {
  if (!value) {
    return value;
  }
  return `${value[0].toUpperCase()}${value.slice(1)}`;
}

function toSnakeCase(value: string): string {
  return value
    .replace(/([a-z0-9])([A-Z])/g, "$1_$2")
    .replace(/([A-Z]+)([A-Z][a-z])/g, "$1_$2")
    .replace(/[-\s]+/g, "_")
    .toLowerCase();
}

function uniqueNormalizedNames(values: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const rawValue of values) {
    const value = String(rawValue || "").trim();
    if (!value) {
      continue;
    }
    if (!seen.has(value)) {
      seen.add(value);
      result.push(value);
    }
    const lower = value.toLowerCase();
    if (!seen.has(lower)) {
      seen.add(lower);
      result.push(lower);
    }
  }
  return result;
}

function lombokPropertyName(fieldName: string, fieldType: string | null): string {
  if (isPrimitiveBooleanType(fieldType) && /^is[A-Z]/.test(fieldName)) {
    return fieldName.slice(2);
  }
  return fieldName;
}

function inferLombokGetter(fieldName: string, fieldType: string | null): { methodName: string; returnType: string | null } {
  if (isPrimitiveBooleanType(fieldType) && /^is[A-Z]/.test(fieldName)) {
    return { methodName: fieldName, returnType: fieldType };
  }
  const propertyName = lombokPropertyName(fieldName, fieldType);
  const prefix = isPrimitiveBooleanType(fieldType) ? "is" : "get";
  return {
    methodName: `${prefix}${capitalizeJavaIdentifier(propertyName)}`,
    returnType: fieldType,
  };
}

function inferLombokSetter(fieldName: string, fieldType: string | null): { methodName: string; params: string } {
  const propertyName = lombokPropertyName(fieldName, fieldType);
  const paramType = fieldType || "Object";
  return {
    methodName: `set${capitalizeJavaIdentifier(propertyName)}`,
    params: `${paramType} ${fieldName}`,
  };
}

function inferLombokMethods(
  className: string,
  classAnnotations: string[],
  fieldMetadata: Array<{
    field_name: string;
    field_type: string | null;
    annotations: string[];
    raw_annotation_text: string;
    is_final: boolean;
    is_static: boolean;
  }>,
  existingMethodDetails: ProjectExplorerMethod[],
): ProjectExplorerMethod[] {
  const existingSignatures = new Set(existingMethodDetails.map((item) => item.signature));
  const inferred = new Map<string, ProjectExplorerMethod>();
  const classAnnotationSet = new Set(classAnnotations);
  const classHasGetter = classAnnotationSet.has("Getter") || classAnnotationSet.has("Data");
  const classHasSetter = classAnnotationSet.has("Setter") || classAnnotationSet.has("Data");

  for (const field of fieldMetadata) {
    if (field.is_static) {
      continue;
    }
    const fieldAnnotationSet = new Set(field.annotations);
    const shouldInferGetter = classHasGetter || fieldAnnotationSet.has("Getter");
    const shouldInferSetter = (classHasSetter || fieldAnnotationSet.has("Setter")) && !field.is_final;

    if (shouldInferGetter) {
      const getter = inferLombokGetter(field.field_name, field.field_type);
      const detail = buildMethodDetail(
        getter.methodName,
        "",
        getter.returnType,
        "",
        {
          inferred: true,
          inferenceSource: "lombok-getter",
          confidence: "low",
          ownerClass: className,
        },
      );
      if (!existingSignatures.has(detail.signature)) {
        inferred.set(detail.signature, detail);
      }
    }

    if (shouldInferSetter) {
      const setter = inferLombokSetter(field.field_name, field.field_type);
      const detail = buildMethodDetail(
        setter.methodName,
        setter.params,
        "void",
        "",
        {
          inferred: true,
          inferenceSource: "lombok-setter",
          confidence: "low",
          ownerClass: className,
        },
      );
      if (!existingSignatures.has(detail.signature)) {
        inferred.set(detail.signature, detail);
      }
    }
  }

  return Array.from(inferred.values()).sort((a, b) => a.signature.localeCompare(b.signature));
}

function buildJpaMetadata(
  className: string,
  classAnnotationText: string,
  fieldMetadata: Array<{ field_name: string; field_type: string | null; annotations: string[]; raw_annotation_text: string }>,
): ProjectExplorerJpaEntity | undefined {
  const hasEntity = /@Entity\b/.test(classAnnotationText);
  const hasMappedSuperclass = /@MappedSuperclass\b/.test(classAnnotationText);
  if (!hasEntity && !hasMappedSuperclass) {
    return undefined;
  }
  const explicitTableName = parseFieldAnnotationName(classAnnotationText, "Table");
  const entityName = parseFieldAnnotationName(classAnnotationText, "Entity");
  const candidateTableNames = hasEntity
    ? uniqueNormalizedNames([
        explicitTableName,
        entityName,
        className,
        toSnakeCase(className),
      ])
    : [];
  const idFields = fieldMetadata
    .filter((item) => item.annotations.includes("Id") || item.annotations.includes("EmbeddedId"))
    .map((item) => item.field_name)
    .sort();
  const relationFields = fieldMetadata
    .filter((item) => item.annotations.some((annotation) => ["OneToOne", "OneToMany", "ManyToOne", "ManyToMany"].includes(annotation)))
    .map((item) => item.field_name)
    .sort();
  return {
    entity_kind: hasEntity ? "entity" : "mapped-superclass",
    table_name: hasEntity ? (explicitTableName || entityName || className) : null,
    candidate_table_names: candidateTableNames,
    id_fields: idFields,
    relation_fields: relationFields,
    column_mappings: fieldMetadata.map((item) => {
      const columnName = parseFieldAnnotationName(item.raw_annotation_text, "Column");
      const joinColumnName = parseFieldAnnotationName(item.raw_annotation_text, "JoinColumn");
      return {
        field_name: item.field_name,
        field_type: item.field_type,
        column_name: columnName || joinColumnName,
        candidate_column_names: uniqueNormalizedNames([
          columnName,
          joinColumnName,
          item.field_name,
          toSnakeCase(item.field_name),
        ]),
        annotations: item.annotations,
      };
    }),
  };
}

function collectClassMembers(
  body: string,
  className: string,
  classType: string,
  classBasePath: string,
  classAnnotations: string[],
): {
  declaredMethods: string[];
  methodDetails: ProjectExplorerMethod[];
  fields: string[];
  fieldDetails: ProjectExplorerField[];
  fieldMetadata: Array<{
    field_name: string;
    field_type: string | null;
    annotations: string[];
    raw_annotation_text: string;
    is_final: boolean;
    is_static: boolean;
  }>;
  endpoints: ProjectExplorerEndpoint[];
} {
  const declaredMethods = new Set<string>();
  const methodDetails = new Map<string, ProjectExplorerMethod>();
  const fields = new Set<string>();
  const fieldDetails = new Map<string, ProjectExplorerField>();
  const fieldMetadata = new Map<
    string,
    { field_name: string; field_type: string | null; annotations: string[]; raw_annotation_text: string; is_final: boolean; is_static: boolean }
  >();
  const endpoints = new Map<string, ProjectExplorerEndpoint>();
  const pendingAnnotations: string[] = [];
  let depth = 0;

  for (const rawLine of body.split(/\r?\n/)) {
    const line = rawLine.replace(/\r$/, "");
    const trimmed = line.trim();

    if (depth === 0 && trimmed.startsWith("@")) {
      pendingAnnotations.push(trimmed);
      depth += countBraceDelta(line);
      continue;
    }

    if (depth === 0) {
      const fieldMatch = FIELD_LINE_PATTERN.exec(line);
      if (fieldMatch) {
        fields.add(fieldMatch[1]);
        const parsedField = parseFieldDeclaration(line);
        const annotationText = pendingAnnotations.join("\n");
        const annotations = Array.from(annotationText.matchAll(/@([A-Za-z_][A-Za-z0-9_.]*)/g)).map((match) => match[1].split(".").pop() || match[1]);
        fieldDetails.set(fieldMatch[1], {
          name: fieldMatch[1],
          type: parsedField?.fieldType || null,
          annotations: Array.from(new Set(annotations)).sort(),
        });
        fieldMetadata.set(fieldMatch[1], {
          field_name: fieldMatch[1],
          field_type: parsedField?.fieldType || null,
          annotations: Array.from(new Set(annotations)).sort(),
          raw_annotation_text: annotationText,
          is_final: Boolean(parsedField?.isFinal),
          is_static: Boolean(parsedField?.isStatic),
        });
        pendingAnnotations.length = 0;
      }

      const publicMethodMatch = parseMethodDeclaration(line, classType);
      if (publicMethodMatch && PUBLIC_METHOD_LINE_PATTERN.exec(line)) {
        const methodName = publicMethodMatch.name;
        if (!["if", "for", "while", "switch", "catch"].includes(methodName) && methodName !== className) {
          const annotationText = pendingAnnotations.join("\n");
          const signature = normalizeMethodSignature(methodName, publicMethodMatch.params);
          declaredMethods.add(signature);
          methodDetails.set(
            signature,
            buildMethodDetail(methodName, publicMethodMatch.params, publicMethodMatch.returnType, annotationText, {
              ownerClass: className,
            }),
          );
          const endpoint = extractEndpointFromAnnotations(annotationText, methodName, classBasePath);
          if (endpoint) {
            endpoints.set(`${endpoint.method} ${endpoint.path} ${endpoint.operation_id}`, endpoint);
          }
        }
        pendingAnnotations.length = 0;
        depth += countBraceDelta(line);
        continue;
      }

      if (classType === "interface") {
        const interfaceMethodMatch = parseMethodDeclaration(line, classType);
        if (interfaceMethodMatch) {
          const methodName = interfaceMethodMatch.name;
          if (!["if", "for", "while", "switch", "catch"].includes(methodName) && methodName !== className) {
            const annotationText = pendingAnnotations.join("\n");
            const signature = normalizeMethodSignature(methodName, interfaceMethodMatch.params);
            declaredMethods.add(signature);
            methodDetails.set(
              signature,
              buildMethodDetail(methodName, interfaceMethodMatch.params, interfaceMethodMatch.returnType, annotationText, {
                ownerClass: className,
              }),
            );
            const endpoint = extractEndpointFromAnnotations(annotationText, methodName, classBasePath);
            if (endpoint) {
              endpoints.set(`${endpoint.method} ${endpoint.path} ${endpoint.operation_id}`, endpoint);
            }
          }
          pendingAnnotations.length = 0;
          depth += countBraceDelta(line);
          continue;
        }
      }

      if (trimmed && !trimmed.startsWith("@")) {
        pendingAnnotations.length = 0;
      }
    }

    depth += countBraceDelta(line);
  }

  const inferredMethodDetails =
    classType === "class" ? inferLombokMethods(className, classAnnotations, Array.from(fieldMetadata.values()), Array.from(methodDetails.values())) : [];
  for (const detail of inferredMethodDetails) {
    declaredMethods.add(detail.signature);
    methodDetails.set(detail.signature, detail);
  }

  return {
    declaredMethods: Array.from(declaredMethods).sort(),
    methodDetails: Array.from(methodDetails.values()).sort((a, b) => a.signature.localeCompare(b.signature)),
    fields: Array.from(fields).sort(),
    fieldDetails: Array.from(fieldDetails.values()).sort((a, b) => a.name.localeCompare(b.name)),
    fieldMetadata: Array.from(fieldMetadata.values()).sort((a, b) => a.field_name.localeCompare(b.field_name)),
    endpoints: Array.from(endpoints.values()).sort((a, b) => `${a.method} ${a.path}`.localeCompare(`${b.method} ${b.path}`)),
  };
}

function extractAnnotationArgs(annotationText: string, annotationName: string): string | null {
  const pattern = new RegExp(`@${annotationName}\\s*(?:\\(([^)]*)\\))?`, "m");
  const match = pattern.exec(annotationText);
  return match ? match[1] || "" : null;
}

function extractPathFromAnnotationArgs(args: string | null): string {
  if (args === null) {
    return "";
  }
  const named = /\b(?:value|path)\s*=\s*["']([^"']+)["']/.exec(args);
  if (named) {
    return named[1];
  }
  const first = /["']([^"']+)["']/.exec(args);
  return first ? first[1] : "";
}

function joinEndpointPaths(basePath: string, methodPath: string): string {
  const parts = [basePath, methodPath].filter(Boolean).map((item) => item.trim().replace(/^\/+|\/+$/g, ""));
  return `/${parts.join("/")}`.replace(/\/+/g, "/");
}

function extractClassBasePath(annotationText: string): string {
  return extractPathFromAnnotationArgs(extractAnnotationArgs(annotationText, "RequestMapping"));
}

function extractEndpointFromAnnotations(annotationText: string, methodName: string, basePath: string): ProjectExplorerEndpoint | null {
  const mappingMethods: Array<[string, string]> = [
    ["GetMapping", "GET"],
    ["PostMapping", "POST"],
    ["PutMapping", "PUT"],
    ["DeleteMapping", "DELETE"],
    ["PatchMapping", "PATCH"],
  ];
  for (const [annotation, httpMethod] of mappingMethods) {
    const args = extractAnnotationArgs(annotationText, annotation);
    if (args !== null) {
      return {
        path: joinEndpointPaths(basePath, extractPathFromAnnotationArgs(args)),
        method: httpMethod,
        operation_id: methodName,
        method_name: methodName,
      };
    }
  }
  const requestArgs = extractAnnotationArgs(annotationText, "RequestMapping");
  if (requestArgs !== null) {
    const methodMatch = /RequestMethod\.([A-Z]+)/.exec(requestArgs) || /\bmethod\s*=\s*["']?([A-Za-z]+)["']?/.exec(requestArgs);
    return {
      path: joinEndpointPaths(basePath, extractPathFromAnnotationArgs(requestArgs)),
      method: methodMatch ? methodMatch[1].toUpperCase() : "ANY",
      operation_id: methodName,
      method_name: methodName,
    };
  }
  return null;
}

function collectLeadingAnnotationText(lines: string[], lineIndex: number, declarationLine: string): string {
  const annotations: string[] = [];
  for (let index = lineIndex - 1; index >= 0; index -= 1) {
    const trimmed = lines[index].trim();
    if (!trimmed) {
      continue;
    }
    if (!trimmed.startsWith("@")) {
      break;
    }
    annotations.unshift(trimmed);
  }
  for (const match of declarationLine.matchAll(/@[^@\s]+(?:\([^)]*\))?/g)) {
    annotations.push(match[0]);
  }
  return annotations.join("\n");
}

function detectUnsupportedFeatures(text: string): string[] {
  const features = new Set<string>();
  if (/@(?:Builder|SuperBuilder|Value|RequiredArgsConstructor|AllArgsConstructor|NoArgsConstructor|With|Accessors|Delegate)\b/.test(text)) {
    features.add("lombok-generated-methods");
  }
  if (/\bClass\.forName\s*\(|\.getDeclaredMethod\s*\(|\.getMethod\s*\(/.test(text)) {
    features.add("reflection");
  }
  if (/@(?:Mapper|Select|Insert|Update|Delete)\b/.test(text)) {
    features.add("mybatis-mapper-binding");
  }
  return Array.from(features).sort();
}

type JavaParseResult = {
  classes: ProjectExplorerClass[];
  unsupported_features: string[];
  warnings: string[];
};

type MyBatisBinding = {
  namespace: string;
  xml_file: string;
  result_maps: Array<{
    id: string;
    type: string | null;
    mapped_columns: string[];
    mapped_properties: string[];
  }>;
  statements: Array<{
    id: string;
    kind: string;
    parameter_type: string | null;
    result_type: string | null;
    result_map: string | null;
    tables: string[];
  }>;
};

function cloneMethodDetail(detail: ProjectExplorerMethod): ProjectExplorerMethod {
  return {
    ...detail,
    annotations: [...(detail.annotations || [])],
    parameter_types: [...(detail.parameter_types || [])],
    mybatis_statement: detail.mybatis_statement
      ? {
          ...detail.mybatis_statement,
          mapped_columns: [...(detail.mybatis_statement.mapped_columns || [])],
          mapped_properties: [...(detail.mybatis_statement.mapped_properties || [])],
          tables: [...(detail.mybatis_statement.tables || [])],
        }
      : null,
  };
}

function methodConfidenceRank(value: string | null | undefined): number {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "high") {
    return 3;
  }
  if (normalized === "medium") {
    return 2;
  }
  if (normalized === "low") {
    return 1;
  }
  return 2;
}

function rankToConfidence(rank: number): string {
  if (rank >= 3) {
    return "high";
  }
  if (rank <= 1) {
    return "low";
  }
  return "medium";
}

function buildClassReliability(item: ProjectExplorerClass): ProjectExplorerClassReliability {
  const methodDetails = Array.isArray(item.method_details) ? item.method_details : [];
  const warnings: string[] = [];
  const evidenceSources = new Set<string>([String(item.source_kind || "").startsWith("java") ? "lexical-java" : "design-snapshot"]);
  let inferredMethods = 0;
  let inheritedMethods = 0;
  let mybatisBoundMethods = 0;
  let methodConfidenceRankValue = 2;

  if (item.jpa_entity) {
    evidenceSources.add("jpa-annotation");
  }
  if (item.mybatis_mapper) {
    evidenceSources.add("mybatis-xml");
  }

  for (const detail of methodDetails) {
    const confidenceRankValue = methodConfidenceRank(detail.confidence);
    methodConfidenceRankValue = Math.min(methodConfidenceRankValue, confidenceRankValue);
    if (detail.inferred) {
      inferredMethods += 1;
    }
    if (detail.inherited_from) {
      inheritedMethods += 1;
      evidenceSources.add("inheritance");
    }
    if (detail.inference_source === "lombok-getter" || detail.inference_source === "lombok-setter") {
      evidenceSources.add("lombok-inference");
      warnings.push(`method ${detail.signature} relies on ${detail.inference_source}`);
    }
    if (detail.mybatis_statement) {
      mybatisBoundMethods += 1;
      evidenceSources.add("mybatis-xml");
    }
  }

  if (mybatisBoundMethods > 0) {
    methodConfidenceRankValue = Math.max(methodConfidenceRankValue, 2);
  }
  if (methodDetails.length === 0 && item.type === "interface" && item.mybatis_mapper) {
    methodConfidenceRankValue = Math.min(methodConfidenceRankValue, 2);
  }

  let classConfidence = "medium";
  if (String(item.source_kind || "") === "design") {
    classConfidence = "low";
  } else if (warnings.length > 0 || inferredMethods > 0) {
    classConfidence = "low";
  } else if (item.jpa_entity || item.mybatis_mapper || inheritedMethods > 0) {
    classConfidence = "medium";
  }

  return {
    class_confidence: classConfidence,
    method_confidence: rankToConfidence(methodConfidenceRankValue),
    evidence_sources: Array.from(evidenceSources).sort(),
    inferred_methods: inferredMethods,
    inherited_methods: inheritedMethods,
    mybatis_bound_methods: mybatisBoundMethods,
    jpa_entity: Boolean(item.jpa_entity),
    warnings: Array.from(new Set(warnings)).sort(),
  };
}

function buildMethodDetailFromSignature(
  signature: string,
  ownerClass: string | null,
  inheritedFrom: string | null = null,
): ProjectExplorerMethod {
  const match = /^([A-Za-z_][A-Za-z0-9_]*)\((.*)\)$/.exec(signature.trim());
  const methodName = match ? match[1] : signature;
  const params = match ? match[2] : "";
  return buildMethodDetail(methodName, params, null, "", {
    inferred: Boolean(inheritedFrom),
    inferenceSource: inheritedFrom ? "inheritance" : null,
    confidence: inheritedFrom ? "medium" : null,
    ownerClass,
    inheritedFrom,
  });
}

function simpleJavaTypeName(value: string | null): string | null {
  if (!value) {
    return null;
  }
  const normalized = normalizeJavaType(value).replace(/\.\.\./g, "[]");
  const simple = normalized.split(".").pop() || normalized;
  return simple.trim() || null;
}

function methodTypeIncludes(expectedType: string | null, actualType: string | null): boolean {
  const expectedSimple = simpleJavaTypeName(expectedType);
  const actualNormalized = normalizeJavaType(actualType || "");
  if (!expectedSimple || !actualNormalized) {
    return true;
  }
  const tokenPattern = new RegExp(`(^|[^A-Za-z0-9_])${expectedSimple}([^A-Za-z0-9_]|$)`);
  return tokenPattern.test(actualNormalized);
}

function resolveMyBatisMethodCandidate(
  candidates: ProjectExplorerMethod[],
  statement: MyBatisBinding["statements"][number],
  effectiveResultType: string | null,
): ProjectExplorerMethod | null {
  if (candidates.length <= 1) {
    return candidates[0] || null;
  }
  const scored = candidates.map((detail) => {
    let score = 0;
    if (statement.parameter_type) {
      if (detail.parameter_types.length === 1 && methodTypeIncludes(statement.parameter_type, detail.parameter_types[0])) {
        score += 4;
      } else if (detail.parameter_types.some((parameterType) => methodTypeIncludes(statement.parameter_type, parameterType))) {
        score += 2;
      }
    } else if (detail.parameter_types.length === 0) {
      score += 1;
    }
    if (effectiveResultType && detail.return_type && methodTypeIncludes(effectiveResultType, detail.return_type)) {
      score += 3;
    }
    return { detail, score };
  });
  const bestScore = Math.max(...scored.map((item) => item.score));
  if (bestScore <= 0) {
    return null;
  }
  const winners = scored.filter((item) => item.score === bestScore);
  return winners.length === 1 ? winners[0].detail : null;
}

function attachMyBatisBindings(target: ProjectExplorerClass, binding: MyBatisBinding, scanWarnings: string[]): void {
  const methodDetails = new Map<string, ProjectExplorerMethod>();
  for (const detail of target.method_details || []) {
    methodDetails.set(detail.signature, cloneMethodDetail(detail));
  }
  const resultMapsById = new Map(binding.result_maps.map((item) => [item.id, item]));
  const methodsByName = new Map<string, ProjectExplorerMethod[]>();
  for (const detail of methodDetails.values()) {
    methodsByName.set(detail.name, [...(methodsByName.get(detail.name) || []), detail]);
  }
  for (const statement of binding.statements) {
    let candidates = methodsByName.get(statement.id) || [];
    const resultMap = statement.result_map ? resultMapsById.get(statement.result_map) || null : null;
    const effectiveResultType = statement.result_type || resultMap?.type || null;
    if (statement.result_map && !resultMap) {
      scanWarnings.push(`${binding.xml_file} MyBatis statement ${binding.namespace}.${statement.id} 引用了未解析的 resultMap=${statement.result_map}`);
    }
    if (candidates.length > 1) {
      const resolvedCandidate = resolveMyBatisMethodCandidate(candidates, statement, effectiveResultType);
      if (resolvedCandidate) {
        candidates = [resolvedCandidate];
      }
    }
    if (candidates.length === 0) {
      scanWarnings.push(`${binding.xml_file} MyBatis statement ${binding.namespace}.${statement.id} 鏈尮閰嶅埌 Java mapper 鏂规硶`);
      continue;
    }
    if (candidates.length > 1) {
      scanWarnings.push(`${binding.xml_file} MyBatis statement ${binding.namespace}.${statement.id} 鍖归厤鍒板涓?Java mapper 鏂规硶`);
      continue;
    }
    const detail = candidates[0];
    detail.mybatis_statement = {
      id: statement.id,
      kind: statement.kind,
      parameter_type: statement.parameter_type,
      result_type: statement.result_type,
      result_map: statement.result_map,
      result_map_type: resultMap?.type || null,
      mapped_columns: [...(resultMap?.mapped_columns || [])],
      mapped_properties: [...(resultMap?.mapped_properties || [])],
      tables: [...statement.tables],
    };
    detail.inference_source = detail.inference_source || "mybatis-xml-binding";
    detail.confidence = detail.confidence || "medium";
    if (statement.parameter_type && detail.parameter_types.length === 1 && !methodTypeIncludes(statement.parameter_type, detail.parameter_types[0])) {
      scanWarnings.push(
        `${binding.xml_file} MyBatis statement ${binding.namespace}.${statement.id} parameterType=${statement.parameter_type} 涓?Java 鏂规硶鍙傛暟涓嶄竴鑷? ${detail.signature}`,
      );
    }
    if (effectiveResultType && detail.return_type && !methodTypeIncludes(effectiveResultType, detail.return_type)) {
      scanWarnings.push(
        `${binding.xml_file} MyBatis statement ${binding.namespace}.${statement.id} resultType=${statement.result_type} 涓?Java 鏂规硶杩斿洖鍊间笉涓€鑷? ${detail.signature}`,
      );
    }
  }
  target.method_details = Array.from(methodDetails.values()).sort((a, b) => a.signature.localeCompare(b.signature));
}

export function parseJavaFile(filePath: string, sourceKind: string, modulePrefixMap: Record<string, string>): JavaParseResult {
  const text = fs.readFileSync(filePath, "utf8");
  const packageMatch = PACKAGE_PATTERN.exec(text);
  const packageName = packageMatch ? packageMatch[1] : null;

  const imports: string[] = [];
  for (const match of text.matchAll(IMPORT_PATTERN)) {
    imports.push(match[1].split(".").pop() || match[1]);
  }

  const moduleName = moduleFromPackage(packageName, modulePrefixMap) || moduleFromPath(filePath) || path.basename(ROOT);
  const snapshotPath = normalizeSnapshotPath(filePath);
  const classes: ProjectExplorerClass[] = [];
  const warnings: string[] = [];
  const lines = text.split(/\r?\n/);
  let offset = 0;
  for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
    const line = lines[lineIndex];
    const match = CLASS_LINE_PATTERN.exec(line);
    if (!match) {
      offset += line.length + 1;
      continue;
    }
    const classType = match[1];
    const className = match[2];
    const lineStart = offset;
    const declarationStart = lineStart + line.indexOf(match[0]);
    const braceIndex = text.indexOf("{", declarationStart);
    if (braceIndex < 0) {
      warnings.push(`${snapshotPath}:${lineIndex + 1} 未找到 ${className} 的类体`);
      offset += line.length + 1;
      continue;
    }
    const bodyEnd = findMatchingBrace(text, braceIndex);
    const header = text.slice(declarationStart, braceIndex);
    const body = text.slice(braceIndex + 1, bodyEnd);
    const inheritance = extractInheritance(header);
    const classAnnotationText = collectLeadingAnnotationText(lines, lineIndex, line);
    const classAnnotations = collectLeadingAnnotations(lines, lineIndex, line);
    const classBasePath = extractClassBasePath(classAnnotationText);
    const fqn = packageName ? `${packageName}.${className}` : null;
    const members = collectClassMembers(body, className, classType, classBasePath, classAnnotations);
    const ownerClass = fqn || className;
    classes.push({
      class_name: className,
      simple_name: className,
      fqn,
      package: packageName,
      module: moduleName,
      type: classType,
      source_file: snapshotPath,
      source_kind: sourceKind,
      public_methods: members.declaredMethods,
      method_details: members.methodDetails.map((detail) => ({
        ...detail,
        owner_class: ownerClass,
      })),
      declared_public_methods: members.declaredMethods,
      inherited_public_methods: [],
      fields: members.fields,
      field_details: members.fieldDetails,
      annotations: classAnnotations,
      extends: inheritance.extendsList,
      implements: inheritance.implementsList,
      endpoints: members.endpoints,
      jpa_entity: buildJpaMetadata(className, classAnnotationText, members.fieldMetadata),
      dependencies: Array.from(new Set([...imports, ...inheritance.extendsList, ...inheritance.implementsList])).sort(),
      source_files: [snapshotPath],
    });
    offset += line.length + 1;
  }
  return { classes, unsupported_features: detectUnsupportedFeatures(text), warnings };
}

function inferResourceRoots(scanRoots: string[]): string[] {
  const resourceRoots = new Set<string>();
  for (const rootPath of scanRoots) {
    const normalized = rootPath.replace(/\\/g, "/");
    if (normalized.includes("/src/main/java")) {
      resourceRoots.add(normalized.replace("/src/main/java", "/src/main/resources"));
    }
    if (normalized.includes("/src/test/java")) {
      resourceRoots.add(normalized.replace("/src/test/java", "/src/test/resources"));
    }
  }
  return Array.from(resourceRoots).filter((item) => fs.existsSync(item)).sort();
}

function parseMyBatisBindings(filePath: string): MyBatisBinding | null {
  const text = fs.readFileSync(filePath, "utf8");
  const namespaceMatch = MAPPER_NAMESPACE_PATTERN.exec(text);
  if (!namespaceMatch) {
    return null;
  }
  const resultMaps: MyBatisBinding["result_maps"] = [];
  for (const match of text.matchAll(MAPPER_RESULT_MAP_PATTERN)) {
    const attrs = `${match[1] || ""} ${match[3] || ""}`;
    const typeMatch = /\btype\s*=\s*["']([^"']+)["']/.exec(attrs);
    const mappedColumns = new Set<string>();
    const mappedProperties = new Set<string>();
    for (const entryMatch of match[4].matchAll(MAPPER_RESULT_MAPPING_ENTRY_PATTERN)) {
      const entryAttrs = entryMatch[2] || "";
      const propertyMatch = /\bproperty\s*=\s*["']([^"']+)["']/.exec(entryAttrs);
      const columnMatch = /\bcolumn\s*=\s*["']([^"']+)["']/.exec(entryAttrs);
      if (propertyMatch) {
        mappedProperties.add(propertyMatch[1]);
      }
      if (columnMatch) {
        mappedColumns.add(columnMatch[1]);
      }
    }
    resultMaps.push({
      id: match[2],
      type: typeMatch ? typeMatch[1] : null,
      mapped_columns: Array.from(mappedColumns).sort(),
      mapped_properties: Array.from(mappedProperties).sort(),
    });
  }
  const statements: MyBatisBinding["statements"] = [];
  for (const match of text.matchAll(MAPPER_STATEMENT_PATTERN)) {
    const attrs = `${match[2] || ""} ${match[4] || ""}`;
    const parameterType = /\bparameterType\s*=\s*["']([^"']+)["']/.exec(attrs);
    const resultType = /\bresultType\s*=\s*["']([^"']+)["']/.exec(attrs);
    const resultMap = /\bresultMap\s*=\s*["']([^"']+)["']/.exec(attrs);
    const statementBody = match[5] || "";
    const tables = Array.from(new Set(Array.from(statementBody.matchAll(/\bt_[a-zA-Z0-9_]+\b/gi)).map((item) => item[0]))).sort();
    statements.push({
      id: match[3],
      kind: match[1].toLowerCase(),
      parameter_type: parameterType ? parameterType[1] : null,
      result_type: resultType ? resultType[1] : null,
      result_map: resultMap ? resultMap[1] : null,
      tables,
    });
  }
  return {
    namespace: namespaceMatch[1],
    xml_file: normalizeSnapshotPath(filePath),
    result_maps: resultMaps.sort((a, b) => a.id.localeCompare(b.id)),
    statements,
  };
}

function parseDesignParticipants(filePath: string): ProjectExplorerClass[] {
  const text = fs.readFileSync(filePath, "utf8");
  const participants: Record<string, string> = {};
  const dependenciesByClass = new Map<string, Set<string>>();
  const methodsByClass = new Map<string, Set<string>>();
  let inSequence = false;

  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.replace(/\r$/, "");
    const trimmed = line.trim();
    if (trimmed.startsWith("```mermaid")) {
      inSequence = false;
      continue;
    }
    if (trimmed === "sequenceDiagram") {
      inSequence = true;
      continue;
    }
    if (trimmed.startsWith("```")) {
      inSequence = false;
      continue;
    }
    if (!inSequence) {
      continue;
    }

    const participantMatch = PARTICIPANT_ALIAS_PATTERN.exec(line);
    if (participantMatch) {
      participants[participantMatch[1]] = participantMatch[2];
      continue;
    }

    const callMatch = SEQUENCE_CALL_PATTERN.exec(line);
    if (!callMatch) {
      continue;
    }

    const [, sourceAlias, targetAlias, message] = callMatch;
    const sourceClass = participants[sourceAlias];
    const targetClass = participants[targetAlias];
    const methodName = extractMethodName(message.trim());

    if (sourceClass && targetClass) {
      if (!dependenciesByClass.has(sourceClass)) {
        dependenciesByClass.set(sourceClass, new Set<string>());
      }
      dependenciesByClass.get(sourceClass)?.add(targetClass);
    }

    if (targetClass && methodName) {
      if (!methodsByClass.has(targetClass)) {
        methodsByClass.set(targetClass, new Set<string>());
      }
      methodsByClass.get(targetClass)?.add(`${methodName}(...)`);
    }
  }

  const featureModule = moduleFromPath(filePath) || "design";
  const classes = Array.from(new Set(Array.from(text.matchAll(PARTICIPANT_PATTERN)).map((match) => match[1]))).sort();
  const snapshotPath = normalizeSnapshotPath(filePath);
  return classes.map((className) => ({
    class_name: className,
    simple_name: className,
    fqn: null,
    package: null,
    module: featureModule,
    type: "participant",
    source_file: snapshotPath,
    source_kind: "design",
    public_methods: Array.from(methodsByClass.get(className) || []).sort(),
    declared_public_methods: Array.from(methodsByClass.get(className) || []).sort(),
    inherited_public_methods: [],
    fields: [],
    annotations: [],
    extends: [],
    implements: [],
    endpoints: [],
    dependencies: Array.from(dependenciesByClass.get(className) || []).sort(),
    source_files: [snapshotPath],
  }));
}

function resolveParentReference(
  reference: string,
  byFqn: Map<string, ProjectExplorerClass>,
  bySimpleName: Map<string, ProjectExplorerClass[]>,
): ProjectExplorerClass | null {
  const trimmed = String(reference || "").trim();
  if (!trimmed) {
    return null;
  }
  if (byFqn.has(trimmed)) {
    return byFqn.get(trimmed) || null;
  }
  const simpleName = trimmed.split(".").pop() || trimmed;
  const candidates = bySimpleName.get(simpleName) || [];
  return candidates.length === 1 ? candidates[0] : null;
}

function enrichInheritedMethods(classes: ProjectExplorerClass[]): ProjectExplorerClass[] {
  const byFqn = new Map<string, ProjectExplorerClass>();
  const bySimpleName = new Map<string, ProjectExplorerClass[]>();
  for (const item of classes) {
    if (item.fqn) {
      byFqn.set(item.fqn, item);
    }
    const key = String(item.simple_name || "");
    bySimpleName.set(key, [...(bySimpleName.get(key) || []), item]);
  }

  const memo = new Map<string, { signatures: string[]; details: ProjectExplorerMethod[] }>();
  const visiting = new Set<string>();

  function keyFor(item: ProjectExplorerClass): string {
    return String(item.fqn || `${item.source_kind}::${item.source_file}::${item.simple_name}`);
  }

  function collect(item: ProjectExplorerClass): { signatures: string[]; details: ProjectExplorerMethod[] } {
    const itemKey = keyFor(item);
    if (memo.has(itemKey)) {
      return memo.get(itemKey) || { signatures: [], details: [] };
    }
    if (visiting.has(itemKey)) {
      return { signatures: [], details: [] };
    }
    visiting.add(itemKey);
    const inherited = new Set<string>();
    const inheritedDetails = new Map<string, ProjectExplorerMethod>();
    for (const reference of [...(item.extends || []), ...(item.implements || [])]) {
      const parent = resolveParentReference(reference, byFqn, bySimpleName);
      if (!parent || parent === item) {
        continue;
      }
      const parentOwner = String(parent.fqn || parent.simple_name || parent.class_name || "");
      const parentDeclared = parent.declared_public_methods || parent.public_methods || [];
      for (const methodName of parentDeclared) {
        inherited.add(methodName);
        const declaredDetail =
          (parent.method_details || []).find((detail) => detail.signature === methodName) ||
          buildMethodDetailFromSignature(methodName, parentOwner || null);
        inheritedDetails.set(
          methodName,
          {
            ...cloneMethodDetail(declaredDetail),
            inferred: true,
            inference_source: "inheritance",
            confidence: declaredDetail.confidence || "medium",
            owner_class: declaredDetail.owner_class || parentOwner || null,
            inherited_from: parentOwner || null,
          },
        );
      }
      const parentInherited = collect(parent);
      for (const methodName of parentInherited.signatures) {
        inherited.add(methodName);
      }
      for (const detail of parentInherited.details) {
        inheritedDetails.set(
          detail.signature,
          {
            ...cloneMethodDetail(detail),
            inferred: true,
            inference_source: "inheritance",
            confidence: detail.confidence || "medium",
            inherited_from: detail.inherited_from || parentOwner || null,
          },
        );
      }
    }
    visiting.delete(itemKey);
    const result = {
      signatures: Array.from(inherited).sort(),
      details: Array.from(inheritedDetails.values()).sort((a, b) => a.signature.localeCompare(b.signature)),
    };
    memo.set(itemKey, result);
    return result;
  }

  for (const item of classes) {
    const declared = Array.from(new Set(item.declared_public_methods || item.public_methods || [])).sort();
    const inheritedResult = collect(item);
    const inherited = inheritedResult.signatures.filter((methodName) => !declared.includes(methodName));
    item.declared_public_methods = declared;
    item.inherited_public_methods = inherited;
    item.public_methods = Array.from(new Set([...declared, ...inherited])).sort();
    const methodDetails = new Map<string, ProjectExplorerMethod>();
    for (const detail of item.method_details || []) {
      methodDetails.set(detail.signature, cloneMethodDetail(detail));
    }
    for (const detail of inheritedResult.details) {
      if (!methodDetails.has(detail.signature)) {
        methodDetails.set(detail.signature, cloneMethodDetail(detail));
      }
    }
    item.method_details = Array.from(methodDetails.values()).sort((a, b) => a.signature.localeCompare(b.signature));
  }
  return classes;
}

function enrichJpaInheritance(classes: ProjectExplorerClass[]): ProjectExplorerClass[] {
  const byFqn = new Map<string, ProjectExplorerClass>();
  const bySimpleName = new Map<string, ProjectExplorerClass[]>();
  for (const item of classes) {
    if (item.fqn) {
      byFqn.set(item.fqn, item);
    }
    const key = String(item.simple_name || "");
    bySimpleName.set(key, [...(bySimpleName.get(key) || []), item]);
  }

  const memo = new Map<string, ProjectExplorerJpaEntity | null>();
  const visiting = new Set<string>();

  function keyFor(item: ProjectExplorerClass): string {
    return String(item.fqn || `${item.source_kind}::${item.source_file}::${item.simple_name}`);
  }

  function collect(item: ProjectExplorerClass): ProjectExplorerJpaEntity | null {
    const itemKey = keyFor(item);
    if (memo.has(itemKey)) {
      return memo.get(itemKey) || null;
    }
    if (visiting.has(itemKey)) {
      return item.jpa_entity || null;
    }
    visiting.add(itemKey);
    const current = item.jpa_entity
      ? {
          ...item.jpa_entity,
          id_fields: [...(item.jpa_entity.id_fields || [])],
          relation_fields: [...(item.jpa_entity.relation_fields || [])],
          candidate_table_names: [...(item.jpa_entity.candidate_table_names || [])],
          column_mappings: (item.jpa_entity.column_mappings || []).map((mapping) => ({
            field_name: mapping.field_name,
            field_type: mapping.field_type ?? null,
            column_name: mapping.column_name,
            candidate_column_names: [...(mapping.candidate_column_names || [])],
            annotations: [...mapping.annotations],
          })),
        }
      : null;
    const merged = current
      ? current
      : {
          entity_kind: "mapped-superclass" as const,
          table_name: null,
          candidate_table_names: [],
          id_fields: [],
          relation_fields: [],
          column_mappings: [],
        };
    const columnMappings = new Map<
      string,
      {
        field_name: string;
        field_type: string | null;
        column_name: string | null;
        candidate_column_names: string[];
        annotations: string[];
      }
    >();
    for (const mapping of merged.column_mappings) {
      columnMappings.set(mapping.field_name, mapping);
    }
    for (const reference of [...(item.extends || []), ...(item.implements || [])]) {
      const parent = resolveParentReference(reference, byFqn, bySimpleName);
      if (!parent || parent === item || !parent.jpa_entity) {
        continue;
      }
      const parentJpa = collect(parent);
      if (!parentJpa) {
        continue;
      }
      for (const fieldName of parentJpa.id_fields || []) {
        if (!merged.id_fields.includes(fieldName)) {
          merged.id_fields.push(fieldName);
        }
      }
      for (const fieldName of parentJpa.relation_fields || []) {
        if (!merged.relation_fields.includes(fieldName)) {
          merged.relation_fields.push(fieldName);
        }
      }
      for (const mapping of parentJpa.column_mappings || []) {
        if (!columnMappings.has(mapping.field_name)) {
          columnMappings.set(mapping.field_name, {
            field_name: mapping.field_name,
            field_type: mapping.field_type ?? null,
            column_name: mapping.column_name,
            candidate_column_names: [...(mapping.candidate_column_names || [])],
            annotations: [...mapping.annotations],
          });
        }
      }
    }
    merged.id_fields = Array.from(new Set(merged.id_fields)).sort();
    merged.relation_fields = Array.from(new Set(merged.relation_fields)).sort();
    merged.column_mappings = Array.from(columnMappings.values()).sort((a, b) => a.field_name.localeCompare(b.field_name));
    visiting.delete(itemKey);
    memo.set(itemKey, current ? merged : null);
    return current ? merged : null;
  }

  for (const item of classes) {
    if (!item.jpa_entity) {
      continue;
    }
    const enriched = collect(item);
    if (enriched) {
      item.jpa_entity = enriched;
    }
  }
  return classes;
}

function mergeClasses(items: ProjectExplorerClass[], duplicateStrategy: string): ProjectExplorerClass[] {
  const merged = new Map<string, ProjectExplorerClass>();

  function findSimpleNameCandidates(simpleName: string): string[] {
    return Array.from(merged.keys()).filter((key) => merged.get(key)?.simple_name === simpleName);
  }

  for (const item of items) {
    const simpleName = String(item.simple_name);
    const fqn = item.fqn;
    let key: string;
    if (fqn) {
      key = fqn;
    } else {
      const candidates = findSimpleNameCandidates(simpleName);
      key = candidates.length === 1 ? candidates[0] : `design::${simpleName}::${item.module || item.source_file}`;
    }

    if (!merged.has(key)) {
      merged.set(key, {
        ...item,
        public_methods: [...(item.public_methods || [])],
        method_details: [...(item.method_details || [])],
        declared_public_methods: [...(item.declared_public_methods || item.public_methods || [])],
        inherited_public_methods: [...(item.inherited_public_methods || [])],
        fields: [...(item.fields || [])],
        field_details: [...(item.field_details || [])],
        annotations: [...(item.annotations || [])],
        extends: [...(item.extends || [])],
        implements: [...(item.implements || [])],
        endpoints: [...(item.endpoints || [])],
        dependencies: [...(item.dependencies || [])],
        jpa_entity: item.jpa_entity
          ? {
              ...item.jpa_entity,
              entity_kind: item.jpa_entity.entity_kind || "entity",
              id_fields: [...item.jpa_entity.id_fields],
              relation_fields: [...item.jpa_entity.relation_fields],
              candidate_table_names: [...(item.jpa_entity.candidate_table_names || [])],
              column_mappings: item.jpa_entity.column_mappings.map((mapping) => ({
                field_name: mapping.field_name,
                field_type: mapping.field_type ?? null,
                column_name: mapping.column_name,
                candidate_column_names: [...(mapping.candidate_column_names || [])],
                annotations: [...mapping.annotations],
              })),
            }
          : undefined,
        mybatis_mapper: item.mybatis_mapper
          ? {
              ...item.mybatis_mapper,
              xml_files: [...item.mybatis_mapper.xml_files],
              statement_ids: [...item.mybatis_mapper.statement_ids],
              result_maps: [...item.mybatis_mapper.result_maps],
              statements: [...item.mybatis_mapper.statements],
            }
          : undefined,
        source_files: [...(item.source_files || [])],
      });
      continue;
    }

    const existing = merged.get(key)!;
    existing.public_methods = Array.from(new Set([...(existing.public_methods || []), ...(item.public_methods || [])])).sort();
    const methodDetails = new Map<string, ProjectExplorerMethod>();
    for (const detail of [...(existing.method_details || []), ...(item.method_details || [])]) {
      methodDetails.set(detail.signature, detail);
    }
    existing.method_details = Array.from(methodDetails.values()).sort((a, b) => a.signature.localeCompare(b.signature));
    existing.declared_public_methods = Array.from(
      new Set([...(existing.declared_public_methods || []), ...(item.declared_public_methods || item.public_methods || [])]),
    ).sort();
    existing.inherited_public_methods = Array.from(
      new Set([...(existing.inherited_public_methods || []), ...(item.inherited_public_methods || [])]),
    ).sort();
    existing.fields = Array.from(new Set([...(existing.fields || []), ...(item.fields || [])])).sort();
    const fieldDetails = new Map<string, ProjectExplorerField>();
    for (const detail of [...(existing.field_details || []), ...(item.field_details || [])]) {
      fieldDetails.set(detail.name, detail);
    }
    existing.field_details = Array.from(fieldDetails.values()).sort((a, b) => a.name.localeCompare(b.name));
    existing.annotations = Array.from(new Set([...(existing.annotations || []), ...(item.annotations || [])])).sort();
    existing.extends = Array.from(new Set([...(existing.extends || []), ...(item.extends || [])])).sort();
    existing.implements = Array.from(new Set([...(existing.implements || []), ...(item.implements || [])])).sort();
    existing.endpoints = Array.from(
      new Map([...(existing.endpoints || []), ...(item.endpoints || [])].map((endpoint) => [`${endpoint.method} ${endpoint.path} ${endpoint.operation_id}`, endpoint])).values()
    ).sort((a, b) => `${a.method} ${a.path}`.localeCompare(`${b.method} ${b.path}`));
    existing.dependencies = Array.from(new Set([...(existing.dependencies || []), ...(item.dependencies || [])])).sort();
    if (item.jpa_entity) {
      const columnMappings = new Map<string, { field_name: string; field_type: string | null; column_name: string | null; candidate_column_names?: string[]; annotations: string[] }>();
      for (const mapping of [...(existing.jpa_entity?.column_mappings || []), ...item.jpa_entity.column_mappings]) {
        columnMappings.set(mapping.field_name, mapping);
      }
      existing.jpa_entity = {
        entity_kind: item.jpa_entity.entity_kind || existing.jpa_entity?.entity_kind || "entity",
        table_name: item.jpa_entity.table_name || existing.jpa_entity?.table_name || null,
        candidate_table_names: Array.from(
          new Set([...(existing.jpa_entity?.candidate_table_names || []), ...(item.jpa_entity.candidate_table_names || [])]),
        ).sort(),
        id_fields: Array.from(new Set([...(existing.jpa_entity?.id_fields || []), ...item.jpa_entity.id_fields])).sort(),
        relation_fields: Array.from(new Set([...(existing.jpa_entity?.relation_fields || []), ...item.jpa_entity.relation_fields])).sort(),
        column_mappings: Array.from(columnMappings.values()).sort((a, b) => a.field_name.localeCompare(b.field_name)),
      };
    }
    if (item.mybatis_mapper) {
      const statementMap = new Map<string, ProjectExplorerMyBatisMapper["statements"][number]>();
      for (const statement of [...(existing.mybatis_mapper?.statements || []), ...item.mybatis_mapper.statements]) {
        statementMap.set(statement.id, statement);
      }
      existing.mybatis_mapper = {
        namespace: item.mybatis_mapper.namespace || existing.mybatis_mapper?.namespace || "",
        xml_files: Array.from(new Set([...(existing.mybatis_mapper?.xml_files || []), ...item.mybatis_mapper.xml_files])).sort(),
        statement_ids: Array.from(new Set([...(existing.mybatis_mapper?.statement_ids || []), ...item.mybatis_mapper.statement_ids])).sort(),
        result_maps: Array.from(
          new Map([...(existing.mybatis_mapper?.result_maps || []), ...item.mybatis_mapper.result_maps].map((resultMap) => [resultMap.id, resultMap])).values()
        ).sort((a, b) => a.id.localeCompare(b.id)),
        statements: Array.from(statementMap.values()).sort((a, b) => a.id.localeCompare(b.id)),
      };
    }
    existing.source_files = Array.from(new Set([...(existing.source_files || []), ...(item.source_files || [])])).sort();

    const existingPriority = SOURCE_PRIORITY[String(existing.source_kind)] || 0;
    const incomingPriority = SOURCE_PRIORITY[String(item.source_kind)] || 0;
    if (incomingPriority > existingPriority) {
      for (const field of ["source_kind", "source_file", "fqn", "package", "type", "module"] as const) {
        existing[field] = item[field] as never;
      }
    }
  }

  const result = Array.from(merged.values()).sort((a, b) => {
    const left = `${String(a.simple_name || "").toLowerCase()}::${String(a.fqn || "")}`;
    const right = `${String(b.simple_name || "").toLowerCase()}::${String(b.fqn || "")}`;
    return left.localeCompare(right);
  });

  if (duplicateStrategy === "disambiguate") {
    const counts = new Map<string, number>();
    for (const item of result) {
      const key = String(item.simple_name || "");
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    for (const item of result) {
      const key = String(item.simple_name || "");
      if ((counts.get(key) || 0) > 1) {
        const moduleName = String(item.module || item.package || item.source_kind || "unknown");
        item.display_name = `${key}[${moduleName}]`;
      } else {
        item.display_name = key;
      }
    }
  } else {
    for (const item of result) {
      item.display_name = String(item.simple_name || "");
    }
  }

  const enriched = enrichJpaInheritance(enrichInheritedMethods(result));
  for (const item of enriched) {
    item.scan_reliability = buildClassReliability(item);
  }
  return enriched;
}

export function buildSnapshot(config: ProjectExplorerConfig, options: { forceRefresh?: boolean } = {}): [SnapshotPayload, boolean] {
  const files = collectWatchedFiles(config);
  const cacheEntry = loadCacheEntry(config);
  if (!options.forceRefresh && cacheIsValid(config, cacheEntry, files)) {
    if (cacheEntry && cacheEntry.payload && typeof cacheEntry.payload === "object") {
      return [cacheEntry.payload as SnapshotPayload, true];
    }
  }

  const items: ProjectExplorerClass[] = [];
  const unsupportedFeatures = new Set<string>();
  const scanWarnings: string[] = [];
  const modulePrefixMap = config.module_prefix_map && typeof config.module_prefix_map === "object" ? config.module_prefix_map : {};

  for (const rootPath of resolveScanRoots(config)) {
    const stack: string[] = [rootPath];
    while (stack.length > 0) {
      const current = stack.pop()!;
      const entries = fs.readdirSync(current, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(current, entry.name);
        if (entry.isDirectory()) {
          stack.push(fullPath);
        } else if (entry.isFile() && fullPath.endsWith(".java")) {
          const sourceKind = classifyJavaSource(fullPath);
          if (sourceKind) {
            try {
              const parsed = parseJavaFile(fullPath, sourceKind, modulePrefixMap);
              items.push(...parsed.classes);
              for (const feature of parsed.unsupported_features) {
                unsupportedFeatures.add(feature);
              }
              for (const warning of parsed.warnings) {
                scanWarnings.push(warning);
              }
            } catch (error) {
              const message = error instanceof Error ? error.message : String(error);
              scanWarnings.push(`${normalizeSnapshotPath(fullPath)} 扫描失败: ${message}`);
            }
          }
        }
      }
    }
  }

  for (const rootPath of resolveDesignRoots(config)) {
    const stack: string[] = [rootPath];
    while (stack.length > 0) {
      const current = stack.pop()!;
      const entries = fs.readdirSync(current, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(current, entry.name);
        if (entry.isDirectory()) {
          stack.push(fullPath);
        } else if (entry.isFile() && /design-v\d+\.md$/i.test(entry.name)) {
          items.push(...parseDesignParticipants(fullPath));
        }
      }
    }
  }

  const byFqn = new Map<string, ProjectExplorerClass>();
  const bySimpleName = new Map<string, ProjectExplorerClass[]>();
  for (const item of items) {
    if (item.fqn) {
      byFqn.set(item.fqn, item);
    }
    const key = String(item.simple_name || "");
    bySimpleName.set(key, [...(bySimpleName.get(key) || []), item]);
  }
  for (const rootPath of inferResourceRoots(resolveScanRoots(config))) {
    const stack: string[] = [rootPath];
    while (stack.length > 0) {
      const current = stack.pop()!;
      const entries = fs.readdirSync(current, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(current, entry.name);
        if (entry.isDirectory()) {
          stack.push(fullPath);
          continue;
        }
        if (!entry.isFile() || !fullPath.endsWith(".xml")) {
          continue;
        }
        const binding = parseMyBatisBindings(fullPath);
        if (!binding) {
          continue;
        }
        const namespaceSimpleName = binding.namespace.split(".").pop() || binding.namespace;
        const target =
          byFqn.get(binding.namespace) ||
          ((bySimpleName.get(namespaceSimpleName) || []).length === 1 ? (bySimpleName.get(namespaceSimpleName) || [])[0] : null);
        if (!target) {
          scanWarnings.push(`${normalizeSnapshotPath(fullPath)} 未找到对应的 MyBatis namespace 类: ${binding.namespace}`);
          continue;
        }
        target.mybatis_mapper = {
          namespace: binding.namespace,
          xml_files: [binding.xml_file],
          statement_ids: binding.statements.map((item) => item.id).sort(),
          result_maps: binding.result_maps,
          statements: binding.statements.sort((a, b) => a.id.localeCompare(b.id)),
        };
        attachMyBatisBindings(target, binding, scanWarnings);
        target.dependencies = Array.from(
          new Set([
            ...(target.dependencies || []),
            ...binding.result_maps
              .map((item) => item.type)
              .filter((item): item is string => Boolean(item))
              .map((item) => item.split(".").pop() || item),
            ...binding.statements
              .flatMap((item) => [item.parameter_type, item.result_type])
              .filter((item): item is string => Boolean(item))
              .map((item) => item.split(".").pop() || item),
          ]),
        ).sort();
      }
    }
  }

  const duplicateStrategy = String(config.duplicate_strategy || "disambiguate");
  const classes = mergeClasses(items, duplicateStrategy);
  const sourceStats: Record<string, number> = {};
  for (const item of classes) {
    const sourceKind = String(item.source_kind || "unknown");
    sourceStats[sourceKind] = (sourceStats[sourceKind] || 0) + 1;
  }
  if (sourceStats["java-main"] || sourceStats["java-test"]) {
    unsupportedFeatures.add("framework-proxy");
  }
  const confidence = scanWarnings.length > 0 ? "low" : "medium";

  const payload: SnapshotPayload = {
    generated_at: new Date().toISOString(),
    scanner: "java-lexical-v2",
    evidence_level: "L2",
    confidence,
    unsupported_features: Array.from(unsupportedFeatures).sort(),
    scan_quality: {
      parser: "lightweight-lexical-java",
      status: confidence === "low" ? "degraded" : "partial",
      warnings: scanWarnings,
      limitations: [
        "no-symbol-resolution",
        "partial-lombok-generated-method-expansion",
        "partial-mybatis-xml-binding-resolution",
        "no-framework-proxy-resolution",
      ],
      method_inference: ["lombok-getter", "lombok-setter", "lombok-data"],
    },
    source_stats: sourceStats,
    duplicate_strategy: duplicateStrategy,
    scan_roots: resolveScanRoots(config).map((item) => normalizeSnapshotPath(item)),
    design_roots: resolveDesignRoots(config).map((item) => normalizeSnapshotPath(item)),
    classes,
  };
  saveCacheEntry(config, payload as unknown as JsonRecord, files);
  return [payload, false];
}

function matchKeywords(item: ProjectExplorerClass, keywords: string[]): boolean {
  if (!keywords || keywords.length === 0) {
    return true;
  }
  const haystack = [
    item.class_name || "",
    item.simple_name || "",
    item.fqn || "",
    item.package || "",
    item.module || "",
    item.type || "",
    item.source_file || "",
    ...(item.public_methods || []),
    ...(item.fields || []),
    ...(item.annotations || []),
    ...(item.extends || []),
    ...(item.implements || []),
    ...(item.endpoints || []).map((endpoint) => `${endpoint.method} ${endpoint.path} ${endpoint.operation_id}`),
    ...(item.dependencies || []),
  ]
    .join(" ")
    .toLowerCase();
  return keywords.some((keyword) => haystack.includes(keyword));
}

function filterClasses(snapshot: SnapshotPayload, keywords: string[], limit?: number): ProjectExplorerClass[] {
  const classes = Array.isArray(snapshot.classes) ? snapshot.classes.filter((item) => item && typeof item === "object") : [];
  const filtered = classes.filter((item) => matchKeywords(item, keywords));
  return typeof limit === "number" ? filtered.slice(0, limit) : filtered;
}

export function scanModules(options: {
  keywords?: string[];
  forceRefresh?: boolean;
  limit?: number;
  scanRoots?: string[] | null;
  designRoots?: string[] | null;
} = {}): JsonRecord {
  const config = loadConfig();
  if (Array.isArray(options.scanRoots)) {
    config.scan_roots = options.scanRoots;
  }
  if (Array.isArray(options.designRoots)) {
    config.design_roots = options.designRoots;
  }
  const normalizedKeywords = (options.keywords || []).map((item) => String(item).trim().toLowerCase()).filter(Boolean);
  const [snapshot, fromCache] = buildSnapshot(config, { forceRefresh: options.forceRefresh });
  return {
    keywords: normalizedKeywords,
    count: filterClasses(snapshot, normalizedKeywords, options.limit ?? 20).length,
    from_cache: fromCache,
    duplicate_strategy: snapshot.duplicate_strategy,
    classes: filterClasses(snapshot, normalizedKeywords, options.limit ?? 20),
  };
}

function resolveMatches(snapshot: SnapshotPayload, query: { className?: string | null; fqn?: string | null }): ProjectExplorerClass[] {
  const classes = Array.isArray(snapshot.classes) ? snapshot.classes : [];
  return classes.filter((item) => {
    if (!item || typeof item !== "object") {
      return false;
    }
    if (query.fqn && String(item.fqn || "") === query.fqn) {
      return true;
    }
    if (query.className && String(item.simple_name || "") === query.className) {
      return true;
    }
    return false;
  });
}

export function verifyClassExists(options: { classNames?: string[]; forceRefresh?: boolean } = {}): JsonRecord {
  const config = loadConfig();
  const [snapshot, fromCache] = buildSnapshot(config, { forceRefresh: options.forceRefresh });
  const results: JsonRecord = {};
  for (const className of options.classNames || []) {
    const normalized = String(className).trim();
    const matches = resolveMatches(snapshot, {
      className: normalized.includes(".") ? null : normalized,
      fqn: normalized.includes(".") ? normalized : null,
    });
    results[normalized] = {
      exists: matches.length > 0,
      match_count: matches.length,
      matches,
    };
  }
  return { from_cache: fromCache, results };
}

export function listMethods(options: { className?: string | null; fqn?: string | null; forceRefresh?: boolean } = {}): JsonRecord {
  const config = loadConfig();
  const [snapshot, fromCache] = buildSnapshot(config, { forceRefresh: options.forceRefresh });
  const matches = resolveMatches(snapshot, { className: options.className || null, fqn: options.fqn || null });
  return {
    from_cache: fromCache,
    query: { class_name: options.className || null, fqn: options.fqn || null },
    matches: matches.map((item) => ({
      class_name: item.class_name,
      fqn: item.fqn,
      source_file: item.source_file,
      public_methods: item.public_methods || [],
    })),
  };
}

export function getClassDetail(options: { className?: string | null; fqn?: string | null; forceRefresh?: boolean } = {}): JsonRecord {
  const config = loadConfig();
  const [snapshot, fromCache] = buildSnapshot(config, { forceRefresh: options.forceRefresh });
  return {
    from_cache: fromCache,
    query: { class_name: options.className || null, fqn: options.fqn || null },
    matches: resolveMatches(snapshot, { className: options.className || null, fqn: options.fqn || null }),
  };
}

export function dumpModuleMapPayload(options: { forceRefresh?: boolean; scanRoots?: string[] | null; designRoots?: string[] | null } = {}): SnapshotPayload {
  const config = loadConfig();
  if (Array.isArray(options.scanRoots)) {
    config.scan_roots = options.scanRoots;
  }
  if (Array.isArray(options.designRoots)) {
    config.design_roots = options.designRoots;
  }
  const [snapshot] = buildSnapshot(config, { forceRefresh: options.forceRefresh });
  return snapshot;
}
