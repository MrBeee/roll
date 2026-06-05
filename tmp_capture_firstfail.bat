@echo off
call "C:\Program Files\QGIS 3.34.13\bin\o4w_env.bat"
set "PATH=C:\Program Files\QGIS 3.34.13\apps\qgis-ltr\bin;%PATH%"
set "QGIS_PREFIX_PATH=C:/Program Files/QGIS 3.34.13/apps/qgis-ltr"
set "GDAL_FILENAME_IS_UTF8=YES"
set "VSI_CACHE=TRUE"
set "VSI_CACHE_SIZE=1000000"
set "QT_PLUGIN_PATH=C:\Program Files\QGIS 3.34.13\apps\qgis-ltr\qtplugins;C:\Program Files\QGIS 3.34.13\apps\qt5\plugins"
set "PYTHONPATH=d:\QGis\MyPlugins\roll;C:\Program Files\QGIS 3.34.13\apps\qgis-ltr\python;%PYTHONPATH%"
cd /d "d:\QGis\MyPlugins\roll"
python -m unittest -f -v discover -s test -t . -p test_*.py > firstfail.txt 2>&1
exit /b %ERRORLEVEL%
