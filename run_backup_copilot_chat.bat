@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ---------------------------------------------------------------------------
rem Backup VS Code Copilot chat folders for the Roll workspace.
rem
rem Usage:
rem   run_backup_copilot_chat.bat [WorkspaceId] [/open]
rem
rem WorkspaceId : optional. Restrict backup to a single workspace folder under
rem               %APPDATA%\Code\User\workspaceStorage. Omit to back up all.
rem /open       : open the timestamped backup folder in Explorer when done.
rem ---------------------------------------------------------------------------

set "SOURCE_ROOT=%APPDATA%\Code\User\workspaceStorage"
set "BACKUP_ROOT=%USERPROFILE%\Documents\CopilotChatBackups\roll"
set "WORKSPACE_ID="
set "OPEN_FOLDER=0"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="/open" (
    set "OPEN_FOLDER=1"
    shift
    goto parse_args
)
if /I "%~1"=="--open" (
    set "OPEN_FOLDER=1"
    shift
    goto parse_args
)
if "!WORKSPACE_ID!"=="" (
    set "WORKSPACE_ID=%~1"
    shift
    goto parse_args
)
echo Unrecognized argument: %~1
exit /b 2
:args_done

if not exist "%SOURCE_ROOT%\" (
    echo VS Code workspace storage root was not found: "%SOURCE_ROOT%"
    exit /b 1
)

rem ---- Build timestamp YYYY-MM-DD_HHMMSS using PowerShell (locale-safe) -----
for /f "usebackq delims=" %%T in (`powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd_HHmmss'"`) do set "TIMESTAMP=%%T"
if "%TIMESTAMP%"=="" (
    echo Failed to obtain timestamp.
    exit /b 1
)

set "DEST_ROOT=%BACKUP_ROOT%\%TIMESTAMP%"
if not exist "%DEST_ROOT%\" mkdir "%DEST_ROOT%"

set "SUMMARY_FILE=%DEST_ROOT%\backup_summary.txt"
> "%SUMMARY_FILE%" echo Backup created: %TIMESTAMP%
>>"%SUMMARY_FILE%" echo Source root: %SOURCE_ROOT%
>>"%SUMMARY_FILE%" echo Backup root: %DEST_ROOT%
>>"%SUMMARY_FILE%" echo.

set "BACKUP_COUNT=0"

if not "%WORKSPACE_ID%"=="" (
    if not exist "%SOURCE_ROOT%\%WORKSPACE_ID%\" (
        echo Workspace ID '%WORKSPACE_ID%' was not found under "%SOURCE_ROOT%".
        exit /b 1
    )
    call :backup_one "%WORKSPACE_ID%"
    goto finish
)

for /d %%W in ("%SOURCE_ROOT%\*") do (
    call :backup_one "%%~nxW"
)

:finish
echo Backed up %BACKUP_COUNT% Copilot chat workspace(s) to "%DEST_ROOT%".
echo Summary : %SUMMARY_FILE%

if "%OPEN_FOLDER%"=="1" (
    start "" "%DEST_ROOT%"
)

endlocal & exit /b 0

rem ---------------------------------------------------------------------------
:backup_one
rem %~1 = workspace id (folder name under %SOURCE_ROOT%)
set "WS_ID=%~1"
set "WS_SRC=%SOURCE_ROOT%\%WS_ID%\GitHub.copilot-chat"
if not exist "%WS_SRC%\" exit /b 0

set "WS_DEST=%DEST_ROOT%\%WS_ID%\GitHub.copilot-chat"
if not exist "%DEST_ROOT%\%WS_ID%\" mkdir "%DEST_ROOT%\%WS_ID%"

rem /E copy subdirs incl. empty, /I assume dest is dir, /Y overwrite, /Q quiet
xcopy "%WS_SRC%" "%WS_DEST%\" /E /I /Y /Q >nul
if errorlevel 1 (
    echo Failed to copy "%WS_SRC%" to "%WS_DEST%".
    exit /b 1
)

set "TRANSCRIPT_COUNT=0"
set "DEBUGLOG_COUNT=0"
if exist "%WS_SRC%\transcripts\" (
    for /f %%C in ('dir /b /a-d "%WS_SRC%\transcripts\" 2^>nul ^| find /c /v ""') do set "TRANSCRIPT_COUNT=%%C"
)
if exist "%WS_SRC%\debug-logs\" (
    for /f %%C in ('dir /b /a-d "%WS_SRC%\debug-logs\" 2^>nul ^| find /c /v ""') do set "DEBUGLOG_COUNT=%%C"
)

>>"%SUMMARY_FILE%" echo Workspace: %WS_ID%
>>"%SUMMARY_FILE%" echo   Source: %WS_SRC%
>>"%SUMMARY_FILE%" echo   Destination: %WS_DEST%
>>"%SUMMARY_FILE%" echo   Transcripts: %TRANSCRIPT_COUNT%
>>"%SUMMARY_FILE%" echo   Debug logs: %DEBUGLOG_COUNT%
>>"%SUMMARY_FILE%" echo.

set /a BACKUP_COUNT+=1
exit /b 0
