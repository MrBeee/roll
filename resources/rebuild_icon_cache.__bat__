@echo off

rem the windows 11 icon cache is kept here: C:\Users\%username%\AppData\Local\Microsoft\Windows\Explorer
rem you need to delete all files with a name starting with "ïconcache".
rem unfortunately, some of these files will be in use by explorer.

rem therefore it is easier to run this from a batch file. See commands below
rem upon completion the batch file will restart the PC
rem an even easier approach is shown here:
rem https://www.elevenforum.com/t/clear-and-reset-thumbnail-cache-in-windows-11.2051/

rem for logic, see: https://stackoverflow.com/questions/1794547/how-can-i-make-an-are-you-sure-prompt-in-a-windows-batch-file


setlocal EnableExtensions DisableDelayedExpansion
echo This batch file will clear the icon cache and restart your PC.
echo(
if exist "%SystemRoot%\System32\choice.exe" goto UseChoice

setlocal EnableExtensions EnableDelayedExpansion
:UseSetPrompt
set "UserChoice="
set /P "UserChoice=Are you sure [Y/N]? "
set "UserChoice=!UserChoice: =!"
if /I "!UserChoice!" == "N" endlocal & exit /B
if /I not "!UserChoice!" == "Y" goto UseSetPrompt
endlocal
goto Continue

:UseChoice
%SystemRoot%\System32\choice.exe /C YN /N /M "Are you sure [Y/N]?"
if not errorlevel 1 goto UseChoice
if errorlevel 2 exit /B

:Continue
echo Okay, let's go ...

rem taskkill /f /im explorer.exe
rem DEL /F /S /Q "%localappdata%\Packages\Microsoft.Windows.Search_cw5n1h2txyewy\localstate\AppIconCache*.*"
rem shutdown /R /F /T 00

rem approach from https://www.elevenforum.com/t/clear-and-reset-thumbnail-cache-in-windows-11.2051/
echo.
taskkill /f /im explorer.exe
timeout 2 /nobreak>nul
echo.

DEL /F /S /Q /A %LocalAppData%\Microsoft\Windows\Explorer\thumbcache_*.db

timeout 2 /nobreak>nul
start explorer.exe

echo restart the computer to fully apply changes

rem More commands can be added here.
endlocal

