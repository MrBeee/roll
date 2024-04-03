"""
This module provides the RollBlock Class that describes a block in a survey
"""
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import clipRectF
from .roll_seed import RollSeed
from .roll_translate import RollTranslate


class RollTemplate:
    # assign default name value
    def __init__(self, name: str = 'template-1') -> None:
        self.name: str = name
        self.nSrcSeeds = 0
        self.nRecSeeds = 0

        self.rollList: list[RollTranslate] = []
        self.seedList: list[RollSeed] = []

        # spatial extent of this template formed by the contributing seeds
        self.srcTemplateRect = QRectF()
        self.recTemplateRect = QRectF()
        self.cmpTemplateRect = QRectF()
        self.templateBox = QRectF()

        # spatial extent of this template  after roll along steps
        self.srcBoundingRect = QRectF()
        self.recBoundingRect = QRectF()
        self.cmpBoundingRect = QRectF()
        self.boundingBox = QRectF()

    def writeXml(self, parent: QDomNode, doc: QDomDocument):

        templateElem = doc.createElement('template')

        if len(self.name) > 0:
            nameElement = doc.createElement('name')
            text = doc.createTextNode(self.name)
            nameElement.appendChild(text)
            templateElem.appendChild(nameElement)

        rollsElem = doc.createElement('roll_list')
        templateElem.appendChild(rollsElem)

        for roll in self.rollList:
            # if roll.steps > 1:
            roll.writeXml(rollsElem, doc)

        seedsElem = doc.createElement('seed_list')
        templateElem.appendChild(seedsElem)

        for seed in self.seedList:
            seed.writeXml(seedsElem, doc)

        parent.appendChild(templateElem)

        return templateElem

    def readXml(self, parent: QDomNode):

        nameElem = parent.namedItem('name').toElement()                         # get the name first
        if not nameElem.isNull():
            self.name = nameElem.text()

        rollsElem = parent.namedItem('roll_list').toElement()                   # get the roll steps next
        r = rollsElem.firstChildElement('translate')

        while not r.isNull():
            translate = RollTranslate()
            translate.readXml(r)  # the REAL parent is actually the roll_list
            self.rollList.append(translate)
            r = r.nextSiblingElement('translate')

        while len(self.rollList) < 3:                                           # Make sure there are 3 roll steps in the list
            self.rollList.insert(0, RollTranslate())

        seedsElem = parent.namedItem('seed_list').toElement()                   # finally, get the seeds
        s = seedsElem.firstChildElement('seed')

        if s.isNull():
            raise AttributeError('We need at least TWO SEEDS in a template (src & rec')

        while not s.isNull():
            seed = RollSeed()
            seed.readXml(s)
            self.seedList.append(seed)
            s = s.nextSiblingElement('seed')

        return True

    def resetBoundingRect(self):
        for seed in self.seedList:
            seed.resetBoundingRect()

        # reset spatial extent of this template formed by the contributing seeds
        self.srcTemplateRect = QRectF()
        self.recTemplateRect = QRectF()
        self.cmpTemplateRect = QRectF()
        self.templateBox = QRectF()

        # reset spatial extent of this template  after roll along steps
        self.srcBoundingRect = QRectF()
        self.recBoundingRect = QRectF()
        self.cmpBoundingRect = QRectF()
        self.boundingBox = QRectF()

    def rollSeed(self, seed):
        # get the pre-calculated seed's boundingbox
        seedBoundingBox = seed.boundingBox
        # start here, with a rect before rolling it
        rolledBoundingRect = QRectF(seedBoundingBox)

        for rollStep in self.rollList:                                          # iterate through all roll steps
            # create a copy to roll around
            seedIter = QRectF(seedBoundingBox)

            # if we get a 0 here, there's no additional rolling occurring
            for _ in range(rollStep.steps - 1):
                # apply a roll step on the seed area
                seedIter.translate(rollStep.increment.toPointF())
                # increase the area with new seed position
                rolledBoundingRect |= seedIter

        return rolledBoundingRect

    # we're in RollTemplate here
    def calcBoundingRect(self, srcBorder=QRectF(), recBorder=QRectF(), roll=True):
        for seed in self.seedList:
            # get the seed's boundingbox
            seedBounds = seed.calcBoundingRect()

            if seed.typ_ == 0 and roll is True:                                 # rolling grid of seeds
                if seed.bSource:                                                # it's a source seed
                    # take note of it; handy for QC
                    self.nSrcSeeds += 1
                    # add it taking roll along into account
                    self.srcTemplateRect |= self.rollSeed(seed)
                    # seed's extent limited by Block's src border; needed when painting
                    seed.blockBorder = srcBorder
                else:
                    # take note of it; handy for QC
                    self.nRecSeeds += 1
                    # add it taking roll along into account
                    self.recTemplateRect |= self.rollSeed(seed)
                    # seed's extent limited by Block's rec border; needed when painting
                    seed.blockBorder = recBorder
            else:
                if seed.bSource:                                                # it's a source seed
                    # take note of it; handy for QC
                    self.nSrcSeeds += 1
                    # add it; no roll along
                    self.srcTemplateRect |= seedBounds
                    # seed's extent limited by Block's src border; needed when painting
                    seed.blockBorder = srcBorder
                else:
                    # take note of it; handy for QC
                    self.nRecSeeds += 1
                    # add it; no roll along
                    self.recTemplateRect |= seedBounds
                    # seed's extent limited by Block's rec border; needed when painting
                    seed.blockBorder = recBorder

        # get the normalized position of all 'grown' seeds in a template
        self.srcTemplateRect = self.srcTemplateRect.normalized()
        # the next step is to 'roll' these templates in the 'roll steps'
        self.recTemplateRect = self.recTemplateRect.normalized()

        # traces are generated WITHIN a template, and a cmp area results between the sources and the receives
        TL = (self.srcTemplateRect.topLeft() + self.recTemplateRect.topLeft()) / 2.0
        BR = (self.srcTemplateRect.bottomRight() + self.recTemplateRect.bottomRight()) / 2.0
        # the cmp area sits in the middle between source and receiver area
        self.cmpTemplateRect = QRectF(TL, BR)

        # overall size of a template
        self.templateBox = self.srcTemplateRect | self.recTemplateRect

        # deal with the block border(s) that has been handed down from block to template
        # create copy that may be truncated
        srcAdd = QRectF(self.srcTemplateRect)
        # check rect against block's src/rec border, if the border is valid
        srcAdd = clipRectF(srcAdd, srcBorder)

        # create copy that may be truncated
        recAdd = QRectF(self.recTemplateRect)
        # check rect against block's src/rec border, if the border is valid
        recAdd = clipRectF(recAdd, recBorder)

        # Recalc the cmp area as it is affected too
        if srcBorder.isValid() or recBorder.isValid():
            # if src or rec fall outside borders; no cmps will be valid
            if srcAdd.isValid() and recAdd.isValid():
                TL = (srcAdd.topLeft() + recAdd.topLeft()) / 2.0
                BR = (srcAdd.bottomRight() + recAdd.bottomRight()) / 2.0
                # the cmp area sits in the middle between source and receiver area
                cmpAdd = QRectF(TL, BR)
            else:
                # nothing to add, really; so use an empty rect
                cmpAdd = QRectF()
        else:
            # use the original value
            cmpAdd = QRectF(self.cmpTemplateRect)

        # Increase the src area with new template position
        self.srcBoundingRect = srcAdd
        # Increase the rec area with new template position
        self.recBoundingRect = recAdd
        # Increase the rec area with new template position
        self.cmpBoundingRect = cmpAdd
        # define 'own' boundingBox
        self.boundingBox = self.srcBoundingRect | self.recBoundingRect

        # print(f"SRC = x1:{self.srcBoundingRect.left():11.2f} y1:{self.srcBoundingRect.top():11.2f}, x2:{self.srcBoundingRect.right():11.2f} y2:{self.srcBoundingRect.bottom():11.2f}")
        # print(f"REC = x1:{self.recBoundingRect.left():11.2f} y1:{self.recBoundingRect.top():11.2f}, x2:{self.recBoundingRect.right():11.2f} y2:{self.recBoundingRect.bottom():11.2f}")
        # print(f"CMP = x1:{self.cmpBoundingRect.left():11.2f} y1:{self.cmpBoundingRect.top():11.2f}, x2:{self.cmpBoundingRect.right():11.2f} y2:{self.cmpBoundingRect.bottom():11.2f}")

        # return all 3 as a tuple
        return (self.srcBoundingRect, self.recBoundingRect, self.cmpBoundingRect)
