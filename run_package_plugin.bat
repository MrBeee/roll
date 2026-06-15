@echo off
setlocal EnableExtensions

rem ---------------------------------------------------------------------------
rem Package the current plugin folder into a zip file using 7-Zip.
rem
rem Default output:
rem   If this script lives in ...\MyPlugins\roll, it creates ...\MyPlugins\roll.zip
rem
rem Usage:
rem   .\run_package_plugin.bat
rem   .\run_package_plugin.bat [/y] [/out path-to-zip] [/nosecurity] [/security-report path] [/?]
rem ---------------------------------------------------------------------------

set "scriptDir=%~dp0"
if "%scriptDir:~-1%"=="\" set "scriptDir=%scriptDir:~0,-1%"

for %%I in ("%scriptDir%") do set "pluginDir=%%~fI"
for %%I in ("%pluginDir%") do set "pluginName=%%~nxI"
for %%I in ("%pluginDir%\..") do set "parentDir=%%~fI"

set "sevenZipExe=C:\Program Files\7-Zip\7z.exe"
set "outputZip=%parentDir%\%pluginName%.zip"
set "forceOverwrite=0"
set "stageRoot=%TEMP%\%pluginName%_package_%RANDOM%%RANDOM%"
set "stagePluginDir=%stageRoot%\%pluginName%"
set "securityScript=%pluginDir%\run_security_checks_qgis.bat"
set "sphinxIndex=%pluginDir%\help\build\html\index.html"
set "securityReport="
set "skipSecurity=0"

if /I "%~1"=="/?" goto showHelp
if /I "%~1"=="-?" goto showHelp

:parseArgs
if "%~1"=="" goto argsDone
if /I "%~1"=="/y" goto setForceOverwrite
if /I "%~1"=="/out" goto setOutputZip
if /I "%~1"=="/nosecurity" goto setSkipSecurity
if /I "%~1"=="/security-report" goto setSecurityReport
echo Unrecognized argument: %~1
echo.
goto showHelp

:setForceOverwrite
set "forceOverwrite=1"
shift
goto parseArgs

:setOutputZip
if "%~2"=="" (
    echo Missing path after /out
    exit /b 2
)
for %%I in ("%~2") do set "outputZip=%%~fI"
shift
shift
goto parseArgs

:setSkipSecurity
set "skipSecurity=1"
shift
goto parseArgs

:setSecurityReport
if "%~2"=="" (
    echo Missing path after /security-report
    exit /b 2
)
for %%I in ("%~2") do set "securityReport=%%~fI"
shift
shift
goto parseArgs

:argsDone
if not exist "%sevenZipExe%" (
    echo 7-Zip executable was not found: "%sevenZipExe%"
    exit /b 1
)

if not "%skipSecurity%"=="1" if not exist "%securityScript%" (
    echo Security check launcher was not found: "%securityScript%"
    exit /b 1
)

if not exist "%sphinxIndex%" (
    echo Sphinx documentation output was not found: "%sphinxIndex%"
    echo Run run_sphinx_documentation.bat before packaging so the built HTML help is included.
    exit /b 1
)

if exist "%outputZip%" goto handleExistingZip
goto createStageDir

:handleExistingZip
if "%forceOverwrite%"=="1" goto deleteExistingZip
set "overwriteReply="
set /p "overwriteReply=Output file already exists. Overwrite [Y/N]? "
if /I not "%overwriteReply:~0,1%"=="Y" exit /b 3

:deleteExistingZip
del /f /q "%outputZip%" >nul 2>&1
if exist "%outputZip%" (
    echo Could not remove existing zip: "%outputZip%"
    exit /b 1
)

:createStageDir
mkdir "%stagePluginDir%" >nul 2>&1
if errorlevel 1 (
    echo Could not create staging folder: "%stagePluginDir%"
    exit /b 1
)

echo Staging plugin files from "%pluginDir%"
rem Exclude local tooling, test material, caches, reports, and packaging helpers
rem that are useful in the repo but should not be uploaded with the plugin.
robocopy "%pluginDir%" "%stagePluginDir%" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP ^
    /XD .continue .git .github __pycache__ __archive__ .vscode markdown matlab test %pluginDir%\help\source .pytest_cache .mypy_cache ^
    /XF *.bat *.pyc *.pyo *.bak *.tmp *.orig *.log *.zip *.ppt *.pptx .buildinfo .buildinfo.bak .flake8 Makefile chat.json .gitignore .pylintrc flake8-report.txt pylint-report.txt full_test_output.txt error_message.txt targeted_tests.log test_run.log test_stack_extract.txt >nul
set "robocopyExit=%ERRORLEVEL%"
if %robocopyExit% GEQ 8 goto robocopyFailed

for %%I in ("%outputZip%") do if not exist "%%~dpI" mkdir "%%~dpI" >nul 2>&1
if not defined securityReport for %%I in ("%outputZip%") do set "securityReport=%%~dpI%pluginName%-security-checks-report.txt"
if not "%skipSecurity%"=="1" (
    for %%I in ("%securityReport%") do if not exist "%%~dpI" mkdir "%%~dpI" >nul 2>&1

    echo Running security checks against staged plugin files
    call "%securityScript%" --plugin-dir "%stagePluginDir%" --report "%securityReport%"
    if errorlevel 1 goto securityChecksFailed
) else (
    echo Skipping security checks
)

echo Creating "%outputZip%"
pushd "%stageRoot%" >nul
"%sevenZipExe%" a -tzip -mx9 "%outputZip%" "%pluginName%\*" >nul
set "zipExit=%ERRORLEVEL%"
popd >nul

rd /s /q "%stageRoot%" >nul 2>&1

if not "%zipExit%"=="0" (
    echo 7-Zip failed with exit code %zipExit%.
    exit /b %zipExit%
)

echo.
echo Created plugin zip: "%outputZip%"
exit /b 0

:robocopyFailed
echo Robocopy failed with exit code %robocopyExit%.
rd /s /q "%stageRoot%" >nul 2>&1
exit /b %robocopyExit%

:securityChecksFailed
set "securityExit=%ERRORLEVEL%"
echo Security checks failed with exit code %securityExit%.
if defined securityReport echo Report saved to "%securityReport%"
rd /s /q "%stageRoot%" >nul 2>&1
exit /b %securityExit%

:showHelp
echo Package the current plugin folder into a zip file using 7-Zip.
echo.
echo Examples:
echo   .\%~nx0
echo   .\%~nx0 /y
echo   .\%~nx0 /out d:\temp\%pluginName%.zip
echo   .\%~nx0 /security-report d:\temp\%pluginName%-security.txt
echo   .\%~nx0 /nosecurity
echo   %~nx0 /y
echo.
echo Before zipping, the script runs bandit, detect-secrets, and flake8
echo against the cleaned staging folder and aborts if they report issues.
echo Use /nosecurity to skip those checks entirely.
echo Use /security-report to choose where the combined security report is written.
echo.
echo Default output:
echo   "%parentDir%\%pluginName%.zip"
echo.
echo Packaging requires built Sphinx HTML help at:
echo   "%sphinxIndex%"
echo Run run_sphinx_documentation.bat before this script.
echo.
echo Excluded by default:
echo   .git, .github, __pycache__, __archive__, .vscode, markdown, test,
echo   Python cache files, report and log files, existing zip files, and this batch file.
exit /b 0