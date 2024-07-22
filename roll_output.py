"""
This module manages the output of binning operations
"""

from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import toFloat


class RollOutput:
    # assign default values
    def __init__(self) -> None:
        self.rctOutput = QRectF()                                               # size and local position of analysis area
        self.binOutput = None                                                   # numpy array with foldmap
        self.minOffset = None                                                   # numpy array with minimum offset
        self.maxOffset = None                                                   # numpy array with maximum offset
        self.rmsOffset = None                                                   # numpy array with rms offset increments
        self.anaOutput = None                                                   # memory mapped numpy trace record array
        self.D2_Output = None                                                   # partially flattened version of self.anaOutput (N x 13)

        self.recGeom = None                                                     # numpy array with list of receiver locations
        self.srcGeom = None                                                     # numpy array with list of source locations
        self.relGeom = None                                                     # numpy array with list of relation records
        self.relTemp = None                                                     # numpy array with temp list of rel records

        # See: https://stackoverflow.com/questions/17915117/nested-dictionary-comprehension-python
        # See: https://stackoverflow.com/questions/20446526/how-to-construct-nested-dictionary-comprehension-in-python-with-correct-ordering
        # See: https://stackoverflow.com/questions/68305584/nested-dictionary-comprehension-2-level
        # See: https://treyhunner.com/2015/12/python-list-comprehensions-now-in-color/
        # See: https://rowannicholls.github.io/python/advanced/dictionaries.html

        self.recDict = None                                                     # nested dictionary to access rec positions
        self.srcDict = None                                                     # nested dictionary to access src positions

        # self.anaType = np.dtype([('SrcX', np.float32), ('SrcY', np.float32),    # Src (x, y)
        #                          ('RecX', np.float32), ('RecY', np.float32),    # Rec (x, y)
        #                          ('CmpX', np.float32), ('CmpY', np.float32),    # Cmp (x, y); needed for spider plot when binning against dipping plane
        #                          ('SrcL', np.int32  ), ('SrcP', np.int32  ),    # SrcLine, SrcPoint
        #                          ('RecL', np.int32  ), ('RecP', np.int32  )])   # RecLine, RecPoint

        # 0 in case no fold is okay
        self.minimumFold: int = 0
        self.maximumFold: int = 0

        self.minMinOffset = 0.0
        self.maxMinOffset = 0.0

        self.minMaxOffset = 0.0
        self.maxMaxOffset = 0.0

        self.minRmsOffset = 0.0
        self.maxRmsOffset = 0.0

    def writeXml(self, parent: QDomNode, doc: QDomDocument):

        outputElem = doc.createElement('output')
        outputElem.setAttribute('xmin', str(self.rctOutput.left()))
        outputElem.setAttribute('xmax', str(self.rctOutput.right()))
        outputElem.setAttribute('ymin', str(self.rctOutput.top()))
        outputElem.setAttribute('ymax', str(self.rctOutput.bottom()))
        parent.appendChild(outputElem)

        return outputElem

    def readXml(self, parent: QDomNode):

        outputElem = parent.namedItem('output').toElement()
        if outputElem.isNull():
            return False

        xmin = toFloat(outputElem.attribute('xmin'))
        xmax = toFloat(outputElem.attribute('xmax'))
        self.rctOutput.setLeft(min(xmin, xmax))
        self.rctOutput.setRight(max(xmin, xmax))

        ymin = toFloat(outputElem.attribute('ymin'))
        ymax = toFloat(outputElem.attribute('ymax'))
        self.rctOutput.setTop(min(ymin, ymax))
        self.rctOutput.setBottom(max(ymin, ymax))

        return True
