$ErrorActionPreference = 'Stop'

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $ProjectDir 'src\bili_mp4box_downloader.py'
$Icon = Join-Path $ProjectDir 'assets\icon.ico'
$Mp4Box = Join-Path $ProjectDir 'vendor\MP4Box.exe'
$DistDir = Join-Path $ProjectDir 'dist'
$BuildDir = Join-Path $ProjectDir 'build'

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name 'B站 MP4Box 下载器' `
  --icon $Icon `
  --add-data "$Icon;." `
  --add-binary "$Mp4Box;." `
  --exclude-module numpy `
  --exclude-module scipy `
  --exclude-module pandas `
  --exclude-module matplotlib `
  --distpath $DistDir `
  --workpath $BuildDir `
  --specpath $ProjectDir `
  $Source

if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
Write-Host "Built: $(Join-Path $DistDir 'B站 MP4Box 下载器.exe')"
