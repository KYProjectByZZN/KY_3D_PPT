$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

Push-Location $projectRoot
try {
    $env:QT_QPA_PLATFORM = "offscreen"

    python -m pytest -q
    if ($LASTEXITCODE -ne 0) {
        throw "pytest failed with exit code $LASTEXITCODE"
    }

    python -m unittest discover -s tests -q
    if ($LASTEXITCODE -ne 0) {
        throw "unittest failed with exit code $LASTEXITCODE"
    }

    python -m compileall -q generate_ppt.py render_template.py run_desktop.py ppt_generator tools
    if ($LASTEXITCODE -ne 0) {
        throw "compileall failed with exit code $LASTEXITCODE"
    }

    Write-Host "Quality gate passed."
}
finally {
    Pop-Location
}
