[CmdletBinding()]
param(
    [string]$WorkspaceId,
    [string]$SourceRoot = (Join-Path $env:APPDATA 'Code\User\workspaceStorage'),
    [string]$BackupRoot = $(
        $documentsPath = [Environment]::GetFolderPath('MyDocuments')
        if ([string]::IsNullOrWhiteSpace($documentsPath)) {
            Join-Path $PSScriptRoot '_copilot_chat_backups'
        }
        else {
            Join-Path $documentsPath 'CopilotChatBackups\roll'
        }
    ),
    [switch]$OpenBackupFolder
)

$ErrorActionPreference = 'Stop'

function Get-WorkspaceTargets {
    param(
        [string]$ResolvedSourceRoot,
        [string]$RequestedWorkspaceId
    )

    if ($RequestedWorkspaceId) {
        $workspacePath = Join-Path $ResolvedSourceRoot $RequestedWorkspaceId
        if (-not (Test-Path -LiteralPath $workspacePath -PathType Container)) {
            throw "Workspace ID '$RequestedWorkspaceId' was not found under '$ResolvedSourceRoot'."
        }

        return @($workspacePath)
    }

    return @(Get-ChildItem -LiteralPath $ResolvedSourceRoot -Directory | ForEach-Object { $_.FullName })
}

function Get-CopilotChatDirectories {
    param(
        [string[]]$WorkspacePaths
    )

    $results = @()
    foreach ($workspacePath in $WorkspacePaths) {
        $chatPath = Join-Path $workspacePath 'GitHub.copilot-chat'
        if (-not (Test-Path -LiteralPath $chatPath -PathType Container)) {
            continue
        }

        $results += [pscustomobject]@{
            WorkspaceId = Split-Path -Path $workspacePath -Leaf
            ChatPath    = $chatPath
        }
    }

    return $results
}

if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
    throw "VS Code workspace storage root was not found: '$SourceRoot'."
}

$workspacePaths = Get-WorkspaceTargets -ResolvedSourceRoot $SourceRoot -RequestedWorkspaceId $WorkspaceId
$copilotChatDirectories = Get-CopilotChatDirectories -WorkspacePaths $workspacePaths

if (-not $copilotChatDirectories) {
    throw "No GitHub.copilot-chat directories were found under '$SourceRoot'."
}

$timestamp = Get-Date -Format 'yyyy-MM-dd_HHmmss'
$destinationRoot = Join-Path $BackupRoot $timestamp
New-Item -ItemType Directory -Path $destinationRoot -Force | Out-Null

$manifest = @()

foreach ($entry in $copilotChatDirectories) {
    $workspaceDestination = Join-Path $destinationRoot $entry.WorkspaceId
    New-Item -ItemType Directory -Path $workspaceDestination -Force | Out-Null

    $destinationPath = Join-Path $workspaceDestination 'GitHub.copilot-chat'
    Copy-Item -LiteralPath $entry.ChatPath -Destination $destinationPath -Recurse -Force

    $transcriptsPath = Join-Path $entry.ChatPath 'transcripts'
    $debugLogsPath = Join-Path $entry.ChatPath 'debug-logs'

    $manifest += [pscustomobject]@{
        workspaceId    = $entry.WorkspaceId
        source         = $entry.ChatPath
        destination    = $destinationPath
        transcriptCount = if (Test-Path -LiteralPath $transcriptsPath) { @(Get-ChildItem -LiteralPath $transcriptsPath -File).Count } else { 0 }
        debugLogCount   = if (Test-Path -LiteralPath $debugLogsPath) { @(Get-ChildItem -LiteralPath $debugLogsPath -File).Count } else { 0 }
    }
}

$manifestPath = Join-Path $destinationRoot 'backup_manifest.json'
$summaryPath = Join-Path $destinationRoot 'backup_summary.txt'

$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

$summaryLines = @(
    "Backup created: $timestamp",
    "Source root: $SourceRoot",
    "Backup root: $destinationRoot",
    ''
)

foreach ($item in $manifest) {
    $summaryLines += "Workspace: $($item.workspaceId)"
    $summaryLines += "  Source: $($item.source)"
    $summaryLines += "  Destination: $($item.destination)"
    $summaryLines += "  Transcripts: $($item.transcriptCount)"
    $summaryLines += "  Debug logs: $($item.debugLogCount)"
    $summaryLines += ''
}

$summaryLines | Set-Content -LiteralPath $summaryPath -Encoding UTF8

Write-Host "Backed up $($manifest.Count) Copilot chat workspace(s) to '$destinationRoot'."
Write-Host "Manifest: $manifestPath"
Write-Host "Summary : $summaryPath"

if ($OpenBackupFolder) {
    Invoke-Item -LiteralPath $destinationRoot
}