# Windows release signing

Build and test the payload on Windows with `build_desktop.py`, `smoke_desktop.py`,
`smoke_speech.py`, `smoke_window.py` and `smoke_launcher.py`. The last check runs
the actual installed EXE with a disposable profile, microphone capture disabled
and no developer tools on PATH. Desktop CI can stage Windows alone with the
`platform: windows` workflow input. Its output is explicitly UNSIGNED and must
not be offered as the signed public download.

On the authorized signing host, use the existing Microsoft Artifact Signing
account and active public-trust profile. Authentication uses the host's Azure
credential provider; do not copy credentials into the repository or CI logs.
The metadata JSON contains Endpoint, CodeSigningAccountName,
CertificateProfileName and an ExcludeCredentials list. For an interactive Azure
CLI session, exclude other providers and retain AzureCliCredential.

Use a verified Microsoft signing client and Windows SDK SignTool. The tested
client is Microsoft.ArtifactSigning.Client 1.0.151, which requires .NET 10.
Verify its NuGet signature with `dotnet nuget verify PACKAGE --all` before use.
Run `sign_windows.ps1` with Payload, OutputDirectory, MetadataPath, SignToolPath,
DlibPath and InnoCompiler. It refuses invalid vendor signatures, preserves valid
ones, bounds new signing operations, signs all remaining PE files, and asks Inno
to sign setup and its generated inner executables. It writes a payload signature
inventory and installer hash/publisher/timestamp receipt. Keep these receipts.

Install the resulting EXE and verify the installed uninstaller and complete PE
inventory. Repeat the full EXE smoke and offline speech checks on those installed
bytes. Check clean installation, upgrade, shortcut ownership and uninstall while
preserving user data. Publish an immutable versioned asset and SHA256SUMS only
after these gates pass; then verify the anonymous download's hash and signature
before updating the public manifest. This host-driven signing step uses an
existing account; GitHub OIDC signing is not configured yet.

Publisher verification does not establish SmartScreen reputation or physical
microphone/keyboard/speaker acceptance. Keep those limits explicit. Never ask
users to disable Windows protections to install a release.

References: [Microsoft signing integration](https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-signing-integrations),
[Windows reputation checks](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation),
[Inno signing and temporary copies](https://jrsoftware.org/ishelp/topic_setup_signtool.htm).
