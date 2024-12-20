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
from qgis.PyQt.QtCore import QRectF, QRegularExpression, Qt
from qgis.PyQt.QtGui import QColor, QImage, QPalette, QPixmap, QRegularExpressionValidator, QTextOption, QTransform
from qgis.PyQt.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QSizePolicy, QSpinBox, QVBoxLayout, QWizard, QWizardPage

from . import config  # used to pass initial settings
from .functions import even, intListToString, knotToMeterperSec, newtonToTonForce, stringToIntList, tonForceToNewton
from .pg_toolbar import PgToolBar
from .roll_pattern import RollPattern
from .roll_survey import PaintMode, RollSurvey, SurveyList, SurveyType

current_dir = os.path.dirname(os.path.abspath(__file__))


class QHLine(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)


class QVLine(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.VLine)
        self.setFrameShadow(QFrame.Sunken)


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

    def cleanupPage(self):                                                      # To prevent initializePage() being called when browsing backwards
        pass                                                                    # Default is to do absolutely nothing !


class MarineSurveyWizard(SurveyWizard):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.nTemplates = 2                                                     # nr of templates in a streamer design. Will be equal to 2 x nr source towed

        self.addPage(Page_1(self))
        self.addPage(Page_2(self))
        self.addPage(Page_3(self))
        self.addPage(Page_4(self))
        self.addPage(Page_5(self))
        self.addPage(Page_6(self))
        self.addPage(Page_7(self))
        self.addPage(Page_8(self))

        self.setWindowTitle('Towed Streamer Survey Wizard')
        self.setWizardStyle(QWizard.ClassicStyle)

        # self.setOption(QWizard.IndependentPages , True) # Don't use this option as fields are no longer updated !!! Make dummy cleanupPage(self) instead
        logo_image = QImage(os.path.join(current_dir, 'icon.png'))
        self.setPixmap(QWizard.LogoPixmap, QPixmap.fromImage(logo_image))


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

        print('page 1 init')

        # create some widgets
        self.name = QLineEdit()
        self.type = QComboBox()

        self.vSail = QDoubleSpinBox()
        self.vTurn = QDoubleSpinBox()

        self.vSail.setRange(0.1, 10.0)
        self.vTurn.setRange(0.1, 10.0)

        self.vSail.setValue(config.vSail)                                       # do this once in the constructor
        self.vTurn.setValue(config.vTurn)                                       # do this once in the constructor

        self.vSail.textChanged.connect(self.updateParameters)
        self.vSail.editingFinished.connect(self.updateParameters)

        self.vTurn.editingFinished.connect(self.evt_vTurn_editingFinished)

        self.vCross = QDoubleSpinBox()
        self.vTail = QDoubleSpinBox()

        self.vCross.textChanged.connect(self.updateParameters)
        self.vCross.editingFinished.connect(self.updateParameters)

        self.vTail.textChanged.connect(self.updateParameters)
        self.vTail.editingFinished.connect(self.updateParameters)

        self.vCurrent = QDoubleSpinBox()                                        # readonly spinbox

        self.vCross.setRange(-5.0, 5.0)
        self.vTail.setRange(-5.0, 5.0)
        self.vCurrent.setRange(-10.0, 10.0)

        self.vCross.setValue(0.0)
        self.vCurrent.setValue(0.0)
        self.vCurrent.setEnabled(False)                                         # readonly

        self.vTail.setValue(0.0)

        self.aFeat = QDoubleSpinBox()
        self.aFeat.setRange(-90.0, 90.0)
        self.aFeat.setValue(0.0)
        self.aFeat.setEnabled(False)                                            # readonly

        self.cabLength = QDoubleSpinBox()
        self.cabLength.setRange(100.0, 20_000.0)
        self.cabLength.setValue(config.cabLength)
        self.cabLength.setSingleStep(1000.0)                                    # increment by km extra streamer

        self.groupInt = QDoubleSpinBox()
        self.groupInt.setRange(3.125, 250.0)
        self.groupInt.setValue(config.groupInt)
        self.groupInt.textChanged.connect(self.updateParameters)
        self.groupInt.editingFinished.connect(self.updateParameters)

        self.nSrc = QSpinBox()
        self.nCab = QSpinBox()

        self.nSrc.setRange(1, 50)
        self.nCab.setRange(1, 50)
        self.nCab.setSingleStep(2)                                              # we want to stick to an even number of streamers

        self.nSrc.textChanged.connect(self.updateParameters)
        self.nSrc.editingFinished.connect(self.updateParameters)

        self.srcPopInt = QDoubleSpinBox()
        self.srcShtInt = QDoubleSpinBox()
        self.srcShtInt.setEnabled(False)

        self.srcPopInt.setRange(0.0, 10_000.0)
        self.srcShtInt.setRange(0.0, 10_000.0)

        self.srcPopInt.textChanged.connect(self.updateParameters)
        self.srcPopInt.editingFinished.connect(self.updateParameters)

        self.recTail = QDoubleSpinBox()
        self.recHead = QDoubleSpinBox()

        self.recTail.setRange(0.001, 1000.0)
        self.recHead.setRange(0.001, 1000.0)

        self.recTail.setEnabled(False)
        self.recHead.setEnabled(False)

        self.srcDepth = QDoubleSpinBox()
        self.recLength = QDoubleSpinBox()

        self.nsl = QSpinBox()
        self.nrl = QSpinBox()

        self.sli = QDoubleSpinBox()
        self.rli = QDoubleSpinBox()

        self.spi = QDoubleSpinBox()
        self.rpi = QDoubleSpinBox()

        self.nsl.setRange(1, 1000)
        self.nrl.setRange(1, 10000)

        self.sli.setRange(0.01, 10000)
        self.rli.setRange(0.01, 10000)

        self.spi.setRange(0.01, 10000)
        self.rpi.setRange(0.01, 10000)

        self.chkPopGroupAlign = QCheckBox('Match pop interval to binsize (binsize = ½ streamer group)')
        self.chkPopGroupAlign.stateChanged.connect(self.updateParameters)

        # controls for specific survey types (orthogonal, parallel, slanted, brick, zigzag)
        self.slantS = QSpinBox()                                                # nr templates required for slant
        self.slantS.setRange(1, 8)
        self.slantS.setValue(5)
        self.slantA = QLineEdit()                                               # slant angle
        self.slantA.setReadOnly(True)                                           # read only

        self.brickS = QDoubleSpinBox()                                          # brick offset distance
        self.brickS.setRange(0.01, 10000)
        self.chkBrickMatchRpi = QCheckBox('&Align distance with RPI')

        self.zigzagS = QSpinBox()
        self.zigzagS.setRange(1, 3)
        self.zigzagS.setValue(1)

        self.chkMirrorOddEven = QCheckBox('&Mirror odd/even templates')
        self.chkMirrorOddEven.setChecked(True)

        # initialize the widgets
        self.type.addItem(SurveyList[-1])

        self.name.setStyleSheet('QLineEdit  { background-color : lightblue} ')
        self.type.setStyleSheet('QComboBox  { background-color : lightblue} ')

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

        # row += 1
        # layout.addWidget(QHLine(), row, 0, 1, 4)

        self.setLayout(layout)

        # start values in the constructor, mostly taken from config.py
        name = SurveyType(SurveyType.Streamer.value).name                       # get name from enum
        number = str(config.surveyNumber).zfill(3)                              # fill with leading zeroes
        self.name.setText(f'{name}_{number}')                                   # show the new name

        self.nSrc.setValue(config.nSrc)
        self.nCab.setValue(config.nCab)

        self.srcPopInt.setValue(4.0 * 0.5 * config.groupInt)
        self.srcShtInt.setValue(4.0 * 0.5 * config.groupInt * config.nSrc)

        self.srcDepth.setValue(config.srcDepth)
        self.recLength.setValue(config.recLength)

        self.recLength.textChanged.connect(self.updateParameters)

        # register fields for variable access in other Wizard Pages
        # see: https://stackoverflow.com/questions/35187729/pyqt5-double-spin-box-returning-none-value
        # See: https://stackoverflow.com/questions/33796022/use-registerfield-in-pyqt
        self.registerField('name', self.name)                                   # Survey name
        self.registerField('type', self.type)                                   # Survey type

        self.registerField('vSail', self.vSail, 'value')                        # Vessel acquisition speed
        self.registerField('vTurn', self.vTurn, 'value')                        # Vessel line turn speed

        self.registerField('vTail', self.vTail, 'value')                        # Tail current speed
        self.registerField('vCross', self.vCross, 'value')                      # crosscurrent speed

        self.registerField('vCurrent', self.vCurrent, 'value')                  # overall current speed
        self.registerField('aFeat', self.aFeat, 'value')                        # Feather angle

        self.registerField('nCab', self.nCab, 'value')                          # number of cables deployed
        self.registerField('nSrc', self.nSrc, 'value')                          # number of sources deployed

        self.registerField('nsl', self.nsl, 'value')                            # nr source lines
        self.registerField('cabLength', self.cabLength, 'value')                # streamer length
        self.registerField('groupInt', self.groupInt, 'value')                  # group interval

        self.registerField('srcPopInt', self.srcPopInt, 'value')                # pop interval
        self.registerField('srcShtInt', self.srcShtInt, 'value')                # shot point interval (per cmp line)

        self.registerField('srcDepth', self.srcDepth, 'value')                  # source depth [m]
        self.registerField('recLength', self.recLength, 'value')                # record length [s]

        self.registerField('recTail', self.recTail, 'value')                    # Clean record time, with tail current
        self.registerField('recHead', self.recHead, 'value')                    # Clean record time, with head current

        # todo: remove this later:

        self.registerField('nrl', self.nrl, 'value')                            # nr receiver lines
        self.registerField('sli', self.sli, 'value')                            # source line interval
        self.registerField('rli', self.rli, 'value')                            # receiver line interval
        self.registerField('spi', self.spi, 'value')                            # source point interval
        self.registerField('rpi', self.rpi, 'value')                            # receiver point interval

        self.registerField('nslant', self.slantS, 'value')                      # nr templates in a slanted survey
        self.registerField('brk', self.brickS, 'value')                         # brick offset distance for 2nd source line
        self.registerField('nzz', self.zigzagS, 'value')                        # nr source fleets in a zigzag survey
        self.registerField('mir', self.chkMirrorOddEven)                        # mirror od/even templates

        # connect signals to slots

        # start values in the constructor, taken from config.py
        self.nsl.setValue(config.nsl)
        self.nrl.setValue(config.nrl)
        self.sli.setValue(config.sli)
        self.rli.setValue(config.rli)
        self.spi.setValue(config.spi)
        self.rpi.setValue(config.rpi)
        self.brickS.setValue(config.brick)

        # variables to keep survey dimensions more or less the same, when editing
        self.old_rpi = config.rpi
        self.old_rli = config.rli
        self.old_sli = config.sli

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        print('initialize page 1')

        self.chkPopGroupAlign.setChecked(True)
        self.updateParameters()

    def cleanupPage(self):                                                      # needed to update previous page
        print('cleanup of page 1')

    def updateParameters(self):
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
        pass


# Page_2 =======================================================================
# 2. Template Properties - Enter Spread and Salvo details


class Page_2(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setTitle('2. Template Properties (2/2)')
        self.setSubTitle('Complete the towing configuration')

        print('page 2 init')

        self.spiderSrcX = None                                                  # needed for the cross-section plot
        self.spiderSrcZ = None
        self.spiderRecX = None
        self.spiderRecZ = None

        self.srcLayback = QDoubleSpinBox()
        self.cabLayback = QDoubleSpinBox()

        self.srcLayback.setRange(0.0, 5000.0)
        self.cabLayback.setRange(0.0, 5000.0)

        self.srcLayback.setValue(config.srcLayback)
        self.cabLayback.setValue(config.cabLayback)

        self.cabSepHead = QDoubleSpinBox()
        self.cabSepTail = QDoubleSpinBox()

        self.cabSepHead.setRange(10.0, 1000.0)
        self.cabSepTail.setRange(10.0, 1000.0)

        self.cabSepHead.setValue(config.cabSepHead)
        self.cabSepTail.setValue(config.cabSepTail)

        self.cabSepHead.textChanged.connect(self.updateCableSeparation)
        self.cabSepHead.editingFinished.connect(self.updateCableSeparation)

        self.cabSepTail.textChanged.connect(self.updateCableSeparation)
        self.cabSepTail.editingFinished.connect(self.updateCableSeparation)

        self.cabDepthHead = QDoubleSpinBox()
        self.cabDepthTail = QDoubleSpinBox()

        self.cabDepthHead.setRange(1.0, 100.0)
        self.cabDepthTail.setRange(1.0, 100.0)

        self.cabDepthHead.setValue(config.cabDepthHead)
        self.cabDepthTail.setValue(config.cabDepthTail)

        self.cabDepthHead.textChanged.connect(self.updateCableDepth)
        self.cabDepthHead.editingFinished.connect(self.updateCableDepth)

        self.cabDepthTail.textChanged.connect(self.updateCableDepth)
        self.cabDepthTail.editingFinished.connect(self.updateCableDepth)

        self.srcSepFactor = QSpinBox()
        self.srcSeparation = QDoubleSpinBox()
        self.srcSeparation.setEnabled(False)                                    # readonly

        self.srcSepFactor.setRange(1, 10)
        self.srcSeparation.setRange(0.0, 1000.0)

        self.srcSepFactor.setValue(config.srcSepFactor)
        self.srcSeparation.setValue(config.srcSeparation)

        self.srcSepFactor.textChanged.connect(self.updateSourceSeparation)
        self.srcSepFactor.editingFinished.connect(self.updateSourceSeparation)

        # variables altered when nrp, nsp change
        self.offsetInshift = 0.0
        self.offsetX_shift = 0.0

        # create some widgets
        self.nsp = QSpinBox()
        self.nrp = QSpinBox()
        self.offImin = QDoubleSpinBox()
        self.offImax = QDoubleSpinBox()

        self.offXmin = QDoubleSpinBox()
        self.offXmax = QDoubleSpinBox()

        self.chkNrecKnown = QCheckBox('Number channels/cable is known')
        self.chkNsrcKnown = QCheckBox('Number shots/salvo is known')

        self.chkNrecMatch = QCheckBox('Match number channels to SLI')
        self.chkNsrcMatch = QCheckBox('Match number of shots to RLI')

        # set ranges
        self.nsp.setRange(1, 1000000)
        self.nrp.setRange(1, 1000000)

        self.offImin.setRange(-100000, 100000)
        self.offImax.setRange(-100000, 100000)
        self.offXmin.setRange(-100000, 100000)
        self.offXmax.setRange(-100000, 100000)

        self.chkNrecKnown.setChecked(True)
        self.chkNsrcKnown.setChecked(True)
        self.chkNrecMatch.setChecked(True)
        self.chkNsrcMatch.setChecked(True)

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

        # start values in the constructor, taken from config.py                 # do this in the constructor, so it is only done ONCE
        self.nsp.setValue(config.nsp)
        self.nrp.setValue(config.nrp)

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

        # self.plotWidget.getViewBox().sigRangeChangedManually.connect(
        #     self.mouseBeingDragged)                                             # essential to find plotting state for LOD plotting

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

        #  todo: remove this later
        self.registerField('nsp', self.nsp, 'value')
        self.registerField('nrp', self.nrp, 'value')
        self.registerField('offImin', self.offImin, 'value')
        self.registerField('offImax', self.offImax, 'value')
        self.registerField('offXmin', self.offXmin, 'value')
        self.registerField('offXmax', self.offXmax, 'value')

        # connect signals to slots for checkboxes
        # connect signals to slots for edit controls

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        print('initialize page 2')

        # disable required edit controls
        chkd = self.chkNrecKnown.isChecked()
        self.nrp.setEnabled(chkd)
        self.offImax.setEnabled(not chkd)

        chkd = self.chkNsrcKnown.isChecked()
        self.nsp.setEnabled(chkd)
        self.offXmax.setEnabled(not chkd)

        # get variables from field names

        # todo: remove this later
        nrl = self.field('nrl')
        nsl = self.field('nsl')
        sli = self.field('sli')
        rli = self.field('rli')
        spi = self.field('spi')
        rpi = self.field('rpi')
        nsp = self.field('nsp')
        nrp = self.field('nrp')
        nam = self.field('name')
        typ = SurveyType.Streamer.value

        # first RESET the survey object, so we can start with it from scratch
        self.parent.survey = RollSurvey()

        # fill in the survey object information we already know now
        self.parent.survey.name = nam                                           # Survey name
        self.parent.survey.type = SurveyType(typ)                               # Survey type Enum

        # set initial offset values
        templateInShift = 0.5 * (nsl - 1) * sli
        templateX_shift = 0.5 * (nrl - 1) * rli

        self.offImin.setValue(-0.5 * (nrp - 1) * rpi + self.offsetInshift + templateInShift)
        self.offImax.setValue(0.5 * (nrp - 1) * rpi + self.offsetInshift + templateInShift)

        self.offXmin.setValue(-0.5 * (nsp - 1) * spi + self.offsetX_shift + templateX_shift)
        self.offXmax.setValue(0.5 * (nsp - 1) * spi + self.offsetX_shift + templateX_shift)

        self.plot()                                                             # refresh the plot

    def cleanupPage(self):                                                      # needed to update previous page
        print('cleanup of page 2')

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
            self.parent.survey.createBasicSkeleton(nTemplates=nSrc, nSrcSeeds=1, nRecSeeds=nCab)    # add  single block with template(s)
            self.updateParentSurvey(1)                                          # update the skeleton, but don't use it for this plot

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

            dCab = self.cabSepHead.value()
            dSrc = self.srcSeparation.value()

            recZ = -self.field('cabDepthHead')
            srcZ = -self.field('srcDepth')
            cmpZ = -config.cdpDepth

            r0 = -0.5 * (nCab - 1) * dCab                                       # first receiver
            s0 = -0.5 * (nSrc - 1) * dSrc                                       # first source actual location
            s1 = -0.5 * (nSrc - 1) * dCab / nSrc                                # first source nominal location (sep. factor == 1)
            c0 = 0.5 * (r0 + s1)                                                # first cmp
            dC = 0.5 * dCab / nSrc                                              # cmp xline size

            for nS in range(nSrc):
                for nR in range(nCab):

                    cmpX = 0.5 * (s0 + nS * dSrc + r0 + nR * dCab)

                    l = nS * nCab + nR                                          # cmp index
                    n = 2 * l                                                   # line segment index 1st point
                    m = n + 1                                                   # line segment index 2nd point

                    spiderSrcX[n] = s0 + nS * dSrc
                    spiderSrcZ[n] = srcZ

                    spiderSrcX[m] = cmpX
                    spiderSrcZ[m] = cmpZ

                    spiderRecX[n] = r0 + nR * dCab
                    spiderRecZ[n] = recZ

                    spiderRecX[m] = cmpX
                    spiderRecZ[m] = cmpZ

                    cmpActX[l] = cmpX
                    cmpActZ[l] = cmpZ

            for n in range(nSrc * nCab):
                cmpNomX[n] = c0 + n * dC
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
            # Create a survey skeleton, so we can simply update survey properties, without having to instantiate underlying classes
            # On this wizard page only forward OR backwards sailing templates are shown at once, determined by the plotIndex
            self.parent.survey.createBasicSkeleton(nTemplates=nSrc, nSrcSeeds=1, nRecSeeds=nCab)    # add  single block with template(s)
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
        # populate / update the survey skeleton

        # source(s) first
        offImin = self.field('offImin')
        offXmin = self.field('offXmin')

        nrl = self.field('nrl')
        nsl = self.field('nsl')
        sli = self.field('sli')
        rli = self.field('rli')
        spi = self.field('spi')
        rpi = self.field('rpi')
        nsp = self.field('nsp')
        nrp = self.field('nrp')
        typ = SurveyType.Streamer.value

        nsla = self.field('nslant')                                             # nr templates in a slanted survey
        brk = self.field('brk')                                                 # brick offset distance
        nzz = self.field('nzz')                                                 # nr source fleets in a zigzag survey
        mir = self.field('mir')                                                 # mirrored zigzag survey

        # populate / update the survey skeleton

        # source & receiver patterns
        rNam = self.field('rNam')
        sNam = self.field('sNam')

        # orthogonal / slanted / brick source patterns
        sBra = config.sBra
        sBrI = config.sBrI
        sEle = config.sEle
        sElI = config.sElI
        srcOriX = -0.5 * (sBra - 1) * sBrI
        srcOriY = -0.5 * (sEle - 1) * sElI

        if typ == SurveyType.Parallel.value or typ == SurveyType.Zigzag.value:
            sBra = config.sEle
            sBrI = config.sElI
            sEle = config.sBra
            sElI = config.sBrI
            srcOriX = -0.5 * (sBra - 1) * sBrI
            srcOriY = -0.5 * (sEle - 1) * sElI

        self.setField('sBra', sBra)                                             # update the relevant fields
        self.setField('sEle', sEle)                                             # only the source pattern
        self.setField('sBrI', sBrI)                                             # may change orientation
        self.setField('sElI', sElI)

        self.parent.survey.patternList[0].name = sNam
        self.parent.survey.patternList[0].seedList[0].color = QColor('red')

        self.parent.survey.patternList[0].seedList[0].origin.setX(srcOriX)      # Seed origin
        self.parent.survey.patternList[0].seedList[0].origin.setY(srcOriY)      # Seed origin

        self.parent.survey.patternList[0].seedList[0].grid.growList[0].steps = sBra              # nr branches
        self.parent.survey.patternList[0].seedList[0].grid.growList[0].increment.setX(sBrI)      # branch interval
        self.parent.survey.patternList[0].seedList[0].grid.growList[0].increment.setY(0.0)       # horizontal

        self.parent.survey.patternList[0].seedList[0].grid.growList[1].steps = sEle              # nr elements
        self.parent.survey.patternList[0].seedList[0].grid.growList[1].increment.setX(0.0)       # vertical
        self.parent.survey.patternList[0].seedList[0].grid.growList[1].increment.setY(sElI)      # element interval

        # receiver pattern
        rBra = self.field('rBra')
        rBrI = self.field('rBrI')
        rEle = self.field('rEle')
        rElI = self.field('rElI')
        recOriX = -0.5 * (rBra - 1) * rBrI
        recOriY = -0.5 * (rEle - 1) * rElI

        self.parent.survey.patternList[1].name = rNam
        self.parent.survey.patternList[1].seedList[0].color = QColor('blue')

        self.parent.survey.patternList[1].seedList[0].origin.setX(recOriX)                  # Seed origin
        self.parent.survey.patternList[1].seedList[0].origin.setY(recOriY)                  # Seed origin

        self.parent.survey.patternList[1].seedList[0].grid.growList[0].steps = rBra              # nr branches
        self.parent.survey.patternList[1].seedList[0].grid.growList[0].increment.setX(rBrI)      # branch interval
        self.parent.survey.patternList[1].seedList[0].grid.growList[0].increment.setY(0.0)       # horizontal

        self.parent.survey.patternList[1].seedList[0].grid.growList[1].steps = rEle              # nr elements
        self.parent.survey.patternList[1].seedList[0].grid.growList[1].increment.setX(0.0)       # vertical
        self.parent.survey.patternList[1].seedList[0].grid.growList[1].increment.setY(rElI)      # element interval

        # calculate the boundingBpx, now the patterns have been populated
        self.parent.survey.patternList[0].calcBoundingRect()                    # also creates the pattern figure
        self.parent.survey.patternList[1].calcBoundingRect()                    # also creates the pattern figure

        # offsets; from start/end of salvo to start/end of spread; both inline and x-line
        if typ == SurveyType.Parallel.value:                                    # no hard values; give arbitrary inline limits
            inline1 = -5975.0                                                   # negative number
            inline2 = 5975.0                                                    # positive number
        else:
            inline1 = offImin                                                   # offImin is a negative number
            inline2 = (nrp - 1) * rpi + inline1                                 # positive number

        x_line1 = -(offXmin + (nsp - 1) * spi)                                  # offXmin is a positive number
        x_line2 = (nrl - 1) * rli - offXmin

        self.parent.survey.offset.rctOffsets.setLeft(inline1 - 1.0)             # inline offset limits
        self.parent.survey.offset.rctOffsets.setRight(inline2 + 1.0)

        self.parent.survey.offset.rctOffsets.setTop(x_line1 - 1.0)              # x_line offset limits
        self.parent.survey.offset.rctOffsets.setBottom(x_line2 + 1.0)

        w = max(abs(inline1), abs(inline2))                                     # calc radial limit r from w & h
        h = max(abs(x_line1), abs(x_line2))
        r = round(math.sqrt(w * w + h * h)) + 1.0

        self.parent.survey.offset.radOffsets.setX(0.0)                          # radial; rmin
        self.parent.survey.offset.radOffsets.setY(r)                            # radial; rmax

        sL = self.field('srcLayback')
        rL = self.field('cabLayback')
        sX = rL - sL

        cL = self.field('cabLength')                                            # streamer length
        gI = self.field('groupInt')                                             # group interval
        nGrp = round(cL / gI)

        dCab = self.field('cabSepHead')
        dSrc = self.field('srcSeparation')
        recZ = -self.field('cabDepthHead')
        srcZ = -self.field('srcDepth')
        nSrc = self.field('nSrc')
        nCab = self.field('nCab')

        r0 = -0.5 * (nCab - 1) * dCab                                           # first receiver
        s0 = -0.5 * (nSrc - 1) * dSrc                                           # first source actual location

        if plotIndex == 1:
            for i in range(nSrc):
                templateNameFwd = f'Sailing Fwd-{i + 1}'                        # get suitable template name for all sources
                self.parent.survey.blockList[0].templateList[i].name = templateNameFwd

                # source fwd
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setX(sX)                         # Seed origin
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setY(s0 + i * dSrc)              # Seed origin
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setZ(srcZ)                       # Seed origin

                for j in range(nCab):
                    # we need to allow for streaer feathering; hence each streamer will have its own orientation
                    # this implies we can not 'grow' the spread to multiple streamers as a grow step in a grid
                    self.parent.survey.blockList[0].templateList[i].seedList[j + 1].origin.setX(0.0)                      # Seed origin
                    self.parent.survey.blockList[0].templateList[i].seedList[j + 1].origin.setY(r0 + j * dCab)              # Seed origin
                    self.parent.survey.blockList[0].templateList[i].seedList[j + 1].origin.setZ(recZ)                     # Seed origin

                    self.parent.survey.blockList[0].templateList[i].seedList[j + 1].grid.growList[2].steps = nGrp         # nr of groups in cable
                    self.parent.survey.blockList[0].templateList[i].seedList[j + 1].grid.growList[2].increment.setX(-gI)  # group interval
                    self.parent.survey.blockList[0].templateList[i].seedList[j + 1].grid.growList[2].increment.setY(0.0)  # no fanning (yet)
                    self.parent.survey.blockList[0].templateList[i].seedList[j + 1].grid.growList[2].increment.setZ(0.0)  # no slant (yet)

        elif plotIndex == 2:
            for i in range(nSrc):
                templateNameBwd = f'Sailing Bwd-{i + 1}'                        # get suitable template name
                self.parent.survey.blockList[0].templateList[i].name = templateNameBwd

                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setX(-sX)                         # Seed origin
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setY(s0 + i * dSrc)               # Seed origin
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setZ(srcZ)                        # Seed origin

                for j in range(nCab):
                    # we need to allow for streaer feathering; hence each streamer will have its own orientation
                    # this implies we can not 'grow' the spread to multiple streamers as a grow step in a grid
                    self.parent.survey.blockList[0].templateList[i].seedList[j + 1].origin.setX(0.0)                      # Seed origin
                    self.parent.survey.blockList[0].templateList[i].seedList[j + 1].origin.setY(r0 + j * dCab)              # Seed origin
                    self.parent.survey.blockList[0].templateList[i].seedList[j + 1].origin.setZ(recZ)                     # Seed origin

                    self.parent.survey.blockList[0].templateList[i].seedList[j + 1].grid.growList[2].steps = nGrp         # nr of groups in cable
                    self.parent.survey.blockList[0].templateList[i].seedList[j + 1].grid.growList[2].increment.setX(gI)   # group interval (in opposite direction)
                    self.parent.survey.blockList[0].templateList[i].seedList[j + 1].grid.growList[2].increment.setY(0.0)  # no fanning (yet)
                    self.parent.survey.blockList[0].templateList[i].seedList[j + 1].grid.growList[2].increment.setZ(0.0)  # no slant (yet)

        else:
            raise NotImplementedError('unsupported survey type.')

        self.parent.survey.calcSeedData()                                       # needed for circles, spirals & well-seeds; may affect bounding box
        self.parent.survey.calcBoundingRect()                                   # (re)calculate extent of survey


# Page_3 =======================================================================
# 3. Template Properties - Enter the bin grid properties


class Page_3(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setTitle('3. Template Properties')
        self.setSubTitle('Enter the bin grid properties')

        print('page 3 init')

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

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        print('initialize page 3')
        self.updateParameters()
        self.updateParentSurvey()
        self.plot()                                                             # refresh the plot

    def cleanupPage(self):                                                      # needed to update previous page
        # note page(x) starts with a ZERO index; therefore pag(0) == Page_1
        self.parent.page(1).plot()                                              # needed to update the plot
        print('cleanup of page 3')

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
        dCab = self.field('cabSepHead')
        nSrc = self.field('nSrc')
        cabLength = self.field('cabLength')                                     # streamer length
        srcShtInt = self.field('srcShtInt')                                     # shot point interval (per cmp line)
        recGrpInt = self.field('groupInt')                                      # group interval

        foldINatural = 0.5 * cabLength / srcShtInt
        foldXNatural = 1.0

        binINatural = 0.5 * recGrpInt
        binXNatural = 0.5 * dCab / nSrc

        binIActual = self.field('binI')
        binXActual = self.field('binX')

        foldIActual = foldINatural * binIActual / binINatural
        foldXActual = foldXNatural * binXActual / binXNatural

        foldTActual = foldIActual * foldXActual

        foldText = f'Max fold: {foldIActual:.1f} inline & {foldXActual:.1f} x-line, {foldTActual:.1f} fold total, in {binIActual:.2f} x {binXActual:.2f} m bins'

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

        # note page(x) starts with a ZERO index; therefore page(0) == Page_1
        self.parent.page(3).evt_binImin_editingFinished(plot=False)             # adjust binning parameters in next page (Page_4)
        self.parent.page(3).evt_binIsiz_editingFinished(plot=False)
        self.parent.page(3).evt_binXmin_editingFinished(plot=False)
        self.parent.page(3).evt_binXsiz_editingFinished(plot=False)

        self.updateParentSurvey()
        self.plot()

    def updateParentSurvey(self):
        # populate / update the survey skeleton

        binI = self.field('binI')
        binX = self.field('binX')

        xTicks = [200.0, binI]                                                    # tick interval, depending on zoom level
        yTicks = [200.0, binX]                                                    # tick interval, depending on zoom level

        axBottom = self.plotWidget.plotItem.getAxis('bottom')                   # get x axis
        axBottom.setTickSpacing(xTicks[0], xTicks[1])                           # set x ticks (major and minor)

        axTop = self.plotWidget.plotItem.getAxis('top')                         # get x axis
        axTop.setTickSpacing(xTicks[0], xTicks[1])                              # set x ticks (major and minor)

        axLeft = self.plotWidget.plotItem.getAxis('left')                       # get y axis
        axLeft.setTickSpacing(yTicks[0], yTicks[1])                             # set y ticks (major and minor)

        axRight = self.plotWidget.plotItem.getAxis('right')                     # get y axis
        axRight.setTickSpacing(yTicks[0], yTicks[1])                            # set y ticks (major and minor)

        self.parent.survey.output.rctOutput = QRectF()                          # don't dislay this in this wizard page; instead, create empty rect

        for i in range(self.parent.nTemplates):                                 # make sure nothing 'rolls'
            self.parent.survey.blockList[0].templateList[i].rollList[0].steps = 1   # nr deployments in y-direction
            self.parent.survey.blockList[0].templateList[i].rollList[1].steps = 1   # nr deployments in x-direction

        self.parent.survey.calcSeedData()                                       # needed for circles, spirals & well-seeds; may affect bounding box
        self.parent.survey.calcBoundingRect()                                   # (re)calculate extent of survey

        # surveyCenter = self.parent.survey.cmpBoundingRect.center()              # get its cmp-center

        # xC = surveyCenter.x()
        # yC = surveyCenter.y()
        # xR = sli if sli > 100 else 100
        # yR = rli if rli > 100 else 100

        # self.plotWidget.setXRange(xC - 0.7 * xR, xC + 0.7 * xR)                 # set scaling for plot
        # self.plotWidget.setYRange(yC - 0.7 * yR, yC + 0.7 * yR)

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
        self.setSubTitle('Race Track details and Binning Area')

        print('page 4 init')
        self.trackList = []                                                     # list of integers

        self.recRect = QRectF()                                                 # receiver rect
        self.srcRect = QRectF()                                                 # source rect
        self.binRect = QRectF()                                                 # cmp rect
        self.an_Rect = QRectF()                                                 # analysis rect

        # create some widgets
        self.turnRad = QDoubleSpinBox()                                         # min turning radius
        self.turnRad.setEnabled(False)                                          # readonly
        self.turnRad.setRange(1.0, 1_000_000.0)

        self.runOut = QDoubleSpinBox()                                          # run-out (= 1/2 streamer length)
        self.runOut.setEnabled(False)                                           # readonly
        self.runOut.setRange(0.0, 1_000_000.0)

        self.vMinInner = QDoubleSpinBox()                                       # min turn radius [m]
        self.vMinInner.setRange(1.0, 1_000_000.0)
        self.vMinInner.setSingleStep(0.1)                                       # increment by km 0.1 knot
        self.vMinInner.setValue(config.vMinInner)
        self.vMinInner.textChanged.connect(self.updateParameters)

        self.maxDragForce = QDoubleSpinBox()                                    # max tow force [tonF]
        self.maxDragForce.setRange(0.1, 100.0)
        self.maxDragForce.setSingleStep(0.1)                                    # increment by km 0.1 tonF
        self.maxDragForce.setValue(config.maxDragForce)
        self.maxDragForce.textChanged.connect(self.updateParameters)

        self.velInn = QDoubleSpinBox()                                          # turning speed inner streamer
        self.velInn.setEnabled(False)                                           # readonly
        self.velInn.setRange(1.0, 1_000_000.0)                                  # turn radius [m]

        self.velOut = QDoubleSpinBox()                                          # turning speed outer streamer
        self.velOut.setEnabled(False)                                           # readonly
        self.velOut.setRange(1.0, 1_000_000.0)                                  # turn radius [m]

        self.radInn = QDoubleSpinBox()                                          # turn radius from inner streamer
        self.radInn.setEnabled(False)                                           # readonly
        self.radInn.setRange(1.0, 1_000_000.0)                                  # turn radius [m]

        self.radOut = QDoubleSpinBox()                                          # turn radius speed outer streamer
        self.radOut.setEnabled(False)                                           # readonly
        self.radOut.setRange(1.0, 1_000_000.0)                                  # turn radius [m]

        self.frcInn = QDoubleSpinBox()                                          # force on inner streamer
        self.frcInn.setEnabled(False)                                           # readonly
        self.frcInn.setRange(1.0, 1_000_000.0)                                  # turn radius [m]

        self.frcOut = QDoubleSpinBox()                                          # force on outer streamer
        self.frcOut.setEnabled(False)                                           # readonly
        self.frcOut.setRange(1.0, 1_000_000.0)                                  # turn radius [m]

        self.nsl = QSpinBox()                                                   # nr sail lines in survey
        self.nsl.setEnabled(False)                                              # readonly

        self.nsl2 = QSpinBox()                                                  # nr sail lines in survey
        self.nsl2.setEnabled(False)                                             # readonly
        self.nsl2.setRange(0, 1_000)                                            # set some (positive) limits

        # See: https://stackoverflow.com/questions/40178432/how-to-customize-text-on-qpushbutton-using-qpalette
        # See: https://forum.qt.io/topic/142031/understanding-qpalette/2
        # See: https://medium.com/@wintersweet001/palette-using-pyside6-pyqt-42982328d6e1
        self.normalPalette = self.nsl2.palette()                                # get the palette of this control
        fgColorActive = self.normalPalette.color(QPalette.Active, QPalette.Text)      # foreground-color
        bgColorActive = self.normalPalette.color(QPalette.Active, QPalette.Window)    # background-color
        fgColorDisabled = self.normalPalette.color(QPalette.Disabled, QPalette.Text)      # foreground-color
        bgColorDisabled = self.normalPalette.color(QPalette.Disabled, QPalette.Window)    # background-color

        self.nsl2.setAutoFillBackground(True)

        self.nrLinesPerTrack = QSpinBox()                                       # nr lines per race track
        self.nrLinesPerTrack.setEnabled(False)                                  # readonly
        self.nrLinesPerTrack.setRange(1, 1_000)                                 # set some (positive) limits

        self.nrTracks = QDoubleSpinBox()                                        # nr race tracks per survey
        self.nrTracks.setEnabled(False)                                         # readonly
        self.nrTracks.setRange(1.0, 1_000.0)                                    # set some (positive) limits

        self.slr = QSpinBox()   # src line roll along
        self.rlr = QSpinBox()   # rec line roll along
        self.sld = QSpinBox()   # src line deployments
        self.rld = QSpinBox()   # rec line deployments

        self.msg = QLineEdit('Min turn radius:')
        self.msg.setReadOnly(True)

        self.binImin = QDoubleSpinBox()
        self.binXmin = QDoubleSpinBox()

        shift = True
        self.chkShiftSpread = QCheckBox('Move first receiver to (0,0) for easier global bingrid definition')
        self.chkShiftSpread.setChecked(shift)

        # set ranges
        self.slr.setRange(1, 1000000)
        self.rlr.setRange(1, 1000000)
        self.sld.setRange(1, 1000000)
        self.rld.setRange(1, 1000000)

        self.binImin.setRange(-1000000, 1000000)
        self.binXmin.setRange(-1000000, 1000000)

        self.surIsiz = QDoubleSpinBox()
        self.surIsiz.setRange(1, 1000000)
        self.surIsiz.setSingleStep(1000.0)                                      # increment by km 1 km
        self.surIsiz.setValue(config.surveySizeI)
        self.surIsiz.textChanged.connect(self.updateParameters)

        self.surXsiz = QDoubleSpinBox()
        self.surXsiz.setRange(1, 1000000)
        self.surXsiz.setSingleStep(1000.0)                                      # increment by km 1 km
        self.surXsiz.setValue(config.surveySizeX)
        self.surXsiz.textChanged.connect(self.updateParameters)

        # set the page layout
        layout = QGridLayout()

        row = 0
        turnLabel = QLabel("· · · · Factors affecting the vessel's minimum <b>turning radius</b> · · · ·")
        turnLabel.setAlignment(Qt.AlignCenter)
        turnLabel.setFrameStyle(QFrame.Panel | QFrame.Raised)
        turnLabel.setLineWidth(2)
        turnLabel.setFixedHeight(30)
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
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('Line turn radius from limits <b>inner</b> and <b>outer</b> streamers '), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.radInn, row, 0)
        layout.addWidget(QLabel('From inner streamer [m]'), row, 1)
        layout.addWidget(self.radOut, row, 2)
        layout.addWidget(QLabel('From outer streamer [m]'), row, 3)

        row += 1
        layout.addWidget(self.turnRad, row, 0)
        layout.addWidget(QLabel('Min turn radius [m]'), row, 1)
        layout.addWidget(self.msg, row, 2, 1, 2)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        ffLabel = QLabel('· · · · Size of full fold <b>survey area</b>, run-outs and nr sail lines · · · ·')
        ffLabel.setAlignment(Qt.AlignCenter)
        ffLabel.setFrameStyle(QFrame.Panel | QFrame.Raised)
        ffLabel.setLineWidth(2)
        ffLabel.setFixedHeight(30)
        layout.addWidget(ffLabel, row, 0, 1, 4)

        row += 1
        layout.addWidget(self.surIsiz, row, 0)
        layout.addWidget(QLabel('FF inline size [m]'), row, 1)
        layout.addWidget(self.surXsiz, row, 2)
        layout.addWidget(QLabel('Crossline size [m]'), row, 3)

        row += 1
        layout.addWidget(self.runOut, row, 0)
        layout.addWidget(QLabel('Run-out length [m]'), row, 1)
        layout.addWidget(self.nsl, row, 2)
        layout.addWidget(QLabel('Sail lines in survey [#]'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        lapsLabel = QLabel('· · · · <b>Optimal</b> nr of <b>sail lines</b> per race track, and nr <b>tracks</b> in survey · · · ·')
        lapsLabel.setAlignment(Qt.AlignCenter)
        lapsLabel.setFrameStyle(QFrame.Panel | QFrame.Raised)
        lapsLabel.setLineWidth(2)
        lapsLabel.setFixedHeight(30)
        layout.addWidget(lapsLabel, row, 0, 1, 4)

        row += 1
        layout.addWidget(self.nrLinesPerTrack, row, 0)
        layout.addWidget(QLabel('lines/race track [#]'), row, 1)
        layout.addWidget(self.nrTracks, row, 2)
        layout.addWidget(QLabel('Race tracks in survey'), row, 3)

        row += 1
        layout.addWidget(QLabel('List the series of race tracks, by their respective nr of sail lines, separated by a space'), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('Note: apart from the <b>last</b> race track, all numbers shall be <b>odd</b>'), row, 0, 1, 4)

        row += 1
        self.lineSeries = QLineEdit('15 15 15 15')
        layout.addWidget(self.lineSeries, row, 0)
        input_validator = QRegularExpressionValidator(QRegularExpression('[0-9 ]+'), self.lineSeries)
        self.lineSeries.setValidator(input_validator)
        self.lineSeries.textEdited.connect(self.updateTrackList)

        layout.addWidget(self.lineSeries, row, 0)
        layout.addWidget(QLabel('list of sail lines/track'), row, 1)
        layout.addWidget(self.nsl2, row, 2)
        layout.addWidget(QLabel('Sail lines in survey [#]'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        # # create a vertical box layout widget (vbl)
        # vbl = QVBoxLayout()

        # # add the so far developed QGridLayout to the QVBoxLayout (layout)
        # vbl.addLayout(layout)

        # # insert PyQtGraph plotWidget                                           # See: https://groups.google.com/g/pyqtgraph/c/ls-9I2tHu2w
        # self.plotWidget = pg.PlotWidget(background='w')
        # self.plotWidget.setAspectLocked(True)                                   # setting can be changed through a toolbar
        # self.plotWidget.showGrid(x=True, y=True, alpha=0.5)                     # shows the grey grid lines
        # self.plotWidget.setMinimumSize(150, 150)                                # prevent excessive widget shrinking
        # self.plotWidget.ctrlMenu = None                                         # get rid of 'Plot Options'
        # self.plotWidget.scene().contextMenu = None                              # get rid of 'Export'

        # self.zoomBar = PgToolBar('ZoomBar', plotWidget=self.plotWidget)
        # self.zoomBar.actionAntiAlias.setChecked(True)                           # toggle Anti-alias on

        # # add toolbar and plotwidget to the vertical box layout
        # vbl.addWidget(self.zoomBar)
        # vbl.addWidget(self.plotWidget)

        # # set the combined layouts to become this page's layout
        # self.setLayout(vbl)

        # set the combined layouts
        self.setLayout(layout)

        # register fields
        self.registerField('vMinInner', self.vMinInner, 'value')                # min cable velocity
        self.registerField('maxDragForce', self.maxDragForce, 'value')          # max towing force

        self.registerField('rlr', self.rlr, 'value')                            # rec line roll steps
        self.registerField('slr', self.slr, 'value')                            # src line roll steps
        self.registerField('rld', self.rld, 'value')                            # rec line deployments
        self.registerField('sld', self.sld, 'value')                            # src line deployments

        self.registerField('rec_00', self.chkShiftSpread)                       # put 1st receiver at (0,0)

        self.registerField('binImin', self.binImin, 'value')                    # bin area x-origin
        self.registerField('surIsiz', self.surIsiz, 'value')                    # bin area x-size
        self.registerField('binXmin', self.binXmin, 'value')                    # bin area y-origin
        self.registerField('surXsiz', self.surXsiz, 'value')                    # bin area y-size

        # connect signals to slots
        self.rlr.editingFinished.connect(self.evt_roll_editingFinished)         # connect all signals to the same slot
        self.slr.editingFinished.connect(self.evt_roll_editingFinished)
        self.rld.editingFinished.connect(self.evt_roll_editingFinished)
        self.sld.editingFinished.connect(self.evt_roll_editingFinished)

        # self.binImin.editingFinished.connect(self.evt_binImin_editingFinished)
        # self.surIsiz.editingFinished.connect(self.evt_binIsiz_editingFinished)
        # self.binXmin.editingFinished.connect(self.evt_binXmin_editingFinished)
        # self.surXsiz.editingFinished.connect(self.evt_binXsiz_editingFinished)

        self.chkShiftSpread.toggled.connect(self.evt_chkShiftSpread_toggled)

        # give some initial values
        self.rlr.setValue(config.rlr)       # moveup one line
        self.slr.setValue(config.slr)       # moveup one line
        self.sld.setValue(round(config.deployInline / (config.slr * config.sli)) + 1)
        self.rld.setValue(round(config.deployX_line / (config.rlr * config.rli)) + 1)

        # initial bin analysis area
        shiftI = 6000 if shift else 0
        self.binImin.setValue(config.binImin + shiftI)
        # self.surXsiz.setValue(config.surveySizeX)

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        print('initialize page 4')

        sli = self.field('sli')
        rli = self.field('rli')
        nsl = self.field('nsl')

        slr = nsl                                                               # normally roll amount of source lines in template; should be different for parallel !!
        rlr = self.parent.nTemplates                                            # roll as many lines as there are templates
        self.setField('slr', slr)
        self.setField('rlr', rlr)

        sld = max(round(config.deployInline / (slr * sli)), 1)
        rld = max(round(config.deployX_line / (rlr * rli)), 1)
        self.setField('sld', sld)
        self.setField('rld', rld)

        self.updateParameters()
        self.updateTrackList()

        self.updateParentSurvey()                                               # update the survey object
        # self.plot()                                                             # show the plot, center the bin analysis area

    def updateParameters(self):
        # need to work out nr of sail lines and ideal racetrack width
        cL = self.field('cabLength')                                            # streamer length
        dCab = self.field('cabSepHead')
        nCab = self.field('nCab')
        surXsiz = self.field('surXsiz')
        vTurn = self.field('vTurn')                                             # Vessel line turn speed (from page 1)
        vMinInner = self.field('vMinInner')
        maxDragForce = self.field('maxDragForce')

        sli = 0.5 * nCab * dCab                                                 # sail line interval
        nsl = math.ceil(surXsiz / sli)                                          # nr sail lines
        self.nsl.setValue(nsl)

        spreadWidth = (nCab - 1) * dCab
        innerTurningRadius = 0.5 * vTurn * spreadWidth / (vTurn - vMinInner)   # speed in knot or m/s does not matter for their ratio

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
        vesselTurningRadius = max(2500.0, 10.0 * math.ceil(0.1 * max(innerTurningRadius, outerTurningRadius)))
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

        nrLinesPerTrack = round(vesselTurningRadius / sli + 0.5) * 2 + 1
        self.nrLinesPerTrack.setValue(nrLinesPerTrack)

        nrTracks = surXsiz / (sli * nrLinesPerTrack)
        self.nrTracks.setValue(nrTracks)

        # create basic tracklist

        self.trackList = []
        while sum(self.trackList) < nsl:
            self.trackList.append(nrLinesPerTrack)
        # else:
        #     print('i is no longer less than 6')

        self.lineSeries.setText(intListToString(self.trackList))
        self.nsl2.setValue(sum(self.trackList))

    def updateTrackList(self):
        # work out sequence of saillines per race track

        trackList = stringToIntList(self.lineSeries.text())
        self.nsl2.setValue(sum(trackList))

        nTracks = len(trackList)

        error = False
        if nTracks > 1:                                                         # need at least 2 tracks to restrict the first track
            for track in trackList[:-1]:                                        # ignore last entry
                if even(track):                                                 # not allowed
                    error = True
                    break
        if error:
            self.lineSeries.setStyleSheet('QLineEdit {color:red; background-color:lightblue;}')
            # self.lineSeries.setStyleSheet('QLabel {color:red}')
        else:
            self.lineSeries.setStyleSheet('QLineEdit {color:black; background-color:white;}')
            # self.lineSeries.setStyleSheet('QLabel {color:black}')

        nsl2 = self.nsl2.value()
        nsl = self.nsl.value()

        if nsl2 < nsl:
            self.nsl2.setStyleSheet('QSpinBox {color:red; background-color:lightblue;}')
            # self.nsl2.setStyleSheet('QLabel {color:red}')
        else:
            self.nsl2.setStyleSheet('QSpinBox {color:black; background-color:lightgrey;}')
            # self.nsl2.setStyleSheet('QLabel {color:black}')

    def updateParentSurvey(self):                                               # update the survey object
        # populate / update the survey skeleton; growList is not being affected
        # depending on the survey type, we need to iterate over the number of templates

        offImin = self.field('offImin')

        nsl = self.field('nsl')                                                 # number source lines
        sli = self.field('sli')                                                 # source line interval
        rli = self.field('rli')                                                 # receiver line interval
        spi = self.field('spi')                                                 # source point interval
        rpi = self.field('rpi')                                                 # receiver point interval
        typ = self.field('type')                                                # template type

        nsla = self.field('nslant')                                             # nr templates in a slanted survey
        brk = self.field('brk')                                                 # brick offset distance
        nzz = self.field('nzz')                                                 # nr source fleets in a zigzag survey
        mir = self.field('mir')                                                 # mirrored zigzag survey

        rec_00 = self.field('rec_00')                                           # if True, move receiver origin to (0, 0)
        shiftI = -offImin if rec_00 else 0.0                                    # amount of x-shift to apply to each seed

        if typ == SurveyType.Orthogonal.value or typ == SurveyType.Parallel.value:
            # source
            nPadding = (nsl - 1) * round(sli / rpi)                                                         # add nr recs between two source lines
            self.parent.survey.blockList[0].templateList[0].seedList[0].origin.setX(shiftI)                # Seed origin
            # receiver
            self.parent.survey.blockList[0].templateList[0].seedList[1].origin.setX(offImin + shiftI)       # Seed origin

        elif typ == SurveyType.Slanted.value:
            nPadding = round(sli / rpi)                                        # as many rec points as there are between 2 src lines
            nPadding += (nsl - 1) * round(sli / rpi)                            # add nr recs between two source lines

            ratio = sli / (nsla * rli)                                          # get the ratio from the slant angle

            for i in range(nsla):
                # source
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setX(i * rli * ratio + shiftI)   # Seed origin
                # receiver
                self.parent.survey.blockList[0].templateList[i].seedList[1].origin.setX(offImin + shiftI)        # Seed origin

        elif typ == SurveyType.Brick.value:
            nPadding = round(brk / rpi)                                          # shift in source lines
            nPadding += (nsl - 1) * round(sli / rpi)                            # add nr recs between two source lines

            for i in range(self.parent.nTemplates):
                # source
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setX(i * brk + shiftI)       # Seed origin
                # receiver
                self.parent.survey.blockList[0].templateList[i].seedList[1].origin.setX(offImin + shiftI)       # Seed origin

        elif typ == SurveyType.Zigzag.value:
            nPadding = 2 * (round(rli / spi) + nzz - 1) - 1                       # zig + zag distance, accounted for nzz
            # no need to adjust for nsl; is always 1 for zigzag

            for i in range(0, 2 * nzz, 2):
                # source up
                self.parent.survey.blockList[0].templateList[0].seedList[i].origin.setX(i * rpi + shiftI)              # Seed origin
                # source down
                self.parent.survey.blockList[0].templateList[0].seedList[i + 1].origin.setX(rli + i * rpi + shiftI)      # Seed origin

            # receiver
            i = 2 * nzz
            self.parent.survey.blockList[0].templateList[0].seedList[i].origin.setX(offImin + shiftI)               # Seed origin

            if mir:                                                                                             # now do the mirror template
                for i in range(0, 2 * nzz, 2):
                    # source up
                    self.parent.survey.blockList[0].templateList[1].seedList[i].origin.setX(i * rpi + shiftI)              # Seed origin
                    # source down
                    self.parent.survey.blockList[0].templateList[1].seedList[i + 1].origin.setX(rli + i * rpi + shiftI)        # Seed origin

                # receiver
                i = 2 * nzz
                self.parent.survey.blockList[0].templateList[1].seedList[i].origin.setX(offImin + shiftI)                # Seed origin

        elif typ == SurveyType.Streamer.value:
            pass

        else:
            raise NotImplementedError('unsupported survey type.')

        # the following parameters are at the core of this wizard page
        # parameters for X-line roll, hence the rec lines increment
        rld = self.field('rld')                                                 # rec line deployments
        rlr = self.field('rlr')                                                 # move-up along src line
        rli = self.field('rli')                                                 # rec line interval
        rlr *= rli

        # parameters for inline roll, hence the source lines increment
        sld = self.field('sld')                                                 # src line deployments
        slr = self.field('slr')                                                 # rec line roll along
        sli = self.field('sli')                                                 # source line interval
        slr *= sli

        for i in range(self.parent.nTemplates):
            self.parent.survey.blockList[0].templateList[i].rollList[0].steps = rld           # nr deployments in y-direction
            self.parent.survey.blockList[0].templateList[i].rollList[0].increment.setX(0.0)   # vertical
            self.parent.survey.blockList[0].templateList[i].rollList[0].increment.setY(rlr)   # deployment interval

            self.parent.survey.blockList[0].templateList[i].rollList[1].steps = sld           # nr deployments in x-direction
            self.parent.survey.blockList[0].templateList[i].rollList[1].increment.setX(slr)   # deployment interval
            self.parent.survey.blockList[0].templateList[i].rollList[1].increment.setY(0.0)   # horizontal

        self.parent.survey.output.rctOutput.setLeft(self.field('binImin'))
        self.parent.survey.output.rctOutput.setWidth(self.field('surIsiz'))
        self.parent.survey.output.rctOutput.setTop(self.field('binXmin'))
        self.parent.survey.output.rctOutput.setHeight(self.field('surXsiz'))

        self.parent.survey.calcSeedData()                                       # needed for circles, spirals & well-seeds; may affect bounding box
        self.parent.survey.calcBoundingRect()                                   # (re)calculate extent of survey

    def cleanupPage(self):                                                      # needed to update previous page
        print('cleanup of page 4')

        # added 19/06/2024
        self.parent.survey.output.rctOutput = QRectF()                          # don't dislay this in 'earlier' wizard pages; instead, create empty rect
        for i in range(self.parent.nTemplates):
            self.parent.survey.blockList[0].templateList[i].rollList[0].steps = 1  # nr deployments in y-direction
            self.parent.survey.blockList[0].templateList[i].rollList[1].steps = 1  # nr deployments in x-direction

        self.parent.survey.calcSeedData()                                       # needed for circles, spirals & well-seeds; may affect bounding box
        self.parent.survey.calcBoundingRect()                                   # (re)calculate extent of survey ignoring rolling along

        # note page(x) starts with a ZERO index; therefore page(0) == Page_1 and page(2) == Page_3
        self.parent.page(2).updateParentSurvey()                                # (re)center single spread, may be shifted inline due to origin shift
        self.parent.page(2).plot()                                              # needed to update the plot

    def plot(self):
        pass
        # """plot the survey area"""

        # self.plotWidget.plotItem.clear()
        # self.plotWidget.setTitle(self.field('name'), color='b', size='12pt')

        # styles = {'color': '#646464', 'font-size': '10pt'}
        # self.plotWidget.setLabel('bottom', 'inline', units='m', **styles)       # shows axis at the bottom, and shows the units label
        # self.plotWidget.setLabel('left', 'crossline', units='m', **styles)      # shows axis at the left, and shows the units label
        # self.plotWidget.setLabel('top', 'inline', units='m', **styles)          # shows axis at the top, and shows the survey name
        # self.plotWidget.setLabel('right', 'crossline', units='m', **styles)     # shows axis at the top, and shows the survey name

        # self.parent.survey.paintMode = PaintMode.justTemplates                      # .justLines
        # self.parent.survey.lodScale = 6.0
        # item = self.parent.survey

        # # 4. roll along and binning area
        # self.plotWidget.plotItem.addItem(item)

        # # Add a marker for the origin
        # oriX = [0.0]
        # oriY = [0.0]
        # orig = self.plotWidget.plot(x=oriX, y=oriY, symbol='h', symbolSize=12, symbolPen=(0, 0, 0, 100), symbolBrush=(180, 180, 180, 100))

    def evt_chkShiftSpread_toggled(self, chkd):
        offImin = self.field('offImin')
        Imin = self.field('binImin')                                     # get inline origin of binning area
        if chkd:                                                                # shifted up to (0,0) for the first receiver ?
            Imin -= offImin                                                   # shift the area to the right (offImin is negative)
        else:                                                                   # shifted up to (0,0) for the first receiver ?
            Imin += offImin                                                   # shift the area back to the left

        self.binImin.setValue(Imin)                                             # update the control
        self.setField('binImin', Imin)                                          # update the field

        self.updateParentSurvey()
        self.plot()

    def evt_roll_editingFinished(self):
        self.updateParentSurvey()
        self.plot()

    def evt_binImin_editingFinished(self, plot=True):
        binI = self.field('binI')
        nrIntervals = max(round(self.binImin.value() / binI), 1)
        binImin = nrIntervals * binI
        self.binImin.setValue(binImin)
        self.updateBinningArea(plot)

    def evt_binIsiz_editingFinished(self, plot=True):
        binI = self.field('binI')
        nrIntervals = max(round(self.surIsiz.value() / binI), 1)
        surIsiz = nrIntervals * binI
        # self.surIsiz.setValue(surIsiz)
        self.updateBinningArea(plot)

    def evt_binXmin_editingFinished(self, plot=True):
        binX = self.field('binX')
        nrIntervals = max(round(self.binXmin.value() / binX), 1)
        binXmin = nrIntervals * binX
        self.binXmin.setValue(binXmin)
        self.updateBinningArea(plot)

    def evt_binXsiz_editingFinished(self, plot=True):
        binX = self.field('binX')
        nrIntervals = max(round(self.surXsiz.value() / binX), 1)
        surXsiz = nrIntervals * binX
        # self.surXsiz.setValue(surXsiz)
        self.updateBinningArea(plot)

    def updateBinningArea(self, plot):
        self.parent.survey.output.rctOutput.setLeft(self.field('binImin'))
        self.parent.survey.output.rctOutput.setWidth(self.field('surIsiz'))
        self.parent.survey.output.rctOutput.setTop(self.field('binXmin'))
        self.parent.survey.output.rctOutput.setHeight(self.field('surXsiz'))

        if plot:
            self.plot()


# Page_5 =======================================================================
# 5. Template Properties - Pattern/array details


class Page_5(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('5. Template Properties')
        self.setSubTitle('Pattern/array details')

        print('page 5 init')

        # Add some widgets
        self.chkExtendOffsets = QCheckBox('Extend offsets with 0.5 bingrid - to prevent roundoff errors')
        self.chkExtendOffsets.setChecked(True)

        self.recPatName = QLineEdit(config.rNam)
        self.srcPatName = QLineEdit(config.sNam)

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

        self.recBranches.setValue(config.rBra)
        self.srcBranches.setValue(config.sBra)
        self.recElements.setValue(config.rEle)
        self.srcElements.setValue(config.sEle)

        self.recBrancInt.setValue(config.rBrI)
        self.srcBrancInt.setValue(config.sBrI)
        self.recElemeInt.setValue(config.rElI)
        self.srcElemeInt.setValue(config.sElI)

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

        # self.plotWidget.getViewBox().sigRangeChangedManually.connect(
        #     self.mouseBeingDragged)                                             # essential to find plotting state for LOD plotting

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
        print('initialize page 5')
        self.updateParentSurvey()
        self.plot()

    def cleanupPage(self):                                                      # needed to update previous page
        print('cleanup of page 5')

    def updateParentSurvey(self):
        # populate / update the survey skeleton

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
        """plot the template"""

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

        # 5. Template Properties

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


# Page_6 =======================================================================
# 6. Project Coordinate Reference System (CRS)


class Page_6(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('6. Project Coordinate Reference System (CRS)')
        self.setSubTitle('Select a Projected CRS to ensure valid distance and areal measurements')

        print('page 6 init')

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
        print('initialize page 6')

    def cleanupPage(self):                                                      # needed to update previous page
        self.parent.page(4).plot()                                              # needed to update the plot
        print('cleanup of page 6')

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


# Page_7 =======================================================================
# 7. Project Coordinate Reference System (CRS) - Enter the survey's coordinate transformation details


class Page_7(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setTitle('7. Project Coordinate Reference System (CRS)')
        self.setSubTitle("Enter the survey's coordinate transformation details")

        print('page 7 init')

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
        » Yt = –mX·sin(azim)·Xs +  mY·cos(azim)·Ys + Yt0<br><br>
        <b>Note:</b> The survey origin can be shifted to the location of the first receiver station<br>
        See <b>Page 3</b> of the wizard for the appropriate (x0, y0) setting
        """
        row = 0
        layout.addWidget(QLabel(strGlobal), row, 0, 1, 4)

        # row += 1
        # layout.addWidget(QHLine(), row, 0, 1, 4)

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

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.azim, row, 0)
        layout.addWidget(QLabel('rotation angle [deg]'), row, 1)
        layout.addWidget(QLabel('(counter clockwise: 0 - 360°)'), row, 2, 1, 2)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

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

        # self.plotWidget.getViewBox().sigRangeChangedManually.connect(
        #     self.mouseBeingDragged)                                             # essential to find plotting state for LOD plotting

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
        print('initialize page 7')
        self.evt_global_editingFinished()

    def cleanupPage(self):                                                      # needed to return to previous pages
        print('cleanup of page 7')
        transform = QTransform()                                                # reset transform
        self.parent.survey.setTransform(transform)                              # back to local survey grid

        # note page(x) starts with a ZERO index; therefore pag(0) == Page_1
        self.parent.page(3).plot()                                              # needed to update the plot

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
        # print(f'm11 ={transform.m11():12.6f},   m12 ={transform.m12():12.6f},   m13 ={transform.m13():12.6f} » [A1, B1, ...]')
        # print(f'm21 ={transform.m21():12.6f},   m22 ={transform.m22():12.6f},   m23 ={transform.m23():12.6f} » [A2, B2, ...]')
        # print(f'm31 ={transform.m31():12.2f},   m32 ={transform.m32():12.2f},   m33 ={transform.m33():12.6f} » [A0, B0, ...]')

        self.parent.survey.setTransform(transform)
        self.plot()

    def plot(self):
        """6. Project Coordinate Reference System (CRS)"""

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


# Page_8 =======================================================================
# 8. Summary information - Survey representation in xml-format


class Page_8(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('8. Summary information')
        self.setSubTitle('Survey representation in xml-format')

        print('page 8 init')

        # Add some widgets
        self.xmlEdit = QPlainTextEdit('Element tree')
        self.xmlEdit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.xmlEdit.setWordWrapMode(QTextOption.NoWrap)

        self.xmlEdit.setPlainText('show xml data here...')
        self.xmlEdit.setMinimumSize(150, 150)                                # prevent excessive widget shrinking
        self.xmlEdit.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)

        layout = QVBoxLayout()
        layout.addWidget(self.xmlEdit)
        self.setLayout(layout)

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        print('initialize page 8')

        xml = self.parent.survey.toXmlString()                                  # check what's in there
        self.xmlEdit.setPlainText(xml)                                          # now show the xml information in the widget

    def cleanupPage(self):                                                      # needed to return to previous pages
        print('cleanup of page 8')
