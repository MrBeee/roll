@echo off
setlocal EnableExtensions

set "rollDir=%~dp0"
set "pluginDir=%rollDir:~0,-1%"
set "pyQgisBat="
set "envBat="
set "qgisRoot="
pushd "%rollDir%help" >nul 2>&1
if errorlevel 1 (
    echo Could not enter "%rollDir%help".
    exit /b 1
)

REM Command file for Sphinx documentation

if defined QGIS_ROOT set "qgisRoot=%QGIS_ROOT%"

set "SPHINXMODE=custom"
if "%SPHINXBUILD%" == "" set "SPHINXMODE=auto"

if /I "%SPHINXMODE%" == "auto" (
    if defined qgisRoot (
        call :tryFindPythonQgis "%qgisRoot%\bin"
        if not defined envBat if exist "%qgisRoot%\bin\o4w_env.bat" set "envBat=%qgisRoot%\bin\o4w_env.bat"
    ) else (
        for /f "delims=" %%D in ('dir /b /ad "C:\Program Files\QGIS 3*" 2^>nul ^| sort /r') do (
            call :tryFindPythonQgis "C:\Program Files\%%~D\bin"
            if not defined envBat if exist "C:\Program Files\%%~D\bin\o4w_env.bat" set "envBat=C:\Program Files\%%~D\bin\o4w_env.bat"
            if defined pyQgisBat goto :afterQgisScan
        )

        for /f "delims=" %%D in ('dir /b /ad "C:\Program Files\QGIS*" 2^>nul ^| sort /r') do (
            call :tryFindPythonQgis "C:\Program Files\%%~D\bin"
            if not defined envBat if exist "C:\Program Files\%%~D\bin\o4w_env.bat" set "envBat=C:\Program Files\%%~D\bin\o4w_env.bat"
            if defined pyQgisBat goto :afterQgisScan
        )
    )
)

:afterQgisScan
if /I "%SPHINXMODE%" == "auto" if not defined pyQgisBat if defined OSGEO4W_ROOT (
    call :tryFindPythonQgis "%OSGEO4W_ROOT%\bin"
    if not defined envBat if exist "%OSGEO4W_ROOT%\bin\o4w_env.bat" set "envBat=%OSGEO4W_ROOT%\bin\o4w_env.bat"
)

if /I "%SPHINXMODE%" == "auto" if not defined pyQgisBat for %%D in ("C:\OSGeo4W" "C:\OSGeo4W64") do (
    call :tryFindPythonQgis "%%~fD\bin"
    if not defined envBat if exist "%%~fD\bin\o4w_env.bat" set "envBat=%%~fD\bin\o4w_env.bat"
)

set "BUILDDIR=build"
set "ALLSPHINXOPTS=-d %BUILDDIR%/doctrees %SPHINXOPTS% source"
if NOT "%PAPER%" == "" (
    set "ALLSPHINXOPTS=-D latex_paper_size=%PAPER% %ALLSPHINXOPTS%"
)

set "TARGET=%~1"
if "%TARGET%" == "" set "TARGET=html"

if "%TARGET%" == "help" (
    :help
    echo.Please use run_sphinx_documentation.bat ^<target^> where ^<target^> is one of
    echo.  html       to make standalone HTML files
    echo.  dirhtml    to make HTML files named index.html in directories
    echo.  singlehtml to make a single large HTML file
    echo.  pickle     to make pickle files
    echo.  json       to make JSON files
    echo.  htmlhelp   to make HTML files and a HTML help project
    echo.  qthelp     to make HTML files and a qthelp project
    echo.  devhelp    to make HTML files and a Devhelp project
    echo.  epub       to make an epub
    echo.  latex      to make LaTeX files, you can set PAPER=a4 or PAPER=letter
    echo.  text       to make text files
    echo.  man        to make manual pages
    echo.  changes    to make an overview over all changed/added/deprecated items
    echo.  linkcheck  to check all external links for integrity
    echo.  doctest    to run all doctests embedded in the documentation if enabled
    goto end
)

if "%TARGET%" == "clean" (
    for /d %%i in (%BUILDDIR%\*) do rmdir /q /s %%i
    del /q /s %BUILDDIR%\*
    goto end
)

if /I "%SPHINXMODE%" == "custom" goto runTarget
if defined pyQgisBat goto runTarget
if defined envBat goto runTarget

where sphinx-build >nul 2>&1
if errorlevel 1 goto missingSphinx
set "SPHINXMODE=path"

:runTarget

if "%TARGET%" == "html" (
    call :runSphinx html %BUILDDIR%/html
    call :stripHtmlBuildMetadata %BUILDDIR%/html
    echo.
    echo.Build finished. The HTML pages are in help\%BUILDDIR%\html.
    goto end
)

if "%TARGET%" == "dirhtml" (
    call :runSphinx dirhtml %BUILDDIR%/dirhtml
    echo.
    echo.Build finished. The HTML pages are in help\%BUILDDIR%\dirhtml.
    goto end
)

if "%TARGET%" == "singlehtml" (
    call :runSphinx singlehtml %BUILDDIR%/singlehtml
    echo.
    echo.Build finished. The HTML pages are in help\%BUILDDIR%\singlehtml.
    goto end
)

if "%TARGET%" == "pickle" (
    call :runSphinx pickle %BUILDDIR%/pickle
    echo.
    echo.Build finished; now you can process the pickle files.
    goto end
)

if "%TARGET%" == "json" (
    call :runSphinx json %BUILDDIR%/json
    echo.
    echo.Build finished; now you can process the JSON files.
    goto end
)

if "%TARGET%" == "htmlhelp" (
    call :runSphinx htmlhelp %BUILDDIR%/htmlhelp
    echo.
    echo.Build finished; now you can run HTML Help Workshop with the ^
.hhp project file in help\%BUILDDIR%\htmlhelp.
    goto end
)

if "%TARGET%" == "qthelp" (
    call :runSphinx qthelp %BUILDDIR%/qthelp
    echo.
    echo.Build finished; now you can run "qcollectiongenerator" with the ^
.qhcp project file in help\%BUILDDIR%\qthelp, like this:
    echo.^> qcollectiongenerator help\%BUILDDIR%\qthelp\template_class.qhcp
    echo.To view the help file:
    echo.^> assistant -collectionFile help\%BUILDDIR%\qthelp\template_class.ghc
    goto end
)

if "%TARGET%" == "devhelp" (
    call :runSphinx devhelp %BUILDDIR%/devhelp
    echo.
    echo.Build finished.
    goto end
)

if "%TARGET%" == "epub" (
    call :runSphinx epub %BUILDDIR%/epub
    echo.
    echo.Build finished. The epub file is in help\%BUILDDIR%\epub.
    goto end
)

if "%TARGET%" == "latex" (
    call :runSphinx latex %BUILDDIR%/latex
    echo.
    echo.Build finished; the LaTeX files are in help\%BUILDDIR%\latex.
    goto end
)

if "%TARGET%" == "text" (
    call :runSphinx text %BUILDDIR%/text
    echo.
    echo.Build finished. The text files are in help\%BUILDDIR%\text.
    goto end
)

if "%TARGET%" == "man" (
    call :runSphinx man %BUILDDIR%/man
    echo.
    echo.Build finished. The manual pages are in help\%BUILDDIR%\man.
    goto end
)

if "%TARGET%" == "changes" (
    call :runSphinx changes %BUILDDIR%/changes
    echo.
    echo.The overview file is in help\%BUILDDIR%\changes.
    goto end
)

if "%TARGET%" == "linkcheck" (
    call :runSphinx linkcheck %BUILDDIR%/linkcheck
    echo.
    echo.Link check complete; look for any errors in the above output ^
or in help\%BUILDDIR%\linkcheck\output.txt.
    goto end
)

if "%TARGET%" == "doctest" (
    call :runSphinx doctest %BUILDDIR%/doctest
    echo.
    echo.Testing of doctests in the sources finished, look at the ^
results in help\%BUILDDIR%\doctest\output.txt.
    goto end
)

echo Unknown target: %TARGET%
set "exitCode=2"
goto finish

:runSphinx
set "builder=%~1"
set "outputDir=%~2"

if /I "%SPHINXMODE%" == "custom" (
    call %SPHINXBUILD% -b %builder% %ALLSPHINXOPTS% %outputDir%
    exit /b %ERRORLEVEL%
)

if /I "%SPHINXMODE%" == "path" (
    call sphinx-build -b %builder% %ALLSPHINXOPTS% %outputDir%
    exit /b %ERRORLEVEL%
)

if defined pyQgisBat (
    echo Using "%pyQgisBat%"
    call "%pyQgisBat%" -m sphinx -b %builder% %ALLSPHINXOPTS% %outputDir%
    exit /b %ERRORLEVEL%
)

if defined envBat (
    call "%envBat%"
    for %%I in ("%envBat%") do set "binDir=%%~dpI"
    for %%I in ("%binDir%..") do set "osgeoRoot=%%~fI"

    if exist "%osgeoRoot%\bin\qt6_env.bat" call "%osgeoRoot%\bin\qt6_env.bat"
    if exist "%osgeoRoot%\bin\qt5_env.bat" call "%osgeoRoot%\bin\qt5_env.bat"
    if exist "%osgeoRoot%\bin\py3_env.bat" call "%osgeoRoot%\bin\py3_env.bat"

    echo Using "%osgeoRoot%\bin\python.exe"
    call "%osgeoRoot%\bin\python.exe" -m sphinx -b %builder% %ALLSPHINXOPTS% %outputDir%
    exit /b %ERRORLEVEL%
)

exit /b 1

:tryFindPythonQgis
set "candidateDir=%~1"
if exist "%candidateDir%\python-qgis.bat" if not defined pyQgisBat set "pyQgisBat=%candidateDir%\python-qgis.bat"
if exist "%candidateDir%\python-qgis-ltr.bat" if not defined pyQgisBat set "pyQgisBat=%candidateDir%\python-qgis-ltr.bat"
if exist "%candidateDir%\python-qgis-ltr-qt6.bat" if not defined pyQgisBat set "pyQgisBat=%candidateDir%\python-qgis-ltr-qt6.bat"
if exist "%candidateDir%\python-qgis-dev.bat" if not defined pyQgisBat set "pyQgisBat=%candidateDir%\python-qgis-dev.bat"
goto :eof

:stripHtmlBuildMetadata
del /f /q "%~1\.buildinfo" >nul 2>&1
del /f /q "%~1\.buildinfo.bak" >nul 2>&1
goto :eof

:missingSphinx
echo.
echo.Sphinx was not found through QGIS, OSGeo4W, or PATH.
echo.Install it in the QGIS or OSGeo4W Python environment first, then rerun this script.
echo.
echo.Example in a QGIS or OSGeo4W Python shell:
echo.  python -m pip install sphinx
echo.
echo.Alternatively, set SPHINXBUILD to the full path of sphinx-build.exe.
set "exitCode=1"
goto finish

:end
set "exitCode=%ERRORLEVEL%"

:finish
popd
exit /b %exitCode%
