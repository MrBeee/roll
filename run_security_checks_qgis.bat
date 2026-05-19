@echo off
rem preferred usage: ".\run_security_checks_qgis.bat --report security-checks-report.txt"
setlocal EnableExtensions

set "rollDir=%~dp0"
set "pluginDir=%rollDir:~0,-1%"
set "targetDir=%pluginDir%"
set "pyQgisBat="
set "envBat="
set "qgisRoot="
set "reportFile="

if defined QGIS_ROOT set "qgisRoot=%QGIS_ROOT%"
if defined SECURITY_CHECKS_PLUGIN_DIR set "targetDir=%SECURITY_CHECKS_PLUGIN_DIR%"
if not defined reportFile if defined SECURITY_CHECKS_REPORT_FILE set "reportFile=%SECURITY_CHECKS_REPORT_FILE%"

:parseArgs
if "%~1"=="" goto argsDone
if /I "%~1"=="/?" goto showHelp
if /I "%~1"=="-?" goto showHelp
if /I "%~1"=="--help" goto showHelp
if /I "%~1"=="--plugin-dir" goto setPluginDir
if /I "%~1"=="--report" goto setReportFile
echo Unrecognized argument: %~1
echo.
goto showHelp

:setPluginDir
if "%~2"=="" (
    echo Missing path after --plugin-dir
    exit /b 2
)
for %%I in ("%~2") do set "targetDir=%%~fI"
shift
shift
goto parseArgs

:setReportFile
if "%~2"=="" (
    echo Missing path after --report
    exit /b 2
)
set "reportFile=%~2"
shift
shift
goto parseArgs

:argsDone
if not exist "%targetDir%" (
    echo Plugin directory does not exist: "%targetDir%"
    exit /b 2
)

if defined qgisRoot (
    call :tryFindPythonQgis "%qgisRoot%\bin"
    if not defined envBat if exist "%qgisRoot%\bin\o4w_env.bat" set "envBat=%qgisRoot%\bin\o4w_env.bat"
) else (
    for /f "delims=" %%D in ('dir /b /ad "C:\Program Files\QGIS*" 2^>nul ^| sort /r') do (
        call :tryFindPythonQgis "C:\Program Files\%%~D\bin"
        if not defined envBat if exist "C:\Program Files\%%~D\bin\o4w_env.bat" set "envBat=C:\Program Files\%%~D\bin\o4w_env.bat"
        if defined pyQgisBat goto :afterQgisScan
    )
)

:afterQgisScan
if not defined pyQgisBat if defined OSGEO4W_ROOT (
    call :tryFindPythonQgis "%OSGEO4W_ROOT%\bin"
    if not defined envBat if exist "%OSGEO4W_ROOT%\bin\o4w_env.bat" set "envBat=%OSGEO4W_ROOT%\bin\o4w_env.bat"
)

if not defined pyQgisBat for %%D in ("C:\OSGeo4W" "C:\OSGeo4W64") do (
    call :tryFindPythonQgis "%%~fD\bin"
    if not defined envBat if exist "%%~fD\bin\o4w_env.bat" set "envBat=%%~fD\bin\o4w_env.bat"
)

if defined pyQgisBat goto :runWithPyQgisBat
if defined envBat goto :runWithEnv

echo Could not find python-qgis launcher or o4w_env.bat.
echo Set QGIS_ROOT or OSGEO4W_ROOT, or install QGIS with its standard launcher scripts.
exit /b 1

:runWithPyQgisBat
call :resolveQgisAppDirFromBat "%pyQgisBat%"
if defined qgisAppDir set "QGIS_PREFIX_PATH=%qgisAppDir%"
cd /d "%pluginDir%"
if defined qgisAppDir (
    set "PYTHONPATH=%pluginDir%;%qgisAppDir%\python;%qgisAppDir%\python\plugins;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%pluginDir%;%PYTHONPATH%"
)
echo Using "%pyQgisBat%"
call :runSecurityChecks "%pyQgisBat%"
set "checksExitCode=%ERRORLEVEL%"
goto :reportResult

:runWithEnv
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

if not defined qgisAppDir for /f "delims=" %%A in ('dir /b /ad "%osgeoRoot%\share" 2^>nul') do (
    if exist "%osgeoRoot%\share\%%~A\python\qgis\__init__.py" set "qgisAppDir=%osgeoRoot%\share\%%~A"
)

if not defined qgisAppDir (
    echo QGIS app dir not found under "%osgeoRoot%\apps" or "%osgeoRoot%\share".
    exit /b 1
)

set "QGIS_PREFIX_PATH=%qgisAppDir%"
set "QT_API=pyqt5"
set "PYQTGRAPH_QT_LIB=PyQt5"
set "PYTHONPATH=%pluginDir%;%qgisAppDir%\python;%qgisAppDir%\python\plugins;%PYTHONPATH%"
set "PATH=%qgisAppDir%\bin;%PATH%"

cd /d "%pluginDir%"
echo Using "%osgeoRoot%\bin\python.exe"
call :runSecurityChecks "%osgeoRoot%\bin\python.exe"
set "checksExitCode=%ERRORLEVEL%"
goto :reportResult

:runSecurityChecks
set "pythonCmd=%~1"
set "overallExitCode=0"

if defined reportFile (
    echo Writing combined output to "%reportFile%"
    > "%reportFile%" echo Security checks for "%targetDir%"
    >> "%reportFile%" echo.
)

echo.
echo Running Bandit against "%targetDir%"
if defined reportFile (
    >> "%reportFile%" echo ===== Bandit =====
    call "%pythonCmd%" -m bandit -r "%targetDir%" >> "%reportFile%" 2>&1
    >> "%reportFile%" echo.
) else (
    call "%pythonCmd%" -m bandit -r "%targetDir%"
)
set "banditExitCode=%ERRORLEVEL%"
call :updateOverallExitCode %banditExitCode%

echo.
echo Running detect-secrets against "%targetDir%"
if defined reportFile (
    >> "%reportFile%" echo ===== detect-secrets =====
    call "%pythonCmd%" -m detect_secrets scan --all-files "%targetDir%" >> "%reportFile%" 2>&1
    >> "%reportFile%" echo.
) else (
    call "%pythonCmd%" -m detect_secrets scan --all-files "%targetDir%"
)
set "detectSecretsExitCode=%ERRORLEVEL%"
call :updateOverallExitCode %detectSecretsExitCode%

echo.
echo Running Flake8 against "%targetDir%"
if defined reportFile (
    >> "%reportFile%" echo ===== Flake8 =====
    call "%pythonCmd%" -m flake8 "%targetDir%" >> "%reportFile%" 2>&1
    >> "%reportFile%" echo.
) else (
    call "%pythonCmd%" -m flake8 "%targetDir%"
)
set "flake8ExitCode=%ERRORLEVEL%"
call :updateOverallExitCode %flake8ExitCode%

echo.
call :printCheckResult "Bandit" %banditExitCode%
call :printCheckResult "detect-secrets" %detectSecretsExitCode%
call :printCheckResult "Flake8" %flake8ExitCode%
if defined reportFile echo Report saved to "%reportFile%"
exit /b %overallExitCode%

:updateOverallExitCode
if not "%~1"=="0" if "%overallExitCode%"=="0" set "overallExitCode=%~1"
goto :eof

:printCheckResult
if "%~2"=="0" (
    echo %~1 PASSED
) else (
    echo %~1 FINISHED WITH ISSUES ^(exit code %~2^)
)
goto :eof

:tryFindPythonQgis
set "candidateDir=%~1"
if exist "%candidateDir%\python-qgis.bat" if not defined pyQgisBat set "pyQgisBat=%candidateDir%\python-qgis.bat"
if exist "%candidateDir%\python-qgis-ltr.bat" if not defined pyQgisBat set "pyQgisBat=%candidateDir%\python-qgis-ltr.bat"
if exist "%candidateDir%\python-qgis-ltr-qt6.bat" if not defined pyQgisBat set "pyQgisBat=%candidateDir%\python-qgis-ltr-qt6.bat"
if exist "%candidateDir%\python-qgis-dev.bat" if not defined pyQgisBat set "pyQgisBat=%candidateDir%\python-qgis-dev.bat"
goto :eof

:resolveQgisAppDirFromBat
set "qgisAppDir="
if defined QGIS_PREFIX_PATH if exist "%QGIS_PREFIX_PATH%\python\qgis\__init__.py" set "qgisAppDir=%QGIS_PREFIX_PATH%"
if defined qgisAppDir goto :eof

for %%I in ("%~1") do set "binDir=%%~dpI"
for %%I in ("%binDir%..") do set "qgisInstallRoot=%%~fI"

for /f "delims=" %%A in ('dir /b /ad "%qgisInstallRoot%\apps" 2^>nul') do (
    if exist "%qgisInstallRoot%\apps\%%~A\python\qgis\__init__.py" set "qgisAppDir=%qgisInstallRoot%\apps\%%~A"
)

if not defined qgisAppDir for /f "delims=" %%A in ('dir /b /ad "%qgisInstallRoot%\share" 2^>nul') do (
    if exist "%qgisInstallRoot%\share\%%~A\python\qgis\__init__.py" set "qgisAppDir=%qgisInstallRoot%\share\%%~A"
)
goto :eof

:reportResult
if "%checksExitCode%"=="0" (
    echo.
    echo ALL SECURITY CHECKS PASSED
) else (
    echo.
    echo SECURITY CHECKS FINISHED WITH ISSUES ^(exit code %checksExitCode%^)
)
exit /b %checksExitCode%

:showHelp
echo Runs QGIS upload checks with a discovered QGIS Python interpreter.
echo.
echo Usage:
echo   %~nx0 [--plugin-dir path] [--report file]
echo.
echo Options:
echo   --plugin-dir path   Directory to scan. Defaults to this plugin folder.
echo   --report file       Write combined bandit, detect-secrets, and flake8 output.
echo   --help              Show this help text.
exit /b 0