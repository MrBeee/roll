"""
3D layout view for the Roll plugin (matplotlib backend).

OpenGL-based 3D (pyqtgraph.opengl, QOpenGLWidget) was found to deadlock
the QGIS main thread on some Windows installations regardless of the
``QT_OPENGL`` setting (software/desktop/angle all hung). Because the
hang reproduced even with a bare ``QOpenGLWidget`` that only called
``glClear``, the root cause is the Qt/QGIS GL context handshake itself
and not pyqtgraph. We therefore render the 3D Subset view with
``matplotlib``'s ``Axes3D`` on a Qt5Agg canvas, which uses a pure
software rasterizer and works on any Qt without requiring a working
GL context.

Public API:

  * ``Layout3DWidget(parent=None)`` -- the QWidget to embed.
  * ``updateFromSurvey(survey, useGlobal=False)`` -- (re)render the
        scene from a ``RollSurvey``. Draws well trajectories, the
        binning plane (if ``BinningType.plane`` is active) and the
        binning sphere (if ``BinningType.sphere`` is active). Survey
        bounding box drives the X/Y extent; deepest well drives the Z
        extent (default 3 km if there are no wells). ``useGlobal``
        selects between local survey coordinates and global
        (CRS-projected) coordinates, matching the 2D plot's
        "Projected" action.
  * ``populateDemoContent()`` -- smoke-test scene used until a survey
        is provided.
  * ``clearScene()`` -- remove every artist.

The widget falls back to a ``QLabel`` carrying a traceback if any of
the matplotlib imports fail, so a missing matplotlib install does not
break plugin load.
"""

from __future__ import annotations

import traceback

import numpy as np
from qgis.PyQt.QtCore import QPointF, Qt
from qgis.PyQt.QtGui import QColor, QVector3D
from qgis.PyQt.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from .enums_and_int_flags import SeedType
from .roll_binning import BinningType

# Default vertical extent (metres, downwards) when no wells are present.
_DEFAULT_DEPTH = 3000.0


def _resolveReflectStyle(reflectorStyle=None):
    """Return reflector outline/fill style, falling back to legacy defaults."""
    defaultFaceColor = (48.0 / 255.0, 112.0 / 255.0, 208.0 / 255.0, 0.25)
    defaultEdgeColor = (26.0 / 255.0, 64.0 / 255.0, 128.0 / 255.0, 1.0)
    defaultEdgeWidth = 1.0
    defaultEdgeStyle = '-'
    if reflectorStyle is None:
        return defaultFaceColor, defaultEdgeColor, defaultEdgeWidth, defaultEdgeStyle
    return (
        reflectorStyle.get('faceColor', defaultFaceColor),
        reflectorStyle.get('edgeColor', defaultEdgeColor),
        reflectorStyle.get('edgeWidth', defaultEdgeWidth),
        reflectorStyle.get('edgeStyle', defaultEdgeStyle),
    )


def _colorToRgba(color):
    if isinstance(color, tuple):
        return color
    qColor = QColor(color)
    if not qColor.isValid():
        qColor = QColor('#ff000000')
    return (qColor.redF(), qColor.greenF(), qColor.blueF(), qColor.alphaF())


def _pgSymbolToMplMarker(symbol):
    markerMap = {
        'o': 'o',
        's': 's',
        't': 'v',
        't1': '^',
        't2': '>',
        't3': '<',
        'd': 'D',
        '+': '+',
        'x': 'x',
        'p': 'p',
        'h': 'h',
        'star': '*',
        '|': '|',
        '_': '_',
        'arrow_up': '^',
        'arrow_right': '>',
        'arrow_down': 'v',
        'arrow_left': '<',
        'crosshair': 'x',
    }
    return markerMap.get(symbol, 'o')


class Layout3DWidget(QWidget):
    """Embeddable matplotlib-3D viewer for the Layout tab."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._figure = None
        self._canvas = None
        self._axes = None
        self._artists = []
        self._demoLoaded = False
        self._lastSurvey = None
        self._lastUseGlobal = False
        # Data-driven z extent (top = 0, bottom = deepest point). Pinned
        # so scroll-zoom does not change the depth range; only X / Y do.
        self._dataZMin = -_DEFAULT_DEPTH
        self._dataZMax = 0.0
        # Cached X / Y spans driving the box aspect ratio. Refreshed on
        # every ``updateFromSurvey`` from the global-mapped survey
        # bbox so both local and global modes show the same footprint
        # shape as the 2D Map view.
        self._aspectXSpan = 1.0
        self._aspectYSpan = 1.0
        self._rotationDragState = None

        # Lazy / guarded matplotlib import.
        try:
            import matplotlib
            matplotlib.use('Qt5Agg', force=False)
            from matplotlib.backends.backend_qt5agg import \
                FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            from mpl_toolkits.mplot3d import \
                Axes3D  # noqa: F401  (registers '3d')
        except Exception as exc:                                # pragma: no cover
            placeholder = QLabel(
                'matplotlib 3D is not available in this Python '
                f'environment.\n\n{type(exc).__name__}: {exc}\n\n'
                + traceback.format_exc()
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setWordWrap(True)
            layout.addWidget(placeholder)
            return

        # NB: NavigationToolbar2QT has been observed to deadlock when
        # constructed inside a QStackedWidget child of a QTabWidget on
        # some QGIS / matplotlib combinations. Skip it; rotation,
        # panning, and zooming work directly on the Axes3D via mouse
        # gestures (left-drag rotate, right-drag zoom, mid-drag pan).
        self._figure = Figure(figsize=(6, 5))
        # Use almost the full figure for the 3D axes -- matplotlib's
        # default leaves ~30% as outer whitespace, which makes the
        # widget look mostly empty.
        self._figure.subplots_adjust(left=0.0, right=1.0,
                                     bottom=0.0, top=1.0)
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setParent(self)

        self._axes = self._figure.add_subplot(111, projection='3d')
        # Disable mplot3d's automatic per-artist depth sorting so our
        # explicit ``zorder`` values are honoured. Without this, two
        # artists whose 3D centroids project to nearly the same depth
        # (e.g. a circle seed and a spiral seed sharing the same XY
        # centre at z = 0) get an essentially-random draw order and
        # one ends up clipping the other view-dependently.
        try:
            self._axes.computed_zorder = False
        except AttributeError:                                  # pragma: no cover
            pass
        # Pull the axes box itself out to the figure edges as well.
        self._axes.set_position([0.02, 0.02, 0.96, 0.96])
        self._configureAxes()

        layout.addWidget(self._canvas)

        # Mouse-wheel zoom. matplotlib's default 3D interaction uses
        # right-drag for zoom which is awkward; scroll-wheel feels much
        # more natural. We zoom isotropically about the data centre by
        # shrinking/expanding all three axis limits and re-applying the
        # box-aspect from the current spans.
        self._canvas.mpl_connect('scroll_event', self._onScroll)
        self._canvas.mpl_connect('button_press_event', self._onRotationPress)
        self._canvas.mpl_connect('motion_notify_event', self._onRotationMove)
        self._canvas.mpl_connect('button_release_event', self._onRotationRelease)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clearScene(self):
        """Remove every artist we previously added (keeps the axes)."""
        if self._axes is None:
            return
        for artist in self._artists:
            try:
                artist.remove()
            except (ValueError, AttributeError):
                pass
        self._artists.clear()

    def populateDemoContent(self):
        """Smoke-test scene shown until a survey has been supplied."""
        if self._axes is None:
            return
        ax = self._axes
        axisLength = 10.0
        for direction, color in (
            ((axisLength, 0, 0), '#d04040'),
            ((0, axisLength, 0), '#40b040'),
            ((0, 0, axisLength), '#5060d0'),
        ):
            line, = ax.plot(
                [0, direction[0]], [0, direction[1]], [0, direction[2]],
                color=color, linewidth=2,
            )
            self._artists.append(line)
        rng = np.random.default_rng(0)
        pts = rng.uniform(-5, 5, size=(200, 3))
        scatter = ax.scatter(
            pts[:, 0], pts[:, 1], pts[:, 2],
            s=8, c=pts[:, 2], cmap='viridis', depthshade=True,
        )
        self._artists.append(scatter)
        if self._canvas is not None:
            self._canvas.draw_idle()

    def updateFromSurvey(self, survey, useGlobal: bool = False,
                         showTemplates: bool = True,
                         showSeedPoints: bool = False,
                         dataPoints=None,
                         pointSets=None,
                         spiderData=None,
                         binArea=None,
                         blockAreas=None,
                         analysisImage=None,
                         reflectorStyle=None):
        """Render the 3D scene from a ``RollSurvey``.

        Draws (in order, only when applicable):
          * well trajectories  -- always (line)
                    * fixed grids        -- non-rolling salvo lines always;
                        individual grid points only if ``showSeedPoints`` is True
          * circle / spiral seeds -- shape always (line); individual
            sample points only if ``showSeedPoints`` is True
          * well sample points -- only if ``showSeedPoints`` is True
            (in addition to the trajectory line)
                    * visible REC / SRC / RPS / SPS point clouds -- when those
                        same layers are enabled in the 2D map and *Show source and
                        receiver points* is active
          * binning plane      -- when ``survey.binning.method`` is
                                   ``BinningType.plane``
          * binning sphere     -- when ``survey.binning.method`` is
                                   ``BinningType.sphere``

        The horizontal extent is taken from ``dataPoints`` when
        provided (e.g. imported SPS source/receiver locations) so the
        3D view matches the actual data footprint instead of the
        templates-driven ``survey.boundingRect()``, which can be
        considerably larger. Falls back to ``survey.boundingRect()``
        when no data points are available.
        ``dataPoints`` is an iterable of ``(Ex, Ny)`` numpy-array
        pairs in survey-local coordinates.
        The vertical extent runs from 0 (surface) down to either the
        deepest well point or ``-_DEFAULT_DEPTH`` (whichever is deeper).
        ``useGlobal=True`` matches the 2D "Projected" action: local
        coords are mapped through ``survey.glbTransform`` and the
        global plane / sphere objects are used.
        ``showTemplates`` mirrors the 2D *Templates* toggle. When
        false, template-owned seed geometries (wells / circles /
        spirals) are omitted from the 3D scene and from its camera
        extents.
        ``showSeedPoints`` mirrors the 2D *Show Points* / *Show
        Patterns* toggles.
        """
        self._lastSurvey = survey
        self._lastUseGlobal = bool(useGlobal)

        if self._axes is None:
            return
        self.clearScene()

        if survey is None:
            self.populateDemoContent()
            return

        # Prefer the actual imported-data footprint (SPS/RPS points)
        # over the template bbox: the latter expands well beyond the
        # data when templates roll outside the imported area.
        # Note: ``spsLiveE/N`` and ``recLiveE/N`` are stored in *global*
        # easting/northing -- the 2D plot inverts ``glbTransform`` to
        # display them in local mode. We do the same here, but per
        # *point* (not per AABB-corner) so that surveys rotated
        # relative to North don't end up with a hugely inflated local
        # bbox: the global axis-aligned hull of a rotated rectangle is
        # much larger than the rectangle itself, and inverse-mapping
        # only its four corners would carry that inflation back into
        # local space.
        dataBbox = self._dataPointsBoundingRect(dataPoints)
        localBbox = self._dataPointsLocalBoundingRect(survey, dataPoints)
        if dataBbox is not None and localBbox is not None:
            gxMin, gyMin, gxMax, gyMax = dataBbox
            lxMin, lyMin, lxMax, lyMax = localBbox
            if useGlobal:
                xMin, yMin, xMax, yMax = gxMin, gyMin, gxMax, gyMax
            else:
                xMin, yMin, xMax, yMax = lxMin, lyMin, lxMax, lyMax
        else:
            bbox = self._safeBoundingRect(survey)
            if bbox is None:
                self.populateDemoContent()
                return
            xMin, xMax = bbox.left(), bbox.right()
            yMin, yMax = bbox.top(), bbox.bottom()
            gxMin, gyMin, gxMax, gyMax = self._mapBoundingRectToGlobal(
                survey, xMin, yMin, xMax, yMax)
            if useGlobal:
                xMin, yMin, xMax, yMax = gxMin, gyMin, gxMax, gyMax
        # The box-aspect (drawing box shape) should match what the 2D
        # Map view shows, regardless of whether tick numbers are local
        # or global. The 2D view plots the rotated survey polygon, so
        # its visible footprint matches the global-mapped AABB. Use
        # those mapped dimensions for the box aspect in both modes.
        self._aspectXSpan = max(gxMax - gxMin, 1.0)
        self._aspectYSpan = max(gyMax - gyMin, 1.0)

        # Z extent driven by deepest well point (default -_DEFAULT_DEPTH).
        # Seed geometries (circles / spirals / wells) can extend beyond
        # the imported-data (SPS/RPS) footprint -- e.g. a circle seed
        # whose centre sits inside the data bbox but whose radius pokes
        # outside it. Expand xMin..yMax to include every seed XY point
        # so circles/spirals don't get clipped against the axis frame.
        seedItems = self._collectSeedGeometries(survey, useGlobal) if showTemplates else []
        zMin = -_DEFAULT_DEPTH
        for item in seedItems:
            pts = item['points']
            if pts.size:
                zMin = min(zMin, float(pts[:, 2].min()))
                xMin = min(xMin, float(pts[:, 0].min()))
                xMax = max(xMax, float(pts[:, 0].max()))
                yMin = min(yMin, float(pts[:, 1].min()))
                yMax = max(yMax, float(pts[:, 1].max()))
        # Expand the bbox to include the analysis (binning) area corners
        # so the rectangle stays inside the camera view even when it
        # extends beyond the SPS / template footprint.
        analysisCorners = self._analysisAreaCorners(survey, useGlobal, binArea)
        if analysisCorners is not None:
            ax_, ay_ = analysisCorners[:, 0], analysisCorners[:, 1]
            xMin = min(xMin, float(ax_.min()))
            xMax = max(xMax, float(ax_.max()))
            yMin = min(yMin, float(ay_.min()))
            yMax = max(yMax, float(ay_.max()))
        # Per-block CMP / Source / Receiver areas. Mirrors the 2D paint
        # path in ``RollSurvey.paint``: each block contributes three
        # rectangles (when their ``actionShow*Area`` toggles are on and
        # ``actionTemplates`` is checked). Always influence the bbox
        # when present so the camera frame contains them.
        blockAreaItems = self._blockAreaCorners(survey, useGlobal, blockAreas)
        for item in blockAreaItems:
            for corners in (item.get('cmp'), item.get('src'), item.get('rec')):
                if corners is None:
                    continue
                bx, by = corners[:, 0], corners[:, 1]
                xMin = min(xMin, float(bx.min()))
                xMax = max(xMax, float(bx.max()))
                yMin = min(yMin, float(by.min()))
                yMax = max(yMax, float(by.max()))
        zMax = 0.0

        if pointSets:
            for pointSet in pointSets:
                zs = pointSet.get('zs')
                if zs is None or getattr(zs, 'size', 0) == 0:
                    continue
                zs = np.asarray(zs, dtype=np.float64)
                if zs.size == 0:
                    continue
                zMin = min(zMin, float(np.min(zs)))
                zMax = max(zMax, float(np.max(zs)))
        zMax = max(zMax, 0.0)
        # Cache the data-driven Z range so scroll-zoom can keep the
        # depth axis pinned to the actual data extent.
        self._dataZMin = zMin
        self._dataZMax = zMax

        # Draw seed geometries (wells / circles / spirals).
        # Order matters: matplotlib 3D z-sorting is unreliable for
        # artists sharing z = 0 (circles vs. spirals), so we draw
        # spirals first, wells next, and circles last. That way a
        # circle whose footprint overlaps a dense spiral disk stays
        # fully visible (latest-drawn = on top).
        drawOrder = {'spiral': 0, 'fixedGrid': 1, 'well': 2, 'circle': 3}
        seedItems = sorted(seedItems,
                           key=lambda it: drawOrder.get(it['kind'], 3))
        ax = self._axes
        for item in seedItems:
            pts = item['points']
            color = item['color']
            alpha = item['alpha']
            kind = item['kind']
            if pts.shape[0] < 1:
                continue

            if kind == 'well':
                # Trajectory line is always drawn (dense, curved).
                if pts.shape[0] >= 2:
                    line, = ax.plot(pts[:, 0], pts[:, 1], pts[:, 2],
                                    color=color, alpha=alpha,
                                    linewidth=1.4, zorder=5)
                    line.set_clip_on(False)
                    self._artists.append(line)
                # Wellhead marker at surface (always).
                head = ax.scatter([pts[0, 0]], [pts[0, 1]], [pts[0, 2]],
                                  s=20, c=[color], alpha=alpha,
                                  depthshade=False, zorder=6)
                head.set_clip_on(False)
                self._artists.append(head)
                # Individual SPS sample points only when *Show Points*
                # / *Show Patterns* is enabled. These come from the
                # original ``pointList`` (not the dense display path).
                samplePoints = item.get('samplePoints')
                if showSeedPoints and samplePoints is not None and samplePoints.shape[0] >= 1:
                    scat = ax.scatter(samplePoints[:, 0], samplePoints[:, 1],
                                      samplePoints[:, 2], s=8, c=[color],
                                      alpha=alpha, depthshade=False)
                    self._artists.append(scat)
            elif kind == 'fixedGrid':
                segments = item.get('segments')
                if segments is not None and segments.shape[0] >= 1:
                    from mpl_toolkits.mplot3d.art3d import Line3DCollection

                    gridLines = Line3DCollection(
                        segments,
                        colors=color,
                        linewidths=1.2,
                        alpha=alpha,
                    )
                    ax.add_collection3d(gridLines)
                    self._artists.append(gridLines)
                samplePoints = item.get('samplePoints')
                if showSeedPoints and samplePoints is not None and samplePoints.shape[0] >= 1:
                    scat = ax.scatter(samplePoints[:, 0], samplePoints[:, 1],
                                      samplePoints[:, 2], s=8, c=[color],
                                      alpha=alpha, depthshade=False,
                                      zorder=4)
                    scat.set_clip_on(False)
                    self._artists.append(scat)
            else:
                # Circle / spiral shape: always drawn as a connected
                # polyline. For circles we close the loop. Circles get
                # the highest zorder so they sit on top of any spiral
                # whose disk overlaps them in XY (with computed_zorder
                # disabled, the explicit zorder is honoured).
                lineZ = 10 if kind == 'circle' else 3
                if pts.shape[0] >= 2:
                    if kind == 'circle':
                        loop = np.vstack([pts, pts[:1]])
                        xs, ys, zs = loop[:, 0], loop[:, 1], loop[:, 2]
                    else:
                        xs, ys, zs = pts[:, 0], pts[:, 1], pts[:, 2]
                    line, = ax.plot(xs, ys, zs, color=color,
                                    alpha=alpha, linewidth=1.2,
                                    zorder=lineZ)
                    # ``set_box_aspect(..., zoom=1.6)`` enlarges the
                    # drawing cube beyond the axes rectangle, so any
                    # vertex projecting outside that 2D rect gets
                    # clipped (visible as a sharp vertical/horizontal
                    # cut whose position changes with camera angle).
                    # Disable 2D clipping for seed lines so the full
                    # ring/spiral always renders.
                    line.set_clip_on(False)
                    self._artists.append(line)
                # Individual sample points only when requested.
                if showSeedPoints:
                    scat = ax.scatter(pts[:, 0], pts[:, 1], pts[:, 2],
                                      s=8, c=[color], alpha=alpha,
                                      depthshade=False,
                                      zorder=lineZ)
                    scat.set_clip_on(False)
                    self._artists.append(scat)

        # Binning plane / sphere if active.
        method = getattr(survey.binning, 'method', None)

        if method is not None:
            try:
                if method == BinningType.plane:
                    # Extend the plane *beyond* the padded axis box so
                    # matplotlib's edge clipping doesn't trim the
                    # plane's left/right borders (which would sit
                    # exactly on the axis frame otherwise).
                    pxMin, pxMax = self._padRange(xMin, xMax, frac=0.10)
                    pyMin, pyMax = self._padRange(yMin, yMax, frac=0.10)
                    self._drawBinningPlane(survey, useGlobal,
                                           pxMin, pxMax, pyMin, pyMax,
                                           reflectorStyle=reflectorStyle)
                    # Pull the bbox floor down to the plane's deepest
                    # point so the plane visually sits on the floor
                    # (avoids perspective mismatch between the plane
                    # at z = -2000 and the floor at z = -default_depth).
                    planeObj = (getattr(survey, 'globalPlane', None)
                                if useGlobal
                                else getattr(survey, 'localPlane', None))
                    if planeObj is None:
                        planeObj = getattr(survey, 'globalPlane', None)
                    if planeObj is not None:
                        for cx, cy in (
                            (pxMin, pyMin), (pxMax, pyMin),
                            (pxMax, pyMax), (pxMin, pyMax),
                        ):
                            try:
                                pz = float(planeObj.depthAt(QPointF(cx, cy)))
                            except Exception:                   # pragma: no cover  # nosec B112
                                # Best-effort plane sampling for display bounds.
                                continue
                            if np.isfinite(pz):
                                zMin = min(zMin, pz)
                elif method == BinningType.sphere:
                    self._drawBinningSphere(survey, useGlobal,
                                            reflectorStyle=reflectorStyle)
            except Exception:                                   # pragma: no cover  # nosec B110
                # Drawing failures must not break the tab.
                # Drawing failures must never break the tab.
                pass

        # Per-block CMP / Source / Receiver areas drawn just below
        # the binning area. Order matches the 2D paint path (rec, then
        # src, then cmp) and the heights stagger 0.85 / 0.90 / 0.95 so
        # the translucent fills don't fight at z = 1.0 with the
        # analysis (binning) area on top.
        if blockAreas is not None and blockAreas.get('visible', False) and blockAreaItems:
            try:
                self._drawBlockAreas(blockAreaItems, blockAreas)
                zMax = max(zMax, 0.95)
            except Exception:                                   # pragma: no cover  # nosec B110
                # Optional overlay draw.
                pass

        if pointSets:
            try:
                self._drawPointSets(survey, useGlobal, pointSets)
            except Exception:                                   # pragma: no cover  # nosec B110
                # Optional point-set draw.
                pass

        # Analysis (binning) area as a horizontal quad at z = 1 m. Drawn
        # whenever ``binArea`` is supplied and visible -- the host
        # window switches it off when "Analysis to display" is set to
        # "None". Uses the same colour / pen styling as the 2D plot.
        if analysisCorners is not None and binArea is not None and binArea.get('visible', False):
            try:
                self._drawAnalysisArea(analysisCorners, binArea)
                zMax = max(zMax, 1.0)
            except Exception:                                   # pragma: no cover  # nosec B110
                # Optional analysis quad draw.
                pass

        # Analysis surface (fold / min-offset / max-offset / rms-offset
        # / offset-gap maps) rendered as a coloured horizontal surface
        # at z = 1 m, matching the 2D "Analysis to display" selection.
        # Drawn after the analysis-area quad so its opaque pixels
        # overpaint the translucent black face fill; ``NaN`` cells
        # stay transparent and let the fill show through.
        if (analysisImage is not None
                and analysisImage.get('visible', False)
                and analysisImage.get('data') is not None):
            try:
                self._drawAnalysisImage(survey, useGlobal, analysisImage)
                zMax = max(zMax, 1.0)
            except Exception:                                   # pragma: no cover  # nosec B110
                # Optional analysis surface draw.
                pass

        # Spider overlay (red src->cmp / blue rec->cmp ray segments).
        # Driven by the 2D *Spider* toggle + ALT/Arrow navigation;
        # the host window passes its current ``spiderSrcX/Y`` etc.
        if spiderData is not None:
            self._drawSpiderOverlay(survey, useGlobal, spiderData)

        # Spider may have extended the cached Z extent -- pick those
        # up so the visible box contains the cmp ray endpoints.
        zMin = min(zMin, self._dataZMin)
        zMax = max(zMax, self._dataZMax)
        self._applyAxisLimits(xMin, xMax, yMin, yMax, zMin, zMax)

        if self._canvas is not None:
            self._canvas.draw_idle()
        self._demoLoaded = True

    def setAnimationEnabled(self, enabled: bool):
        """No-op: kept for API symmetry with the old GL implementation."""
        del enabled

    # ------------------------------------------------------------------
    # Survey-driven helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safeBoundingRect(survey):
        try:
            bbox = survey.boundingRect()
        except Exception:
            return None
        if bbox is None or bbox.isEmpty():
            return None
        return bbox

    @staticmethod
    def _dataPointsBoundingRect(dataPoints):
        """AABB ``(xMin, yMin, xMax, yMax)`` of supplied SPS arrays.

        ``dataPoints`` is an iterable of ``(xs, ys)`` numpy-array
        pairs in survey-local coordinates (e.g. ``spsLiveE/N`` and
        ``recLiveE/N`` from the main window). Returns ``None`` when no
        usable points were provided.
        """
        if not dataPoints:
            return None
        xMin = yMin = float('inf')
        xMax = yMax = float('-inf')
        for pair in dataPoints:
            if pair is None:
                continue
            try:
                xs, ys = pair
            except (TypeError, ValueError):
                continue
            if xs is None or ys is None:
                continue
            if getattr(xs, 'size', 0) == 0 or getattr(ys, 'size', 0) == 0:
                continue
            xMin = min(xMin, float(np.min(xs)))
            xMax = max(xMax, float(np.max(xs)))
            yMin = min(yMin, float(np.min(ys)))
            yMax = max(yMax, float(np.max(ys)))
        if xMin == float('inf') or xMax <= xMin or yMax <= yMin:
            return None
        return xMin, yMin, xMax, yMax

    @staticmethod
    def _dataPointsLocalBoundingRect(survey, dataPoints):
        """Tight AABB of the SPS/RPS points expressed in *local* coords.

        Inverse-transforms each input point individually through
        ``glbTransform`` (which holds the survey's local->global
        rotation+translation), then takes the AABB of the result. This
        is much tighter than inverse-mapping only the four corners of
        the global AABB when the survey is rotated relative to North.
        """
        if not dataPoints:
            return None
        transform = getattr(survey, 'glbTransform', None)
        if transform is None:
            return Layout3DWidget._dataPointsBoundingRect(dataPoints)
        try:
            inverted, ok = transform.inverted()
        except Exception:                                       # pragma: no cover
            return Layout3DWidget._dataPointsBoundingRect(dataPoints)
        if not ok:
            return Layout3DWidget._dataPointsBoundingRect(dataPoints)
        xMin = yMin = float('inf')
        xMax = yMax = float('-inf')
        for pair in dataPoints:
            if pair is None:
                continue
            try:
                xs, ys = pair
            except (TypeError, ValueError):
                continue
            if xs is None or ys is None:
                continue
            if getattr(xs, 'size', 0) == 0 or getattr(ys, 'size', 0) == 0:
                continue
            xs = np.asarray(xs, dtype=np.float64)
            ys = np.asarray(ys, dtype=np.float64)
            # QTransform.map is per-point; vectorise via the affine
            # 3x3 matrix elements (m11..m33) for speed on large SPS
            # files.
            m11, m12 = inverted.m11(), inverted.m12()
            m21, m22 = inverted.m21(), inverted.m22()
            dx, dy = inverted.dx(), inverted.dy()
            lxs = m11 * xs + m21 * ys + dx
            lys = m12 * xs + m22 * ys + dy
            xMin = min(xMin, float(lxs.min()))
            xMax = max(xMax, float(lxs.max()))
            yMin = min(yMin, float(lys.min()))
            yMax = max(yMax, float(lys.max()))
        if xMin == float('inf') or xMax <= xMin or yMax <= yMin:
            return None
        return xMin, yMin, xMax, yMax

    @staticmethod
    def _mapBoundingRectToGlobal(survey, xMin, yMin, xMax, yMax):
        """Map the four corners of the local bbox through ``glbTransform``."""
        transform = getattr(survey, 'glbTransform', None)
        if transform is None:
            return xMin, yMin, xMax, yMax
        corners = [(xMin, yMin), (xMax, yMin), (xMax, yMax), (xMin, yMax)]
        xs, ys = [], []
        for cx, cy in corners:
            mapped = transform.map(cx, cy)
            xs.append(mapped[0])
            ys.append(mapped[1])
        return min(xs), min(ys), max(xs), max(ys)

    @staticmethod
    def _mapPointsToActiveCrs(survey, useGlobal, xs, ys):
        xs = np.asarray(xs, dtype=np.float64)
        ys = np.asarray(ys, dtype=np.float64)
        if useGlobal:
            return xs, ys
        transform = getattr(survey, 'glbTransform', None)
        if transform is None:
            return xs, ys
        try:
            inverted, ok = transform.inverted()
        except Exception:                                       # pragma: no cover
            return xs, ys
        if not ok:
            return xs, ys
        m11, m12 = inverted.m11(), inverted.m12()
        m21, m22 = inverted.m21(), inverted.m22()
        dx, dy = inverted.dx(), inverted.dy()
        return m11 * xs + m21 * ys + dx, m12 * xs + m22 * ys + dy

    @staticmethod
    def _mapGlobalBboxToLocal(survey, xMin, yMin, xMax, yMax):
        """Map the four corners of a global bbox back to local coords.

        Used for the SPS/RPS data footprint, which is stored in
        easting/northing and must be inverted when the 3D view is in
        local mode (matching the 2D plot's behaviour).
        """
        transform = getattr(survey, 'glbTransform', None)
        if transform is None:
            return xMin, yMin, xMax, yMax
        try:
            inverted, ok = transform.inverted()
        except Exception:                                       # pragma: no cover
            return xMin, yMin, xMax, yMax
        if not ok:
            return xMin, yMin, xMax, yMax
        corners = [(xMin, yMin), (xMax, yMin), (xMax, yMax), (xMin, yMax)]
        xs, ys = [], []
        for cx, cy in corners:
            mapped = inverted.map(cx, cy)
            xs.append(mapped[0])
            ys.append(mapped[1])
        return min(xs), min(ys), max(xs), max(ys)

    @staticmethod
    def _iterSeeds(survey):
        for block in getattr(survey, 'blockList', []) or []:
            for template in getattr(block, 'templateList', []) or []:
                for seed in getattr(template, 'seedList', []) or []:
                    yield seed

    def _collectSeedGeometries(self, survey, useGlobal: bool):
        """Return seed geometries to draw in the 3D view.

        Each entry is ``dict(kind, points, color, alpha)`` where:
                    * ``kind``   -- ``'fixedGrid'``, ``'well'``, ``'circle'`` or ``'spiral'``
          * ``points`` -- ``(N, 3)`` numpy array of survey-local-or-global xyz
          * ``color``  -- matplotlib hex color (``'#RRGGBB'``) from ``seed.color``
          * ``alpha``  -- 0..1 from ``seed.color`` alpha channel

        Wells get ``seed.origin`` (the wellhead) prepended so the
        trajectory starts at the surface rather than at the first
        sampled along-hole depth (``ahd0``).
        """
        transform = getattr(survey, 'glbTransform', None) if useGlobal else None
        items = []
        for seed in self._iterSeeds(survey):
            seedType = getattr(seed, 'type', None)
            if seedType is None:
                continue
            if seedType == SeedType.fixedGrid:
                kind = 'fixedGrid'
            elif seedType == SeedType.well:
                kind = 'well'
            elif seedType == SeedType.circle:
                kind = 'circle'
            elif seedType == SeedType.spiral:
                kind = 'spiral'
            else:
                continue

            pts = list(getattr(seed, 'pointList', None) or [])
            segments = None
            spsPts = pts if kind == 'well' else None
            if kind == 'fixedGrid':
                grid = getattr(seed, 'grid', None)
                origin = getattr(seed, 'origin', None)
                if grid is None or origin is None:
                    continue

                pointArray = getattr(seed, 'pointArray', None)
                if pointArray is not None and pointArray.shape[0] > 0:
                    arr = np.asarray(pointArray, dtype=np.float64)
                    pts = [tuple(row) for row in arr]
                else:
                    pts = list(grid.iterPoints(origin))
                    if not pts:
                        continue

                growList = getattr(grid, 'growList', None)
                if growList and len(growList) == 3 and isinstance(origin, QVector3D):
                    segPts = []
                    steps2 = max(int(getattr(growList[2], 'steps', 0)), 0)
                    inc2 = getattr(growList[2], 'increment', QVector3D())
                    for i in range(max(int(getattr(growList[0], 'steps', 0)), 0)):
                        off0 = QVector3D(origin)
                        off0 += growList[0].increment * i
                        for j in range(max(int(getattr(growList[1], 'steps', 0)), 0)):
                            start = QVector3D(off0)
                            start += growList[1].increment * j
                            end = QVector3D(start)
                            if steps2 > 1:
                                end += inc2 * (steps2 - 1)
                            segPts.append(((start.x(), start.y(), start.z()), (end.x(), end.y(), end.z())))
                    if segPts:
                        segments = np.asarray(segPts, dtype=np.float64)
                        if transform is not None:
                            m11 = transform.m11(); m12 = transform.m12()  # noqa: E702
                            m21 = transform.m21(); m22 = transform.m22()  # noqa: E702
                            dx = transform.dx();    dy = transform.dy()   # noqa: E702
                            x = segments[:, :, 0]
                            y = segments[:, :, 1]
                            nx = m11 * x + m21 * y + dx
                            ny = m12 * x + m22 * y + dy
                            segments[:, :, 0] = nx
                            segments[:, :, 1] = ny
            if kind == 'well':
                # Prefer the dense, curvature-preserving trajectory built
                # for the 3D view. ``pointList`` only carries the few SPS
                # coverage samples (one per receiver depth) and produces
                # a visually-straight polyline even for deviated wells.
                # We keep ``spsPts`` separately so *Show Points* renders
                # those SPS samples (not the dense display points).
                well = getattr(seed, 'well', None)
                dense = getattr(well, 'pntList3D', None) if well is not None else None
                if dense:
                    # Dense well paths can carry thousands of samples,
                    # which makes mplot3d's per-vertex depth sort
                    # noticeable on every rotate/zoom. Cap the display
                    # point count: ~200 segments are visually
                    # indistinguishable from the full path for a
                    # smooth deviated well, but ~10x cheaper to
                    # re-project on every interaction. We keep the
                    # first/last samples so the trajectory still meets
                    # the wellhead and the deepest point exactly.
                    maxDisplayPts = 200
                    if len(dense) > maxDisplayPts:
                        idx = np.linspace(0, len(dense) - 1,
                                          maxDisplayPts).astype(int)
                        pts = [dense[int(i)] for i in idx]
                    else:
                        pts = list(dense)
                # Prepend wellhead origin so trajectory starts at surface.
                origin = getattr(seed, 'origin', None)
                if isinstance(origin, QVector3D):
                    if not pts or (
                        isinstance(pts[0], QVector3D)
                        and (pts[0].x(), pts[0].y(), pts[0].z())
                        != (origin.x(), origin.y(), origin.z())
                    ):
                        pts.insert(0, QVector3D(origin))
            if not pts:
                continue

            arr = self._pointsToArray(pts, transform)

            samplePoints = None
            if kind == 'well' and spsPts:
                samplePoints = self._pointsToArray(spsPts, transform)
            elif kind == 'fixedGrid':
                samplePoints = arr

            qcolor = getattr(seed, 'color', None)
            if qcolor is not None and qcolor.isValid():
                color = qcolor.name()                       # '#RRGGBB'
                alpha = float(qcolor.alphaF())
                if alpha <= 0.0:
                    alpha = 1.0                             # treat unset alpha as opaque
            else:
                color = '#202020'
                alpha = 1.0

            items.append(dict(kind=kind, points=arr,
                              segments=segments,
                              samplePoints=samplePoints,
                              color=color, alpha=alpha))
        return items

    @staticmethod
    def _pointsToArray(pts, transform):
        """Convert a list of QVector3D / indexables to an (N,3) array."""
        n = len(pts)
        arr = np.empty((n, 3), dtype=np.float64)
        if n == 0:
            return arr
        # Fast vectorised path when the input is a homogeneous list of
        # ``QVector3D`` (the common case for circles / spirals / wells).
        # ``np.fromiter`` keeps the per-point overhead in C rather than
        # going through a Python ``__getitem__`` for every coordinate.
        if isinstance(pts[0], QVector3D):
            arr[:, 0] = np.fromiter((p.x() for p in pts), dtype=np.float64, count=n)
            arr[:, 1] = np.fromiter((p.y() for p in pts), dtype=np.float64, count=n)
            arr[:, 2] = np.fromiter((p.z() for p in pts), dtype=np.float64, count=n)
        else:
            for i, p in enumerate(pts):
                arr[i] = (float(p[0]), float(p[1]), float(p[2]))
        if transform is not None:
            # Apply the affine 2D transform to all XY pairs at once.
            # ``QTransform.map`` is per-point only, but the full
            # 3x3 affine can be reconstructed from its m11/m12/m21/m22
            # /dx/dy components and applied with a single matmul.
            m11 = transform.m11(); m12 = transform.m12()  # noqa: E702
            m21 = transform.m21(); m22 = transform.m22()  # noqa: E702
            dx = transform.dx();    dy = transform.dy()   # noqa: E702
            x = arr[:, 0]; y = arr[:, 1]  # noqa: E702
            nx = m11 * x + m21 * y + dx
            ny = m12 * x + m22 * y + dy
            arr[:, 0] = nx
            arr[:, 1] = ny
        return arr

    def _analysisAreaCorners(self, survey, useGlobal, binArea):
        """Return the four 3D corners of ``survey.output.rctOutput`` as an
        ``(4, 2)`` ``np.ndarray`` of (x, y) pairs in the active coordinate
        system, or ``None`` if the rect is invalid or not present.

        The corners are returned regardless of ``binArea`` visibility so
        the bbox can include them whenever they exist (mirrors how the
        other geometry items always influence the camera box).
        """
        del binArea                                                             # consulted by caller; corners themselves are visibility-agnostic
        try:
            rect = survey.output.rctOutput
        except AttributeError:
            return None
        if rect is None or not rect.isValid():
            return None
        pts = [
            (rect.left(),  rect.top()),
            (rect.right(), rect.top()),
            (rect.right(), rect.bottom()),
            (rect.left(),  rect.bottom()),
        ]
        if useGlobal:
            glb = getattr(survey, 'glbTransform', None)
            if glb is not None:
                mapped = []
                for x, y in pts:
                    p = glb.map(QPointF(float(x), float(y)))
                    mapped.append((p.x(), p.y()))
                pts = mapped
        return np.asarray(pts, dtype=np.float64)

    def _drawAnalysisArea(self, corners, binArea):
        """Draw the binning area as a horizontal quad at z = 1 m.

        ``corners`` is the ``(4, 2)`` array returned by
        ``_analysisAreaCorners``. ``binArea`` is a dict carrying the
        face / edge styling translated from ``appSettings.binAreaColor``
        and ``appSettings.binAreaPen`` by the host window.
        """
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection

        zHeight = 1.0
        verts = [[(float(x), float(y), zHeight) for x, y in corners]]

        faceColor = binArea.get('faceColor', (0.0, 0.0, 0.0, 0.125))
        edgeColor = binArea.get('edgeColor', (0.0, 0.0, 0.0, 1.0))
        edgeWidth = float(binArea.get('edgeWidth', 2.0))
        edgeStyle = binArea.get('edgeStyle', '--')

        poly = Poly3DCollection(verts, facecolor=faceColor,
                                edgecolor=edgeColor,
                                linewidths=edgeWidth,
                                linestyles=edgeStyle)
        # Disable artist-level clipping so the rectangle's outline isn't
        # trimmed when its corners coincide with the axis-box edges.
        poly.set_clip_on(False)
        self._axes.add_collection3d(poly)
        self._artists.append(poly)

    def _drawAnalysisImage(self, survey, useGlobal, analysisImage):
        """Render the fold / offset analysis surface in 3D.

        ``analysisImage`` follows::

            {
              'visible':  True,
              'data':     <2D ndarray, shape (nx, ny)>,
              'levels':   (lo, hi),
              'colorMap': <matplotlib cmap name; falls back to viridis>,
            }

        ``data`` follows the 2D convention: axis 0 indexes local-X
        (inline), axis 1 indexes local-Y (crossline). ``NaN`` cells
        render fully transparent so the underlying analysis-area fill
        / floor remain visible (matching the 2D no-data behaviour).
        Large grids are decimated by simple striding to keep the
        ``plot_surface`` cost bounded.
        """
        data = analysisImage.get('data')
        if data is None or getattr(data, 'ndim', 0) != 2:
            return
        try:
            rect = survey.output.rctOutput
        except AttributeError:
            return
        if rect is None or not rect.isValid():
            return

        img = np.asarray(data, dtype=np.float32)
        nx, ny = img.shape
        if nx < 1 or ny < 1:
            return

        # Cap the surface mesh so very fine bin grids stay interactive
        # (matplotlib re-projects every facet on each rotate). Decimate
        # by simple striding -- the colour band is still readable.
        maxCells = 300
        sx = max(1, int(np.ceil(nx / maxCells)))
        sy = max(1, int(np.ceil(ny / maxCells)))
        if sx > 1 or sy > 1:
            img = img[::sx, ::sy]
            nx, ny = img.shape

        # Vertex grid in *local* coordinates: (nx+1, ny+1) so each
        # face spans exactly one (decimated) bin cell.
        xs = np.linspace(rect.left(), rect.right(), nx + 1)
        ys = np.linspace(rect.top(), rect.bottom(), ny + 1)
        X, Y = np.meshgrid(xs, ys, indexing='ij')
        if useGlobal:
            glb = getattr(survey, 'glbTransform', None)
            if glb is not None:
                m11 = glb.m11(); m12 = glb.m12()  # noqa: E702
                m21 = glb.m21(); m22 = glb.m22()  # noqa: E702
                tdx = glb.dx();  tdy = glb.dy()   # noqa: E702
                Xn = m11 * X + m21 * Y + tdx
                Yn = m12 * X + m22 * Y + tdy
                X, Y = Xn, Yn
        Z = np.full_like(X, 1.0)

        # Build per-face RGBA colours. ``plot_surface`` uses
        # ``facecolors`` of shape (M-1, N-1) when X/Y/Z are (M, N).
        levels = analysisImage.get('levels', (0.0, 1.0))
        try:
            lo = float(levels[0]); hi = float(levels[1])  # noqa: E702
        except (TypeError, ValueError, IndexError):
            lo, hi = 0.0, 1.0
        if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            hi = lo + 1.0
        nanMask = ~np.isfinite(img)
        norm = (img - lo) / (hi - lo)
        norm = np.clip(norm, 0.0, 1.0)
        norm[nanMask] = 0.0

        try:
            import matplotlib
            cmapName = analysisImage.get('colorMap', 'viridis') or 'viridis'
            try:
                cmap = matplotlib.colormaps.get_cmap(cmapName)
            except (ValueError, KeyError):
                cmap = matplotlib.colormaps.get_cmap('viridis')
        except Exception:                                       # pragma: no cover
            return
        colors = cmap(norm)
        # Fully transparent on no-data cells so the analysis-area fill
        # underneath shows through (matches 2D appearance).
        colors[nanMask, 3] = 0.0

        surf = self._axes.plot_surface(
            X, Y, Z,
            facecolors=colors,
            shade=False,
            linewidth=0.0,
            antialiased=False,
            rstride=1, cstride=1,
        )
        try:
            surf.set_clip_on(False)
        except AttributeError:                                  # pragma: no cover
            pass
        self._artists.append(surf)

    def _rectCornersInActiveCrs(self, rect, survey, useGlobal):
        """Convert a ``QRectF`` (survey-local) to a ``(4, 2)`` ndarray
        in the active CRS, mapping through ``glbTransform`` when
        ``useGlobal`` is True. Returns ``None`` for invalid rects.
        """
        if rect is None or not rect.isValid():
            return None
        pts = [
            (rect.left(),  rect.top()),
            (rect.right(), rect.top()),
            (rect.right(), rect.bottom()),
            (rect.left(),  rect.bottom()),
        ]
        if useGlobal:
            glb = getattr(survey, 'glbTransform', None)
            if glb is not None:
                pts = [(glb.map(QPointF(float(x), float(y))).x(),
                        glb.map(QPointF(float(x), float(y))).y())
                       for x, y in pts]
        return np.asarray(pts, dtype=np.float64)

    def _blockAreaCorners(self, survey, useGlobal, blockAreas):
        """Return a list of dicts -- one per block in ``survey.blockList``
        -- holding the cmp / src / rec rect corners as ``(4, 2)``
        ndarrays in the active CRS. Visibility-agnostic so callers can
        always extend the bbox to enclose them.

        ``blockAreas`` is consulted only to short-circuit the walk when
        the master toggle is off (i.e. ``actionTemplates`` is
        unchecked). Per-area visibility is decided at draw time.
        """
        if blockAreas is None or not blockAreas.get('visible', False):
            return []
        blockList = getattr(survey, 'blockList', None) or []
        items = []
        for block in blockList:
            cmpRect = getattr(block, 'cmpBoundingRect', None)
            srcRect = getattr(block, 'srcBoundingRect', None)
            recRect = getattr(block, 'recBoundingRect', None)
            items.append({
                'cmp': self._rectCornersInActiveCrs(cmpRect, survey, useGlobal),
                'src': self._rectCornersInActiveCrs(srcRect, survey, useGlobal),
                'rec': self._rectCornersInActiveCrs(recRect, survey, useGlobal),
            })
        return items

    def _drawBlockAreas(self, blockAreaItems, blockAreas):
        """Draw the per-block CMP / Source / Receiver rectangles as
        horizontal translucent quads. Heights stagger so the fills
        don't fight at z = 1 m where the analysis area sits.

        ``blockAreas`` carries three sub-dicts (``cmp`` / ``src`` /
        ``rec``), each with ``visible`` / ``faceColor`` / ``edgeColor``
        / ``edgeWidth`` / ``edgeStyle`` keys translated from the
        ``appSettings.{cmp,src,rec}AreaColor`` and matching pens.
        """
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection

        # Paint order matches RollSurvey.paint: rec -> src -> cmp.
        spec = (
            ('rec', 0.85),
            ('src', 0.90),
            ('cmp', 0.95),
        )
        for key, zHeight in spec:
            sub = blockAreas.get(key)
            if sub is None or not sub.get('visible', False):
                continue
            faceColor = sub.get('faceColor', (0.0, 0.0, 0.0, 0.03))
            edgeColor = sub.get('edgeColor', (0.0, 0.0, 0.0, 1.0))
            edgeWidth = float(sub.get('edgeWidth', 1.0))
            edgeStyle = sub.get('edgeStyle', '-.')
            for item in blockAreaItems:
                corners = item.get(key)
                if corners is None:
                    continue
                verts = [[(float(x), float(y), zHeight) for x, y in corners]]
                poly = Poly3DCollection(verts, facecolor=faceColor,
                                        edgecolor=edgeColor,
                                        linewidths=edgeWidth,
                                        linestyles=edgeStyle)
                poly.set_clip_on(False)
                self._axes.add_collection3d(poly)
                self._artists.append(poly)

    def _drawBinningPlane(self, survey, useGlobal, xMin, xMax, yMin, yMax, reflectorStyle=None):
        """Render the dipping plane as a translucent quad over the bbox."""
        plane = (getattr(survey, 'globalPlane', None) if useGlobal
                 else getattr(survey, 'localPlane', None))
        if plane is None:
            # Fall back to the global plane if local wasn't computed yet.
            plane = getattr(survey, 'globalPlane', None)
        if plane is None or plane.normal.z() == 0:
            return

        corners = [
            QPointF(xMin, yMin),
            QPointF(xMax, yMin),
            QPointF(xMax, yMax),
            QPointF(xMin, yMax),
        ]
        xs = np.array([c.x() for c in corners], dtype=np.float64)
        ys = np.array([c.y() for c in corners], dtype=np.float64)
        # ``RollPlane.depthAt`` already returns the plane's z-coordinate
        # in the survey's negative-down convention (e.g. an anchor at
        # z = -2000 produces -2000 for a flat plane). Use the value
        # directly — negating it would mirror the plane above surface.
        zs = np.array([plane.depthAt(c) for c in corners], dtype=np.float64)

        # plot_trisurf wants flat arrays + triangle indices.
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        verts = [list(zip(xs, ys, zs))]
        faceColor, edgeColor, edgeWidth, edgeStyle = _resolveReflectStyle(reflectorStyle)
        poly = Poly3DCollection(
            verts, alpha=0.25,
            facecolor=faceColor, edgecolor=edgeColor,
        )
        poly.set_linewidth(edgeWidth)
        poly.set_linestyle(edgeStyle)
        # Disable artist-level clipping so the plane's outline isn't
        # trimmed when its corners coincide with the axis-box edges.
        poly.set_clip_on(False)
        self._axes.add_collection3d(poly)
        self._artists.append(poly)

    def _drawBinningSphere(self, survey, useGlobal, reflectorStyle=None):
        """Render the binning sphere using the configured reflector color."""
        sphere = (getattr(survey, 'globalSphere', None) if useGlobal
                  else getattr(survey, 'localSphere', None))
        if sphere is None:
            sphere = getattr(survey, 'globalSphere', None)
        if sphere is None:
            return

        cx = sphere.origin.x()
        cy = sphere.origin.y()
        cz = sphere.origin.z()
        r = float(sphere.radius)
        if r <= 0.0:
            return

        # Modest mesh -- matplotlib's 3D rasterizer is fine here.
        nU, nV = 32, 20
        u = np.linspace(0.0, 2.0 * np.pi, nU)
        v = np.linspace(0.0, np.pi, nV)
        x = cx + r * np.outer(np.cos(u), np.sin(v))
        y = cy + r * np.outer(np.sin(u), np.sin(v))
        z = cz + r * np.outer(np.ones_like(u), np.cos(v))

        faceColor, edgeColor, edgeWidth, edgeStyle = _resolveReflectStyle(reflectorStyle)
        surf = self._axes.plot_surface(
            x, y, z,
            rstride=1, cstride=1,
            color=faceColor, edgecolor=edgeColor,
            linewidth=edgeWidth, alpha=faceColor[3],
            shade=True,
        )
        surf.set_linestyle(edgeStyle)
        self._artists.append(surf)

    def _drawSpiderOverlay(self, survey, useGlobal, spiderData):
        """Draw the 3D spider rays for one selected bin.

        ``spiderData`` is a dict with the pair-arrays produced by
        ``functions_numba.numbaSpiderBin`` /
        ``SpiderNavigationMixin._spiderLegArraysPython``:

        ``{'srcX', 'srcY', 'srcZ', 'recX', 'recY', 'recZ'}`` — each
        ``(2*fold,)`` float arrays in *survey-local* coordinates where
        index ``2k`` is the source / receiver and ``2k+1`` is the cmp
        midpoint. The ``*Z`` arrays carry the actual z-coordinates that
        were captured at binning time (src/rec real elevation, cmp z
        from the binning plane / sphere). Because the analysis table
        now always carries z, the overlay no longer needs to know which
        binning method produced the data.

        Coordinates are mapped through ``survey.glbTransform`` when
        ``useGlobal`` is True so they line up with the rest of the
        global-mode 3D scene.
        """
        if not spiderData:
            return
        srcX = spiderData.get('srcX')
        srcY = spiderData.get('srcY')
        srcZ = spiderData.get('srcZ')
        recX = spiderData.get('recX')
        recY = spiderData.get('recY')
        recZ = spiderData.get('recZ')
        if srcX is None or srcY is None or recX is None or recY is None:
            return
        if srcZ is None or recZ is None:
            return
        if srcX.size == 0 or srcX.size % 2 != 0:
            return
        if srcZ.size != srcX.size or recZ.size != recX.size:
            return

        transform = getattr(survey, 'glbTransform', None) if useGlobal else None

        def buildXYZ(xs, ys, zs):
            xs = np.asarray(xs, dtype=np.float64)
            ys = np.asarray(ys, dtype=np.float64)
            zs = np.asarray(zs, dtype=np.float64)
            if transform is not None:
                # Vectorised affine: avoid per-point QTransform.map.
                m11 = transform.m11(); m12 = transform.m12()  # noqa: E702
                m21 = transform.m21(); m22 = transform.m22()  # noqa: E702
                tdx = transform.dx();  tdy = transform.dy()   # noqa: E702
                nx = m11 * xs + m21 * ys + tdx
                ny = m12 * xs + m22 * ys + tdy
                xs, ys = nx, ny
            return xs, ys, zs

        ax = self._axes

        sx, sy, sz = buildXYZ(srcX, srcY, srcZ)
        rx, ry, rz = buildXYZ(recX, recY, recZ)
        nSeg = sx.size // 2

        # Extend the cached data Z extent so ``_applyAxisLimits`` (and
        # subsequent scroll-zoom) include the spider cmp depths --
        # otherwise the segments fall below the visible box and get
        # clipped, which makes the overlay invisible.
        cmpZmin = float(min(sz.min(), rz.min(), 0.0))
        cmpZmax = float(max(sz.max(), rz.max(), 0.0))
        if cmpZmin < self._dataZMin:
            self._dataZMin = cmpZmin
        if cmpZmax > self._dataZMax:
            self._dataZMax = cmpZmax

        # Per-segment ax.plot was previously used to avoid NaN-handling
        # quirks in Axes3D.plot, but it creates one Line3D artist per
        # ray which makes mplot3d's per-vertex depth sort scale badly
        # for high-fold bins. A single ``Line3DCollection`` per colour
        # carries hundreds of segments as one artist and is roughly an
        # order of magnitude cheaper to re-project on every interaction.
        from mpl_toolkits.mplot3d.art3d import Line3DCollection

        srcSegs = np.empty((nSeg, 2, 3), dtype=np.float64)
        recSegs = np.empty((nSeg, 2, 3), dtype=np.float64)
        srcSegs[:, 0, 0] = sx[0::2]; srcSegs[:, 0, 1] = sy[0::2]; srcSegs[:, 0, 2] = sz[0::2]  # noqa: E702
        srcSegs[:, 1, 0] = sx[1::2]; srcSegs[:, 1, 1] = sy[1::2]; srcSegs[:, 1, 2] = sz[1::2]  # noqa: E702
        recSegs[:, 0, 0] = rx[0::2]; recSegs[:, 0, 1] = ry[0::2]; recSegs[:, 0, 2] = rz[0::2]  # noqa: E702
        recSegs[:, 1, 0] = rx[1::2]; recSegs[:, 1, 1] = ry[1::2]; recSegs[:, 1, 2] = rz[1::2]  # noqa: E702

        srcCol = Line3DCollection(srcSegs, colors='red',
                                  linewidths=1.4, alpha=0.9)
        recCol = Line3DCollection(recSegs, colors='blue',
                                  linewidths=1.4, alpha=0.9)
        ax.add_collection3d(srcCol)
        ax.add_collection3d(recCol)
        self._artists.extend([srcCol, recCol])

        # Endpoint dots: src/rec at surface, cmp at depth.
        srcPts = ax.scatter(sx[0::2], sy[0::2], sz[0::2], s=14, c='red',
                            depthshade=False, alpha=0.95)
        recPts = ax.scatter(rx[0::2], ry[0::2], rz[0::2], s=14, c='blue',
                            depthshade=False, alpha=0.95)
        cmpPts = ax.scatter(sx[1::2], sy[1::2], sz[1::2], s=22,
                            facecolor='none', edgecolor='black',
                            linewidths=0.8, depthshade=False)
        self._artists.extend([srcPts, recPts, cmpPts])

    def _drawPointSets(self, survey, useGlobal, pointSets):
        ax = self._axes
        if ax is None or not pointSets:
            return

        for pointSet in pointSets:
            xs = pointSet.get('xs')
            ys = pointSet.get('ys')
            if xs is None or ys is None or getattr(xs, 'size', 0) == 0 or getattr(ys, 'size', 0) == 0:
                continue

            xs, ys = self._mapPointsToActiveCrs(survey, useGlobal, xs, ys)
            zs = pointSet.get('zs')
            if zs is None or getattr(zs, 'size', 0) != getattr(xs, 'size', 0):
                zs = np.zeros_like(xs, dtype=np.float64)
            else:
                zs = np.asarray(zs, dtype=np.float64)
            marker = _pgSymbolToMplMarker(pointSet.get('symbol', 'o'))
            faceColor = _colorToRgba(pointSet.get('faceColor', '#ff000000'))
            edgeColor = _colorToRgba(pointSet.get('edgeColor', '#ff000000'))
            size = max(float(pointSet.get('size', 1.0)), 1.0)

            scatter = ax.scatter(
                xs,
                ys,
                zs,
                s=size,
                marker=marker,
                c=[faceColor],
                edgecolors=[edgeColor],
                linewidths=0.8,
                depthshade=False,
                alpha=faceColor[3],
                zorder=7,
            )
            scatter.set_clip_on(False)
            self._artists.append(scatter)

    @staticmethod
    def _padRange(lo, hi, frac=0.05, minPad=1.0):
        """Symmetric 5%-padding helper used for axis limits and the
        binning-plane extent so they line up exactly."""
        span = hi - lo
        if span <= 0:
            return lo - minPad, hi + minPad
        margin = max(span * frac, minPad)
        return lo - margin, hi + margin

    def _applyAxisLimits(self, xMin, xMax, yMin, yMax, zMin, zMax):
        xLo, xHi = self._padRange(xMin, xMax)
        yLo, yHi = self._padRange(yMin, yMax)
        # Z is special: don't pad below ``zMin`` so the deepest
        # geometry (binning plane / sphere) sits *exactly* on the
        # bbox floor — otherwise perspective foreshortening makes the
        # plane look "shifted" relative to the floor edges. A small
        # symmetric pad is still applied so a single-depth scene
        # doesn't degenerate to a zero-height box.
        zSpan = zMax - zMin
        if zSpan <= 0:
            zLo, zHi = zMin - 1.0, zMax + 1.0
        else:
            zLo = zMin
            zHi = zMax + max(0.05 * zSpan, 1.0)
        ax = self._axes
        ax.set_xlim(xLo, xHi)
        ax.set_ylim(yLo, yHi)
        ax.set_zlim(zLo, zHi)
        self._refreshBoxAspect()

    def _refreshBoxAspect(self):
        """Re-apply ``set_box_aspect`` from the *current* axis limits.

        Driving the box aspect from the *current* xlim / ylim / zlim
        (instead of the cached survey-wide spans) makes the drawing
        isotropic: 1 m on X is the same length as 1 m on Y or Z. Rays
        therefore keep their geometric angle (e.g. a 45° reflection
        ray stays 45°) regardless of zoom level.
        """
        ax = self._axes
        if ax is None:
            return
        try:
            xLo, xHi = ax.get_xlim()
            yLo, yHi = ax.get_ylim()
            zLo, zHi = ax.get_zlim()
        except Exception:                                       # pragma: no cover
            return
        dx = max(xHi - xLo, 1.0)
        dy = max(yHi - yLo, 1.0)
        dz = max(zHi - zLo, 1.0)
        try:
            # ``zoom`` scales the drawing cube up inside the axes
            # rectangle without changing the (isotropic) aspect.
            # ~1.3 leaves a small margin while filling the available
            # widget area much better than the default (=1.0).
            ax.set_box_aspect((dx, dy, dz), zoom=1.3)
        except (TypeError, ValueError):
            try:
                ax.set_box_aspect((1, 1, 1))
            except Exception:                                   # pragma: no cover
                # Optional aspect ratio support.
                return

    def _onScroll(self, event):
        """
        Scroll-zoom only resizes the X / Y axes; the Z axis stays
        pinned to the data extent so the scene does not flatten or
        stretch above the well bottoms.
        """
        ax = self._axes
        if ax is None:
            return

        # Standard 10% per notch; scroll up = zoom in.
        scale = 0.9 if event.button == 'up' else 1.1

        xLo, xHi = ax.get_xlim()
        yLo, yHi = ax.get_ylim()
        cx = 0.5 * (xLo + xHi)
        cy = 0.5 * (yLo + yHi)
        hx = 0.5 * (xHi - xLo) * scale
        hy = 0.5 * (yHi - yLo) * scale
        ax.set_xlim(cx - hx, cx + hx)
        ax.set_ylim(cy - hy, cy + hy)

        # Keep Z pinned to the data extent.
        ax.set_zlim(self._dataZMin, self._dataZMax)
        self._refreshBoxAspect()
        if self._canvas is not None:
            self._canvas.draw_idle()

    def _onRotationPress(self, event):
        if self._axes is None or event.inaxes is not self._axes or event.button != 1:
            return
        self._rotationDragState = self._captureRotationState()

    def _onRotationMove(self, event):
        ax = self._axes
        state = self._rotationDragState
        if ax is None or state is None:
            return

        if event.inaxes not in (None, ax):
            return

        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.AltModifier:
            self._applyAltRotationLock(state)
            return

        self._rotationDragState = self._captureRotationState()

    def _onRotationRelease(self, event):
        if event.button == 1:
            self._rotationDragState = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _captureRotationState(self):
        ax = self._axes
        if ax is None:
            return None
        return dict(elev=ax.elev, roll=getattr(ax, 'roll', None))

    def _applyAltRotationLock(self, state):
        ax = self._axes
        if ax is None:
            return

        try:
            if state['roll'] is None:
                ax.view_init(elev=state['elev'], azim=ax.azim)
            else:
                ax.view_init(elev=state['elev'], azim=ax.azim, roll=state['roll'])
        except TypeError:
            ax.view_init(elev=state['elev'], azim=ax.azim)

        if self._canvas is not None:
            self._canvas.draw_idle()

    def _configureAxes(self):
        ax = self._axes
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z (depth)')
        # Cap ticks per axis and enable an offset/scientific formatter
        # so labels stay short whether we are in local (numbers like
        # 14000) or global (600000+) coordinates. Without this the
        # default 3D ScalarFormatter picks no offset for local extents
        # and the long labels collide.
        try:
            from matplotlib.ticker import MaxNLocator, ScalarFormatter
            for axis in (ax.xaxis, ax.yaxis):
                axis.set_major_locator(MaxNLocator(nbins=5, prune='both'))
                fmt = ScalarFormatter(useOffset=True)
                fmt.set_powerlimits((-3, 4))
                axis.set_major_formatter(fmt)
            ax.zaxis.set_major_locator(MaxNLocator(nbins=5))
        except Exception:                                       # pragma: no cover  # nosec B110
            # Matplotlib axis tweaks are optional.
            pass
        try:
            ax.set_box_aspect((1, 1, 0.5))
        except Exception:  # nosec B110
            # Matplotlib axis tweaks are optional.
            pass
        try:
            ax.view_init(elev=25, azim=-60)
        except Exception:  # nosec B110
            # Matplotlib camera setup is optional.
            pass

    # ------------------------------------------------------------------
    # Qt lifecycle
    # ------------------------------------------------------------------

    def showEvent(self, event):
        # Defer demo population to the first show: drawing into a
        # canvas before it has been sized produces a tiny figure.
        if not self._demoLoaded and self._axes is not None:
            try:
                self.populateDemoContent()
            except Exception:  # nosec B110
                # Demo content should never block widget startup.
                pass
            self._demoLoaded = True
        super().showEvent(event)
