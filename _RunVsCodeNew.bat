@REM this batch file starts VsCode from OSGeo4W.bat via a script batch file
@REM See: https://www.tutorialspoint.com/batch_script/batch_script_quick_guide.htm 
@REM See: https://stackoverflow.com/questions/22716069/how-to-open-a-new-shell-in-cmd-then-run-script-in-a-new-shell

@REM start "C:\Program Files\QGIS 3.28.1\OSGeo4W.bat" start cmd.exe /k  _VsCodeScript
start "" "C:\Program Files\QGIS 3.28.1\OSGeo4W.bat" start cmd.exe /k  _VsCodeScriptNew
@REM start "" "C:\Users\Bart\AppData\Local\Programs\Microsoft VS Code\Code.exe"


@rem pause
exit

