import copy

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPen, QVector3D

# This module provides some default settings for variables used in Roll

# for the use of this file
# See: https://www.edureka.co/community/52900/how-do-i-share-global-variables-across-modules-python


# general settings
surveyNumber = 1                                                                # number increments within a session

# most recently used (MRU) files
maxRecentFiles = 9                                                              # used in the File -> Open Recent menu

# Level of Detail (LOD) settings
lod0 = 0.005                                                                    # Lowest level;  < lod0: paint survey as rect outline
lod1 = 0.050                                                                    # Next level up; < lod1: paint the templates as rects
lod2 = 0.500                                                                    # Next level up; < lod2: paint the templates as set of lines
lod3 = 1.250                                                                    # Next level up; < lod3: paint individual points
#                                                                               # Last level up; > lod3: paint the individual points with their patterns

# acceptable ranges for the four LOD settings
lod0Range = [0.001, 0.025]
lod1Range = [0.010, 0.250]
lod2Range = [0.100, 2.500]
lod3Range = [0.250, 6.250]

# Default color and pen parameters to display analysis areas, they can be altered in the settings dialog
binAreaColor = '#20000000'                                                      # argb - light grey
cmpAreaColor = '#0800ff00'                                                      # argb - light green
recAreaColor = '#080000ff'                                                      # argb - light blue
srcAreaColor = '#08ff0000'                                                      # argb - light red

# Default pen parameters for analysis areas, these can be altered in the settings dialog
binAreaPen = QPen(Qt.GlobalColor.black, 2, Qt.PenStyle.DashLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
cmpAreaPen = QPen(Qt.GlobalColor.green, 1, Qt.PenStyle.DashDotLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
recAreaPen = QPen(Qt.GlobalColor.blue, 1, Qt.PenStyle.DashDotLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
srcAreaPen = QPen(Qt.GlobalColor.red, 1, Qt.PenStyle.DashDotLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

# Default colormaps, used to display images
foldDispCmap = 'CET-L4'                                                         # used for fold/offset map (layout tab)
analysisCmap = 'CET-R4'                                                         # used for analysis results (analysis tab)
inActiveCmap = 'CET-L1'                                                         # used when no imageItem is available

# RPS, SPS point format
rpsBrushGrey = '#77F0F0F0'                                                      # used for inactive stations
rpsBrushColor = '#772929FF'
rpsPointSymbol = 'o'
rpsSymbolSize = 25

spsBrushGrey = '#77F0F0F0'                                                      # used for inactive stations
spsBrushColor = '#77FF2929'
spsPointSymbol = 'o'
spsSymbolSize = 25

# REC, SRC point format
recBrushGrey = '#77F0F0F0'                                                      # used for inactive stations
recBrushColor = '#772929FF'                                                     # used for active stations
recPointSymbol = 'o'
recSymbolSize = 25

srcBrushGrey = '#77F0F0F0'                                                      # used for inactive stations
srcBrushColor = '#77FF2929'                                                     # used for active stations
srcPointSymbol = 'o'
srcSymbolSize = 25

# select true, in case you have parallel or zigzag geometries, where source lines follow the direction of the receiver lines
DEFAULT_SPS_PARALLEL = False

# Default spsDialect should equal a name from the default SPS format dicts
DEFAULT_SPS_DIALECT = 'New Zealand'

# used in sps_import_dialog.py for human readable input
spsPointFormatDict = dict(
    id='Record identification',
    line='Line',
    point='Point',
    index='Point index',
    code='Point code',
    depth='Point depth',
    east='Easting',
    north='Northing',
    elev='Elevation',
)

spsRelationFormatDict = dict(
    id='Record identification',
    recNum='Field Record number',
    srcLin='Source line number',
    srcPnt='Source point number',
    srcInd='Source point index',
    recLin='Receiver line number',
    recMin='First receiver point',
    recMax='Last receiver point',
    recInd='Receiver point index',
)

# fmt: off
_spsFormatDefaults = [
    # configuration settings for locations of point fields in SPS files;
    # all indices are 'zero' based and the last number is not included
    # the first character on a line is therefore [0, 1], the last one is [79, 80]
    # Note: In SEG rev2.1, Point is followed by two spaces (Col 22-23 as per SPS 2.1 format)
    dict(name='Netherlands', hdr='H', src='S', rec='R', rel='X', id=[0, 1], line=[11, 15], point=[21, 25], index=[25, 26], code=[26, 28], depth=[33, 37], east=[47, 55], north=[57, 65], elev=[65, 71]),
    dict(name='New Zealand', hdr='H', src='S', rec='R', rel='X', id=[0, 1], line=[13, 17], point=[17, 21], index=[23, 24], code=[24, 26], depth=[30, 34], east=[47, 55], north=[57, 65], elev=[65, 71]),
    dict(name='SEG rev2.1',  hdr='H', src='S', rec='R', rel='X', id=[0, 1], line=[ 1, 11], point=[11, 21], index=[23, 24], code=[24, 26], depth=[30, 34], east=[46, 55], north=[55, 65], elev=[65, 71]),
    dict(name='Sudan',       hdr='H', src='S', rec='R', rel='X', id=[0, 1], line=[ 1, 12], point=[21, 25], index=[25, 26], code=[26, 28], depth=[29, 33], east=[46, 55], north=[55, 65], elev=[66, 71]),
]
# fmt: on

# fmt: off
_rpsFormatDefaults = [
    # configuration settings for locations of point fields in RPS files;
    # all indices are 'zero' based and the last number is not included
    # the first character on a line is therefore [0, 1], the last one is [79, 80]
    # Note: In SEG rev2.1, Point is followed by two spaces (Col 22-23 as per SPS 2.1 format)
    dict(name='Netherlands', hdr='H', src='S', rec='R', rel='X', id=[0,1], line=[11, 15], point=[21, 25], index=[25, 26], code=[26, 28], depth=[33, 37], east=[47, 55], north=[57, 65], elev=[65, 71]),
    dict(name='New Zealand', hdr='H', src='S', rec='R', rel='X', id=[0,1], line=[13, 17], point=[17, 21], index=[23, 24], code=[24, 26], depth=[30, 34], east=[47, 55], north=[57, 65], elev=[65, 71]),
    dict(name='SEG rev2.1',  hdr='H', src='S', rec='R', rel='X', id=[0,1], line=[ 1, 11], point=[11, 21], index=[23, 24], code=[24, 26], depth=[30, 34], east=[46, 55], north=[55, 65], elev=[65, 71]),
    dict(name='Sudan',       hdr='H', src='S', rec='R', rel='X', id=[0,1], line=[ 1, 12], point=[21, 25], index=[25, 26], code=[26, 28], depth=[29, 33], east=[46, 55], north=[55, 65], elev=[66, 71]),
]
# fmt: on

# fmt: off
_xpsFormatDefaults = [
    # configuration settings for locations of fields in SPS data;
    # all indices are 'zero' based and the last number is not included
    # the first character on a line is therefore [0, 1], the last one is [79, 80]
    dict(name='Netherlands', hdr='H', src='S', rec='R', rel='X', id=[0,1], recNum=[8, 11], srcLin=[23, 27], srcPnt=[33, 37], srcInd=[37, 38], recLin=[57, 61], recMin=[67, 71], recMax=[75, 79], recInd=[79, 80]),
    dict(name='New Zealand', hdr='H', src='S', rec='R', rel='X', id=[0,1], recNum=[8, 15], srcLin=[29, 33], srcPnt=[33, 37], srcInd=[37, 38], recLin=[61, 65], recMin=[65, 69], recMax=[75, 79], recInd=[79, 80]),
    dict(name='SEG rev2.1',  hdr='H', src='S', rec='R', rel='X', id=[0,1], recNum=[7, 15], srcLin=[17, 27], srcPnt=[27, 37], srcInd=[37, 38], recLin=[49, 59], recMin=[59, 69], recMax=[69, 79], recInd=[79, 80]),
    dict(name='Sudan',       hdr='H', src='S', rec='R', rel='X', id=[0,1], recNum=[4, 12], srcLin=[13, 17], srcPnt=[33, 37], srcInd=[37, 38], recLin=[47, 51], recMin=[67, 71], recMax=[75, 79], recInd=[79, 80]),
]
# fmt: on

def getDefaultSpsFormats():
    return copy.deepcopy(_spsFormatDefaults)


def getDefaultRpsFormats():
    return copy.deepcopy(_rpsFormatDefaults)


def getDefaultXpsFormats():
    return copy.deepcopy(_xpsFormatDefaults)


# for access to QSettings()
organization = 'Duijndam.Dev'
application = 'Roll'

# k-plot settings
kraStack = QVector3D(0.0, 20.0, 0.10)   # settings for kra plots (min, max, step size)
kxyStack = QVector3D(-5.0, 5.0, 0.05)   # settings for kxy plots (min, max, step size)
kxyArray = QVector3D(-50.0, 50.0, 0.5)  # settings for pattern kxy plots (min, max, step size)

# useNumba is used to indicate whether or not to use numba (IF it has been installed)
useNumba = False

# showUnfinished is used to indicate whether or not code "still under construction" is to be shown to end user
DEFAULT_SHOW_UNFINISHED = False

# showSummary is used to indicate whether or not to show summary info of underlying parameters in the property pane
DEFAULT_SHOW_SUMMARIES = False

# debug parameters in settings menu
# See: https://stackoverflow.com/questions/8391411/how-to-block-calls-to-print
DEFAULT_DEBUG = True                                                            # show debug messages in Logging pane
DEFAULT_DEBUGPY = False                                                         # run worker threads in debug mode

# QTableView can handle a max number of rows without 'hanging' QGIS.
# For this reason a chunked approach is used to show analysis results in the table view.
# This variable indicates the maximum number of rows that can be handled per chunk.
# See: https://bugreports.qt.io/browse/QTBUG-31194
maxRowsPerChunk = 1_000_000

# filename handling for wells in a .roll project
useRelativePaths = True   # save well file names relative to .roll project file

# style definitions for consistent style across the application
# toolButtonStyle = 'QToolButton { selection-background-color: blue } QToolButton:checked { background-color: lightblue } QToolButton:pressed { background-color: red }'
toolButtonStyle = '''
QToolButton {
    background-color: #f2f2f2;
    color: #202020;
    border: 1px solid #8f8f8f;
    border-radius: 4px;
    padding: 2px 5px;
    margin: 1px;
    min-height: 15px;
}

QToolButton:hover {
    background-color: #e6f0ff;
    border: 1px solid #5b8bd9;
}

QToolButton:pressed {
    background-color: #cfe2ff;
    border: 1px solid #3f6fb5;
}

QToolButton:checked {
    background-color: #bcd7ff;
    border: 1px solid #3f6fb5;
    font-weight: bold;
}

QToolButton:checked:hover {
    background-color: #aecdff;
    border: 1px solid #2f5fa5;
}

QToolButton:disabled {
    background-color: #f7f7f7;
    color: #9a9a9a;
    border: 1px solid #c8c8c8;
}
'''.strip()

purpleLabelStyle = 'border: 1px solid black;background-color:lavender'
exportButtonStyle = 'background-color:lightgoldenrodyellow; font-weight:bold;'
purpleButtonStyle = 'background-color:lavender; font-weight:bold;'
dockWidgetTitleStyle = 'QDockWidget::title {background : lightblue;}'
wizardEditHighlightStyle = 'QLineEdit  { background-color : lightblue} '
wizardComboHighlightStyle = 'QComboBox  { background-color : lightblue} '

dSpinBoxBoldStyle = 'QDoubleSpinBox {font: bold;} '
dSpinBoxErrorStyle = 'QDoubleSpinBox {color:red; background-color:lightblue;}'
dSpinBoxNormalStyle = 'QDoubleSpinBox {color:black; background-color:white;}'

nSpinBoxExactStyle = 'QSpinBox {font:bold; color:forestgreen} '
nSpinBoxErrorStyle = 'QSpinBox {font:bold; color:red} '
nSpinBoxWarningStyle = 'QSpinBox {font:bold; color:darkorange} '

labelErrorStyle = 'QLabel {color:red}'
labelNormalStyle = 'QLabel {color:black}'
labelWarningStyle = 'QLabel {color:darkorange}'
labelExactStyle = 'QLabel {color:forestgreen}'

editErrorStyle = 'QLineEdit {color:red; background-color:lightblue;}'
editNormalStyle = 'QLineEdit {color:black; background-color:white;}'

# See: https://stackoverflow.com/questions/7840325/change-the-selection-color-of-a-qtablewidget
tableStyle = 'QTableView::item:selected{background-color : #add8e6;selection-color : #000000;}'
labelStyle = 'font-family: Arial; font-weight: bold; font-size: 16px;'


# Example on using config.py
# A) Set a default value of 'x' in config.py
#
# x = 100
#
# B) in my_module.py, import and change value of x:
#
# from . import config
# parameter1 = config.x
# config.x = parameter2
#
# C) in main.py, print the value of x:
#
# import my_module
# from . import config
# print(config.x)
