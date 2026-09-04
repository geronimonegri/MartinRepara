@echo off
setlocal

rem Genera dist\MartinRepara.exe. Correr desde cualquier lado, doble
rem click o `build.bat` en la terminal estando en admin\.

cd /d "%~dp0"

set PY=..\venv\Scripts\python.exe

if not exist "%PY%" (
    echo No se encontro el venv en ..\venv - revisa la ruta o activa tu propio venv.
    exit /b 1
)

echo === 1/2: recolectando archivos estaticos ===
"%PY%" manage.py collectstatic --noinput
if errorlevel 1 goto :error

echo === 2/2: generando MartinRepara.exe con PyInstaller ===
"%PY%" -m PyInstaller MartinRepara.spec --noconfirm
if errorlevel 1 goto :error

echo.
echo Listo: dist\MartinRepara.exe
exit /b 0

:error
echo.
echo Fallo el build. Revisa el error de arriba.
exit /b 1
