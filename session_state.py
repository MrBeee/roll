# coding=utf-8

from dataclasses import dataclass

import numpy as np


@dataclass
class SessionState:
    rpsImport: np.ndarray | None = None
    spsImport: np.ndarray | None = None
    xpsImport: np.ndarray | None = None
    recGeom: np.ndarray | None = None
    srcGeom: np.ndarray | None = None
    relGeom: np.ndarray | None = None

    rpsLiveE: np.ndarray | None = None
    rpsLiveN: np.ndarray | None = None
    rpsDeadE: np.ndarray | None = None
    rpsDeadN: np.ndarray | None = None

    spsLiveE: np.ndarray | None = None
    spsLiveN: np.ndarray | None = None
    spsDeadE: np.ndarray | None = None
    spsDeadN: np.ndarray | None = None

    recLiveE: np.ndarray | None = None
    recLiveN: np.ndarray | None = None
    recDeadE: np.ndarray | None = None
    recDeadN: np.ndarray | None = None

    srcLiveE: np.ndarray | None = None
    srcLiveN: np.ndarray | None = None
    srcDeadE: np.ndarray | None = None
    srcDeadN: np.ndarray | None = None

    rpsBound: np.ndarray | None = None
    spsBound: np.ndarray | None = None

    def clearImportedArrays(self):
        self.rpsImport = None
        self.spsImport = None
        self.xpsImport = None
        self.rpsLiveE = None
        self.rpsLiveN = None
        self.rpsDeadE = None
        self.rpsDeadN = None
        self.spsLiveE = None
        self.spsLiveN = None
        self.spsDeadE = None
        self.spsDeadN = None
        self.rpsBound = None
        self.spsBound = None

    def clearGeometryArrays(self):
        self.recGeom = None
        self.srcGeom = None
        self.relGeom = None
        self.recLiveE = None
        self.recLiveN = None
        self.recDeadE = None
        self.recDeadN = None
        self.srcLiveE = None
        self.srcLiveN = None
        self.srcDeadE = None
        self.srcDeadN = None

    def clearSurveyArrays(self):
        self.clearImportedArrays()
        self.clearGeometryArrays()
