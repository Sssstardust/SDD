# SDD Pipeline MCP Server

Local stdio MCP server for the SDD developer MVP.

The public tool contract is designed so it can later be backed by a long-running
service, while this first implementation stays simple and executes:

```powershell
python sdd_core/run_pipeline.py --json <command>
```

## Tools

- `sdd_doctor`
- `sdd_attach_project`
- `sdd_inspect_flow`
- `sdd_bootstrap_feature`
- `sdd_validate_design`
- `sdd_continue_flow`

All tools return a normalized JSON envelope as MCP text content:

```json
{
  "status": "ok",
  "blocking": false,
  "stage": "validate-design",
  "feature": "auth_login",
  "message": "validate completed",
  "artifacts": [],
  "errors": [],
  "warnings": [],
  "next_action": {
    "type": "run_command",
    "target": "python sdd_core/run_pipeline.py release-gate specs/auth_login",
    "reason": "Follow the SDD flow state's next command"
  },
  "raw": {}
}
```

## Example MCP Client Config

```json
{
  "mcpServers": {
    "sdd-pipeline": {
      "command": "python",
      "args": ["D:/project/SDD/mcp-servers/sdd-pipeline/server.py"]
    }
  }
}
```

## Smoke Test

```powershell
python mcp-servers/sdd-pipeline/smoke_test.py
```
