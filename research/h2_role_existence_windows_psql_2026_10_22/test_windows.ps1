#requires -Version 7.4
$ErrorActionPreference='Stop'
Push-Location $PSScriptRoot
try {
    python (Join-Path $PSScriptRoot 'test_offline.py')
    if ($LASTEXITCODE -ne 0) { throw 'Python negative tests failed' }
    python (Join-Path $PSScriptRoot 'test_ca_bundle.py')
    if ($LASTEXITCODE -ne 0) { throw 'Pinned CA offline tests failed' }
    $good=@('absent','exists')
    $bad=@('missing_rollback','extra_statement','sql_error','timeout','wrong_role','wrong_database','wrong_guard','multiple_rows','malformed_header','exit_failure','stderr_noise')
    $count=0
    foreach($case in ($good+$bad)) {
        $receipt=Join-Path ([IO.Path]::GetTempPath()) ("h2-synthetic-"+[guid]::NewGuid().ToString('N')+'.json')
        try {
            # These process messages are synthetic-only and contain no real credentials.
            $syntheticOutput = @(& (Join-Path $PSScriptRoot 'Invoke-H2RoleExistence.ps1') -OfflineSelfTest -MockScenario $case -ReceiptPath $receipt 2>&1)
            $exitCode=$LASTEXITCODE
            if ($good -contains $case -and ($exitCode -ne 0 -or -not (Test-Path $receipt))) {
                Write-Host "SYNTHETIC_POSITIVE_DIAGNOSTIC case=$case exit=$exitCode receipt=$([bool](Test-Path $receipt))"
                foreach ($line in $syntheticOutput) { Write-Host "MOCK_ONLY: $line" }
            }
            if ($good -contains $case) {
                if ($exitCode -ne 0 -or -not (Test-Path $receipt)) { throw "positive $case did not produce receipt" }
                python (Join-Path $PSScriptRoot 'verify_receipt.py') $receipt --synthetic-only
                if ($LASTEXITCODE -ne 0) { throw "positive $case receipt rejected" }
            } else {
                if ($exitCode -eq 0 -or (Test-Path $receipt)) { throw "negative $case failed open" }
            }
            Write-Host "PASS $case"
            $count++
        } finally { Remove-Item -LiteralPath $receipt -Force -ErrorAction SilentlyContinue }
    }
    Write-Host "SYNTHETIC_WINDOWS_MOCK_PASS $count/$($good.Count+$bad.Count) -- NO NEON; NO TLS PROOF"
} finally { Pop-Location }
