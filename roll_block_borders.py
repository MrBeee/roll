"""
This module provides the borders of a survey block"""

from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import toFloat


class BlockBorders:
    # assign default values; all zeros implies invalid QRectF; so no truncation applied
    def __init__(self, src=QRectF(), rec=QRectF()) -> None:
        # creates new object instead of creating a reference to existing border
        self.srcBorder = QRectF(src)
        self.recBorder = QRectF(rec)

    def writeXml(self, parent: QDomNode, doc: QDomDocument):

        bordersElem = doc.createElement('borders')

        srcElem = doc.createElement('src_border')
        bordersElem.appendChild(srcElem)

        # do top & left first; this *anchors* the QRectF
        srcElem.setAttribute('ymin', str(self.srcBorder.top()))
        srcElem.setAttribute('xmin', str(self.srcBorder.left()))
        # do bottom & right next; this defines width & height of the QRectF
        srcElem.setAttribute('ymax', str(self.srcBorder.bottom()))
        srcElem.setAttribute('xmax', str(self.srcBorder.right()))

        recElem = doc.createElement('rec_border')
        bordersElem.appendChild(recElem)

        # do top & left first; this *anchors* the QRectF
        recElem.setAttribute('ymin', str(self.recBorder.top()))
        recElem.setAttribute('xmin', str(self.recBorder.left()))
        # do bottom & right next; this defines width & height of the QRectF
        recElem.setAttribute('ymax', str(self.recBorder.bottom()))
        recElem.setAttribute('xmax', str(self.recBorder.right()))

        parent.appendChild(bordersElem)

        return bordersElem

    def readXml(self, parent: QDomNode):

        bordersElem = parent.namedItem('borders').toElement()

        srcElem = bordersElem.namedItem('src_border').toElement()
        if srcElem.isNull():
            return False

        xmin = toFloat(srcElem.attribute('xmin'))
        xmax = toFloat(srcElem.attribute('xmax'))
        self.srcBorder.setLeft(min(xmin, xmax))
        self.srcBorder.setRight(max(xmin, xmax))

        ymin = toFloat(srcElem.attribute('ymin'))
        ymax = toFloat(srcElem.attribute('ymax'))
        self.srcBorder.setTop(min(ymin, ymax))
        self.srcBorder.setBottom(max(ymin, ymax))

        recElem = bordersElem.namedItem('rec_border').toElement()
        if recElem.isNull():
            return False

        xmin = toFloat(recElem.attribute('xmin'))
        xmax = toFloat(recElem.attribute('xmax'))

        self.recBorder.setLeft(min(xmin, xmax))
        self.recBorder.setRight(max(xmin, xmax))

        ymin = toFloat(recElem.attribute('ymin'))
        ymax = toFloat(recElem.attribute('ymax'))
        self.recBorder.setTop(min(ymin, ymax))
        self.recBorder.setBottom(max(ymin, ymax))

        return True
