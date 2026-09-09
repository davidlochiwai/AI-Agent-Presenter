param(
    [switch]$RotatePresenterToken,
    [string]$PublicWebhookUrl = ""
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$envPath = Join-Path $root ".env"
$examplePath = Join-Path $root ".env.example"

if (-not (Test-Path $envPath)) {
    if (-not (Test-Path $examplePath)) {
        throw "Neither .env nor .env.example exists."
    }
    Copy-Item $examplePath $envPath
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupPath = Join-Path $root ".env.backup-$stamp"
Copy-Item $envPath $backupPath

$text = [IO.File]::ReadAllText($envPath)

function Set-EnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value
    )

    $line = "$Name=$Value"
    $pattern = "(?m)^" + [regex]::Escape($Name) + "\s*=.*$"
    if ([regex]::IsMatch($script:text, $pattern)) {
        $script:text = [regex]::Replace($script:text, $pattern, $line)
    }
    else {
        if ($script:text.Length -gt 0 -and -not $script:text.EndsWith("`n")) {
            $script:text += "`r`n"
        }
        $script:text += "$line`r`n"
    }
}

function Ensure-EnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Value
    )

    $pattern = "(?m)^" + [regex]::Escape($Name) + "\s*="
    if (-not [regex]::IsMatch($script:text, $pattern)) {
        Set-EnvValue $Name $Value
    }
}

function New-RandomToken {
    $bytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($bytes)
}

Set-EnvValue "PUBLIC_BASE_URL" ""
Set-EnvValue "APP_HOST" "0.0.0.0"
Set-EnvValue "AUTO_TUNNEL" "false"
Set-EnvValue "N8N_SESSION_WEBHOOK_URL" "http://127.0.0.1:5678/webhook/presenter/session"
Set-EnvValue "N8N_DELIVER_NEXT_WEBHOOK_URL" ""
Set-EnvValue "N8N_BRIDGE_URL" "http://host.docker.internal:8787/api/bridge"
Set-EnvValue "N8N_LOCAL_PORT" "5678"
Set-EnvValue "QDRANT_URL" "http://127.0.0.1:6333"
Set-EnvValue "QDRANT_COLLECTION" "presenter_knowledge"
Set-EnvValue "QA_KNOWLEDGE_DIR" "data/knowledge_sources"
Set-EnvValue "QA_AUTO_INDEX" "true"
Ensure-EnvValue "AZURE_OPENAI_ENDPOINT" ""
Ensure-EnvValue "AZURE_OPENAI_API_KEY" ""
Ensure-EnvValue "AZURE_OPENAI_API_VERSION" ""
Ensure-EnvValue "AZURE_OPENAI_CHAT_DEPLOYMENT" ""
Ensure-EnvValue "AZURE_OPENAI_EMBEDDING_DEPLOYMENT" ""

$tokenMatch = [regex]::Match($text, "(?m)^N8N_WEBHOOK_TOKEN\s*=(.*)$")
$existingToken = if ($tokenMatch.Success) { $tokenMatch.Groups[1].Value.Trim() } else { "" }
if (-not $existingToken) {
    Set-EnvValue "N8N_WEBHOOK_TOKEN" (New-RandomToken)
}

if ($RotatePresenterToken) {
    Set-EnvValue "PRESENTER_TOOL_TOKEN" (New-RandomToken)
}

if ($PublicWebhookUrl) {
    Set-EnvValue "N8N_AUTO_TUNNEL" "false"
    Set-EnvValue "N8N_PUBLIC_WEBHOOK_URL" ($PublicWebhookUrl.TrimEnd("/") + "/")
}
else {
    Set-EnvValue "N8N_AUTO_TUNNEL" "true"
    Set-EnvValue "N8N_PUBLIC_WEBHOOK_URL" ""
}

[IO.File]::WriteAllText($envPath, $text, [Text.UTF8Encoding]::new($false))

Write-Host "Configured local n8n mode in .env."
Write-Host "Backup: $backupPath"
Write-Host "The n8n webhook token is stored in .env and was not printed."
if ($RotatePresenterToken) {
    Write-Host "The presenter bridge token was rotated and was not printed."
}
if ($PublicWebhookUrl) {
    Write-Host "n8n public webhook origin: $($PublicWebhookUrl.TrimEnd('/'))/"
}
else {
    Write-Host "Automatic n8n quick tunnel enabled; the app will update Retell on every startup."
}
Write-Host "Restart voice-app.cmd after n8n webhook authentication is configured."
