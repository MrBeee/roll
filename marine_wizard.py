# -----------------------------------------------------------------------------------------------------------------
# https://north-road.com/2018/03/09/implementing-an-in-house-new-project-wizard-for-qgis/
# See: https://doc.qt.io/archives/qq/qq22-qwizard.html#registeringandusingfields for innards of a QWizard
# -----------------------------------------------------------------------------------------------------------------

# See: https://p.yusukekamiyamane.com/ for free icons
# See: https://www.pythonguis.com/faq/editing-pyqt-tableview/ for editing a table widget

import math
import os
import os.path

import numpy as np
import pyqtgraph as pg
from qgis.gui import QgsProjectionSelectionTreeWidget
from qgis.PyQt.QtCore import QRectF, QRegularExpression
from qgis.PyQt.QtGui import (QColor, QImage, QPixmap,
                             QRegularExpressionValidator, QTextOption,
                             QTransform)
from qgis.PyQt.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFrame,
                                 QGridLayout, QLabel, QLineEdit, QMessageBox,
                                 QPlainTextEdit, QSizePolicy, QSpinBox,
                                 QVBoxLayout, QWizard, QWizardPage)

from . import config  # used to pass initial settings
from .functions import (even, intListToString, knotToMeterperSec,
                        lineturnDetour, maxCableLengthVsTurnSpeed,
                        maxTurnSpeedVsCableLength, myPrint, newtonToTonForce,
                        rotatePoint2D, stringToIntList, tonForceToNewton)
from .pg_toolbar import PgToolBar
from .roll_pattern import RollPattern
from .roll_survey import (PaintDetails, PaintMode, RollSurvey, SurveyList,
                          SurveyType)

current_dir = os.path.dirname(os.path.abspath(__file__))
resource_dir = os.path.join(current_dir, 'resources')


class QHLine(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)


class QVLine(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.VLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)


# WIZARD  =======================================================================

# this derived wizard class contains a survey object, that is passed to the wizard pages
class SurveyWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)

        # to access the main window and its components
        self.parent = parent

        # in the wizard constructor, first create the survey object for use in subsequent wizard pages
        self.survey = RollSurvey()


class SurveyWizardPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent                                                    # to access parent's parameters in the wizard pages (this will crash if parent is None)

    def cleanupPage(self):                                                      # is called to reset the page’s contents when the user clicks the wizard’s Back button.
        # The default implementation resets the page’s fields to their original values
        # To prevent initializePage() being called when browsing backwards,
        pass                                                                    # the default is now to do absolutely nothing !


class MarineSurveyWizard(SurveyWizard):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.addPage(Page_1(self))
        self.addPage(Page_2(self))
        self.addPage(Page_3(self))
        self.addPage(Page_4(self))
        self.addPage(Page_5(self))
        self.addPage(Page_6(self))
        self.addPage(Page_7(self))
        self.addPage(Page_8(self))
        self.addPage(Page_9(self))

        self.setWindowTitle('Towed Streamer Survey Wizard')
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)

        # self.setOption(QWizard.IndependentPages , True) # Don't use this option as fields are no longer updated !!! Make dummy cleanupPage(self) instead
        logo_image = QImage(os.path.join(resource_dir, 'icon.png'))
        self.setPixmap(QWizard.WizardPixmap.LogoPixmap, QPixmap.fromImage(logo_image))


#        self.setOption(QWizard.NoCancelButton, True)
#        self.setWindowFlags(self.windowFlags() | QtCore.Qt.CustomizeWindowHint)
#        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowCloseButtonHint)

# def reject(self):
#        pass


# Page_1 =======================================================================
# 1. Survey type, Nr lines, and line & point intervals


class Page_1(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setTitle('1. Template Properties (1/2)')
        self.setSubTitle('Enter survey name, currents and towing configuration')

        myPrint('page 1 init')

        # create some widgets
        self.name = QLineEdit()
        self.name.setStyleSheet('QLineEdit  { background-color : lightblue} ')
        name = SurveyType(SurveyType.Streamer.value).name                       # get name from enum
        number = str(config.surveyNumber).zfill(3)                              # fill with leading zeroes
        self.name.setText(f'{name}_{number}')                                   # show the new name
        self.registerField('name', self.name)                                   # Survey name

        # to register fields for variable access in other Wizard Pages
        # see: https://stackoverflow.com/questions/35187729/pyqt5-double-spin-box-returning-none-value
        # See: https://stackoverflow.com/questions/33796022/use-registerfield-in-pyqt

        self.type = QComboBox()
        self.type.addItem(SurveyList[-1])
        self.type.setStyleSheet('QComboBox  { background-color : lightblue} ')
        self.registerField('type', self.type)                                   # Survey type

        self.vSail = QDoubleSpinBox()
        self.vSail.setRange(0.1, 10.0)
        self.vSail.setValue(config.vSail)                                       # do this once in the constructor
        self.vSail.textChanged.connect(self.updateParameters)
        self.vSail.editingFinished.connect(self.updateParameters)
        self.registerField('vSail', self.vSail, 'value')                        # Vessel acquisition speed

        self.vTurn = QDoubleSpinBox()
        self.vTurn.setRange(0.1, 10.0)
        self.vTurn.setValue(config.vTurn)                                       # do this once in the constructor
        self.vTurn.editingFinished.connect(self.evt_vTurn_editingFinished)
        self.registerField('vTurn', self.vTurn, 'value')                        # Vessel line turn speed

        self.vCross = QDoubleSpinBox()
        self.vCross.textChanged.connect(self.updateParameters)
        self.vCross.editingFinished.connect(self.updateParameters)
        self.vCross.setRange(-5.0, 5.0)
        self.vCross.setValue(0.0)
        # self.vCross.setEnabled(False)
        # self.vCross.setToolTip('Template rotation due to crossline currents not yet implemented')
        self.registerField('vCross', self.vCross, 'value')                      # crosscurrent speed

        self.vTail = QDoubleSpinBox()
        self.vTail.textChanged.connect(self.updateParameters)
        self.vTail.editingFinished.connect(self.updateParameters)
        self.vTail.setRange(-5.0, 5.0)
        self.vTail.setValue(0.0)
        self.registerField('vTail', self.vTail, 'value')                        # Tail current speed

        self.vCurrent = QDoubleSpinBox()                                        # readonly spinbox
        self.vCurrent.setRange(-10.0, 10.0)
        self.vCurrent.setValue(0.0)
        self.vCurrent.setEnabled(False)                                         # readonly
        self.registerField('vCurrent', self.vCurrent, 'value')                  # overall current speed

        self.aFeat = QDoubleSpinBox()
        self.aFeat.setRange(-90.0, 90.0)
        self.aFeat.setValue(0.0)
        self.aFeat.setEnabled(False)                                            # readonly
        self.registerField('aFeat', self.aFeat, 'value')                        # Feather angle

        self.cabLength = QDoubleSpinBox()
        self.cabLength.setRange(100.0, 20_000.0)
        self.cabLength.setValue(config.cabLength)
        self.cabLength.setSingleStep(1000.0)                                    # increment by km extra streamer
        self.cabLength.editingFinished.connect(self.evt_cabLength_editingFinished)
        self.registerField('cabLength', self.cabLength, 'value')                # streamer length

        self.groupInt = QDoubleSpinBox()
        self.groupInt.setRange(3.125, 250.0)
        self.groupInt.setValue(config.groupInt)
        self.groupInt.textChanged.connect(self.updateParameters)
        self.groupInt.editingFinished.connect(self.updateParameters)
        self.registerField('groupInt', self.groupInt, 'value')                  # group interval

        self.nSrc = QSpinBox()
        self.nSrc.setRange(1, 50)
        self.nSrc.setValue(config.nSrc)
        self.nSrc.textChanged.connect(self.updateParameters)
        self.nSrc.editingFinished.connect(self.updateParameters)
        self.registerField('nSrc', self.nSrc, 'value')                          # number of sources deployed

        self.nCab = QSpinBox()
        self.nCab.setRange(1, 50)
        self.nCab.setValue(config.nCab)
        self.nCab.setSingleStep(2)                                              # we want to stick to an even number of streamers
        self.registerField('nCab', self.nCab, 'value')                          # number of cables deployed

        self.srcPopInt = QDoubleSpinBox()
        self.srcPopInt.setRange(0.0, 10_000.0)
        self.srcPopInt.setValue(4.0 * 0.5 * config.groupInt)
        self.srcPopInt.textChanged.connect(self.updateParameters)
        self.srcPopInt.editingFinished.connect(self.updateParameters)
        self.registerField('srcPopInt', self.srcPopInt, 'value')                # pop interval

        self.srcShtInt = QDoubleSpinBox()
        self.srcShtInt.setEnabled(False)
        self.srcShtInt.setRange(0.0, 10_000.0)
        self.srcShtInt.setValue(4.0 * 0.5 * config.groupInt * config.nSrc)
        self.registerField('srcShtInt', self.srcShtInt, 'value')                # shot point interval (per cmp line)

        self.recTail = QDoubleSpinBox()
        self.recTail.setRange(0.001, 1000.0)
        self.recTail.setEnabled(False)
        self.registerField('recTail', self.recTail, 'value')                    # Clean record time, with tail current

        self.recHead = QDoubleSpinBox()
        self.recHead.setRange(0.001, 1000.0)
        self.recHead.setEnabled(False)
        self.registerField('recHead', self.recHead, 'value')                    # Clean record time, with head current

        self.srcDepth = QDoubleSpinBox()
        self.srcDepth.setValue(config.srcDepth)
        self.registerField('srcDepth', self.srcDepth, 'value')                  # source depth [m]

        self.recLength = QDoubleSpinBox()
        self.recLength.setValue(config.recLength)
        self.recLength.textChanged.connect(self.updateParameters)
        self.registerField('recLength', self.recLength, 'value')                # record length [s]

        self.chkPopGroupAlign = QCheckBox('Match pop interval to binsize (binsize = ½ streamer group)')
        self.chkPopGroupAlign.stateChanged.connect(self.updateParameters)

        # set the page layout
        layout = QGridLayout()

        row = 0
        layout.addWidget(self.type, row, 0, 1, 3)
        layout.addWidget(QLabel('<b>Survey type</b>'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('Provide an appropriate <b>description/name</b> for the survey'), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.name, row, 0, 1, 4)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Vessel speed in water'), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.vSail, row, 0)
        layout.addWidget(QLabel('<b>Acquisition</b> speed [kn]'), row, 1)
        layout.addWidget(self.vTurn, row, 2)
        layout.addWidget(QLabel('<b>Line turn</b> speed [kn]'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Tail- and Crossline currents</b>'), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.vTail, row, 0)
        layout.addWidget(QLabel('<b>Tail</b> current [kn]'), row, 1)
        layout.addWidget(self.vCross, row, 2)
        layout.addWidget(QLabel('<b>Crossline</b> current [kn]'), row, 3)

        # row += 1
        # layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Total current and feather angle</b>'), row, 0, 1, 2)

        row += 1
        layout.addWidget(self.vCurrent, row, 0)
        layout.addWidget(QLabel('<b>Total</b> current [kn]'), row, 1)   ##
        layout.addWidget(self.aFeat, row, 2)
        layout.addWidget(QLabel('<b>Feather</b> angle [deg]'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Towing configuration</b>'), row, 0, 1, 2)

        row += 1
        layout.addWidget(self.nCab, row, 0)
        layout.addWidget(QLabel('<b>Nr. streamers</b> [#]'), row, 1)
        layout.addWidget(self.nSrc, row, 2)
        layout.addWidget(QLabel('<b>Nr. sources</b> [#]'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Streamer length & Group interval</b>'), row, 0, 1, 2)

        row += 1
        layout.addWidget(self.cabLength, row, 0)
        layout.addWidget(QLabel('Streamer <b>length</b> [m]'), row, 1)   ##
        layout.addWidget(self.groupInt, row, 2)
        layout.addWidget(QLabel('Group <b>interval</b> [m]'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Shooting operation</b> (pop- and source point interval)'), row, 0, 1, 2)

        row += 1
        layout.addWidget(self.srcPopInt, row, 0)
        layout.addWidget(QLabel('<b>Pop</b> interval [m]'), row, 1)
        layout.addWidget(self.srcShtInt, row, 2)
        layout.addWidget(QLabel('<b>SP</b> interval [m]'), row, 3)

        row += 1
        layout.addWidget(self.chkPopGroupAlign, row, 0, 1, 4)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Source depth</b> and <b>record length</b>'), row, 0, 1, 2)

        row += 1
        self.recLengthLabel = QLabel('<b>Record length</b> [s]')
        layout.addWidget(self.srcDepth, row, 0)
        layout.addWidget(QLabel('<b>depth</b> [m]'), row, 1)   ##
        layout.addWidget(self.recLength, row, 2)
        layout.addWidget(self.recLengthLabel, row, 3)

        # row += 1
        # layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Clean record length</b> (i.e. without SP blending)'), row, 0, 1, 2)

        row += 1
        layout.addWidget(self.recTail, row, 0)
        layout.addWidget(QLabel('for <b>Tail</b> current [s]'), row, 1)
        layout.addWidget(self.recHead, row, 2)
        layout.addWidget(QLabel('for <b>Head</b> current [s]'), row, 3)

        self.setLayout(layout)

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        myPrint('initialize page 1')

        self.chkPopGroupAlign.setChecked(True)
        self.updateParameters()

    def cleanupPage(self):                                                      # needed to update previous page
        myPrint('cleanup of page 1')

    def updateParameters(self):
        # Page_1
        vSail = self.vSail.value()
        vTail = self.vTail.value()
        vCross = self.vCross.value()

        if abs(vTail) >= vSail:                                                 # handle excessive tail current
            vTrunc = vSail - 0.1
            vTail = vTrunc if vTail > 0.0 else -vTrunc
            self.vTail.setValue(vTail)

        if abs(vCross) >= vSail:                                                # handle excessive cross current
            vTrunc = vSail - 0.1
            vCross = vTrunc if vCross > 0.0 else -vTrunc
            self.vCross.setValue(vCross)

        popInt = self.srcPopInt.value()

        aFeat = math.degrees(math.asin(vCross / vSail))
        vCurrent = math.sqrt(vTail * vTail + vCross * vCross)

        vAtHeadCurrent = knotToMeterperSec(vSail * math.cos(vCross / vSail) - vTail)
        vAtTailCurrent = knotToMeterperSec(vSail * math.cos(vCross / vSail) + vTail)

        tAtHeadCurrent = popInt / vAtHeadCurrent
        tAtTailCurrent = popInt / vAtTailCurrent

        self.aFeat.setValue(aFeat)
        self.vCurrent.setValue(vCurrent)

        self.recTail.setValue(tAtTailCurrent)
        self.recHead.setValue(tAtHeadCurrent)

        tRecord = self.recLength.value()

        if tRecord > tAtHeadCurrent or tRecord > tAtTailCurrent:
            self.recLength.setStyleSheet('QDoubleSpinBox {color:red; background-color:lightblue;}')
            self.recLengthLabel.setStyleSheet('QLabel {color:red}')
        else:
            self.recLength.setStyleSheet('QDoubleSpinBox {color:black; background-color:white;}')
            self.recLengthLabel.setStyleSheet('QLabel {color:black}')

        nSrc = self.nSrc.value()
        self.srcShtInt.setValue(popInt * nSrc)

        groupInt = self.groupInt.value()
        step = 0.5 * groupInt
        if self.chkPopGroupAlign.isChecked():
            self.srcPopInt.setSingleStep(step)
            steps = max(round(popInt / step), 1)
            self.srcPopInt.setValue(steps * step)
        else:
            self.srcPopInt.setSingleStep(1.0)

    def evt_vTurn_editingFinished(self):
        vTurn = self.field('vTurn')                                             # Vessel line turn speed
        cL = self.field('cabLength')                                            # streamer length
        vMax = maxTurnSpeedVsCableLength(cL)
        if vTurn > vMax:
            reply = QMessageBox.warning(
                None, 'Excessive towing force', 'Line turn speed is too high for the current streamer length.\n Reduce streamer length to match line turn speed ?', QMessageBox.Yes, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                cLmax = maxCableLengthVsTurnSpeed(vTurn)
                self.cabLength.setValue(cLmax)
                self.vTurn.setValue(vTurn)
            else:
                self.vTurn.setValue(vMax)

    def evt_cabLength_editingFinished(self):
        cL = self.field('cabLength')                                            # streamer length
        vTurn = self.field('vTurn')                                             # Vessel line turn speed (from page 1)
        cLmax = maxCableLengthVsTurnSpeed(vTurn)
        if cL > cLmax:
            reply = QMessageBox.warning(
                None, 'Excessive towing force', 'Streamers are too long for the current line turn speed.\nReduce line turn speed to match streamer length ?', QMessageBox.Yes, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                vMax = maxTurnSpeedVsCableLength(cL)
                self.vTurn.setValue(vMax)
                self.cabLength.setValue(cL)
            else:
                self.cabLength.setValue(cLmax)


# Page_2 =======================================================================
# 2. Template Properties - Enter Spread and Salvo details


class Page_2(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setTitle('2. Template Properties (2/2)')
        self.setSubTitle('Complete the towing configuration')

        myPrint('page 2 init')

        self.spiderSrcX = None                                                  # np arrays needed for the cross-section plot
        self.spiderSrcZ = None
        self.spiderRecX = None
        self.spiderRecZ = None

        self.srcLayback = QDoubleSpinBox()
        self.srcLayback.setRange(0.0, 5000.0)
        self.srcLayback.setValue(config.srcLayback)

        self.cabLayback = QDoubleSpinBox()
        self.cabLayback.setRange(0.0, 5000.0)
        self.cabLayback.setValue(config.cabLayback)

        self.cabSepHead = QDoubleSpinBox()
        self.cabSepHead.setRange(10.0, 1000.0)
        self.cabSepHead.setValue(config.cabSepHead)
        self.cabSepHead.textChanged.connect(self.updateCableSeparation)
        self.cabSepHead.editingFinished.connect(self.updateCableSeparation)

        self.cabSepTail = QDoubleSpinBox()
        self.cabSepTail.setRange(10.0, 1000.0)
        self.cabSepTail.setValue(config.cabSepTail)
        self.cabSepTail.textChanged.connect(self.updateCableSeparation)
        self.cabSepTail.editingFinished.connect(self.updateCableSeparation)

        self.cabDepthHead = QDoubleSpinBox()
        self.cabDepthHead.setRange(1.0, 100.0)
        self.cabDepthHead.setValue(config.cabDepthHead)
        self.cabDepthHead.textChanged.connect(self.updateCableDepth)
        self.cabDepthHead.editingFinished.connect(self.updateCableDepth)

        self.cabDepthTail = QDoubleSpinBox()
        self.cabDepthTail.setRange(1.0, 10000.0)
        self.cabDepthTail.setValue(config.cabDepthTail)
        self.cabDepthTail.textChanged.connect(self.updateCableDepth)
        self.cabDepthTail.editingFinished.connect(self.updateCableDepth)

        self.srcSepFactor = QSpinBox()
        self.srcSepFactor.setRange(1, 10)
        self.srcSepFactor.setValue(config.srcSepFactor)
        self.srcSepFactor.textChanged.connect(self.updateSourceSeparation)
        self.srcSepFactor.editingFinished.connect(self.updateSourceSeparation)

        self.srcSeparation = QDoubleSpinBox()
        self.srcSeparation.setEnabled(False)                                    # readonly
        self.srcSeparation.setRange(0.0, 1000.0)
        self.srcSeparation.setValue(config.srcSeparation)

        # set the page layout
        layout = QGridLayout()

        row = 0
        layout.addWidget(QLabel('<b>Laybacks</b> in towing configuration'), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.cabLayback, row, 0)
        layout.addWidget(QLabel('<b>Streamer</b> layback [m]'), row, 1)
        layout.addWidget(self.srcLayback, row, 2)
        layout.addWidget(QLabel('<b>Source</b> layback [m]'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Streamer separation</b> (with optional fanning)'), row, 0, 1, 2)

        row += 1
        self.cabSepTailLabel = QLabel('<b>Tail</b> [m]')
        layout.addWidget(self.cabSepHead, row, 0)
        layout.addWidget(QLabel('<b>Head</b> [m]'), row, 1)   ##
        layout.addWidget(self.cabSepTail, row, 2)
        layout.addWidget(self.cabSepTailLabel, row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Streamer depth</b> (with optional slant)'), row, 0, 1, 2)

        row += 1
        self.cabDepthTailLabel = QLabel('<b>Tail</b> [m]')
        layout.addWidget(self.cabDepthHead, row, 0)
        layout.addWidget(QLabel('<b>Head</b> [m]'), row, 1)   ##
        layout.addWidget(self.cabDepthTail, row, 2)
        layout.addWidget(self.cabDepthTailLabel, row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Source separation </b> (resulting from streamer separation & widening <b>factor</b>)'), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.srcSepFactor, row, 0)
        layout.addWidget(QLabel('<b>Factor</b> [#]'), row, 1)   ##
        layout.addWidget(self.srcSeparation, row, 2)
        layout.addWidget(QLabel('<b>Separation</b> [m]'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        self.plotType = QComboBox()
        self.plotType.addItems(['Cross section of towed equipment', 'template(s) forward sailing on race track', 'template(s) return sailing  on race track'])
        self.plotType.setStyleSheet('QComboBox  { background-color : lightblue} ')
        self.plotType.currentIndexChanged.connect(self.plotTypeChanged)

        row += 1
        layout.addWidget(self.plotType, row, 0, 1, 3)
        layout.addWidget(QLabel('<b>Plot type</b>'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        # create a vertical box layout widget (vbl)
        vbl = QVBoxLayout()

        # add the so far developed QGridLayout to the QVBoxLayout (layout)
        vbl.addLayout(layout)

        # insert PyQtGraph plotWidget                                           # See: https://groups.google.com/g/pyqtgraph/c/ls-9I2tHu2w
        self.plotWidget = pg.PlotWidget(background='w')
        self.plotWidget.setAspectLocked(False)                                  # setting can be changed through a toolbar
        self.plotWidget.showGrid(x=True, y=True, alpha=0.5)                     # shows the grey grid lines
        self.plotWidget.setMinimumSize(150, 150)                                # prevent excessive widget shrinking
        self.plotWidget.ctrlMenu = None                                         # get rid of 'Plot Options'
        self.plotWidget.scene().contextMenu = None                              # get rid of 'Export'

        self.zoomBar = PgToolBar('ZoomBar', plotWidget=self.plotWidget)
        self.zoomBar.actionAntiAlias.setChecked(True)                           # toggle Anti-alias on
        self.zoomBar.actionAspectRatio.setChecked(False)                        # don't use same scaling for x and y axes

        # add toolbar and plotwidget to the vertical box layout
        vbl.addWidget(self.zoomBar)
        vbl.addWidget(self.plotWidget)

        # set the combined layouts to become this page's layout
        self.setLayout(vbl)

        self.registerField('srcLayback', self.srcLayback, 'value')
        self.registerField('cabLayback', self.cabLayback, 'value')

        self.registerField('cabSepHead', self.cabSepHead, 'value')
        self.registerField('cabSepTail', self.cabSepTail, 'value')

        self.registerField('cabDepthHead', self.cabDepthHead, 'value')
        self.registerField('cabDepthTail', self.cabDepthTail, 'value')

        self.registerField('srcSepFactor', self.srcSepFactor, 'value')
        self.registerField('srcSeparation', self.srcSeparation, 'value')

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        myPrint('initialize page 2')

        # completely RESET the survey object, so we can start with it from scratch
        self.parent.survey = RollSurvey()                                       # the survey object that will be modified

        # fill in the survey object information we already know now
        self.parent.survey.name = self.field('name')                            # Survey name
        self.parent.survey.type = SurveyType(SurveyType.Streamer.value)         # Survey type Enum

        # we know the cable length, so let's use that to define the allowed offsets
        cL = self.field('cabLength')                                            # streamer length

        maxInlineOffset = 1.5 * cL
        max_XlineOffset = 1.5 * cL
        maxRadialOffset = 2.5 * cL

        self.parent.survey.offset.rctOffsets.setLeft(-maxInlineOffset)
        self.parent.survey.offset.rctOffsets.setRight(maxInlineOffset)

        self.parent.survey.offset.rctOffsets.setTop(-max_XlineOffset)
        self.parent.survey.offset.rctOffsets.setBottom(max_XlineOffset)

        self.parent.survey.offset.radOffsets.setX(0.0)
        self.parent.survey.offset.radOffsets.setY(maxRadialOffset)

        self.plot()                                                             # refresh the plot

    def cleanupPage(self):                                                      # needed to update previous page
        myPrint('cleanup of page 2')

    def plotTypeChanged(self):
        self.plot()
        self.plotWidget.autoRange()

    def updateCableSeparation(self):
        cabSepHead = self.cabSepHead.value()
        cabSepTail = self.cabSepTail.value()

        if cabSepTail < cabSepHead:                                             # provide a warning
            self.cabSepTail.setStyleSheet('QDoubleSpinBox {color:red; background-color:lightblue;}')
            self.cabSepTailLabel.setStyleSheet('QLabel {color:red}')
        else:
            self.cabSepTail.setStyleSheet('QDoubleSpinBox {color:black; background-color:white;}')
            self.cabSepTailLabel.setStyleSheet('QLabel {color:black}')

        self.updateSourceSeparation()                                           # cable separation affects source separation too; contains self.plot()

    def updateCableDepth(self):
        cabDepthHead = self.cabDepthHead.value()
        cabDepthTail = self.cabDepthTail.value()

        if cabDepthTail < cabDepthHead:                                         # give a warning
            self.cabDepthTail.setStyleSheet('QDoubleSpinBox {color:red; background-color:lightblue;}')
            self.cabDepthTailLabel.setStyleSheet('QLabel {color:red}')
        else:
            self.cabDepthTail.setStyleSheet('QDoubleSpinBox {color:black; background-color:white;}')
            self.cabDepthTailLabel.setStyleSheet('QLabel {color:black}')
        self.plot()                                                             # refresh the plot

    def updateSourceSeparation(self):
        nSrc = self.field('nSrc')
        cabSepHead = self.cabSepHead.value()
        srcSepFactor = self.srcSepFactor.value()

        srcSeparation = cabSepHead * srcSepFactor / nSrc
        self.srcSeparation.setValue(srcSeparation)
        self.plot()                                                             # refresh the plot

    def plot(self):
        """plot cross-section or templates"""

        # parameters from fields from other page
        nSrc = self.field('nSrc')
        nCab = self.field('nCab')
        name = self.field('name')

        self.plotWidget.plotItem.clear()
        self.plotWidget.setTitle(name, color='b', size='12pt')
        self.plotWidget.setAntialiasing(True)
        # styles = {'color': '#646464', 'font-size': '10pt'}
        styles = {'color': '#000', 'font-size': '10pt'}

        plotIndex = self.plotType.currentIndex()                                # first, check what type of plot is expected
        if plotIndex == 0:                                                      # crossection plot
            self.updateParentSurvey(1)                                          # setup the skeleton anyhow, but don't use it for this plot

            self.plotWidget.setLabel('bottom', 'cross-section', units='m', **styles)   # shows axis at the bottom, and shows the units label
            self.plotWidget.setLabel('left', 'depth', units='m', **styles)      # shows axis at the left, and shows the units label
            # self.plotWidget.setLabel('top', ' ', **styles)                    # shows axis at the top, no label, no tickmarks
            # self.plotWidget.setLabel('right', ' ', **styles)                  # shows axis at the right, no label, no tickmarks
            self.plotWidget.setLabel('top', 'cross-section', units='m', **styles)   # shows axis at the top, no label, no tickmarks
            self.plotWidget.setLabel('right', 'depth', units='m', **styles)         # shows axis at the right, no label, no tickmarks

            cmps = nSrc * nCab                                                  # nr of cmp locations created by nSrc and nCab combined
            rays = 2 * cmps                                                     # to draw a line between from source --> cdp --> receiver for all src & rec combinations
            spiderSrcX = np.zeros(shape=rays, dtype=np.float32)                 # needed to display data points
            spiderSrcZ = np.zeros(shape=rays, dtype=np.float32)                 # needed to display data points
            spiderRecX = np.zeros(shape=rays, dtype=np.float32)                 # needed to display data points
            spiderRecZ = np.zeros(shape=rays, dtype=np.float32)                 # needed to display data points

            cmpActX = np.zeros(shape=cmps, dtype=np.float32)                    # needed to display data points
            cmpActZ = np.zeros(shape=cmps, dtype=np.float32)                    # needed to display data points
            cmpNomX = np.zeros(shape=cmps, dtype=np.float32)                    # needed to display data points
            cmpNomZ = np.zeros(shape=cmps, dtype=np.float32)                    # needed to display data points

            dCab0 = self.cabSepHead.value()
            dSrc = self.srcSeparation.value()

            recZ0 = -self.field('cabDepthHead')
            srcZ = -self.field('srcDepth')
            cmpZ = -config.cdpDepth

            rec0 = -0.5 * (nCab - 1) * dCab0                                    # first receiver
            src0 = -0.5 * (nSrc - 1) * dSrc                                     # first source actual location
            src1 = -0.5 * (nSrc - 1) * dCab0 / nSrc                             # first source nominal location (sep. factor == 1)
            cmp0 = 0.5 * (rec0 + src1)                                          # first cmp
            dCmp = 0.5 * dCab0 / nSrc                                           # cmp xline size

            for nS in range(nSrc):
                for nR in range(nCab):

                    cmpX = 0.5 * (src0 + nS * dSrc + rec0 + nR * dCab0)

                    l = nS * nCab + nR                                          # cmp index
                    n = 2 * l                                                   # line segment index 1st point
                    m = n + 1                                                   # line segment index 2nd point

                    spiderSrcX[n] = src0 + nS * dSrc
                    spiderSrcZ[n] = srcZ

                    spiderSrcX[m] = cmpX
                    spiderSrcZ[m] = cmpZ

                    spiderRecX[n] = rec0 + nR * dCab0
                    spiderRecZ[n] = recZ0

                    spiderRecX[m] = cmpX
                    spiderRecZ[m] = cmpZ

                    cmpActX[l] = cmpX
                    cmpActZ[l] = cmpZ

            for n in range(nSrc * nCab):
                cmpNomX[n] = cmp0 + n * dCmp
                cmpNomZ[n] = cmpZ

            # Add a marker for the origin
            oriX = [0.0]
            oriY = [0.0]
            orig = self.plotWidget.plot(x=oriX, y=oriY, symbol='h', symbolSize=12, symbolPen=(0, 0, 0, 100), symbolBrush=(180, 180, 180, 100))

            src = self.plotWidget.plot(x=spiderSrcX, y=spiderSrcZ, connect='pairs', pen=pg.mkPen('r', width=2), symbol='o', symbolSize=6, symbolPen=(0, 0, 0, 100), symbolBrush='r')
            rec = self.plotWidget.plot(x=spiderRecX, y=spiderRecZ, connect='pairs', pen=pg.mkPen('b', width=2), symbol='o', symbolSize=6, symbolPen=(0, 0, 0, 100), symbolBrush='b')
            nom = self.plotWidget.plot(x=cmpNomX, y=cmpNomZ, symbol='o', symbolSize=6, symbolPen=(0, 0, 0, 100), symbolBrush=(180, 180, 180, 100))
            act = self.plotWidget.plot(x=cmpActX, y=cmpActZ, symbol='o', symbolSize=6, symbolPen=(0, 0, 0, 100), symbolBrush='g')

        else:                                                      # top view forwards on race track
            # On this wizard page only forward OR backwards sailing templates are shown at once, determined by the plotIndex
            self.updateParentSurvey(plotIndex)                                      # create towing configuration without any roll along

            self.plotWidget.setLabel('bottom', 'inline', units='m', **styles)       # shows axis at the bottom, and shows the units label
            self.plotWidget.setLabel('left', 'crossline', units='m', **styles)      # shows axis at the left, and shows the units label
            self.plotWidget.setLabel('top', 'inline', units='m', **styles)          # shows axis at the top, and shows the survey name
            self.plotWidget.setLabel('right', 'crossline', units='m', **styles)     # shows axis at the top, and shows the survey name

            self.parent.survey.paintMode = PaintMode.justPoints                     # justPoints
            self.parent.survey.lodScale = 6.0
            item = self.parent.survey

            # 2. Template Properties - Enter the towing configuration
            self.plotWidget.plotItem.addItem(item)

            # Add a marker for the origin
            oriX = [0.0]
            oriY = [0.0]
            orig = self.plotWidget.plot(x=oriX, y=oriY, symbol='h', symbolSize=12, symbolPen=(0, 0, 0, 100), symbolBrush=(180, 180, 180, 100))

    def updateParentSurvey(self, plotIndex):
        # create / update the survey skeleton - Page_2

        nSrc = self.field('nSrc')
        nCab = self.field('nCab')

        dCab0 = self.field('cabSepHead')
        dCab9 = self.field('cabSepTail')

        fanning = True if dCab9 != dCab0 else False
        # Create a new survey skeleton, so we can simply update survey properties, without having to instantiate the underlying classes
        # in case no streamer fanning is required (parallel streamers), we just need a single receiver-seed per template
        if fanning:
            self.parent.survey.createBasicSkeleton(nTemplates=nSrc, nSrcSeeds=1, nRecSeeds=nCab)    # add  single block with template(s), with one seed for each streamer
        else:
            self.parent.survey.createBasicSkeleton(nTemplates=nSrc, nSrcSeeds=1, nRecSeeds=1)       # add  single block with template(s), with one seed for all streamers

        sL = self.field('srcLayback')
        rL = self.field('cabLayback')
        LB = rL - sL                                                            # relative source location (Lay back)
        cL = self.field('cabLength')                                            # streamer length
        gI = self.field('groupInt')                                             # group interval
        nGrp = round(cL / gI)                                                   # nr groups per streamer

        recZ0 = -self.field('cabDepthHead')
        recZ9 = -self.field('cabDepthTail')

        dSrc = self.field('srcSeparation')
        srcZ = -self.field('srcDepth')
        azim = self.field('aFeat')                                              # Feather angle

        dZCab = recZ9 - recZ0                                                   # depth increase along cable(s)
        dZGrp = -gI / cL * dZCab                                                # depth increase along group(s); independent on azimuth (from fanning and currents)

        dip = math.degrees(math.asin(dZCab / cL))
        cL9 = cL * math.cos(math.radians(dip))                                  # cable length reduced by slant

        src0 = -0.5 * (nSrc - 1) * dSrc                                         # cross-line position; first source
        rec0 = -0.5 * (nCab - 1) * dCab0                                        # cross-line position head receiver; first streamer
        rec9 = -0.5 * (nCab - 1) * dCab9                                        # cross-line position tail receiver; first streamer

        if plotIndex == 1:                                                      # forward leg
            for i in range(nSrc):
                templateNameFwd = f'Sailing Fwd-{i + 1}'                        # get suitable template name for all sources
                self.parent.survey.blockList[0].templateList[i].name = templateNameFwd

                # source fwd
                srcX, srcY = rotatePoint2D(LB, src0 + i * dSrc, azim)                                                       # rotate source location
                # self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setX(LB)                                 # Seed origin
                # self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setY(src0 + i * dSrc)                    # Seed origin
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setX(srcX)                               # Seed origin
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setY(srcY)                               # Seed origin
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setZ(srcZ)                               # Seed origin

                if fanning:
                    for j in range(nCab):
                        # we need to allow for streaer fanning; hence each streamer will have its own orientation
                        # this implies we can not 'grow' the spread to multiple streamers as a grow step in a grid

                        dRec = rec9 - rec0 + j * (dCab9 - dCab0)                                                                # cross-line cable distance
                        azi = math.degrees(math.asin(dRec / cL9)) - azim                                                        # corrresponding azimuth
                        dRGrp = gI * math.cos(math.radians(dip))

                        dXGrp = -dRGrp * math.cos(math.radians(azi))
                        dYGrp = dRGrp * math.sin(math.radians(azi))

                        recX0, recY0 = rotatePoint2D(0.0, rec0 + j * dCab0, azim)                                               # rotate source location
                        # self.parent.survey.blockList[0].templateList[i].seedList[j + 1].origin.setX(0.0)                        # Seed origin
                        # self.parent.survey.blockList[0].templateList[i].seedList[j + 1].origin.setY(rec0 + j * dCab0)           # Seed origin
                        self.parent.survey.blockList[0].templateList[i].seedList[j + 1].origin.setX(recX0)                      # Seed origin
                        self.parent.survey.blockList[0].templateList[i].seedList[j + 1].origin.setY(recY0)                      # Seed origin
                        self.parent.survey.blockList[0].templateList[i].seedList[j + 1].origin.setZ(recZ0)                      # Seed origin

                        self.parent.survey.blockList[0].templateList[i].seedList[j + 1].grid.growList[2].steps = nGrp           # nr of groups in cable
                        self.parent.survey.blockList[0].templateList[i].seedList[j + 1].grid.growList[2].increment.setX(dXGrp)  # group interval
                        self.parent.survey.blockList[0].templateList[i].seedList[j + 1].grid.growList[2].increment.setY(dYGrp)  # impact of fanning
                        self.parent.survey.blockList[0].templateList[i].seedList[j + 1].grid.growList[2].increment.setZ(dZGrp)  # normalized slant
                else:                                                                                                       # no fanning
                    dRGrp = gI * math.cos(math.radians(dip))
                    dXGrp = -dRGrp

                    recX0, recY0 = rotatePoint2D(0.0, rec0, azim)                                                           # rotate source location
                    # self.parent.survey.blockList[0].templateList[i].seedList[1].origin.setX(0.0)                            # Seed origin
                    # self.parent.survey.blockList[0].templateList[i].seedList[1].origin.setY(rec0)                           # Seed origin
                    self.parent.survey.blockList[0].templateList[i].seedList[1].origin.setX(recX0)                          # Seed origin
                    self.parent.survey.blockList[0].templateList[i].seedList[1].origin.setY(recY0)                          # Seed origin
                    self.parent.survey.blockList[0].templateList[i].seedList[1].origin.setZ(recZ0)                          # Seed origin

                    dCabX, dCabY = rotatePoint2D(0.0, dCab0, azim)                                                          # rotate cable orientation
                    self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].steps = nCab               # nr of cables in spread
                    # self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].increment.setX(0.0)        # no inline shift
                    # self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].increment.setY(dCab0)      # cable interval
                    self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].increment.setX(dCabX)      # no inline shift
                    self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].increment.setY(dCabY)      # cable interval
                    self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].increment.setZ(0.0)        # no depth shift

                    dXGrp, dYGrp = rotatePoint2D(dXGrp, 0.0, azim)                                                          # rotate group orientation
                    self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].steps = nGrp               # nr of groups in cable
                    # self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].increment.setX(dXGrp)      # group interval
                    # self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].increment.setY(0.0)        # no fanning
                    self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].increment.setX(dXGrp)      # group interval
                    self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].increment.setY(dYGrp)      # no fanning
                    self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].increment.setZ(dZGrp)      # normalized slant

        elif plotIndex == 2:                                                    # return leg
            for i in range(nSrc):
                templateNameBwd = f'Sailing Bwd-{i + 1}'                        # get suitable template name for all sources
                self.parent.survey.blockList[0].templateList[i].name = templateNameBwd

                # source bwd
                srcX, srcY = rotatePoint2D(-LB, src0 + i * dSrc, -azim)                                                     # rotate source location
                # self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setX(-LB)                                # Seed origin
                # self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setY(src0 + i * dSrc)                    # Seed origin
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setX(srcX)                               # Seed origin
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setY(srcY)                               # Seed origin
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setZ(srcZ)                               # Seed origin

                if fanning:
                    for j in range(nCab):
                        # we need to allow for streamer fanning; hence each streamer will have its own orientation
                        # this implies we can not 'grow' the spread to multiple streamers using a grow step in a grid

                        dRec = rec9 - rec0 + j * (dCab9 - dCab0)                                                                # cross-line cable distance
                        azi = math.degrees(math.asin(dRec / cL9)) - azim                                                        # corrresponding azimuth
                        dRGrp = gI * math.cos(math.radians(dip))

                        dXGrp = dRGrp * math.cos(math.radians(azi))
                        dYGrp = dRGrp * math.sin(math.radians(azi))

                        recX0, recY0 = rotatePoint2D(0.0, rec0 + j * dCab0, -azim)                                               # rotate source location
                        self.parent.survey.blockList[0].templateList[i].seedList[j + 1].origin.setX(recX0)                      # Seed origin
                        self.parent.survey.blockList[0].templateList[i].seedList[j + 1].origin.setY(recY0)                      # Seed origin
                        self.parent.survey.blockList[0].templateList[i].seedList[j + 1].origin.setZ(recZ0)                      # Seed origin

                        self.parent.survey.blockList[0].templateList[i].seedList[j + 1].grid.growList[2].steps = nGrp           # nr of groups in cable
                        self.parent.survey.blockList[0].templateList[i].seedList[j + 1].grid.growList[2].increment.setX(dXGrp)  # group interval (in opposite direction)
                        self.parent.survey.blockList[0].templateList[i].seedList[j + 1].grid.growList[2].increment.setY(dYGrp)  # no fanning (yet)
                        self.parent.survey.blockList[0].templateList[i].seedList[j + 1].grid.growList[2].increment.setZ(dZGrp)  # normalized slant
                else:                                                                                                       # no fanning
                    dRGrp = gI * math.cos(math.radians(dip))
                    dXGrp = dRGrp

                    recX0, recY0 = rotatePoint2D(0.0, rec0, -azim)                                                           # rotate source location
                    # self.parent.survey.blockList[0].templateList[i].seedList[1].origin.setX(0.0)                          # Seed origin
                    # self.parent.survey.blockList[0].templateList[i].seedList[1].origin.setY(rec0)                         # Seed origin
                    self.parent.survey.blockList[0].templateList[i].seedList[1].origin.setX(recX0)                          # Seed origin
                    self.parent.survey.blockList[0].templateList[i].seedList[1].origin.setY(recY0)                          # Seed origin
                    self.parent.survey.blockList[0].templateList[i].seedList[1].origin.setZ(recZ0)                          # Seed origin

                    dCabX, dCabY = rotatePoint2D(0.0, dCab0, -azim)                                                          # rotate cable orientation
                    self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].steps = nCab               # nr of cables in spread
                    # self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].increment.setX(0.0)      # no inline shift
                    # self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].increment.setY(dCab0)    # cable interval
                    self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].increment.setX(dCabX)      # no inline shift
                    self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].increment.setY(dCabY)      # cable interval
                    self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].increment.setZ(0.0)        # no depth shift

                    dXGrp, dYGrp = rotatePoint2D(dXGrp, 0.0, -azim)                                                          # rotate group orientation
                    self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].steps = nGrp               # nr of groups in cable
                    # self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].increment.setX(dXGrp)    # group interval (in opposite direction)
                    # self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].increment.setY(0.0)      # no fanning
                    self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].increment.setX(dXGrp)      # group interval (in opposite direction)
                    self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].increment.setY(dYGrp)      # no fanning
                    self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].increment.setZ(dZGrp)      # normalized slant

        else:
            raise NotImplementedError('unsupported plot index.')

        self.parent.survey.calcSeedData()                                       # needed for circles, spirals & well-seeds; may affect bounding box
        self.parent.survey.calcBoundingRect()                                   # (re)calculate extent of survey


# Page_3 =======================================================================
# 3. Template Properties - Enter the bin grid properties


class Page_3(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setTitle('3. Template Properties')
        self.setSubTitle('Enter the bin grid properties')

        myPrint('page 3 init')

        # create some widgets
        self.binI = QDoubleSpinBox()
        self.binX = QDoubleSpinBox()

        # set ranges
        self.binI.setRange(1.0, 10000.0)
        self.binX.setRange(1.0, 10000.0)

        # set accuracy
        self.binI.setDecimals(3)
        self.binX.setDecimals(3)

        self.chkBingridAlign = QCheckBox('Match bin grid to SPI && RPI')

        self.msg = QLineEdit('Max fold:')
        self.msg.setReadOnly(True)

        # set the page layout
        layout = QGridLayout()

        row = 0
        layout.addWidget(QLabel('<b>LOCAL</b> Bin grid definition'), row, 0, 1, 4)

        strLocal = """
        The wizard creates N streamers centered around y = 0, and starting at x = 0.<br>
        Source x-location is determined by the difference between src and rec laybacks.<br><br> 
        This implies the local origin (0, 0) is not at a bin center location.<br>
        And the bingrid centers are therefore shifted by half the bin size.
        """
        row += 1
        layout.addWidget(QLabel(strLocal), row, 0, 1, 4)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('Bin grid <b>size</b>'), row, 0, 1, 2)
        layout.addWidget(self.chkBingridAlign, row, 2, 1, 2)

        row += 1
        layout.addWidget(self.binI, row, 0)
        layout.addWidget(QLabel('Inline size [m]'), row, 1)
        layout.addWidget(self.binX, row, 2)
        layout.addWidget(QLabel('X-line size [m]'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.msg, row, 0, 1, 4)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        # create a vertical box layout widget (vbl)
        vbl = QVBoxLayout()

        # add the so far developed QGridLayout to the QVBoxLayout (layout)
        vbl.addLayout(layout)

        # insert PyQtGraph plotWidget                                           # See: https://groups.google.com/g/pyqtgraph/c/ls-9I2tHu2w
        self.plotWidget = pg.PlotWidget(background='w')
        self.plotWidget.setAspectLocked(True)                                   # setting can be changed through a toolbar
        self.plotWidget.showGrid(x=True, y=True, alpha=0.5)                     # shows the grey grid lines
        self.plotWidget.setMinimumSize(150, 150)                                # prevent excessive widget shrinking
        self.plotWidget.ctrlMenu = None                                         # get rid of 'Plot Options'
        self.plotWidget.scene().contextMenu = None                              # get rid of 'Export'

        # See: https://groups.google.com/g/pyqtgraph/c/3jWiatJPilc on how to disable context menu in a plotWidget
        # See: https://stackoverflow.com/questions/64583563/whats-the-difference-between-qtcore-signal-and-signal for signal and slot stuff

        self.zoomBar = PgToolBar('ZoomBar', plotWidget=self.plotWidget)
        self.zoomBar.actionAntiAlias.setChecked(True)                           # toggle Anti-alias on

        # add toolbar and plotwidget to the vertical box layout
        vbl.addWidget(self.zoomBar)
        vbl.addWidget(self.plotWidget)

        # set the combined layouts to become this page's layout
        self.setLayout(vbl)

        # set default values for checkboxes
        self.chkBingridAlign.setChecked(True)

        # register fields for access in other Wizard Page
        # see: https://stackoverflow.com/questions/35187729/pyqt5-double-spin-box-returning-none-value
        self.registerField('binI', self.binI, 'value')   # Inline bin size [m]
        self.registerField('binX', self.binX, 'value')   # X-line bin size [m]
        self.registerField('chkBingridAlign', self.chkBingridAlign)

        # connect signals to slots
        self.binI.textChanged.connect(self.updateParameters)
        self.binX.textChanged.connect(self.updateParameters)
        self.binI.editingFinished.connect(self.updateParameters)                # see when editing is finished for bin values
        self.binX.editingFinished.connect(self.updateParameters)

        self.chkBingridAlign.toggled.connect(self.evt_BingridAlign_toggled)

    def initializePage(self):                                                   # This function is called when the user clicks "Next" to prepare the page for display
        myPrint('initialize page 3')
        self.updateParameters()
        self.updateParentSurvey()
        self.plot()                                                             # refresh the plot

    def cleanupPage(self):                                                      # This function is called when the user clicks "Back" to leave the page, going backwards
        # note page(x) starts with a ZERO index; therefore pag(0) == Page_1
        self.parent.page(1).plot()                                              # needed to update the plot
        myPrint('cleanup of page 3')

    def plot(self):
        """plot a template"""

        self.plotWidget.plotItem.clear()
        self.plotWidget.setTitle(self.field('name'), color='b', size='12pt')

        styles = {'color': '#646464', 'font-size': '10pt'}
        self.plotWidget.setLabel('bottom', 'inline', units='m', **styles)       # shows axis at the bottom, and shows the units label
        self.plotWidget.setLabel('left', 'crossline', units='m', **styles)      # shows axis at the left, and shows the units label
        self.plotWidget.setLabel('top', 'inline', units='m', **styles)          # shows axis at the top, and shows the survey name
        self.plotWidget.setLabel('right', 'crossline', units='m', **styles)     # shows axis at the top, and shows the survey name

        self.parent.survey.paintMode = PaintMode.justPoints                     # justPoints
        self.parent.survey.lodScale = 6.0
        item = self.parent.survey

        # 3. Template Properties - Enter the bin grid properties
        self.plotWidget.plotItem.addItem(item)

        # Add a marker for the origin
        oriX = [0.0]
        oriY = [0.0]
        orig = self.plotWidget.plot(x=oriX, y=oriY, symbol='h', symbolSize=12, symbolPen=(0, 0, 0, 100), symbolBrush=(180, 180, 180, 100))

    def updateParameters(self):
        # from other pages
        dCab0 = self.field('cabSepHead')
        nSrc = self.field('nSrc')
        cabLength = self.field('cabLength')                                     # streamer length
        srcShtInt = self.field('srcShtInt')                                     # shot point interval (per cmp line)
        recGrpInt = self.field('groupInt')                                      # group interval

        foldINatural = 0.5 * cabLength / srcShtInt
        foldXNatural = 1.0

        binINatural = 0.5 * recGrpInt
        binXNatural = 0.5 * dCab0 / nSrc

        binIActual = self.field('binI')
        binXActual = self.field('binX')

        foldIActual = foldINatural * binIActual / binINatural
        foldXActual = foldXNatural * binXActual / binXNatural

        foldTActual = foldIActual * foldXActual

        foldText = f'Max fold: {foldIActual:.1f} inline & {foldXActual:.1f} x-line, {foldTActual:.1f} fold total, in {binIActual:.2f} x {binXActual:.2f} m bins'

        self.parent.survey.grid.fold = int(foldTActual * 1.5)                   # convenient point to update the max fold in the survey object

        self.msg.setText(foldText)

        if self.chkBingridAlign.isChecked():                                    # adjust the bin grid if required
            self.binI.setSingleStep(binINatural)
            self.binX.setSingleStep(binXNatural)

            stepsI = max(round(self.binI.value() / binINatural), 1)
            stepsX = max(round(self.binX.value() / binXNatural), 1)

            self.binI.setValue(stepsI * binINatural)
            self.binX.setValue(stepsX * binXNatural)
        else:
            self.binI.setSingleStep(1.0)
            self.binX.setSingleStep(1.0)

        # # note page(x) starts with a ZERO index; therefore page(0) == Page_1
        # self.parent.page(3).evt_binImin_editingFinished(plot=False)             # adjust binning parameters in next page (Page_4)
        # self.parent.page(3).evt_binIsiz_editingFinished(plot=False)
        # self.parent.page(3).evt_binXmin_editingFinished(plot=False)
        # self.parent.page(3).evt_binXsiz_editingFinished(plot=False)

        self.updateParentSurvey()
        self.plot()

    def updateParentSurvey(self):
        # adjust plot settings and populate / update the survey skeleton - Page_3

        binI = self.field('binI')
        binX = self.field('binX')

        xTicks = [200.0, binI]                                                  # tick interval, depending on zoom level
        yTicks = [200.0, binX]                                                  # tick interval, depending on zoom level

        axBottom = self.plotWidget.plotItem.getAxis('bottom')                   # get x axis
        axBottom.setTickSpacing(xTicks[0], xTicks[1])                           # set x ticks (major and minor)

        axTop = self.plotWidget.plotItem.getAxis('top')                         # get x axis
        axTop.setTickSpacing(xTicks[0], xTicks[1])                              # set x ticks (major and minor)

        axLeft = self.plotWidget.plotItem.getAxis('left')                       # get y axis
        axLeft.setTickSpacing(yTicks[0], yTicks[1])                             # set y ticks (major and minor)

        axRight = self.plotWidget.plotItem.getAxis('right')                     # get y axis
        axRight.setTickSpacing(yTicks[0], yTicks[1])                            # set y ticks (major and minor)

        self.parent.survey.output.rctOutput = QRectF()                          # don't display this in this wizard page; instead, create empty rect

        # make sure nothing 'rolls'; iterate over all blocks
        for nBlock, _ in enumerate(self.parent.survey.blockList):
            for nTemplate, _ in enumerate(self.parent.survey.blockList[0].templateList):
                self.parent.survey.blockList[nBlock].templateList[nTemplate].rollList[0].steps = 1   # nr deployments in y-direction
                self.parent.survey.blockList[nBlock].templateList[nTemplate].rollList[1].steps = 1   # nr deployments in x-direction
                # self.parent.survey.blockList[nBlock].templateList[nTemplate].rollList[2].steps = 1   # nr deployments in z-direction; 3rd roll direction not implemented (yet)

        self.parent.survey.calcSeedData()                                       # needed for circles, spirals & well-seeds; may affect bounding box
        self.parent.survey.calcBoundingRect()                                   # (re)calculate extent of survey

        self.plotWidget.setXRange(-300.0, 300.0)                                # set plot range
        self.plotWidget.setYRange(-200.0, 200.0)

        self.parent.survey.grid.binSize.setX(self.field('binI'))                # inline bin size [m]
        self.parent.survey.grid.binSize.setY(self.field('binX'))                # x-line bin size [m]

        self.parent.survey.grid.binShift.setX(self.field('binI') * 0.5)         # inline shift size [m]
        self.parent.survey.grid.binShift.setY(self.field('binX') * 0.5)         # x-line shift size [m]

        self.parent.survey.grid.stakeOrig.setX(1000)                            # set inline stake number @ grid origin
        self.parent.survey.grid.stakeOrig.setY(1000)                            # set x-line stake number @ grid origin

        self.parent.survey.grid.stakeSize.setX(self.field('binI'))              # inline stake interval
        self.parent.survey.grid.stakeSize.setY(self.field('binX'))              # x-line line interval

    def evt_BingridAlign_toggled(self):
        self.updateParameters()


# Page_4 =======================================================================
# 4. Template Properties - Enter Roll Along and Binning Area details


class Page_4(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('4. Template Properties')
        self.setSubTitle('Race-Track details, Line-Turn overhead and Survey-Size definition')

        myPrint('page 4 init')
        self.trackList = []                                                     # list of integers

        # create some widgets
        self.turnRad = QDoubleSpinBox()                                         # min turning radius
        self.turnRad.setEnabled(False)                                          # readonly
        self.turnRad.setRange(-1.0, 1_000_000.0)
        self.turnRad.setStyleSheet('QDoubleSpinBox {font: bold;} ')
        self.registerField('turnRad', self.turnRad, 'value')                    # turn radius

        self.runOut = QDoubleSpinBox()                                          # run-out (= 1/2 streamer length)
        self.runOut.setEnabled(False)                                           # readonly
        self.runOut.setRange(0.0, 1_000_000.0)

        self.vMinInner = QDoubleSpinBox()                                       # min turn radius [m]
        self.vMinInner.setRange(1.0, 1_000_000.0)
        self.vMinInner.setSingleStep(0.1)                                       # increment by km 0.1 knot
        self.vMinInner.setValue(config.vMinInner)
        self.vMinInner.textChanged.connect(self.updateParameters)
        self.registerField('vMinInner', self.vMinInner, 'value')                # min cable velocity

        self.maxDragForce = QDoubleSpinBox()                                    # max tow force [tonF]
        self.maxDragForce.setRange(0.1, 100.0)
        self.maxDragForce.setSingleStep(0.1)                                    # increment by km 0.1 tonF
        self.maxDragForce.setValue(config.maxDragForce)
        self.maxDragForce.textChanged.connect(self.updateParameters)
        self.registerField('maxDragForce', self.maxDragForce, 'value')          # max towing force

        self.velInn = QDoubleSpinBox()                                          # turning speed inner streamer
        self.velInn.setEnabled(False)                                           # readonly
        self.velInn.setRange(1.0, 1_000_000.0)                                  # turn radius [m]

        self.velOut = QDoubleSpinBox()                                          # turning speed outer streamer
        self.velOut.setEnabled(False)                                           # readonly
        self.velOut.setRange(1.0, 1_000_000.0)                                  # turn radius [m]

        self.radInn = QDoubleSpinBox()                                          # turn radius from inner streamer
        self.radInn.setEnabled(False)                                           # readonly
        self.radInn.setRange(1.0, 1_000_000.0)                                  # turn radius [m]

        self.radOut = QDoubleSpinBox()                                          # turn radius from inner streamer
        self.radOut.setEnabled(False)                                           # readonly
        self.radOut.setRange(1.0, 1_000_000.0)                                  # turn radius [m]

        self.frcInn = QDoubleSpinBox()                                          # force on inner streamer
        self.frcInn.setEnabled(False)                                           # readonly
        self.frcInn.setRange(1.0, 1_000_000.0)                                  # turn radius [m]

        self.frcOut = QDoubleSpinBox()                                          # force on outer streamer
        self.frcOut.setEnabled(False)                                           # readonly
        self.frcOut.setRange(1.0, 1_000_000.0)                                  # turn radius [m]

        self.nrSaillines = QSpinBox()                                           # required nr sail lines in survey
        self.nrSaillines.setEnabled(False)                                      # readonly

        self.noSaillines = QSpinBox()                                           # actual nr sail lines in survey
        self.noSaillines.setStyleSheet('QDoubleSpinBox {font: bold;} ')
        self.noSaillines.setEnabled(False)                                      # readonly
        self.noSaillines.setRange(0, 1_000)                                     # set some (positive) limits
        linesTip = (
            '<p><font color="red"><b>Red</b></font> when there are too few lines in the survey.'
            '<p><font color="darkorange"><b>Orange</b></font> when there are too many lines in the survey.'
            '<p><font color="forestgreen"><b>Green</b></font> when the number matches expectations.'
        )
        self.noSaillines.setToolTip(linesTip)

        self.nrLinesPerTrack = QSpinBox()                                       # nr lines per race track
        self.nrLinesPerTrack.setEnabled(False)                                  # readonly
        self.nrLinesPerTrack.setRange(1, 1_000)                                 # set some (positive) limits

        self.nrTracks = QDoubleSpinBox()                                        # nr race tracks per survey
        self.nrTracks.setEnabled(False)                                         # readonly
        self.nrTracks.setRange(1.0, 1_000.0)                                    # set some (positive) limits

        self.msg = QLineEdit('Min turn radius:')
        self.msg.setReadOnly(True)

        self.surIsiz = QDoubleSpinBox()
        self.surIsiz.setRange(1, 1000000)
        self.surIsiz.setSingleStep(1000.0)                                      # increment by km 1 km
        self.surIsiz.setValue(config.surveySizeI)
        self.surIsiz.textChanged.connect(self.updateParameters)
        self.registerField('surIsiz', self.surIsiz, 'value')                    # inline survey size

        self.surXsiz = QDoubleSpinBox()
        self.surXsiz.setRange(1, 1000000)
        self.surXsiz.setSingleStep(1000.0)                                      # increment by km 1 km
        self.surXsiz.setValue(config.surveySizeX)
        self.surXsiz.textChanged.connect(self.updateParameters)
        self.registerField('surXsiz', self.surXsiz, 'value')                    # x-line survey size

        self.lineSeries = QLineEdit()
        input_validator = QRegularExpressionValidator(QRegularExpression('[0-9 ]+'), self.lineSeries)
        self.lineSeries.setValidator(input_validator)
        self.lineSeries.textEdited.connect(self.updateSailLineOverhead)
        self.registerField('lineSeries', self.lineSeries)                       # series of lines per race track

        # needed to prevent that the edit control consumes al available extra space when expanding, for no obvious reasons...
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.lineSeries.setSizePolicy(sizePolicy)

        self.lineSeriesLabel = QLabel('<b>list</b> of sail lines/track')
        self.nsl2Label = QLabel('<b>Sail lines in survey</b> [#]')
        self.nsl2Label.setToolTip(linesTip)

        self.teardrops = QDoubleSpinBox()
        self.teardrops.setEnabled(False)                                  # readonly
        self.teardrops.setRange(-1.0, 1_000_000.0)

        self.xLineSail = QDoubleSpinBox()
        self.xLineSail.setEnabled(False)                                  # readonly
        self.xLineSail.setRange(-1.0, 1_000_000.0)

        self.turn180 = QDoubleSpinBox()
        self.turn180.setEnabled(False)                                  # readonly
        self.turn180.setRange(-1.0, 1_000_000.0)

        self.runIns = QDoubleSpinBox()
        self.runIns.setEnabled(False)                                  # readonly
        self.runIns.setRange(-1.0, 1_000_000.0)

        self.turnOverhead = QDoubleSpinBox()
        self.turnOverhead.setStyleSheet('QDoubleSpinBox {font: bold;} ')
        self.turnOverhead.setRange(-1.0, 1_000_000.0)
        self.turnOverhead.setEnabled(False)                                  # readonly

        self.totalTurns = QDoubleSpinBox()
        self.totalTurns.setEnabled(False)                                  # readonly
        self.totalTurns.setRange(-1.0, 1_000_000.0)

        self.totalPrime = QDoubleSpinBox()
        self.totalPrime.setStyleSheet('QDoubleSpinBox {font: bold;} ')
        self.totalPrime.setEnabled(False)                                  # readonly
        self.totalPrime.setRange(-1.0, 1_000_000.0)

        # set the page layout
        layout = QGridLayout()

        row = 0
        turnLabel = QLabel("Factors affecting the vessel's minimum <b>turning radius</b>")
        layout.addWidget(turnLabel, row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('Minimum streamer <b>speed</b> [kn] and maximum <b>tow force</b> [tonF] in water'), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.vMinInner, row, 0)
        layout.addWidget(QLabel('Min speed [kn]'), row, 1)
        layout.addWidget(self.maxDragForce, row, 2)
        layout.addWidget(QLabel('Max force [tonF]'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('Speed during line turns for <b>inner</b> and <b>outer</b> streamers '), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.velInn, row, 0)
        layout.addWidget(QLabel('Inner speed [kn]'), row, 1)
        layout.addWidget(self.velOut, row, 2)
        layout.addWidget(QLabel('Outer speed [kn]'), row, 3)

        row += 1
        layout.addWidget(QLabel('Towing force during line turns for <b>inner</b> and <b>outer</b> streamers'), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.frcInn, row, 0)
        layout.addWidget(QLabel('Inner force [tonF]'), row, 1)
        layout.addWidget(self.frcOut, row, 2)
        layout.addWidget(QLabel('Outer force [tonF]'), row, 3)

        row += 1
        layout.addWidget(QLabel('Line turn radius from limits <b>inner</b> and <b>outer</b> streamers '), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.radInn, row, 0)
        layout.addWidget(QLabel('From <b>inner</b> streamer [m]'), row, 1)
        layout.addWidget(self.radOut, row, 2)
        layout.addWidget(QLabel('From <b>outer</b> streamer [m]'), row, 3)

        row += 1
        layout.addWidget(self.turnRad, row, 0)
        layout.addWidget(QLabel('<b>Min turn radius</b> [m]'), row, 1)
        layout.addWidget(self.msg, row, 2, 1, 2)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Size</b> of full fold <b>survey area</b>, run-outs, nr sail lines and <b><i>optimal</i></b>  nr lines per race track'), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.surIsiz, row, 0)
        layout.addWidget(QLabel('FF inline size [m]'), row, 1)
        layout.addWidget(self.surXsiz, row, 2)
        layout.addWidget(QLabel('Crossline size [m]'), row, 3)

        row += 1
        layout.addWidget(self.runOut, row, 0)
        layout.addWidget(QLabel('Run-out length [m]'), row, 1)
        layout.addWidget(self.nrSaillines, row, 2)
        layout.addWidget(QLabel('<b>Sail lines</b> in survey [#]'), row, 3)

        row += 1
        layout.addWidget(self.nrLinesPerTrack, row, 0)
        layout.addWidget(QLabel('lines/race track [#]'), row, 1)
        layout.addWidget(self.nrTracks, row, 2)
        layout.addWidget(QLabel('Race tracks in survey'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>List the series of race tracks</b>, by their number of sail lines, separated by a space'), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('Note: apart from the <b>final</b> race track, all sail line numbers must be <b>odd</b>'), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.lineSeries, row, 0)
        layout.addWidget(self.lineSeriesLabel, row, 1)
        layout.addWidget(self.noSaillines, row, 2)
        layout.addWidget(self.nsl2Label, row, 3)

        row += 1
        layout.addWidget(self.turnOverhead, row, 0)
        layout.addWidget(QLabel('<b>% Line turn overhead</b>'), row, 1)
        layout.addWidget(self.totalPrime, row, 2)
        layout.addWidget(QLabel('<b>Total km prime lines</b>'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Detailed line turn information</b>'), row, 0, 1, 2)
        layout.addWidget(self.totalTurns, row, 2)
        layout.addWidget(QLabel('Total turn effort [km]'), row, 3)

        row += 1
        layout.addWidget(self.turn180, row, 0)
        layout.addWidget(QLabel('180° turns [km]'), row, 1)
        layout.addWidget(self.runIns, row, 2)
        layout.addWidget(QLabel('run-ins [km]'), row, 3)

        row += 1
        layout.addWidget(self.teardrops, row, 0)
        layout.addWidget(QLabel('Tear drops [km]'), row, 1)
        layout.addWidget(self.xLineSail, row, 2)
        layout.addWidget(QLabel('x-line sailing [km]'), row, 3)

        self.setLayout(layout)

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        myPrint('initialize page 4')

        self.updateParameters()
        self.updateSailLineOverhead()

    def updateParameters(self):
        # Page_4. need to work out ideal racetrack width and nr of tracks and sail lines in survey
        cL = self.field('cabLength')                                            # streamer length
        dCab0 = self.field('cabSepHead')
        nCab = self.field('nCab')
        surXsiz = self.field('surXsiz')
        vTurn = self.field('vTurn')                                             # Vessel line turn speed (from page 1)
        vMinInner = self.field('vMinInner')
        maxDragForce = self.field('maxDragForce')

        sailLineInterval = 0.5 * nCab * dCab0                                   # sail line interval
        nrSaillines = math.ceil(surXsiz / sailLineInterval)                     # required nr sail lines in survey
        self.nrSaillines.setValue(nrSaillines)

        spreadWidth = (nCab - 1) * dCab0
        innerTurningRadius = 0.5 * vTurn * spreadWidth / (vTurn - vMinInner)    # speed in knot or m/s does not matter for their ratio

        self.runOut.setValue(0.5 * cL)

        wetSurface = math.pi * cL * config.cabDiameter                          # wet area per streamer
        dragPerMeter = 0.5 * wetSurface * config.swDensity * config.cDrag
        a = 1.0 - tonForceToNewton(maxDragForce) / (dragPerMeter * knotToMeterperSec(vTurn) ** 2.0)
        b = spreadWidth
        c = 0.25 * spreadWidth**2.0
        outerTurningRadius = (-1.0 * b - math.sqrt(b**2 - 4 * a * c)) / (2 * a)

        self.radInn.setValue(innerTurningRadius)
        self.radOut.setValue(outerTurningRadius)

        # rounded up minimum turning radius, constraint by inner- and outer streamers
        vesselTurningRadius = max(500.0, 10.0 * math.ceil(0.1 * max(innerTurningRadius, outerTurningRadius)))
        self.turnRad.setValue(vesselTurningRadius)

        velInn = (1.0 - 0.5 * spreadWidth / vesselTurningRadius) * vTurn
        self.velInn.setValue(velInn)

        velOut = (1.0 + 0.5 * spreadWidth / vesselTurningRadius) * vTurn
        self.velOut.setValue(velOut)

        innerStreamerDrag = newtonToTonForce(dragPerMeter * knotToMeterperSec(velInn) ** 2)
        self.frcInn.setValue(innerStreamerDrag)

        outerStreamerDrag = newtonToTonForce(dragPerMeter * knotToMeterperSec(velOut) ** 2)
        self.frcOut.setValue(outerStreamerDrag)

        if innerTurningRadius > outerTurningRadius:
            turnText = 'Limited by min speed inner streamer'
        else:
            turnText = 'Limited by max force on outer streamer'

        self.msg.setText(turnText)

        nrLinesForward = round(vesselTurningRadius / sailLineInterval + 0.5) * 2 + 1
        nrLinesBackward = nrLinesForward - 1

        nrLinesPerTrack = nrLinesForward + nrLinesBackward
        self.nrLinesPerTrack.setValue(nrLinesPerTrack)

        nrTracks = surXsiz / (sailLineInterval * nrLinesPerTrack)
        self.nrTracks.setValue(nrTracks)

        # create basic tracklist
        self.trackList = []
        while sum(self.trackList) < nrSaillines:
            self.trackList.append(nrLinesPerTrack)

        self.lineSeries.setText(intListToString(self.trackList))
        self.noSaillines.setValue(sum(self.trackList))

    def updateSailLineOverhead(self):
        # work out sequence of saillines per race track

        trackList = stringToIntList(self.lineSeries.text())
        noSaillines = sum(trackList)

        self.noSaillines.setValue(noSaillines)

        nTracks = len(trackList)

        error = False
        if nTracks > 1:                                                         # need at least 2 tracks to restrict the first track
            for track in trackList[:-1]:                                        # ignore last entry
                if even(track):                                                 # not allowed
                    error = True
                    break
        if error:
            self.lineSeries.setStyleSheet('QLineEdit {color:red; background-color:lightblue;}')
            self.lineSeriesLabel.setStyleSheet('QLabel {color:red}')
        else:
            self.lineSeries.setStyleSheet('QLineEdit {color:black; background-color:white;}')
            self.lineSeriesLabel.setStyleSheet('QLabel {color:black}')

        nrSaillines = self.nrSaillines.value()
        if noSaillines < nrSaillines:                                           # required < actual
            self.noSaillines.setStyleSheet('QSpinBox {font:bold; color:red} ')
            self.nsl2Label.setStyleSheet('QLabel {color:red}')
        elif nrSaillines < noSaillines:                                         # actual > required
            self.noSaillines.setStyleSheet('QSpinBox {font:bold; color:darkorange} ')
            self.nsl2Label.setStyleSheet('QLabel {color:darkorange}')
        else:
            # self.noSaillines.setStyleSheet('QSpinBox {font:bold; color:dimgrey} ')
            # self.nsl2Label.setStyleSheet('QLabel {color:black}')                # actual == required
            self.noSaillines.setStyleSheet('QSpinBox {font:bold; color:forestgreen} ')
            self.nsl2Label.setStyleSheet('QLabel {color:forestgreen}')                # actual == required

        cL = self.field('cabLength')                                            # streamer length
        FF = self.field('surIsiz')                                              # bin area inline size
        totalPrimeKm = 0.001 * noSaillines * (FF + 0.5 * cL)                    # sailline effort in km
        totalRuninKm = 0.001 * noSaillines * 0.5 * cL

        turnRadius = self.field('turnRad')                                      # turn radius
        dCab0 = self.field('cabSepHead')
        nCab = self.field('nCab')
        saillineInterval = 0.5 * nCab * dCab0

        if noSaillines == 0:
            self.totalTurns.setValue(0.0)
            self.totalPrime.setValue(0.0)
            self.turn180.setValue(0.0)
            self.teardrops.setValue(0.0)
            self.xLineSail.setValue(0.0)
            self.runIns.setValue(0.0)
            self.turnOverhead.setValue(0.0)
        elif error:
            self.totalTurns.setValue(-1.0)
            self.totalPrime.setValue(-1.0)
            self.turn180.setValue(-1.0)
            self.teardrops.setValue(-1.0)
            self.xLineSail.setValue(-1.0)
            self.runIns.setValue(-1.0)
            self.turnOverhead.setValue(-1.0)
        else:
            self.totalPrime.setValue(totalPrimeKm)
            self.runIns.setValue(totalRuninKm)

            lineturnTotal = 0.0
            crosslineTotal = 0.0
            teardropTotal = 0.0

            if nTracks > 0:                                                     # need at least 2 tracks to restrict the first track
                for lines in trackList[:-1]:                                    # ignore last entry
                    lineturn, crossline, teardrop = lineturnDetour(turnRadius, saillineInterval, lines)
                    lineturnTotal += lineturn
                    crosslineTotal += crossline
                    teardropTotal += teardrop

                lines = trackList[-1]                                           # use the  last entry
                lineturn, crossline, teardrop = lineturnDetour(turnRadius, saillineInterval, lines, final=True)
                lineturnTotal += lineturn
                crosslineTotal += crossline
                teardropTotal += teardrop

                lineturnTotal *= 0.001
                teardropTotal *= 0.001
                crosslineTotal *= 0.001

                cL = self.field('cabLength')                                    # streamer length
                FF = self.field('surIsiz')                                      # bin area inline size
                totalPrimeKm = 0.001 * noSaillines * (FF + 0.5 * cL)            # sailline effort in km, including run-outs
                totalRuninKm = 0.001 * noSaillines * 0.5 * cL
                totalTurns = lineturnTotal + teardropTotal + crosslineTotal + totalRuninKm

                self.turn180.setValue(lineturnTotal)
                self.teardrops.setValue(teardropTotal)
                self.xLineSail.setValue(crosslineTotal)
                self.totalTurns.setValue(totalTurns)
                self.turnOverhead.setValue(100.0 * totalTurns / totalPrimeKm)

        self.completeChanged.emit()

    def cleanupPage(self):                                                      # needed to update previous page(s)
        myPrint('cleanup of page 4')

        # added 19/06/2024
        self.parent.survey.output.rctOutput = QRectF()                          # don't display this in 'earlier' wizard pages; instead, create empty rect

        # # make sure nothing 'rolls'; iterate over all blocks
        # for nBlock, _ in enumerate(self.parent.survey.blockList):
        #     for nTemplate, _ in enumerate(self.parent.survey.blockList[0].templateList):
        #         self.parent.survey.blockList[nBlock].templateList[nTemplate].rollList[0].steps = 1   # nr deployments in y-direction
        #         self.parent.survey.blockList[nBlock].templateList[nTemplate].rollList[1].steps = 1   # nr deployments in x-direction
        #         # self.parent.survey.blockList[nBlock].templateList[nTemplate].rollList[2].steps = 1   # nr deployments in z-direction; 3rd roll direction not implemented (yet)

        # self.parent.survey.calcSeedData()                                       # needed for circles, spirals & well-seeds; may affect bounding box
        # self.parent.survey.calcBoundingRect()                                   # (re)calculate extent of survey ignoring rolling along

        # note page(x) starts with a ZERO index; therefore page(0) == Page_1 and page(2) == Page_3
        # self.parent.page(2).updateParentSurvey()                                # (re)center single spread, may be shifted inline due to origin shift
        # self.parent.page(2).plot()                                              # needed to update the plot

    def isComplete(self):
        #  See: https://doc.qt.io/archives/qq/qq22-qwizard.html#validatebeforeitstoolate
        lineSeries = self.field('lineSeries')                                   # from edit control
        trackList = stringToIntList(lineSeries)
        nrSailLines = sum(trackList)

        if nrSailLines == 0:
            return False
        else:
            return True


# Page_5 =======================================================================
# 5. Template Properties - Binning extent in survey area


class Page_5(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('5. Template Properties')
        self.setSubTitle('Binning extent in survey area')

        myPrint('page 5 init')

        # Add some widgets
        self.binImin = QDoubleSpinBox()
        self.binImin.setRange(-1_000_000, 1_000_000)
        self.registerField('binImin', self.binImin, 'value')                    # bin area x-origin

        self.binIsiz = QDoubleSpinBox()
        self.binIsiz.setRange(0.0, 1_000_000)
        self.binIsiz.setValue(2000.0)
        self.registerField('binIsiz', self.binIsiz, 'value')                    # bin area inline size

        self.binXmin = QDoubleSpinBox()
        self.binXmin.setRange(-1_000_000, 1_000_000)
        self.registerField('binXmin', self.binXmin, 'value')                    # bin area y-origin

        self.binXsiz = QDoubleSpinBox()
        self.binXsiz.setRange(0.0, 1_000_000)
        self.binXsiz.setValue(2000.0)
        self.registerField('binXsiz', self.binXsiz, 'value')                    # bin area x-line size

        self.binImin.editingFinished.connect(self.evt_binImin_editingFinished)
        self.binIsiz.editingFinished.connect(self.evt_binIsiz_editingFinished)
        self.binXmin.editingFinished.connect(self.evt_binXmin_editingFinished)
        self.binXsiz.editingFinished.connect(self.evt_binXsiz_editingFinished)

        self.chkShowSrc = QCheckBox('Source areas')
        self.chkShowRec = QCheckBox('Receiver areas')
        self.chkShowCmp = QCheckBox('CMP areas')
        self.chkShowBin = QCheckBox('Binning area')

        self.chkShowSrc.setChecked(True)
        self.chkShowRec.setChecked(True)
        self.chkShowCmp.setChecked(True)
        self.chkShowBin.setChecked(True)

        self.chkShowSrc.stateChanged.connect(self.updatePaintedAreas)
        self.chkShowRec.stateChanged.connect(self.updatePaintedAreas)
        self.chkShowCmp.stateChanged.connect(self.updatePaintedAreas)
        self.chkShowBin.stateChanged.connect(self.updatePaintedAreas)

        # set the page layout
        layout = QGridLayout()

        row = 0
        layout.addWidget(QLabel('<b>Start corner</b> of binning area'), row, 0, 1, 2)
        layout.addWidget(QLabel('<b>Size</b> of binning area'), row, 2, 1, 2)

        row += 1
        layout.addWidget(self.binImin, row, 0)
        layout.addWidget(QLabel('Inline origin [m]'), row, 1)
        layout.addWidget(self.binIsiz, row, 2)
        layout.addWidget(QLabel('Inline size [m]'), row, 3)

        row += 1
        layout.addWidget(self.binXmin, row, 0)
        layout.addWidget(QLabel('X-line origin [m]'), row, 1)
        layout.addWidget(self.binXsiz, row, 2)
        layout.addWidget(QLabel('X-line size [m]'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Show or hide</b> source, receiver, CMP and binning areas'), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.chkShowSrc, row, 0)
        layout.addWidget(self.chkShowRec, row, 1)
        layout.addWidget(self.chkShowCmp, row, 2)
        layout.addWidget(self.chkShowBin, row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        # create a vertical box layout widget (vbl)
        vbl = QVBoxLayout()

        # add the so far developed QGridLayout to the QVBoxLayout (layout)
        vbl.addLayout(layout)

        # insert PyQtGraph plotWidget                                           # See: https://groups.google.com/g/pyqtgraph/c/ls-9I2tHu2w
        self.plotWidget = pg.PlotWidget(background='w')
        self.plotWidget.setAspectLocked(True)                                   # setting can be changed through a toolbar
        self.plotWidget.showGrid(x=True, y=True, alpha=0.5)                     # shows the grey grid lines
        self.plotWidget.setMinimumSize(150, 150)                                # prevent excessive widget shrinking
        self.plotWidget.ctrlMenu = None                                         # get rid of 'Plot Options'
        self.plotWidget.scene().contextMenu = None                              # get rid of 'Export'

        self.zoomBar = PgToolBar('ZoomBar', plotWidget=self.plotWidget)
        self.zoomBar.actionAntiAlias.setChecked(True)                           # toggle Anti-alias on

        # add toolbar and plotwidget to the vertical box layout
        vbl.addWidget(self.zoomBar)
        vbl.addWidget(self.plotWidget)

        # set the combined layouts to become this page's layout
        self.setLayout(vbl)

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        myPrint('initialize page 5')

        lineSeries = self.field('lineSeries')                                   # text from edit control
        trackList = stringToIntList(lineSeries)                                 # turn numbers into int list
        nrSailLines = sum(trackList)                                            # get total nr of saillines

        dCab0 = self.field('cabSepHead')
        nCab = self.field('nCab')
        sailLineInterval = 0.5 * nCab * dCab0                                   # sail line interval
        surveyWidth = nrSailLines * sailLineInterval                            # calc survey width

        cL = self.field('cabLength')                                            # streamer length
        FF = self.field('surIsiz') + 0.5 * cL                                   # bin area inline size

        self.binImin.setValue(0.5 * FF - 1000.0)
        self.binXmin.setValue(0.5 * surveyWidth - 1000.0)

        self.updateParentSurvey()
        self.plot()

    def cleanupPage(self):                                                      # needed to update previous page
        myPrint('cleanup of page 5')

    def updateParentSurvey(self):
        # build up total survey object from scratch - Page_5

        lineSeries = self.field('lineSeries')                                   # list from edit control
        trackList = stringToIntList(lineSeries)                                 # list converted to integers
        trackCount = len(trackList)                                             # nr of entries in list
        # nrSailLines = sum(trackList)                                            # total nr of saillines in survey

        nSrc = self.field('nSrc')
        nCab = self.field('nCab')

        # Create a new survey skeleton, so we can simply update survey properties, without having to instantiate the underlying classes
        # in case no streamer fanning is required (parallel streamers), we just need a single receiver-seed per template
        dCab0 = self.field('cabSepHead')
        dCab9 = self.field('cabSepTail')

        # a marine survey cconsists of a number of race tracks, each with a number of sail lines going forward, and a number of sail lines going backward
        # the lines going forward and those going backward are represented by a single block in Roll
        # therefore; with n race tracks in a survey, the survey would contain 2n blocks 0, 2, 4, ... going forwards and 1, 3, 5, ... going backwards
        # in practice, we want to reduce the number of sailline reversals. This can be achieved by flipping the direction of the even race tracks

        # block number  direction   flipped ?   final direction
        ################################################
        #       0       forwards        no      forwards
        ################################################
        #       1       backward        no      backward
        #       2       forwards        yes     backward
        ################################################
        #       3       backward        yes     forwards
        #       4       forwards        no      forwards
        ################################################
        #       5       backward        no      backward
        #       6       forwards        yes     backward
        ################################################
        #       7       backward        yes     forwards

        # so by flipping the direction of the even race tracks, we can create a survey with 'paired' forward and backward sailing
        # this reduces the number of sail line reversals by ~ 2, thereby reducing the amount of striping in the data

        # at present feathering is implemented partially: streamers are feathered, but the vessel isn't crabbing accordingly

        fanning = True if dCab9 != dCab0 else False
        if fanning:
            self.parent.survey.createBasicSkeleton(nBlocks=trackCount * 2, nTemplates=nSrc, nSrcSeeds=1, nRecSeeds=nCab)    # setup multiple blocks with their templates and one seed per streamer
        else:
            self.parent.survey.createBasicSkeleton(nBlocks=trackCount * 2, nTemplates=nSrc, nSrcSeeds=1, nRecSeeds=1)       # setup multiple blocks with their templates and one seed for all streamers

        sailLineInt = 0.5 * nCab * dCab0                                        # sail line interval

        sL = self.field('srcLayback')
        rL = self.field('cabLayback')
        LB = rL - sL                                                            # Lay Back; source location relative to receiver location

        cL = self.field('cabLength')                                            # streamer length
        gI = self.field('groupInt')                                             # group interval
        nGrp = round(cL / gI)                                                   # nr groups per streamer

        recZ0 = -self.field('cabDepthHead')
        recZ9 = -self.field('cabDepthTail')
        dZCab = recZ9 - recZ0                                                   # depth increase along the cable(s)
        dZGrp = -gI / cL * dZCab                                                # depth increase along a group; independent of azimuth (i.e. from fanning and currents)

        dSrcY = self.field('srcSeparation')                                     # source separation in cross-line direction
        srcZ = -self.field('srcDepth')                                          # source depth
        srcShtInt = self.field('srcShtInt')                                     # shot point interval (per cmp line)

        FF = self.field('surIsiz')                                              # bin area full fold inline size
        RO = 0.5 * cL                                                           # run out
        nSht = round((FF + RO) / srcShtInt)                                     # nr of shot points per source array
        PI = self.field('srcPopInt')                                            # pop interval (subsequent firings of any of the sources)

        azim = self.field('aFeat')                                              # streamer feather angle

        dip = math.degrees(math.asin(dZCab / cL))                               # cable dip angle, due to slant
        cL9 = cL * math.cos(math.radians(dip))                                  # cable length reduced by slant

        srcY0 = -0.5 * (nSrc - 1) * dSrcY                                       # cross-line position; first source
        recY0 = -0.5 * (nCab - 1) * dCab0                                       # cross-line position; first streamer @ head receiver
        recY9 = -0.5 * (nCab - 1) * dCab9                                       # cross-line position; first streamer @ tail receiver

        trackNo = 0
        for i in range(0, trackCount * 2, 2):                                   # iterate over all blocks in steps of two; for forward & backward sailing

            # blocks 0, 2, 4, ... = moving forward block [i]
            # blocks 1, 3, 5, ... = moving back in block [i + 1]
            # 'flip' condition will reverse direction. See below

            linesPerTrack = trackList[trackNo]                                  # the nr of lines in this race track (need to divide i by 2)
            nrLinesFwd = math.ceil(0.5 * linesPerTrack)                         # the nr of lines sailing forward in this race track

            nrLinesBwd = math.floor(0.5 * linesPerTrack)                        # the nr of lines sailing backward in this race track
            nrLinesOff = sum(trackList[0:trackNo])                              # the nr of lines PRIOR to the lines in this race track (=offset)

            blkOffFwd = nrLinesOff * sailLineInt                                # crossline starting point of forward sail lines
            blkOffBwd = blkOffFwd + nrLinesFwd * sailLineInt                    # crossline starting point of backward sail lines

            flip = trackNo % 2 == 1                                             # forward/backward direction of odd race tracks needs to be flipped
            trackNo += 1                                                        # make it ready for next iteration of i (=trackCount)

            self.parent.survey.blockList[i + 0].name = f'Track-{trackNo}a'      # name the block after its role in a race track
            self.parent.survey.blockList[i + 1].name = f'Track-{trackNo}b'      # name the block after its role in a race track

            for j in range(nSrc):                                               # iterate over templates; each template contains 1 source point
                # for every increment in j, the source point is moved by dSrcY in crossline direction, and moved by PopInt in inline direction

                # iterate over all templates (= sources), start with sailing FORWARD in block i = 0
                if flip:
                    nameFwd = 'Sailing Bwd'
                    nameBwd = 'Sailing Fwd'
                    PopInt = -self.field('srcPopInt')
                    RolInt = -self.field('srcShtInt')                           # shot point interval (per cmp line)
                    SrcFwdX0 = FF - 1.0 * LB - PI
                    SrcBwdX0 = 0.0
                    RecFwdX0 = FF + 1.0 * LB - PI
                    RecBwdX0 = 0.0
                    RecFwdDx = 1.0
                    RecBwdDx = -1.0
                else:
                    nameFwd = 'Sailing Fwd'
                    nameBwd = 'Sailing Bwd'
                    PopInt = self.field('srcPopInt')                            # pop interval (subsequent firings)
                    RolInt = self.field('srcShtInt')                            # shot point interval (per cmp line)
                    SrcFwdX0 = 0.0
                    SrcBwdX0 = FF - 1.0 * LB - PI
                    RecFwdX0 = 0.0
                    RecBwdX0 = FF + 1.0 * LB - PI
                    RecFwdDx = -1.0
                    RecBwdDx = 1.0

                self.parent.survey.blockList[i].templateList[j].name = f'{nameFwd}-{j + 1}'                                 # get suitable template name for all sources

                # source seed fwd sailing
                dX, dY = rotatePoint2D(LB, srcY0 + j * dSrcY, azim * RecBwdDx)                                              # rotate source seed location, based on layback, source y-location and azimuth
                # self.parent.survey.blockList[i].templateList[j].seedList[0].origin.setX(SrcFwdX0 + j * PopInt)              # The x-origin is shifted by the pop interval between source arrays
                # self.parent.survey.blockList[i].templateList[j].seedList[0].origin.setY(blkOffFwd + srcY0 + j * dSrcY)      # The y-origin is shifted by the x-line interval between source arrays
                self.parent.survey.blockList[i].templateList[j].seedList[0].origin.setX(dX + SrcFwdX0 + j * PopInt)         # The x-origin is shifted by the pop interval between source arrays
                self.parent.survey.blockList[i].templateList[j].seedList[0].origin.setY(dY + blkOffFwd)                     # The y-origin is shifted by the x-line interval between source arrays
                self.parent.survey.blockList[i].templateList[j].seedList[0].origin.setZ(srcZ)                               # The z-origin is simply the source depth

                # roll along in crossline direction
                self.parent.survey.blockList[i].templateList[j].rollList[0].steps = nrLinesFwd                              # nr deployments in crossline-direction
                self.parent.survey.blockList[i].templateList[j].rollList[0].increment.setX(0.0)                             # vertical move, hence dX = 0
                self.parent.survey.blockList[i].templateList[j].rollList[0].increment.setY(sailLineInt)                     # vertical move to the extennt of the sailline interval

                # roll along in inline direction
                self.parent.survey.blockList[i].templateList[j].rollList[1].steps = nSht                                    # nr deployments in inline-direction
                self.parent.survey.blockList[i].templateList[j].rollList[1].increment.setX(RolInt)                          # each source progresses by the shot interval
                self.parent.survey.blockList[i].templateList[j].rollList[1].increment.setY(0.0)                             # horizontal movement, hence dY = 0

                if fanning:                                                                                                 # this all for streamer fanning; hence each streamer will have its own orientation
                    for k in range(nCab):                                                                                   # iterate over all deployed cables; create one seed per cable

                        # we need to allow for streamer fanning; hence each streamer will have its own orientation
                        # this implies we can not 'grow' the spread to multiple streamers as a grow step in a grid

                        dRec = recY9 - recY0 + k * (dCab9 - dCab0)                                                          # cross-line cable distance
                        azi = math.degrees(math.asin(dRec / cL9)) - azim                                                    # corrresponding azimuth
                        dRGrp = gI * math.cos(math.radians(dip))

                        dXGrp = dRGrp * math.cos(math.radians(azi)) * RecFwdDx
                        dYGrp = dRGrp * math.sin(math.radians(azi))

                        dX, dY = rotatePoint2D(0.0, recY0 + k * dCab0, azim * RecBwdDx)                                             # rotate receiver seed origin
                        # self.parent.survey.blockList[i].templateList[j].seedList[k + 1].origin.setX(RecFwdX0 + j * PopInt)          # Seed origin
                        # self.parent.survey.blockList[i].templateList[j].seedList[k + 1].origin.setY(blkOffFwd + recY0 + k * dCab0)  # Seed origin
                        self.parent.survey.blockList[i].templateList[j].seedList[k + 1].origin.setX(dX + RecFwdX0 + j * PopInt)     # Seed origin
                        self.parent.survey.blockList[i].templateList[j].seedList[k + 1].origin.setY(dY + blkOffFwd)                 # Seed origin
                        self.parent.survey.blockList[i].templateList[j].seedList[k + 1].origin.setZ(recZ0)                          # Seed origin

                        self.parent.survey.blockList[i].templateList[j].seedList[k + 1].grid.growList[2].steps = nGrp               # nr of groups in cable
                        self.parent.survey.blockList[i].templateList[j].seedList[k + 1].grid.growList[2].increment.setX(dXGrp)      # group interval
                        self.parent.survey.blockList[i].templateList[j].seedList[k + 1].grid.growList[2].increment.setY(dYGrp)      # impact of fanning
                        self.parent.survey.blockList[i].templateList[j].seedList[k + 1].grid.growList[2].increment.setZ(dZGrp)      # normalized slant
                else:
                    # no allowance for streamer fanning; all streamers will have the same orientation
                    # this implies we can 'grow' the spread to multiple streamers as a single grow step in a grid

                    dRGrp = gI * math.cos(math.radians(dip))
                    dXGrp = dRGrp * RecFwdDx

                    dX, dY = rotatePoint2D(0.0, recY0, azim * RecBwdDx)                                                     # rotate receiver seed origin for all streamers
                    # self.parent.survey.blockList[i].templateList[j].seedList[1].origin.setX(RecFwdX0 + j * PopInt)          # Seed origin
                    # self.parent.survey.blockList[i].templateList[j].seedList[1].origin.setY(blkOffFwd + recY0)              # Seed origin
                    self.parent.survey.blockList[i].templateList[j].seedList[1].origin.setX(dX + RecFwdX0 + j * PopInt)     # Seed origin
                    self.parent.survey.blockList[i].templateList[j].seedList[1].origin.setY(dY + blkOffFwd)                 # Seed origin
                    self.parent.survey.blockList[i].templateList[j].seedList[1].origin.setZ(recZ0)                          # Seed origin

                    dCabX, dCabY = rotatePoint2D(0.0, dCab0, azim * RecBwdDx)                                           # rotate cable orientation
                    self.parent.survey.blockList[i].templateList[j].seedList[1].grid.growList[1].steps = nCab           # nr cable in spread
                    # self.parent.survey.blockList[i].templateList[j].seedList[1].grid.growList[1].increment.setX(0.0)    # no inline shift
                    # self.parent.survey.blockList[i].templateList[j].seedList[1].grid.growList[1].increment.setY(dCab0)  # cable interval
                    self.parent.survey.blockList[i].templateList[j].seedList[1].grid.growList[1].increment.setX(dCabX)  # no inline shift
                    self.parent.survey.blockList[i].templateList[j].seedList[1].grid.growList[1].increment.setY(dCabY)  # cable interval
                    self.parent.survey.blockList[i].templateList[j].seedList[1].grid.growList[1].increment.setZ(0.0)    # no vertical shift

                    dXGrp, dYGrp = rotatePoint2D(dXGrp, 0.0, azim * RecBwdDx)                                           # rotate group orientation
                    self.parent.survey.blockList[i].templateList[j].seedList[1].grid.growList[2].steps = nGrp           # nr of groups in cable
                    # self.parent.survey.blockList[i].templateList[j].seedList[1].grid.growList[2].increment.setX(dXGrp)  # group interval
                    # self.parent.survey.blockList[i].templateList[j].seedList[1].grid.growList[2].increment.setY(0.0)    # no fanning
                    self.parent.survey.blockList[i].templateList[j].seedList[1].grid.growList[2].increment.setX(dXGrp)  # group interval
                    self.parent.survey.blockList[i].templateList[j].seedList[1].grid.growList[2].increment.setY(dYGrp)  # no fanning
                    self.parent.survey.blockList[i].templateList[j].seedList[1].grid.growList[2].increment.setZ(dZGrp)  # normalized slant

                #####################################################################################################################################################################
                # iterate over all templates (= sources), continue with sailing BACKWARD in block i + 1  ############################################################################
                # so i now becomes i + 1 and j is still the same                                         ############################################################################
                #####################################################################################################################################################################

                self.parent.survey.blockList[i + 1].templateList[j].name = f'{nameBwd}-{j + 1}'                             # get suitable template name for all sources

                # source seed bwd sailing
                dX, dY = rotatePoint2D(LB, srcY0 + j * dSrcY, -azim * RecBwdDx)                                             # rotate source seed location, based on layback, source y-location and azimuth
                # self.parent.survey.blockList[i + 1].templateList[j].seedList[0].origin.setX(SrcBwdX0 - j * PopInt)          # The x-origin is shifted by the pop interval between source arrays
                # self.parent.survey.blockList[i + 1].templateList[j].seedList[0].origin.setY(blkOffBwd + srcY0 + j * dSrcY)  # The y-origin is shifted by the x-line interval between source arrays
                self.parent.survey.blockList[i + 1].templateList[j].seedList[0].origin.setX(dX + SrcBwdX0 - j * PopInt)     # The x-origin is shifted by the pop interval between source arrays
                self.parent.survey.blockList[i + 1].templateList[j].seedList[0].origin.setY(dY + blkOffBwd)                 # The y-origin is shifted by the x-line interval between source arrays
                self.parent.survey.blockList[i + 1].templateList[j].seedList[0].origin.setZ(srcZ)                           # The z-origin is simply the source depth

                # roll along in crossline direction
                self.parent.survey.blockList[i + 1].templateList[j].rollList[0].steps = nrLinesBwd                          # nr deployments in crossline-direction
                self.parent.survey.blockList[i + 1].templateList[j].rollList[0].increment.setX(0.0)                         # vertical movement, hence dX = 0
                self.parent.survey.blockList[i + 1].templateList[j].rollList[0].increment.setY(sailLineInt)

                # roll along in inline direction
                self.parent.survey.blockList[i + 1].templateList[j].rollList[1].steps = nSht                                # nr deployments in inline-direction
                self.parent.survey.blockList[i + 1].templateList[j].rollList[1].increment.setX(-RolInt)                     # src shot interval
                self.parent.survey.blockList[i + 1].templateList[j].rollList[1].increment.setY(0.0)                         # horizontal movement, hence dY = 0

                if fanning:                                                                                                 # this all for streamer fanning; hence each streamer will have its own orientation
                    for k in range(nCab):                                           # iterate over all deployed cables

                        # we need to allow for streamer fanning; hence each streamer will have its own orientation
                        # this implies we can not 'grow' the spread to multiple streamers as a grow step in a grid

                        dRec = recY9 - recY0 + k * (dCab9 - dCab0)                                                          # cross-line cable distance
                        azi = math.degrees(math.asin(dRec / cL9)) - azim                                                    # corrresponding azimuth
                        dRGrp = gI * math.cos(math.radians(dip))

                        dXGrp = dRGrp * math.cos(math.radians(azi)) * RecBwdDx
                        dYGrp = dRGrp * math.sin(math.radians(azi))

                        dX, dY = rotatePoint2D(0.0, recY0 + k * dCab0, -azim * RecBwdDx)                                                # rotate receiver seed origin
                        # self.parent.survey.blockList[i + 1].templateList[j].seedList[k + 1].origin.setX(RecBwdX0 - j * PopInt)          # Seed origin
                        # self.parent.survey.blockList[i + 1].templateList[j].seedList[k + 1].origin.setY(blkOffBwd + recY0 + k * dCab0)   # Seed origin
                        self.parent.survey.blockList[i + 1].templateList[j].seedList[k + 1].origin.setX(dX + RecBwdX0 - j * PopInt)     # Seed origin
                        self.parent.survey.blockList[i + 1].templateList[j].seedList[k + 1].origin.setY(dY + blkOffBwd)                 # Seed origin
                        self.parent.survey.blockList[i + 1].templateList[j].seedList[k + 1].origin.setZ(recZ0)                          # Seed origin

                        self.parent.survey.blockList[i + 1].templateList[j].seedList[k + 1].grid.growList[2].steps = nGrp               # nr of groups in cable
                        self.parent.survey.blockList[i + 1].templateList[j].seedList[k + 1].grid.growList[2].increment.setX(dXGrp)      # group interval
                        self.parent.survey.blockList[i + 1].templateList[j].seedList[k + 1].grid.growList[2].increment.setY(dYGrp)      # impact of fanning
                        self.parent.survey.blockList[i + 1].templateList[j].seedList[k + 1].grid.growList[2].increment.setZ(dZGrp)      # normalized slant
                else:
                    # no allowance for streamer fanning; all streamers will have the same orientation
                    # this implies we can 'grow' the spread to multiple streamers as a single grow step in a grid

                    dRGrp = gI * math.cos(math.radians(dip))
                    dXGrp = dRGrp * RecBwdDx

                    dX, dY = rotatePoint2D(0.0, recY0, -azim * RecBwdDx)                                                        # rotate receiver seed origin for all streamers
                    # self.parent.survey.blockList[i + 1].templateList[j].seedList[1].origin.setX(RecBwdX0 - j * PopInt)          # Seed origin
                    # self.parent.survey.blockList[i + 1].templateList[j].seedList[1].origin.setY(blkOffBwd + recY0)              # Seed origin
                    self.parent.survey.blockList[i + 1].templateList[j].seedList[1].origin.setX(dX + RecBwdX0 - j * PopInt)     # Seed origin
                    self.parent.survey.blockList[i + 1].templateList[j].seedList[1].origin.setY(dY + blkOffBwd)                 # Seed origin
                    self.parent.survey.blockList[i + 1].templateList[j].seedList[1].origin.setZ(recZ0)                          # Seed origin

                    dCabX, dCabY = rotatePoint2D(0.0, dCab0, -azim * RecBwdDx)                                                  # rotate cable orientation
                    self.parent.survey.blockList[i + 1].templateList[j].seedList[1].grid.growList[1].steps = nCab               # nr of cables in spread
                    # self.parent.survey.blockList[i + 1].templateList[j].seedList[1].grid.growList[1].increment.setX(0.0)        # no inline shift
                    # self.parent.survey.blockList[i + 1].templateList[j].seedList[1].grid.growList[1].increment.setY(dCab0)      # cable interval
                    self.parent.survey.blockList[i + 1].templateList[j].seedList[1].grid.growList[1].increment.setX(dCabX)      # no inline shift
                    self.parent.survey.blockList[i + 1].templateList[j].seedList[1].grid.growList[1].increment.setY(dCabY)      # cable interval
                    self.parent.survey.blockList[i + 1].templateList[j].seedList[1].grid.growList[1].increment.setZ(0.0)        # no vertical shift

                    dXGrp, dYGrp = rotatePoint2D(dXGrp, 0.0, -azim * RecBwdDx)                                                  # rotate group orientation
                    self.parent.survey.blockList[i + 1].templateList[j].seedList[1].grid.growList[2].steps = nGrp               # nr of groups in cable
                    # self.parent.survey.blockList[i + 1].templateList[j].seedList[1].grid.growList[2].increment.setX(dXGrp)      # group interval
                    # self.parent.survey.blockList[i + 1].templateList[j].seedList[1].grid.growList[2].increment.setY(0.0)        # no fanning
                    self.parent.survey.blockList[i + 1].templateList[j].seedList[1].grid.growList[2].increment.setX(dXGrp)      # group interval
                    self.parent.survey.blockList[i + 1].templateList[j].seedList[1].grid.growList[2].increment.setY(dYGrp)      # no fanning
                    self.parent.survey.blockList[i + 1].templateList[j].seedList[1].grid.growList[2].increment.setZ(dZGrp)      # normalized slant

        self.parent.survey.output.rctOutput.setLeft(self.field('binImin'))
        self.parent.survey.output.rctOutput.setTop(self.field('binXmin'))
        self.parent.survey.output.rctOutput.setWidth(self.field('binIsiz'))
        self.parent.survey.output.rctOutput.setHeight(self.field('binXsiz'))

        self.parent.survey.calcTransforms()                                     # (re)calculate the transforms being used
        self.parent.survey.calcSeedData()                                       # needed for circles, spirals & well-seeds; may affect bounding box
        self.parent.survey.calcBoundingRect()                                   # (re)calculate extent of survey

    def plot(self):
        """plot the survey area"""

        self.plotWidget.plotItem.clear()
        self.plotWidget.setTitle(self.field('name'), color='b', size='12pt')

        styles = {'color': '#646464', 'font-size': '10pt'}
        self.plotWidget.setLabel('bottom', 'inline', units='m', **styles)       # shows axis at the bottom, and shows the units label
        self.plotWidget.setLabel('left', 'crossline', units='m', **styles)      # shows axis at the left, and shows the units label
        self.plotWidget.setLabel('top', 'inline', units='m', **styles)          # shows axis at the top, and shows the survey name
        self.plotWidget.setLabel('right', 'crossline', units='m', **styles)     # shows axis at the top, and shows the survey name

        # self.parent.survey.paintMode = PaintMode.justLines
        # self.parent.survey.paintMode = PaintMode.justTemplates
        self.parent.survey.paintMode = PaintMode.justBlocks
        self.parent.survey.lodScale = 6.0
        item = self.parent.survey

        # 4. roll along and binning area
        self.plotWidget.plotItem.addItem(item)

        # Add a marker for the origin
        oriX = [0.0]
        oriY = [0.0]
        orig = self.plotWidget.plot(x=oriX, y=oriY, symbol='h', symbolSize=12, symbolPen=(0, 0, 0, 100), symbolBrush=(180, 180, 180, 100))

    def evt_binImin_editingFinished(self, plot=True):
        binI = self.field('binI')
        nrIntervals = round(self.binImin.value() / binI)
        binImin = nrIntervals * binI
        self.binImin.setValue(binImin)
        self.updateBinningArea(plot)

    def evt_binXmin_editingFinished(self, plot=True):
        binX = self.field('binX')
        nrIntervals = max(round(self.binXmin.value() / binX), 1)
        binXmin = nrIntervals * binX
        self.binXmin.setValue(binXmin)
        self.updateBinningArea(plot)

    def evt_binIsiz_editingFinished(self, plot=True):
        binI = self.field('binI')
        # nrIntervals = round(self.binIsiz.value() / binI)
        nrIntervals = max(round(self.binIsiz.value() / binI), 1)
        binIsiz = nrIntervals * binI
        self.binIsiz.setValue(binIsiz)
        self.updateBinningArea(plot)

    def evt_binXsiz_editingFinished(self, plot=True):
        binX = self.field('binX')
        # nrIntervals = round(self.binXsiz.value() / binX)
        nrIntervals = max(round(self.binXsiz.value() / binX), 1)
        binXsiz = nrIntervals * binX
        self.binXsiz.setValue(binXsiz)
        self.updateBinningArea(plot)

    def updateBinningArea(self, plot):
        self.parent.survey.output.rctOutput.setLeft(self.field('binImin'))
        self.parent.survey.output.rctOutput.setTop(self.field('binXmin'))

        self.parent.survey.output.rctOutput.setWidth(self.field('binIsiz'))
        self.parent.survey.output.rctOutput.setHeight(self.field('binXsiz'))

        if plot:
            self.plot()

    def updatePaintedAreas(self):
        self.parent.survey.paintDetails = PaintDetails.none
        if self.chkShowSrc.isChecked():
            self.parent.survey.paintDetails |= PaintDetails.srcArea
        if self.chkShowRec.isChecked():
            self.parent.survey.paintDetails |= PaintDetails.recArea
        if self.chkShowCmp.isChecked():
            self.parent.survey.paintDetails |= PaintDetails.cmpArea
        if self.chkShowBin.isChecked():
            self.parent.survey.paintDetails |= PaintDetails.binArea
        self.plot()


# Page_6 =======================================================================
# 6. Template Properties - Pattern/array details


class Page_6(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('6. Template Properties')
        self.setSubTitle('Pattern/array details')

        myPrint('page 6 init')

        # Add some widgets
        self.recPatName = QLineEdit(config.rName)
        self.srcPatName = QLineEdit(config.sName)

        self.chkRecPattern = QCheckBox('Use receiver patterns')
        self.chkSrcPattern = QCheckBox('Use source patterns')
        self.chkRecPattern.setChecked(True)
        self.chkSrcPattern.setChecked(True)

        self.recBranches = QSpinBox()
        self.srcBranches = QSpinBox()
        self.recElements = QSpinBox()
        self.srcElements = QSpinBox()

        self.recBrancInt = QDoubleSpinBox()
        self.srcBrancInt = QDoubleSpinBox()
        self.recElemeInt = QDoubleSpinBox()
        self.srcElemeInt = QDoubleSpinBox()

        self.recBranches.setValue(config.rBran)
        self.srcBranches.setValue(config.sBran)
        self.recElements.setValue(config.rElem)
        self.srcElements.setValue(config.sElem)

        self.recBrancInt.setValue(config.rBrIn)
        self.srcBrancInt.setValue(config.sBrIn)
        self.recElemeInt.setValue(config.rElIn)
        self.srcElemeInt.setValue(config.sElIn)

        self.recElements.setEnabled(False)
        self.recElemeInt.setEnabled(False)

        # set the page layout
        layout = QGridLayout()

        row = 0
        layout.addWidget(self.chkRecPattern, row, 0, 1, 2)
        layout.addWidget(self.chkSrcPattern, row, 2, 1, 2)

        row += 1
        layout.addWidget(QLabel('<b>Receiver pattern</b>'), row, 0)
        layout.addWidget(QLabel('<b>Source pattern</b>'), row, 2)

        row += 1
        layout.addWidget(self.recPatName, row, 0)
        layout.addWidget(QLabel('Array name'), row, 1)
        layout.addWidget(self.srcPatName, row, 2)
        layout.addWidget(QLabel('Array name'), row, 3)

        row += 1
        layout.addWidget(self.recBranches, row, 0)
        layout.addWidget(QLabel('<b></b>Nr inline [&#8594;]'), row, 1)
        layout.addWidget(self.srcBranches, row, 2)
        layout.addWidget(QLabel('<b></b>Nr inline [&#8594;]'), row, 3)

        row += 1
        layout.addWidget(self.recBrancInt, row, 0)
        layout.addWidget(QLabel('Inline spacing [m]'), row, 1)
        layout.addWidget(self.srcBrancInt, row, 2)
        layout.addWidget(QLabel('Inline spacing [m]'), row, 3)

        row += 1
        layout.addWidget(self.recElements, row, 0)
        layout.addWidget(QLabel('<b></b>Nr x-line [&#8593;]'), row, 1)
        layout.addWidget(self.srcElements, row, 2)
        layout.addWidget(QLabel('<b></b>Nr x-line [&#8593;]'), row, 3)

        row += 1
        layout.addWidget(self.recElemeInt, row, 0)
        layout.addWidget(QLabel('X-line spacing [m]'), row, 1)
        layout.addWidget(self.srcElemeInt, row, 2)
        layout.addWidget(QLabel('X-line spacing [m]'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        # create a vertical box layout widget (vbl)
        vbl = QVBoxLayout()

        # add the so far developed QGridLayout to the QVBoxLayout (layout)
        vbl.addLayout(layout)

        # insert PyQtGraph plotWidget                                           # See: https://groups.google.com/g/pyqtgraph/c/ls-9I2tHu2w
        self.plotWidget = pg.PlotWidget(background='w')
        self.plotWidget.setAspectLocked(True)                                   # setting can be changed through a toolbar
        self.plotWidget.showGrid(x=True, y=True, alpha=0.5)                     # shows the grey grid lines
        self.plotWidget.setMinimumSize(150, 150)                                # prevent excessive widget shrinking
        self.plotWidget.ctrlMenu = None                                         # get rid of 'Plot Options'
        self.plotWidget.scene().contextMenu = None                              # get rid of 'Export'

        self.zoomBar = PgToolBar('ZoomBar', plotWidget=self.plotWidget)
        self.zoomBar.actionAntiAlias.setChecked(True)                           # toggle Anti-alias on

        # add toolbar and plotwidget to the vertical box layout
        vbl.addWidget(self.zoomBar)
        vbl.addWidget(self.plotWidget)

        # set the combined layouts to become this page's layout
        self.setLayout(vbl)

        # register fields for access in other Wizard Page
        # see: https://stackoverflow.com/questions/35187729/pyqt5-double-spin-box-returning-none-value
        self.registerField('rUse', self.chkRecPattern)                          # use the pattern
        self.registerField('sUse', self.chkSrcPattern)                          # use the pattern

        self.registerField('rNam', self.recPatName)                             # pattern name
        self.registerField('sNam', self.srcPatName)

        self.registerField('rBra', self.recBranches, 'value')                   # nr branches in pattern
        self.registerField('sBra', self.srcBranches, 'value')

        self.registerField('rEle', self.recElements, 'value')                   # nr elem in branch
        self.registerField('sEle', self.srcElements, 'value')

        self.registerField('rBrI', self.recBrancInt, 'value')                   # nr branches in pattern
        self.registerField('sBrI', self.srcBrancInt, 'value')

        self.registerField('rElI', self.recElemeInt, 'value')                   # nr elem in branch
        self.registerField('sElI', self.srcElemeInt, 'value')

        # connect signals to slots
        self.chkRecPattern.stateChanged.connect(self.initializePage)
        self.chkSrcPattern.stateChanged.connect(self.initializePage)

        self.recPatName.editingFinished.connect(self.initializePage)
        self.srcPatName.editingFinished.connect(self.initializePage)

        self.recBranches.editingFinished.connect(self.initializePage)
        self.srcBranches.editingFinished.connect(self.initializePage)
        self.recElements.editingFinished.connect(self.initializePage)
        self.srcElements.editingFinished.connect(self.initializePage)

        self.recBrancInt.editingFinished.connect(self.initializePage)
        self.srcBrancInt.editingFinished.connect(self.initializePage)
        self.recElemeInt.editingFinished.connect(self.initializePage)
        self.srcElemeInt.editingFinished.connect(self.initializePage)

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        myPrint('initialize page 6')

        self.updateParentSurvey()
        self.plot()

    def cleanupPage(self):                                                      # needed to update previous page
        myPrint('cleanup of page 6')

    def updateParentSurvey(self):
        # populate / update the survey skeleton - Page_6

        rUse = self.field('rUse')
        sUse = self.field('sUse')

        rNam = self.field('rNam')
        sNam = self.field('sNam')

        rBra = self.field('rBra')
        sBra = self.field('sBra')
        rEle = self.field('rEle')
        sEle = self.field('sEle')

        rBrI = self.field('rBrI')
        sBrI = self.field('sBrI')
        rElI = self.field('rElI')
        sElI = self.field('sElI')

        srcOriX = -0.5 * (sBra - 1) * sBrI
        srcOriY = -0.5 * (sEle - 1) * sElI
        recOriX = -0.5 * (rBra - 1) * rBrI
        recOriY = -0.5 * (rEle - 1) * rElI

        # source
        self.parent.survey.patternList[0].name = sNam
        self.parent.survey.patternList[0].seedList[0].color = QColor('red')

        self.parent.survey.patternList[0].seedList[0].origin.setX(srcOriX)                      # Seed origin
        self.parent.survey.patternList[0].seedList[0].origin.setY(srcOriY)                      # Seed origin

        self.parent.survey.patternList[0].seedList[0].grid.growList[0].steps = sBra             # nr branches
        self.parent.survey.patternList[0].seedList[0].grid.growList[0].increment.setX(sBrI)     # branch interval
        self.parent.survey.patternList[0].seedList[0].grid.growList[0].increment.setY(0.0)      # horizontal

        self.parent.survey.patternList[0].seedList[0].grid.growList[1].steps = sEle             # nr elements
        self.parent.survey.patternList[0].seedList[0].grid.growList[1].increment.setX(0.0)      # vertical
        self.parent.survey.patternList[0].seedList[0].grid.growList[1].increment.setY(sElI)     # element interval

        self.parent.survey.patternList[0].calcPatternPicture()                                  # update pattern picture

        # receiver
        self.parent.survey.patternList[1].name = rNam
        self.parent.survey.patternList[1].seedList[0].color = QColor('blue')

        self.parent.survey.patternList[1].seedList[0].origin.setX(recOriX)                      # Seed origin
        self.parent.survey.patternList[1].seedList[0].origin.setY(recOriY)                      # Seed origin

        self.parent.survey.patternList[1].seedList[0].grid.growList[0].steps = rBra             # nr branches
        self.parent.survey.patternList[1].seedList[0].grid.growList[0].increment.setX(rBrI)     # branch interval
        self.parent.survey.patternList[1].seedList[0].grid.growList[0].increment.setY(0.0)      # horizontal

        self.parent.survey.patternList[1].seedList[0].grid.growList[1].steps = rEle             # nr elements
        self.parent.survey.patternList[1].seedList[0].grid.growList[1].increment.setX(0.0)      # vertical
        self.parent.survey.patternList[1].seedList[0].grid.growList[1].increment.setY(rElI)     # element interval

        self.parent.survey.patternList[1].calcPatternPicture()                                  # update pattern picture

        # calculate the boundingBpx, now the patterns have been populated
        self.parent.survey.patternList[0].calcBoundingRect()
        self.parent.survey.patternList[1].calcBoundingRect()

        # finally, we need to update the template-seeds giving them the right pattern type
        for block in self.parent.survey.blockList:
            for template in block.templateList:
                for seed in template.seedList:
                    if seed.bSource:
                        if sUse:
                            seed.patternNo = 0
                            seed.patternPicture = self.parent.survey.patternList[0].patternPicture
                        else:
                            seed.patternNo = -1
                            seed.patternPicture = None
                    else:
                        if rUse:
                            seed.patternNo = 1
                            seed.patternPicture = self.parent.survey.patternList[1].patternPicture
                        else:
                            seed.patternNo = -1
                            seed.patternPicture = None

    def plot(self):
        """plot the pattern(s)"""

        rUse = self.field('rUse')
        sUse = self.field('sUse')

        rNam = self.field('rNam')
        sNam = self.field('sNam')

        rNam = rNam if rUse else 'no rec pattern'
        sNam = sNam if sUse else 'no src pattern'

        connect = ' & ' if rUse and sUse else ' - '

        self.plotWidget.plotItem.clear()
        self.plotWidget.setTitle(f'{rNam}{connect}{sNam}', color='b', size='12pt')

        styles = {'color': '#646464', 'font-size': '10pt'}
        self.plotWidget.setLabel('bottom', 'inline', units='m', **styles)       # shows axis at the bottom, and shows the units label
        self.plotWidget.setLabel('left', 'crossline', units='m', **styles)      # shows axis at the left, and shows the units label
        self.plotWidget.setLabel('top', 'inline', units='m', **styles)          # shows axis at the top, and shows the survey name
        self.plotWidget.setLabel('right', 'crossline', units='m', **styles)     # shows axis at the top, and shows the survey name

        srcPattern = RollPattern()
        srcPattern = self.parent.survey.patternList[0]

        recPattern = RollPattern()
        recPattern = self.parent.survey.patternList[1]

        if sUse:
            item1 = srcPattern
            self.plotWidget.plotItem.addItem(item1)

        if rUse:
            item2 = recPattern
            self.plotWidget.plotItem.addItem(item2)

        # Add a marker for the origin
        # oriX = [0.0]
        # oriY = [0.0]
        # orig = self.plotWidget.plot(x=oriX, y=oriY, symbol='h', symbolSize=12, symbolPen=(0, 0, 0, 100), symbolBrush=(180, 180, 180, 100))


# Page_7 =======================================================================
# 7. Project Coordinate Reference System (CRS)


class Page_7(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('7. Project Coordinate Reference System (CRS)')
        self.setSubTitle('Select a Projected CRS to ensure valid distance and areal measurements')

        myPrint('page 7 init')

        # See: https://api.qgis.org/api/3.16/qgscoordinatereferencesystem_8h_source.html#l00668
        # See https://api.qgis.org/api/classQgsProjectionSelectionTreeWidget.html
        self.proj_selector = QgsProjectionSelectionTreeWidget()

        # See: https://qgis.org/pyqgis/master/core/QgsProject.html#qgis.core.QgsProject.crs
        # tmpCrs = QgsProject.instance().crs()
        # if tmpCrs.isValid():
        #    self.proj_selector.setCrs(tmpCrs)

        # set the page layout
        layout = QVBoxLayout()
        layout.addWidget(self.proj_selector)
        self.setLayout(layout)

        self.registerField('crs', self.proj_selector)
        self.proj_selector.crsSelected.connect(self.crs_selected)

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        myPrint('initialize page 7')

    def cleanupPage(self):                                                      # needed to update previous page
        self.parent.page(4).plot()                                              # needed to update the plot
        myPrint('cleanup of page 7')

    def crs_selected(self):
        # See: https://api.qgis.org/api/classQgsCoordinateReferenceSystem.html

        if self.proj_selector.crs().isGeographic():
            QMessageBox.warning(self, 'Wrong CRS type', 'Please select a Projected Coordinate System to ensure valid distance and area measurements.')
        else:
            self.setField('crs', self.proj_selector.crs())                       # Needed, as we have redefined isComplete()
        self.completeChanged.emit()

    def isComplete(self):
        if self.proj_selector.crs().isValid() and not self.proj_selector.crs().isGeographic():
            self.parent.survey.crs = self.field('crs')
            return True
        return False


# Page_8 =======================================================================
# 8. Project Coordinate Reference System (CRS) - Enter the survey's coordinate transformation details


class Page_8(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setTitle('8. Project Coordinate Reference System (CRS)')
        self.setSubTitle("Enter the survey's coordinate transformation details")

        myPrint('page 8 init')

        # create some widgets
        self.Xt_0 = QDoubleSpinBox()
        self.Yt_0 = QDoubleSpinBox()

        self.azim = QDoubleSpinBox()

        self.scaX = QDoubleSpinBox()
        self.scaY = QDoubleSpinBox()

        # set ranges
        self.Xt_0.setRange(-500000, 500000)
        self.Yt_0.setRange(-500000, 500000)

        self.azim.setRange(0, 360)
        self.azim.setWrapping(True)
        self.azim.setDecimals(6)

        self.scaX.setRange(-10000, 10000)
        self.scaY.setRange(-10000, 10000)
        self.scaX.setDecimals(6)
        self.scaY.setDecimals(6)

        # set the page layout
        layout = QGridLayout()

        strGlobal = """
        The <b>GLOBAL</b> bin grid is realized through an affine transformation.<br>
        The transformation from source (Xs, Ys) to target (Xt, Yt) is represented by:<br>
        » Xt =&nbsp;&nbsp;mX·cos(azim)·Xs +  mY·sin(azim)·Ys + Xt0<br>
        » Yt = –mX·sin(azim)·Xs +  mY·cos(azim)·Ys + Yt0
        """
        row = 0
        layout.addWidget(QLabel(strGlobal), row, 0, 1, 4)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        # now we are ready to add the transform to world coordinates
        # adding a figure would be very handy for this purpose. See:
        # https://www.pythonguis.com/faq/adding-images-to-pyqt5-applications/
        # https://gis.stackexchange.com/questions/350228/define-custom-projection-in-qgis-from-some-control-points
        # file:///D:/WorkStuff/Desktop-Shell/2010%20CD/SEG-UKOOA%20Formats%20and%20Standards/UKOOA%20Formats/ukooa_p6_98.pdf

        row += 1
        layout.addWidget(self.Xt_0, row, 0)
        layout.addWidget(QLabel('X-origin [m]'), row, 1)
        layout.addWidget(self.Yt_0, row, 2)
        layout.addWidget(QLabel('Y-origin [m]'), row, 3)

        # row += 1
        # layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.azim, row, 0)
        layout.addWidget(QLabel('rotation angle [deg]'), row, 1)
        layout.addWidget(QLabel('(counter clockwise: 0 - 360°)'), row, 2, 1, 2)

        # row += 1
        # layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.scaX, row, 0)
        layout.addWidget(QLabel('X-scaling (mX)'), row, 1)
        layout.addWidget(self.scaY, row, 2)
        layout.addWidget(QLabel('Y-scaling (mY)'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        # set default values for checkboxes and scale values
        self.scaX.setValue(1.0)
        self.scaY.setValue(1.0)

        # create a vertical box layout widget (vbl)
        vbl = QVBoxLayout()

        # add the so far developed QGridLayout to the QVBoxLayout (layout)
        vbl.addLayout(layout)

        # insert PyQtGraph plotWidget                                           # See: https://groups.google.com/g/pyqtgraph/c/ls-9I2tHu2w
        self.plotWidget = pg.PlotWidget(background='w')
        self.plotWidget.setAspectLocked(True)                                   # setting can be changed through a toolbar
        self.plotWidget.showGrid(x=True, y=True, alpha=0.5)                     # shows the grey grid lines
        self.plotWidget.setMinimumSize(150, 150)                                # prevent excessive widget shrinking
        self.plotWidget.ctrlMenu = None                                         # get rid of 'Plot Options'
        self.plotWidget.scene().contextMenu = None                              # get rid of 'Export'

        self.zoomBar = PgToolBar('ZoomBar', plotWidget=self.plotWidget)
        self.zoomBar.actionAntiAlias.setChecked(True)                           # toggle Anti-alias on

        # add toolbar and plotwidget to the vertical box layout
        vbl.addWidget(self.zoomBar)
        vbl.addWidget(self.plotWidget)

        # set the combined layouts to become this page's layout
        self.setLayout(vbl)

        # register fields for access in other Wizard Page
        # see: https://stackoverflow.com/questions/35187729/pyqt5-double-spin-box-returning-none-value
        self.registerField('Xt_0', self.Xt_0, 'value')
        self.registerField('Yt_0', self.Yt_0, 'value')
        self.registerField('azim', self.azim, 'value')
        self.registerField('scaX', self.scaX, 'value')
        self.registerField('scaY', self.scaY, 'value')

        # connect signals to slots
        self.Xt_0.editingFinished.connect(self.evt_global_editingFinished)
        self.Yt_0.editingFinished.connect(self.evt_global_editingFinished)
        self.azim.editingFinished.connect(self.evt_global_editingFinished)
        self.scaX.editingFinished.connect(self.evt_global_editingFinished)
        self.scaY.editingFinished.connect(self.evt_global_editingFinished)

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        myPrint('initialize page 8')
        self.evt_global_editingFinished()

    def cleanupPage(self):                                                      # needed to return to previous pages
        myPrint('cleanup of page 8')
        # transform = QTransform()                                                # reset transform
        # self.parent.survey.setTransform(transform)                              # back to local survey grid

        # note page(x) starts with a ZERO index; therefore pag(0) == Page_1
        # self.parent.page(3).plot()                                              # needed to update the plot

    def evt_global_editingFinished(self):
        azim = self.field('azim')
        Xt_0 = self.field('Xt_0')
        Yt_0 = self.field('Yt_0')
        scaX = self.field('scaX')
        scaY = self.field('scaY')

        self.parent.survey.grid.angle = azim
        self.parent.survey.grid.orig.setX(Xt_0)
        self.parent.survey.grid.orig.setY(Yt_0)
        self.parent.survey.grid.scale.setX(scaX)
        self.parent.survey.grid.scale.setY(scaY)

        transform = QTransform()
        transform.translate(Xt_0, Yt_0)
        transform.rotate(azim)
        transform.scale(scaX, scaY)

        # mainWindow = self.parent.parent
        # if mainWindow and mainWindow.debug:
        # myPrint(f'm11 ={transform.m11():12.6f},   m12 ={transform.m12():12.6f},   m13 ={transform.m13():12.6f} » [A1, B1, ...]')
        # myPrint(f'm21 ={transform.m21():12.6f},   m22 ={transform.m22():12.6f},   m23 ={transform.m23():12.6f} » [A2, B2, ...]')
        # myPrint(f'm31 ={transform.m31():12.2f},   m32 ={transform.m32():12.2f},   m33 ={transform.m33():12.6f} » [A0, B0, ...]')

        self.parent.survey.setTransform(transform)
        self.plot()

    def plot(self):
        """8. Project Coordinate Reference System (CRS)"""

        self.plotWidget.plotItem.clear()
        self.plotWidget.setTitle(self.field('name'), color='b', size='12pt')

        styles = {'color': '#646464', 'font-size': '10pt'}
        self.plotWidget.setLabel('bottom', 'Easting', units='m', **styles)  # shows axis at the bottom, and shows the units label
        self.plotWidget.setLabel('left', 'Northing', units='m', **styles)   # shows axis at the left, and shows the units label
        self.plotWidget.setLabel('top', 'Easting', units='m', **styles)     # shows axis at the top, and shows the survey name
        self.plotWidget.setLabel('right', 'Northing', units='m', **styles)  # shows axis at the top, and shows the survey name

        self.parent.survey.paintMode = PaintMode.justTemplates                  # .justTemplates justLines
        self.parent.survey.lodScale = 6.0
        item = self.parent.survey

        # 6. Project Coordinate Reference System (CRS)
        self.plotWidget.plotItem.addItem(item)
        # Add a marker for the origin
        oriX = [0.0]
        oriY = [0.0]
        orig = self.plotWidget.plot(x=oriX, y=oriY, symbol='h', symbolSize=12, symbolPen=(0, 0, 0, 100), symbolBrush=(180, 180, 180, 100))

        transform = item.transform()
        orig.setTransform(transform)

    # The global bin grid is realized through an affine transformation. See:<br>
    # » <a href = "https://epsg.io/9623-method"> EPSG 9623</a> for an affine geometric transformation<br>
    # » <a href = "https://epsg.io/9624-method"> EPSG 9624</a> for an affine parametric transformation<br>
    # » <a href = "https://epsg.org/guidance-notes.html"> EPSG Guidance note 7.2</a> for supporting information
    # <p>The affine geometric transformation of (Xs, Ys) to (Xt, Yt) is represented as:</p>
    # » Xt = Xt0  +  Xs * k * mX * cos(phiX)  +  Ys * k * mY * Ishift(phiY)<br>
    # » Yt = Yt0  –  Xs * k * mX * Ishift(phiX)  +  Ys * k * mY * cos(phiY)<br>


# Page_9 =======================================================================
# 9. Summary information - Survey representation in xml-format


class Page_9(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('9. Summary information')
        self.setSubTitle('Survey representation in xml-format')

        myPrint('page 9 init')

        # Add some widgets
        self.xmlEdit = QPlainTextEdit('Element tree')
        self.xmlEdit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.xmlEdit.setWordWrapMode(QTextOption.WrapMode.NoWrap)

        self.xmlEdit.setPlainText('show xml data here...')
        self.xmlEdit.setMinimumSize(150, 150)                                # prevent excessive widget shrinking
        self.xmlEdit.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)

        layout = QVBoxLayout()
        layout.addWidget(self.xmlEdit)
        self.setLayout(layout)

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        myPrint('initialize page 9')

        xml = self.parent.survey.toXmlString()                                  # check what's in there
        self.xmlEdit.setPlainText(xml)                                          # now show the xml information in the widget

    def cleanupPage(self):                                                      # needed to return to previous pages
        myPrint('cleanup of page 9')
