$owner = "jl-cmd"
$repo = "claude-code-config"
$prNumber = 415
$sha = "37f9e6c9"

$comments = @(
    @{id=3214999044; body="Fixed in $sha -- title is now HTML-escaped via escape() before interpolation into <title> tag in main()"}
    @{id=3214999049; body="Fixed in $sha -- language identifier validated with re.match(r'^[A-Za-z0-9_+#-]+$') before emitting class=language-"}
    @{id=3214999053; body="Fixed in $sha -- _is_exempt_path now checks for basename in (readme.md, changelog.md) case-insensitively"}
    @{id=3214999057; body="Fixed in $sha -- reordered _inline_format to protect link syntax with placeholders before applying bold/italic/code, links converted last"}
)

foreach ($each in $comments) {
    $payload = @{body = $each.body} | ConvertTo-Json -Compress
    $payloadPath = [System.IO.Path]::ChangeExtension((New-TemporaryFile).FullName, '.json')
    [IO.File]::WriteAllText($payloadPath, $payload, [Text.UTF8Encoding]::new($false))

    $endpoint = "repos/$owner/$repo/pulls/$prNumber/comments/$($each.id)/replies"
    $result = gh api $endpoint --method POST --input $payloadPath 2>&1
    $status = if ($LASTEXITCODE -eq 0) { "OK" } else { "FAILED: $result" }
    Write-Output "Comment $($each.id): $status"

    Remove-Item -Path $payloadPath -Force -ErrorAction SilentlyContinue
}
