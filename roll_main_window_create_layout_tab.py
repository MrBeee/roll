import traceback

import numpy as np
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QPen
from qgis.PyQt.QtWidgets import (QAction, QActionGroup, QFrame, QGroupBox,
                                 QHBoxLayout, QLabel, QSplitter,
                                 QStackedWidget, QToolButton, QVBoxLayout,
                                 QWidget)

from . import config
from .config import toolButtonStyle
from .enums_and_int_flags import MsgType

_QT_PEN_STYLE_TO_MPL = {
    Qt.PenStyle.SolidLine: '-',
    Qt.PenStyle.DashLine: '--',
    Qt.PenStyle.DotLine: ':',
    Qt.PenStyle.DashDotLine: '-.',
    Qt.PenStyle.DashDotDotLine: (0, (3, 1, 1, 1, 1, 1)),
    Qt.PenStyle.NoPen: 'None',
}


def _qColorToRgba(color):
    """Convert a ``QColor`` (or ARGB hex string) to a normalized RGBA tuple."""
    if not isinstance(color, QColor):
        color = QColor(color)
    if not color.isValid():
        return (0.0, 0.0, 0.0, 0.125)
    return (color.redF(), color.greenF(), color.blueF(), color.alphaF())


def _qPenToMplStyle(pen):
    """Translate a ``QPen`` to (edgeColor rgba, lineWidth, mpl linestyle)."""
    edgeColor = _qColorToRgba(pen.color()) if pen is not None else (0.0, 0.0, 0.0, 1.0)
    lineWidth = float(pen.widthF()) if pen is not None else 2.0
    if lineWidth <= 0.0:
        lineWidth = 1.0
    style = _QT_PEN_STYLE_TO_MPL.get(pen.style(), '--') if pen is not None else '--'
    return edgeColor, lineWidth, style


def _buildBinAreaConfig(self):
    """Build the ``binArea`` kwarg dict for ``Layout3DWidget.updateFromSurvey``.

    Visibility mirrors the user request: the analysis area quad is
    drawn whenever the *Analysis to display* group is set to anything
    other than *None*. Colour / pen styling matches the 2D plot's
    ``appSettings.binAreaColor`` / ``appSettings.binAreaPen``.
    """
    appSettings = getattr(self, 'appSettings', None)
    if appSettings is None:
        return None
    tbNone = getattr(self, 'tbNone', None)
    visible = True if tbNone is None else not tbNone.isChecked()
    faceColor = _qColorToRgba(getattr(appSettings, 'binAreaColor', '#20000000'))
    edgeColor, edgeWidth, edgeStyle = _qPenToMplStyle(
        getattr(appSettings, 'binAreaPen', None)
    )
    return dict(
        visible=visible,
        faceColor=faceColor,
        edgeColor=edgeColor,
        edgeWidth=edgeWidth,
        edgeStyle=edgeStyle,
    )


def _buildBlockAreasConfig(self):
    """Build the ``blockAreas`` kwarg dict for the 3D widget.

    The master ``visible`` flag is gated by ``actionTemplates``: when
    templates aren't being shown in 2D, the per-block CMP / Source /
    Receiver rectangles must be hidden in 3D as well. The three
    sub-dicts mirror the ``actionShow{Cmp,Src,Rec}Area`` toggles and
    pull colour / pen styling from ``appSettings``.
    """
    appSettings = getattr(self, 'appSettings', None)
    if appSettings is None:
        return None

    actionTemplates = getattr(self, 'actionTemplates', None)
    masterVisible = True if actionTemplates is None else actionTemplates.isChecked()

    def _subDict(visibleAction, colorAttr, penAttr):
        action = getattr(self, visibleAction, None)
        visible = True if action is None else action.isChecked()
        faceColor = _qColorToRgba(getattr(appSettings, colorAttr, '#08000000'))
        edgeColor, edgeWidth, edgeStyle = _qPenToMplStyle(
            getattr(appSettings, penAttr, None)
        )
        return dict(
            visible=visible,
            faceColor=faceColor,
            edgeColor=edgeColor,
            edgeWidth=edgeWidth,
            edgeStyle=edgeStyle,
        )

    return dict(
        visible=masterVisible,
        cmp=_subDict('actionShowCmpArea', 'cmpAreaColor', 'cmpAreaPen'),
        src=_subDict('actionShowSrcArea', 'srcAreaColor', 'srcAreaPen'),
        rec=_subDict('actionShowRecArea', 'recAreaColor', 'recAreaPen'),
    )


def _buildReflectorStyleConfig(self):
    """Build the 3D reflector style dict for plane/sphere rendering."""
    appSettings = getattr(self, 'appSettings', None)
    if appSettings is None:
        return None

    faceColor = QColor(getattr(appSettings, 'reflectColor', '#403070d0'))
    if not faceColor.isValid():
        faceColor = QColor('#403070d0')

    reflectPen = getattr(appSettings, 'reflectPen', None)
    if reflectPen is None:
        edgeColor = QColor(faceColor)
        edgeColor.setAlpha(255)
        edgeColor = edgeColor.darker(180)
        edgeColor, edgeWidth, edgeStyle = _qPenToMplStyle(QPen(edgeColor, 1))
    else:
        edgeColor, edgeWidth, edgeStyle = _qPenToMplStyle(reflectPen)

    return dict(
        faceColor=_qColorToRgba(faceColor),
        edgeColor=edgeColor,
        edgeWidth=edgeWidth,
        edgeStyle=edgeStyle,
    )


def _buildVisiblePointSets(self):
    """Return visible 2D point layers to mirror into the 3D subset."""
    appSettings = getattr(self, 'appSettings', None)
    if appSettings is None:
        return [], []

    pointSets = []
    dataPoints = []
    tbAllList = getattr(self, 'tbAllList', None)
    showAllPoints = tbAllList is not None and tbAllList.isChecked()

    def _extractPointCoords(arrayAttr, xAttr, yAttr, isDead):
        array = getattr(self, arrayAttr, None)
        if array is not None and getattr(array, 'shape', (0,))[0] > 0:
            dtypeNames = getattr(getattr(array, 'dtype', None), 'names', ()) or ()

            if 'East' in dtypeNames and 'North' in dtypeNames:
                if 'InUse' in dtypeNames:
                    liveMask = array['InUse'] > 0
                else:
                    liveMask = np.ones(array.shape[0], dtype=bool)

                mask = np.logical_not(liveMask) if isDead else liveMask
                if not np.any(mask):
                    return None, None, None

                xs = np.asarray(array['East'][mask], dtype=np.float64)
                ys = np.asarray(array['North'][mask], dtype=np.float64)

                if 'Elev' in dtypeNames and 'Depth' in dtypeNames:
                    zs = np.asarray(array['Elev'][mask] - array['Depth'][mask], dtype=np.float64)
                elif 'Elev' in dtypeNames:
                    zs = np.asarray(array['Elev'][mask], dtype=np.float64)
                elif 'Depth' in dtypeNames:
                    zs = np.asarray(-array['Depth'][mask], dtype=np.float64)
                else:
                    zs = np.zeros_like(xs, dtype=np.float64)

                return xs, ys, zs

        xs = getattr(self, xAttr, None)
        ys = getattr(self, yAttr, None)
        if xs is None or ys is None or getattr(xs, 'size', 0) == 0 or getattr(ys, 'size', 0) == 0:
            return None, None, None

        xs = np.asarray(xs, dtype=np.float64)
        ys = np.asarray(ys, dtype=np.float64)
        zs = np.zeros_like(xs, dtype=np.float64)
        return xs, ys, zs

    pointSpecs = (
        ('tbSpsList', 'spsImport', 'spsLiveE', 'spsLiveN', 'spsPointSymbol', 'spsSymbolSize', 'spsBrushColor', '#000000', False),
        ('tbSpsList', 'spsImport', 'spsDeadE', 'spsDeadN', 'spsPointSymbol', 'spsSymbolSize', config.spsBrushGrey, '#000000', True),
        ('tbRpsList', 'rpsImport', 'rpsLiveE', 'rpsLiveN', 'rpsPointSymbol', 'rpsSymbolSize', 'rpsBrushColor', '#000000', False),
        ('tbRpsList', 'rpsImport', 'rpsDeadE', 'rpsDeadN', 'rpsPointSymbol', 'rpsSymbolSize', config.rpsBrushGrey, '#000000', True),
        ('tbSrcList', 'srcGeom', 'srcLiveE', 'srcLiveN', 'srcPointSymbol', 'srcSymbolSize', 'srcBrushColor', '#bdbdbd', False),
        ('tbSrcList', 'srcGeom', 'srcDeadE', 'srcDeadN', 'srcPointSymbol', 'srcSymbolSize', config.srcBrushGrey, '#bdbdbd', True),
        ('tbRecList', 'recGeom', 'recLiveE', 'recLiveN', 'recPointSymbol', 'recSymbolSize', 'recBrushColor', '#bdbdbd', False),
        ('tbRecList', 'recGeom', 'recDeadE', 'recDeadN', 'recPointSymbol', 'recSymbolSize', config.recBrushGrey, '#bdbdbd', True),
    )

    for toggleName, arrayAttr, xAttr, yAttr, symbolAttr, sizeAttr, faceColorAttr, edgeColor, isDead in pointSpecs:
        toggle = getattr(self, toggleName, None)
        if toggle is None or not toggle.isChecked():
            continue
        if isDead and not showAllPoints:
            continue

        xs, ys, zs = _extractPointCoords(arrayAttr, xAttr, yAttr, isDead)
        if xs is None or ys is None or zs is None or xs.size == 0 or ys.size == 0:
            continue

        faceColor = faceColorAttr if isinstance(faceColorAttr, str) and faceColorAttr.startswith('#') else getattr(appSettings, faceColorAttr)
        pointSets.append(
            dict(
                xs=xs,
                ys=ys,
                zs=zs,
                symbol=getattr(appSettings, symbolAttr),
                size=getattr(appSettings, sizeAttr),
                faceColor=faceColor,
                edgeColor=edgeColor,
            )
        )
        dataPoints.append((xs, ys))

    return pointSets, dataPoints


# Best-effort translation of pyqtgraph / colorcet map names to a
# matplotlib-resolvable equivalent. The 3D analysis surface uses
# ``matplotlib.cm.get_cmap`` which only knows its own registry; the
# 2D plot uses pyqtgraph + the ``CET-*`` linear maps. Anything not
# listed here falls back to ``viridis`` at draw time.
_CMAP_NAME_TO_MPL = {
    'CET-L1': 'gray',          # white -> black linear
    'CET-L2': 'gray',
    'CET-L3': 'hot',           # red heat
    'CET-L4': 'inferno',       # blue -> red
    'CET-L7': 'viridis',
    'CET-L8': 'plasma',
    'CET-L13': 'cividis',
}


def _buildAnalysisImageConfig(self):
    """Build the ``analysisImage`` kwarg dict for the 3D widget.

    Mirrors the 2D "Analysis to display" selection: when *None* is
    active (``imageType == 0``) the surface is hidden; otherwise the
    current ``layoutImg`` is rendered as a coloured horizontal
    surface at z = 1 m using the same min/max levels as the 2D plot.
    """
    imageType = getattr(self, 'imageType', 0)
    if imageType == 0:
        return dict(visible=False, data=None)
    img = getattr(self, 'layoutImg', None)
    if img is None:
        return dict(visible=False, data=None)
    layoutMax = float(getattr(self, 'layoutMax', 0.0) or 0.0)
    if layoutMax <= 0.0:
        layoutMax = 1.0
    levelLo, levelHi = 0.0, layoutMax

    # Prefer the *current* 2D colorbar levels so user-driven rescaling
    # (drag the colorbar handles to clip outliers) propagates into the
    # 3D plot. Falls back to the initial (0, layoutMax) range when the
    # bar is missing or its API returns nothing useful.
    colorBar = getattr(self, 'layoutColorBar', None)
    if colorBar is not None:
        for getter in ('levels', 'getLevels'):
            fn = getattr(colorBar, getter, None)
            if fn is None:
                continue
            try:
                got = fn()
            # Color-bar probing is best effort.
            except Exception:                                   # pragma: no cover  # nosec B112
                continue
            if got is None:
                continue
            try:
                lo, hi = float(got[0]), float(got[1])
            except (TypeError, ValueError, IndexError):
                continue
            if hi > lo:
                levelLo, levelHi = lo, hi
                break

    # Resolve the colormap name. ``_resolveLayoutAnalysisSurface``
    # is the source of truth for the 2D plot; we ask it for the same
    # name and translate to a matplotlib-known equivalent.
    cmapName = 'viridis'
    resolver = getattr(self, '_resolveLayoutAnalysisSurface', None)
    if resolver is not None:
        try:
            surface = resolver(imageType)
            cmapName = surface.get('colorMap', cmapName) or cmapName
        # Fall back to default colormap on resolver failure.
        except Exception:                                       # pragma: no cover  # nosec B110
            pass
    cmapName = _CMAP_NAME_TO_MPL.get(cmapName, cmapName)

    return dict(
        visible=True,
        data=img,
        levels=(levelLo, levelHi),
        colorMap=cmapName,
    )


def updateLayoutMethodControlsVisibility(self):
    if hasattr(self, 'layoutMethodSidePanel'):
        self.layoutMethodSidePanel.setVisible(True)
    if hasattr(self, 'layoutMethodChoice'):
        self.layoutMethodChoice.setVisible(True)
    if hasattr(self, 'layoutMethodSplitter'):
        self.layoutMethodSplitter.setSizes([100, 500])


def _ensureLayout3DWidget(self):
    """Construct the 3D widget on first use.

    Lazy-init keeps startup light while still treating the widget as a
    normal peer of the 2D map once it has been created. Any failure
    during construction is caught and replaced with a QLabel explaining
    the problem so the rest of the Layout tab keeps working.
    """
    if self.layout3DWidget is not None:
        return self.layout3DWidget
    try:
        from .layout_3D import Layout3DWidget
        widget = Layout3DWidget()
    except Exception as exc:                                # pragma: no cover
        msg = ('3D Subset view could not be initialized.\n\n'
               f'{type(exc).__name__}: {exc}\n\n' +              # noqa: W504
               traceback.format_exc())
        widget = QLabel(msg)
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.setWordWrap(True)
    self.layout3DWidget = widget
    self.layoutViewStack.addWidget(widget)
    return widget


def _teardownLayout3DWidget(self):
    """Destroy the 3D widget when callers explicitly want to reclaim it."""
    if not getattr(self, 'layout3DWidget', None):
        return
    widget = self.layout3DWidget
    self.layout3DWidget = None
    try:
        self.layoutViewStack.removeWidget(widget)
    # Widget teardown is best effort.
    except Exception:  # nosec B110
        pass
    try:
        widget.setParent(None)
        widget.deleteLater()
    # Widget teardown is best effort.
    except Exception:  # nosec B110
        pass


def _onLayoutViewModeChanged(self):
    """Switch the layout-tab right-hand pane between 2D and 3D views."""
    if not hasattr(self, 'layoutViewStack'):
        return
    if self.actionLayout3D.isChecked():
        self.layoutViewMode = '3d'
        widget = _ensureLayout3DWidget(self)
        self.layoutViewStack.setCurrentWidget(widget)
        # Refresh 3D content from the current survey, matching the 2D
        # plot's local/global coordinate convention.
        refreshLayout3DFromSurvey(self)
    else:
        self.layoutViewMode = '2d'
        self.layoutViewStack.setCurrentWidget(self.layoutWidget)


def refreshLayout3DFromSurvey(self):
    """If the 3D widget is visible, redraw it from the active survey.

    Call this after the survey changes (load / edit) or after toggling
    the "Projected" action so the 3D Subset view stays in sync with the
    2D map.
    """
    widget = getattr(self, 'layout3DWidget', None)
    if widget is None:
        return
    update = getattr(widget, 'updateFromSurvey', None)
    if update is None:
        return
    survey = getattr(self, 'survey', None)
    useGlobal = bool(getattr(self, 'glob', False))
    actionTemplates = getattr(self, 'actionTemplates', None)
    showTemplates = True if actionTemplates is None else actionTemplates.isChecked()

    # Mirror the 2D *Show Points* / *Show Patterns* toggles. When either
    # is checked we render individual seed sample points in 3D too.
    showSeedPoints = False
    for actionName in ('actionShowPoints', 'actionShowPatterns'):
        action = getattr(self, actionName, None)
        if action is not None and action.isChecked():
            showSeedPoints = True
            break

    # Mirror the currently visible 2D point layers in 3D, including the
    # same marker shape and color. The same visible sets also drive the
    # 3D footprint so the camera matches what the 2D map is showing.
    pointSets, dataPoints = _buildVisiblePointSets(self)

    # Mirror the 2D *Spider* toggle. When the spider is enabled and
    # has computed src/rec arrays, forward them so the 3D view can
    # render the same overlay (with cmp Z taken from plane / sphere).
    spiderData = None
    spiderOn = False
    spiderToggle = getattr(self, 'tbSpider', None)
    if spiderToggle is not None and spiderToggle.isChecked():
        spiderOn = True
    if spiderOn:
        srcX = getattr(self, 'spiderSrcX', None)
        srcY = getattr(self, 'spiderSrcY', None)
        srcZ = getattr(self, 'spiderSrcZ', None)
        recX = getattr(self, 'spiderRecX', None)
        recY = getattr(self, 'spiderRecY', None)
        recZ = getattr(self, 'spiderRecZ', None)
        if srcX is not None and srcY is not None \
                and recX is not None and recY is not None:
            spiderData = dict(srcX=srcX, srcY=srcY, srcZ=srcZ, recX=recX, recY=recY, recZ=recZ)

    # Log when the host has spider state but no arrays yet so the user
    # gets a hint to navigate with ALT+arrows in the 2D view first.
    if spiderOn and spiderData is None:
        log = getattr(self, 'appendLogMessage', None)
        if log is not None:
            log('Spider : Switched "on", but no spider-rays available yet '
                '(navigate with ALT+arrows or work in the 2D Map view first).', MsgType.Warning)

    binArea = _buildBinAreaConfig(self)
    blockAreas = _buildBlockAreasConfig(self)
    analysisImage = _buildAnalysisImageConfig(self)
    reflectorStyle = _buildReflectorStyleConfig(self)

    try:
        update(
            survey,
            useGlobal,
            showTemplates=showTemplates,
            showSeedPoints=showSeedPoints,
            dataPoints=dataPoints,
            pointSets=pointSets,
            spiderData=spiderData,
            binArea=binArea,
            blockAreas=blockAreas,
            analysisImage=analysisImage,
            reflectorStyle=reflectorStyle,
        )
    except TypeError:
        # Backward-compat: older widget without the kwargs.
        try:
            update(
                survey,
                useGlobal,
                showTemplates=showTemplates,
                showSeedPoints=showSeedPoints,
                dataPoints=dataPoints,
                pointSets=pointSets,
                spiderData=spiderData,
                binArea=binArea,
                blockAreas=blockAreas,
            )
        except TypeError:
            try:
                update(
                    survey,
                    useGlobal,
                    showTemplates=showTemplates,
                    showSeedPoints=showSeedPoints,
                    dataPoints=dataPoints,
                    pointSets=pointSets,
                    spiderData=spiderData,
                    binArea=binArea,
                )
            except TypeError:
                try:
                    update(
                        survey,
                        useGlobal,
                        showTemplates=showTemplates,
                        showSeedPoints=showSeedPoints,
                        dataPoints=dataPoints,
                        pointSets=pointSets,
                        spiderData=spiderData,
                    )
                except TypeError:
                    try:
                        update(
                            survey,
                            useGlobal,
                            showTemplates=showTemplates,
                            showSeedPoints=showSeedPoints,
                            pointSets=pointSets,
                            dataPoints=dataPoints,
                        )
                    except TypeError:
                        try:
                            update(survey, useGlobal, showSeedPoints=showSeedPoints)
                        except TypeError:
                            update(survey, useGlobal)
    except Exception as exc:                                    # pragma: no cover
        log = getattr(self, 'appendLogMessage', None)
        if log is not None:
            log(f'3D Subset render failed: {type(exc).__name__}: {exc}')


def _onMainTabChangedFor3D(self, index):
    """Refresh the 3D widget when the Layout tab regains focus."""
    if index != 0:
        return
    actionLayout3D = getattr(self, 'actionLayout3D', None)
    if actionLayout3D is not None and actionLayout3D.isChecked():
        refreshLayout3DFromSurvey(self)


def createLayoutTab(self):
    self.layoutWidget = self.createPlotWidget()

    # 3D widget is created lazily the first time the user picks 3D
    # Subset, then kept alive as a normal peer of the 2D map so its
    # state survives view switches and project loads.
    self.layout3DWidget = None

    # The 2D plot widget and the 3D viewer share the same splitter slot
    # via a QStackedWidget; the action group below controls which one is
    # visible. Existing code that reaches for `self.layoutWidget` keeps
    # working because the 2D widget is never re-parented.
    self.layoutViewStack = QStackedWidget()
    self.layoutViewStack.addWidget(self.layoutWidget)
    self.layoutViewStack.setCurrentWidget(self.layoutWidget)

    self.layoutMethodChoice = QGroupBox('Layout view')
    self.layoutMethodChoice.setMinimumWidth(140)
    self.layoutMethodChoice.setAlignment(Qt.AlignmentFlag.AlignHCenter)

    self.tbLayout2D = QToolButton()
    self.tbLayout3D = QToolButton()
    self.tbLayout2D.setMinimumWidth(110)
    self.tbLayout3D.setMinimumWidth(110)
    self.tbLayout2D.setStyleSheet(toolButtonStyle)
    self.tbLayout3D.setStyleSheet(toolButtonStyle)

    self.actionLayout2D = QAction('2D Map view', self)
    self.actionLayout2D.setCheckable(True)
    self.actionLayout3D = QAction('3D Subset', self)
    self.actionLayout3D.setCheckable(True)

    self.layoutMethodActionGroup = QActionGroup(self)
    self.layoutMethodActionGroup.setExclusive(True)
    self.layoutMethodActionGroup.addAction(self.actionLayout2D)
    self.layoutMethodActionGroup.addAction(self.actionLayout3D)

    # Connect both actions to the same handler so the stacked widget
    # follows whichever one becomes active.
    self.actionLayout2D.toggled.connect(lambda _checked: _onLayoutViewModeChanged(self))
    self.actionLayout3D.toggled.connect(lambda _checked: _onLayoutViewModeChanged(self))

    initialLayoutView = getattr(self, 'layoutViewMode', '2d')
    if initialLayoutView == '3d':
        self.actionLayout3D.setChecked(True)
    else:
        self.actionLayout2D.setChecked(True)

    self.tbLayout2D.setDefaultAction(self.actionLayout2D)
    self.tbLayout3D.setDefaultAction(self.actionLayout3D)

    controlsLayout = QVBoxLayout()
    controlsLayout.addWidget(self.tbLayout2D)
    controlsLayout.addWidget(self.tbLayout3D)
    self.layoutMethodChoice.setLayout(controlsLayout)

    leftLayout = QVBoxLayout()
    leftLayout.addStretch(2)
    leftLayout.addWidget(self.layoutMethodChoice)
    leftLayout.addStretch(10)

    leftWrapper = QHBoxLayout()
    leftWrapper.addStretch()
    leftWrapper.addLayout(leftLayout)
    leftWrapper.addStretch()

    self.layoutMethodSidePanel = QFrame()
    self.layoutMethodSidePanel.setFrameShape(QFrame.Shape.StyledPanel)
    self.layoutMethodSidePanel.setLayout(leftWrapper)
    self.layoutMethodSidePanel.setMaximumWidth(180)

    self.layoutMethodSplitter = QSplitter(Qt.Orientation.Horizontal)
    self.layoutMethodSplitter.addWidget(self.layoutMethodSidePanel)
    self.layoutMethodSplitter.addWidget(self.layoutViewStack)
    self.layoutMethodSplitter.setSizes([0, 1])

    self.tabLayout = QWidget()
    tabLayout = QHBoxLayout(self.tabLayout)
    tabLayout.setContentsMargins(0, 0, 0, 0)
    tabLayout.addWidget(self.layoutMethodSplitter)

    updateLayoutMethodControlsVisibility(self)
