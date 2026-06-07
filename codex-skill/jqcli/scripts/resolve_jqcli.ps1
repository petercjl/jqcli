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

if (-not (Test-Path -LiteralPath $Jqcli)) {
    throw "jqcli.exe not found at $Jqcli. Run: uv sync --extra test"
}

Write-Output $Jqcli
