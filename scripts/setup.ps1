$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $root ".env"
if (Test-Path $envPath) {
  throw ".env already exists. It was left untouched."
}
$password = Read-Host "Create owner password (14+ characters)" -AsSecureString
$confirmation = Read-Host "Confirm owner password" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($password)
$confirmPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($confirmation)
try {
  $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  $confirmPlain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($confirmPtr)
  if ($plain.Length -lt 14) { throw "Use at least 14 characters." }
  if ($plain -cne $confirmPlain) { throw "Passwords did not match." }
  $salt = New-Object byte[] 32
  $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
  $rng.GetBytes($salt)
  $derive = [Security.Cryptography.Rfc2898DeriveBytes]::new(
    $plain, $salt, 600000, [Security.Cryptography.HashAlgorithmName]::SHA256
  )
  $hash = $derive.GetBytes(32)
  $secret = New-Object byte[] 48
  $rng.GetBytes($secret)
  $googleTokenKeyBytes = New-Object byte[] 32
  $rng.GetBytes($googleTokenKeyBytes)
  $googleTokenKey = [Convert]::ToBase64String($googleTokenKeyBytes).Replace('+', '-').Replace('/', '_')
  $lines = @(
    "BIKASH_DATABASE_PATH=./data/bikash.sqlite3"
    "BIKASH_OWNER_SALT=$([Convert]::ToHexString($salt).ToLowerInvariant())"
    "BIKASH_OWNER_HASH=$([Convert]::ToHexString($hash).ToLowerInvariant())"
    "BIKASH_SESSION_SECRET=$([Convert]::ToHexString($secret).ToLowerInvariant())"
    "BIKASH_GOOGLE_TOKEN_ENCRYPTION_KEY=$googleTokenKey"
    "BIKASH_SESSION_MINUTES=720"
    "BIKASH_COOKIE_SECURE=false"
    "MODEL_PROVIDER=none"
    "OLLAMA_BASE_URL=http://127.0.0.1:11434"
    "OLLAMA_MODEL="
  )
  [IO.File]::WriteAllText($envPath, ($lines -join [Environment]::NewLine) + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
  Write-Host "Owner profile created. Password is not stored; only a derived hash is saved."
} finally {
  if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
  if ($confirmPtr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($confirmPtr) }
  $plain = $null
  $confirmPlain = $null
  if ($rng) { $rng.Dispose() }
  if ($googleTokenKeyBytes) { [Array]::Clear($googleTokenKeyBytes, 0, $googleTokenKeyBytes.Length) }
}
