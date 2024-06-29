"""
This module provides the RollBlock Class that describes a block in a survey
"""
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .roll_block_borders import BlockBorders
from .roll_template import RollTemplate


class RollBlock:
    def __init__(self, name: str = 'block-1') -> None:  # assign default name value
        self.name: str = name

        # block spatial extent
        self.srcBoundingRect = QRectF()
        self.recBoundingRect = QRectF()
        self.cmpBoundingRect = QRectF()
        self.boundingBox = QRectF()

        self.borders = BlockBorders()
        self.templateList: list[RollTemplate] = []

    def writeXml(self, parent: QDomNode, doc: QDomDocument):

        blockElem = doc.createElement('block')

        if len(self.name) > 0:
            nameElement = doc.createElement('name')
            text = doc.createTextNode(self.name)
            nameElement.appendChild(text)
            blockElem.appendChild(nameElement)

        self.borders.writeXml(blockElem, doc)

        templatesElem = doc.createElement('template_list')
        blockElem.appendChild(templatesElem)

        for template in self.templateList:
            template.writeXml(templatesElem, doc)

        parent.appendChild(blockElem)

        return blockElem

    def readXml(self, parent: QDomNode):

        nameElem = parent.namedItem('name').toElement()
        if not nameElem.isNull():
            self.name = nameElem.text()

        templatesElem = parent.namedItem('template_list').toElement()

        t = templatesElem.firstChildElement('template')

        if t.isNull():
            return False  # We need at least one template in a block

        while not t.isNull():
            template = RollTemplate()
            template.readXml(t)
            self.templateList.append(template)
            t = t.nextSiblingElement('template')

        if not self.borders.readXml(parent):
            return False

    def calcBoundingRect(self):
        self.srcBoundingRect = QRectF()  # reset it
        self.recBoundingRect = QRectF()  # reset it
        self.cmpBoundingRect = QRectF()  # reset it
        self.boundingBox = QRectF()  # reset it

        for template in self.templateList:
            srcBounds, recBounds, cmpBounds = template.calcBoundingRect(self.borders.srcBorder, self.borders.recBorder)
            self.srcBoundingRect |= srcBounds  # add it
            self.recBoundingRect |= recBounds  # add it
            self.cmpBoundingRect |= cmpBounds  # add it

        self.boundingBox = self.srcBoundingRect | self.recBoundingRect
        # return all 3 as a tuple
        return (self.srcBoundingRect, self.recBoundingRect, self.cmpBoundingRect)
