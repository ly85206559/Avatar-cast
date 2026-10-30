"""Exercise setup using synthetic Windows credentials and a local mock, never a real account."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PWSH = shutil.which("pwsh")
pytestmark = pytest.mark.skipif(sys.platform != "win32" or not PWSH,
                                reason="Windows and PowerShell 7 are required")


HARNESS = r'''
$ErrorActionPreference = 'Stop'
. $env:AVATARCAST_SETUP_SCRIPT -FunctionsOnly
$testRoot = $env:AVATARCAST_TEST_ROOT
$scenario = $env:AVATARCAST_TEST_SCENARIO
$appPath = Join-Path $testRoot 'app'
$configPath = Join-Path $testRoot 'gbm/config.json'
[IO.Directory]::CreateDirectory($appPath) | Out-Null
[IO.Directory]::CreateDirectory((Split-Path -Parent $configPath)) | Out-Null
$key = [byte[]]::new(32)
$nonce = [byte[]]::new(12)
[Security.Cryptography.RandomNumberGenerator]::Fill($key)
[Security.Cryptography.RandomNumberGenerator]::Fill($nonce)
$keyProtected = [Security.Cryptography.ProtectedData]::Protect($key, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
[byte[]]$wrappedKey = [Text.Encoding]::ASCII.GetBytes('DPAPI') + $keyProtected
$source = [Text.Encoding]::UTF8.GetBytes('eyJ0ZXN0.eyJ0ZXN0.c2ln')
$cipher = [byte[]]::new($source.Length)
$tag = [byte[]]::new(16)
$aes = [Security.Cryptography.AesGcm]::new($key)
$aes.Encrypt($nonce, $source, $cipher, $tag)
$aes.Dispose()
$prefix = if ($scenario -eq 'bad-format') {'v11'} else {'v10'}
[byte[]]$blob = [Text.Encoding]::ASCII.GetBytes($prefix) + $nonce + $cipher + $tag
$state = @{os_crypt=@{encrypted_key=[Convert]::ToBase64String($wrappedKey)}}
$accounts = @{active='fixture';accounts=@{fixture=@{'cursor-access-token'=[Convert]::ToBase64String($blob)}}}
$secrets = @{'cursor-accounts'=($accounts | ConvertTo-Json -Depth 10 -Compress)}
[IO.File]::WriteAllText((Join-Path $appPath 'Local State'), ($state | ConvertTo-Json -Depth 10))
[IO.File]::WriteAllText((Join-Path $appPath 'sand-secrets.json'), ($secrets | ConvertTo-Json -Depth 10))
if ($scenario -in @('existing','idempotent','bad-config','unsafe-existing-acl')) {
  $existing = if ($scenario -eq 'bad-config') {'{invalid'} else {'{"version":1,"keep":{"hello":"world"}}'}
  [IO.File]::WriteAllText($configPath, $existing)
  if ($scenario -in @('existing','idempotent')) { Protect-GrokConfig $configPath }
  if ($scenario -eq 'unsafe-existing-acl') {
    & "$env:SystemRoot\System32\icacls.exe" $configPath '/grant' '*S-1-1-0:(R)' 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not create synthetic unsafe ACL' }
    $originalAcl = (Get-Acl -LiteralPath $configPath).Sddl
  }
}
$global:grokMockCalls = [Collections.Generic.List[object]]::new()
function global:Invoke-RestMethod {
  param($Method,$Uri,$Headers,$ContentType,$Body,$MaximumRedirection,$TimeoutSec)
  $global:grokMockCalls.Add(@{uri=$Uri;body=$Body;maximumRedirection=$MaximumRedirection})
  if ($scenario -eq 'network-fail') { throw 'synthetic-gateway-token and synthetic-network-token' }
  if ($Uri -eq 'https://api2.cursor.sh/aiserver.v1.GrokBotService/GetSandBoxRunState') {
    return @{state=$(if($scenario -eq 'sleeping') {'SAND_BOX_RUN_STATE_HIBERNATED'} else {'SAND_BOX_RUN_STATE_RUNNING'})}
  }
  if ($Uri -eq 'https://api2.cursor.sh/aiserver.v1.GrokBotService/EnsureSandBox') {
    return @{runState='SAND_BOX_RUN_STATE_RUNNING'; gatewayUrl=$(if($scenario -eq 'bad-origin') {'https://evil.example/secret'} else {'https://fixture.us10.cursorvm.com'}); gatewayToken='synthetic-gateway-token'; networkToken='synthetic-network-token'}
  }
  throw 'Unexpected API call'
}
$ok=$false; $reason=''
try {
  Import-GrokBotGateway $appPath $configPath | Out-Null
  if ($scenario -eq 'idempotent') { Import-GrokBotGateway $appPath $configPath | Out-Null }
  $ok=$true
}
catch [GrokSetupError] { $reason=$_.Exception.Message }
$result = @{ok=$ok;reason=$reason;calls=@($global:grokMockCalls);configExists=(Test-Path -LiteralPath $configPath)}
if ($result.configExists) {
  $content=[IO.File]::ReadAllText($configPath)
  $result.isOriginalInvalidConfig=($content -eq '{invalid')
  try {
    $parsed=$content | ConvertFrom-Json
    $result.preserved=($parsed.keep.hello -eq 'world')
    $result.savedGateway=($parsed.gateway.token -eq 'synthetic-gateway-token' -and $parsed.gateway.headers.'x-anyrun-network-token' -eq 'synthetic-network-token')
  } catch { }
  $acl=Get-Acl -LiteralPath $configPath
  $ids=@($acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]) | ForEach-Object {$_.IdentityReference.Value} | Select-Object -Unique)
  $userSid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
  $result.private=($acl.AreAccessRulesProtected -and @($ids | Where-Object {$_ -notin @($userSid,'S-1-5-18')}).Count -eq 0 -and $ids -contains $userSid -and $ids -contains 'S-1-5-18')
  if ($scenario -eq 'unsafe-existing-acl') {
    $result.aclUnchanged=($acl.Sddl -eq $originalAcl)
    $result.contentUnchanged=($content -eq $existing)
  }
}
$result | ConvertTo-Json -Depth 10 -Compress
'''


def _setup(tmp_path, scenario):
    env = os.environ.copy()
    env["AVATARCAST_SETUP_SCRIPT"] = str(ROOT / "scripts" / "setup_grok_bot_windows.ps1")
    env["AVATARCAST_TEST_ROOT"] = str(tmp_path)
    env["AVATARCAST_TEST_SCENARIO"] = scenario
    harness_file = tmp_path / "harness.ps1"
    harness_file.write_text(HARNESS, encoding="utf-8")
    completed = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(harness_file)],
                               text=True, capture_output=True,
                               encoding="utf-8", env=env, timeout=45)
    # The only credentials used by this test are synthetic. They still should
    # never be printed by setup, even on an error path.
    assert "synthetic-gateway-token" not in completed.stdout + completed.stderr
    assert "synthetic-network-token" not in completed.stdout + completed.stderr
    assert "eyJ0ZXN0.eyJ0ZXN0.c2ln" not in completed.stdout + completed.stderr
    assert "fixture.us10.cursorvm.com" not in completed.stdout + completed.stderr
    assert completed.returncode == 0, completed.stderr
    import json
    return json.loads(completed.stdout.strip().splitlines()[-1])


@pytest.mark.parametrize("scenario", ["new", "existing", "idempotent"])
def test_import_running_box_with_private_acl_and_no_wake(tmp_path, scenario):
    result = _setup(tmp_path, scenario)
    assert result["ok"] is True, result["reason"]
    assert result["savedGateway"] is True
    assert result["private"] is True
    if scenario in {"existing", "idempotent"}:
        assert result["preserved"] is True
    expected = ["GetSandBoxRunState", "EnsureSandBox"]
    assert [call["uri"].split("/")[-1] for call in result["calls"]] == expected * (2 if scenario == "idempotent" else 1)
    assert all(call["body"] == '{"wake":false}' for call in result["calls"] if call["uri"].endswith("EnsureSandBox"))
    assert all(call["maximumRedirection"] == 0 for call in result["calls"])


@pytest.mark.parametrize("scenario", ["sleeping", "bad-origin", "bad-format", "bad-config", "network-fail", "unsafe-existing-acl"])
def test_setup_failure_does_not_save_a_gateway(tmp_path, scenario):
    result = _setup(tmp_path, scenario)
    assert result["ok"] is False
    assert result["reason"]
    assert result.get("savedGateway") is not True
    if scenario == "sleeping":
        assert len(result["calls"]) == 1
    if scenario == "bad-format":
        assert result["calls"] == []
    if scenario == "bad-config":
        assert result["isOriginalInvalidConfig"] is True
    if scenario == "unsafe-existing-acl":
        assert "permissions" in result["reason"]
        assert result["aclUnchanged"] is True
        assert result["contentUnchanged"] is True
