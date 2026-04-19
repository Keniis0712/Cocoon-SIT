param(
    [string]$OutputDir = "dist",
    [string]$ArchiveName = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

$requiredPaths = @(
    "deploy/docker-compose.yml",
    "deploy/backend.Dockerfile",
    "deploy/.env.example",
    "deploy/init-db.sql",
    "backend",
    "frontend",
    "packages",
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml"
)

$includeRoots = @(
    "deploy",
    "backend",
    "frontend",
    "packages",
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml"
)

$excludePrefixes = @(
    ".git/",
    "node_modules/",
    ".pnpm-store/",
    ".uv-cache/",
    ".tmp_pytest/",
    ".artifacts/",
    "dist/",
    "backend/.venv/",
    "backend/.pytest_cache/",
    "backend/.mypy_cache/",
    "backend/.ruff_cache/",
    "backend/.artifacts/",
    "frontend/dist/",
    "frontend/node_modules/",
    "packages/ts-sdk/node_modules/"
)

function Normalize-RelativePath {
    param([string]$PathValue)
    return ($PathValue -replace "\\", "/").TrimStart("./")
}

function Test-Excluded {
    param([string]$RelativePath)
    $normalized = Normalize-RelativePath $RelativePath
    foreach ($prefix in $excludePrefixes) {
        if ($normalized.StartsWith($prefix)) {
            return $true
        }
    }
    return $false
}

function Get-IncludedFiles {
    $result = New-Object System.Collections.Generic.List[string]
    foreach ($entry in $includeRoots) {
        $fullPath = Join-Path $repoRoot $entry
        if (Test-Path $fullPath -PathType Container) {
            Get-ChildItem -LiteralPath $fullPath -Recurse -File | ForEach-Object {
                $relative = Normalize-RelativePath ($_.FullName.Substring($repoRoot.Path.Length + 1))
                if (-not (Test-Excluded $relative)) {
                    $result.Add($relative)
                }
            }
        } elseif (Test-Path $fullPath -PathType Leaf) {
            $relative = Normalize-RelativePath $entry
            if (-not (Test-Excluded $relative)) {
                $result.Add($relative)
            }
        }
    }
    return $result | Sort-Object -Unique
}

foreach ($path in $requiredPaths) {
    if (-not (Test-Path (Join-Path $repoRoot $path))) {
        throw "Missing required deployment path: $path"
    }
}

$resolvedOutputDir = Join-Path $repoRoot $OutputDir
if (-not (Test-Path $resolvedOutputDir)) {
    New-Item -ItemType Directory -Path $resolvedOutputDir | Out-Null
}

if ([string]::IsNullOrWhiteSpace($ArchiveName)) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $ArchiveName = "cocoon-sit-deploy-$timestamp.zip"
}
if (-not $ArchiveName.EndsWith(".zip")) {
    $ArchiveName = "$ArchiveName.zip"
}

$archivePath = Join-Path $resolvedOutputDir $ArchiveName
if (Test-Path $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
}

$files = Get-IncludedFiles
if ($files.Count -eq 0) {
    throw "No deployment files matched the include list."
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$zipFile = [System.IO.File]::Open($archivePath, [System.IO.FileMode]::CreateNew)
try {
    $archive = New-Object System.IO.Compression.ZipArchive($zipFile, [System.IO.Compression.ZipArchiveMode]::Create, $false)
    try {
        foreach ($relative in $files) {
            $sourcePath = Join-Path $repoRoot $relative
            $entry = $archive.CreateEntry($relative, [System.IO.Compression.CompressionLevel]::Optimal)
            $entryStream = $entry.Open()
            try {
                $sourceStream = [System.IO.File]::OpenRead($sourcePath)
                try {
                    $sourceStream.CopyTo($entryStream)
                } finally {
                    $sourceStream.Dispose()
                }
            } finally {
                $entryStream.Dispose()
            }
        }
    } finally {
        $archive.Dispose()
    }
} finally {
    $zipFile.Dispose()
}

$archiveItem = Get-Item -LiteralPath $archivePath
$sizeMb = [Math]::Round($archiveItem.Length / 1MB, 2)
Write-Host "Created deploy bundle: $($archiveItem.FullName)"
Write-Host "Files packed: $($files.Count)"
Write-Host "Archive size: $sizeMb MB"
