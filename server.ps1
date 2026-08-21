# 简易本地 HTTP 服务器（PowerShell HttpListener）
# 用途：为 Reddit 分析工具提供本地访问，无需 python/node
$root = $PSScriptRoot
if (-not $root) { $root = (Get-Location).Path }
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add('http://localhost:8765/')
$listener.Start()
Write-Host "Server running at http://localhost:8765/  (root: $root)"
Write-Host "Press Ctrl+C to stop."
while ($listener.IsListening) {
  try {
    $ctx = $listener.GetContext()
  } catch {
    break
  }
  $req = $ctx.Request
  $resp = $ctx.Response
  $path = $req.Url.AbsolutePath
  if ($path -eq '/' -or $path -eq '') { $path = '/index.html' }
  $rel = $path -replace '/', '\'
  $file = Join-Path $root $rel.TrimStart('\')
  if (Test-Path $file -PathType Leaf) {
    $bytes = [System.IO.File]::ReadAllBytes($file)
    $ext = [System.IO.Path]::GetExtension($file).ToLower()
    switch ($ext) {
      '.html' { $resp.ContentType = 'text/html; charset=utf-8' }
      '.css'  { $resp.ContentType = 'text/css; charset=utf-8' }
      '.js'   { $resp.ContentType = 'application/javascript; charset=utf-8' }
      '.json' { $resp.ContentType = 'application/json; charset=utf-8' }
      '.png'  { $resp.ContentType = 'image/png' }
      '.jpg'  { $resp.ContentType = 'image/jpeg' }
      '.svg'  { $resp.ContentType = 'image/svg+xml' }
      default { $resp.ContentType = 'application/octet-stream' }
    }
    $resp.ContentLength64 = $bytes.Length
    $resp.OutputStream.Write($bytes, 0, $bytes.Length)
  } else {
    $resp.StatusCode = 404
    $msg = [System.Text.Encoding]::UTF8.GetBytes('404 Not Found: ' + $path)
    $resp.ContentType = 'text/plain; charset=utf-8'
    $resp.OutputStream.Write($msg, 0, $msg.Length)
  }
  $resp.Close()
}
