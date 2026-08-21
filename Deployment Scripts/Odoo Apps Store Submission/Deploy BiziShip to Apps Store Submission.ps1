$Source = "C:\Startups\BiziShip.ai\SW\Odoo\biziship"
$Repo = "C:\Startups\BiziShip.ai\SW\Odoo\biziship_apps_store_submission"
$Target = Join-Path $Repo "biziship"
$Branch = "17.0"

# INCLUDE-LIST (default-deny), not exclude-list. An exclude-list is default-allow:
# any new file dropped into $Source (a stray .docx, a scratch script, etc.) ships to
# the PUBLIC repo unless someone remembers to blocklist it by name — which is exactly
# how "Run Odoo.docx" / "Set up new env.docx" (containing a live API key) leaked to
# the Apps Store submission repo on 2026-07-12. An include-list only ships what is
# explicitly named here, so anything new added to the dev folder is safe by default.
$IncludeFiles = @(
    "__init__.py",
    "__manifest__.py",
    "api_utils.py",
    "requirements.txt",
    "README.md"
)
$IncludeDirs = @(
    "controllers",
    "data",
    "models",
    "security",
    "static",
    "tests",
    "views",
    "wizards"
)

Write-Host "===> Switching submission repo to $Branch"
Set-Location $Repo
git checkout $Branch 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Branch $Branch does not exist locally yet - creating it."
    git checkout -b $Branch
}

Write-Host "===> Removing old target folder"
if (Test-Path $Target) {
    Remove-Item $Target -Recurse -Force
}
New-Item -ItemType Directory -Path $Target -Force | Out-Null

Write-Host "===> Copying only explicitly-listed module files"
foreach ($f in $IncludeFiles) {
    $srcFile = Join-Path $Source $f
    if (Test-Path $srcFile) {
        Copy-Item $srcFile (Join-Path $Target $f) -Force
    } else {
        Write-Host "  (skip, not present: $f)"
    }
}

# Dead/unregistered static assets: not loaded by any entry in __manifest__.py's
# assets, left over from reverted features. Not sensitive, just clutter that
# shouldn't ship in a public listing.
$DeadCodeFiles = @(
    "biziship_version_dialog.js",
    "biziship_version_dialog.xml",
    "nmfc_suggestion.js"
)

Write-Host "===> Copying only explicitly-listed module folders"
foreach ($d in $IncludeDirs) {
    $srcDir = Join-Path $Source $d
    if (Test-Path $srcDir) {
        $dstDir = Join-Path $Target $d
        robocopy $srcDir $dstDir /MIR /XD "__pycache__" /XF "*.pyc" "secrets.json" ".env" $DeadCodeFiles | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy failed copying $d" }
    }
}

Write-Host "===> Safety-net scan: fail loudly on any unexpected file type"
$BadExtensions = @("*.docx", "*.doc", "*.xlsx", "*.pptx", "*.zip", "*.7z", "*.rar", "*.pem", "*.key", "*.pfx", "*.env")
foreach ($pattern in $BadExtensions) {
    $hits = Get-ChildItem -Path $Target -Recurse -Filter $pattern -File -ErrorAction SilentlyContinue
    if ($hits) {
        $hits | ForEach-Object { Write-Host "  UNEXPECTED FILE: $($_.FullName)" }
        throw "Unexpected file type ($pattern) found in the copy - aborting before commit"
    }
}

Write-Host "===> Belt-and-suspenders secrets check before commit"
if (Test-Path (Join-Path $Target "secrets.json")) { throw "secrets.json made it into the copy - aborting" }
$fallbackHit = Select-String -Path (Join-Path $Target "api_utils.py") -Pattern "BIZISHIP_FALLBACK_KEY" -ErrorAction SilentlyContinue
if ($fallbackHit) { throw "Hardcoded fallback key pattern found in api_utils.py - aborting" }
$keyPatternHit = Get-ChildItem -Path $Target -Recurse -File | Select-String -Pattern "116b2056ca09c1006119ec548cff60a66a1182b579b86f0f6168ec44e74a1409" -ErrorAction SilentlyContinue
if ($keyPatternHit) { throw "The previously-exposed API key literal was found in the copy - aborting" }

Write-Host "===> Git add"
git add biziship
if ($LASTEXITCODE -ne 0) { throw "git add failed" }

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$commitMessage = "Sync from dev module - $timestamp"

Write-Host "===> Git commit"
git commit -m $commitMessage
if ($LASTEXITCODE -ne 0) {
    Write-Host "No changes to commit, or commit failed."
}

Write-Host "===> Git push"
git push origin $Branch
if ($LASTEXITCODE -ne 0) { throw "git push failed" }

Write-Host "===> Done. Reminder: bump the version in __manifest__.py before syncing a real"
Write-Host "     feature release, so the Apps Store listing reflects a new version number."
