@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ---------------------------------------------------------------------------
rem Create a clean QGIS plugin zip from tracked git files using 7-Zip.
rem
rem Usage:
rem   package_plugin_zip.bat [OutputZip] [/list] [/open]
rem
rem OutputZip : optional output zip path. Defaults to <repo>\<plugin>.zip
rem /list     : list files that would be packaged, but do not create the zip
rem /open     : open Explorer and select the created zip when done
rem ---------------------------------------------------------------------------

set "scriptDir=%~dp0"
set "repoDir=%scriptDir:~0,-1%"
for %%I in ("%repoDir%") do (
    set "pluginName=%%~nxI"
    set "parentDir=%%~dpI"
)
set "parentDir=%parentDir:~0,-1%"

set "outputZip=%repoDir%\%pluginName%.zip"
set "listOnly=0"
set "openWhenDone=0"

rem Edit these lists to control what is excluded from the zip.
set "SKIP_PREFIXES=.github/ .vscode/ __archive__/ markdown/ test/"
set "SKIP_EXACT=.gitignore .pylintrc backup_copilot_chat.bat chat.json error_message.txt flake8-report.txt full_test_output.txt launch_roll_standalone.bat launch_roll_standalone.log Makefile package_plugin_zip.bat pyproject.toml pylint-report.txt Refactoring_roadmap.txt run_flake8_qgis.bat run_pylint_qgis.bat run_tests_qgis.bat targeted_tests.log test_run.log test_stack_extract.txt"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="/?" goto usage
if /I "%~1"=="-h" goto usage
if /I "%~1"=="--help" goto usage
if /I "%~1"=="/list" (
    set "listOnly=1"
    shift
    goto parse_args
)
if /I "%~1"=="--list" (
    set "listOnly=1"
    shift
    goto parse_args
)
if /I "%~1"=="/open" (
    set "openWhenDone=1"
    shift
    goto parse_args
)
if /I "%~1"=="--open" (
    set "openWhenDone=1"
    shift
    goto parse_args
)
if "%~2"=="" (
    set "outputZip=%~1"
    shift
    goto parse_args
)
echo Unrecognized argument: %~1
exit /b 2

:args_done
if not defined outputZip set "outputZip=%repoDir%\%pluginName%.zip"
if not "%outputZip:~1,1%"==":" if not "%outputZip:~0,2%"=="\\" set "outputZip=%repoDir%\%outputZip%"

call :findGit
if errorlevel 1 exit /b 1

call :find7Zip
if errorlevel 1 exit /b 1

git -C "%repoDir%" rev-parse --show-toplevel >nul 2>&1
if errorlevel 1 (
    echo "%repoDir%" is not inside a git working tree.
    exit /b 1
)

set "fileList=%TEMP%\%pluginName%_package_%RANDOM%%RANDOM%.txt"
set "fileCount=0"
set "skipCount=0"

> "%fileList%" (
    for /f "usebackq delims=" %%F in (`git -C "%repoDir%" ls-files`) do (
        call :shouldSkip "%%F"
        if errorlevel 1 (
            set "archivePath=%pluginName%\%%F"
            set "archivePath=!archivePath:/=\!"
            echo !archivePath!
            set /a fileCount+=1
        ) else (
            set /a skipCount+=1
        )
    )
)

if "%fileCount%"=="0" (
    del "%fileList%" >nul 2>&1
    echo No files matched the packaging rules.
    exit /b 1
)

echo.
echo Plugin   : %pluginName%
echo Source   : %repoDir%
echo Files    : %fileCount% included, %skipCount% skipped

if "%listOnly%"=="1" (
    echo.
    echo Files that would be packaged:
    type "%fileList%"
    del "%fileList%" >nul 2>&1
    exit /b 0
)

for %%I in ("%outputZip%") do set "outputDir=%%~dpI"
if not exist "%outputDir%" mkdir "%outputDir%"
if exist "%outputZip%" del "%outputZip%"

echo Output   : %outputZip%
echo 7-Zip    : %sevenZipExe%
echo.
echo Creating zip archive...

pushd "%parentDir%" >nul
"%sevenZipExe%" a -tzip -mx9 "%outputZip%" @"%fileList%"
set "zipExitCode=%ERRORLEVEL%"
popd >nul

del "%fileList%" >nul 2>&1

if not "%zipExitCode%"=="0" (
    echo 7-Zip failed with exit code %zipExitCode%.
    exit /b %zipExitCode%
)

echo.
echo Package created: "%outputZip%"
if "%openWhenDone%"=="1" explorer /select,"%outputZip%"
exit /b 0

:usage
echo.
echo Usage:
echo   package_plugin_zip.bat [OutputZip] [/list] [/open]
echo.
echo Examples:
echo   package_plugin_zip.bat
echo   package_plugin_zip.bat release\roll.zip
echo   package_plugin_zip.bat /list
echo   package_plugin_zip.bat release\roll.zip /open
exit /b 0

:findGit
where git >nul 2>&1
if errorlevel 1 (
    echo Git was not found on PATH.
    exit /b 1
)
exit /b 0

:find7Zip
set "sevenZipExe="
where 7z >nul 2>&1
if not errorlevel 1 for /f "usebackq delims=" %%I in (`where 7z`) do if not defined sevenZipExe set "sevenZipExe=%%I"
if defined sevenZipExe exit /b 0

if exist "%ProgramFiles%\7-Zip\7z.exe" set "sevenZipExe=%ProgramFiles%\7-Zip\7z.exe"
if defined sevenZipExe exit /b 0

if defined ProgramFiles(x86) if exist "%ProgramFiles(x86)%\7-Zip\7z.exe" set "sevenZipExe=%ProgramFiles(x86)%\7-Zip\7z.exe"
if defined sevenZipExe exit /b 0

echo 7-Zip was not found on PATH or in the default install folders.
echo Install 7-Zip or add 7z.exe to PATH.
exit /b 1

:shouldSkip
set "candidate=%~1"
set "candidate=!candidate:\=/!"

for %%P in (%SKIP_PREFIXES%) do (
    echo(!candidate!| findstr /B /I /L /C:"%%~P" >nul
    if not errorlevel 1 exit /b 0
)

for %%P in (%SKIP_EXACT%) do (
    if /I "!candidate!"=="%%~P" exit /b 0
)

exit /b 1