@echo off
echo ===> Deploying BiziShip to HexcelPack Production...
PowerShell -ExecutionPolicy Bypass -File "%~dp0deploy_hexcelpack_production.ps1"
pause
