$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$target = [IO.Path]::GetFullPath((Join-Path $root 'build\desktop'))
New-Item -ItemType Directory -Path $target -Force | Out-Null
$sdk = Join-Path $root 'build/webview2-sdk'
$archive = Join-Path $root 'build/webview2.zip'
Invoke-WebRequest 'https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/1.0.4191.47/microsoft.web.webview2.1.0.4191.47.nupkg' -OutFile $archive
if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLower() -ne 'f492bbf547d0da329553b6727435b677579b1e9f91cc9e4a1ad029366d5f23d0') { throw 'WebView2 SDK checksum mismatch' }
Expand-Archive $archive $sdk
Copy-Item "$sdk/lib/net462/Microsoft.Web.WebView2.Core.dll" $target
Copy-Item "$sdk/lib/net462/Microsoft.Web.WebView2.WinForms.dll" $target
Copy-Item "$sdk/runtimes/win-x64/native/WebView2Loader.dll" $target
Copy-Item "$sdk/LICENSE.txt" "$target/WebView2-LICENSE.txt"
Copy-Item "$root/desktop/WeChatMemory.exe.config" $target
$compiler = Join-Path $env:SystemRoot 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
$source = [IO.Path]::GetFullPath((Join-Path $root 'desktop\WeChatMemory.cs'))
& $compiler /nologo /target:winexe /platform:x64 /optimize+ "/out:$target\WeChatMemory.exe" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll "/reference:$target\Microsoft.Web.WebView2.Core.dll" "/reference:$target\Microsoft.Web.WebView2.WinForms.dll" $source
if ($LASTEXITCODE -ne 0) { throw 'Desktop compilation failed' }
$bootstrap = Join-Path $target 'MicrosoftEdgeWebview2Setup.exe'
Invoke-WebRequest 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $bootstrap
$signature = Get-AuthenticodeSignature $bootstrap
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') { throw 'WebView2 bootstrapper signature is not valid Microsoft signature' }
$manifest = Get-ChildItem $target -Recurse -File | Where-Object Name -ne 'SHA256SUMS.txt' | ForEach-Object {
    (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower() + '  ' + [IO.Path]::GetRelativePath($target, $_.FullName).Replace('\','/')
}
$manifest | Set-Content -Encoding utf8 "$target/SHA256SUMS.txt"
