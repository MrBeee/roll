"""
CFP analysis parameter model and XML serialization helpers.
"""

import re

from qgis.PyQt.QtCore import QPointF
from qgis.PyQt.QtXml import QDomDocument, QDomNode

from .aux_functions import toBool, toFloat


class RollCfp:
    _FREQ_ALLOWED_PATTERN = re.compile(r'^[0-9eE+\-\.,;\[\]\s]+$')

    def __init__(
        self,
        frequencyList=None,
        maxAperture=40.0,
        rmsVelocity=2000.0,
        focalDepth=2000.0,
        useBinningAreaCenter=True,
        analysisLocation=None,
    ):
        self.frequencyList = self.normalizeFrequencyList(frequencyList if frequencyList is not None else [40.0])
        self.maxAperture = float(maxAperture)
        self.rmsVelocity = float(rmsVelocity)
        self.focalDepth = abs(float(focalDepth))
        self.useBinningAreaCenter = bool(useBinningAreaCenter)
        self.analysisLocation = analysisLocation if analysisLocation is not None else QPointF(0.0, 0.0)

    def writeXml(self, parent: QDomNode, doc: QDomDocument):
        cfpElem = doc.createElement('cfpana')
        cfpElem.setAttribute('frequencies', self.writeFrequencyList(self.frequencyList))
        cfpElem.setAttribute('maxAperture', str(self.maxAperture))
        cfpElem.setAttribute('rmsVelocity', str(self.rmsVelocity))
        cfpElem.setAttribute('focalDepth', str(self.focalDepth))
        cfpElem.setAttribute('useBinningAreaCenter', str(self.useBinningAreaCenter))
        cfpElem.setAttribute('analysisX', str(self.analysisLocation.x()))
        cfpElem.setAttribute('analysisY', str(self.analysisLocation.y()))
        parent.appendChild(cfpElem)
        return cfpElem

    def readXml(self, parent: QDomNode):
        cfpElem = parent.namedItem('cfpana').toElement()
        if cfpElem.isNull():
            return False

        self.frequencyList = self.readFrequencyList(cfpElem.attribute('frequencies'), default=self.frequencyList)
        self.maxAperture = self._clampMaxAperture(toFloat(cfpElem.attribute('maxAperture'), self.maxAperture))
        self.rmsVelocity = max(toFloat(cfpElem.attribute('rmsVelocity'), self.rmsVelocity), 1.0)
        self.focalDepth = abs(toFloat(cfpElem.attribute('focalDepth'), self.focalDepth))
        self.useBinningAreaCenter = toBool(cfpElem.attribute('useBinningAreaCenter'), self.useBinningAreaCenter)
        x = toFloat(cfpElem.attribute('analysisX'), self.analysisLocation.x())
        y = toFloat(cfpElem.attribute('analysisY'), self.analysisLocation.y())
        self.analysisLocation = QPointF(x, y)
        return True

    @staticmethod
    def _clampMaxAperture(value):
        if value < 0.0:
            return 0.0
        if value > 90.0:
            return 90.0
        return float(value)

    @classmethod
    def normalizeFrequencyList(cls, frequencies):
        parsed = []
        for value in frequencies or []:
            try:
                f = float(value)
            except (TypeError, ValueError):
                continue
            if f > 0.0:
                parsed.append(f)

        if not parsed:
            return [40.0]

        parsed.sort()
        return parsed

    @classmethod
    def readFrequencyList(cls, stringValue, default=None):
        if stringValue is None:
            return cls.normalizeFrequencyList(default if default is not None else [40.0])

        stripped = str(stringValue).strip()
        if not stripped:
            return cls.normalizeFrequencyList(default if default is not None else [40.0])

        sanitized = stripped.replace('[', ' ').replace(']', ' ').replace(',', ' ').replace(';', ' ')
        parts = [part for part in sanitized.split() if part]
        return cls.normalizeFrequencyList(parts)

    @classmethod
    def parseFrequencyListInput(cls, stringValue):
        """Strict parser for interactive UI input.

        Accepts numbers separated by whitespace, commas or semicolons (optionally wrapped in brackets).
        Returns (values, isValid).
        """
        if stringValue is None:
            return ([], False)

        stripped = str(stringValue).strip()
        if not stripped:
            return ([], False)

        if cls._FREQ_ALLOWED_PATTERN.match(stripped) is None:
            return ([], False)

        sanitized = stripped.replace('[', ' ').replace(']', ' ').replace(',', ' ').replace(';', ' ')
        parts = [part for part in sanitized.split() if part]
        if not parts:
            return ([], False)

        parsed = []
        for part in parts:
            try:
                value = float(part)
            except (TypeError, ValueError):
                return ([], False)
            if value <= 0.0:
                return ([], False)
            parsed.append(value)

        return (parsed, True)

    @classmethod
    def writeFrequencyList(cls, frequencies):
        normalized = cls.normalizeFrequencyList(frequencies)
        return ';'.join(f'{value:g}' for value in normalized)

    @classmethod
    def writeFrequencyListDisplay(cls, frequencies):
        normalized = cls.normalizeFrequencyList(frequencies)
        return ' '.join(f'{value:g}' for value in normalized)
