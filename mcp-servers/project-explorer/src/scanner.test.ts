#!/usr/bin/env node

import assert from "node:assert/strict";
import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";

import { dumpModuleMapPayload, parseJavaFile } from "./lib/scanner";

function writeTempJavaFile(name: string, content: string): string {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "project-explorer-"));
  const filePath = path.join(directory, name);
  fs.writeFileSync(filePath, content, "utf8");
  return filePath;
}

function writeTempProject(structure: Record<string, string>): string {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "project-explorer-project-"));
  for (const [relativePath, content] of Object.entries(structure)) {
    const filePath = path.join(directory, relativePath);
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, content, "utf8");
  }
  return directory;
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

{
  const projectRoot = writeTempProject({
    "src/main/java/demo/BaseService.java": `package demo;

public class BaseService {
  public String loadById(Long id) {
    return String.valueOf(id);
  }
}
`,
    "src/main/java/demo/EmployeeService.java": `package demo;

public class EmployeeService extends BaseService {
  public void activate(Long id) {
  }
}
`,
  });
  const payload = dumpModuleMapPayload({
    forceRefresh: true,
    scanRoots: [path.join(projectRoot, "src/main/java")],
    designRoots: [],
  });
  const employeeService = payload.classes.find((item) => item.fqn === "demo.EmployeeService");
  assert(employeeService);
  assert(employeeService.inherited_public_methods?.includes("loadById(Long id)"));
  const inheritedDetail = employeeService.method_details?.find((item) => item.signature === "loadById(Long id)");
  assert(inheritedDetail);
  assert.equal(inheritedDetail.inference_source, "inheritance");
  assert.equal(inheritedDetail.inherited_from, "demo.BaseService");
  assert.equal(inheritedDetail.owner_class, "demo.BaseService");
  assert.equal(employeeService.scan_reliability?.method_confidence, "medium");
  assert(employeeService.scan_reliability?.evidence_sources.includes("inheritance"));
  assert.equal(employeeService.scan_reliability?.inherited_methods, 1);
}

{
  const projectRoot = writeTempProject({
    "src/main/java/demo/OrderRecord.java": `package demo;

public class OrderRecord {
  private Long id;
  private String code;
}
`,
    "src/main/java/demo/OrderMapper.java": `package demo;

public interface OrderMapper {
  OrderRecord selectById(Long id);
}
`,
    "src/main/resources/demo/OrderMapper.xml": `<?xml version="1.0" encoding="UTF-8" ?>
<mapper namespace="demo.OrderMapper">
  <select id="selectById" parameterType="java.lang.Long" resultType="demo.OrderRecord">
    select id, code from t_order where id = #{id}
  </select>
</mapper>
`,
  });
  const payload = dumpModuleMapPayload({
    forceRefresh: true,
    scanRoots: [path.join(projectRoot, "src/main/java")],
    designRoots: [],
  });
  const orderMapper = payload.classes.find((item) => item.fqn === "demo.OrderMapper");
  assert(orderMapper?.mybatis_mapper);
  assert.deepEqual(orderMapper.mybatis_mapper?.statement_ids, ["selectById"]);
  const boundMethod = orderMapper.method_details?.find((item) => item.signature === "selectById(Long id)");
  assert(boundMethod?.mybatis_statement);
  assert.equal(boundMethod.mybatis_statement?.id, "selectById");
  assert.equal(boundMethod.mybatis_statement?.kind, "select");
  assert.deepEqual(boundMethod.mybatis_statement?.tables, ["t_order"]);
  assert.equal(orderMapper.scan_reliability?.class_confidence, "medium");
  assert.equal(orderMapper.scan_reliability?.method_confidence, "medium");
  assert(orderMapper.scan_reliability?.evidence_sources.includes("mybatis-xml"));
  assert.equal(orderMapper.scan_reliability?.mybatis_bound_methods, 1);
}

{
  const projectRoot = writeTempProject({
    "src/main/java/demo/UserMapper.java": `package demo;

public interface UserMapper {
  String findName(Long id);
}
`,
    "src/main/resources/demo/UserMapper.xml": `<?xml version="1.0" encoding="UTF-8" ?>
<mapper namespace="demo.UserMapper">
  <select id="findName" parameterType="java.lang.String" resultType="java.lang.Long">
    select id from t_user where id = #{id}
  </select>
</mapper>
`,
  });
  const payload = dumpModuleMapPayload({
    forceRefresh: true,
    scanRoots: [path.join(projectRoot, "src/main/java")],
    designRoots: [],
  });
  assert.equal(payload.confidence, "low");
  const warnings = Array.isArray(payload.scan_quality?.warnings) ? payload.scan_quality.warnings.map(String) : [];
  assert(warnings.some((item) => item.includes("parameterType=java.lang.String")));
  assert(warnings.some((item) => item.includes("resultType=java.lang.Long")));
}

{
  const projectRoot = writeTempProject({
    "src/main/java/demo/OrderView.java": `package demo;

public class OrderView {
  private Long id;
  private String code;
}
`,
    "src/main/java/demo/OrderSummary.java": `package demo;

public class OrderSummary {
  private String code;
}
`,
    "src/main/java/demo/OrderMapper.java": `package demo;

public interface OrderMapper {
  OrderView selectById(Long id);
  OrderSummary selectById(String code);
}
`,
    "src/main/resources/demo/OrderMapper.xml": `<?xml version="1.0" encoding="UTF-8" ?>
<mapper namespace="demo.OrderMapper">
  <resultMap id="orderViewMap" type="demo.OrderView">
    <id property="id" column="id" />
    <result property="code" column="code" />
  </resultMap>
  <select id="selectById" parameterType="java.lang.Long" resultMap="orderViewMap">
    select id, code from t_order where id = #{id}
  </select>
</mapper>
`,
  });
  const payload = dumpModuleMapPayload({
    forceRefresh: true,
    scanRoots: [path.join(projectRoot, "src/main/java")],
    designRoots: [],
  });
  assert.equal(payload.confidence, "medium");
  const orderMapper = payload.classes.find((item) => item.fqn === "demo.OrderMapper");
  const longMethod = orderMapper?.method_details?.find((item) => item.signature === "selectById(Long id)");
  const stringMethod = orderMapper?.method_details?.find((item) => item.signature === "selectById(String code)");
  assert(longMethod?.mybatis_statement);
  assert.equal(longMethod.mybatis_statement?.result_map, "orderViewMap");
  assert.equal(longMethod.mybatis_statement?.result_map_type, "demo.OrderView");
  assert.deepEqual(longMethod.mybatis_statement?.mapped_columns, ["code", "id"]);
  assert.deepEqual(longMethod.mybatis_statement?.mapped_properties, ["code", "id"]);
  assert.equal(stringMethod?.mybatis_statement, null);
}

{
  const filePath = writeTempJavaFile(
    "AuditLog.java",
    `package demo;

import jakarta.persistence.Entity;

@Entity
public class AuditLog {
  private String createdAt;
}
`,
  );
  const parsed = parseJavaFile(filePath, "java-main", {});
  const auditLog = parsed.classes[0];
  assert(auditLog.jpa_entity);
  assert.equal(auditLog.jpa_entity?.entity_kind, "entity");
  assert.equal(auditLog.jpa_entity?.table_name, "AuditLog");
  assert(auditLog.jpa_entity?.candidate_table_names?.includes("AuditLog"));
  assert(auditLog.jpa_entity?.candidate_table_names?.includes("auditlog"));
  assert(auditLog.jpa_entity?.candidate_table_names?.includes("audit_log"));
  const createdAt = auditLog.jpa_entity?.column_mappings.find((item) => item.field_name === "createdAt");
  assert(createdAt);
  assert(createdAt.candidate_column_names?.includes("createdAt"));
  assert(createdAt.candidate_column_names?.includes("createdat"));
  assert(createdAt.candidate_column_names?.includes("created_at"));
}

{
  const filePath = writeTempJavaFile(
    "EmployeeEntity.java",
    `package demo;

import jakarta.persistence.Entity;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;

@Entity
public class EmployeeEntity {
  @ManyToOne
  @JoinColumn(name = "dept_id")
  private Department department;
}
`,
  );
  const parsed = parseJavaFile(filePath, "java-main", {});
  const employeeEntity = parsed.classes[0];
  assert(employeeEntity.jpa_entity);
  assert(employeeEntity.jpa_entity?.relation_fields.includes("department"));
  const departmentColumn = employeeEntity.jpa_entity?.column_mappings.find((item) => item.field_name === "department");
  assert(departmentColumn);
  assert.equal(departmentColumn.column_name, "dept_id");
  assert(departmentColumn.candidate_column_names?.includes("dept_id"));
}

{
  const projectRoot = writeTempProject({
    "src/main/java/demo/BaseEntity.java": `package demo;

import jakarta.persistence.MappedSuperclass;
import jakarta.persistence.Column;

@MappedSuperclass
public class BaseEntity {
  @Column(name = "created_at")
  private String createdAt;
}
`,
    "src/main/java/demo/OrderEntity.java": `package demo;

import jakarta.persistence.Entity;
import jakarta.persistence.Table;

@Entity
@Table(name = "t_order")
public class OrderEntity extends BaseEntity {
  private Long id;
}
`,
  });
  const payload = dumpModuleMapPayload({
    forceRefresh: true,
    scanRoots: [path.join(projectRoot, "src/main/java")],
    designRoots: [],
  });
  const baseEntity = payload.classes.find((item) => item.fqn === "demo.BaseEntity");
  const orderEntity = payload.classes.find((item) => item.fqn === "demo.OrderEntity");
  assert(baseEntity?.jpa_entity);
  assert.equal(baseEntity.jpa_entity?.entity_kind, "mapped-superclass");
  assert.equal(baseEntity.jpa_entity?.table_name, null);
  assert.deepEqual(baseEntity.jpa_entity?.candidate_table_names, []);
  assert(orderEntity?.jpa_entity);
  assert.equal(orderEntity.jpa_entity?.entity_kind, "entity");
  const inheritedColumn = orderEntity.jpa_entity?.column_mappings.find((item) => item.field_name === "createdAt");
  assert(inheritedColumn);
  assert.equal(inheritedColumn.column_name, "created_at");
}

process.stdout.write("project-explorer scanner tests passed\n");
