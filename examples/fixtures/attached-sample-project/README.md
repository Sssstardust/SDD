# Attached Sample Project

这个目录是 SDD 工具仓库的示例附着项目。

用途：

- 为 `project-explorer` / `module-map` 提供可扫描的 Java 实现示例
- 验证 `Gate 2 / Gate 5` 的真实实现追溯能力
- 演示“SDD 工具仓库附着外部目标项目”的使用方式

相关使用手册：

- [docs/attached-project-mode.md](D:/project/SDD/docs/attached-project-mode.md)
- [docs/team-onboarding.md](D:/project/SDD/docs/team-onboarding.md)

约束：

- 这里的源码是 fixture，不是 SDD 工具本体代码
- 若实际接入团队项目，应将 `.spec/attached-project.json` 指向真实业务仓库
