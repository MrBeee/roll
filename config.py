from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPen

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

# source
nsl = 1                                                                         # nr. src lines in template
nsl_par = 681                                                                   # nr. src pointd in parallel template
nsp = 4                                                                         # nr. src points in template
sli = 250                                                                       # src line interval
sli_par = 50                                                                    # src POINT interval in a parallel template
spi = 50                                                                        # src point interval; src LINE interval in a parallel template
slr = 1                                                                         # src line roll along
sld = 41                                                                        # src line deployments (inline)

# receiver
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

# Level of Detail (LOD) settings
lod0 = 0.005                                                                    # Lowest level;  < lod0: paint survey as rect outline
lod1 = 0.050                                                                    # Next level up; < lod1: paint the templates as rects
lod2 = 0.500                                                                    # Next level up; < lod2: paint the templates as set of lines; > paint individual points
lod3 = 1.250                                                                    # Next level up; > lod3: paint the individual points with their patterns

lod0Range = [0.001, 0.025]
lod1Range = [0.010, 0.250]
lod2Range = [0.100, 2.500]
lod3Range = [0.250, 6.250]

# geophone and source patterns
rNam = 'rec-array'                                                              # pattern name
sNam = 'src-array'                                                              # pattern name
rBra = 4                                                                        # nr branches in pattern
sBra = 1                                                                        # nr branches in pattern
rEle = 6                                                                        # nr elem in branch
sEle = 3                                                                        # nr elem in branch
rBrI = 12.5                                                                     # branch interval
sBrI = 0.0                                                                      # branch interval
rElI = 25.0 / 3.0                                                                 # element interval
sElI = 12.5                                                                     # element interval

# default color and pen parameters to display analysis areas, they can be altered in the settings dialog
binAreaColor = '#20000000'                                                      # argb - light grey
cmpAreaColor = '#0800ff00'                                                      # argb - light green
recAreaColor = '#080000ff'                                                      # argb - light blue
srcAreaColor = '#08ff0000'                                                      # argb - light red

# default pen parameters for analysis areas, these can be altered in the settings dialog
binAreaPen = QPen(Qt.black, 2, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin)
cmpAreaPen = QPen(Qt.green, 1, Qt.DashDotLine, Qt.RoundCap, Qt.RoundJoin)
recAreaPen = QPen(Qt.blue, 1, Qt.DashDotLine, Qt.RoundCap, Qt.RoundJoin)
srcAreaPen = QPen(Qt.red, 1, Qt.DashDotLine, Qt.RoundCap, Qt.RoundJoin)

# default colormaps, used to display images
fold_OffCmap = 'CET-L4'                                                         # used for fold/offset map (layout tab)
analysisCmap = 'CET-R4'                                                         # used for analysis results (analysis tab)
inActiveCmap = 'CET-L1'                                                         # used when no imageItem is available

# RPS, SPS point format
rpsBrushColor = '#772929FF'
rpsPointSymbol = 'o'
rpsSymbolSize = 25

spsBrushColor = '#77FF2929'
spsPointSymbol = 'o'
spsSymbolSize = 25

# REC, SRC point format
recBrushColor = '#772929FF'
recPointSymbol = 'o'
recSymbolSize = 25

srcBrushColor = '#77FF2929'
srcPointSymbol = 'o'
srcSymbolSize = 25


# default spsDialect should equal a name from the spsFormatList dicts
spsDialect = 'New Zealand'

spsFormatList = [
    # configuration settings for locations of fields in SPS data;
    # all indices are 'zero' based and the last number is not included
    # the first character is therefore [0, 1], the last one is [79, 80]
    # Note: In SEG rev2.1, Point is followed by two spaces (Col 22-23 as per SPS 2.1 format)
    dict(name='Netherlands', hdr='H', src='S', rec='R', rel='X', line=[11, 15], point=[21, 25], index=[25, 26], code=[26, 28], depth=[33, 37], east=[47, 55], north=[57, 65], elev=[65, 71]),
    dict(name='New Zealand', hdr='H', src='S', rec='R', rel='X', line=[13, 17], point=[17, 21], index=[23, 24], code=[24, 26], depth=[30, 34], east=[47, 55], north=[57, 65], elev=[65, 71]),
    dict(name='SEG rev2.1', hdr='H', src='S', rec='R', rel='X', line=[1, 12], point=[11, 21], index=[23, 24], code=[24, 25], depth=[30, 34], east=[46, 55], north=[55, 65], elev=[65, 71]),
    dict(name='Sudan', hdr='H', src='S', rec='R', rel='X', line=[1, 12], point=[21, 25], index=[25, 26], code=[26, 28], depth=[29, 33], east=[46, 55], north=[55, 65], elev=[66, 71]),
]

xpsFormatList = [
    # configuration settings for locations of fields in SPS data;
    # all indices are 'zero' based and the last number is not included
    # the first character is therefore [0, 1], the last one is [79, 80]
    dict(name='Netherlands', hdr='H', src='S', rec='R', rel='X', recNum=[8, 11], srcLin=[23, 27], srcPnt=[33, 37], srcInd=[37, 38], recLin=[57, 61], recMin=[67, 71], recMax=[75, 79], recInd=[79, 80]),
    dict(name='New Zealand', hdr='H', src='S', rec='R', rel='X', recNum=[8, 15], srcLin=[29, 33], srcPnt=[33, 37], srcInd=[37, 38], recLin=[61, 65], recMin=[65, 69], recMax=[75, 79], recInd=[79, 80]),
    dict(name='SEG rev2.1', hdr='H', src='S', rec='R', rel='X', recNum=[7, 15], srcLin=[17, 27], srcPnt=[27, 37], srcInd=[37, 38], recLin=[49, 59], recMin=[59, 69], recMax=[69, 79], recInd=[79, 80]),
    dict(name='Sudan', hdr='H', src='S', rec='R', rel='X', recNum=[4, 12], srcLin=[13, 17], srcPnt=[33, 37], srcInd=[37, 38], recLin=[47, 51], recMin=[67, 71], recMax=[75, 79], recInd=[79, 80]),
]

# for access to QSettings()
organization = 'Duijndam.Dev'
application = 'Roll'

# used to share a 'global' variable between roll_main_window.py and my_parameters.py
patternList = []

# currently used as a backdoor to access survey.crs and global transform from other parameters
surveyCrs = None
surveyTransform = None

# useNumba is used to indicate wether or not to use numba (IF it has been installed)
useNumba = False

# Example on using config.py
# A) Set a default value of 'x' in config.py
#
# x = 100
#
# B) in module.py, import and change value of x:
#
# from . import config
# parameter1 = config.x
# config.x = parameter2
#
# C) in main.py, print the value of x:
#
# from . import config
# import module
# print(config.x)
