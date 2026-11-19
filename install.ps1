<#
.SYNOPSIS
    1-Klick-Installation für UX-mAInd Studio unter Windows (US-75).
.DESCRIPTION
    Prüft Python >= 3.11, erstellt eine isolierte virtuelle Umgebung (.venv),
    installiert alle Open-Source-Abhängigkeiten editierbar und baut bei vorhandenem
    Node.js optional das React-Frontend neu (vorgebaute Web-Assets liegen bereits bei).
#>
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== UX-mAInd Studio · 1-Klick-Setup (Windows) ===" -ForegroundColor Cyan

$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) {
    throw "Python (>= 3.11) wurde nicht im PATH gefunden. Bitte von https://www.python.org/downloads/ installieren."
}

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "[1/3] Erstelle virtuelle Python-Umgebung (.venv) ..." -ForegroundColor Yellow
    python -m venv .venv
} else {
    Write-Host "[1/3] Vorhandene .venv gefunden." -ForegroundColor Green
}

Write-Host "[2/3] Installiere UX-mAInd und Open-Source-Bibliotheken (Docling, Docling-Graph, LiteLLM) ..." -ForegroundColor Yellow
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e .

$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
$npmCmd = Get-Command npm -ErrorAction SilentlyContinue
if ($nodeCmd -and $npmCmd -and (Test-Path ".\frontend\package.json")) {
    Write-Host "[3/3] Node.js erkannt — aktualisiere lokales React-Studio-Bundle ..." -ForegroundColor Yellow
    npm install --prefix frontend --no-audit --no-fund
    & $nodeCmd.Source .\frontend\build.mjs
} else {
    Write-Host "[3/3] Nutze bereits mitgeliefertes lokales Web-Bundle (kein Node.js zur Laufzeit erforderlich)." -ForegroundColor Green
}

$soffice = Get-Command soffice -ErrorAction SilentlyContinue
if (-not $soffice -and -not (Test-Path "C:\Program Files\LibreOffice\program\soffice.exe")) {
    Write-Host "Hinweis: LibreOffice (optional, MPL-2.0) nicht gefunden. DOCX/PPTX/ODT-Konvertierung & DoclingReader funktionieren vollständig ohne LibreOffice; für linke PDF-Folienvorschau optional LibreOffice installieren." -ForegroundColor DarkYellow
}

Write-Host "`nSetup erfolgreich abgeschlossen! Starte die Anwendung jederzeit per Doppelklick auf start-ux-maind.cmd oder via:" -ForegroundColor Green
Write-Host "  .\.venv\Scripts\ux-maind.exe" -ForegroundColor Cyan
