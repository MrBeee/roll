# -----------------------------------------------------------------------------------------------------------------
# See: https://north-road.com/2018/03/09/implementing-an-in-house-new-project-wizard-for-qgis/
# And: https://plugins.qgis.org/planet/user/29/tag/python/
# See: https://doc.qt.io/archives/qq/qq22-qwizard.html#registeringandusingfields for innards of a QWizard
# -----------------------------------------------------------------------------------------------------------------

# See: https://p.yusukekamiyamane.com/ for free icons
# See: https://www.pythonguis.com/faq/editing-pyqt-tableview/ for editing a table widget

import math
import os
import os.path

import pyqtgraph as pg
from qgis.gui import QgsProjectionSelectionTreeWidget
from qgis.PyQt.QtCore import QRectF, QSizeF
from qgis.PyQt.QtGui import QColor, QImage, QPixmap, QTextOption, QTransform
from qgis.PyQt.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                                 QGridLayout, QLabel, QLineEdit, QMessageBox,
                                 QPlainTextEdit, QSizePolicy, QSpinBox,
                                 QVBoxLayout, QWizard)

from . import config  # used to pass initial settings
from .aux_classes import QHLine, SurveyWizard, SurveyWizardPage
from .aux_functions import myPrint
from .enums_and_int_flags import PaintMode, SurveyType
from .pg_toolbar import PgToolBar
from .roll_pattern import RollPattern
from .roll_survey import RollSurvey, SurveyList

current_dir = os.path.dirname(os.path.abspath(__file__))
resource_dir = os.path.join(current_dir, 'resources')


# WIZARD  =======================================================================

class LandSurveyWizard(SurveyWizard):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.nTemplates = 1                                                     # nr of templates in a design. Will be affected by brick, slant & zigzag geometries
        self.surveySize = QSizeF(config.deployInline, config.deployX_line)      # initial survey size; determined by src area for orthogonal surveys and rec area for parallel

        self.addPage(Page_1(self))
        self.addPage(Page_2(self))
        self.addPage(Page_3(self))
        self.addPage(Page_4(self))
        self.addPage(Page_5(self))
        self.addPage(Page_6(self))
        self.addPage(Page_7(self))
        self.addPage(Page_8(self))

        self.setWindowTitle('Land & OBN Seismic Survey Wizard')
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

        self.setTitle('1. Template Properties')
        self.setSubTitle('Enter survey type and template properties')

        myPrint('page 1 init')

        # create some widgets
        self.name = QLineEdit()
        self.type = QComboBox()

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

        self.chkLinePntAlign = QCheckBox('Match point intervals (SPI && RPI) to line intervals (SLI && RLI)')

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
        for item in SurveyList[:-1]:                                            # skip last item from list; streamer survey
            self.type.addItem(item)

        self.name.setStyleSheet('QLineEdit  { background-color : lightblue} ')
        self.type.setStyleSheet('QComboBox  { background-color : lightblue} ')

        # set the page layout
        layout = QGridLayout()

        row = 0
        layout.addWidget(QLabel('Select the correct survey <b>type</b>'), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.type, row, 0, 1, 4)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('Provide an appropriate <b>description</b> for the survey (default is survey type)'), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.name, row, 0, 1, 4)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Source</b> and <b>receiver</b> basic template configuration'), row, 0, 1, 4)

        # » Page 2 (this page) defines nr of lines and line/point intervals of the template<br>
        # » Page 3 defines the bin grid, used to combine traces for 'fold' calculations<br>
        # » Page 4 defines the starting point and the length of source and receiver lines <br>
        # » Page 5 defines how and how often a template is rolled to a new location<br>
        # » Page 6 defines the offset range valid for binning purposes<br>

        strLocal = """
        The template(s) consist(s) of one or more source and receiver lines<br>
        Only sources and receivers within the same template result in valid traces<br>
        <br>
        You can freely move forwards and backwards through the wizard. Please note:<br>
        » changes made in later pages won't introduce changes in the earlier pages<br>
        » changes in earlier pages can affect parameters in the later pages. E.g. :<br>
        &nbsp;&nbsp;· Changing receiver line interval (RLI) may impact the salvo length (NSP)<br>
        &nbsp;&nbsp;· But changing the salvo length (NSP) won't affect the receiver line interval (RLI)<br>
        """

        row += 1
        layout.addWidget(QLabel(strLocal), row, 0, 1, 4)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        self.templateLabel = QLabel('Nr <b>active</b> source and receiver lines in a template')
        layout.addWidget(self.templateLabel, row, 0, 1, 4)

        row += 1
        layout.addWidget(self.nsl, row, 0)

        self.nslLabel = QLabel('<b>NSL</b> Nr Src Line(s)')
        layout.addWidget(self.nslLabel, row, 1)   ##

        layout.addWidget(self.nrl, row, 2)
        layout.addWidget(QLabel('<b>NRL</b> Nr Rec Lines [&#8593;]'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        self.lineLabel = QLabel('<b>Line</b> spacing between sources and receivers')
        layout.addWidget(self.lineLabel, row, 0, 1, 4)

        row += 1
        layout.addWidget(self.sli, row, 0)
        self.sliLabel = QLabel('<b>SLI</b> Src Line Int [m&#8594;]')   ##
        layout.addWidget(self.sliLabel, row, 1)   ##

        layout.addWidget(self.rli, row, 2)
        layout.addWidget(QLabel('<b>RLI</b> Rec Line Int [m&#8593;]'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        self.pointLabel = QLabel('<b>Point</b> spacing between sources and receivers')
        layout.addWidget(self.pointLabel, row, 0, 1, 4)

        row += 1
        layout.addWidget(self.spi, row, 0)
        self.spiLabel = QLabel('<b>SLI</b> Src Point Int [m&#8593;]')   ##
        layout.addWidget(self.spiLabel, row, 1)
        layout.addWidget(self.rpi, row, 2)
        layout.addWidget(QLabel('<b>RPI</b> Rec Point Int [m&#8594;]'), row, 3)

        row += 1
        layout.addWidget(self.chkLinePntAlign, row, 0, 1, 4)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        # controls for specific survey types (parallel, slanted, brick, zigzag)
        row += 1
        self.slantH = QLabel('<b>Slanted</b> template source configuration')    # slant header
        layout.addWidget(self.slantH, row, 0, 1, 4)                             # slant header

        row += 1
        self.slantL = QLabel("Nr RLI's needed to move up one complete SLI")     # slant label
        layout.addWidget(self.slantS, row, 0)                                   # slant spinbox
        layout.addWidget(self.slantL, row, 1, 1, 3)                             # slant label

        row += 1
        self.slantT = QLabel('Slant angle [deg] (deviation from orthogonal)')   # slant text
        layout.addWidget(self.slantA, row, 0)                                   # slant spinbox
        layout.addWidget(self.slantT, row, 1, 1, 3)                             # slant label

        row += 1
        self.brickH = QLabel('<b>Brick </b> template source configuration')     # brick header
        layout.addWidget(self.brickH, row, 0, 1, 2)                             # brick header
        layout.addWidget(self.chkBrickMatchRpi, row, 2, 1, 2)                   # checkbox - match or not

        row += 1
        self.brickL = QLabel('<b></b>Distance of 2nd- to 1st source line [m&#8594;]')         # brick label (force html)
        layout.addWidget(self.brickS, row, 0)                                   # brick spinbox
        layout.addWidget(self.brickL, row, 1, 1, 2)                             # brick label

        row += 1
        self.zigzagH = QLabel('<b>Zigzag </b> template source configuration')   # zigzag header
        layout.addWidget(self.zigzagH, row, 0, 1, 2)                            # zigzag header

        row += 1
        self.zigzagL = QLabel('Nr zig-zags [1 - 3]')                            # zigzag label
        layout.addWidget(self.zigzagS, row, 0)                                  # zigzag spinbox
        layout.addWidget(self.zigzagL, row, 1)                                  # zigzag label
        layout.addWidget(self.chkMirrorOddEven, row, 2, 1, 2)                   # checkbox - mirror or not

        self.setLayout(layout)

        # register fields for variable access in other Wizard Pages
        # see: https://stackoverflow.com/questions/35187729/pyqt5-double-spin-box-returning-none-value
        self.registerField('nsl', self.nsl, 'value')                            # nr source lines
        self.registerField('nrl', self.nrl, 'value')                            # nr receiver lines
        self.registerField('sli', self.sli, 'value')                            # source line interval
        self.registerField('rli', self.rli, 'value')                            # receiver line interval
        self.registerField('spi', self.spi, 'value')                            # source point interval
        self.registerField('rpi', self.rpi, 'value')                            # receiver point interval
        self.registerField('type', self.type)                                   # Survey type
        self.registerField('name', self.name)                                   # Survey name

        self.registerField('chkLinePntAlign', self.chkLinePntAlign)             # Match point intervals (SPI && RPI) to line intervals (SLI && RLI)

        self.registerField('nslant', self.slantS, 'value')                      # nr templates in a slanted survey
        self.registerField('brk', self.brickS, 'value')                         # brick offset distance for 2nd source line
        self.registerField('nzz', self.zigzagS, 'value')                        # nr source fleets in a zigzag survey
        self.registerField('mir', self.chkMirrorOddEven)                        # mirror od/even templates

        # connect signals to slots
        self.type.currentIndexChanged.connect(self.evt_type_indexChanged)

        # signals and slots for when editing is finished
        self.sli.editingFinished.connect(self.evt_sli_editingFinished)          # for source line interval
        self.spi.editingFinished.connect(self.evt_spi_editingFinished)          # for source point interval
        self.rli.editingFinished.connect(self.evt_rli_editingFinished)          # for receiver line interval
        self.rpi.editingFinished.connect(self.evt_rpi_editingFinished)          # for receiver point interval

        self.chkLinePntAlign.stateChanged.connect(self.evt_align_stateChanged)
        self.chkBrickMatchRpi.stateChanged.connect(self.evt_match_stateChanged)

        self.slantS.valueChanged.connect(self.evt_slantS_valueChanged)
        self.brickS.editingFinished.connect(self.evt_brickS_editingFinished)

        # start values in the constructor, taken from config.py
        self.nsl.setValue(config.nsl)
        self.nrl.setValue(config.nrl)
        self.sli.setValue(config.sli)
        self.rli.setValue(config.rli)
        self.spi.setValue(config.spi)
        self.rpi.setValue(config.rpi)
        self.name.setText(config.surveyName)
        self.brickS.setValue(config.brick)

        # variables to keep survey dimensions more or less the same, when editing
        self.old_rpi = config.rpi
        self.old_rli = config.rli
        self.old_sli = config.sli

        # hide optional controls for non-orthogonal surveys
        slanted = False
        self.slantH.setVisible(slanted)
        self.slantS.setVisible(slanted)
        self.slantL.setVisible(slanted)
        self.slantA.setVisible(slanted)
        self.slantT.setVisible(slanted)

        brick = False
        self.brickH.setVisible(brick)
        self.brickS.setVisible(brick)
        self.brickL.setVisible(brick)
        self.chkBrickMatchRpi.setVisible(brick)

        Zigzag = False
        self.zigzagH.setVisible(Zigzag)
        self.zigzagS.setVisible(Zigzag)
        self.zigzagL.setVisible(Zigzag)
        self.chkMirrorOddEven.setVisible(Zigzag)

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        myPrint('initialize page 1')
        self.chkLinePntAlign.setChecked(True)
        self.chkBrickMatchRpi.setChecked(True)

    def cleanupPage(self):                                                      # needed to update previous page
        myPrint('cleanup of page 1')

    def adjustBingrid(self):
        rpi = self.rpi.value()                                                  # horizontal
        sli = self.sli.value()
        rpi = min(rpi, sli)

        spi = self.spi.value()                                                  # vertical
        rli = self.rli.value()
        spi = min(spi, rli)

        self.setField('binI', 0.5 * rpi)                                        # need to adjust bingrid too
        self.setField('binX', 0.5 * spi)

        # note page(x) starts with a ZERO index; therefore pag(0) == Page_1
        self.parent.page(3).evt_binImin_editingFinished(plot=False)             # need to update binning area too
        self.parent.page(3).evt_binIsiz_editingFinished(plot=False)
        self.parent.page(3).evt_binXmin_editingFinished(plot=False)
        self.parent.page(3).evt_binXsiz_editingFinished(plot=False)

    def evt_align_stateChanged(self):                                           # alignment state changed
        self.evt_sli_editingFinished()                                          # update dependent controls
        self.evt_rli_editingFinished()
        self.evt_spi_editingFinished()
        self.evt_rpi_editingFinished()

    def evt_match_stateChanged(self):                                           # match state changed
        self.evt_brickS_editingFinished()                                       # update dependent control

    def evt_type_indexChanged(self, index):
        self.nsl.setValue(1)                                                    # reset nr source lines in case we came from zigzag or parallel

        self.sli.setEnabled(True)                                               # in case we disabled this earlier
        self.nsl.setEnabled(True)                                               # for instance with zigzag or parallel

        self.sli.setValue(config.sli)                                           # in case we used parallel earlier
        self.old_sli = config.sli                                               # in case we used parallel earlier

        self.nsl.setValue(config.nsl)
        self.setField('rlr', 1)                                                 # One line to roll
        self.setField('slr', 1)                                                 # One line to roll
        self.setField('sld', round(config.deployInline / (config.slr * config.sli)) + 1)
        self.setField('rld', round(config.deployX_line / (config.rlr * config.rli)) + 1)

        name = SurveyType(index).name                                           # get name from enum
        number = str(config.surveyNumber).zfill(3)                              # fill with leading zeroes
        self.name.setText(f'{name}_{number}')                                   # show the new name
        # self.type = SurveyType(index)                                         # update survey type; no need for this, done automatically

        parallel = index == SurveyType.Parallel.value
        if parallel:
            # self.sli.setEnabled(False)                                          # calculate sli from nsl
            self.templateLabel.setText('In a <b>parallel</b> template, source points run <b>parallel</b> to the receiver lines')
            self.lineLabel.setText('<b>Point</b> spacing between sources and <b>line</b> spacing between receivers')
            self.pointLabel.setText('<b>Line</b> spacing between sources and <b>point</b> spacing between receivers')
            self.sli.setValue(config.sli_par)
            self.nsl.setValue(config.nsl_par)
            self.setField('nrp', config.nrp_par)

            self.nslLabel.setText('<b>NSP</b> Nr Src Points [&#8594;]')
            self.sliLabel.setText('<b>SPI</b> Src Point Int [m&#8594;]')   ##
            self.spiLabel.setText('<b>SLI</b> Src Line Int [m&#8593;]')
        else:
            self.templateLabel.setText('<b>Active</b> source and receiver lines in a template')
            self.lineLabel.setText('<b>Line</b> spacing between sources and receivers')
            self.pointLabel.setText('<b>point</b> spacing between sources and receivers')

            self.nslLabel.setText('<b>NSL</b> Nr Src Lines [&#8594;]')
            self.sliLabel.setText('<b>SLI</b> Src Line Int [m&#8594;]')   ##
            self.spiLabel.setText('<b>SPI</b> Src Point Int [m&#8593;]')

        slanted = index == SurveyType.Slanted.value
        self.slantH.setVisible(slanted)
        self.slantS.setVisible(slanted)
        self.slantL.setVisible(slanted)
        self.slantA.setVisible(slanted)
        self.slantT.setVisible(slanted)
        if slanted:
            self.evt_slantS_valueChanged(self.slantS.value())

        brick = index == SurveyType.Brick.value
        self.brickH.setVisible(brick)
        self.brickS.setVisible(brick)
        self.brickL.setVisible(brick)
        self.chkBrickMatchRpi.setVisible(brick)

        zigzag = index == SurveyType.Zigzag.value
        self.zigzagH.setVisible(zigzag)
        self.zigzagS.setVisible(zigzag)
        self.zigzagL.setVisible(zigzag)
        self.chkMirrorOddEven.setVisible(zigzag)

        if zigzag:
            self.nsl.setEnabled(False)                                          # always 1 source line
            self.nsl.setValue(2)

            self.sli.setEnabled(False)
            rli = self.field('rli')                                             # get variables from field names
            rpi = self.field('rpi')
            spi = self.field('spi')
            nsp = max(round(rli / spi), 1)
            self.sli.setValue(nsp * rpi)

        self.update()                                                           # update GUI

    def evt_sli_editingFinished(self):
        nrIntervals = max(round(self.sli.value() / self.rpi.value()), 1)
        rpiValue = self.sli.value() / nrIntervals

        if self.chkLinePntAlign.isChecked():
            if self.field('type') != SurveyType.Zigzag.value:                   # don't update rpi in case of zigzag
                self.rpi.setValue(rpiValue)                                     # for zigzag sli is 'fixed' by other variables

        nslant = self.field('nslant')                                           # get variable from field name
        self.evt_slantS_valueChanged(nslant)                                    # update the slant angle for slanted surveys

        sld = self.field('sld')                                                 # get variables from field names
        slr = self.field('slr')                                                 # get variables from field names
        sizI = sld * slr * self.old_sli
        sld = max(round(sizI / self.sli.value()), 1)
        self.setField('sld', sld)                                               # adjust nr source line deployments

        self.old_sli = self.sli.value()
        self.adjustBingrid()

    def evt_rli_editingFinished(self):
        nrIntervals = max(round(self.rli.value() / self.spi.value()), 1)
        spiValue = self.rli.value() / nrIntervals

        if self.chkLinePntAlign.isChecked():
            self.spi.setValue(spiValue)
            # Affects Page 4
            self.setField('nsp', nrIntervals)                                   # RLI has been altered; adjust the salvo length

        if self.field('type') == SurveyType.Zigzag.value:
            self.sli.setValue(nrIntervals * self.rpi.value())

        # if self.field("type") == SurveyType.Parallel.value:                     # in case of a parallel template
        #     sliValue = self.rli.value() / self.nsl.value()
        #     self.sli.setValue(sliValue)

        nslant = self.field('nslant')                                           # get variable from field name
        self.evt_slantS_valueChanged(nslant)                                    # update the slant angle for slanted surveys

        rld = self.field('rld')                                                 # get variables from field names
        rlr = self.field('rlr')                                                 # get variables from field names
        sizX = rld * rlr * self.old_rli
        rld = max(round(sizX / self.rli.value()), 1)
        self.setField('rld', rld)                                               # adjust nr receiver line deployments

        self.old_rli = self.rli.value()
        self.adjustBingrid()

    def evt_spi_editingFinished(self):
        nsp = self.field('nsp')                                                 # get variables from field names
        rli = self.rli.value()
        rpi = self.rpi.value()
        spi = self.spi.value()

        if self.field('type') == SurveyType.Parallel.value:                     # in case of a parallel template
            pass
            # # set initial offset values
            # lenS = self.parent.surveySize.width() + config.spreadlength
            # nsp = round(lenS / spi) + 1                                         # SPI has been altered; adjust the salvo length
        else:
            nrIntervals = max(round(rli / spi), 1)
            spiValue = rli / nrIntervals

            if self.chkLinePntAlign.isChecked():                                # write back the aligned value
                self.spi.setValue(spiValue)

            if self.field('type') == SurveyType.Zigzag.value:                   # need to adjust sli for zigzag
                self.sli.setValue(nrIntervals * rpi)

            nsp = max(round(rli / spi), 1)
            self.setField('nsp', nsp)                                           # Adjust the salvo length

        self.adjustBingrid()

    def evt_rpi_editingFinished(self):
        nrIntervals = max(round(self.sli.value() / self.rpi.value()), 1)
        rpiValue = self.sli.value() / nrIntervals

        if self.chkLinePntAlign.isChecked():
            self.rpi.setValue(rpiValue)

        if self.field('type') == SurveyType.Zigzag.value:
            nsp = self.field('nsp')                                             # get variables from field names
            self.sli.setValue(nsp * self.rpi.value())

        nrp = self.field('nrp')                                                 # get variables from field names
        spreadlength = nrp * self.old_rpi                                       # current receiver line length
        nrp = max(round(spreadlength / self.rpi.value()), 1)                    # RPI has been altered; adjust nrp
        self.setField('nrp', nrp)                                               # save its value

        self.old_rpi = self.rpi.value()
        self.adjustBingrid()

    def evt_slantS_valueChanged(self, i):
        sli = self.field('sli')                                                 # get variables from field names
        rli = self.field('rli')
        angle = 90.0 - math.degrees(math.atan2(i * rli, sli))                   # get the slant angle (deviation from orthogonal
        self.slantA.setText(f'{angle:.3f}')                                     # put it back in the edit window

    def evt_brickS_editingFinished(self):
        sli = self.field('sli')                                                 # get variable from field names
        brick = self.brickS.value()
        brick = min(sli - 1.0, brick)
        if self.chkBrickMatchRpi.isChecked():
            rpi = self.field('rpi')                                             # get variable from field names
            nrIntervals = max(round(brick / rpi), 1)
            if nrIntervals * rpi == sli:
                nrIntervals -= 1
            brick = rpi * nrIntervals
        self.brickS.setValue(brick)


# Page_2 =======================================================================
# 2. Template Properties - Enter Spread and Salvo details


class Page_2(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setTitle('2. Template Properties')
        self.setSubTitle('Enter Spread and Salvo details')

        myPrint('page 2 init')

        # to support plotting
        self.rect = False
        self.XisY = True
        self.antA = False
        self.grid = True

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
        layout.addWidget(QLabel('<b>SPREAD</b> definition  [nr &#8594;]'), row, 0)
        layout.addWidget(QLabel('<b>SALVO</b> definition  [nr &#8593;]'), row, 2)

        row += 1
        layout.addWidget(self.chkNrecMatch, row, 0, 1, 2)
        layout.addWidget(self.chkNsrcMatch, row, 2, 1, 2)

        row += 1
        layout.addWidget(self.chkNrecKnown, row, 0, 1, 2)
        layout.addWidget(self.chkNsrcKnown, row, 2, 1, 2)

        row += 1
        layout.addWidget(self.nrp, row, 0)
        layout.addWidget(QLabel('Nr channels/cable'), row, 1)
        layout.addWidget(self.nsp, row, 2)
        layout.addWidget(QLabel('Nr shots/traverse'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Inline</b> [&#8594;] offset range relative <b>first</b> shot line'), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.offImin, row, 0)
        layout.addWidget(QLabel('Minimum [m]'), row, 1)
        layout.addWidget(self.offImax, row, 2)
        layout.addWidget(QLabel('Maximum [m]'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('<b>Crossline</b> [&#8593;] offset range relative <b>first</b> receiver line'), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.offXmin, row, 0)
        layout.addWidget(QLabel('Minimum [m]'), row, 1)
        layout.addWidget(self.offXmax, row, 2)
        layout.addWidget(QLabel('Maximum [m]'), row, 3)

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

        ## self.nrp.setValue(round(config.spreadlength/config.rpi))
        ## self.nsp.setValue(round(config.rli/config.spi))

        self.registerField('nsp', self.nsp, 'value')
        self.registerField('nrp', self.nrp, 'value')
        self.registerField('offImin', self.offImin, 'value')
        self.registerField('offImax', self.offImax, 'value')
        self.registerField('offXmin', self.offXmin, 'value')
        self.registerField('offXmax', self.offXmax, 'value')

        # connect signals to slots for checkboxes
        self.chkNrecKnown.toggled.connect(self.evt_chkNrecKnown_toggled)        # work from numbers or offsets
        self.chkNsrcKnown.toggled.connect(self.evt_chkNsrcKnown_toggled)
        self.chkNrecMatch.toggled.connect(self.evt_chkNrecMatch_toggled)        # require NRP & NSP, matching to SLI & RLI
        self.chkNsrcMatch.toggled.connect(self.evt_chkNsrcMatch_toggled)

        # connect signals to slots for edit controls
        self.nsp.editingFinished.connect(self.evt_nsp_editingFinished)      # evaluate new nsp
        self.nrp.editingFinished.connect(self.evt_nrp_editingFinished)      # evaluate new nrp
        self.offImin.editingFinished.connect(self.evt_offImin_editingFinished)  # evaluate new offsets
        self.offImax.editingFinished.connect(self.evt_offImax_editingFinished)
        self.offXmin.editingFinished.connect(self.evt_offxmin_editingFinished)
        self.offXmax.editingFinished.connect(self.evt_offXmax_editingFinished)

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        myPrint('initialize page 2')

        # disable required edit controls
        chkd = self.chkNrecKnown.isChecked()
        self.nrp.setEnabled(chkd)
        self.offImax.setEnabled(not chkd)

        chkd = self.chkNsrcKnown.isChecked()
        self.nsp.setEnabled(chkd)
        self.offXmax.setEnabled(not chkd)

        # get variables from field names
        nrl = self.field('nrl')
        nsl = self.field('nsl')
        sli = self.field('sli')
        rli = self.field('rli')
        spi = self.field('spi')
        rpi = self.field('rpi')
        nsp = self.field('nsp')
        nrp = self.field('nrp')
        typ = self.field('type')

        # first RESET the survey object, so we can start with it from scratch
        self.parent.survey = RollSurvey()

        # fill in the survey object information we already know now
        self.parent.survey.name = self.field('name')                            # Survey name
        self.parent.survey.type = SurveyType(typ)                               # Survey type Enum

        nsla = self.field('nslant')                                             # nr templates in a slanted survey
        nzz = self.field('nzz')                                                 # nr source fleets in a zigzag survey
        mir = self.field('mir')                                                 # mirrored zigzag survey

        # set initial offset values
        templateInShift = 0.5 * (nsl - 1) * sli
        templateX_shift = 0.5 * (nrl - 1) * rli

        self.offImin.setValue(-0.5 * (nrp - 1) * rpi + self.offsetInshift + templateInShift)
        self.offImax.setValue(0.5 * (nrp - 1) * rpi + self.offsetInshift + templateInShift)

        self.offXmin.setValue(-0.5 * (nsp - 1) * spi + self.offsetX_shift + templateX_shift)
        self.offXmax.setValue(0.5 * (nsp - 1) * spi + self.offsetX_shift + templateX_shift)

        # as of Python version 3.10, there is an official switch-case statement.
        # Alas, QGIS 3.28 is using Python v3.9.5 so we have to use if ... elif ... elif etc.
        self.parent.nTemplates = 1
        nSrcSeeds = 1
        if typ == SurveyType.Orthogonal.value:
            pass
        elif typ == SurveyType.Parallel.value:
            pass
        elif typ == SurveyType.Slanted.value:
            self.parent.nTemplates = nsla                                       # as many as needed for the slanted design
        elif typ == SurveyType.Brick.value:
            self.parent.nTemplates = 2                                          # for odd/even templates
        elif typ == SurveyType.Zigzag.value:
            self.parent.nTemplates = 2 if mir else 1                            # for mirrored templates
            nSrcSeeds = 2 * nzz                                                 # every zigzag requires 2 source seeds
        else:
            raise NotImplementedError('unsupported survey type.')

        # Create a survey skeleton, so we can simply update survey properties, without having to instantiate underlying classes
        self.parent.survey.createBasicSkeleton(nTemplates=self.parent.nTemplates, nSrcSeeds=nSrcSeeds, nRecSeeds=1)    # add Block, template(s)

        self.updateParentSurvey()                                               # update the survey object
        self.plot()                                                             # refresh the plot

    def cleanupPage(self):                                                      # needed to update previous page
        myPrint('cleanup of page 2')

    def updateParentSurvey(self):
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
        typ = self.field('type')

        nsla = self.field('nslant')                                             # nr templates in a slanted survey
        brk = self.field('brk')                                                 # brick offset distance
        nzz = self.field('nzz')                                                 # nr source fleets in a zigzag survey
        mir = self.field('mir')                                                 # mirrored zigzag survey

        # populate / update the survey skeleton

        # do the patterns here (instead of page 5) as pattern orientation may depend on template type (e.g. zigzag)
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

        # now the patterns have been initialized, initialise the figures with the right color
        # self.parent.survey.patternList[0].calcPatternPicture()                  # not needed; done in calcBoundingRect()
        # self.parent.survey.patternList[1].calcPatternPicture()                  # not needed; done in calcBoundingRect()

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

        # deal with different survey types
        if typ == SurveyType.Orthogonal.value:

            # source
            if nsl > 6:                                                                                         # it is assumed only crossline roll is being used
                nPadding = 0                                                                                    # don't add extra nr recs to the rec lines
            else:
                nPadding = (nsl - 1) * round(sli / rpi)                                                         # lengthen rec lines with nr recs between the source lines
            self.parent.survey.blockList[0].templateList[0].seedList[0].origin.setX(0.0)                        # Seed origin; source inline at x = 0.0
            self.parent.survey.blockList[0].templateList[0].seedList[0].origin.setY(offXmin)                    # Seed origin; positive number

            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[0].steps = 1              # nr planes
            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[0].increment.setX(0.0)    # n/a
            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[0].increment.setY(0.0)    # n/a

            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[1].steps = nsl            # nsl
            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[1].increment.setX(sli)    # sli
            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[1].increment.setY(0.0)    # horizontal

            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[2].steps = nsp            # nsp
            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[2].increment.setX(0.0)    # vertical
            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[2].increment.setY(spi)    # spi

            # receiver
            self.parent.survey.blockList[0].templateList[0].seedList[1].origin.setX(offImin)                    # Seed origin; negative number
            self.parent.survey.blockList[0].templateList[0].seedList[1].origin.setY(0.0)                        # Seed origin; receiver x-line at 0.0

            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[0].steps = 1              # nr planes
            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[0].increment.setX(0.0)    # n/a
            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[0].increment.setY(0.0)    # n/a

            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[1].steps = nrl            # nrl
            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[1].increment.setX(0.0)    # vertical
            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[1].increment.setY(rli)    # rli

            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[2].steps = nrp + nPadding  # nrp
            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[2].increment.setX(rpi)    # rpi
            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[2].increment.setY(0.0)    # horizontal

        elif typ == SurveyType.Parallel.value:
            # source
            nPadding = 0                                                                                        # no paddding required
            self.parent.survey.blockList[0].templateList[0].seedList[0].origin.setX(0.0)                        # Seed origin
            self.parent.survey.blockList[0].templateList[0].seedList[0].origin.setY(offXmin)                    # Seed origin

            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[0].steps = 1              # nr planes
            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[0].increment.setX(0.0)    # n/a
            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[0].increment.setY(0.0)    # n/a

            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[1].steps = nsp            # nsp
            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[1].increment.setX(0.0)    # vertical
            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[1].increment.setY(spi)    # spi

            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[2].steps = nsl            # nsl
            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[2].increment.setX(sli)    # sli
            self.parent.survey.blockList[0].templateList[0].seedList[0].grid.growList[2].increment.setY(0.0)    # horizontal

            # receiver
            self.parent.survey.blockList[0].templateList[0].seedList[1].origin.setX(offImin)                    # Seed origin
            self.parent.survey.blockList[0].templateList[0].seedList[1].origin.setY(0.0)                        # Seed origin

            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[0].steps = 1              # nr planes
            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[0].increment.setX(0.0)    # n/a
            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[0].increment.setY(0.0)    # n/a

            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[1].steps = nrl            # nrl
            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[1].increment.setX(0.0)    # vertical
            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[1].increment.setY(rli)    # rli

            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[2].steps = nrp + nPadding   # nrp
            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[2].increment.setX(rpi)    # rpi
            self.parent.survey.blockList[0].templateList[0].seedList[1].grid.growList[2].increment.setY(0.0)    # horizontal

        elif typ == SurveyType.Slanted.value:
            nPadding = round(sli / rpi)                                                                         # as many rec points as there are between 2 src lines
            nPadding += (nsl - 1) * round(sli / rpi)                                                            # add nr recs between two source lines

            ratio = sli / (nsla * rli)                                                                          # get the ratio from the slant angle

            for i in range(nsla):
                # source
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setX(i * rli * ratio)        # Seed origin
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setY(offXmin + i * rli)      # Seed origin
                self.parent.survey.blockList[0].templateList[i].seedList[0].bAzimuth = True                     # Pattern in deviated direction

                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[0].steps = 1              # nr planes
                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[0].increment.setX(0.0)    # n/a
                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[0].increment.setY(0.0)    # n/a

                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[1].steps = nsl            # nsl
                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[1].increment.setX(sli)    # sli
                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[1].increment.setY(0.0)    # horizontal

                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[2].steps = nsp            # nsp
                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[2].increment.setX(spi * ratio)   # slanted
                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[2].increment.setY(spi)    # spi

                # receiver
                self.parent.survey.blockList[0].templateList[i].seedList[1].origin.setX(offImin)                    # Seed origin
                self.parent.survey.blockList[0].templateList[i].seedList[1].origin.setY(i * rli)                    # Seed origin

                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[0].steps = 1              # nr planes
                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[0].increment.setX(0.0)    # n/a
                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[0].increment.setY(0.0)    # n/a

                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].steps = nrl            # nrl
                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].increment.setX(0.0)    # vertical
                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].increment.setY(rli)    # rli

                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].steps = nrp + nPadding  # nrp
                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].increment.setX(rpi)    # rpi
                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].increment.setY(0.0)    # horizontal

        elif typ == SurveyType.Brick.value:
            nPadding = round(brk / rpi)                                                                             # shift in source lines
            nPadding += (nsl - 1) * round(sli / rpi)                                                                # add nr recs between two source lines

            for i in range(self.parent.nTemplates):
                # source
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setX(i * brk)                    # Seed origin
                self.parent.survey.blockList[0].templateList[i].seedList[0].origin.setY(offXmin + i * rli)          # Seed origin

                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[0].steps = 1              # nr planes
                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[0].increment.setX(0.0)    # n/a
                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[0].increment.setY(0.0)    # n/a

                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[1].steps = nsl            # nsl
                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[1].increment.setX(sli)    # sli
                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[1].increment.setY(0.0)    # horizontal

                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[2].steps = nsp            # nsp
                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[2].increment.setX(0.0)    # vertical
                self.parent.survey.blockList[0].templateList[i].seedList[0].grid.growList[2].increment.setY(spi)    # spi

                # receiver
                self.parent.survey.blockList[0].templateList[i].seedList[1].origin.setX(offImin)                    # Seed origin
                self.parent.survey.blockList[0].templateList[i].seedList[1].origin.setY(i * rli)                    # Seed origin

                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[0].steps = 1              # nr planes
                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[0].increment.setX(0.0)    # n/a
                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[0].increment.setY(0.0)    # n/a

                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].steps = nrl            # nrl
                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].increment.setX(0.0)    # vertical
                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[1].increment.setY(rli)    # rli

                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].steps = nrp + nPadding  # nrp
                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].increment.setX(rpi)    # rpi
                self.parent.survey.blockList[0].templateList[i].seedList[1].grid.growList[2].increment.setY(0.0)    # horizontal

        elif typ == SurveyType.Zigzag.value:
            nPadding = 2 * (round(rli / spi) + nzz - 1) - 1                       # zig + zag distance, accounted for nzz
            # no need to adjust for nsl; is always 1 for zigzag

            # The zigzag template is a special case, as it leads to (max) two templates with a lot of source seeds.
            # A 'zig' and a 'zag' combined can be seen as two seperate (slanted) source lines, together defining 'sli'

            # Some zigzag implementations allow for a single zig/zag point at each end of a zig/zag source segment
            # These implementations are inferior, as they result in reduced coverage for cmp lines next to the receiver lines
            # Or they create a duplicate SP (=duplicate ray paths) at these VP locations.
            # also, they lead to a discontinuity in the slanted source lines around receiver line crossings
            # Therefore, this wizard only creates zigzags with double end points near the adjacent receiver line

            # It is standard practice to mirror odd and even templates, as this provides continuity in the source lines
            # this allows for an FKxKy analysis, both in the common source- and in the common receiver domain

            for i in range(0, 2 * nzz, 2):
                # source up
                self.parent.survey.blockList[0].templateList[0].seedList[i].origin.setX(i * rpi)              # Seed origin
                self.parent.survey.blockList[0].templateList[0].seedList[i].origin.setY(offXmin)              # Seed origin

                self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[0].steps = 1              # nr planes
                self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[0].increment.setX(0.0)    # n/a
                self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[0].increment.setY(0.0)    # n/a

                self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[1].steps = 1              # nr lines
                self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[1].increment.setX(0.0)    # n/a
                self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[1].increment.setY(0.0)    # n/a

                self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[2].steps = nsp           # nsp
                self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[2].increment.setX(rpi)   # rpi
                self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[2].increment.setY(spi)   # spi

                # source down
                self.parent.survey.blockList[0].templateList[0].seedList[i + 1].origin.setX(sli + i * rpi)        # Seed origin
                self.parent.survey.blockList[0].templateList[0].seedList[i + 1].origin.setY(offXmin + rli - spi)  # Seed origin

                self.parent.survey.blockList[0].templateList[0].seedList[i + 1].grid.growList[0].steps = 1              # nr planes
                self.parent.survey.blockList[0].templateList[0].seedList[i + 1].grid.growList[0].increment.setX(0.0)    # n/a
                self.parent.survey.blockList[0].templateList[0].seedList[i + 1].grid.growList[0].increment.setY(0.0)    # n/a

                self.parent.survey.blockList[0].templateList[0].seedList[i + 1].grid.growList[1].steps = 1              # nr lines
                self.parent.survey.blockList[0].templateList[0].seedList[i + 1].grid.growList[1].increment.setX(0.0)    # n/a
                self.parent.survey.blockList[0].templateList[0].seedList[i + 1].grid.growList[1].increment.setY(0.0)    # n/a

                self.parent.survey.blockList[0].templateList[0].seedList[i + 1].grid.growList[2].steps = nsp           # nsp
                self.parent.survey.blockList[0].templateList[0].seedList[i + 1].grid.growList[2].increment.setX(rpi)   # rpi
                self.parent.survey.blockList[0].templateList[0].seedList[i + 1].grid.growList[2].increment.setY(-spi)  # spi

            # receiver
            i = 2 * nzz
            self.parent.survey.blockList[0].templateList[0].seedList[i].origin.setX(offImin)                # Seed origin
            self.parent.survey.blockList[0].templateList[0].seedList[i].origin.setY(0)                      # Seed origin

            self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[0].steps = 1              # nr planes
            self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[0].increment.setX(0.0)    # n/a
            self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[0].increment.setY(0.0)    # n/a

            self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[1].steps = nrl             # nrl
            self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[1].increment.setX(0.0)   # vertical
            self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[1].increment.setY(rli)   # rli

            self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[2].steps = nrp + nPadding  # nrp
            self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[2].increment.setX(rpi)   # rpi
            self.parent.survey.blockList[0].templateList[0].seedList[i].grid.growList[2].increment.setY(0.0)   # horizontal

            if mir:                                                             # now do the second template (templateList[1])
                for i in range(0, 2 * nzz, 2):
                    # source up
                    self.parent.survey.blockList[0].templateList[1].seedList[i].origin.setX(i * rpi)              # Seed origin
                    self.parent.survey.blockList[0].templateList[1].seedList[i].origin.setY(offXmin + 2.0 * rli - spi)   # Seed origin

                    self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[0].steps = 1              # nr planes
                    self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[0].increment.setX(0.0)    # n/a
                    self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[0].increment.setY(0.0)    # n/a

                    self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[1].steps = 1              # nr lines
                    self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[1].increment.setX(0.0)    # n/a
                    self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[1].increment.setY(0.0)    # n/a

                    self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[2].steps = nsp            # nsp
                    self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[2].increment.setX(rpi)    # rpi
                    self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[2].increment.setY(-spi)   # spi

                    # source down
                    self.parent.survey.blockList[0].templateList[1].seedList[i + 1].origin.setX(sli + i * rpi)        # Seed origin
                    self.parent.survey.blockList[0].templateList[1].seedList[i + 1].origin.setY(offXmin + rli)        # Seed origin

                    self.parent.survey.blockList[0].templateList[1].seedList[i + 1].grid.growList[0].steps = 1              # nr planes
                    self.parent.survey.blockList[0].templateList[1].seedList[i + 1].grid.growList[0].increment.setX(0.0)    # n/a
                    self.parent.survey.blockList[0].templateList[1].seedList[i + 1].grid.growList[0].increment.setY(0.0)    # n/a

                    self.parent.survey.blockList[0].templateList[1].seedList[i + 1].grid.growList[1].steps = 1              # nr lines
                    self.parent.survey.blockList[0].templateList[1].seedList[i + 1].grid.growList[1].increment.setX(0.0)    # n/a
                    self.parent.survey.blockList[0].templateList[1].seedList[i + 1].grid.growList[1].increment.setY(0.0)    # n/a

                    self.parent.survey.blockList[0].templateList[1].seedList[i + 1].grid.growList[2].steps = nsp           # nsp
                    self.parent.survey.blockList[0].templateList[1].seedList[i + 1].grid.growList[2].increment.setX(rpi)   # rpi
                    self.parent.survey.blockList[0].templateList[1].seedList[i + 1].grid.growList[2].increment.setY(spi)  # spi

                # receiver
                i = 2 * nzz
                self.parent.survey.blockList[0].templateList[1].seedList[i].origin.setX(offImin)                # Seed origin
                self.parent.survey.blockList[0].templateList[1].seedList[i].origin.setY(rli)                    # Seed origin

                self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[0].steps = 1              # nr planes
                self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[0].increment.setX(0.0)    # n/a
                self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[0].increment.setY(0.0)    # n/a

                self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[1].steps = nrl             # nrl
                self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[1].increment.setX(0.0)   # vertical
                self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[1].increment.setY(rli)   # rli

                self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[2].steps = nrp + nPadding  # nrp
                self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[2].increment.setX(rpi)   # rpi
                self.parent.survey.blockList[0].templateList[1].seedList[i].grid.growList[2].increment.setY(0.0)   # horizontal
        else:
            raise NotImplementedError('unsupported survey type.')

        self.parent.survey.calcSeedData()                                       # needed for circles, spirals & well-seeds; may affect bounding box
        self.parent.survey.calcBoundingRect()                                   # (re)calculate extent of survey

    def evt_chkNrecKnown_toggled(self, chkd):                                   # toggle enabled status for 2 controls
        self.nrp.setEnabled(chkd)
        self.offImax.setEnabled(not chkd)

    def evt_chkNsrcKnown_toggled(self, chkd):                                   # toggle enabled status for 2 controls
        self.nsp.setEnabled(chkd)
        self.offXmax.setEnabled(not chkd)

    def evt_chkNrecMatch_toggled(self):
        nrp = self.field('nrp')
        self.alignRecPoints(nrp)

        self.updateParentSurvey()                                               # update the survey object
        self.plot()                                                             # refresh the plot

    def evt_chkNsrcMatch_toggled(self):
        nsp = self.field('nsp')
        self.alignSrcPoints(nsp)

        self.updateParentSurvey()                                               # update the survey object
        self.plot()                                                             # refresh the plot

    def alignRecPoints(self, nrp):
        sli = self.field('sli')
        rpi = self.field('rpi')

        if self.chkNrecMatch.isChecked():
            nrIntervals = max(round(nrp * rpi / sli), 1)                        # spreadlength expressed in source line intervals
            nrPtsPerInt = max(round(sli / rpi), 1)                              # nr receivers per source line interval
            nrp = nrIntervals * nrPtsPerInt

        self.nrp.setValue(nrp)                                                  # always set value; so value becomes permanent
        return nrp

    def alignSrcPoints(self, nsp):
        rli = self.field('rli')
        spi = self.field('spi')
        if self.chkNsrcMatch.isChecked():
            nrIntervals = max(round(nsp * spi / rli), 1)                        # salvo length expressed in receiver line intervals
            nrPtsPerInt = max(round(rli / spi), 1)                              # nr source points per receiver line interval
            nsp = nrIntervals * nrPtsPerInt

        self.nsp.setValue(nsp)                                                  # always set value; so value becomes permanent
        return nsp

    def evt_nrp_editingFinished(self):
        sli = self.field('sli')
        rpi = self.field('rpi')
        nsl = self.field('nsl')
        nrp = self.field('nrp')
        nrp = self.alignRecPoints(nrp)                                          # checks nrp and stores its value

        # set the offset values
        templateInShift = 0.5 * (nsl - 1) * sli
        self.offImin.setValue(-0.5 * (nrp - 1) * rpi + self.offsetInshift + templateInShift)
        self.offImax.setValue(0.5 * (nrp - 1) * rpi + self.offsetInshift + templateInShift)

        self.updateParentSurvey()                                               # update the survey object
        self.plot()                                                             # refresh the plot

    def evt_nsp_editingFinished(self):
        rli = self.field('rli')
        spi = self.field('spi')
        nrl = self.field('nrl')
        nsp = self.field('nsp')
        nsp = self.alignSrcPoints(nsp)                                          # checks nsp and stores its value

        # set the  offset values
        templateX_shift = 0.5 * (nrl - 1) * rli
        self.offXmin.setValue(-0.5 * (nsp - 1) * spi + self.offsetX_shift + templateX_shift)
        self.offXmax.setValue(0.5 * (nsp - 1) * spi + self.offsetX_shift + templateX_shift)

        self.updateParentSurvey()                                               # update the survey object
        self.plot()                                                             # refresh the plot

    def evt_offImin_editingFinished(self):
        nsl = self.field('nsl')
        rpi = self.field('rpi')
        nrp = self.field('nrp')
        sli = self.field('sli')

        templateInshift = 0.5 * (nsl - 1) * sli
        halfSpreadLength = 0.5 * (nrp - 1) * rpi

        self.offsetInshift = halfSpreadLength - templateInshift + self.offImin.value()
        self.offImax.setValue(self.offImin.value() + 2 * halfSpreadLength)

        self.updateParentSurvey()                                               # update the survey object
        self.plot()                                                             # refresh the plot

    def evt_offxmin_editingFinished(self):
        nsp = self.field('nsp')
        nrl = self.field('nrl')
        spi = self.field('spi')
        rli = self.field('rli')

        templateX_shift = 0.5 * (nrl - 1) * rli
        halfSalvoLength = 0.5 * (nsp - 1) * spi

        self.offsetX_shift = halfSalvoLength - templateX_shift + self.offXmin.value()
        self.offXmax.setValue(self.offXmin.value() + 2 * halfSalvoLength)

        self.updateParentSurvey()                                               # update the survey object
        self.plot()                                                             # refresh the plot

    def evt_offImax_editingFinished(self):
        nsl = self.field('nsl')
        rpi = self.field('rpi')
        sli = self.field('sli')

        nrp = max(round((self.offImax.value() - self.offImin.value()) / rpi) + 1, 1)  # nr channels over offset range
        nrp = self.alignRecPoints(nrp)                                          # checks nrp and stores its value

        templateInshift = 0.5 * (nsl - 1) * sli
        halfSpreadLength = 0.5 * (nrp - 1) * rpi

        self.offsetInshift = templateInshift - halfSpreadLength + self.offImin.value()
        self.offImax.setValue(self.offImin.value() + 2 * halfSpreadLength)

        self.updateParentSurvey()                                               # update the survey object
        self.plot()                                                             # refresh the plot

    def evt_offXmax_editingFinished(self):
        nrl = self.field('nrl')
        rli = self.field('rli')
        spi = self.field('spi')

        nsp = max(round((self.offXmax.value() - self.offXmin.value()) / spi) + 1, 1)  # nr source points over offset range
        nsp = self.alignSrcPoints(nsp)                                          # checks nsp and stores its value

        templateX_shift = 0.5 * (nrl - 1) * rli
        halfSalvoLength = 0.5 * (nsp - 1) * spi

        self.offsetX_shift = templateX_shift - halfSalvoLength + self.offXmin.value()
        self.offXmax.setValue(self.offXmin.value() + 2 * halfSalvoLength)

        self.updateParentSurvey()                                               # update the survey object
        self.plot()                                                             # refresh the plot

    def plot(self):
        """plot spread and salvo detail"""

        self.plotWidget.plotItem.clear()
        self.plotWidget.setTitle(self.field('name'), color='b', size='12pt')
        self.plotWidget.setAntialiasing(True)

        styles = {'color': '#646464', 'font-size': '10pt'}
        self.plotWidget.setLabel('bottom', 'inline', units='m', **styles)   # shows axis at the bottom, and shows the units label
        self.plotWidget.setLabel('left', 'crossline', units='m', **styles)  # shows axis at the left, and shows the units label
        self.plotWidget.setLabel('top', 'inline', units='m', **styles)      # shows axis at the top, and shows the survey name
        self.plotWidget.setLabel('right', 'crossline', units='m', **styles)   # shows axis at the top, and shows the survey name

        self.parent.survey.paintMode = PaintMode.justPoints                 # justLines
        self.parent.survey.lodScale = 6.0
        item = self.parent.survey

        # 2. Template Properties - Enter Spread and Salvo details
        self.plotWidget.plotItem.addItem(item)

        # Add a marker for the origin
        # oriX = [0.0]
        # oriY = [0.0]
        # orig = self.plotWidget.plot(x=oriX, y=oriY, symbol='h', symbolSize=12, symbolPen=(0, 0, 0, 100), symbolBrush=(180, 180, 180, 100))


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
        self.binI.setRange(0.01, 10000.0)
        self.binX.setRange(0.01, 10000.0)

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
        The wizard created receiver lines starting at y = 0 (along the x-axis)<br>
        and source lines that started at x = 0 (along the y-axis).<br><br>
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
        self.binI.editingFinished.connect(self.evt_bin_editingFinished)         # see when editing is finished for bin values
        self.binX.editingFinished.connect(self.evt_bin_editingFinished)

        self.chkBingridAlign.toggled.connect(self.evt_BingridAlign_toggled)

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        myPrint('initialize page 3')
        self.alignBingrid()
        self.updateParentSurvey()

        # from other pages
        nrl = self.field('nrl')
        nrp = self.field('nrp')
        nsl = self.field('nsl')
        rpi = self.field('rpi')
        sli = self.field('sli')
        rlr = self.field('rlr')
        slr = self.field('slr')
        typ = self.field('type')

        binI = self.field('binI')
        binX = self.field('binX')

        lenI = nrp * rpi
        if typ == SurveyType.Parallel.value:                                    # make exeption for parallel template, as nrp will be excessive (whole spread)
            spread = nrp * rpi
            salvo = nsl * sli
            lenI = max(abs(spread - salvo), 6000)                               # a least 6 km inline offset

        foldI = 0.5 * lenI / (slr * sli)
        foldX = 0.5 * nrl / rlr
        foldT = foldI * foldX

        foldText = f'Max fold: {foldI:.1f} inline, {foldX:.1f} x-line, {foldT:.1f} fold total in {binI:.1f} x {binX:.1f} m bins'

        self.msg.setText(foldText)

        self.plot()                                                             # refresh the plot

    def cleanupPage(self):                                                      # needed to update previous page
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

        self.parent.survey.paintMode = PaintMode.justPoints                     # justLines
        self.parent.survey.lodScale = 6.0
        item = self.parent.survey

        # 3. Template Properties - Enter the bin grid properties
        self.plotWidget.plotItem.addItem(item)

        # Add a marker for the origin
        # oriX = [0.0]
        # oriY = [0.0]
        # orig = self.plotWidget.plot(x=oriX, y=oriY, symbol='h', symbolSize=12, symbolPen=(0, 0, 0, 100), symbolBrush=(180, 180, 180, 100))

    def updateParentSurvey(self):
        # populate / update the survey skeleton

        rli = self.field('rli')
        sli = self.field('sli')
        binI = self.field('binI')
        binX = self.field('binX')

        xTicks = [sli, binI]                                                    # tick interval, depending on zoom level
        yTicks = [rli, binX]                                                    # tick interval, depending on zoom level

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

        surveyCenter = self.parent.survey.cmpBoundingRect.center()              # get its cmp-center

        xC = surveyCenter.x()
        yC = surveyCenter.y()
        xR = sli if sli > 100 else 100
        yR = rli if rli > 100 else 100

        self.plotWidget.setXRange(xC - 0.7 * xR, xC + 0.7 * xR)                 # set scaling for plot
        self.plotWidget.setYRange(yC - 0.7 * yR, yC + 0.7 * yR)

        self.parent.survey.grid.binSize.setX(self.field('binI'))                # inline bin size [m]
        self.parent.survey.grid.binSize.setY(self.field('binX'))                # x-line bin size [m]
        self.parent.survey.grid.binShift.setX(self.field('binI') * 0.5)         # inline shift size [m]
        self.parent.survey.grid.binShift.setY(self.field('binX') * 0.5)         # x-line shift size [m]
        self.parent.survey.grid.stakeOrig.setX(1000)                            # set inline stake number @ grid origin
        self.parent.survey.grid.stakeOrig.setY(1000)                            # set x-line stake number @ grid origin
        self.parent.survey.grid.stakeSize.setX(self.field('binI'))              # inline stake interval
        self.parent.survey.grid.stakeSize.setY(self.field('binX'))              # x-line line interval

    def alignBingrid(self):
        rpi = self.field('rpi')                                                 # inline
        sli = self.field('sli')                                                 # inline
        spi = self.field('spi')                                                 # x-line
        rli = self.field('rli')                                                 # x-line

        rpi = min(rpi, sli)                                                     # inline
        spi = min(spi, rli)                                                     # x-line

        if self.chkBingridAlign.isChecked():                                    # adjust the bin grid if required
            self.binI.setValue(0.5 * rpi)
            self.binX.setValue(0.5 * spi)

        # note page(x) starts with a ZERO index; therefore page(0) == Page_1
        self.parent.page(3).evt_binImin_editingFinished(plot=False)             # adjust binning parameters in next page (Page_4)
        self.parent.page(3).evt_binIsiz_editingFinished(plot=False)
        self.parent.page(3).evt_binXmin_editingFinished(plot=False)
        self.parent.page(3).evt_binXsiz_editingFinished(plot=False)

        self.updateParentSurvey()
        self.plot()

    def evt_bin_editingFinished(self):
        # adjust the bin grid and/or offsets if required
        self.alignBingrid()

    def evt_BingridAlign_toggled(self):
        self.alignBingrid()


# Page_4 =======================================================================
# 4. Template Properties - Enter Roll Along and Binning Area details


class Page_4(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('4. Template Properties')
        self.setSubTitle('Enter Roll Along and Binning Area details')

        myPrint('page 4 init')

        # create some widgets
        self.slr = QSpinBox()   # src line roll along
        self.rlr = QSpinBox()   # rec line roll along
        self.sld = QSpinBox()   # src line deployments
        self.rld = QSpinBox()   # rec line deployments

        self.binImin = QDoubleSpinBox()
        self.binIsiz = QDoubleSpinBox()
        self.binXmin = QDoubleSpinBox()
        self.binXsiz = QDoubleSpinBox()

        shift = True
        self.chkShiftSpread = QCheckBox('Move first receiver to (0,0) for easier global bingrid definition')
        self.chkShiftSpread.setChecked(shift)

        # set ranges
        self.slr.setRange(1, 1000000)
        self.rlr.setRange(1, 1000000)
        self.sld.setRange(1, 1000000)
        self.rld.setRange(1, 1000000)

        self.binImin.setRange(-1000000, 1000000)
        self.binIsiz.setRange(-1000000, 1000000)
        self.binXmin.setRange(-1000000, 1000000)
        self.binXsiz.setRange(-1000000, 1000000)

        # set the page layout
        layout = QGridLayout()

        row = 0
        layout.addWidget(QLabel('Nr of <b>RLI/SLI intervals</b> to roll the template to its next location'), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.slr, row, 0)
        layout.addWidget(QLabel('Nr shot line(s) to roll'), row, 1)
        layout.addWidget(self.rlr, row, 2)
        layout.addWidget(QLabel('Nr cable(s) to roll'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
        layout.addWidget(QLabel('Nr of times to <b>deploy</b> the template in inline and X-line direction'), row, 0, 1, 4)

        row += 1
        layout.addWidget(self.sld, row, 0)
        layout.addWidget(QLabel('Inline deployments'), row, 1)
        layout.addWidget(self.rld, row, 2)
        layout.addWidget(QLabel('X-line deployments'), row, 3)

        row += 1
        layout.addWidget(QHLine(), row, 0, 1, 4)

        row += 1
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
        layout.addWidget(self.chkShiftSpread, row, 0, 1, 4)

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

        # set the combined layouts
        self.setLayout(vbl)

        # register fields
        self.registerField('rlr', self.rlr, 'value')                            # rec line roll steps
        self.registerField('slr', self.slr, 'value')                            # src line roll steps
        self.registerField('rld', self.rld, 'value')                            # rec line deployments
        self.registerField('sld', self.sld, 'value')                            # src line deployments

        self.registerField('rec_00', self.chkShiftSpread)                       # put 1st receiver at (0,0)

        self.registerField('binImin', self.binImin, 'value')                    # bin area x-origin
        self.registerField('binIsiz', self.binIsiz, 'value')                    # bin area x-size
        self.registerField('binXmin', self.binXmin, 'value')                    # bin area y-origin
        self.registerField('binXsiz', self.binXsiz, 'value')                    # bin area y-size

        # connect signals to slots
        self.rlr.editingFinished.connect(self.evt_roll_editingFinished)         # connect all signals to the same slot
        self.slr.editingFinished.connect(self.evt_roll_editingFinished)
        self.rld.editingFinished.connect(self.evt_roll_editingFinished)
        self.sld.editingFinished.connect(self.evt_roll_editingFinished)

        self.binImin.editingFinished.connect(self.evt_binImin_editingFinished)
        self.binIsiz.editingFinished.connect(self.evt_binIsiz_editingFinished)
        self.binXmin.editingFinished.connect(self.evt_binXmin_editingFinished)
        self.binXsiz.editingFinished.connect(self.evt_binXsiz_editingFinished)

        self.chkShiftSpread.toggled.connect(self.evt_chkShiftSpread_toggled)

        # give some initial values
        self.rlr.setValue(config.rlr)       # moveup one line
        self.slr.setValue(config.slr)       # moveup one line
        self.sld.setValue(round(config.deployInline / (config.slr * config.sli)) + 1)
        self.rld.setValue(round(config.deployX_line / (config.rlr * config.rli)) + 1)

        # initial bin analysis area
        shiftI = 6000 if shift else 0
        self.binImin.setValue(config.binImin + shiftI)
        self.binIsiz.setValue(config.binIsiz)
        self.binXmin.setValue(config.binXmin)
        self.binXsiz.setValue(config.binXsiz)

    def initializePage(self):                                                   # This routine is done each time before the page is activated
        myPrint('initialize page 4')

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

        self.updateParentSurvey()                                               # update the survey object
        self.plot()                                                             # show the plot, center the bin analysis area

    def cleanupPage(self):                                                      # needed to update previous page
        myPrint('cleanup of page 4')

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
        self.parent.survey.output.rctOutput.setWidth(self.field('binIsiz'))
        self.parent.survey.output.rctOutput.setTop(self.field('binXmin'))
        self.parent.survey.output.rctOutput.setHeight(self.field('binXsiz'))

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

        self.parent.survey.paintMode = PaintMode.justTemplates                      # .justLines
        self.parent.survey.lodScale = 6.0
        item = self.parent.survey

        # 4. roll along and binning area
        self.plotWidget.plotItem.addItem(item)

        # Add a marker for the origin
        oriX = [0.0]
        oriY = [0.0]
        _ = self.plotWidget.plot(x=oriX, y=oriY, symbol='h', symbolSize=12, symbolPen=(0, 0, 0, 100), symbolBrush=(180, 180, 180, 100))  # origin marker 'orig' not used further

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
        nrIntervals = max(round(self.binIsiz.value() / binI), 1)
        binIsiz = nrIntervals * binI
        self.binIsiz.setValue(binIsiz)
        self.updateBinningArea(plot)

    def evt_binXmin_editingFinished(self, plot=True):
        binX = self.field('binX')
        nrIntervals = max(round(self.binXmin.value() / binX), 1)
        binXmin = nrIntervals * binX
        self.binXmin.setValue(binXmin)
        self.updateBinningArea(plot)

    def evt_binXsiz_editingFinished(self, plot=True):
        binX = self.field('binX')
        nrIntervals = max(round(self.binXsiz.value() / binX), 1)
        binXsiz = nrIntervals * binX
        self.binXsiz.setValue(binXsiz)
        self.updateBinningArea(plot)

    def updateBinningArea(self, plot):
        self.parent.survey.output.rctOutput.setLeft(self.field('binImin'))
        self.parent.survey.output.rctOutput.setWidth(self.field('binIsiz'))
        self.parent.survey.output.rctOutput.setTop(self.field('binXmin'))
        self.parent.survey.output.rctOutput.setHeight(self.field('binXsiz'))

        if plot:
            self.plot()


# Page_5 =======================================================================
# 5. Template Properties - Pattern/array details


class Page_5(SurveyWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle('5. Template Properties')
        self.setSubTitle('Pattern/array details')

        myPrint('page 5 init')

        # Add some widgets
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
        myPrint('initialize page 5')
        self.updateParentSurvey()
        self.plot()

    def cleanupPage(self):                                                      # needed to update previous page
        myPrint('cleanup of page 5')

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

        myPrint('page 6 init')

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
        myPrint('initialize page 6')

    def cleanupPage(self):                                                      # needed to update previous page
        self.parent.page(4).plot()                                              # needed to update the plot
        myPrint('cleanup of page 6')

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

        myPrint('page 7 init')

        # create some widgets
        self.Xt_0 = QDoubleSpinBox()
        self.Yt_0 = QDoubleSpinBox()

        self.azim = QDoubleSpinBox()

        self.scaX = QDoubleSpinBox()
        self.scaY = QDoubleSpinBox()

        # set ranges
        self.Xt_0.setRange(-999_000, 999_000)
        self.Yt_0.setRange(-999_000, 999_000)

        self.azim.setRange(0, 360)
        self.azim.setWrapping(True)
        self.azim.setDecimals(6)

        self.scaX.setRange(-10_000, 10_000)
        self.scaY.setRange(-10_000, 10_000)
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
        myPrint('initialize page 7')
        self.evt_global_editingFinished()

    def cleanupPage(self):                                                      # needed to return to previous pages
        myPrint('cleanup of page 7')
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
        # myPrint(f'm11 ={transform.m11():12.6f},   m12 ={transform.m12():12.6f},   m13 ={transform.m13():12.6f} » [A1, B1, ...]')
        # myPrint(f'm21 ={transform.m21():12.6f},   m22 ={transform.m22():12.6f},   m23 ={transform.m23():12.6f} » [A2, B2, ...]')
        # myPrint(f'm31 ={transform.m31():12.2f},   m32 ={transform.m32():12.2f},   m33 ={transform.m33():12.6f} » [A0, B0, ...]')

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

        myPrint('page 8 init')

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
        myPrint('initialize page 8')

        xml = self.parent.survey.toXmlString()                                  # check what's in there
        self.xmlEdit.setPlainText(xml)                                          # now show the xml information in the widget

    def cleanupPage(self):                                                      # needed to return to previous pages
        myPrint('cleanup of page 8')
