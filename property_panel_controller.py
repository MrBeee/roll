# coding=utf-8

import os

import pyqtgraph as pg
from qgis.PyQt.QtGui import QColor, QVector3D
from qgis.PyQt.QtWidgets import QMessageBox

from .enums_and_int_flags import SeedType, SurveyType
from .my_parameters import MySeedParameter, syncWellDirectoryForParameterTree
from .roll_main_window_create_layout_tab import refreshLayout3DFromSurvey
from .roll_survey import RollSurvey
from .roll_translate import RollTranslate


class PropertyPanelController:
    def __init__(self, window) -> None:
        self.window = window
        self._trackedSeedNames = {}
        self._trackedSeedColors = {}
        self._trackedSeedOrigins = {}
        self._trackedSeedGridGrowLists = {}
        self._trackedSeedPatterns = {}
        self._pendingSeedRenames = {}
        self._pendingSeedColors = {}
        self._pendingSeedOrigins = {}
        self._pendingSeedGridGrowLists = {}
        self._pendingSeedPatterns = {}

    def handlePropertyTreeChange(self, param, change, data) -> None:
        if change == 'value' and param.name() == 'Well file' and isinstance(data, str) and data:
            wellDirectory = os.path.dirname(data)
            if wellDirectory:
                self.window.wellDirectory = wellDirectory
                syncWellDirectoryForParameterTree(param, wellDirectory)

        if change == 'name' and isinstance(param, MySeedParameter):
            paramId = id(param)
            oldName = self._trackedSeedNames.get(paramId)
            newName = param.name()
            if oldName and oldName != newName:
                self.window.seedNameChangeDetected(param, oldName, newName)
            self._trackedSeedNames[paramId] = newName

        if change == 'value' and param.name() == 'Seed color':
            seedParam = param.parent()
            if isinstance(seedParam, MySeedParameter):
                paramId = id(seedParam)
                oldColor = self._trackedSeedColors.get(paramId)
                newColor = self._copyColor(param.value() if hasattr(param, 'value') else data)
                if oldColor is not None and self._colorKey(oldColor) != self._colorKey(newColor):
                    self.window.seedColorChangeDetected(seedParam, oldColor, newColor)
                self._trackedSeedColors[paramId] = newColor

        if change == 'value' and param.name() == 'Seed pattern':
            seedParam = param.parent()
            if isinstance(seedParam, MySeedParameter):
                paramId = id(seedParam)
                oldPattern = self._trackedSeedPatterns.get(paramId)
                newPattern = param.value() if hasattr(param, 'value') else data
                if oldPattern is not None and oldPattern != newPattern:
                    self.window.seedPatternChangeDetected(seedParam, oldPattern, newPattern)
                self._trackedSeedPatterns[paramId] = newPattern

        self._handleSeedOriginTreeChange(param, change, data)
        self._handleSeedGridGrowStepsTreeChange(param, change, data)

    def _handleSeedOriginTreeChange(self, param, change, data) -> None:
        if change != 'value':
            return

        originParam = None
        seedParam = None

        if param.name() == 'Seed origin':
            originParam = param
            seedParam = param.parent()
        else:
            parentParam = param.parent()
            if parentParam is not None and parentParam.name() == 'Seed origin':
                originParam = parentParam
                seedParam = parentParam.parent()

        if originParam is None or not isinstance(seedParam, MySeedParameter):
            return

        paramId = id(seedParam)
        oldOrigin = self._trackedSeedOrigins.get(paramId)
        newOrigin = self._copyVector(originParam.value() if hasattr(originParam, 'value') else data)
        if oldOrigin is not None and self._vectorKey(oldOrigin) != self._vectorKey(newOrigin):
            self.window.seedOriginShiftDetected(seedParam, oldOrigin, newOrigin)
        self._trackedSeedOrigins[paramId] = newOrigin

    def _handleSeedGridGrowStepsTreeChange(self, param, change, data) -> None:
        del data

        if change != 'value':
            return

        gridParam = self._findAncestorByName(param, 'Grid grow steps')
        if gridParam is None:
            return

        seedParam = gridParam.parent()
        if not isinstance(seedParam, MySeedParameter):
            return

        paramId = id(seedParam)
        oldGrowList = self._trackedSeedGridGrowLists.get(paramId)
        newGrowList = self._growListFromParam(gridParam)
        if oldGrowList is not None and self._growListKey(oldGrowList) != self._growListKey(newGrowList):
            self.window.seedGridGrowStepsChangeDetected(seedParam, oldGrowList, newGrowList)
        self._trackedSeedGridGrowLists[paramId] = newGrowList

    def seedNameChangeDetected(self, param, oldName, newName) -> None:
        paramId = id(param)
        pendingRename = self._pendingSeedRenames.get(paramId)

        if pendingRename is None:
            self._pendingSeedRenames[paramId] = {'oldName': oldName, 'newName': newName}
        else:
            pendingRename['newName'] = newName

        if self._pendingSeedRenames[paramId]['oldName'] == self._pendingSeedRenames[paramId]['newName']:
            self._pendingSeedRenames.pop(paramId, None)

        self._trackedSeedNames[paramId] = newName

    def seedColorChangeDetected(self, param, oldColor, newColor) -> None:
        paramId = id(param)
        pendingColor = self._pendingSeedColors.get(paramId)

        if pendingColor is None:
            self._pendingSeedColors[paramId] = {'param': param, 'oldColor': self._copyColor(oldColor), 'newColor': self._copyColor(newColor)}
        else:
            pendingColor['newColor'] = self._copyColor(newColor)

        if self._colorKey(self._pendingSeedColors[paramId]['oldColor']) == self._colorKey(self._pendingSeedColors[paramId]['newColor']):
            self._pendingSeedColors.pop(paramId, None)

        self._trackedSeedColors[paramId] = self._copyColor(newColor)

    def seedOriginShiftDetected(self, param, oldOrigin, newOrigin) -> None:
        paramId = id(param)
        pendingOrigin = self._pendingSeedOrigins.get(paramId)

        if pendingOrigin is None:
            self._pendingSeedOrigins[paramId] = {'param': param, 'oldOrigin': self._copyVector(oldOrigin), 'newOrigin': self._copyVector(newOrigin)}
        else:
            pendingOrigin['newOrigin'] = self._copyVector(newOrigin)

        if self._vectorKey(self._pendingSeedOrigins[paramId]['oldOrigin']) == self._vectorKey(self._pendingSeedOrigins[paramId]['newOrigin']):
            self._pendingSeedOrigins.pop(paramId, None)

        self._trackedSeedOrigins[paramId] = self._copyVector(newOrigin)

    def seedGridGrowStepsChangeDetected(self, param, oldGrowList, newGrowList) -> None:
        paramId = id(param)
        pendingGrowList = self._pendingSeedGridGrowLists.get(paramId)

        if pendingGrowList is None:
            self._pendingSeedGridGrowLists[paramId] = {'param': param, 'oldGrowList': self._copyGrowList(oldGrowList), 'newGrowList': self._copyGrowList(newGrowList)}
        else:
            pendingGrowList['newGrowList'] = self._copyGrowList(newGrowList)

        if self._growListKey(self._pendingSeedGridGrowLists[paramId]['oldGrowList']) == self._growListKey(self._pendingSeedGridGrowLists[paramId]['newGrowList']):
            self._pendingSeedGridGrowLists.pop(paramId, None)

        self._trackedSeedGridGrowLists[paramId] = self._copyGrowList(newGrowList)

    def seedPatternChangeDetected(self, param, oldPattern, newPattern) -> None:
        paramId = id(param)
        pendingPattern = self._pendingSeedPatterns.get(paramId)

        if pendingPattern is None:
            self._pendingSeedPatterns[paramId] = {'param': param, 'oldPattern': oldPattern, 'newPattern': newPattern}
        else:
            pendingPattern['newPattern'] = newPattern

        if self._pendingSeedPatterns[paramId]['oldPattern'] == self._pendingSeedPatterns[paramId]['newPattern']:
            self._pendingSeedPatterns.pop(paramId, None)

        self._trackedSeedPatterns[paramId] = newPattern

    def resetSurveyProperties(self):
        window = self.window

        window.paramTree.clear()

        surveyCopy = window.survey.deepcopy()
        if surveyCopy is None:
            return

        window.updatePatternList(surveyCopy)

        window.parameters = pg.parametertree.Parameter.create(
            name='Survey Properties',
            type='group',
            children=self._buildSurveyParameters(surveyCopy),
        )
        window.parameters.sigTreeStateChanged.connect(window.propertyTreeStateChanged)

        window.paramTree.blockSignals(True)
        window.paramTree.setParameters(window.parameters, showTop=False)
        window.paramTree.blockSignals(False)

        self._connectBinningWatchers()
        nItem = self._configureParameterTreeItems()
        self._resetSeedChangeTracking()
        window.appendLogMessage(f'Params : {window.fileName} survey object read, containing {nItem} parameters')
        window.enableProcessingMenuItems(True)

    def updatePatternList(self, survey):
        # Controller contract.
        assert isinstance(survey, RollSurvey), 'make sure we have a RollSurvey object here'  # nosec B101

        patternNames = [pattern.name for pattern in survey.patternList]
        combos = [self.window.pattern1, self.window.pattern2, self.window.pattern3, self.window.pattern4]

        for combo in combos:
            combo.blockSignals(True)

        try:
            self._populatePatternCombo(self.window.pattern1, patternNames)
            self._populatePatternCombo(self.window.pattern2, patternNames)
            self._populatePatternCombo(self.window.pattern3, patternNames)
            self._populatePatternCombo(self.window.pattern4, patternNames)

            listSize = len(patternNames)
            self.window.pattern1.setCurrentIndex(min(listSize, 1))
            self.window.pattern2.setCurrentIndex(min(listSize, 2))
            self.window.pattern3.setCurrentIndex(min(listSize, 1))
            self.window.pattern4.setCurrentIndex(min(listSize, 2))
        finally:
            for combo in combos:
                combo.blockSignals(False)

    def applyPropertyChanges(self):
        window = self.window

        surveyCopy = self._buildSurveyFromParameters()
        confirmedSeedRenames = self._applyPendingSeedRenamePropagation(surveyCopy)
        confirmedSeedColors = self._applyPendingSeedColorPropagation(surveyCopy)
        confirmedSeedOriginShifts = self._applyPendingSeedOriginShiftPropagation(surveyCopy)
        confirmedSeedGridGrowLists = self._applyPendingSeedGridGrowStepPropagation(surveyCopy)
        confirmedSeedPatterns = self._applyPendingSeedPatternPropagation(surveyCopy)
        if surveyCopy.checkIntegrity() is False:
            return

        self._commitSurveyCopy(surveyCopy)
        self._applyConfirmedSeedRenamesToWorkingTree(confirmedSeedRenames)
        self._applyConfirmedSeedColorsToWorkingTree(confirmedSeedColors)
        self._applyConfirmedSeedOriginShiftsToWorkingTree(confirmedSeedOriginShifts)
        self._applyConfirmedSeedGridGrowListsToWorkingTree(confirmedSeedGridGrowLists)
        self._applyConfirmedSeedPatternsToWorkingTree(confirmedSeedPatterns)
        self._pendingSeedRenames.clear()
        self._pendingSeedColors.clear()
        self._pendingSeedOrigins.clear()
        self._pendingSeedGridGrowLists.clear()
        self._pendingSeedPatterns.clear()
        self._resetSeedChangeTracking()

        if window.binAreaChanged:
            self._invalidateAnalysisOutputs()
        else:
            window.updateMenuStatus(False)

        window.enableProcessingMenuItems(True)
        window.appendLogMessage(f'Edited : {window.fileName} survey object updated')
        window.updatePatternList(window.survey)
        window.plotLayout()

        # Keep the 3D Subset view (if currently shown) in sync with the
        # edited survey.
        refreshLayout3DFromSurvey(window)

    def _buildSurveyParameters(self, surveyCopy):
        brush = '#add8e6'

        return [
            dict(brush=brush, name='Survey configuration', type='myConfiguration', value=surveyCopy, default=surveyCopy),
            dict(brush=brush, name='Survey analysis', type='myAnalysis', value=surveyCopy, default=surveyCopy),
            dict(brush=brush, name='Survey reflectors', type='myReflectors', value=surveyCopy, default=surveyCopy),
            dict(brush=brush, name='Survey grid', type='myGrid', value=surveyCopy.grid, default=surveyCopy.grid),
            dict(brush=brush, name='Block list', type='myBlockList', value=surveyCopy.blockList, default=surveyCopy.blockList, wellDirectory=self.window.wellDirectory, survey=surveyCopy),
            dict(brush=brush, name='Pattern list', type='myPatternList', value=surveyCopy.patternList, default=surveyCopy.patternList, survey=surveyCopy),
        ]

    def _connectBinningWatchers(self):
        window = self.window

        window.binChild = window.parameters.child('Survey analysis', 'Binning area')
        window.binChild.sigTreeStateChanged.connect(window.binningSettingsHaveChanged)

        window.grdChild = window.parameters.child('Survey grid')
        window.grdChild.sigTreeStateChanged.connect(window.binningSettingsHaveChanged)

    def _configureParameterTreeItems(self):
        nItem = 0

        for item in self.window.paramTree.listAllItems():
            parameter = item.param
            if 'tip' in parameter.opts:
                item.setToolTip(0, parameter.opts['tip'])
            if hasattr(item, 'updateDefaultBtn'):
                parameter.setToDefault()
                item.updateDefaultBtn()
            nItem += 1

        return nItem

    def _resetSeedChangeTracking(self):
        self._trackedSeedNames = {}
        self._trackedSeedColors = {}
        self._trackedSeedOrigins = {}
        self._trackedSeedGridGrowLists = {}
        self._trackedSeedPatterns = {}
        self._pendingSeedRenames = {}
        self._pendingSeedColors = {}
        self._pendingSeedOrigins = {}
        self._pendingSeedGridGrowLists = {}
        self._pendingSeedPatterns = {}

        for item in self.window.paramTree.listAllItems():
            param = getattr(item, 'param', None)
            if isinstance(param, MySeedParameter):
                self._trackedSeedNames[id(param)] = param.name()
                if hasattr(param, 'parL'):
                    self._trackedSeedColors[id(param)] = self._copyColor(param.parL.value())
                if hasattr(param, 'parO'):
                    self._trackedSeedOrigins[id(param)] = self._copyVector(param.parO.value())
                if hasattr(param, 'parG'):
                    self._trackedSeedGridGrowLists[id(param)] = self._copyGrowList(param.parG.value())
                if hasattr(param, 'parP'):
                    self._trackedSeedPatterns[id(param)] = param.parP.value()

    def _populatePatternCombo(self, combo, patternNames):
        combo.clear()
        combo.addItem('<no pattern>')
        for name in patternNames:
            combo.addItem(name)

    def _buildSurveyFromParameters(self):
        window = self.window
        surveyCopy = RollSurvey()

        configuration = window.parameters.child('Survey configuration')
        surveyCopy.crs, surveyType, surveyCopy.name = configuration.value()
        surveyCopy.type = SurveyType[surveyType]

        analysis = window.parameters.child('Survey analysis')
        surveyCopy.output.rctOutput, surveyCopy.angles, surveyCopy.binning, surveyCopy.offset, surveyCopy.unique = analysis.value()

        reflectors = window.parameters.child('Survey reflectors')
        surveyCopy.globalPlane, surveyCopy.globalSphere = reflectors.value()

        surveyGrid = window.parameters.child('Survey grid')
        surveyCopy.grid = surveyGrid.value()

        blockList = window.parameters.child('Block list')
        surveyCopy.blockList = blockList.value()

        patternList = window.parameters.child('Pattern list')
        surveyCopy.patternList = patternList.value()

        surveyCopy.bindSeedsToSurvey()
        return surveyCopy

    def _applyPendingSeedRenamePropagation(self, surveyCopy):
        confirmedSeedRenames = []

        for pendingRename in self._pendingSeedRenames.values():
            oldName = pendingRename['oldName']
            newName = pendingRename['newName']

            if oldName == newName:
                continue

            matchingSeeds = [seed for seed in self._iterSurveySeeds(surveyCopy) if seed.name == oldName]
            if not matchingSeeds:
                continue

            reply = QMessageBox.question(
                self.window,
                'Propagate seed rename',
                f'Seed name changed from "{oldName}" to "{newName}".\n\nRename {len(matchingSeeds)} other seed(s) with the old name?',
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                for seed in matchingSeeds:
                    seed.name = newName

                confirmedSeedRenames.append((oldName, newName))

        return confirmedSeedRenames

    def _applyPendingSeedColorPropagation(self, surveyCopy):
        confirmedSeedColors = []

        for pendingColor in self._pendingSeedColors.values():
            seedName = pendingColor['param'].name()
            newColor = self._copyColor(pendingColor['newColor'])
            matchingSeeds = [seed for seed in self._iterSurveySeeds(surveyCopy) if seed.name == seedName]
            otherSeedCount = len(matchingSeeds) - 1

            if otherSeedCount <= 0:
                continue

            reply = QMessageBox.question(
                self.window,
                'Propagate seed color',
                f'Seed color changed for "{seedName}".\n\nApply the new color to {otherSeedCount} other seed(s) with the same name?',
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                for seed in matchingSeeds:
                    seed.color = self._copyColor(newColor)

                confirmedSeedColors.append((seedName, self._copyColor(newColor)))

        return confirmedSeedColors

    def _applyPendingSeedOriginShiftPropagation(self, surveyCopy):
        confirmedSeedOriginShifts = []

        for pendingOrigin in self._pendingSeedOrigins.values():
            seedParam = pendingOrigin['param']
            seedName = seedParam.name()
            oldOrigin = self._copyVector(pendingOrigin['oldOrigin'])
            newOrigin = self._copyVector(pendingOrigin['newOrigin'])
            shift = self._vectorDelta(oldOrigin, newOrigin)

            if self._isZeroVector(shift):
                continue

            matchingSeeds = [seed for seed in self._iterSurveySeeds(surveyCopy) if seed.name == seedName]
            sameNameIndex = self._findWorkingTreeSeedOccurrenceIndex(seedParam, seedName)
            if sameNameIndex is None or sameNameIndex >= len(matchingSeeds):
                continue

            otherSeeds = [seed for index, seed in enumerate(matchingSeeds) if index != sameNameIndex]
            if not otherSeeds:
                continue

            reply = QMessageBox.question(
                self.window,
                'Propagate seed origin shift',
                (
                    f'Seed origin changed for "{seedName}" by {self._formatVector(shift)}.\n\n'
                    f'Apply the same shift, relative to each seed\'s own original origin, '
                    f'to {len(otherSeeds)} other seed(s) with the same name?'
                ),
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                for seed in otherSeeds:
                    seed.origin = self._shiftVector(seed.origin, shift)

                confirmedSeedOriginShifts.append((seedParam, seedName, self._copyVector(shift)))

        return confirmedSeedOriginShifts

    def _applyPendingSeedGridGrowStepPropagation(self, surveyCopy):
        confirmedSeedGridGrowLists = []

        for pendingGrowList in self._pendingSeedGridGrowLists.values():
            seedParam = pendingGrowList['param']
            seedName = seedParam.name()
            newGrowList = self._copyGrowList(pendingGrowList['newGrowList'])
            matchingSeeds = [seed for seed in self._iterSurveySeeds(surveyCopy) if self._isGridSurveySeed(seed) and seed.name == seedName]
            sameNameIndex = self._findWorkingTreeSeedOccurrenceIndex(seedParam, seedName, seedFilter=self._isGridSeedParameter)
            if sameNameIndex is None or sameNameIndex >= len(matchingSeeds):
                continue

            otherSeeds = [seed for index, seed in enumerate(matchingSeeds) if index != sameNameIndex]
            if not otherSeeds:
                continue

            reply = QMessageBox.question(
                self.window,
                'Propagate grid grow steps',
                f'Grid grow steps changed for "{seedName}".\n\nApply these grow steps to {len(otherSeeds)} other seed(s) with the same name?',
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                for seed in otherSeeds:
                    seed.grid.growList = self._copyGrowList(newGrowList)

                confirmedSeedGridGrowLists.append((seedParam, seedName, self._copyGrowList(newGrowList)))

        return confirmedSeedGridGrowLists

    def _applyPendingSeedPatternPropagation(self, surveyCopy):
        confirmedSeedPatterns = []

        for pendingPattern in self._pendingSeedPatterns.values():
            seedParam = pendingPattern['param']
            seedName = seedParam.name()
            newPattern = pendingPattern['newPattern']
            patternIndex = self._patternNameToIndex(surveyCopy, newPattern)
            matchingSeeds = [seed for seed in self._iterSurveySeeds(surveyCopy) if self._isGridSurveySeed(seed) and seed.name == seedName]
            sameNameIndex = self._findWorkingTreeSeedOccurrenceIndex(seedParam, seedName, seedFilter=self._isGridSeedParameter)
            if sameNameIndex is None or sameNameIndex >= len(matchingSeeds):
                continue

            otherSeeds = [seed for index, seed in enumerate(matchingSeeds) if index != sameNameIndex]
            if not otherSeeds:
                continue

            reply = QMessageBox.question(
                self.window,
                'Propagate seed pattern',
                f'Seed pattern changed for "{seedName}" to "{newPattern}".\n\nApply the same pattern to {len(otherSeeds)} other seed(s) with the same name?',
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                for seed in otherSeeds:
                    seed.patternNo = patternIndex

                confirmedSeedPatterns.append((seedParam, seedName, newPattern))

        return confirmedSeedPatterns

    def _applyConfirmedSeedRenamesToWorkingTree(self, confirmedSeedRenames):
        if not confirmedSeedRenames:
            return

        for oldName, newName in confirmedSeedRenames:
            for item in self.window.paramTree.listAllItems():
                param = getattr(item, 'param', None)
                if isinstance(param, MySeedParameter) and param.name() == oldName:
                    param.setName(newName)

    def _applyConfirmedSeedColorsToWorkingTree(self, confirmedSeedColors):
        if not confirmedSeedColors:
            return

        for seedName, newColor in confirmedSeedColors:
            for item in self.window.paramTree.listAllItems():
                param = getattr(item, 'param', None)
                if isinstance(param, MySeedParameter) and param.name() == seedName:
                    param.parL.setValue(self._copyColor(newColor))

    def _applyConfirmedSeedOriginShiftsToWorkingTree(self, confirmedSeedOriginShifts):
        if not confirmedSeedOriginShifts:
            return

        for changedParam, seedName, shift in confirmedSeedOriginShifts:
            for item in self.window.paramTree.listAllItems():
                param = getattr(item, 'param', None)
                if isinstance(param, MySeedParameter) and param is not changedParam and param.name() == seedName:
                    param.parO.child('X').setValue(param.parO.child('X').value() + shift.x())
                    param.parO.child('Y').setValue(param.parO.child('Y').value() + shift.y())
                    param.parO.child('Z').setValue(param.parO.child('Z').value() + shift.z())

    def _applyConfirmedSeedGridGrowListsToWorkingTree(self, confirmedSeedGridGrowLists):
        if not confirmedSeedGridGrowLists:
            return

        for changedParam, seedName, growList in confirmedSeedGridGrowLists:
            for item in self.window.paramTree.listAllItems():
                param = getattr(item, 'param', None)
                if isinstance(param, MySeedParameter) and param is not changedParam and param.name() == seedName and self._isGridSeedParameter(param):
                    self._applyGrowListToWorkingTree(param.parG, growList)

    def _applyConfirmedSeedPatternsToWorkingTree(self, confirmedSeedPatterns):
        if not confirmedSeedPatterns:
            return

        for changedParam, seedName, patternName in confirmedSeedPatterns:
            for item in self.window.paramTree.listAllItems():
                param = getattr(item, 'param', None)
                if isinstance(param, MySeedParameter) and param is not changedParam and param.name() == seedName and self._isGridSeedParameter(param):
                    param.parP.setValue(patternName)

    def _iterSurveySeeds(self, surveyCopy):
        for block in surveyCopy.blockList:
            for template in block.templateList:
                for seed in template.seedList:
                    yield seed

    def _copyColor(self, color):
        return QColor(color)

    def _colorKey(self, color):
        return self._copyColor(color).name(QColor.NameFormat.HexArgb)

    def _copyVector(self, vector):
        return QVector3D(float(vector.x()), float(vector.y()), float(vector.z()))

    def _vectorKey(self, vector):
        value = self._copyVector(vector)
        return (value.x(), value.y(), value.z())

    def _vectorDelta(self, oldVector, newVector):
        return QVector3D(
            newVector.x() - oldVector.x(),
            newVector.y() - oldVector.y(),
            newVector.z() - oldVector.z(),
        )

    def _shiftVector(self, vector, shift):
        return QVector3D(
            float(vector.x()) + shift.x(),
            float(vector.y()) + shift.y(),
            float(vector.z()) + shift.z(),
        )

    def _isZeroVector(self, vector):
        return self._vectorKey(vector) == (0.0, 0.0, 0.0)

    def _formatVector(self, vector):
        return f'({vector.x():.2f}, {vector.y():.2f}, {vector.z():.2f})'

    def _copyGrowList(self, growList):
        return [self._copyTranslate(translate) for translate in growList]

    def _growListFromParam(self, gridParam):
        stepNames = ('Planes', 'Lines', 'Points')

        if hasattr(gridParam, 'child'):
            try:
                return [self._translateFromParam(gridParam.child(stepName)) for stepName in stepNames]
            except (AttributeError, KeyError, TypeError, ValueError):
                pass

        return self._copyGrowList(gridParam.value())

    def _translateFromParam(self, stepParam):
        if hasattr(stepParam, 'child'):
            try:
                copy = RollTranslate(getattr(stepParam, 'name', lambda: '')())
                copy.steps = int(stepParam.child('N').value())
                copy.increment.setX(float(stepParam.child('dX').value()))
                copy.increment.setY(float(stepParam.child('dY').value()))
                copy.increment.setZ(float(stepParam.child('dZ').value()))
                return copy
            except (AttributeError, KeyError, TypeError, ValueError):
                pass

        return self._copyTranslate(stepParam.value())

    def _copyTranslate(self, translate):
        copy = RollTranslate(getattr(translate, 'name', ''))
        copy.steps = int(translate.steps)
        copy.increment = QVector3D(translate.increment)
        copy.azim = getattr(translate, 'azim', None)
        copy.tilt = getattr(translate, 'tilt', None)
        return copy

    def _growListKey(self, growList):
        return tuple((translate.steps, translate.increment.x(), translate.increment.y(), translate.increment.z()) for translate in growList)

    def _applyGrowListToWorkingTree(self, gridParam, growList):
        stepNames = ('Planes', 'Lines', 'Points')

        for stepName, translate in zip(stepNames, growList):
            stepParam = gridParam.child(stepName)
            stepParam.child('N').setValue(translate.steps)
            stepParam.child('dX').setValue(translate.increment.x())
            stepParam.child('dY').setValue(translate.increment.y())
            stepParam.child('dZ').setValue(translate.increment.z())

    def _patternNameToIndex(self, surveyCopy, patternName):
        if patternName == '<None>':
            return -1

        for index, pattern in enumerate(surveyCopy.patternList):
            if pattern.name == patternName:
                return index

        return -1

    def _findAncestorByName(self, param, targetName):
        current = param
        while current is not None:
            if current.name() == targetName:
                return current
            current = current.parent()
        return None

    def _isGridSurveySeed(self, seed):
        return seed.type <= SeedType.fixedGrid

    def _isGridSeedParameter(self, param):
        return not hasattr(param, 'parT') or param.parT.value() in ('Grid (roll along)', 'Grid (stationary)')

    def _findWorkingTreeSeedOccurrenceIndex(self, targetParam, seedName, seedFilter=None):
        occurrenceIndex = 0

        for item in self.window.paramTree.listAllItems():
            param = getattr(item, 'param', None)
            if not isinstance(param, MySeedParameter) or param.name() != seedName:
                continue

            if seedFilter is not None and not seedFilter(param):
                continue

            if param is targetParam:
                return occurrenceIndex

            occurrenceIndex += 1

        return None

    def _commitSurveyCopy(self, surveyCopy):
        window = self.window

        currentPaintMode = getattr(window.survey, 'paintMode', None)
        currentPaintDetails = getattr(window.survey, 'paintDetails', None)

        window.survey = surveyCopy.deepcopy()
        if currentPaintMode is not None:
            window.survey.paintMode = currentPaintMode
        if currentPaintDetails is not None:
            window.survey.paintDetails = currentPaintDetails
        window.survey.calcTransforms()
        window.survey.calcSeedData()
        window.survey.calcBoundingRect()
        window.survey.calcNoShotPoints()

        plainText = window.survey.toXmlString()
        window.textEdit.setTextViaCursor(plainText)
        window.textEdit.document().setModified(True)

    def _invalidateAnalysisOutputs(self):
        window = self.window

        window.binAreaChanged = False

        window.inlineStk = None
        window.x0lineStk = None
        window.xyCellStk = None
        window.xyPatResp = None
        window.plotRedrawHelper.reset()

        window.output.binOutput = None
        window.output.minOffset = None
        window.output.maxOffset = None
        window.output.rmsOffset = None
        window.output.gapOffset = None
        window.output.cfpOutput = None
        window.output.ofAziHist = None
        window.output.offstHist = None

        window.output.minOffsetGap = 0.0
        window.output.maxOffsetGap = 0.0

        if window.resetAnaTableModel():
            window.appendLogMessage(f"Edited : Closing memory mapped file {window.fileName + '.ana.npy'}")

        self._deleteAnalysisSidecars()
        window.updateMenuStatus(True)

    def _deleteAnalysisSidecars(self):
        sidecarPaths = [
            self.window.fileName + '.bin.npy',
            self.window.fileName + '.min.npy',
            self.window.fileName + '.max.npy',
            self.window.fileName + '.rms.npy',
            self.window.fileName + '.gap.npy',
            self.window.fileName + '.cfp.npy',
            self.window.fileName + '.ana.npy',
        ]

        try:
            for sidecarPath in sidecarPaths:
                if os.path.exists(sidecarPath):
                    os.remove(sidecarPath)
        except OSError as exc:
            self.window.appendLogMessage(f"Can't delete file, {exc}")
