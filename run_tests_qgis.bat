@echo off
setlocal EnableExtensions

set "rollDir=%~dp0"
set "pluginDir=%rollDir:~0,-1%"
set "pyQgisBat="
set "envBat="
set "qgisRoot="

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
if not defined pyQgisBat if defined OSGEO4W_ROOT (
    call :tryFindPythonQgis "%OSGEO4W_ROOT%\bin"
    if not defined envBat if exist "%OSGEO4W_ROOT%\bin\o4w_env.bat" set "envBat=%OSGEO4W_ROOT%\bin\o4w_env.bat"
)

if not defined pyQgisBat for %%D in ("C:\OSGeo4W" "C:\OSGeo4W64") do (
    call :tryFindPythonQgis "%%~fD\bin"
    if not defined envBat if exist "%%~fD\bin\o4w_env.bat" set "envBat=%%~fD\bin\o4w_env.bat"
)

if "%~1"=="" (
    set "TEST_TARGETS=test.test_roll_plugin test.test_roll_well_transform"
) else (
    set "TEST_TARGETS=%*"
)

if defined pyQgisBat goto :runWithPyQgisBat
if defined envBat goto :runWithEnv

echo Could not find python-qgis.bat or o4w_env.bat.
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
call "%pyQgisBat%" -m unittest %TEST_TARGETS%
set "testExitCode=%ERRORLEVEL%"
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
"%osgeoRoot%\bin\python.exe" -m unittest %TEST_TARGETS%
set "testExitCode=%ERRORLEVEL%"
goto :reportResult

:tryFindPythonQgis
set "candidateDir=%~1"
if exist "%candidateDir%\python-qgis.bat" if not defined pyQgisBat set "pyQgisBat=%candidateDir%\python-qgis.bat"
if exist "%candidateDir%\python-qgis-ltr.bat" if not defined pyQgisBat set "pyQgisBat=%candidateDir%\python-qgis-ltr.bat"
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
if "%testExitCode%"=="0" (
    echo.
    echo TESTS PASSED
) else (
    echo.
    echo TESTS FAILED ^(exit code %testExitCode%^)
)
exit /b %testExitCode%