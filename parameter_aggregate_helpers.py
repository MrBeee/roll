from dataclasses import dataclass

from .enums_and_int_flags import SurveyType


@dataclass(frozen=True)
class AnalysisParameterValues:
    area: object
    angles: object
    binning: object
    offset: object
    unique: object

    def asTuple(self):
        return (self.area, self.angles, self.binning, self.offset, self.unique)


@dataclass(frozen=True)
class ConfigurationParameterValues:
    crs: object
    typ: str
    nam: str

    def asTuple(self):
        return (self.crs, self.typ, self.nam)


@dataclass(frozen=True)
class ReflectorParameterValues:
    plane: object
    sphere: object

    def asTuple(self):
        return (self.plane, self.sphere)


@dataclass(frozen=True)
class CfpAnalysisParameterValues:
    frequencyList: list[float]
    maxAperture: float
    rmsVelocity: float
    focalDepth: float
    useBinningAreaCenter: bool
    analysisLocation: object

    def asTuple(self):
        return (
            self.frequencyList,
            self.maxAperture,
            self.rmsVelocity,
            self.focalDepth,
            self.useBinningAreaCenter,
            self.analysisLocation,
        )


@dataclass(frozen=True)
class BlockParameterValues:
    srcBorder: object
    recBorder: object
    templateList: object

    def asTuple(self):
        return (self.srcBorder, self.recBorder, self.templateList)


@dataclass(frozen=True)
class TemplateParameterValues:
    rollList: object
    seedList: object

    def asTuple(self):
        return (self.rollList, self.seedList)


def analysisValuesFromSurvey(survey):
    return AnalysisParameterValues(
        area=survey.output.rctOutput,
        angles=survey.angles,
        binning=survey.binning,
        offset=survey.offset,
        unique=survey.unique,
    )


def analysisValuesFromParameters(*, area, angles, binning, offset, unique):
    return AnalysisParameterValues(
        area=area,
        angles=angles,
        binning=binning,
        offset=offset,
        unique=unique,
    )


def configurationValuesFromSurvey(survey):
    return ConfigurationParameterValues(
        crs=survey.crs,
        typ=survey.type.name,
        nam=survey.name,
    )


def applyConfigurationValues(survey, *, crs, typ, nam):
    values = ConfigurationParameterValues(crs=crs, typ=typ, nam=nam)
    if survey is not None:
        survey.crs = values.crs
        survey.type = SurveyType[values.typ]
        survey.name = values.nam
    return values


def applyLocalGridValues(binGrid, localGrid):
    binGrid.binSize = localGrid.binSize
    binGrid.binShift = localGrid.binShift
    binGrid.stakeOrig = localGrid.stakeOrig
    binGrid.stakeSize = localGrid.stakeSize
    binGrid.fold = localGrid.fold
    return binGrid


def applyGlobalGridValues(binGrid, globalGrid):
    binGrid.orig = globalGrid.orig
    binGrid.scale = globalGrid.scale
    binGrid.angle = globalGrid.angle
    return binGrid


def reflectorValuesFromSurvey(survey):
    return ReflectorParameterValues(
        plane=survey.globalPlane,
        sphere=survey.globalSphere,
    )


def reflectorValuesFromParameters(*, plane, sphere):
    return ReflectorParameterValues(plane=plane, sphere=sphere)


def cfpAnalysisValuesFromSurvey(survey):
    cfp = survey.cfp
    return CfpAnalysisParameterValues(
        frequencyList=list(cfp.frequencyList),
        maxAperture=cfp.maxAperture,
        rmsVelocity=cfp.rmsVelocity,
        focalDepth=cfp.focalDepth,
        useBinningAreaCenter=cfp.useBinningAreaCenter,
        analysisLocation=cfp.analysisLocation,
    )


def applyCfpAnalysisValues(survey, *, frequencyList, maxAperture, rmsVelocity, focalDepth, useBinningAreaCenter, analysisLocation):
    values = CfpAnalysisParameterValues(
        frequencyList=list(frequencyList),
        maxAperture=float(maxAperture),
        rmsVelocity=float(rmsVelocity),
        focalDepth=float(focalDepth),
        useBinningAreaCenter=bool(useBinningAreaCenter),
        analysisLocation=analysisLocation,
    )
    if survey is not None:
        survey.cfp.frequencyList = values.frequencyList
        survey.cfp.maxAperture = values.maxAperture
        survey.cfp.rmsVelocity = values.rmsVelocity
        survey.cfp.focalDepth = values.focalDepth
        survey.cfp.useBinningAreaCenter = values.useBinningAreaCenter
        survey.cfp.analysisLocation = values.analysisLocation
    return values


def blockValuesFromBlock(block):
    return BlockParameterValues(
        srcBorder=block.borders.srcBorder,
        recBorder=block.borders.recBorder,
        templateList=block.templateList,
    )


def applyBlockValues(block, *, srcBorder, recBorder, templateList):
    values = BlockParameterValues(srcBorder=srcBorder, recBorder=recBorder, templateList=templateList)
    block.borders.srcBorder = values.srcBorder
    block.borders.recBorder = values.recBorder
    block.templateList = values.templateList
    return values


def templateValuesFromTemplate(template):
    return TemplateParameterValues(
        rollList=template.rollList,
        seedList=template.seedList,
    )


def applyTemplateValues(template, *, rollList, seedList):
    values = TemplateParameterValues(rollList=rollList, seedList=seedList)
    template.rollList = values.rollList
    template.seedList = values.seedList
    return values
