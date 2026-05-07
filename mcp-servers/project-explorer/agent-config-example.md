# project-explorer MCP 配置示例

本文给出把 `project-explorer` 配置到 agent / IDE 上的最小示例。

当前仓库路径：

- 工作区：`D:\project\SDD`
- MCP Server（TypeScript 源码）：`D:\project\SDD\mcp-servers\project-explorer\src\server.ts`
- MCP Server（运行入口）：`D:\project\SDD\mcp-servers\project-explorer\dist\server.js`
- Node：建议直接使用系统里的 `node` / `npx`

如果后续这个 MCP 被发布到 npm，推荐优先改成 `npx` 启动，而不是继续写死本地源码路径。

## 1. 通用 MCP JSON 配置

大多数支持 MCP 的工具都可以使用下面这段 JSON，只是配置文件路径不同：

```json
{
  "mcpServers": {
    "project-explorer": {
      "command": "node",
      "args": [
        "D:\\project\\SDD\\mcp-servers\\project-explorer\\dist\\server.js"
      ]
    }
  }
}
```

说明：

- 运行入口使用 `dist/server.js`
- TS 源码位于 `src/`
- 当前实现会优先使用 `mcp-servers/project-explorer/config.yaml`
- 本地开发若改了 TS 源码，记得先执行 `npm install` 和 `npm run build`

## 1.1 已发布后的 `npx` 通用配置

如果后续你把这个 MCP 发布到了 npm，推荐改成下面这种配置：

```json
{
  "mcpServers": {
    "project-explorer": {
      "command": "npx",
      "args": [
        "-y",
        "<发布后的包名>"
      ]
    }
  }
}
```

带版本号示例：

```json
{
  "mcpServers": {
    "project-explorer": {
      "command": "npx",
      "args": [
        "-y",
        "<发布后的包名>@0.1.0"
      ]
    }
  }
}
```

说明：

- 把 `<发布后的包名>` 替换成你实际发布到 npm 的包名，例如 `project-explorer-mcp`
- 如果你的包安装后默认暴露了 console script，这种写法最合适
- 这是后续最推荐的 agent 配置方式，因为它不依赖本地工作区绝对路径

## 1.2 已发布后的 `npm exec` / `npx --package` 通用配置

如果你更希望显式指定包名，也可以使用 `npx --package`：

```json
{
  "mcpServers": {
    "project-explorer": {
      "command": "npx",
      "args": [
        "-y",
        "--package",
        "<发布后的包名>",
        "<发布后的可执行入口>"
      ]
    }
  }
}
```

如果你使用 `npm exec`，也可以写成：

```json
{
  "mcpServers": {
    "project-explorer": {
      "command": "npm",
      "args": [
        "exec",
        "--yes",
        "--package",
        "<发布后的包名>",
        "--",
        "<发布后的可执行入口>"
      ]
    }
  }
}
```

## 2. Codex CLI / Codex App 示例

配置文件位置：

- `~/.codex/config.json`

示例：

```json
{
  "mcpServers": {
    "project-explorer": {
      "command": "node",
      "args": [
        "D:\\project\\SDD\\mcp-servers\\project-explorer\\dist\\server.js"
      ]
    }
  }
}
```

如果你使用 `codex mcp add` 一类的命令行能力，也可以把上面的 `command + args` 写进去，效果等价。

如果改成发布版，Codex 里推荐这样写：

```json
{
  "mcpServers": {
    "project-explorer": {
      "command": "npx",
      "args": [
        "-y",
        "<发布后的包名>"
      ]
    }
  }
}
```

## 3. Cursor 工作区示例

配置文件位置：

- `D:\project\SDD\.cursor\mcp.json`

示例：

```json
{
  "mcpServers": {
    "project-explorer": {
      "command": "node",
      "args": [
        "D:\\project\\SDD\\mcp-servers\\project-explorer\\dist\\server.js"
      ]
    }
  }
}
```

如果改成发布版，Cursor 示例：

```json
{
  "mcpServers": {
    "project-explorer": {
      "command": "npx",
      "args": [
        "-y",
        "<发布后的包名>"
      ]
    }
  }
}
```

## 4. Kiro 工作区示例

配置文件位置：

- `D:\project\SDD\.kiro\settings\mcp.json`

示例：

```json
{
  "mcpServers": {
    "project-explorer": {
      "command": "node",
      "args": [
        "D:\\project\\SDD\\mcp-servers\\project-explorer\\dist\\server.js"
      ]
    }
  }
}
```

如果改成发布版，Kiro 示例：

```json
{
  "mcpServers": {
    "project-explorer": {
      "command": "npx",
      "args": [
        "-y",
        "<发布后的包名>"
      ]
    }
  }
}
```

## 5. VS Code / Copilot MCP 扩展示例

配置文件位置：

- `D:\project\SDD\.vscode\mcp.json`

示例：

```json
{
  "mcpServers": {
    "project-explorer": {
      "command": "node",
      "args": [
        "D:\\project\\SDD\\mcp-servers\\project-explorer\\dist\\server.js"
      ]
    }
  }
}
```

## 6. Claude Code / Claude Desktop 全局示例

配置文件位置：

- `~/.claude/claude_desktop_config.json`

示例：

```json
{
  "mcpServers": {
    "project-explorer": {
      "command": "node",
      "args": [
        "D:\\project\\SDD\\mcp-servers\\project-explorer\\dist\\server.js"
      ]
    }
  }
}
```

## 7. 本地 CLI 验证命令

在真正接到 agent 前，可以先本地验证：

按关键词扫描：

```powershell
$argsJson = "{'keywords':['payment'],'limit':10,'force_refresh':true}"
node D:\project\SDD\mcp-servers\project-explorer\dist\server.js --tool scan_modules --arguments $argsJson
```

校验类是否存在：

```powershell
$argsJson = "{'class_names':['PaymentReviewService','FooBarNotExist'],'force_refresh':false}"
node D:\project\SDD\mcp-servers\project-explorer\dist\server.js --tool verify_class_exists --arguments $argsJson
```

查看类详情：

```powershell
$argsJson = "{'class_name':'PaymentReviewService'}"
node D:\project\SDD\mcp-servers\project-explorer\dist\server.js --tool get_class_detail --arguments $argsJson
```

刷新 `module-map.json` 快照：

```powershell
python D:\project\SDD\scripts\refresh_module_map.py --force-refresh
```

## 8. 连接成功后建议验证的 Tool

建议在 agent 中至少验证这三个调用：

- `scan_modules`
- `verify_class_exists`
- `get_class_detail`

如果这三个都能正常返回，说明 `project-explorer` 已经成功挂到 agent 上了。

## 9. 从本地源码版切到发布版时要改什么

只需要替换 MCP 配置里的这两项：

- 把 `command` 从 `node` 改成 `npx` 或 `npm`
- 把 `args` 从本地 `dist/server.js` 路径改成发布后的包名或可执行入口

建议优先顺序：

1. 已发布到 npm 并暴露 console script：优先用 `npx -y <发布后的包名>`
2. 已发布但需要显式指定执行入口：用 `npx -y --package <发布后的包名> <发布后的可执行入口>`
3. 本地开发调试阶段：继续用当前文档里的源码路径方式
