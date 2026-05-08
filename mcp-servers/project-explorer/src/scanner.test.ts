#!/usr/bin/env node

import assert from "node:assert/strict";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

import { parseJavaFile } from "./lib/scanner";

function writeTempJavaFile(name: string, content: string): string {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "project-explorer-"));
  const filePath = path.join(directory, name);
  fs.writeFileSync(filePath, content, "utf8");
  return filePath;
}

{
  const filePath = writeTempJavaFile(
    "Employee.java",
    `package demo;

import lombok.Data;

@Data
public class Employee {
  private String name;
  private boolean active;
  private final String tenantId = "t1";
}
`,
  );
  const parsed = parseJavaFile(filePath, "java-main", {});
  assert.equal(parsed.classes.length, 1);
  const employee = parsed.classes[0];
  assert(employee.public_methods.includes("getName()"));
  assert(employee.public_methods.includes("setName(String name)"));
  assert(employee.public_methods.includes("isActive()"));
  assert(employee.public_methods.includes("setActive(boolean active)"));
  assert(employee.public_methods.includes("getTenantId()"));
  assert.equal(employee.public_methods.includes("setTenantId(String tenantId)"), false);

  const getName = employee.method_details?.find((item) => item.signature === "getName()");
  assert.equal(getName?.inferred, true);
  assert.equal(getName?.inference_source, "lombok-getter");
  assert.equal(getName?.confidence, "low");
  assert.equal(parsed.unsupported_features.includes("lombok-generated-methods"), false);
}

{
  const filePath = writeTempJavaFile(
    "Profile.java",
    `package demo;

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
`,
  );
  const parsed = parseJavaFile(filePath, "java-main", {});
  const profile = parsed.classes[0];
  assert.equal(profile.public_methods.filter((item) => item === "getNickname()").length, 1);
  assert(profile.public_methods.includes("setAge(Integer age)"));
  const explicitGetter = profile.method_details?.find((item) => item.signature === "getNickname()");
  assert.equal(explicitGetter?.inferred, false);
}

{
  const filePath = writeTempJavaFile(
    "BuilderExample.java",
    `package demo;

import lombok.Builder;

@Builder
public class BuilderExample {
  private String code;
}
`,
  );
  const parsed = parseJavaFile(filePath, "java-main", {});
  assert.equal(parsed.unsupported_features.includes("lombok-generated-methods"), true);
}

process.stdout.write("project-explorer scanner tests passed\n");
