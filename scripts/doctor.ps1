param(
  [switch]$Strict
)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$script:HasFailure = $false
$script:HasWarning = $false

function Write-Check {
  param(
    [string]$Level,
    [string]$Message
  )

  $prefix = switch ($Level) {
    "OK" { "[OK]" }
    "WARN" { "[WARN]" }
    "FAIL" { "[FAIL]" }
    default { "[INFO]" }
  }

  Write-Host "$prefix $Message"

  if ($Level -eq "FAIL") {
    $script:HasFailure = $true
  }
  if ($Level -eq "WARN") {
    $script:HasWarning = $true
  }
}

function Resolve-RepoRoot {
  return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Test-CommandAvailable {
  param([string]$Command)
  return $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

function Invoke-Capture {
  param(
    [string]$Command,
    [string[]]$Arguments
  )

  try {
    $output = & $Command @Arguments 2>&1
    return @{
      ExitCode = $LASTEXITCODE
      Output = ($output -join "`n")
    }
  } catch {
    return @{
      ExitCode = 1
      Output = $_.Exception.Message
    }
  }
}

function Test-Version {
  param(
    [string]$Name,
    [string]$Command,
    [string[]]$Arguments,
    [int]$RequiredMajor,
    [int]$RequiredMinor = 0
  )

  if (-not (Test-CommandAvailable $Command)) {
    Write-Check "FAIL" "$Name was not found. Please install it first."
    return
  }

  $result = Invoke-Capture $Command $Arguments
  $text = $result.Output.Trim()
  if ($result.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($text)) {
    Write-Check "FAIL" "$Name version check failed: $text"
    return
  }

  $match = [regex]::Match($text, "(\d+)\.(\d+)(?:\.(\d+))?")
  if (-not $match.Success) {
    Write-Check "WARN" "$Name is installed, but the version could not be parsed: $text"
    return
  }

  $major = [int]$match.Groups[1].Value
  $minor = [int]$match.Groups[2].Value
  if ($major -lt $RequiredMajor -or ($major -eq $RequiredMajor -and $minor -lt $RequiredMinor)) {
    Write-Check "FAIL" "$Name version is too old: $text. Required >= $RequiredMajor.$RequiredMinor."
    return
  }

  Write-Check "OK" "$Name is available: $text"
}

function Test-PathRequired {
  param(
    [string]$Path,
    [string]$Description
  )

  if (Test-Path $Path) {
    Write-Check "OK" "$Description exists: $Path"
  } else {
    Write-Check "FAIL" "$Description is missing: $Path"
  }
}

function Test-McpCli {
  param(
    [string]$Name,
    [string]$ServerPath,
    [string]$Tool,
    [string]$ArgumentsJson
  )

  if (-not (Test-Path $ServerPath)) {
    Write-Check "FAIL" "$Name MCP entrypoint does not exist: $ServerPath"
    return
  }

  if (-not (Test-CommandAvailable "node")) {
    Write-Check "FAIL" "$Name MCP requires Node.js."
    return
  }

  $result = Invoke-Capture -Command "node" -Arguments @($ServerPath, "--tool", $Tool, "--arguments", $ArgumentsJson)
  if ($result.ExitCode -eq 0) {
    Write-Check "OK" "$Name MCP smoke test passed: $Tool"
  } else {
    Write-Check "FAIL" "$Name MCP smoke test failed: $($result.Output)"
  }
}

function Find-SecurityWarnings {
  param([string]$Root)

  $patterns = @(
    "password\s*[:=]\s*['""]?[^'""\s`$][^'""\s,}]+",
    "jdbc:[^`r`n]+",
    "(mysql|postgres|postgresql|oracle)://[^`r`n]+:[^`r`n@`$]+@",
    "AKIA[0-9A-Z]{16}",
    "secret[_-]?key\s*[:=]\s*['""]?[^'""\s]+"
  )
  $roots = @(
    (Join-Path $Root "config"),
    (Join-Path $Root ".spec")
  )
  $files = @()
  foreach ($candidate in $roots) {
    if (Test-Path $candidate) {
      $files += Get-ChildItem -Path $candidate -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @(".json", ".yaml", ".yml", ".env", ".txt", ".md") }
    }
  }
  $envFiles = Get-ChildItem -Path $Root -Force -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like ".env*" -and $_.Name -ne ".env.example" }
  $files += $envFiles

  $warnings = @()
  foreach ($file in $files) {
    $text = Get-Content -Raw -ErrorAction SilentlyContinue -LiteralPath $file.FullName
    if ([string]::IsNullOrWhiteSpace($text)) {
      continue
    }
    foreach ($pattern in $patterns) {
      if ($text -match $pattern) {
        $relative = Resolve-Path -Relative -LiteralPath $file.FullName
        $warnings += "$relative matches $pattern"
        break
      }
    }
  }
  return $warnings
}

function Test-JsonFileReady {
  param(
    [string]$Path,
    [string]$Description
  )
  if (-not (Test-Path $Path)) {
    Write-Check "WARN" "$Description is missing: $Path"
    return
  }
  try {
    $null = Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json
    Write-Check "OK" "$Description is valid JSON: $Path"
  } catch {
    Write-Check "WARN" "$Description is not valid JSON: $($_.Exception.Message)"
  }
}

$repoRoot = Resolve-RepoRoot
Set-Location $repoRoot

Write-Host "SDD Doctor"
Write-Host "Repo: $repoRoot"
Write-Host ""

Write-Host "== Toolchain =="
Test-Version -Name "Python" -Command "python" -Arguments @("--version") -RequiredMajor 3 -RequiredMinor 13
Test-Version -Name "Node.js" -Command "node" -Arguments @("--version") -RequiredMajor 18

if (Test-CommandAvailable "javac") {
  $javac = Invoke-Capture -Command "javac" -Arguments @("--version")
  if ($javac.ExitCode -eq 0) {
    Write-Check "OK" "Java javac is available: $($javac.Output.Trim())"
  } else {
    Write-Check "WARN" "javac exists, but version check failed: $($javac.Output)"
  }
} else {
  Write-Check "WARN" "javac was not found; Gate 5 Java verification may be unavailable."
}

Write-Host ""
Write-Host "== Workspace =="
Test-PathRequired -Path (Join-Path $repoRoot "README.md") -Description "README"
Test-PathRequired -Path (Join-Path $repoRoot "scripts\run_pipeline.py") -Description "Pipeline entry"
Test-PathRequired -Path (Join-Path $repoRoot "skills\sdd-assistant\SKILL.md") -Description "sdd-assistant Skill"
Test-PathRequired -Path (Join-Path $repoRoot "skills\requirement-analyzer\SKILL.md") -Description "requirement-analyzer Skill"
Test-PathRequired -Path (Join-Path $repoRoot "skills\sdd-generation\SKILL.md") -Description "sdd-generation Skill"
Test-PathRequired -Path (Join-Path $repoRoot "docs\agent-integration.md") -Description "Agent integration doc"

Write-Host ""
Write-Host "== MCP =="
$projectExplorer = Join-Path $repoRoot "mcp-servers\project-explorer\dist\server.js"
$archStandard = Join-Path $repoRoot "mcp-servers\arch-standard\dist\server.js"
Test-PathRequired -Path $projectExplorer -Description "project-explorer MCP dist"
Test-PathRequired -Path $archStandard -Description "arch-standard MCP dist"

Test-McpCli -Name "arch-standard" -ServerPath $archStandard -Tool "list_rules" -ArgumentsJson "{}"
Test-McpCli -Name "project-explorer" -ServerPath $projectExplorer -Tool "scan_modules" -ArgumentsJson "{'keywords':['payment'],'limit':1,'force_refresh':false}"

Write-Host ""
Write-Host "== Attached Project =="
$attachment = Invoke-Capture -Command "python" -Arguments @("scripts\run_pipeline.py", "show-attachment")
if ($attachment.ExitCode -eq 0) {
  Write-Check "OK" "Attached project config is readable."
  Write-Host $attachment.Output
} else {
  Write-Check "WARN" "Attached project config could not be read. Run onboard-project for first-time setup."
}

Write-Host ""
Write-Host "== Baseline =="
$baselineRoot = Join-Path $repoRoot ".spec\baselines"
if (Test-Path $baselineRoot) {
  $baselineDirs = Get-ChildItem -Path $baselineRoot -Directory -ErrorAction SilentlyContinue
  if ($baselineDirs.Count -gt 0) {
    Write-Check "OK" "Baseline buckets found: $($baselineDirs.Count)"
  } else {
    Write-Check "WARN" "Baseline root exists but contains no buckets."
  }
} else {
  Write-Check "WARN" "Baseline root is missing. Run refresh-baseline after onboarding."
}

Write-Host ""
Write-Host "== PolyQuery =="
Test-PathRequired -Path (Join-Path $repoRoot "config\polyquery.example.json") -Description "PolyQuery example config"
Test-JsonFileReady -Path (Join-Path $repoRoot "config\polyquery.json") -Description "Local PolyQuery config"

Write-Host ""
Write-Host "== Gate Smoke Test =="
$gateSmoke = Invoke-Capture -Command "python" -Arguments @("scripts\doctor_smoke.py")
if ($gateSmoke.ExitCode -eq 0) {
  Write-Check "OK" "Gate smoke test passed."
} else {
  Write-Check "FAIL" "Gate smoke test failed: $($gateSmoke.Output)"
}

Write-Host ""
Write-Host "== Security =="
$securityWarnings = Find-SecurityWarnings -Root $repoRoot
if ($securityWarnings.Count -eq 0) {
  Write-Check "OK" "No obvious plaintext credentials found in config/.spec/.env files."
} else {
  foreach ($warning in $securityWarnings) {
    Write-Check "WARN" "Potential plaintext secret: $warning"
  }
}

Write-Host ""
if ($script:HasFailure) {
  Write-Check "FAIL" "Doctor finished with failures."
  exit 1
}

if ($Strict -and $script:HasWarning) {
  Write-Check "FAIL" "Doctor finished with warnings; Strict mode treats warnings as failures."
  exit 1
}

if ($script:HasWarning) {
  Write-Check "WARN" "Doctor finished with warnings; local source integration is not blocked."
  exit 0
}

Write-Check "OK" "Doctor finished. This environment is ready for phase-1 agent integration."
