<#
Build a signed Windows release from a tested desktop payload. Credentials stay
in the signing host's Azure credential provider; metadata contains no secrets.
Existing valid vendor signatures are preserved. Invalid signatures fail closed.
#>
param(
    [Parameter(Mandatory=$true)][string]$Payload,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [Parameter(Mandatory=$true)][string]$MetadataPath,
    [Parameter(Mandatory=$true)][string]$SignToolPath,
    [Parameter(Mandatory=$true)][string]$DlibPath,
    [Parameter(Mandatory=$true)][string]$InnoCompiler,
    [string]$ExpectedPublisher='FRACTAL RESEARCH GROUP LLC.',
    [int]$MaxNewSignatures=500
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$repo=Split-Path $PSScriptRoot -Parent
$Payload=(Resolve-Path -LiteralPath $Payload).Path.TrimEnd('\')
foreach ($file in @($MetadataPath,$SignToolPath,$DlibPath,$InnoCompiler)) {
    if (!(Test-Path -LiteralPath $file -PathType Leaf)) {throw "Required signing input missing: $file"}
}
foreach ($file in @($SignToolPath,$DlibPath,$InnoCompiler)) {
    if ((Get-AuthenticodeSignature $file).Status -ne 'Valid') {throw "Untrusted signing tool: $file"}
}
$metadata=Get-Content -LiteralPath $MetadataPath -Raw | ConvertFrom-Json
foreach ($field in @('Endpoint','CodeSigningAccountName','CertificateProfileName')) {
    if (!$metadata.$field) {throw "Signing metadata missing $field"}
}
$version=(Get-Content "$repo\package.json" -Raw | ConvertFrom-Json).version
$bundledVersion=(Get-Content "$Payload\runtime\Lib\site-packages\package.json" -Raw | ConvertFrom-Json).version
if ($version -ne $bundledVersion) {throw 'Source and bundled versions disagree'}
if (!(Test-Path "$Payload\DocReader.exe")) {throw 'Desktop launcher missing'}
if (Get-ChildItem $Payload -Filter 'unins*') {throw 'Use a payload without previous installer bookkeeping'}
New-Item -ItemType Directory -Force $OutputDirectory | Out-Null
$OutputDirectory=(Resolve-Path $OutputDirectory).Path
$installer=Join-Path $OutputDirectory "Read-Docs-$version-Windows-x64-Setup.exe"
if (Test-Path $installer) {throw 'Release installer already exists; verify it before rebuilding'}
$files=@(Get-ChildItem $Payload -Recurse -File | Where-Object {$_.Extension -in @('.exe','.dll','.pyd')})
$unsigned=@()
foreach ($file in $files) {
    $signature=Get-AuthenticodeSignature $file.FullName
    if ($signature.Status -eq 'NotSigned') {$unsigned+=$file.FullName}
    elseif ($signature.Status -ne 'Valid') {throw "Invalid existing signature: $($file.FullName) ($($signature.Status))"}
}
# Include the setup/uninstall signing operations in the bounded request count.
if ($unsigned.Count + 4 -gt $MaxNewSignatures) {throw "Signing bound exceeded: $($unsigned.Count) payload files"}
Write-Output "Signing $($unsigned.Count) files; preserving $($files.Count-$unsigned.Count) vendor/already valid signatures"
$arguments=@('sign','/fd','SHA256','/tr','http://timestamp.acs.microsoft.com','/td','SHA256','/dlib',$DlibPath,'/dmdf',$MetadataPath)
for ($i=0; $i -lt $unsigned.Count; $i+=25) {
    $batch=$unsigned[$i..([Math]::Min($i+24,$unsigned.Count-1))]
    & $SignToolPath @arguments @batch
    if ($LASTEXITCODE -ne 0) {throw 'Payload signing failed; keep the staging directory for inspection/recovery'}
}
$receipt=@()
foreach ($file in $files) {
    $signature=Get-AuthenticodeSignature $file.FullName
    if ($signature.Status -ne 'Valid') {throw "Payload signature verification failed: $($file.FullName)"}
    $publisher=$signature.SignerCertificate.GetNameInfo('SimpleName',$false)
    if ($file.FullName -in $unsigned -and ($publisher -ne $ExpectedPublisher -or !$signature.TimeStamperCertificate)) {
        throw "Expected publisher/timestamp missing: $($file.FullName)"
    }
    $receipt+=[ordered]@{path=$file.FullName.Substring($Payload.Length+1);sha256=(Get-FileHash $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant();status='Valid';publisher=$publisher;timestamp=[bool]$signature.TimeStamperCertificate}
}
$receipt | ConvertTo-Json -Depth 5 | Set-Content "$OutputDirectory\payload-signatures.json" -Encoding UTF8
# Let Inno sign its generated setup, uninstaller and temporary setup copies.
# Signing only the final EXE would leave these inner executables unsigned.
$signCommand='$q'+$SignToolPath+'$q sign /fd SHA256 /tr http://timestamp.acs.microsoft.com /td SHA256 /dlib $q'+$DlibPath+'$q /dmdf $q'+$MetadataPath+'$q $f'
& $InnoCompiler "/DAppVersion=$version" "/DPayload=$Payload" '/DSignRelease=1' "/O$OutputDirectory" "/SReadDocs=$signCommand" "$PSScriptRoot\windows.iss"
if ($LASTEXITCODE -ne 0) {throw 'Signed installer compilation failed'}
& $SignToolPath verify /pa /all /v $installer
if ($LASTEXITCODE -ne 0) {throw 'Installer trust verification failed'}
$signature=Get-AuthenticodeSignature $installer
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.GetNameInfo('SimpleName',$false) -ne $ExpectedPublisher -or !$signature.TimeStamperCertificate) {throw 'Installer signer/timestamp verification failed'}
[ordered]@{status='PASS';version=$version;artifact=(Split-Path $installer -Leaf);sha256=(Get-FileHash $installer -Algorithm SHA256).Hash.ToLowerInvariant();bytes=(Get-Item $installer).Length;publisher=$ExpectedPublisher;timestamp=$true;payloadFiles=$files.Count;newPayloadSignatures=$unsigned.Count;preservedSignatures=$files.Count-$unsigned.Count;provider='Microsoft Artifact Signing'} | ConvertTo-Json | Set-Content "$OutputDirectory\signing-receipt.json" -Encoding UTF8
Get-Content "$OutputDirectory\signing-receipt.json"
