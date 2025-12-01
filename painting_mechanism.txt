# Add near the top of the file
from time import perf_counter

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QImage, QPainter, QTransform


class RollSurvey(pg.GraphicsObject):
    # ... existing code ...

    def __init__(self, name: str = 'Untitled') -> None:
        super().__init__()
        # ... your existing init code ...

        # Progressive painting members
        self._fb: QImage | None = None       # framebuffer image (device-space)
        self._fbKey: tuple | None = None     # cache key for fb validity
        self._paintEpoch: int = 0            # bump this to invalidate cache externally
        self._ps: dict | None = None         # resumable paint state: {"b":..., "t":..., "i":..., "j":..., "k":...}
        self._paintBudgetMs: float = 20.0    # ~1 frame budget (~50 FPS). Tune to taste.
        self._paintStart: float = 0.0        # timer per pass

    # ---------- Public: call this when visuals changed (binning, layout, styles, etc.) ----------
    def invalidatePaintCache(self) -> None:
        """Invalidate the progressive paint buffer and state, then request a repaint."""
        self._paintEpoch += 1
        self._fb = None
        self._fbKey = None
        self._ps = None
        self.update()

    # ---------- Paint override: blit accumulated buffer, then add next chunk ----------
    def paint(self, painter: QPainter, option, widget):
        # Ensure framebuffer matches the current device/transform/LOD
        self._ensure_fb(painter, option)

        # 1) Always blit what we already drew to the screen first (fast)
        painter.save()
        try:
            # Draw in device coordinates so pixels align 1:1 with the viewport
            painter.setWorldTransform(QTransform())
            if self._fb is not None:
                painter.drawImage(0, 0, self._fb)
        finally:
            painter.restore()

        # 2) If there's more to draw, paint the next chunk into the framebuffer
        if self._ps is not None:
            self._paintStart = perf_counter()

            # Use SAME world transform and a tight clip to match your normal drawing path
            fbp = QPainter(self._fb)
            try:
                fbp.setWorldTransform(painter.worldTransform())
                fbp.setClipRect(self.viewRect())  # only paint what’s visible
                fbp.setRenderHints(painter.renderHints())

                finished = self._paint_pass_into(fbp, option)
            finally:
                fbp.end()

            # 3) If not finished, schedule another frame; else clear state
            if not finished:
                self.update()
            else:
                self._ps = None

    # ---------- Framebuffer/key management ----------
    def _make_fb_key(self, painter: QPainter, option) -> tuple:
        dev = painter.device()
        # Logical size of the paint device
        dev_w = getattr(dev, "width", lambda: 0)()
        dev_h = getattr(dev, "height", lambda: 0)()

        # Transform matrix (pan/zoom) and LOD factor
        T: QTransform = painter.worldTransform()
        m = (T.m11(), T.m12(), T.m13(),
             T.m21(), T.m22(), T.m23(),
             T.m31(), T.m32(), T.m33())
        lod = option.levelOfDetailFromTransform(T) * self.lodScale

        # Include paint flags and an epoch that you can bump when data changes
        return (
            dev_w, dev_h,
            m,
            round(lod, 3),
            int(self.paintMode),
            int(self.paintDetails),
            self._paintEpoch,
        )

    def _ensure_fb(self, painter: QPainter, option) -> None:
        key = self._make_fb_key(painter, option)
        if key != self._fbKey or self._fb is None:
            dev = painter.device()
            # Device pixel ratio for crisp output on high-DPI monitors
            try:
                dpr = dev.devicePixelRatioF()  # PyQt6
            except Exception:
                # Fallback; most devices expose devicePixelRatio()/devicePixelRatioF()
                dpr = getattr(dev, "devicePixelRatio", lambda: 1.0)()

            w_log = getattr(dev, "width", lambda: 0)()
            h_log = getattr(dev, "height", lambda: 0)()
            w_px = max(1, int(round(w_log * dpr)))
            h_px = max(1, int(round(h_log * dpr)))

            img = QImage(w_px, h_px, QImage.Format.Format_ARGB32_Premultiplied)
            img.setDevicePixelRatio(float(dpr))
            img.fill(0)  # transparent

            self._fb = img
            self._fbKey = key
            self._initPaintState()  # restart progressive drawing for new view

    # ---------- Progressive pass state/time budget ----------
    def _initPaintState(self) -> None:
        # Indices over your nested loops (blocks/templates/roll steps)
        self._ps = {"b": 0, "t": 0, "i": 0, "j": 0, "k": 0}

    def _time_budget_exceeded(self) -> bool:
        return (perf_counter() - self._paintStart) * 1000.0 > self._paintBudgetMs

    # ---------- One time-budgeted pass into the framebuffer ----------
    def _paint_pass_into(self, p: QPainter, option) -> bool:
        """
        Draw a chunk of content into self._fb using painter p.
        Resume from self._ps; return True when fully done, False to continue next frame.
        """
        if self._ps is None:
            self._initPaintState()

        vb: QRectF = self.viewRect()
        lod = option.levelOfDetailFromTransform(p.worldTransform()) * self.lodScale

        b = self._ps["b"]; t = self._ps["t"]; i = self._ps["i"]; j = self._ps["j"]; k = self._ps["k"]

        # Example: walk blocks -> templates -> roll steps (0..3 deep)
        while b < len(self.blockList):
            block = self.blockList[b]

            # Cull by view box; skip non-visible blocks
            if not block.boundingBox.intersects(vb):
                b += 1
                t = i = j = k = 0
                if self._time_budget_exceeded():
                    self._ps.update({"b": b, "t": 0, "i": 0, "j": 0, "k": 0})
                    return False
                continue

            templates = block.templateList
            while t < len(templates):
                template = templates[t]
                length = len(template.rollList) if template.rollList else 0

                # Decide how detailed to paint based on LOD/flags
                # You can keep your simplified logic in here.
                if length == 0:
                    # Draw a single instance at template.totTemplateRect
                    # (Example) outline-only at low LOD
                    if lod < 1.0 or self.paintMode == PaintMode.justTemplates:
                        r = template.totTemplateRect & self.boundingRect()  # clamp
                        if r.intersects(vb):
                            p.drawRect(r)
                    else:
                        # Call your simplified template renderer
                        # self.paintTemplate(p, vb, lod, template, QVector3D())
                        pass

                    t += 1
                    if self._time_budget_exceeded():
                        self._ps.update({"b": b, "t": t, "i": 0, "j": 0, "k": 0})
                        return False

                elif length == 1:
                    steps0 = template.rollList[0].steps
                    while i < steps0:
                        if self._time_budget_exceeded():
                            self._ps.update({"b": b, "t": t, "i": i, "j": 0, "k": 0})
                            return False

                        offset = template.rollList[0].increment * i
                        rect = template.totTemplateRect.translated(offset.toPointF())
                        if rect.intersects(vb):
                            if lod < 1.0 or self.paintMode == PaintMode.justTemplates:
                                r = rect & self.boundingRect()
                                p.drawRect(r)
                            else:
                                # self.paintTemplate(p, vb, lod, template, offset)
                                pass
                        i += 1
                    i = 0; t += 1

                elif length == 2:
                    s0 = template.rollList[0].steps
                    s1 = template.rollList[1].steps
                    while i < s0:
                        while j < s1:
                            if self._time_budget_exceeded():
                                self._ps.update({"b": b, "t": t, "i": i, "j": j, "k": 0})
                                return False
                            offset = (template.rollList[0].increment * i) + (template.rollList[1].increment * j)
                            rect = template.totTemplateRect.translated(offset.toPointF())
                            if rect.intersects(vb):
                                if lod < 1.0 or self.paintMode == PaintMode.justTemplates:
                                    r = rect & self.boundingRect()
                                    p.drawRect(r)
                                else:
                                    # self.paintTemplate(p, vb, lod, template, offset)
                                    pass
                            j += 1
                        j = 0; i += 1
                    i = 0; t += 1

                elif length == 3:
                    s0 = template.rollList[0].steps
                    s1 = template.rollList[1].steps
                    s2 = template.rollList[2].steps
                    while i < s0:
                        while j < s1:
                            while k < s2:
                                if self._time_budget_exceeded():
                                    self._ps.update({"b": b, "t": t, "i": i, "j": j, "k": k})
                                    return False
                                offset = (template.rollList[0].increment * i) + \
                                         (template.rollList[1].increment * j) + \
                                         (template.rollList[2].increment * k)
                                rect = template.totTemplateRect.translated(offset.toPointF())
                                if rect.intersects(vb):
                                    if lod < 1.0 or self.paintMode == PaintMode.justTemplates:
                                        r = rect & self.boundingRect()
                                        p.drawRect(r)
                                    else:
                                        # self.paintTemplate(p, vb, lod, template, offset)
                                        pass
                                k += 1
                            k = 0; j += 1
                        j = 0; i += 1
                    i = 0; t += 1

                else:
                    # Unsupported depth
                    t += 1
                    if self._time_budget_exceeded():
                        self._ps.update({"b": b, "t": t, "i": 0, "j": 0, "k": 0})
                        return False

            # Next block
            b += 1
            t = i = j = k = 0
            if self._time_budget_exceeded():
                self._ps.update({"b": b, "t": 0, "i": 0, "j": 0, "k": 0})
                return False

        # All done
        self._ps = {"b": b, "t": 0, "i": 0, "j": 0, "k": 0}
        return True

    # ... rest of your class ...


    def paint_progressive_incomplete_templates(self, painter, option, widget):
        """ Progressive, two-layer paint:
        - Base buffer (_fbBase): invariant layers (bin/src/rec/cmp) drawn once per view.
        - Progressive buffer (_fbProg): templates/seeds drawn incrementally over multiple passes.
        """

        # Determine the screen the viewport lives on. 'widget' is typically the QGraphicsView's viewport; get its screen
        screen = None
        try:
            wh = widget.windowHandle() if widget is not None else None
            screen = wh.screen() if wh is not None else QGuiApplication.primaryScreen()
        except Exception:
            screen = QGuiApplication.primaryScreen()

        penWidth = self.lineWidthForScreen(screen)

        # Ensure buffers for current view/transform/flags/epoch
        self._ensure_buffers(painter, option)

        # Blit base + progressive buffers in device coordinates for crisp pixels
        painter.save()
        try:
            painter.setWorldTransform(QTransform())
            if getattr(self, "_fbBase", None) is not None:
                painter.drawImage(0, 0, self._fbBase)
            if getattr(self, "_fbProg", None) is not None:
                painter.drawImage(0, 0, self._fbProg)
        finally:
            painter.restore()

        if self.paintMode == PaintMode.justBlocks:            # just paint the blocks bounding box, irrespective of LOD
            return

        # If there’s more to draw, render the next chunk into the progressive buffer
        if getattr(self, "_ps", None) is not None:
            # Reset cancel flag and use a sane time budget default
            self._cancelPaint = False
            if not hasattr(self, "_paintBudgetMs"):
                self._paintBudgetMs = 20.0  # default ~20ms per frame

            fbp = QPainter(self._fbProg)
            try:
                fbp.setWorldTransform(painter.worldTransform())
                fbp.setClipRect(self.viewRect())
                fbp.setRenderHints(painter.renderHints())
                finished = self._paint_pass_into_progressive(fbp, option, penWidth=penWidth)
            finally:
                fbp.end()

            # Schedule another frame if not finished yet
            if not finished:
                self.update()



    def paint_newly_proposed(self, painter, option, widget):
        """
        Progressive, two-layer paint:
        - Base buffer (_fbBase): invariant layers (bin/src/rec/cmp) drawn once per view.
        - Progressive buffer (_fbProg): templates/seeds drawn incrementally over multiple passes.

        This version renders one progressive pass BEFORE blitting so the frame always
        shows the latest content (no need to call plotLayout()) and schedules more
        repaints until the progressive stage is complete.
        """
        # Choose a sensible cosmetic pen width per screen (if your progressive passes use it)
        try:
            wh = widget.windowHandle() if widget is not None else None
            screen = wh.screen() if wh is not None else QGuiApplication.primaryScreen()
        except Exception:
            screen = QGuiApplication.primaryScreen()
        penWidth = self.lineWidthForScreen(screen)

        # Ensure buffers and rebuild base if the view/LOD/flags/epoch changed
        self._ensure_buffers(painter, option)

        # If the user only wants block outlines/areas, no progressive work is needed
        if self.paintMode == PaintMode.justBlocks:
            painter.save()
            try:
                painter.setWorldTransform(QTransform())  # blit in device coords
                if getattr(self, "_fbBase", None) is not None:
                    painter.drawImage(0, 0, self._fbBase)
            finally:
                painter.restore()
            return

        # 1) Do one progressive pass FIRST so the newly drawn chunk is visible in this frame
        finished = True
        if getattr(self, "_ps", None) is not None and getattr(self, "_fbProg", None) is not None:
            # time budget default
            if not hasattr(self, "_paintBudgetMs"):
                self._paintBudgetMs = 20.0
            self._cancelPaint = False

            fbp = QPainter(self._fbProg)
            try:
                # Match the on-screen transform and clip to the visible area
                fbp.setWorldTransform(painter.worldTransform())
                fbp.setClipRect(self.viewRect())
                fbp.setRenderHints(painter.renderHints())
                finished = self._paint_pass_into_progressive(fbp, option, penWidth=penWidth)
            finally:
                fbp.end()

        # 2) Blit the latest buffers now (base first, then progressive)
        painter.save()
        try:
            painter.setWorldTransform(QTransform())  # draw images in device coords
            if getattr(self, "_fbBase", None) is not None:
                painter.drawImage(0, 0, self._fbBase)
            if getattr(self, "_fbProg", None) is not None:
                painter.drawImage(0, 0, self._fbProg)
        finally:
            painter.restore()

        # 3) If progressive is not finished, schedule another frame; otherwise we’re done
        if getattr(self, "_ps", None) is not None and not finished:
            self.update()

