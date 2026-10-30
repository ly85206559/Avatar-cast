param([switch]$FunctionsOnly)

# Grok Bot's gateway is a private, version-dependent interface. This imports
# the current account's running connection; it does not wake or create a box.
class GrokSetupError : System.Exception {
    GrokSetupError([string]$message) : base($message) {}
}

function Read-GrokJson([string]$Path, [string]$Description) {
    try { return [IO.File]::ReadAllText($Path) | ConvertFrom-Json }
    catch { throw [GrokSetupError]::new("Unable to read $Description. Check that Grok Bot is installed and signed in.") }
}

function Protect-GrokConfig([string]$Path) {
    try {
        $acl = Get-Acl -LiteralPath $Path
        $userSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        $allowed = @($userSid, 'S-1-5-18')
        $rules = @($acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
        $unwanted = @($rules | Where-Object { $_.IdentityReference.Value -notin $allowed })
        $hasUser = @($rules | Where-Object { $_.IdentityReference.Value -eq $userSid -and $_.AccessControlType -eq 'Allow' }).Count -gt 0
        $hasSystem = @($rules | Where-Object { $_.IdentityReference.Value -eq 'S-1-5-18' -and $_.AccessControlType -eq 'Allow' }).Count -gt 0
        if ($acl.AreAccessRulesProtected -and $unwanted.Count -eq 0 -and $hasUser -and $hasSystem) { return }

        # icacls modifies the DACL without requesting SACL privileges.
        $arguments = @($Path, '/inheritance:r', '/grant:r', "*${userSid}:(F)", '*S-1-5-18:(F)')
        foreach ($sid in @($unwanted.IdentityReference.Value | Select-Object -Unique)) {
            $arguments += @('/remove', "*$sid")
        }
        & "$env:SystemRoot\System32\icacls.exe" @arguments 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'icacls failed' }
        $updated = Get-Acl -LiteralPath $Path
        $rules = @($updated.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
        $unexpected = @($rules | Where-Object { $_.IdentityReference.Value -notin $allowed })
        $hasUser = @($rules | Where-Object { $_.IdentityReference.Value -eq $userSid -and $_.AccessControlType -eq 'Allow' }).Count -gt 0
        $hasSystem = @($rules | Where-Object { $_.IdentityReference.Value -eq 'S-1-5-18' -and $_.AccessControlType -eq 'Allow' }).Count -gt 0
        if (-not $updated.AreAccessRulesProtected -or $unexpected.Count -gt 0 -or -not $hasUser -or -not $hasSystem) {
            throw 'Unexpected DACL'
        }
    } catch {
        throw [GrokSetupError]::new('Unable to restrict the gateway configuration to this Windows user and SYSTEM.')
    }
}

function Assert-GrokConfigPrivate([string]$Path) {
    # Do not change the user's existing configuration or its access rules.
    try {
        $acl = Get-Acl -LiteralPath $Path
        $userSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        $allowed = @($userSid, 'S-1-5-18')
        $rules = @($acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
        $unexpected = @($rules | Where-Object { $_.IdentityReference.Value -notin $allowed })
        $hasUser = @($rules | Where-Object { $_.IdentityReference.Value -eq $userSid -and $_.AccessControlType -eq 'Allow' }).Count -gt 0
        $hasSystem = @($rules | Where-Object { $_.IdentityReference.Value -eq 'S-1-5-18' -and $_.AccessControlType -eq 'Allow' }).Count -gt 0
        if (-not $acl.AreAccessRulesProtected -or $unexpected.Count -gt 0 -or -not $hasUser -or -not $hasSystem) {
            throw 'Unexpected DACL'
        }
    } catch {
        throw [GrokSetupError]::new('Existing gateway configuration permissions are not restricted to this Windows user and SYSTEM. No changes were made; review the file permissions and run setup again.')
    }
}

function Invoke-GrokSetupRequest([string]$Method, [string]$Body, [hashtable]$Headers) {
    try {
        return Invoke-RestMethod -Method Post -Uri "https://api2.cursor.sh/aiserver.v1.GrokBotService/$Method" `
            -Headers $Headers -ContentType 'application/json' -Body $Body -MaximumRedirection 0 -TimeoutSec 20
    } catch {
        throw [GrokSetupError]::new('Unable to check the Grok Bot computer or its gateway. Verify the account connection.')
    }
}

function Import-GrokBotGateway([string]$AppDataPath, [string]$ConfigPath) {
    $localState = Read-GrokJson (Join-Path $AppDataPath 'Local State') 'Grok Bot Local State'
    $appSecrets = Read-GrokJson (Join-Path $AppDataPath 'sand-secrets.json') 'Grok Bot sign-in data'
    $dataKey = $null
    $plain = $null
    $aes = $null
    $temporary = $null
    try {
        try {
            $wrappedKey = [Convert]::FromBase64String($localState.os_crypt.encrypted_key)
            if ($wrappedKey.Length -le 5 -or [Text.Encoding]::ASCII.GetString($wrappedKey,0,5) -ne 'DPAPI') {
                throw 'Unknown key format'
            }
            $dataKey = [Security.Cryptography.ProtectedData]::Unprotect(
                [byte[]]$wrappedKey[5..($wrappedKey.Length-1)], $null,
                [Security.Cryptography.DataProtectionScope]::CurrentUser)
            $accounts = $appSecrets.'cursor-accounts' | ConvertFrom-Json
            $active = $accounts.accounts.PSObject.Properties[$accounts.active].Value
            $blob = [Convert]::FromBase64String($active.'cursor-access-token')
            if ($blob.Length -le 31 -or [Text.Encoding]::ASCII.GetString($blob,0,3) -ne 'v10') {
                throw 'Unknown credential format'
            }
            $cipher = [byte[]]$blob[15..($blob.Length-17)]
            $plain = [byte[]]::new($cipher.Length)
            $aes = [Security.Cryptography.AesGcm]::new($dataKey)
            $aes.Decrypt([byte[]]$blob[3..14], $cipher, [byte[]]$blob[($blob.Length-16)..($blob.Length-1)], $plain)
            $jwt = [regex]::Match([Text.Encoding]::UTF8.GetString($plain),
                '^eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')
            if (-not $jwt.Success) { throw 'Invalid credential' }
        } catch {
            throw [GrokSetupError]::new('Unable to read the active Grok Bot sign-in. Unsupported or invalid local credential format.')
        }

        $version = '0.1.0'
        $desktopStatusPath = Join-Path $AppDataPath 'desktop-status.json'
        if (Test-Path -LiteralPath $desktopStatusPath) {
            $desktopStatus = Read-GrokJson $desktopStatusPath 'Grok Bot desktop status'
            if ($desktopStatus.appVersion -match '^\d+\.\d+\.\d+$') { $version = $desktopStatus.appVersion }
        }
        $headers = @{
            Authorization = 'Bearer ' + $jwt.Value
            'Connect-Protocol-Version' = '1'
            'x-cursor-client-type' = 'sand'
            'x-cursor-client-version' = $version
            'x-sand-box-namespace' = 'prod'
        }
        $state = Invoke-GrokSetupRequest 'GetSandBoxRunState' '{}' $headers
        if ($state.state -ne 'SAND_BOX_RUN_STATE_RUNNING' -and $state.state -ne 3) {
            throw [GrokSetupError]::new('The Grok Bot computer is not running. Wake it in Grok Bot and run setup again.')
        }
        # This is the application's describe request for an already-running box.
        # Provider-side behavior is private and can change; it is not a stable API.
        $route = Invoke-GrokSetupRequest 'EnsureSandBox' '{"wake":false}' $headers
        if ($route.runState -ne 'SAND_BOX_RUN_STATE_RUNNING' -and $route.runState -ne 3) {
            throw [GrokSetupError]::new('The Grok Bot computer is no longer running; no connection was saved.')
        }
        if (-not $route.gatewayUrl -or -not $route.gatewayToken) {
            throw [GrokSetupError]::new('The running Grok Bot computer did not provide gateway connection fields.')
        }
        $gatewayUri = $null
        if (-not [Uri]::TryCreate([string]$route.gatewayUrl, [UriKind]::Absolute, [ref]$gatewayUri) -or
            $gatewayUri.Scheme -ne 'https' -or -not $gatewayUri.Host.EndsWith('.cursorvm.com', [StringComparison]::OrdinalIgnoreCase) -or
            $gatewayUri.UserInfo -or $gatewayUri.Query -or $gatewayUri.Fragment) {
            throw [GrokSetupError]::new('The provider returned an unsupported gateway origin; no connection was saved.')
        }
        $extraHeaders = @{}
        if ($route.networkToken) { $extraHeaders['x-anyrun-network-token'] = $route.networkToken }
        elseif ($route.gatewayPortToken) { $extraHeaders['x-anyrun-port-token'] = $route.gatewayPortToken }

        $configDir = Split-Path -Parent $ConfigPath
        [IO.Directory]::CreateDirectory($configDir) | Out-Null
        $existing = Test-Path -LiteralPath $ConfigPath
        if ($existing) {
            try {
                $originalConfig = [IO.File]::ReadAllText($ConfigPath)
                $config = $originalConfig | ConvertFrom-Json -AsHashtable
            }
            catch { throw [GrokSetupError]::new('Existing gateway configuration is invalid; it was not overwritten.') }
            if ($config -isnot [Collections.IDictionary]) {
                throw [GrokSetupError]::new('Existing gateway configuration is invalid; it was not overwritten.')
            }
            Assert-GrokConfigPrivate $ConfigPath
        } else { $config = @{version=1} }
        $config.gateway = @{baseUrl=$route.gatewayUrl; token=$route.gatewayToken; headers=$extraHeaders}

        # The temporary file is secured before secrets are written. Its final
        # move is in the same directory and retains unrelated config keys.
        $temporary = Join-Path $configDir ('.gateway-' + [guid]::NewGuid().ToString('N') + '.tmp')
        $created = [IO.File]::Open($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
        $created.Dispose()
        Protect-GrokConfig $temporary
        [IO.File]::WriteAllText($temporary, ($config | ConvertTo-Json -Depth 15), [Text.UTF8Encoding]::new($false))
        if ($existing -and [IO.File]::ReadAllText($ConfigPath) -cne $originalConfig) {
            throw [GrokSetupError]::new('Gateway configuration changed during setup; it was not overwritten.')
        }
        if ($existing) { [IO.File]::Move($temporary, $ConfigPath, $true) }
        else { [IO.File]::Move($temporary, $ConfigPath) }
        $temporary = $null
        Write-Output 'Grok Bot gateway configuration imported. No credentials were displayed.'
    } finally {
        if ($aes) { $aes.Dispose() }
        if ($dataKey) { [Array]::Clear($dataKey, 0, $dataKey.Length) }
        if ($plain) { [Array]::Clear($plain, 0, $plain.Length) }
        if ($temporary -and (Test-Path -LiteralPath $temporary)) { Remove-Item -LiteralPath $temporary -Force }
        $headers=$null; $jwt=$null; $route=$null; $config=$null
    }
}

if (-not $FunctionsOnly) {
    if (-not $IsWindows -or $PSVersionTable.PSVersion.Major -lt 7) {
        Write-Error 'This setup requires Windows and PowerShell 7 or newer.'
        exit 1
    }
    $appDataPath = if ($env:SAND_USER_DATA_DIR) { $env:SAND_USER_DATA_DIR } else { Join-Path $env:APPDATA 'Grok Bot' }
    $configPath = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.gbm/config.json'
    try { Import-GrokBotGateway $appDataPath $configPath }
    catch [GrokSetupError] { Write-Error $_.Exception.Message; exit 1 }
    catch { Write-Error 'Grok Bot setup failed. The connection was not imported.'; exit 1 }
}
