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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const strict_1 = __importDefault(require("node:assert/strict"));
const fs = __importStar(require("node:fs"));
const os = __importStar(require("node:os"));
const path = __importStar(require("node:path"));
const scanner_1 = require("./lib/scanner");
function writeTempJavaFile(name, content) {
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), "project-explorer-"));
    const filePath = path.join(directory, name);
    fs.writeFileSync(filePath, content, "utf8");
    return filePath;
}
{
    const filePath = writeTempJavaFile("Employee.java", `package demo;

import lombok.Data;

@Data
public class Employee {
  private String name;
  private boolean active;
  private final String tenantId = "t1";
}
`);
    const parsed = (0, scanner_1.parseJavaFile)(filePath, "java-main", {});
    strict_1.default.equal(parsed.classes.length, 1);
    const employee = parsed.classes[0];
    (0, strict_1.default)(employee.public_methods.includes("getName()"));
    (0, strict_1.default)(employee.public_methods.includes("setName(String name)"));
    (0, strict_1.default)(employee.public_methods.includes("isActive()"));
    (0, strict_1.default)(employee.public_methods.includes("setActive(boolean active)"));
    (0, strict_1.default)(employee.public_methods.includes("getTenantId()"));
    strict_1.default.equal(employee.public_methods.includes("setTenantId(String tenantId)"), false);
    const getName = employee.method_details?.find((item) => item.signature === "getName()");
    strict_1.default.equal(getName?.inferred, true);
    strict_1.default.equal(getName?.inference_source, "lombok-getter");
    strict_1.default.equal(getName?.confidence, "low");
    strict_1.default.equal(parsed.unsupported_features.includes("lombok-generated-methods"), false);
}
{
    const filePath = writeTempJavaFile("Profile.java", `package demo;

import lombok.Getter;
import lombok.Setter;

public class Profile {
  @Getter
  private String nickname;

  @Setter
  private Integer age;

  public String getNickname() {
    return nickname;
  }
}
`);
    const parsed = (0, scanner_1.parseJavaFile)(filePath, "java-main", {});
    const profile = parsed.classes[0];
    strict_1.default.equal(profile.public_methods.filter((item) => item === "getNickname()").length, 1);
    (0, strict_1.default)(profile.public_methods.includes("setAge(Integer age)"));
    const explicitGetter = profile.method_details?.find((item) => item.signature === "getNickname()");
    strict_1.default.equal(explicitGetter?.inferred, false);
}
{
    const filePath = writeTempJavaFile("BuilderExample.java", `package demo;

import lombok.Builder;

@Builder
public class BuilderExample {
  private String code;
}
`);
    const parsed = (0, scanner_1.parseJavaFile)(filePath, "java-main", {});
    strict_1.default.equal(parsed.unsupported_features.includes("lombok-generated-methods"), true);
}
process.stdout.write("project-explorer scanner tests passed\n");
