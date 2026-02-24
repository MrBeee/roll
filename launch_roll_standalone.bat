@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "rollDir=%~dp0"
set "pluginsDir=%rollDir%.."
set "pyQgisBat="
set "envBat="
set "qgisRoot="
set "logFile=%rollDir%launch_roll_standalone.log"

echo [INFO] Starting launcher> "%logFile%"
echo [INFO] CWD=%cd%>> "%logFile%"

if defined QGIS_ROOT set "qgisRoot=%QGIS_ROOT%"

if defined qgisRoot (
    call :tryFindPythonQgis "%qgisRoot%\bin"
    if not defined envBat if exist "%qgisRoot%\bin\o4w_env.bat" set "envBat=%qgisRoot%\bin\o4w_env.bat"
) else (
    for /f "delims=" %%D in ('dir /b /ad "C:\Program Files\QGIS*" ^| sort /r') do (
        call :tryFindPythonQgis "C:\Program Files\%%~D\bin"
        if not defined envBat if exist "C:\Program Files\%%~D\bin\o4w_env.bat" set "envBat=C:\Program Files\%%~D\bin\o4w_env.bat"
        if defined pyQgisBat goto :afterQgisScan
    )
)

:afterQgisScan
if defined pyQgisBat goto :afterOsgeoScan

if defined OSGEO4W_ROOT (
    call :tryFindPythonQgis "%OSGEO4W_ROOT%\bin"
    if not defined envBat if exist "%OSGEO4W_ROOT%\bin\o4w_env.bat" set "envBat=%OSGEO4W_ROOT%\bin\o4w_env.bat"
)

for %%D in ("C:\OSGeo4W" "C:\OSGeo4W64") do (
    call :tryFindPythonQgis "%%~fD\bin"
    if not defined envBat if exist "%%~fD\bin\o4w_env.bat" set "envBat=%%~fD\bin\o4w_env.bat"
)

:afterOsgeoScan
if defined envBat goto :runWithEnv
if defined pyQgisBat goto :runWithPyQgisBat
if defined qgisRoot goto :runWithQgisBin

echo [ERROR] Could not find o4w_env.bat or python-qgis.bat>> "%logFile%"
exit /b 1

:runWithPyQgisBat
echo [INFO] Using: "%pyQgisBat%">> "%logFile%"
set "PYTHONPATH=%pluginsDir%;%PYTHONPATH%"
cd /d "%pluginsDir%"
call "%pyQgisBat%" -m roll.standalone %*
exit /b %ERRORLEVEL%

:runWithEnv
echo [INFO] Using environment: "%envBat%">> "%logFile%"
call "%envBat%"
for %%I in ("%envBat%") do set "binDir=%%~dpI"
for %%I in ("%binDir%..") do set "osgeoRoot=%%~fI"

if exist "%osgeoRoot%\bin\qt6_env.bat" call "%osgeoRoot%\bin\qt6_env.bat"
if exist "%osgeoRoot%\bin\qt5_env.bat" call "%osgeoRoot%\bin\qt5_env.bat"
if exist "%osgeoRoot%\bin\py3_env.bat" call "%osgeoRoot%\bin\py3_env.bat"

set "qgisAppDir="

for /f "delims=" %%A in ('dir /b /ad "%osgeoRoot%\apps" 2^>nul') do (
    if exist "%osgeoRoot%\apps\%%~A\python\qgis\__init__.py" set "qgisAppDir=%osgeoRoot%\apps\%%~A"
)

if not defined qgisAppDir (
    for /f "delims=" %%A in ('dir /b /ad "%osgeoRoot%\share" 2^>nul') do (
        if exist "%osgeoRoot%\share\%%~A\python\qgis\__init__.py" set "qgisAppDir=%osgeoRoot%\share\%%~A"
    )
)

if not defined qgisAppDir (
    echo [ERROR] QGIS app dir not found under "%osgeoRoot%\apps" or "%osgeoRoot%\share">> "%logFile%"
    exit /b 1
)

set "QGIS_PREFIX_PATH=%qgisAppDir%"
set "PYTHONPATH=%pluginsDir%;%qgisAppDir%\python;%qgisAppDir%\python\plugins;%PYTHONPATH%"
set "PATH=%qgisAppDir%\bin;%PATH%"

cd /d "%pluginsDir%"

set "pyExe=%osgeoRoot%\bin\pythonw.exe"
if /i "%ROLL_DEBUG_CONSOLE%"=="1" set "pyExe=%osgeoRoot%\bin\python.exe"
echo [INFO] Using Python: "%pyExe%">> "%logFile%"

"%pyExe%" -X faulthandler -m roll.standalone %* 1>"%rollDir%roll_standalone.out.log" 2>"%rollDir%roll_standalone.err.log"
exit /b %ERRORLEVEL%

:runWithQgisBin
echo [INFO] Using qgisRoot: "%qgisRoot%">> "%logFile%"
set "PYTHONPATH=%pluginsDir%;%PYTHONPATH%"
cd /d "%pluginsDir%"

set "pyExe=%qgisRoot%\bin\python.exe"
if exist "%qgisRoot%\bin\pythonw.exe" set "pyExe=%qgisRoot%\bin\pythonw.exe"
echo [INFO] Using Python: "%pyExe%">> "%logFile%"
"%pyExe%" -m roll.standalone %*
exit /b %ERRORLEVEL%

:tryFindPythonQgis
set "candidateDir=%~1"
if exist "%candidateDir%\python-qgis.bat" if not defined pyQgisBat set "pyQgisBat=%candidateDir%\python-qgis.bat"
if exist "%candidateDir%\python-qgis-ltr.bat" if not defined pyQgisBat set "pyQgisBat=%candidateDir%\python-qgis-ltr.bat"
if exist "%candidateDir%\python-qgis-dev.bat" if not defined pyQgisBat set "pyQgisBat=%candidateDir%\python-qgis-dev.bat"
goto :eof