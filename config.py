import copy
from time import perf_counter

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPen, QVector3D
from qgis.PyQt.QtWidgets import QApplication

# This module provides some default settings for variables used in Roll

# for the use of this file
# See: https://www.edureka.co/community/52900/how-do-i-share-global-variables-across-modules-python


# general settings
surveyNumber = 1                                                                # number increments within a session
surveyName = 'Orthogonal_001'                                                   # initial survey name

# most recently used (MRU) files
maxRecentFiles = 9                                                              # used in the File -> Open Recent menu

# deployment area
deployInline = 10000                                                            # inline deployment distance
deployX_line = 10000                                                            # x-line deployment distance

# source for land/obc templates
nsl = 1                                                                         # nr. src lines in template
nsl_par = 681                                                                   # nr. src pointd in parallel template
nsp = 4                                                                         # nr. src points in template
sli = 250                                                                       # src line interval
sli_par = 50                                                                    # src POINT interval in a parallel template
spi = 50                                                                        # src point interval; src LINE interval in a parallel template
slr = 1                                                                         # src line roll along
sld = 41                                                                        # src line deployments (inline)

# receiver for land/obc templates
# spreadlength = 12000                                                          # initial spread length [m], before changes are made
nrl = 8                                                                         # nr. rec lines in template
nrp = 240                                                                       # nr. rec points in template
nrp_par = 440                                                                   # nr. rec points in template
rli = 200                                                                       # rec line interval
rpi = 50                                                                        # rec point interval
rlr = 1                                                                         # rec line roll along
rld = 51                                                                        # rec line deployments (x-line)

brick = 100                                                                     # offset of 2nd source line

# binning area
binImin = 4000                                                                  # x-min - of initial cmp analysis area
binXmin = 5000                                                                  # x-size
binIsiz = 2000                                                                  # y-min
binXsiz = 2000                                                                  # y-size

# General presets for towed marine settings
swDensity = 1029.0                                                              # [kg/m3]   seawater density
cDrag = 0.0055                                                                  # [-]       streamer drag coefficient
maxDragForce = 3.07                                                             # [ton-force]   max force on streamer(s)
vSail = 4.60                                                                    # [knot]    vessel's acquisition speed in water
vTurn = 4.47                                                                    # [knot]    vessel's line turn speed in water
vMinInner = 3.75                                                                # [knot]    min speed in water of inner streamer

vCross = 0.0                                                                    # [knot]    cross current
vTail = 0.0                                                                     # [knot]    tail current

srcPopInt = 25.0                                                                # [m]       default pop-interval; impacts 'clean' record length
nSrc = 2                                                                        # [#]       flip-flop shooting
nCab = 10                                                                       # [#]       using 10 cables is quite normal

srcLayback = 250.0                                                              # [m]       limited by umbilical length
cabLayback = 450.0                                                              # [m]       approximately half the spreadwidth

cabLength = 8000.0                                                              # [m]       8 km streamer per default
cabDiameter = 0.06                                                              # [m]       cable diameter; for drag forces
groupInt = 12.5                                                                 # [m]       group interval, 12.5 m is industry standard

cabDepthHead = 8.0                                                              # [m]       streamer depth at head of spread
cabDepthTail = 10.0                                                             # [m]       streamer depth at end of spread

cabSepHead = 100.0                                                              # [m]       streamer inerval at head of spread
cabSepTail = 100.0                                                              # [m]       streamer depth at end of spread

srcDepth = 10.0                                                                 # [m]       source depth default
recLength = 8.0                                                                 # [s]       record length

srcSepFactor = 1                                                                # [#]       Source separation factor [1 ... nCab-1]
srcSeparation = 50.0                                                            # [#]       Source separation interval

cdpDepth = 2000.0                                                               # [m]       shown cdp depth in marine wizard

surveySizeI = 50_000.0                                                          # [m]       inline survey size
surveySizeX = 30_000.0                                                          # [m]       x-line survey size

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

# Source and receiver patterns land / obc
rNam = 'rec-array'                                                              # pattern name
sNam = 'src-array'                                                              # pattern name
rBra = 4                                                                        # nr branches in pattern
sBra = 1                                                                        # nr branches in pattern
rEle = 6                                                                        # nr elem in branch
sEle = 3                                                                        # nr elem in branch
rBrI = 12.5                                                                     # branch interval
sBrI = 0.0                                                                      # branch interval
rElI = 25.0 / 3.0                                                               # element interval
sElI = 12.5                                                                     # element interval

# Source and receiver patterns streamers
rName = 'streamer-group'                                                        # pattern name
sName = 'airgun-array'                                                          # pattern name
rBran = 6                                                                       # nr branches in pattern
sBran = 5                                                                       # nr branches in pattern
rElem = 1                                                                       # nr elem in branch
sElem = 3                                                                       # nr elem in branch
rBrIn = 12.5 / 6                                                                # branch interval
sBrIn = 15.0 / 5                                                                # branch interval
rElIn = 0.0                                                                     # element interval
sElIn = 15.0                                                                    # element interval

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
fold_OffCmap = 'CET-L4'                                                         # used for fold/offset map (layout tab)
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
spsParallel = False

# Default spsDialect should equal a name from the spsFormatList dicts
spsDialect = 'New Zealand'

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
spsFormatList = [
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
rpsFormatList = [
    # configuration settings for locations of point fields in RPS files;
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
xpsFormatList = [
    # configuration settings for locations of fields in SPS data;
    # all indices are 'zero' based and the last number is not included
    # the first character on a line is therefore [0, 1], the last one is [79, 80]
    dict(name='Netherlands', hdr='H', src='S', rec='R', rel='X', id=[0, 1], recNum=[8, 11], srcLin=[23, 27], srcPnt=[33, 37], srcInd=[37, 38], recLin=[57, 61], recMin=[67, 71], recMax=[75, 79], recInd=[79, 80]),
    dict(name='New Zealand', hdr='H', src='S', rec='R', rel='X', id=[0, 1], recNum=[8, 15], srcLin=[29, 33], srcPnt=[33, 37], srcInd=[37, 38], recLin=[61, 65], recMin=[65, 69], recMax=[75, 79], recInd=[79, 80]),
    dict(name='SEG rev2.1',  hdr='H', src='S', rec='R', rel='X', id=[0, 1], recNum=[7, 15], srcLin=[17, 27], srcPnt=[27, 37], srcInd=[37, 38], recLin=[49, 59], recMin=[59, 69], recMax=[69, 79], recInd=[79, 80]),
    dict(name='Sudan',       hdr='H', src='S', rec='R', rel='X', id=[0, 1], recNum=[4, 12], srcLin=[13, 17], srcPnt=[33, 37], srcInd=[37, 38], recLin=[47, 51], recMin=[67, 71], recMax=[75, 79], recInd=[79, 80]),
]
# fmt: on

_spsFormatDefaults = copy.deepcopy(spsFormatList)
_rpsFormatDefaults = copy.deepcopy(rpsFormatList)
_xpsFormatDefaults = copy.deepcopy(xpsFormatList)

def reset_sps_database():
    global spsFormatList, rpsFormatList, xpsFormatList                      # pylint: disable=W0603; need to update global variables
    spsFormatList = copy.deepcopy(_spsFormatDefaults)
    rpsFormatList = copy.deepcopy(_rpsFormatDefaults)
    xpsFormatList = copy.deepcopy(_xpsFormatDefaults)


# for access to QSettings()
organization = 'Duijndam.Dev'
application = 'Roll'

# used to share a 'global' variable between roll_main_window.py and my_parameters.py
patternList = []

# currently used as a backdoor to access survey.crs and global transform from other parameters
surveyCrs = None
surveyTransform = None

# k-plot settings
kr_Stack = QVector3D(0.0, 20.0, 0.10)   # settings for k_r plots (min, max, step size)
kxyStack = QVector3D(-5.0, 5.0, 0.05)   # settings for kxy plots (min, max, step size)
kxyArray = QVector3D(-50.0, 50.0, 0.5)  # settings for pattern kxy plots (min, max, step size)

# useNumba is used to indicate whether or not to use numba (IF it has been installed)
useNumba = False

# showUnfinished is used to indicate whether or not code "still under construction" is to be shown to end user
showUnfinished = False

# showSummary is used to indicate whether or not to show summary info of underlying parameters in the property pane
showSummaries = False

# debug parameters in settings menu
# See: https://stackoverflow.com/questions/8391411/how-to-block-calls-to-print
debug = False   # show debug messages in Logging pane
debugpy = False   # run worker threads in debug mode

# QTableView can handle a max number of rows without 'hanging' QGIS.
# For this reason a chunked approach is used to show analysis results in the table view.
# This variable indicates the maximum number of rows that can be handled per chunk.
# See: https://bugreports.qt.io/browse/QTBUG-31194
maxRowsPerChunk = 1_000_000

# filename handling for wells in a .roll project
useRelativePaths = True   # save well file names relative to .roll project file

# timings for time critical functions, allowing for 20 steps, accessed through config.elapsedTime(startTime, index: int)
timerTmin = [float('Inf') for _ in range(20)]
timerTmax = [0.0 for _ in range(20)]
timerTtot = [0.0 for _ in range(20)]
timerFreq = [0 for _ in range(20)]


def elapsedTime(startTime, index: int) -> None:
    currentTime = perf_counter()
    deltaTime = currentTime - startTime

    timerTmin[index] = min(deltaTime, timerTmin[index])
    timerTmax[index] = max(deltaTime, timerTmax[index])
    timerTtot[index] = timerTtot[index] + deltaTime
    timerFreq[index] = timerFreq[index] + 1
    QApplication.processEvents()
    return perf_counter()  # call again; to ignore any time spent in this funtion


def resetTimers(timers=20) -> None:

    # Need access to global variables to reset their values; disable pylint warning
    global timerTmin                                                            # pylint: disable=W0603
    global timerTmax                                                            # pylint: disable=W0603
    global timerTtot                                                            # pylint: disable=W0603
    global timerFreq                                                            # pylint: disable=W0603

    timerTmin = [float('Inf') for _ in range(timers)]
    timerTmax = [0.0 for _ in range(timers)]
    timerTtot = [0.0 for _ in range(timers)]
    timerFreq = [0 for _ in range(timers)]


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
