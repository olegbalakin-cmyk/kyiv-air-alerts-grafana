#requires -Version 7.4
<#
Actual PostgreSQL 18 Windows psql client probe. NEVER execute the H2 launcher,
approved SQL or any Neon route. The only connection destination is IPv4 loopback
127.0.0.1, at a locally checked unused port; no -f, -c, or SQL input.
Use -ManualConsole ONLY in a local interactive Windows Terminal with DUMMY input.
This script deliberately does not log raw stdout, stderr or console input.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PsqlPath,
    [switch]$ManualConsole
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not $IsWindows) { throw 'WINDOWS_ONLY' }
if ([Environment]::GetEnvironmentVariable('H2_NO_NEON') -ne '1') {
    throw 'H2_NO_NEON=1_REQUIRED'
}
if ($ManualConsole) {
    if ([Environment]::GetEnvironmentVariable('CI') -eq 'true' -or
        [Console]::IsInputRedirected -or [Console]::IsOutputRedirected -or
        [Console]::IsErrorRedirected) {
        throw 'MANUAL_TEST_REQUIRES_INTERACTIVE_WINDOWS_CONSOLE_NO_REDIRECTION'
    }
}
$client = [IO.Path]::GetFullPath($PsqlPath)
if (-not [IO.File]::Exists($client)) { throw 'CLIENT_MISSING_FAIL_CLOSED' }
$version = (& $client --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'CLIENT_VERSION_EXECUTION_FAILED' }
$guard = '^psql \(PostgreSQL\) 18\.\d+(?:\.\d+)?$'
$launcher = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'Invoke-H2RoleExistence.ps1'))
if (-not $launcher.Contains("version -cnotmatch '$guard'")) {
    throw 'LAUNCHER_VERSION_GUARD_DRIFT'
}
if ($version -cnotmatch $guard) { throw 'CLIENT_MUST_BE_PG18' }
foreach ($bad in @('psql (PostgreSQL) 17.11','psql (PostgreSQL) 19.0',
                    'psql (PostgreSQL) 18.6 forged','psql (PostgreSQL) 18.')) {
    if ($bad -cmatch $guard) { throw 'VERSION_GUARD_BAD_FIXTURE_ACCEPTED' }
}
if ([IO.File]::Exists((Join-Path $PSScriptRoot 'definitely-no-such-psql.exe'))) {
    throw 'MISSING_CLIENT_FIXTURE_NOT_MISSING'
}
$digest = (Get-FileHash -LiteralPath $client -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "REAL_CLIENT_VERSION=$version"
Write-Host "REAL_CLIENT_PATH=$client"
Write-Host "REAL_CLIENT_SHA256=$digest"
Write-Host 'REAL_CLIENT_VERSION_GUARD=PASS (real client and missing/invalid/unsupported negatives)'

# OS-assigned loopback port, independently re-bound successfully to confirm it
# was unused immediately before testing. No listener remains active.
$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
$listener.Start()
try {
    $port = ([Net.IPEndPoint]$listener.LocalEndpoint).Port
} finally {
    $listener.Stop()
}
$check = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $port)
$check.Start()
$check.Stop()
Write-Host "LOOPBACK_TARGET=127.0.0.1:$port"
Write-Host 'LOOPBACK_PORT_BIND_PROOF=PASS'

$arguments = [string[]]@('-X','-W','-h','127.0.0.1','-p',[string]$port,
                         '-U','h2_dummy_local','-d','h2_dummy_local')
if (($arguments -join ' ') -match 'neon|\.sql| -f | -c |pooler') {
    throw 'FORBIDDEN_TARGET_OR_SQL'
}
$si = [Diagnostics.ProcessStartInfo]::new()
$si.FileName = $client
$si.UseShellExecute = $false
$si.CreateNoWindow = $false
$si.RedirectStandardOutput = $true
$si.RedirectStandardError = $true
$si.RedirectStandardInput = $false
$si.StandardOutputEncoding = [Text.UTF8Encoding]::new($false)
$si.StandardErrorEncoding = [Text.UTF8Encoding]::new($false)
$si.WorkingDirectory = [IO.Path]::GetDirectoryName($client)
foreach ($arg in $arguments) { [void]$si.ArgumentList.Add($arg) }
$keep = @('SystemRoot','WINDIR','PATH','TEMP','TMP','USERPROFILE',
          'APPDATA','LOCALAPPDATA','HOMEDRIVE','HOMEPATH')
$si.Environment.Clear()
foreach ($name in $keep) {
    $value = [Environment]::GetEnvironmentVariable($name)
    if ($null -ne $value) { $si.Environment[$name] = $value }
}
$si.Environment['PGSSLMODE'] = 'verify-full'
$si.Environment['PGSSLROOTCERT'] = 'system'
$si.Environment['PGGSSENCMODE'] = 'disable'
$si.Environment['PGCONNECT_TIMEOUT'] = '5'
$si.Environment['PGCLIENTENCODING'] = 'UTF8'
$si.Environment['PGAPPNAME'] = 'h2-psql18-local-offline-prompt-test'
$si.Environment['PGPASSFILE'] = Join-Path ([IO.Path]::GetTempPath()) ('h2-not-created-' + [guid]::NewGuid().ToString('N'))
if (($si.ArgumentList -join ' ') -match '(?i)password|\.sql|neon') {
    throw 'SENSITIVE_OR_FORBIDDEN_ARGUMENT'
}
if ($si.Environment.Keys -contains 'PGPASSWORD') { throw 'PASSWORD_IN_CHILD_ENV' }
Write-Host 'PROMPT_EXPERIMENT=REAL_PSQL18_REDIRECT_STDERR_TRUE_STDIN_FALSE'
if ($ManualConsole) {
    Write-Host 'ENTER ONLY THE DUMMY TEST PASSWORD h2PROMPT_TEST_9397; no real credentials.'
    Write-Host 'Observe whether Password for user h2_dummy_local: is visible and whether typed characters are hidden.'
    Write-Host 'There is a 20-second deadline. No transcript/screen recording should be active.'
}
$p = [Diagnostics.Process]::new()
$p.StartInfo = $si
$started = $false
$timedOut = $false
$watch = [Diagnostics.Stopwatch]::StartNew()
try {
    if (-not $p.Start()) { throw 'CHILD_START_FAILED' }
    $started = $true
    $outTask = $p.StandardOutput.ReadToEndAsync()
    $errTask = $p.StandardError.ReadToEndAsync()
    if (-not $p.WaitForExit(20000)) {
        $timedOut = $true
        try { $p.Kill($true) } catch {}
        [void]$p.WaitForExit(1500)
    }
    $watch.Stop()
    $stdout = $outTask.GetAwaiter().GetResult()
    $stderr = $errTask.GetAwaiter().GetResult()
    if ([Text.Encoding]::UTF8.GetByteCount($stdout) -gt 4096 -or
        [Text.Encoding]::UTF8.GetByteCount($stderr) -gt 4096) {
        throw 'UNEXPECTED_OUTPUT_BUDGET'
    }
    if ($stdout.Contains('h2PROMPT_TEST_9397') -or $stderr.Contains('h2PROMPT_TEST_9397')) {
        throw 'DUMMY_PASSWORD_LEAKED_IN_CAPTURE'
    }
    if (-not $timedOut -and $p.ExitCode -eq 0) {
        throw 'UNEXPECTED_CONNECTION_SUCCESS_LOOPBACK_ONLY'
    }
    $promptInStderr = $stderr.Contains('Password for user h2_dummy_local:')
    $refused = $stderr -match '(?i)connection refused|actively refused|could not connect'
    Write-Host "STDERR_FALLBACK_PROMPT_CAPTURED=$promptInStderr"
    Write-Host "CONNECTION_REFUSED_OBSERVED=$([bool]$refused)"
    Write-Host "CHILD_TIMED_OUT=$timedOut"
    Write-Host "CHILD_NONZERO_EXIT=$($timedOut -or $p.ExitCode -ne 0)"
    Write-Host "CHILD_ELAPSED_MS=$([int]$watch.ElapsedMilliseconds)"
    Write-Host 'DUMMY_PASSWORD_ABSENT_FROM_ARGV_ENV_CAPTURE=PASS'
    Write-Host 'ATTEMPTS=1; RAW_STDERR_NOT_LOGGED=YES; SQL_EXECUTED=NO; NEON_ACCESSED=NO'
    if ($ManualConsole) {
        Write-Host 'INTERACTIVE_NO_ECHO_REQUIRES_HUMAN_OBSERVATION; do not report PASS from this script alone.'
    } else {
        Write-Host 'INTERACTIVE_NO_ECHO=UNVERIFIED (noninteractive runner).'
    }
    Write-Host 'REAL_PSQL18_LOOPBACK_PROBE=PASS_BOUNDED'
} finally {
    if ($started) {
        try {
            if (-not $p.HasExited) {
                $p.Kill($true)
                [void]$p.WaitForExit(1500)
            }
        } catch {}
    }
    $p.Dispose()
}
