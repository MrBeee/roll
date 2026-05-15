import contextlib
from dataclasses import dataclass

from .enums_and_int_flags import SeedType


@dataclass(frozen=True)
class SeedTypeVisibilityState:
    showOrigin: bool
    showGrid: bool
    showPattern: bool
    showCircle: bool
    showSpiral: bool
    showWell: bool


@dataclass(frozen=True)
class SeedPatternRefreshState:
    patterns: list[str]
    selectedPattern: str
    visibilityState: SeedTypeVisibilityState


class SeedParameterStateHelper:
    seedTypes = ('Grid (roll along)', 'Grid (stationary)', 'Circle', 'Spiral', 'Well')

    def __init__(self, seed, survey=None):
        self.seed = seed
        self.survey = survey

    @classmethod
    def isGridSeedType(cls, seedType):
        return seedType in cls.seedTypes[:2]

    @classmethod
    def visibilityState(cls, seedType):
        isGridSeed = cls.isGridSeedType(seedType)
        isWellSeed = seedType == 'Well'
        return SeedTypeVisibilityState(
            showOrigin=not isWellSeed,
            showGrid=isGridSeed,
            showPattern=isGridSeed,
            showCircle=seedType == 'Circle',
            showSpiral=seedType == 'Spiral',
            showWell=isWellSeed,
        )

    def patternNames(self, root=None):
        patternParam = None
        if root is not None:
            with contextlib.suppress(KeyError):
                patternParam = root.child('Pattern list')

        if patternParam is not None and hasattr(patternParam, 'patternList'):
            return ['<None>'] + [pattern.name for pattern in patternParam.patternList]
        if self.survey is not None:
            return ['<None>'] + [pattern.name for pattern in self.survey.patternList]
        return ['<None>']

    def initialPatternIndex(self, patterns):
        if self.seed.type > SeedType.fixedGrid:
            return 0

        patternIndex = self.seed.patternNo + 1
        if patternIndex >= len(patterns):
            return 0
        return patternIndex

    def applySeedType(self, seedType):
        self.seed.type = SeedType(self.seedTypes.index(seedType))
        if not self.isGridSeedType(seedType):
            self.seed.patternNo = -1
        return self.visibilityState(seedType)

    def selectedPatternValue(self, patterns, seedType):
        if self.isGridSeedType(seedType):
            patternIndex = max(min(self.seed.patternNo + 1, len(patterns) - 1), 0)
        else:
            patternIndex = 0
        return patterns[patternIndex]

    def refreshedPatternState(self, seedType, root=None):
        patterns = self.patternNames(root)
        return SeedPatternRefreshState(
            patterns=patterns,
            selectedPattern=self.selectedPatternValue(patterns, seedType),
            visibilityState=self.visibilityState(seedType),
        )

    def selectedPatternIndex(self, patterns, selectedPattern):
        index = patterns.index(selectedPattern) if selectedPattern in patterns else 0
        self.seed.patternNo = index - 1
        return self.seed.patternNo


class WellParameterStateHelper:
    def __init__(self, well, survey=None):
        self.well = well
        self.survey = survey

    def bindSurvey(self):
        if self.survey is not None:
            self.well.setSurvey(self.survey)

    def refreshHeader(self, *, name=None, crs=None):
        return self.well.refreshHeaderFromCurrentState(
            name=name,
            crs=crs,
            survey=self.survey,
            surveyCrs=self.survey.crs if self.survey is not None else None,
            glbTransform=self.survey.glbTransform if self.survey is not None else None,
        )

    def refreshHeaderOrRaise(self, *, name=None, crs=None):
        return self.well.refreshHeaderFromCurrentStateOrRaise(
            name=name,
            crs=crs,
            survey=self.survey,
            surveyCrs=self.survey.crs if self.survey is not None else None,
            glbTransform=self.survey.glbTransform if self.survey is not None else None,
        )

    def applySamplingConstraints(self, *, ahd0, dAhd, nAhd):
        return self.well.applySamplingConstraints(ahd0=ahd0, dAhd=dAhd, nAhd=nAhd)

    def originValues(self):
        return {
            'well': (self.well.origW.x(), self.well.origW.y(), self.well.origW.z()),
            'global': (self.well.origG.x(), self.well.origG.y()),
            'local': (self.well.origL.x(), self.well.origL.y()),
        }

    def samplingValues(self):
        return self.well.ahd0, self.well.dAhd, self.well.nAhd
