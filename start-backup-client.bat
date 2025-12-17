@echo off
REM Script de démarrage automatique pour Windows
REM À configurer dans le Planificateur de tâches Windows

cd /d "%~dp0"

REM Démarrer le client en arrière-plan
start /B pythonw.exe client.py > backup_client.log 2>&1

echo Daemon de sauvegarde démarré
timeout /t 3
