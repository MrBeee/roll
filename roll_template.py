"""
This module provides the RollBlock Class that describes a block in a survey
"""
from qgis.PyQt.QtCore import QRectF
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .functions import clipRectF
from .roll_seed import RollSeed, SeedType
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
        self.srcTemplateRect = QRectF()                                         # src area in one template
        self.recTemplateRect = QRectF()                                         # rec area in one template
        self.totTemplateRect = QRectF()                                         # src|rec area in one template

        # spatial extent of this template  after roll along steps
        self.srcBoundingRect = QRectF()                                         # src area of all templates
        self.recBoundingRect = QRectF()                                         # rec area of all templates
        self.cmpBoundingRect = QRectF()                                         # cmp area of all templates
        self.boundingBox = QRectF()                                             # src|rec area of all templates

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
            translate.readXml(r)                                                # the REAL parent is actually the roll_list
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

    def rollSeedOld(self, seed):
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

    def rollSeed(self, seed):
        # get the pre-calculated seed's boundingbox
        seedBoundingBox = seed.boundingBox
        # start here, with a rect before rolling it
        rolledBoundingRect = QRectF(seedBoundingBox)

        for rollStep in self.rollList:                                          # iterate through all roll steps
            # create a copy to roll around
            seedIter = QRectF(seedBoundingBox)

            if rollStep.steps > 1:
                seedIter.translate(rollStep.increment.toPointF() * (rollStep.steps - 1))
                rolledBoundingRect |= seedIter

        # the following code comes from RollGrid, used as an example, as here the same faster approach was applied earlier

        # # It's quicker NOT to iterate over all growsteps individually, as was done earlier below, but to apply these steps all at once
        # # for growStep in self.growList:                                          # iterate through all grow steps
        # #     for _ in range(growStep.steps - 1):                                 # we have to subtract 1 here' to get from deployments to roll steps
        # #         pointIter += growStep.increment                                 # shift the iteration point with the appropriate amount

        # for growStep in self.growList:                                          # iterate through all grow steps
        #     if growStep.steps > 1:                                              # need more than one to roll
        #         pointIter += growStep.increment * (growStep.steps - 1)          # define the new end point, and add this to the previous one

        return rolledBoundingRect

    # we're in RollTemplate here
    def calcBoundingRect(self, srcBorder=QRectF(), recBorder=QRectF()):
        for seed in self.seedList:                                              # reset all seeds
            seed.boundingBox = QRectF()

        # reset spatial extent of this template formed by the contributing seeds
        self.srcTemplateRect = QRectF()                                         # src area in one template
        self.recTemplateRect = QRectF()                                         # rec area in one template
        self.totTemplateRect = QRectF()                                         # src|rec area in one template

        # reset spatial extent of this template  after roll along steps
        self.srcBoundingRect = QRectF()                                         # src area of all templates
        self.recBoundingRect = QRectF()                                         # rec area of all templates
        self.cmpBoundingRect = QRectF()                                         # cmp area of all templates
        self.boundingBox = QRectF()                                             # src|rec area of all templates

        for seed in self.seedList:
            # get the seed's boundingbox
            seedBounds = seed.calcBoundingRect()

            if seed.bSource:                                                    # it's a source seed
                self.nSrcSeeds += 1                                             # take note of it; handy for QC
                self.srcTemplateRect |= seedBounds                              # add it; no roll along
                seed.blockBorder = srcBorder                                    # seed's extent limited by Block's src border; needed when painting
            else:
                self.nRecSeeds += 1                                             # take note of it; handy for QC
                self.recTemplateRect |= seedBounds                              # add it; no roll along
                seed.blockBorder = recBorder                                    # seed's extent limited by Block's rec border; needed when painting

            if seed.type == SeedType.rollingGrid:                               # in case of rolling grid of seeds
                if seed.bSource:                                                # it's a source seed
                    self.srcBoundingRect |= self.rollSeed(seed)                 # add it taking roll along into account
                else:                                                           # it's a receiver seed
                    self.recBoundingRect |= self.rollSeed(seed)                 # add it taking roll along into account
            else:
                if seed.bSource:                                                # it's a source seed
                    self.srcBoundingRect |= self.srcTemplateRect                # add it; no roll along
                else:                                                           # it's a receiver seed
                    self.recBoundingRect |= self.recTemplateRect                # add it; no roll along

        self.totTemplateRect = self.srcTemplateRect | self.recTemplateRect      # overall size of a template

        self.srcBoundingRect = self.srcBoundingRect.normalized()                # normalize src bounding area to work with TL, BR
        self.recBoundingRect = self.recBoundingRect.normalized()                # normalize rec bounding area to work with TL, BR

        TL = (self.srcBoundingRect.topLeft() + self.recBoundingRect.topLeft()) / 2.0
        BR = (self.srcBoundingRect.bottomRight() + self.recBoundingRect.bottomRight()) / 2.0
        self.cmpBoundingRect = QRectF(TL, BR)                                   # the cmp area sits in the middle between source and receiver area

        # deal with the block border(s) that has been handed down from block to template
        srcAdd = QRectF(self.srcBoundingRect)                                   # create copy that may be truncated
        srcAdd = clipRectF(srcAdd, srcBorder)                                   # check rect against block's src/rec border, if the border is valid

        recAdd = QRectF(self.recBoundingRect)                                   # create copy that may be truncated
        recAdd = clipRectF(recAdd, recBorder)                                   # check rect against block's src/rec border, if the border is valid

        if srcBorder.isValid() or recBorder.isValid():                          # Recalc the cmp area as it is affected too
            if srcAdd.isValid() and recAdd.isValid():                           # if src or rec fall outside borders; no cmps will be valid
                TL = (srcAdd.topLeft() + recAdd.topLeft()) / 2.0
                BR = (srcAdd.bottomRight() + recAdd.bottomRight()) / 2.0
                cmpAdd = QRectF(TL, BR)                                         # the cmp area sits in the middle between source and receiver area
            else:
                cmpAdd = QRectF()                                               # nothing to add, really; so use an empty rect
        else:
            cmpAdd = QRectF(self.cmpBoundingRect)                               # use the original value

        self.srcBoundingRect = srcAdd                                           # Increase the src area with new template position
        self.recBoundingRect = recAdd                                           # Increase the rec area with new template position
        self.cmpBoundingRect = cmpAdd                                           # Increase the rec area with new template position
        self.boundingBox = self.srcBoundingRect | self.recBoundingRect          # define 'own' boundingBox

        # print(f"SRC = x1:{self.srcBoundingRect.left():11.2f} y1:{self.srcBoundingRect.top():11.2f}, x2:{self.srcBoundingRect.right():11.2f} y2:{self.srcBoundingRect.bottom():11.2f}")
        # print(f"REC = x1:{self.recBoundingRect.left():11.2f} y1:{self.recBoundingRect.top():11.2f}, x2:{self.recBoundingRect.right():11.2f} y2:{self.recBoundingRect.bottom():11.2f}")
        # print(f"CMP = x1:{self.cmpBoundingRect.left():11.2f} y1:{self.cmpBoundingRect.top():11.2f}, x2:{self.cmpBoundingRect.right():11.2f} y2:{self.cmpBoundingRect.bottom():11.2f}")

        # return all 3 bounding areas as a tuple
        return (self.srcBoundingRect, self.recBoundingRect, self.cmpBoundingRect)
