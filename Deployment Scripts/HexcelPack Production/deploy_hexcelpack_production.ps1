$Source = "C:\Startups\BiziShip.ai\SW\Odoo\biziship"
$Repo = "C:\Startups\BiziShip.ai\Customers\HexcelPack\biziShipGItHubModule\hexcelpack"
$Target = Join-Path $Repo "biziship"
$Branch = "production"

Write-Host "===> Switching repo to $Branch"
Set-Location $Repo
git checkout $Branch
if ($LASTEXITCODE -ne 0) { throw "git checkout failed" }

git pull
if ($LASTEXITCODE -ne 0) { throw "git pull failed" }

Write-Host "===> Removing old target folder"
if (Test-Path $Target) {
    Remove-Item $Target -Recurse -Force
}

Write-Host "===> Copying updated module"
robocopy $Source $Target /MIR
if ($LASTEXITCODE -ge 8) { throw "robocopy failed" }

Write-Host "===> Removing embedded .git (prevents submodule issue)"
if (Test-Path "$Target\.git") {
    Remove-Item "$Target\.git" -Recurse -Force
}

Write-Host "===> Cleaning junk files"
Get-ChildItem $Target -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $Target -Recurse -Filter "~$*" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem $Target -Recurse -Filter "secrets.json" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "===> Removing stale submodule reference (if any)"
git rm --cached biziship 2>$null

Write-Host "===> Git add"
git add biziship
if ($LASTEXITCODE -ne 0) { throw "git add failed" }

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$commitMessage = "Update biziship for HexcelPack production - $timestamp"

Write-Host "===> Git commit"
git commit -m $commitMessage
if ($LASTEXITCODE -ne 0) {
    Write-Host "No changes to commit, or commit failed."
}

Write-Host "===> Git push"
git push origin $Branch
if ($LASTEXITCODE -ne 0) { throw "git push failed" }

Write-Host "===> Done. Monitor build at HexcelPack Odoo.sh production branch."
