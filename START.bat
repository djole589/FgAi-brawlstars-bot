@echo off
title FgAi Brawlstars Bot
color 0A

echo.
echo  ███████╗ ██████╗      █████╗ ██╗
echo  ██╔════╝██╔════╝     ██╔══██╗██║
echo  █████╗  ██║  ███╗    ███████║██║
echo  ██╔══╝  ██║   ██║    ██╔══██║██║
echo  ██║     ╚██████╔╝    ██║  ██║██║
echo  ╚═╝      ╚═════╝     ╚═╝  ╚═╝╚═╝
echo.
echo  FgAi Brawlstars Bot - Starting...
echo  ===================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python nije instaliran!
    echo  Pokreni prvo INSTALL.bat
    pause
    exit /b 1
)

:: Check main.py exists
if not exist "main.py" (
    echo  [ERROR] main.py nije pronasjen!
    echo  Pokreni bat iz foldera gdje su fajlovi bota.
    pause
    exit /b 1
)

:: Check LDPlayer running (optional warning)
tasklist /fi "imagename eq LDPlayer.exe" 2>nul | findstr /i "ldplayer" >nul
if %errorlevel% neq 0 (
    tasklist /fi "imagename eq LDPlayer4.exe" 2>nul | findstr /i "ldplayer" >nul
    if %errorlevel% neq 0 (
        echo  [!] UPOZORENJE: LDPlayer nije detektovan kao pokrenut proces.
        echo      Pokreni LDPlayer i otvori Brawl Stars pre nego nastavis.
        echo.
        pause
    )
)

echo  [OK] Pokrecem FgAi Bot...
echo.
echo  Napomene:
echo    - U LDPlayer ukljuci ADB: Settings ^> Other ^> ADB Debugging ON
echo    - Pritisni F2 u igri za ESP overlay toggle
echo    - Zatvori ovaj prozor da zaustavis bota
echo.

python main.py

echo.
echo  [Bot zaustavljen]
pause
