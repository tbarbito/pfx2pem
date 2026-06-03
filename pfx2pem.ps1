#Requires -Version 5.1
<#
.SYNOPSIS
    Converts PFX certificates to PEM format files.

.DESCRIPTION
    Reads PFX files from the configured import directory and generates
    _key.pem, _cert.pem, _ca.pem and _all.pem for each mapped entity code.

    One CNPJ can map to multiple entity codes -- the same certificate content
    is written once per code, using the code as the output filename prefix.

    The CA chain is built automatically by following AIA (Authority Information
    Access) URLs embedded in the certificate. An internet connection is required
    the first time a certificate from a given CA chain is processed.

.NOTES
    Requires OpenSSL to be installed and accessible via PATH or one of the
    well-known installation paths.

    Copy config.example.json to config.json and fill in your values before running.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

# ============================================================
# Load configuration
# ============================================================
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigPath = Join-Path $ScriptDir "config.json"

if (-not (Test-Path $ConfigPath)) {
    Write-Error "config.json not found in $ScriptDir.`nCopy config.example.json to config.json and fill in your values."
    exit 1
}

try {
    $Config = Get-Content $ConfigPath -Raw | ConvertFrom-Json
} catch {
    Write-Error "Failed to parse config.json: $_"
    exit 1
}

$ImportDir = $Config.importDir
$ExportDir = $Config.exportDir

# Build lookup: cnpj -> { password, codes[] }
$CertMap = @{}
foreach ($entry in $Config.certificates) {
    $CertMap[$entry.cnpj] = $entry
}

# ============================================================
# Logging
# ============================================================
function Write-Log {
    param([string]$Message, [string]$Color = "White")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "$ts - $Message" -ForegroundColor $Color
}

# ============================================================
# Locate OpenSSL
# ============================================================
function Find-OpenSSL {
    $candidates = [System.Collections.Generic.List[string]]::new()
    $candidates.Add("openssl")
    $candidates.Add("C:\Program Files\OpenSSL-Win64\bin\openssl.exe")
    $candidates.Add("C:\Program Files (x86)\OpenSSL-Win32\bin\openssl.exe")
    $candidates.Add("C:\OpenSSL-Win64\bin\openssl.exe")
    $candidates.Add("C:\OpenSSL-Win32\bin\openssl.exe")

    # Git for Windows bundles OpenSSL -- locate it via git.exe
    $git = Get-Command git -ErrorAction SilentlyContinue
    if ($git) {
        $gitDir = Split-Path (Split-Path $git.Source -Parent) -Parent
        $candidates.Add((Join-Path $gitDir "mingw64\bin\openssl.exe"))
        $candidates.Add((Join-Path $gitDir "usr\bin\openssl.exe"))
    }

    foreach ($c in $candidates) {
        try {
            $null = & $c version 2>&1
            if ($LASTEXITCODE -eq 0) { return $c }
        } catch { }
    }
    return $null
}

# ============================================================
# Run pkcs12 extraction -- tries without -legacy first, then with
# ============================================================
function Export-PfxContent {
    param(
        [string]   $PfxPath,
        [string]   $Password,
        [string]   $OutPath,
        [string[]] $ExtraArgs
    )

    foreach ($legacy in @($false, $true)) {
        $opensslArgs = @("pkcs12", "-in", $PfxPath, "-passin", "pass:$Password") + $ExtraArgs + @("-out", $OutPath)
        if ($legacy) { $opensslArgs += "-legacy" }

        & $script:OpenSSL @opensslArgs 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0 -and (Test-Path $OutPath) -and (Get-Item $OutPath).Length -gt 0) {
            return $true
        }
    }
    return $false
}

# ============================================================
# Extract CNPJ from PEM certificate bytes
# Filters out all-zero values, repeated digits, and the CA's own CNPJ
# ============================================================
function Get-CnpjFromPem {
    param([string]$PemPath)

    $tempDer = Join-Path $env:TEMP "pfx2pem_$([System.IO.Path]::GetRandomFileName()).der"
    try {
        & $script:OpenSSL x509 -in $PemPath -outform DER -out $tempDer 2>&1
        if (-not (Test-Path $tempDer)) { return $null }

        $bytes   = [System.IO.File]::ReadAllBytes($tempDer)
        $content = [System.Text.Encoding]::Latin1.GetString($bytes)

        # Exclude the CA's CNPJ (found in issuer OU)
        $subjectText = (& $script:OpenSSL x509 -in $PemPath -noout -subject 2>&1) | Out-String
        $caCnpj = if ($subjectText -match 'OU\s*=\s*(\d{14})') { $Matches[1] } else { $null }

        $candidates = [regex]::Matches($content, '\d{14}') |
                      ForEach-Object { $_.Value } |
                      Select-Object -Unique

        foreach ($c in $candidates) {
            if ($c -match '^0{14}$')      { continue }   # all zeros
            if ($c -match '^(.)\1{13}$')  { continue }   # all same digit
            if ($c -eq $caCnpj)           { continue }   # belongs to CA
            return $c
        }
    } finally {
        Remove-Item $tempDer -Force -ErrorAction SilentlyContinue
    }
    return $null
}

# ============================================================
# Build CA chain by following AIA URLs upward to the root
# Returns a list of PEM certificate strings (intermediates + root)
# ============================================================
function Get-CaChain {
    param([string]$LeafCertPemPath)

    $chain   = [System.Collections.Generic.List[string]]::new()
    $current = $LeafCertPemPath
    $depth   = 0

    while ($depth -lt 10) {
        $depth++

        # Stop when we reach a self-signed (root) certificate
        $subjectLine = (& $script:OpenSSL x509 -in $current -noout -subject 2>&1) | Out-String
        $issuerLine  = (& $script:OpenSSL x509 -in $current -noout -issuer  2>&1) | Out-String
        $subjectVal  = if ($subjectLine -match 'subject=(.+)') { $Matches[1].Trim() } else { "" }
        $issuerVal   = if ($issuerLine  -match 'issuer=(.+)')  { $Matches[1].Trim() } else { "" }
        if ($subjectVal -eq $issuerVal) { break }

        # Get AIA CA Issuers URL from current cert
        $certText = (& $script:OpenSSL x509 -in $current -noout -text 2>&1) | Out-String
        $aiaMatch = [regex]::Match($certText, 'CA Issuers - URI:([^\s]+)')
        if (-not $aiaMatch.Success) { break }

        $aiaUrl = $aiaMatch.Groups[1].Value.Trim()
        Write-Log "    Fetching CA cert from: $aiaUrl" "Gray"

        $tmpDl  = Join-Path $env:TEMP "pfx2pem_dl_${depth}.tmp"
        $tmpPem = Join-Path $env:TEMP "pfx2pem_ca_${depth}.pem"

        try {
            [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $aiaUrl -OutFile $tmpDl -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop

            # Try PKCS#7 DER (common for ICP-Brasil .p7c files)
            & $script:OpenSSL pkcs7 -inform DER -in $tmpDl -print_certs -out $tmpPem 2>&1

            if (-not (Test-Path $tmpPem) -or (Get-Item $tmpPem).Length -eq 0) {
                # Fallback: plain DER certificate
                & $script:OpenSSL x509 -inform DER -in $tmpDl -out $tmpPem 2>&1
            }

            if (-not (Test-Path $tmpPem) -or (Get-Item $tmpPem).Length -eq 0) {
                Write-Log "    Could not parse CA cert from $aiaUrl" "Yellow"
                break
            }

            $pemContent  = Get-Content $tmpPem -Raw
            $certBlocks  = [regex]::Matches($pemContent, "(?s)(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)")
            foreach ($block in $certBlocks) {
                $chain.Add($block.Value)
            }

            $current = $tmpPem

        } catch {
            Write-Log "    Failed to fetch CA cert: $_" "Yellow"
            break
        } finally {
            Remove-Item $tmpDl -Force -ErrorAction SilentlyContinue
        }
    }

    return $chain
}

# ============================================================
# Resolve which config entry matches a given PFX file
# ============================================================
function Resolve-PfxEntry {
    param([System.IO.FileInfo]$PfxFile)

    # 1. Filename is a 14-digit CNPJ
    if ($PfxFile.BaseName -match '^\d{14}$') {
        $cnpj = $PfxFile.BaseName
        if ($script:CertMap.ContainsKey($cnpj)) {
            return $script:CertMap[$cnpj]
        }
        # CNPJ known from filename but not mapped -- return it with no codes
        return [PSCustomObject]@{ cnpj = $cnpj; password = $null; codes = @() }
    }

    # 2. Try all configured passwords; extract CNPJ from cert content
    $tmpCert = Join-Path $env:TEMP "pfx2pem_resolve_$([System.IO.Path]::GetRandomFileName()).pem"
    try {
        foreach ($cnpj in $script:CertMap.Keys) {
            $entry = $script:CertMap[$cnpj]
            $ok    = Export-PfxContent -PfxPath $PfxFile.FullName -Password $entry.password `
                         -OutPath $tmpCert -ExtraArgs @("-clcerts", "-nokeys")
            if ($ok) {
                $foundCnpj = Get-CnpjFromPem -PemPath $tmpCert
                if ($foundCnpj -and $script:CertMap.ContainsKey($foundCnpj)) {
                    return $script:CertMap[$foundCnpj]
                }
                if ($foundCnpj) {
                    return [PSCustomObject]@{ cnpj = $foundCnpj; password = $entry.password; codes = @($foundCnpj) }
                }
            }
        }
    } finally {
        Remove-Item $tmpCert -Force -ErrorAction SilentlyContinue
    }

    return $null
}

# ============================================================
# Convert a single PFX file
# ============================================================
function Convert-Pfx {
    param([System.IO.FileInfo]$PfxFile)

    Write-Log "Processing: $($PfxFile.Name)" "Cyan"

    $entry = Resolve-PfxEntry -PfxFile $PfxFile

    if (-not $entry) {
        Write-Log "  Skipping: no config entry found for '$($PfxFile.Name)'" "Yellow"
        return $false
    }

    if (-not $entry.password) {
        Write-Log "  Skipping: no password configured for CNPJ $($entry.cnpj)" "Yellow"
        return $false
    }

    $cnpj  = $entry.cnpj
    $pass  = $entry.password
    $codes = if ($entry.codes -and $entry.codes.Count -gt 0) { $entry.codes } else { @($cnpj) }

    Write-Log "  CNPJ: $cnpj  ->  Codes: $($codes -join ', ')" "Green"

    $tmpCert = Join-Path $env:TEMP "pfx2pem_cert_$([System.IO.Path]::GetRandomFileName()).pem"
    $success = $true

    try {
        # --- Private key (raw string, no temp file needed) ---
        Write-Log "  Extracting private key..." "Gray"

        $keyRaw = $null
        foreach ($legacy in @($false, $true)) {
            $opensslArgs = @("pkcs12", "-in", $PfxFile.FullName, "-nocerts", "-nodes", "-passin", "pass:$pass")
            if ($legacy) { $opensslArgs += "-legacy" }
            $out = (& $script:OpenSSL @opensslArgs 2>&1) | Out-String
            if ($out -match "(?s)(-----BEGIN (?:RSA )?PRIVATE KEY-----.*?-----END (?:RSA )?PRIVATE KEY-----)") {
                $keyRaw = $Matches[1] + "`n"
                break
            }
        }

        if (-not $keyRaw) {
            Write-Log "  ERROR: Could not extract private key" "Red"
            return $false
        }

        # --- Client certificate ---
        Write-Log "  Extracting certificate..." "Gray"
        $ok = Export-PfxContent -PfxPath $PfxFile.FullName -Password $pass `
                  -OutPath $tmpCert -ExtraArgs @("-clcerts", "-nokeys")

        if (-not $ok) {
            Write-Log "  ERROR: Could not extract certificate" "Red"
            return $false
        }

        $certContent = Get-Content $tmpCert -Raw
        if (-not ($certContent -match "(?s)(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)")) {
            Write-Log "  ERROR: Could not parse certificate block" "Red"
            return $false
        }
        $certRaw = $Matches[1] + "`n"

        # --- CA chain (downloaded once, shared across all codes) ---
        Write-Log "  Building CA chain..." "Gray"
        $caChain = Get-CaChain -LeafCertPemPath $tmpCert

        if ($caChain.Count -gt 0) {
            $caRaw  = ($caChain -join "`n") + "`n"
            $allRaw = $certRaw + $caRaw
            Write-Log "  CA chain: $($caChain.Count) certificate(s) fetched" "Green"
        } else {
            Write-Log "  WARNING: CA chain unavailable. _ca.pem skipped, _all.pem = cert only" "Yellow"
            $caRaw  = $null
            $allRaw = $certRaw
        }

        # --- Write output files for each mapped code ---
        foreach ($code in $codes) {
            Write-Log "  Writing files for code: $code" "Gray"

            [System.IO.File]::WriteAllText((Join-Path $ExportDir "${code}_key.pem"),  $keyRaw,  [System.Text.Encoding]::ASCII)
            [System.IO.File]::WriteAllText((Join-Path $ExportDir "${code}_cert.pem"), $certRaw, [System.Text.Encoding]::ASCII)
            [System.IO.File]::WriteAllText((Join-Path $ExportDir "${code}_all.pem"),  $allRaw,  [System.Text.Encoding]::ASCII)

            if ($caRaw) {
                [System.IO.File]::WriteAllText((Join-Path $ExportDir "${code}_ca.pem"), $caRaw, [System.Text.Encoding]::ASCII)
            }

            Write-Log "    ${code}_key.pem, ${code}_cert.pem, ${code}_ca.pem, ${code}_all.pem" "Green"
        }

    } finally {
        Remove-Item $tmpCert -Force -ErrorAction SilentlyContinue
    }

    return $success
}

# ============================================================
# Entry point
# ============================================================
$script:OpenSSL = Find-OpenSSL
if (-not $script:OpenSSL) {
    Write-Log "OpenSSL not found. Install it and ensure it is in PATH." "Red"
    exit 1
}
Write-Log "OpenSSL: $script:OpenSSL" "Green"

if (-not (Test-Path $ImportDir)) {
    Write-Log "Import directory not found: $ImportDir" "Red"
    exit 1
}

if (-not (Test-Path $ExportDir)) {
    New-Item -ItemType Directory -Path $ExportDir | Out-Null
    Write-Log "Export directory created: $ExportDir" "Yellow"
}

$pfxFiles = @(Get-ChildItem -Path $ImportDir -Filter "*.pfx")
if ($pfxFiles.Count -eq 0) {
    Write-Log "No PFX files found in: $ImportDir" "Yellow"
    exit 0
}

Write-Log "Found $($pfxFiles.Count) PFX file(s) to process"
Write-Log "============================================================" "Gray"

$ok   = 0
$fail = 0

foreach ($pfx in $pfxFiles) {
    $result = Convert-Pfx -PfxFile $pfx
    if ($result) { $ok++ } else { $fail++ }
    Write-Log "------------------------------------------------------------" "Gray"
}

Write-Log "Done. Success: $ok | Failed/Skipped: $fail" "Cyan"
Write-Log "Output directory: $ExportDir" "Cyan"

if ($fail -gt 0) { exit 1 }
exit 0
