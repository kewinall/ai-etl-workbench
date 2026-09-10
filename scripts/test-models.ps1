Write-Host 'Codex CLI'; Get-Command codex -ErrorAction SilentlyContinue|Select-Object Source; codex --version
Write-Host 'GitHub Copilot'; Get-Command gh -ErrorAction SilentlyContinue|Select-Object Source; gh auth status; gh copilot --version
