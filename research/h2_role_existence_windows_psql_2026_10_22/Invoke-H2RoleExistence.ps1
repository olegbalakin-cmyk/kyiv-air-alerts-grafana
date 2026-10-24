#requires -Version 7.4
<#
H2 role-existence: local Windows operator launcher, never run by CI against Neon.
OfflineSelfTest uses only a Python mock and synthetic.invalid (no network).
The SQL and route template are immutable Git-pinned inputs.
#>
[CmdletBinding()]
param(
    [switch]$ExecuteOneRead,
    [switch]$OfflineSelfTest,
    [switch]$ClientPathPreflight,
    [string]$PsqlPath = '',
    [ValidateSet('absent','exists','missing_rollback','extra_statement','sql_error','timeout','wrong_role','wrong_database','wrong_guard','multiple_rows','malformed_header','exit_failure','stderr_noise')]
    [string]$MockScenario = 'absent',
    [string]$AttestationPath = '',
    [string]$OperatorName = '',
    [string]$ReceiptPath = ''
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$SqlBlob = 'dd3595f7402cdc6e44d3fce6c5632dd9cfb88052'
$SqlSha256 = '3e8a8d62440ec30245f64da21a263d84793e7e77a8cf45806f60a656ba6a31ee'
$RouteBlob = '0ea2e8688c5b5a5e3934704a29b2ad51195584b4'
$PsqlExeSha256 = 'fde952534f520909c02db04675588ecb1da8d618b6e5c93e106f42a752daf720'
$HostPin = 'ep-calm-rice-b5073ypp.c-7.us-east-2.aws.neon.tech'
$UserPin = 'neondb_owner'
$SqlPath = Join-Path $PSScriptRoot 'ROLE_EXISTENCE_PINNED.sql'
$RoutePath = Join-Path $PSScriptRoot 'ROUTE_ATTESTATION_TEMPLATE.json'
$CaPath = Join-Path $PSScriptRoot 'ISRG_ROOTS_PINNED.pem'
$CaSha256 = '0cd98d2dd7a71afe5e2e93673933f15254c5a41a9be4682f27ec582e72c52ce0'

function Get-Hashes([string]$Path) {
    $bytes = [IO.File]::ReadAllBytes($Path)
    $prefix = [Text.Encoding]::ASCII.GetBytes('blob ' + $bytes.Length + [char]0)
    $gitInput = [byte[]]($prefix + $bytes)
    return @{
        git = [Convert]::ToHexString([Security.Cryptography.SHA1]::HashData($gitInput)).ToLowerInvariant()
        sha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
    }
}
function Assert-StrictObject([string]$Path) {
    $content = [IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8)
    $doc = [Text.Json.JsonDocument]::Parse($content)
    try {
        if ($doc.RootElement.ValueKind -ne [Text.Json.JsonValueKind]::Object) { throw 'JSON root must be object' }
        $names = @($doc.RootElement.EnumerateObject() | ForEach-Object { $_.Name })
        if (@($names | Select-Object -Unique).Count -ne $names.Count) { throw 'Duplicate JSON fields' }
    } finally { $doc.Dispose() }
    return (ConvertFrom-Json -InputObject $content)
}
function Assert-Attestation([object]$route, [object]$record, [string]$operator) {
    $keys = @($route.PSObject.Properties.Name | Sort-Object)
    $recordKeys = @($record.PSObject.Properties.Name | Sort-Object)
    if (($keys -join '|') -cne ($recordKeys -join '|')) { throw 'Unexpected/missing attestation fields' }
    foreach ($key in @('project','branch','database','endpoint','fqdn','port','endpoint_type','pooler_enabled','postgres_major')) {
        if ($record.$key -cne $route.$key) { throw "Route mismatch: $key" }
    }
    if ($record.fqdn -cne $HostPin -or $record.port -ne 5432 -or
        $record.endpoint_type -cne 'read_only' -or $record.pooler_enabled -ne $false -or
        $record.postgres_major -ne 18) { throw 'Unexpected route identity' }
    if ($record.port_independently_verified -cne $true -or $record.independently_reviewed -cne $true) {
        throw 'Route/port not independently approved'
    }
    if ($record.source_sha256 -isnot [string] -or $record.source_sha256 -cnotmatch '^[0-9a-f]{64}$' -or
        $record.source_sha256 -eq ('0' * 64)) { throw 'Missing independent source digest' }
    if ($record.reviewed_by -isnot [string] -or $record.reviewed_by -notmatch '^[A-Za-z0-9_. -]{3,80}$' -or
        $record.reviewed_by -eq $operator) { throw 'Missing distinct named independent reviewer' }
    if ($record.observed_at_utc -isnot [string] -or $record.observed_at_utc -cnotmatch '^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$') {
        throw 'Missing UTC attestation timestamp'
    }
    $at = [DateTimeOffset]::ParseExact($record.observed_at_utc, 'yyyy-MM-ddTHH:mm:ssZ',
        [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::AssumeUniversal)
    $hours = ([DateTimeOffset]::UtcNow - $at).TotalHours
    if ($hours -lt 0 -or $hours -gt 72) { throw 'Route observation expired or in future' }
}
function Assert-PinnedCA {
    # Offline-only; do not substitute CA from caller environment, downloads or pgAdmin.
    if (-not [IO.File]::Exists($CaPath)) { throw 'PINNED_CA_MISSING' }
    $file = Get-Item -LiteralPath $CaPath -Force
    if (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'PINNED_CA_REPARSE_POINT' }
    $parent = [IO.DirectoryInfo]::new([IO.Path]::GetDirectoryName($CaPath))
    while ($null -ne $parent) {
        if (($parent.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'PINNED_CA_REPARSE_POINT' }
        $parent = $parent.Parent
    }
    $hash = (Get-FileHash -LiteralPath $CaPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -cne $CaSha256) { throw 'PINNED_CA_SHA256_MISMATCH' }
    return $CaPath
}
function Assert-ApprovedPsqlClient([string]$requestedPath) {
    if (-not $IsWindows) { throw 'CLIENT_PATH_WINDOWS_ONLY' }
    $defaultPath = Join-Path $env:ProgramFiles 'PostgreSQL\18\bin\psql.exe'
    $ownerPath = Join-Path $HOME 'h2-psql18\pgsql\bin\psql.exe'
    $candidate = if ([string]::IsNullOrWhiteSpace($requestedPath)) { $defaultPath } else { $requestedPath }
    if (-not [IO.Path]::IsPathFullyQualified($candidate)) { throw 'CLIENT_PATH_MUST_BE_ABSOLUTE' }
    $full = [IO.Path]::GetFullPath($candidate)
    $allowed = @([IO.Path]::GetFullPath($defaultPath), [IO.Path]::GetFullPath($ownerPath))
    if (-not @($allowed | Where-Object { [string]::Equals($_, $full, [StringComparison]::OrdinalIgnoreCase) }).Count) {
        throw 'CLIENT_PATH_NOT_ALLOWLISTED'
    }
    if (-not [IO.File]::Exists($full)) { throw 'CLIENT_EXECUTABLE_MISSING' }
    $entry = Get-Item -LiteralPath $full -Force
    if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'CLIENT_PATH_REPARSE_POINT' }
    $parent = [IO.DirectoryInfo]::new([IO.Path]::GetDirectoryName($full))
    while ($null -ne $parent) {
        if (($parent.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'CLIENT_PATH_REPARSE_POINT' }
        $parent = $parent.Parent
    }
    $hash = (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -cne $PsqlExeSha256) { throw 'CLIENT_EXECUTABLE_SHA256_MISMATCH' }
    $version = (& $full --version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $version -cnotmatch '^psql \(PostgreSQL\) 18\.\d+(?:\.\d+)?$') { throw 'CLIENT_MUST_BE_PG18' }
    return @{ path = $full; version = $version }
}
function Invoke-BoundedChild([string]$file, [string[]]$arguments, [bool]$synthetic) {
    $si = [Diagnostics.ProcessStartInfo]::new()
    $si.FileName = $file
    $si.UseShellExecute = $false
    $si.CreateNoWindow = $false
    $si.RedirectStandardOutput = $true
    $si.RedirectStandardError = $true
    $si.RedirectStandardInput = $false
    $si.StandardOutputEncoding = [Text.UTF8Encoding]::new($false)
    $si.StandardErrorEncoding = [Text.UTF8Encoding]::new($false)
    $si.WorkingDirectory = $PSScriptRoot
    foreach ($arg in $arguments) { [void]$si.ArgumentList.Add($arg) }
    $keep = @('SystemRoot','WINDIR','PATH','TEMP','TMP','USERPROFILE','APPDATA','LOCALAPPDATA','HOMEDRIVE','HOMEPATH')
    $si.Environment.Clear()
    foreach ($name in $keep) {
        $value = [Environment]::GetEnvironmentVariable($name)
        if ($null -ne $value) { $si.Environment[$name] = $value }
    }
    $si.Environment['PGSSLMODE'] = 'verify-full'
    $si.Environment['PGSSLROOTCERT'] = $script:CaPath
    $si.Environment['PGGSSENCMODE'] = 'disable'
    $si.Environment['PGCONNECT_TIMEOUT'] = '5'
    $si.Environment['PGCLIENTENCODING'] = 'UTF8'
    $si.Environment['PGAPPNAME'] = 'h2-role-existence-single-read'
    $si.Environment['PGPASSFILE'] = Join-Path ([IO.Path]::GetTempPath()) ('h2-no-such-pgpass-' + [guid]::NewGuid().ToString('N'))
    if ($synthetic) { $si.Environment['H2_MOCK_ONLY'] = '1' }
    $p = [Diagnostics.Process]::new()
    $p.StartInfo = $si
    $timer = [Diagnostics.Stopwatch]::StartNew()
    try {
        if (-not $p.Start()) { throw 'CLIENT_START_FAILED' }
        $stdoutTask = $p.StandardOutput.ReadToEndAsync()
        $stderrTask = $p.StandardError.ReadToEndAsync()
        if (-not $p.WaitForExit(20000)) {
            try { $p.Kill($true) } catch {}
            throw 'CLIENT_WALL_TIMEOUT_NO_RETRY'
        }
        $timer.Stop()
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        if ([Text.Encoding]::UTF8.GetByteCount($stdout) -gt 4096 -or
            [Text.Encoding]::UTF8.GetByteCount($stderr) -gt 1024) { throw 'CLIENT_OUTPUT_BUDGET' }
        return @{ stdout = $stdout; stderr = $stderr; exit_code = $p.ExitCode; elapsed_ms = [int]$timer.ElapsedMilliseconds }
    } finally { $p.Dispose() }
}

try {
    if (([int]$OfflineSelfTest.IsPresent + [int]$ExecuteOneRead.IsPresent + [int]$ClientPathPreflight.IsPresent) -ne 1) {
        throw 'Choose exactly one mode: OfflineSelfTest, ClientPathPreflight OR ExecuteOneRead'
    }
    if ($ClientPathPreflight) {
        if ($AttestationPath -ne '' -or $OperatorName -ne '' -or $ReceiptPath -ne '' -or
            $MockScenario -ne 'absent') { throw 'CLIENT_PREFLIGHT_FORBIDS_EXECUTION_INPUTS' }
        $ca = Assert-PinnedCA
        $client = Assert-ApprovedPsqlClient $PsqlPath
        Write-Host "CLIENT_PATH_PREFLIGHT_PASS version=$($client.version); no SQL, no network, no Neon"
        exit 0
    }
    if ($OfflineSelfTest -and $PsqlPath -ne '') { throw 'OFFLINE_MOCK_FORBIDS_REAL_CLIENT_PATH' }
    if ([string]::IsNullOrWhiteSpace($ReceiptPath)) { throw 'ReceiptPath required (OUTSIDE repository)' }
    $destination = [IO.Path]::GetFullPath($ReceiptPath)
    $repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
    if ($destination.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Receipt must remain outside the repository'
    }
    if ([IO.File]::Exists($destination)) { throw 'Receipt exists: refusing overwrite' }

    $ca = Assert-PinnedCA
    $sqlHashes = Get-Hashes $SqlPath
    $routeHashes = Get-Hashes $RoutePath
    if ($sqlHashes.git -cne $SqlBlob -or $sqlHashes.sha256 -cne $SqlSha256) { throw 'PINNED_SQL_MISMATCH' }
    if ($routeHashes.git -cne $RouteBlob) { throw 'ROUTE_TEMPLATE_MISMATCH' }
    $route = Assert-StrictObject $RoutePath
    $hostValue = $HostPin
    $attestationHash = $null
    $sourceDigest = $null
    $observedAt = $null
    $reviewer = 'MOCK_NOT_REVIEWED'
    $actor = 'MOCK_OPERATOR'
    if ($OfflineSelfTest) {
        if ($AttestationPath -ne '' -or $OperatorName -ne '') { throw 'OfflineSelfTest forbids attestation/operator inputs' }
        $hostValue = 'synthetic.invalid'
        $pythonCandidates = @(Get-Command python -CommandType Application -All -ErrorAction Stop)
        $python = @($pythonCandidates | ForEach-Object { $_.Path } | Where-Object { $_ -and [IO.File]::Exists($_) })[0]
        if (-not $python) { throw 'MOCK_PYTHON_NOT_FOUND' }
        $executable = $python
        $preArgs = @((Join-Path $PSScriptRoot 'mock_psql.py'), '--scenario', $MockScenario, '--')
        $version = 'psql (PostgreSQL) 18.6'
    } else {
        if ($OperatorName -cnotmatch '^[A-Za-z0-9_. -]{3,80}$' -or [string]::IsNullOrWhiteSpace($AttestationPath)) {
            throw 'Named local operator and separate attestation file required'
        }
        $attestation = Assert-StrictObject $AttestationPath
        Assert-Attestation $route $attestation $OperatorName
        $attestationHash = (Get-Hashes $AttestationPath).sha256
        $sourceDigest = $attestation.source_sha256
        $observedAt = $attestation.observed_at_utc
        $reviewer = $attestation.reviewed_by
        $actor = $OperatorName
        $client = Assert-ApprovedPsqlClient $PsqlPath
        $executable = $client.path
        $version = $client.version
        $preArgs = @()
        Write-Host 'One local psql password prompt will follow. Do not paste credentials into chat, CI or files.'
    }
    $psqlArgs = @('-X','-v','ON_ERROR_STOP=1','-v','ON_ERROR_ROLLBACK=off','-A','-F','|',
        '-P','footer=off','-P','pager=off','-P','tuples_only=off','-W',
        '-h',$hostValue,'-p','5432','-U',$UserPin,'-d','neondb','-f',$SqlPath)
    $actualArgs = [string[]]($preArgs + $psqlArgs)
    $result = Invoke-BoundedChild $executable $actualArgs ([bool]$OfflineSelfTest)
    if ($result.exit_code -ne 0) { throw 'PSQL_NONZERO_EXIT_SQL_OR_CONNECTION_ERROR' }
    $stderr = $result.stderr.Trim()
    if ($stderr -ne '' -and $stderr -cne ('Password for user ' + $UserPin + ':')) { throw 'UNEXPECTED_PSQL_STDERR' }
    if ($result.elapsed_ms -gt 20000) { throw 'WALL_BUDGET_EXCEEDED' }

    $newline = [string][char]10
    $normalized = $result.stdout.Replace(([string][char]13 + [string][char]10), $newline)
    if ($normalized.EndsWith($newline)) { $normalized = $normalized.Substring(0, $normalized.Length - 1) }
    $lines = @($normalized.Split([char]10))
    $header = 'database_name|session_role|current_role|server_version_num|transaction_read_only|transaction_isolation|inspector_exists'
    if ($lines.Count -ne 8) { throw 'UNEXPECTED_OUTPUT_LINE_COUNT' }
    $expectTags = @('BEGIN','SET','SET','SET','SET')
    for ($i=0; $i -lt 5; $i++) { if ($lines[$i] -cne $expectTags[$i]) { throw 'UNEXPECTED_STATEMENT_TAG' } }
    if ($lines[5] -cne $header -or $lines[7] -cne 'ROLLBACK') { throw 'BAD_HEADER_OR_ROLLBACK' }
    if ([Text.Encoding]::UTF8.GetByteCount($lines[6]) -gt 2048) { throw 'RESULT_TOO_LARGE' }
    $parts = @($lines[6].Split([char]'|'))
    if ($parts.Count -ne 7 -or $parts[0] -cne 'neondb' -or $parts[1] -cne $UserPin -or
        $parts[2] -cne $UserPin -or $parts[3] -cnotmatch '^18[0-9]{4}$' -or
        $parts[4] -cne 'on' -or $parts[5] -cne 'repeatable read' -or
        $parts[6] -cnotin @('t','f')) { throw 'RESULT_IDENTITY_SHAPE_OR_GUARD_INVALID' }

    $canonical = $normalized + $newline
    $transcriptSha = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData(
        [Text.Encoding]::UTF8.GetBytes($canonical))).ToLowerInvariant()
    $publicArgs = @($psqlArgs)
    $publicArgs[$publicArgs.Count-1] = 'ROLE_EXISTENCE_PINNED.sql'
    $receipt = [ordered]@{
        schema = 'h2-role-existence-receipt-v1'
        mode = $(if ($OfflineSelfTest) { 'SYNTHETIC' } else { 'OPERATOR_LOCAL' })
        verdict = 'UNVERIFIED_PENDING_INDEPENDENT_REVIEW'
        role_existence = 'UNVERIFIED'
        provisional_inspector_exists = ($parts[6] -ceq 't')
        sql_git_blob = $SqlBlob
        sql_sha256 = $SqlSha256
        route_template_git_blob = $RouteBlob
        project = $route.project
        branch = $route.branch
        endpoint = $(if ($OfflineSelfTest) { 'SYNTHETIC_ONLY' } else { $route.endpoint })
        fqdn = $hostValue
        database = 'neondb'
        port = 5432
        expected_role = $UserPin
        operator = $actor
        reviewed_by = $reviewer
        route_attestation_sha256 = $attestationHash
        route_source_sha256 = $sourceDigest
        route_observed_at_utc = $observedAt
        client_version = $version
        pg_sslmode = 'verify-full'
        pg_sslrootcert = 'ISRG_ROOTS_PINNED.pem'
        pg_gssencmode = 'disable'
        connect_timeout_seconds = 5
        wall_budget_seconds = 20
        elapsed_ms = $result.elapsed_ms
        client_exit_code = $result.exit_code
        attempt_count = 1
        sql_statement_count_expected = 7
        select_count_expected = 1
        stderr_status = $(if ($stderr -eq '') { 'EMPTY' } else { 'PROMPT_ONLY' })
        psql_arguments = $publicArgs
        transcript = $lines
        transcript_sha256 = $transcriptSha
        observed_at_utc = [DateTimeOffset]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
        tls_handshake_independently_proven = $false
        single_physical_session_independently_proven = $false
    }
    $json = $receipt | ConvertTo-Json -Depth 6
    $parentDir = [IO.Path]::GetDirectoryName($destination)
    if (-not [IO.Directory]::Exists($parentDir)) { throw 'Receipt directory must pre-exist' }
    [IO.File]::WriteAllText($destination, $json + $newline, [Text.UTF8Encoding]::new($false))
    Write-Host 'SANITIZED RECEIPT WRITTEN. ROLE EXISTENCE STILL UNVERIFIED pending independent route/TLS/session review.'
    if ($OfflineSelfTest) { Write-Host 'SYNTHETIC MOCK ONLY. NO DATABASE CONNECTION.' }
    exit 0
} catch {
    Write-Error -Message ('FAIL CLOSED / NO RESULT: ' + $_.Exception.Message) -ErrorAction Continue
    exit 1
}
