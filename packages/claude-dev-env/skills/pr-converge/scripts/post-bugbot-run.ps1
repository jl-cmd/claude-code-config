[CmdletBinding()]
param(
    [Parameter(Position = 0, HelpMessage = 'GitHub pull request URL or owner/repo#number.')]
    [string] $PullRequest = '',
    [Parameter(HelpMessage = 'owner/repo when using -Number instead of a URL or owner/repo#number.')]
    [string] $Repository = '',
    [Parameter(HelpMessage = 'Pull request number; requires -Repository.')]
    [int] $Number = 0
)

$LiteralBugbotRunBody = "bugbot run`n"

function Resolve-InvocationMode {
    param([string] $PullRequestInput, [string] $RepositoryInput, [int] $NumberInput)

    if ($NumberInput -gt 0) {
        if ([string]::IsNullOrWhiteSpace($RepositoryInput)) {
            throw 'When -Number is set, -Repository must be owner/repo (for example jl-cmd/claude-code-config).'
        }
        return @{ Mode = 'RepoNumber'; Repository = $RepositoryInput; Number = $NumberInput }
    }

    $trimmed = $PullRequestInput.Trim()
    if (-not [string]::IsNullOrWhiteSpace($trimmed)) {
        return @{ Mode = 'Uri'; PullRequest = $trimmed }
    }

    throw 'Provide a pull request URL, owner/repo#number as the first argument, or -Repository with -Number.'
}

function Build-GhArgumentList {
    param([hashtable] $Invocation, [string] $BodyFilePath)

    if ($Invocation.Mode -eq 'RepoNumber') {
        return @(
            'pr', 'comment',
            $Invocation.Number.ToString(),
            '-R', $Invocation.Repository,
            '--body-file', $BodyFilePath
        )
    }

    $trimmed = $Invocation.PullRequest
    if ($trimmed -match '^https://github\.com/[^/]+/[^/]+/pull/\d+') {
        return @('pr', 'comment', $trimmed, '--body-file', $BodyFilePath)
    }

    if ($trimmed -match '^([^/]+)/([^/#]+)#(\d+)$') {
        $owner = $Matches[1]
        $repository_name = $Matches[2]
        $pull_number = $Matches[3]
        return @(
            'pr', 'comment',
            $pull_number,
            '-R', ('{0}/{1}' -f $owner, $repository_name),
            '--body-file', $BodyFilePath
        )
    }

    throw ('Unrecognized PullRequest "{0}". Use a https://github.com/owner/repo/pull/NN URL or owner/repo#NN.' -f $trimmed)
}

$invocation = Resolve-InvocationMode -PullRequestInput $PullRequest -RepositoryInput $Repository -NumberInput $Number
$body_file_path = [System.IO.Path]::ChangeExtension([System.IO.Path]::GetTempFileName(), '.md')

try {
    $utf8_without_byte_order_mark = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($body_file_path, $LiteralBugbotRunBody, $utf8_without_byte_order_mark)

    $null = Get-Command gh -ErrorAction Stop
    $argument_list = Build-GhArgumentList -Invocation $invocation -BodyFilePath $body_file_path
    & gh @argument_list
    if ($LASTEXITCODE -ne 0) {
        throw ('gh exited with code {0}.' -f $LASTEXITCODE)
    }
} finally {
    Remove-Item -LiteralPath $body_file_path -Force -ErrorAction SilentlyContinue
}
