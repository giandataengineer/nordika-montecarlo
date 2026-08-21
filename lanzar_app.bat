@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

set "ENV_NAME=montecarlo"
set "APP_URL=http://127.0.0.1:8765/"
set "SERVER_SCRIPT=scripts\mission_control_server.py"
set "WAIT_SECONDS=60"
set "CONDA_CMD="

call :resolve_conda
if errorlevel 1 exit /b 1

if not exist "%SERVER_SCRIPT%" (
    echo [ERROR] No encuentro %SERVER_SCRIPT%.
    exit /b 1
)

echo [1/4] Validando el entorno Conda "%ENV_NAME%"...
call "%CONDA_CMD%" run -n "%ENV_NAME%" python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] El entorno "%ENV_NAME%" no existe o no se puede ejecutar.
    echo         Crea el entorno con: conda env create -f environment.yml
    exit /b 1
)

echo [2/4] Comprobando dependencias del proyecto...
call "%CONDA_CMD%" run -n "%ENV_NAME%" python -c "import numpy, pandas, sklearn, plotly, dotenv" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Faltan dependencias dentro del entorno "%ENV_NAME%".
    echo         Reinstala el entorno con: conda env update -n %ENV_NAME% -f environment.yml --prune
    exit /b 1
)

if not exist ".env" (
    echo [AVISO] No existe .env en la raiz. La app arranca igual, pero cualquier uso de OpenAI fallara hasta definir OPENAI_API_KEY.
)

echo [3/4] Revisando si existe una instancia previa de Mission Control...
call :restart_existing_mission_control
if errorlevel 1 exit /b 1

echo [4/4] Arrancando Mission Control en una ventana nueva...
start "Monte Carlo Mission Control" cmd /k "cd /d "%cd%" && "%CONDA_CMD%" run --no-capture-output -n "%ENV_NAME%" python "%SERVER_SCRIPT%""

echo Esperando a que el backend responda en %APP_URL%
for /L %%S in (1,1,%WAIT_SECONDS%) do (
    call :is_app_ready
    if not errorlevel 1 goto open_browser
    echo   intento %%S de %WAIT_SECONDS%...
    timeout /t 1 /nobreak >nul
)

echo [ERROR] La app no respondio en %WAIT_SECONDS% segundos.
echo         Revisa la ventana "Monte Carlo Mission Control" para ver el error de arranque.
exit /b 1

:open_browser
echo Abriendo %APP_URL%
start "" "%APP_URL%"
exit /b 0

:restart_existing_mission_control
set "MC_PID="
set "MC_COMMAND="

for /f "usebackq delims=" %%I in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; $listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if (-not $listener) { exit 0 }; $proc = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + $listener.OwningProcess); if ($proc) { Write-Output ('PID=' + $proc.ProcessId); Write-Output ('CMD=' + $proc.CommandLine) }"`) do (
    set "LINE=%%I"
    if /I "!LINE:~0,4!"=="PID=" set "MC_PID=!LINE:~4!"
    if /I "!LINE:~0,4!"=="CMD=" set "MC_COMMAND=!LINE:~4!"
)

if not defined MC_PID (
    echo         No hay instancia previa escuchando en el puerto 8765.
    exit /b 0
)

echo         Puerto 8765 ocupado por PID !MC_PID!.
echo         Comando: !MC_COMMAND!

echo(!MC_COMMAND! | findstr /I /C:"mission_control_server.py" >nul
if errorlevel 1 (
    echo [ERROR] El puerto 8765 esta ocupado por otro proceso distinto de Mission Control.
    echo         Cierra ese proceso o cambia el puerto antes de volver a lanzar la app.
    exit /b 1
)

echo         Cerrando instancia previa para cargar la version mas reciente del codigo...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Stop-Process -Id !MC_PID! -Force"
if errorlevel 1 (
    echo [ERROR] No se pudo cerrar la instancia previa de Mission Control.
    exit /b 1
)

for /L %%S in (1,1,15) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) { exit 1 } else { exit 0 }" >nul 2>&1
    if not errorlevel 1 exit /b 0
    timeout /t 1 /nobreak >nul
)

echo [ERROR] La instancia previa no libero el puerto 8765 a tiempo.
exit /b 1

:resolve_conda
if defined CONDA_EXE if exist "%CONDA_EXE%" set "CONDA_CMD=%CONDA_EXE%"
if defined CONDA_CMD exit /b 0

for /f "delims=" %%I in ('where conda 2^>nul') do (
    if not defined CONDA_CMD set "CONDA_CMD=%%I"
)
if defined CONDA_CMD exit /b 0

for %%I in (
    "%UserProfile%\miniconda3\Scripts\conda.exe"
    "%UserProfile%\anaconda3\Scripts\conda.exe"
    "%ProgramData%\miniconda3\Scripts\conda.exe"
    "%ProgramData%\Anaconda3\Scripts\conda.exe"
) do (
    if not defined CONDA_CMD if exist %%~I set "CONDA_CMD=%%~I"
)

if defined CONDA_CMD exit /b 0

echo [ERROR] No encuentro conda.exe.
echo         Abre Anaconda Prompt o anade Conda al PATH y vuelve a lanzar este archivo.
exit /b 1

:is_app_ready
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { $response = Invoke-WebRequest -UseBasicParsing -Uri '%APP_URL%' -TimeoutSec 3; if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
exit /b %errorlevel%