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
exports.parseJavaFile = parseJavaFile;
exports.buildSnapshot = buildSnapshot;
exports.scanModules = scanModules;
exports.verifyClassExists = verifyClassExists;
exports.listMethods = listMethods;
exports.getClassDetail = getClassDetail;
exports.dumpModuleMapPayload = dumpModuleMapPayload;
const fs = __importStar(require("node:fs"));
const path = __importStar(require("node:path"));
const cache_1 = require("./cache");
const CLASS_LINE_PATTERN = /^\s*(?:(?:public|protected|private|abstract|final|static|sealed|non-sealed|strictfp)\s+)*(class|interface|enum|record)\s+([A-Z][A-Za-z0-9_]*)\b(.*)$/;
const PACKAGE_PATTERN = /^\s*package\s+([a-zA-Z0-9_.]+)\s*;/m;
const IMPORT_PATTERN = /^\s*import\s+([a-zA-Z0-9_.]+)\s*;/gm;
const PUBLIC_METHOD_PATTERN = /^\s*public\s+(?:static\s+)?(?:final\s+)?(?:<[^>]+>\s+)?(?:[\w.$<>\[\], ?@]+\s+)?([a-zA-Z_][A-Za-z0-9_]*)\s*\(([^)]*)\)/gm;
const PUBLIC_METHOD_LINE_PATTERN = /^\s*public\s+(?:static\s+)?(?:final\s+)?(?:<[^>]+>\s+)?(?:[\w.$<>\[\], ?@]+\s+)?([a-zA-Z_][A-Za-z0-9_]*)\s*\(([^)]*)\)/;
const INTERFACE_METHOD_LINE_PATTERN = /^\s*(?:(?:public|private|protected|static|default|abstract|final|synchronized|strictfp)\s+)*(?:<[^>]+>\s+)?(?:[\w.$<>\[\], ?@]+\s+)?([a-zA-Z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*(?:throws\s+[\w.$<>\[\], ?]+\s*)?(?:;|\{)/;
const FIELD_PATTERN = /^\s*(?:public|protected|private)\s+(?:static\s+)?(?:final\s+)?(?:volatile\s+)?(?:transient\s+)?[\w.$<>\[\], ?]+\s+([a-zA-Z_][A-Za-z0-9_]*)\s*(?:=|;)/gm;
const FIELD_LINE_PATTERN = /^\s*(?:public|protected|private)\s+(?:static\s+)?(?:final\s+)?(?:volatile\s+)?(?:transient\s+)?[\w.$<>\[\], ?]+\s+([a-zA-Z_][A-Za-z0-9_]*)\s*(?:=|;)/;
const PARTICIPANT_PATTERN = /^\s*participant\s+\w+\s+as\s+([A-Z][A-Za-z0-9_]*)\s*$/gm;
const PARTICIPANT_ALIAS_PATTERN = /^\s*participant\s+(\w+)\s+as\s+([A-Z][A-Za-z0-9_]*)\s*$/;
const SEQUENCE_CALL_PATTERN = /^\s*(\w+)\s*->>\s*(\w+)\s*:\s*(.+?)\s*$/;
const MAPPER_NAMESPACE_PATTERN = /<mapper\b[^>]*\bnamespace\s*=\s*["']([^"']+)["'][^>]*>/i;
const MAPPER_RESULT_MAP_PATTERN = /<resultMap\b([^>]*)\bid\s*=\s*["']([^"']+)["']([^>]*)>([\s\S]*?)<\/resultMap>/gi;
const MAPPER_RESULT_MAPPING_ENTRY_PATTERN = /<(id|result|association|collection)\b([^>]*)\/?>/gi;
const MAPPER_STATEMENT_PATTERN = /<(select|insert|update|delete)\b([^>]*)\bid\s*=\s*["']([^"']+)["']([^>]*)>([\s\S]*?)<\/\1>/gi;
const SOURCE_PRIORITY = {
    "java-main": 4,
    "java-test": 3,
    design: 1,
};
function classifyJavaSource(filePath) {
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
function moduleFromPackage(packageName, modulePrefixMap) {
    if (!packageName) {
        return null;
    }
    let matchedPrefix = null;
    let matchedModule = null;
    for (const [prefix, moduleName] of Object.entries(modulePrefixMap || {})) {
        if (packageName.startsWith(prefix) && (matchedPrefix === null || prefix.length > matchedPrefix.length)) {
            matchedPrefix = prefix;
            matchedModule = String(moduleName);
        }
    }
    return matchedModule;
}
function moduleFromPath(filePath) {
    const normalized = filePath.replace(/\\/g, "/");
    if (normalized.includes("/src/main/java/") || normalized.includes("/src/test/java/")) {
        const sourceMarkerIndex = normalized.lastIndexOf("/src/");
        if (sourceMarkerIndex > 0) {
            return path.basename(normalized.slice(0, sourceMarkerIndex));
        }
    }
    const relativePath = path.relative(cache_1.ROOT, filePath);
    const parts = relativePath.split(path.sep);
    if (parts.length >= 4 && parts[1] === "src") {
        return parts[0];
    }
    if (parts.length >= 2 && parts[0] === "src") {
        return path.basename(cache_1.ROOT);
    }
    if (parts.length >= 2 && parts[0] === "specs") {
        return parts[1];
    }
    return parts[0] || null;
}
function extractMethodName(message) {
    const match = /^([a-zA-Z_][A-Za-z0-9_]*)\s*\(/.exec(message);
    return match ? match[1] : null;
}
function findMatchingBrace(text, openIndex) {
    let depth = 0;
    let inString = null;
    let escaped = false;
    for (let index = openIndex; index < text.length; index += 1) {
        const char = text[index];
        if (inString) {
            if (escaped) {
                escaped = false;
            }
            else if (char === "\\") {
                escaped = true;
            }
            else if (char === inString) {
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
        }
        else if (char === "}") {
            depth -= 1;
            if (depth === 0) {
                return index;
            }
        }
    }
    return text.length - 1;
}
function collectLeadingAnnotations(lines, lineIndex, declarationLine) {
    const annotations = [];
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
function splitTypeList(value) {
    if (!value) {
        return [];
    }
    return value
        .split(",")
        .map((item) => item.trim().replace(/[<{].*$/, "").trim())
        .filter(Boolean)
        .map((item) => item.split(".").pop() || item);
}
function extractInheritance(header) {
    const extendsMatch = /\bextends\s+([A-Za-z0-9_.$<>, ?]+?)(?=\s+implements\b|\s*$)/.exec(header);
    const implementsMatch = /\bimplements\s+([A-Za-z0-9_.$<>, ?]+)/.exec(header);
    return {
        extendsList: splitTypeList(extendsMatch?.[1]),
        implementsList: splitTypeList(implementsMatch?.[1]),
    };
}
function extractPublicMethods(body, className) {
    const methods = [];
    for (const match of body.matchAll(PUBLIC_METHOD_PATTERN)) {
        const name = match[1];
        const params = match[2].trim().replace(/\s+/g, " ");
        if (!["if", "for", "while", "switch", "catch"].includes(name) && name !== className) {
            methods.push(`${name}(${params})`);
        }
    }
    return Array.from(new Set(methods)).sort();
}
function countBraceDelta(line) {
    let delta = 0;
    let inString = null;
    let escaped = false;
    for (const char of line) {
        if (inString) {
            if (escaped) {
                escaped = false;
            }
            else if (char === "\\") {
                escaped = true;
            }
            else if (char === inString) {
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
        }
        else if (char === "}") {
            delta -= 1;
        }
    }
    return delta;
}
function normalizeMethodSignature(name, params) {
    return `${name}(${params.trim().replace(/\s+/g, " ")})`;
}
function splitTopLevelComma(value) {
    const parts = [];
    let current = "";
    let angleDepth = 0;
    let parenDepth = 0;
    let braceDepth = 0;
    let bracketDepth = 0;
    let inString = null;
    let escaped = false;
    for (const char of value) {
        if (inString) {
            current += char;
            if (escaped) {
                escaped = false;
            }
            else if (char === "\\") {
                escaped = true;
            }
            else if (char === inString) {
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
        }
        else if (char === ">") {
            angleDepth = Math.max(0, angleDepth - 1);
        }
        else if (char === "(") {
            parenDepth += 1;
        }
        else if (char === ")") {
            parenDepth = Math.max(0, parenDepth - 1);
        }
        else if (char === "{") {
            braceDepth += 1;
        }
        else if (char === "}") {
            braceDepth = Math.max(0, braceDepth - 1);
        }
        else if (char === "[") {
            bracketDepth += 1;
        }
        else if (char === "]") {
            bracketDepth = Math.max(0, bracketDepth - 1);
        }
        else if (char === "," && angleDepth === 0 && parenDepth === 0 && braceDepth === 0 && bracketDepth === 0) {
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
function normalizeJavaType(value) {
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
function extractParameterTypes(params) {
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
function parseMethodDeclaration(line, classType) {
    const normalizedLine = line.replace(/\r$/, "");
    const publicPattern = /^\s*public\s+(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?(?:default\s+)?(?:<[^>]+>\s+)?([\w.$<>\[\], ?@]+?)\s+([a-zA-Z_][A-Za-z0-9_]*)\s*\(([^)]*)\)/;
    const interfacePattern = /^\s*(?:(?:public|private|protected|static|default|abstract|final|synchronized|strictfp)\s+)*(?:<[^>]+>\s+)?([\w.$<>\[\], ?@]+?)\s+([a-zA-Z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*(?:throws\s+[\w.$<>\[\], ?]+\s*)?(?:;|\{)/;
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
function buildMethodDetail(methodName, params, returnType, annotationText, options = {}) {
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
    };
}
function parseFieldAnnotationName(annotationText, annotationName) {
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
function parseFieldDeclaration(line) {
    const match = /^\s*(?:public|protected|private)\s+((?:static\s+)?(?:final\s+)?(?:volatile\s+)?(?:transient\s+)?)?([\w.$<>\[\], ?@]+)\s+([a-zA-Z_][A-Za-z0-9_]*)\s*(?:=|;)/.exec(line.replace(/\r$/, ""));
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
function isPrimitiveBooleanType(type) {
    return normalizeJavaType(type || "") === "boolean";
}
function capitalizeJavaIdentifier(value) {
    if (!value) {
        return value;
    }
    return `${value[0].toUpperCase()}${value.slice(1)}`;
}
function lombokPropertyName(fieldName, fieldType) {
    if (isPrimitiveBooleanType(fieldType) && /^is[A-Z]/.test(fieldName)) {
        return fieldName.slice(2);
    }
    return fieldName;
}
function inferLombokGetter(fieldName, fieldType) {
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
function inferLombokSetter(fieldName, fieldType) {
    const propertyName = lombokPropertyName(fieldName, fieldType);
    const paramType = fieldType || "Object";
    return {
        methodName: `set${capitalizeJavaIdentifier(propertyName)}`,
        params: `${paramType} ${fieldName}`,
    };
}
function inferLombokMethods(classAnnotations, fieldMetadata, existingMethodDetails) {
    const existingSignatures = new Set(existingMethodDetails.map((item) => item.signature));
    const inferred = new Map();
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
            const detail = buildMethodDetail(getter.methodName, "", getter.returnType, "", {
                inferred: true,
                inferenceSource: "lombok-getter",
                confidence: "low",
            });
            if (!existingSignatures.has(detail.signature)) {
                inferred.set(detail.signature, detail);
            }
        }
        if (shouldInferSetter) {
            const setter = inferLombokSetter(field.field_name, field.field_type);
            const detail = buildMethodDetail(setter.methodName, setter.params, "void", "", {
                inferred: true,
                inferenceSource: "lombok-setter",
                confidence: "low",
            });
            if (!existingSignatures.has(detail.signature)) {
                inferred.set(detail.signature, detail);
            }
        }
    }
    return Array.from(inferred.values()).sort((a, b) => a.signature.localeCompare(b.signature));
}
function buildJpaMetadata(classAnnotationText, fieldMetadata) {
    if (!/@Entity\b/.test(classAnnotationText) && !/@MappedSuperclass\b/.test(classAnnotationText)) {
        return undefined;
    }
    const idFields = fieldMetadata
        .filter((item) => item.annotations.includes("Id") || item.annotations.includes("EmbeddedId"))
        .map((item) => item.field_name)
        .sort();
    const relationFields = fieldMetadata
        .filter((item) => item.annotations.some((annotation) => ["OneToOne", "OneToMany", "ManyToOne", "ManyToMany"].includes(annotation)))
        .map((item) => item.field_name)
        .sort();
    return {
        table_name: parseFieldAnnotationName(classAnnotationText, "Table"),
        id_fields: idFields,
        relation_fields: relationFields,
        column_mappings: fieldMetadata.map((item) => ({
            field_name: item.field_name,
            field_type: item.field_type,
            column_name: parseFieldAnnotationName(item.raw_annotation_text, "Column"),
            annotations: item.annotations,
        })),
    };
}
function collectClassMembers(body, className, classType, classBasePath, classAnnotations) {
    const declaredMethods = new Set();
    const methodDetails = new Map();
    const fields = new Set();
    const fieldDetails = new Map();
    const fieldMetadata = new Map();
    const endpoints = new Map();
    const pendingAnnotations = [];
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
                    methodDetails.set(signature, buildMethodDetail(methodName, publicMethodMatch.params, publicMethodMatch.returnType, annotationText));
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
                        methodDetails.set(signature, buildMethodDetail(methodName, interfaceMethodMatch.params, interfaceMethodMatch.returnType, annotationText));
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
    const inferredMethodDetails = classType === "class" ? inferLombokMethods(classAnnotations, Array.from(fieldMetadata.values()), Array.from(methodDetails.values())) : [];
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
function extractAnnotationArgs(annotationText, annotationName) {
    const pattern = new RegExp(`@${annotationName}\\s*(?:\\(([^)]*)\\))?`, "m");
    const match = pattern.exec(annotationText);
    return match ? match[1] || "" : null;
}
function extractPathFromAnnotationArgs(args) {
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
function joinEndpointPaths(basePath, methodPath) {
    const parts = [basePath, methodPath].filter(Boolean).map((item) => item.trim().replace(/^\/+|\/+$/g, ""));
    return `/${parts.join("/")}`.replace(/\/+/g, "/");
}
function extractClassBasePath(annotationText) {
    return extractPathFromAnnotationArgs(extractAnnotationArgs(annotationText, "RequestMapping"));
}
function extractEndpointFromAnnotations(annotationText, methodName, basePath) {
    const mappingMethods = [
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
function collectLeadingAnnotationText(lines, lineIndex, declarationLine) {
    const annotations = [];
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
function detectUnsupportedFeatures(text) {
    const features = new Set();
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
function parseJavaFile(filePath, sourceKind, modulePrefixMap) {
    const text = fs.readFileSync(filePath, "utf8");
    const packageMatch = PACKAGE_PATTERN.exec(text);
    const packageName = packageMatch ? packageMatch[1] : null;
    const imports = [];
    for (const match of text.matchAll(IMPORT_PATTERN)) {
        imports.push(match[1].split(".").pop() || match[1]);
    }
    const moduleName = moduleFromPackage(packageName, modulePrefixMap) || moduleFromPath(filePath) || path.basename(cache_1.ROOT);
    const snapshotPath = (0, cache_1.normalizeSnapshotPath)(filePath);
    const classes = [];
    const warnings = [];
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
            method_details: members.methodDetails,
            declared_public_methods: members.declaredMethods,
            inherited_public_methods: [],
            fields: members.fields,
            field_details: members.fieldDetails,
            annotations: classAnnotations,
            extends: inheritance.extendsList,
            implements: inheritance.implementsList,
            endpoints: members.endpoints,
            jpa_entity: buildJpaMetadata(classAnnotationText, members.fieldMetadata),
            dependencies: Array.from(new Set([...imports, ...inheritance.extendsList, ...inheritance.implementsList])).sort(),
            source_files: [snapshotPath],
        });
        offset += line.length + 1;
    }
    return { classes, unsupported_features: detectUnsupportedFeatures(text), warnings };
}
function inferResourceRoots(scanRoots) {
    const resourceRoots = new Set();
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
function parseMyBatisBindings(filePath) {
    const text = fs.readFileSync(filePath, "utf8");
    const namespaceMatch = MAPPER_NAMESPACE_PATTERN.exec(text);
    if (!namespaceMatch) {
        return null;
    }
    const resultMaps = [];
    for (const match of text.matchAll(MAPPER_RESULT_MAP_PATTERN)) {
        const attrs = `${match[1] || ""} ${match[3] || ""}`;
        const typeMatch = /\btype\s*=\s*["']([^"']+)["']/.exec(attrs);
        const mappedColumns = new Set();
        const mappedProperties = new Set();
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
    const statements = [];
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
        xml_file: (0, cache_1.normalizeSnapshotPath)(filePath),
        result_maps: resultMaps.sort((a, b) => a.id.localeCompare(b.id)),
        statements,
    };
}
function parseDesignParticipants(filePath) {
    const text = fs.readFileSync(filePath, "utf8");
    const participants = {};
    const dependenciesByClass = new Map();
    const methodsByClass = new Map();
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
                dependenciesByClass.set(sourceClass, new Set());
            }
            dependenciesByClass.get(sourceClass)?.add(targetClass);
        }
        if (targetClass && methodName) {
            if (!methodsByClass.has(targetClass)) {
                methodsByClass.set(targetClass, new Set());
            }
            methodsByClass.get(targetClass)?.add(`${methodName}(...)`);
        }
    }
    const featureModule = moduleFromPath(filePath) || "design";
    const classes = Array.from(new Set(Array.from(text.matchAll(PARTICIPANT_PATTERN)).map((match) => match[1]))).sort();
    const snapshotPath = (0, cache_1.normalizeSnapshotPath)(filePath);
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
function resolveParentReference(reference, byFqn, bySimpleName) {
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
function enrichInheritedMethods(classes) {
    const byFqn = new Map();
    const bySimpleName = new Map();
    for (const item of classes) {
        if (item.fqn) {
            byFqn.set(item.fqn, item);
        }
        const key = String(item.simple_name || "");
        bySimpleName.set(key, [...(bySimpleName.get(key) || []), item]);
    }
    const memo = new Map();
    const visiting = new Set();
    function keyFor(item) {
        return String(item.fqn || `${item.source_kind}::${item.source_file}::${item.simple_name}`);
    }
    function collect(item) {
        const itemKey = keyFor(item);
        if (memo.has(itemKey)) {
            return memo.get(itemKey) || [];
        }
        if (visiting.has(itemKey)) {
            return [];
        }
        visiting.add(itemKey);
        const inherited = new Set();
        for (const reference of [...(item.extends || []), ...(item.implements || [])]) {
            const parent = resolveParentReference(reference, byFqn, bySimpleName);
            if (!parent || parent === item) {
                continue;
            }
            const parentDeclared = parent.declared_public_methods || parent.public_methods || [];
            for (const methodName of parentDeclared) {
                inherited.add(methodName);
            }
            for (const methodName of collect(parent)) {
                inherited.add(methodName);
            }
        }
        visiting.delete(itemKey);
        const result = Array.from(inherited).sort();
        memo.set(itemKey, result);
        return result;
    }
    for (const item of classes) {
        const declared = Array.from(new Set(item.declared_public_methods || item.public_methods || [])).sort();
        const inherited = collect(item).filter((methodName) => !declared.includes(methodName));
        item.declared_public_methods = declared;
        item.inherited_public_methods = inherited;
        item.public_methods = Array.from(new Set([...declared, ...inherited])).sort();
    }
    return classes;
}
function mergeClasses(items, duplicateStrategy) {
    const merged = new Map();
    function findSimpleNameCandidates(simpleName) {
        return Array.from(merged.keys()).filter((key) => merged.get(key)?.simple_name === simpleName);
    }
    for (const item of items) {
        const simpleName = String(item.simple_name);
        const fqn = item.fqn;
        let key;
        if (fqn) {
            key = fqn;
        }
        else {
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
                        id_fields: [...item.jpa_entity.id_fields],
                        relation_fields: [...item.jpa_entity.relation_fields],
                        column_mappings: item.jpa_entity.column_mappings.map((mapping) => ({
                            field_name: mapping.field_name,
                            field_type: mapping.field_type ?? null,
                            column_name: mapping.column_name,
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
        const existing = merged.get(key);
        existing.public_methods = Array.from(new Set([...(existing.public_methods || []), ...(item.public_methods || [])])).sort();
        const methodDetails = new Map();
        for (const detail of [...(existing.method_details || []), ...(item.method_details || [])]) {
            methodDetails.set(detail.signature, detail);
        }
        existing.method_details = Array.from(methodDetails.values()).sort((a, b) => a.signature.localeCompare(b.signature));
        existing.declared_public_methods = Array.from(new Set([...(existing.declared_public_methods || []), ...(item.declared_public_methods || item.public_methods || [])])).sort();
        existing.inherited_public_methods = Array.from(new Set([...(existing.inherited_public_methods || []), ...(item.inherited_public_methods || [])])).sort();
        existing.fields = Array.from(new Set([...(existing.fields || []), ...(item.fields || [])])).sort();
        const fieldDetails = new Map();
        for (const detail of [...(existing.field_details || []), ...(item.field_details || [])]) {
            fieldDetails.set(detail.name, detail);
        }
        existing.field_details = Array.from(fieldDetails.values()).sort((a, b) => a.name.localeCompare(b.name));
        existing.annotations = Array.from(new Set([...(existing.annotations || []), ...(item.annotations || [])])).sort();
        existing.extends = Array.from(new Set([...(existing.extends || []), ...(item.extends || [])])).sort();
        existing.implements = Array.from(new Set([...(existing.implements || []), ...(item.implements || [])])).sort();
        existing.endpoints = Array.from(new Map([...(existing.endpoints || []), ...(item.endpoints || [])].map((endpoint) => [`${endpoint.method} ${endpoint.path} ${endpoint.operation_id}`, endpoint])).values()).sort((a, b) => `${a.method} ${a.path}`.localeCompare(`${b.method} ${b.path}`));
        existing.dependencies = Array.from(new Set([...(existing.dependencies || []), ...(item.dependencies || [])])).sort();
        if (item.jpa_entity) {
            const columnMappings = new Map();
            for (const mapping of [...(existing.jpa_entity?.column_mappings || []), ...item.jpa_entity.column_mappings]) {
                columnMappings.set(mapping.field_name, mapping);
            }
            existing.jpa_entity = {
                table_name: item.jpa_entity.table_name || existing.jpa_entity?.table_name || null,
                id_fields: Array.from(new Set([...(existing.jpa_entity?.id_fields || []), ...item.jpa_entity.id_fields])).sort(),
                relation_fields: Array.from(new Set([...(existing.jpa_entity?.relation_fields || []), ...item.jpa_entity.relation_fields])).sort(),
                column_mappings: Array.from(columnMappings.values()).sort((a, b) => a.field_name.localeCompare(b.field_name)),
            };
        }
        if (item.mybatis_mapper) {
            const statementMap = new Map();
            for (const statement of [...(existing.mybatis_mapper?.statements || []), ...item.mybatis_mapper.statements]) {
                statementMap.set(statement.id, statement);
            }
            existing.mybatis_mapper = {
                namespace: item.mybatis_mapper.namespace || existing.mybatis_mapper?.namespace || "",
                xml_files: Array.from(new Set([...(existing.mybatis_mapper?.xml_files || []), ...item.mybatis_mapper.xml_files])).sort(),
                statement_ids: Array.from(new Set([...(existing.mybatis_mapper?.statement_ids || []), ...item.mybatis_mapper.statement_ids])).sort(),
                result_maps: Array.from(new Map([...(existing.mybatis_mapper?.result_maps || []), ...item.mybatis_mapper.result_maps].map((resultMap) => [resultMap.id, resultMap])).values()).sort((a, b) => a.id.localeCompare(b.id)),
                statements: Array.from(statementMap.values()).sort((a, b) => a.id.localeCompare(b.id)),
            };
        }
        existing.source_files = Array.from(new Set([...(existing.source_files || []), ...(item.source_files || [])])).sort();
        const existingPriority = SOURCE_PRIORITY[String(existing.source_kind)] || 0;
        const incomingPriority = SOURCE_PRIORITY[String(item.source_kind)] || 0;
        if (incomingPriority > existingPriority) {
            for (const field of ["source_kind", "source_file", "fqn", "package", "type", "module"]) {
                existing[field] = item[field];
            }
        }
    }
    const result = Array.from(merged.values()).sort((a, b) => {
        const left = `${String(a.simple_name || "").toLowerCase()}::${String(a.fqn || "")}`;
        const right = `${String(b.simple_name || "").toLowerCase()}::${String(b.fqn || "")}`;
        return left.localeCompare(right);
    });
    if (duplicateStrategy === "disambiguate") {
        const counts = new Map();
        for (const item of result) {
            const key = String(item.simple_name || "");
            counts.set(key, (counts.get(key) || 0) + 1);
        }
        for (const item of result) {
            const key = String(item.simple_name || "");
            if ((counts.get(key) || 0) > 1) {
                const moduleName = String(item.module || item.package || item.source_kind || "unknown");
                item.display_name = `${key}[${moduleName}]`;
            }
            else {
                item.display_name = key;
            }
        }
    }
    else {
        for (const item of result) {
            item.display_name = String(item.simple_name || "");
        }
    }
    return enrichInheritedMethods(result);
}
function buildSnapshot(config, options = {}) {
    const files = (0, cache_1.collectWatchedFiles)(config);
    const cacheEntry = (0, cache_1.loadCacheEntry)(config);
    if (!options.forceRefresh && (0, cache_1.cacheIsValid)(config, cacheEntry, files)) {
        if (cacheEntry && cacheEntry.payload && typeof cacheEntry.payload === "object") {
            return [cacheEntry.payload, true];
        }
    }
    const items = [];
    const unsupportedFeatures = new Set();
    const scanWarnings = [];
    const modulePrefixMap = config.module_prefix_map && typeof config.module_prefix_map === "object" ? config.module_prefix_map : {};
    for (const rootPath of (0, cache_1.resolveScanRoots)(config)) {
        const stack = [rootPath];
        while (stack.length > 0) {
            const current = stack.pop();
            const entries = fs.readdirSync(current, { withFileTypes: true });
            for (const entry of entries) {
                const fullPath = path.join(current, entry.name);
                if (entry.isDirectory()) {
                    stack.push(fullPath);
                }
                else if (entry.isFile() && fullPath.endsWith(".java")) {
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
                        }
                        catch (error) {
                            const message = error instanceof Error ? error.message : String(error);
                            scanWarnings.push(`${(0, cache_1.normalizeSnapshotPath)(fullPath)} 扫描失败: ${message}`);
                        }
                    }
                }
            }
        }
    }
    for (const rootPath of (0, cache_1.resolveDesignRoots)(config)) {
        const stack = [rootPath];
        while (stack.length > 0) {
            const current = stack.pop();
            const entries = fs.readdirSync(current, { withFileTypes: true });
            for (const entry of entries) {
                const fullPath = path.join(current, entry.name);
                if (entry.isDirectory()) {
                    stack.push(fullPath);
                }
                else if (entry.isFile() && /design-v\d+\.md$/i.test(entry.name)) {
                    items.push(...parseDesignParticipants(fullPath));
                }
            }
        }
    }
    const byFqn = new Map();
    const bySimpleName = new Map();
    for (const item of items) {
        if (item.fqn) {
            byFqn.set(item.fqn, item);
        }
        const key = String(item.simple_name || "");
        bySimpleName.set(key, [...(bySimpleName.get(key) || []), item]);
    }
    for (const rootPath of inferResourceRoots((0, cache_1.resolveScanRoots)(config))) {
        const stack = [rootPath];
        while (stack.length > 0) {
            const current = stack.pop();
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
                const target = byFqn.get(binding.namespace) ||
                    ((bySimpleName.get(namespaceSimpleName) || []).length === 1 ? (bySimpleName.get(namespaceSimpleName) || [])[0] : null);
                if (!target) {
                    scanWarnings.push(`${(0, cache_1.normalizeSnapshotPath)(fullPath)} 未找到对应的 MyBatis namespace 类: ${binding.namespace}`);
                    continue;
                }
                target.mybatis_mapper = {
                    namespace: binding.namespace,
                    xml_files: [binding.xml_file],
                    statement_ids: binding.statements.map((item) => item.id).sort(),
                    result_maps: binding.result_maps,
                    statements: binding.statements.sort((a, b) => a.id.localeCompare(b.id)),
                };
                target.dependencies = Array.from(new Set([
                    ...(target.dependencies || []),
                    ...binding.result_maps
                        .map((item) => item.type)
                        .filter((item) => Boolean(item))
                        .map((item) => item.split(".").pop() || item),
                    ...binding.statements
                        .flatMap((item) => [item.parameter_type, item.result_type])
                        .filter((item) => Boolean(item))
                        .map((item) => item.split(".").pop() || item),
                ])).sort();
            }
        }
    }
    const duplicateStrategy = String(config.duplicate_strategy || "disambiguate");
    const classes = mergeClasses(items, duplicateStrategy);
    const sourceStats = {};
    for (const item of classes) {
        const sourceKind = String(item.source_kind || "unknown");
        sourceStats[sourceKind] = (sourceStats[sourceKind] || 0) + 1;
    }
    if (sourceStats["java-main"] || sourceStats["java-test"]) {
        unsupportedFeatures.add("framework-proxy");
    }
    const confidence = scanWarnings.length > 0 ? "low" : "medium";
    const payload = {
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
        scan_roots: (0, cache_1.resolveScanRoots)(config).map((item) => (0, cache_1.normalizeSnapshotPath)(item)),
        design_roots: (0, cache_1.resolveDesignRoots)(config).map((item) => (0, cache_1.normalizeSnapshotPath)(item)),
        classes,
    };
    (0, cache_1.saveCacheEntry)(config, payload, files);
    return [payload, false];
}
function matchKeywords(item, keywords) {
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
function filterClasses(snapshot, keywords, limit) {
    const classes = Array.isArray(snapshot.classes) ? snapshot.classes.filter((item) => item && typeof item === "object") : [];
    const filtered = classes.filter((item) => matchKeywords(item, keywords));
    return typeof limit === "number" ? filtered.slice(0, limit) : filtered;
}
function scanModules(options = {}) {
    const config = (0, cache_1.loadConfig)();
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
function resolveMatches(snapshot, query) {
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
function verifyClassExists(options = {}) {
    const config = (0, cache_1.loadConfig)();
    const [snapshot, fromCache] = buildSnapshot(config, { forceRefresh: options.forceRefresh });
    const results = {};
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
function listMethods(options = {}) {
    const config = (0, cache_1.loadConfig)();
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
function getClassDetail(options = {}) {
    const config = (0, cache_1.loadConfig)();
    const [snapshot, fromCache] = buildSnapshot(config, { forceRefresh: options.forceRefresh });
    return {
        from_cache: fromCache,
        query: { class_name: options.className || null, fqn: options.fqn || null },
        matches: resolveMatches(snapshot, { className: options.className || null, fqn: options.fqn || null }),
    };
}
function dumpModuleMapPayload(options = {}) {
    const config = (0, cache_1.loadConfig)();
    if (Array.isArray(options.scanRoots)) {
        config.scan_roots = options.scanRoots;
    }
    if (Array.isArray(options.designRoots)) {
        config.design_roots = options.designRoots;
    }
    const [snapshot] = buildSnapshot(config, { forceRefresh: options.forceRefresh });
    return snapshot;
}
