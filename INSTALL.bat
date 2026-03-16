@echo off
title FgAi Bot - Installer
color 0A
setlocal enabledelayedexpansion

echo.
echo  ========================================
echo   FgAi Brawlstars Bot - INSTALLER
echo  ========================================
echo.

:: ── Check Python ─────────────────────────────────────────────────────────────
python --version >nul 2>&1
if !errorlevel! neq 0 (
    echo  [ERROR] Python nije instaliran!
    echo  Skini Python 3.11 sa https://www.python.org/downloads/
    echo  OBAVEZNO stikliraj "Add Python to PATH"!
    pause
    exit /b 1
)
echo  [OK] Python pronadjen

:: ── Check Git ────────────────────────────────────────────────────────────────
git --version >nul 2>&1
if !errorlevel! neq 0 (
    echo  [!] Git nije instaliran - potreban za scrcpy
    echo  Skini sa https://git-scm.com/download/win i instaliraj
    echo  Pa ponovo pokreni INSTALL.bat
    pause
    exit /b 1
)
echo  [OK] Git pronadjen
echo.

:: ── Detect GPU ───────────────────────────────────────────────────────────────
echo  [*] Detektujem graficku karticu...
set GPU_TYPE=unknown

wmic path win32_VideoController get name 2>nul | findstr /i "nvidia geforce gtx rtx quadro" >nul
if !errorlevel! equ 0 ( set GPU_TYPE=nvidia & echo  [GPU] NVIDIA pronadjena! & goto :adb_setup )

wmic path win32_VideoController get name 2>nul | findstr /i "amd radeon rx vega" >nul
if !errorlevel! equ 0 ( set GPU_TYPE=amd & echo  [GPU] AMD Radeon pronadjena! & goto :adb_setup )

echo  Nije moguce automatski detektovati graficku.
echo.
echo  [1] NVIDIA  (GTX / RTX)
echo  [2] AMD     (Radeon RX)
echo  [3] CPU mode
echo.
set /p GPU_CHOICE="  Izbor (1/2/3): "
if "!GPU_CHOICE!"=="1" set GPU_TYPE=nvidia
if "!GPU_CHOICE!"=="2" set GPU_TYPE=amd
if "!GPU_CHOICE!"=="3" set GPU_TYPE=cpu

:: ── LDPlayer ADB Setup ───────────────────────────────────────────────────────
:adb_setup
echo.
echo  [*] Trazim LDPlayer i podesavam ADB...

set LDP_PATH=
set ADB_OK=0
set ADB_PORT=5555

for %%P in (
    "%LOCALAPPDATA%\LDPlayer\LDPlayer9"
    "%LOCALAPPDATA%\LDPlayer\LDPlayer4"
    "C:\LDPlayer\LDPlayer9"
    "C:\LDPlayer\LDPlayer4"
    "C:\Program Files\LDPlayer\LDPlayer9"
    "C:\Program Files\LDPlayer\LDPlayer4"
) do (
    if exist "%%~P\ldconsole.exe" (
        set LDP_PATH=%%~P
        goto :ldp_found
    )
)

echo  [!] LDPlayer nije pronadjen automatski.
echo  [1] Unesi putanju rucno
echo  [2] Preskocu
set /p LDP_C="  Izbor (1/2): "
if "!LDP_C!"=="2" goto :install
set /p LDP_PATH="  Putanja do LDPlayer foldera: "
if not exist "!LDP_PATH!\ldconsole.exe" (
    echo  [!] Putanja nije validna, preskacemo.
    goto :install
)

:ldp_found
echo  [OK] LDPlayer: !LDP_PATH!

:: Ukljuci ADB debugging
"!LDP_PATH!\ldconsole.exe" globalsetting --enable-adb 1 >nul 2>&1
echo  [OK] ADB debugging ukljucen

:: Odaberi adb.exe
set ADB_EXE=%~dp0adb.exe
if not exist "!ADB_EXE!" set ADB_EXE=!LDP_PATH!\adb.exe
if not exist "!ADB_EXE!" (
    echo  [!] adb.exe nije pronadjen, preskacemo.
    goto :install
)

:: Konektuj
"!ADB_EXE!" start-server >nul 2>&1
timeout /t 2 /nobreak >nul

for %%PORT in (5555 5556 5557 5558 16384 5635) do (
    "!ADB_EXE!" connect 127.0.0.1:%%PORT >nul 2>&1
    "!ADB_EXE!" -s 127.0.0.1:%%PORT shell echo ok >nul 2>&1
    if !errorlevel! equ 0 (
        echo  [OK] ADB konektovan na port %%PORT
        set ADB_OK=1
        set ADB_PORT=%%PORT
        goto :adb_done
    )
)
echo  [!] ADB konekcija nije uspjela - pokreni LDPlayer pa START.bat

:adb_done
if "!ADB_OK!"=="1" (
    if exist "%~dp0cfg\general_config.toml" (
        python -c "import re; f=open('cfg/general_config.toml','r+'); c=f.read(); c=re.sub(r'emulator_port\s*=\s*\d+','emulator_port = !ADB_PORT!',c); f.seek(0); f.write(c); f.truncate(); f.close()" 2>nul
        echo  [OK] Port !ADB_PORT! sacuvan u config
    )
)

:: ── Install packages ──────────────────────────────────────────────────────────
:install
echo.
echo  ========================================
echo  [*] Instaliram Python pakete...
echo  ========================================
echo.

python -m pip install --upgrade pip --quiet

echo  [1/5] Core paketi...
python -m pip install customtkinter~=5.2.2 keyboard pillow requests toml aiohttp discord.py shapely ultralytics bettercam packaging google-play-scraper easyocr pywin32 pyautogui numpy --quiet
echo  [OK] Core

echo  [2/5] OpenCV...
python -m pip uninstall opencv-python opencv-python-headless -y --quiet 2>nul
python -m pip install opencv-python --quiet
echo  [OK] OpenCV

echo  [3/5] ADB / scrcpy...
python -m pip install "adbutils==1.2.1" whichcraft apkutils2 cigam av --quiet
python -m pip install "scrcpy-client@git+https://github.com/leng-yue/py-scrcpy-client.git@v0.5.0" --no-deps --quiet
echo  [OK] ADB

echo  [4/5] ONNX + PyTorch...
python -m pip install onnxruntime-gpu --quiet

if "!GPU_TYPE!"=="nvidia" (
    python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121 --quiet
    echo  [OK] PyTorch NVIDIA CUDA
) else if "!GPU_TYPE!"=="amd" (
    python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118 --quiet
    echo  [OK] PyTorch AMD
) else (
    python -m pip install torch torchvision --quiet
    echo  [OK] PyTorch CPU
)

echo  [5/5] Cistim cache...
python -m pip cache purge --quiet
echo  [OK] Cache

echo.
echo  ========================================
echo   INSTALACIJA ZAVRSENA!
echo  ========================================
echo.
if "!ADB_OK!"=="1" (
    echo  ADB  : Konektovan na port !ADB_PORT!
) else (
    echo  ADB  : Ukljuci rucno u LDPlayer
    echo         Settings - Other Settings - ADB Debugging = ON
)
echo.
echo  Sve je spremno! Pokreni START.bat
echo.
pause
