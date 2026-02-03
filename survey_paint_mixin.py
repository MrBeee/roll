# survey_paint_mixin.py
from .enums_and_int_flags import PaintDetails, PaintMode


class SurveyPaintMixin:
    """Keeps the paint-mode bookkeeping out of RollMainWindow."""

    def setup_paint_actions(self) -> None:
        # call during init after self.actionShow* exist
        toggles = [
            self.actionShowCmpArea,
            self.actionShowSrcArea,
            self.actionShowSrcLines,
            self.actionShowSrcPoints,
            self.actionShowSrcPatterns,
            self.actionShowRecArea,
            self.actionShowRecLines,
            self.actionShowRecPoints,
            self.actionShowRecPatterns,
            self.actionShowBlocks,
            self.actionShowTemplates,
            self.actionShowLines,
            self.actionShowPoints,
            self.actionShowPatterns,
        ]
        for action in toggles:
            action.triggered.connect(self.updatePaintDetails)

    def updatePaintDetails(self) -> None:
        if self.survey is None:
            return

        # reset the paintMode flag
        paintMode = PaintMode.none

        # now set the right paintMode value
        if self.actionShowBlocks.isChecked():
            paintMode = PaintMode.justBlocks
        elif self.actionShowTemplates.isChecked():
            paintMode = PaintMode.justTemplates
        elif self.actionShowLines.isChecked():
            paintMode = PaintMode.justLines
        elif self.actionShowPoints.isChecked():
            paintMode = PaintMode.justPoints
        elif self.actionShowPatterns.isChecked():
            paintMode = PaintMode.all
        self.survey.paintMode = paintMode

        # reset all paintDetail flags
        details = PaintDetails.none

        # now start adding flags; start with various areas
        if self.actionShowCmpArea.isChecked():
            details |= PaintDetails.cmpArea
        if self.actionShowSrcArea.isChecked():
            details |= PaintDetails.srcArea
        if self.actionShowRecArea.isChecked():
            details |= PaintDetails.recArea

        # now add source permissions
        if self.actionShowSrcLines.isChecked():
            details |= PaintDetails.srcLin
        if self.actionShowSrcPoints.isChecked():
            details |= PaintDetails.srcPnt
        if self.actionShowSrcPatterns.isChecked():
            details |= PaintDetails.srcPat

        # now add receiver permissions
        if self.actionShowRecLines.isChecked():
            details |= PaintDetails.recLin
        if self.actionShowRecPoints.isChecked():
            details |= PaintDetails.recPnt
        if self.actionShowRecPatterns.isChecked():
            details |= PaintDetails.recPat

        self.survey.paintDetails = details
        self.survey.invalidatePaintCache()
        self.plotLayout()
