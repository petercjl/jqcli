$ErrorActionPreference = "Stop"

function Find-JqcliRepo {
    $Candidates = @()
    if ($env:JQCLI_REPO) {
        $Candidates += $env:JQCLI_REPO
    }
    $Candidates += (Get-Location).Path
    $Candidates += "D:\project\jqcli"

    foreach ($Candidate in $Candidates) {
        if (-not $Candidate) {
            continue
        }
        $Current = Resolve-Path -LiteralPath $Candidate -ErrorAction SilentlyContinue
        while ($Current) {
            $Path = $Current.Path
            $Pyproject = Join-Path $Path "pyproject.toml"
            if ((Test-Path -LiteralPath $Pyproject) -and ((Get-Content -LiteralPath $Pyproject -Raw) -match 'name\s*=\s*"jqcli"')) {
                return $Path
            }
            $Parent = Split-Path -Parent $Path
            if (-not $Parent -or $Parent -eq $Path) {
                break
            }
            $Current = Resolve-Path -LiteralPath $Parent -ErrorAction SilentlyContinue
        }
    }

    throw "jqcli repository not found. Set JQCLI_REPO or run this script from the jqcli workspace."
}

$RepoRoot = Find-JqcliRepo
$Jqcli = Join-Path $RepoRoot ".venv\Scripts\jqcli.exe"
$BaseArgs = @("--format", "json", "--non-interactive", "--timeout", "30")

if (-not (Test-Path -LiteralPath $Jqcli)) {
    throw "jqcli.exe not found at $Jqcli. Run: uv sync --extra test"
}

function Invoke-JqcliJson {
    param(
        [string[]] $Command,
        [string] $StdinText = $null
    )

    if ($null -ne $StdinText) {
        $Output = $StdinText | & $Jqcli @BaseArgs @Command 2>&1
    } else {
        $Output = & $Jqcli @BaseArgs @Command 2>&1
    }
    if ($LASTEXITCODE -ne 0) {
        throw "jqcli $($Command -join ' ') failed: $Output"
    }
    return ($Output | Out-String | ConvertFrom-Json)
}

$Name = "jqcli_skill_smoke_" + (Get-Date -Format "yyyyMMdd_HHmmss")
$CreatedId = $null
$CompileId = $null
$Summary = [ordered]@{}

$Code1 = @'
def initialize(context):
    pass


def handle_data(context, data):
    pass
'@

$Code2 = @'
def initialize(context):
    g.note = "jqcli skill smoke"


def handle_data(context, data):
    pass
'@

try {
    $Created = Invoke-JqcliJson @("strategy", "new", $Name, "--code-stdin") $Code1
    $CreatedId = [string] $Created.id
    $Summary.strategy_new_ok = [bool] $CreatedId

    $Edited = Invoke-JqcliJson @("strategy", "edit", $CreatedId, "--name", ($Name + "_edited"), "--code-stdin") $Code2
    $Summary.strategy_edit_ok = [bool] ($Edited.id -or $Edited.ok -or $Edited.data)

    $Shown = Invoke-JqcliJson @("strategy", "show", $CreatedId, "--code")
    $Summary.strategy_show_created_ok = [bool] $Shown.id

    $Compiled = Invoke-JqcliJson @("backtest", "run", $CreatedId, "--start", "2024-01-02", "--end", "2024-01-03", "--capital", "1000000", "--compile")
    $CompileId = [string] $Compiled.id
    $Summary.backtest_compile_run_ok = [bool] $CompileId

    if ($CompileId) {
        Start-Sleep -Seconds 3
        $CompileResult = Invoke-JqcliJson @("backtest", "result", $CompileId)
        $CompileLogs = Invoke-JqcliJson @("backtest", "logs", $CompileId, "--offset", "0")
        $Summary.backtest_compile_result_ok = [bool] $CompileResult.id
        $Summary.backtest_compile_logs_ok = $null -ne $CompileLogs.logs

        $RemovedCompile = Invoke-JqcliJson @("backtest", "rm", $CompileId, "--compile", "--yes")
        $Summary.backtest_compile_rm_ok = [bool] ($RemovedCompile.ok -or $RemovedCompile.id -or $RemovedCompile.status -eq 0)
        $CompileId = $null
    }
} finally {
    if ($CompileId) {
        try {
            $null = Invoke-JqcliJson @("backtest", "rm", $CompileId, "--compile", "--yes")
        } catch {
            $Summary.backtest_compile_cleanup_error = $_.Exception.Message
        }
    }

    if ($CreatedId) {
        try {
            $Removed = Invoke-JqcliJson @("strategy", "rm", $CreatedId, "--yes")
            $Summary.strategy_rm_ok = [bool] ($Removed.ok -or $Removed.id -or $Removed.status -eq 0)
        } catch {
            $Summary.strategy_cleanup_error = $_.Exception.Message
        }
    }
}

$Summary | ConvertTo-Json -Depth 5
