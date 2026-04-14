# coding=utf-8

import copy
from dataclasses import dataclass, field

from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtGui import QPen, QVector3D

from . import config


def _defaultSpsFormats():
    return config.getDefaultSpsFormats()


def _defaultXpsFormats():
    return config.getDefaultXpsFormats()


def _defaultRpsFormats():
    return config.getDefaultRpsFormats()


def readStoredDebugpySetting():
    settings = QSettings(config.organization, config.application)
    return settings.value('settings/debug/debugpy', config.DEFAULT_DEBUGPY, type=bool)


def readStoredDebugSetting():
    settings = QSettings(config.organization, config.application)
    return settings.value('settings/debug/logging', config.DEFAULT_DEBUG, type=bool)


def readStoredShowSummariesSetting():
    settings = QSettings(config.organization, config.application)
    return settings.value('settings/misc/showSummaries', config.DEFAULT_SHOW_SUMMARIES, type=bool)


def readStoredShowUnfinishedSetting():
    settings = QSettings(config.organization, config.application)
    return settings.value('settings/misc/showUnfinished', config.DEFAULT_SHOW_UNFINISHED, type=bool)


_debugState = {'enabled': config.DEFAULT_DEBUG}
_summaryState = {'enabled': config.DEFAULT_SHOW_SUMMARIES}
_unfinishedState = {'enabled': config.DEFAULT_SHOW_UNFINISHED}


def setActiveDebugLogging(enabled):
    _debugState['enabled'] = bool(enabled)


def isDebugLoggingEnabled():
    return _debugState['enabled']


def setActiveShowSummaries(enabled):
    _summaryState['enabled'] = bool(enabled)


def isShowSummariesEnabled():
    return _summaryState['enabled']


def setActiveShowUnfinished(enabled):
    _unfinishedState['enabled'] = bool(enabled)


def isShowUnfinishedEnabled():
    return _unfinishedState['enabled']


_activeAppSettingsState = {'settings': None}


@dataclass
class AppSettings:
    binAreaColor: str = config.binAreaColor
    cmpAreaColor: str = config.cmpAreaColor
    recAreaColor: str = config.recAreaColor
    srcAreaColor: str = config.srcAreaColor

    binAreaPen: object = field(default_factory=lambda: QPen(config.binAreaPen))
    cmpAreaPen: object = field(default_factory=lambda: QPen(config.cmpAreaPen))
    recAreaPen: object = field(default_factory=lambda: QPen(config.recAreaPen))
    srcAreaPen: object = field(default_factory=lambda: QPen(config.srcAreaPen))

    analysisCmap: str = config.analysisCmap
    foldDispCmap: str = config.foldDispCmap

    rpsBrushColor: str = config.rpsBrushColor
    rpsPointSymbol: str = config.rpsPointSymbol
    rpsSymbolSize: int = config.rpsSymbolSize
    spsBrushColor: str = config.spsBrushColor
    spsPointSymbol: str = config.spsPointSymbol
    spsSymbolSize: int = config.spsSymbolSize
    spsParallel: bool = config.DEFAULT_SPS_PARALLEL
    spsDialect: str = config.DEFAULT_SPS_DIALECT
    spsFormatList: list[dict] = field(default_factory=_defaultSpsFormats)
    xpsFormatList: list[dict] = field(default_factory=_defaultXpsFormats)
    rpsFormatList: list[dict] = field(default_factory=_defaultRpsFormats)

    recBrushColor: str = config.recBrushColor
    recPointSymbol: str = config.recPointSymbol
    recSymbolSize: int = config.recSymbolSize
    srcBrushColor: str = config.srcBrushColor
    srcPointSymbol: str = config.srcPointSymbol
    srcSymbolSize: int = config.srcSymbolSize

    lod0: float = config.lod0
    lod1: float = config.lod1
    lod2: float = config.lod2
    lod3: float = config.lod3

    kraStack: object = field(default_factory=lambda: QVector3D(config.kraStack))
    kxyStack: object = field(default_factory=lambda: QVector3D(config.kxyStack))
    kxyArray: object = field(default_factory=lambda: QVector3D(config.kxyArray))

    debug: bool = config.DEFAULT_DEBUG
    debugpy: bool = config.DEFAULT_DEBUGPY
    useNumba: bool = config.useNumba
    useRelativePaths: bool = config.useRelativePaths
    showUnfinished: bool = config.DEFAULT_SHOW_UNFINISHED
    showSummaries: bool = config.DEFAULT_SHOW_SUMMARIES

    def resetSpsDatabase(self, preferredDialect=None):
        self.spsFormatList = _defaultSpsFormats()
        self.xpsFormatList = _defaultXpsFormats()
        self.rpsFormatList = _defaultRpsFormats()

        availableDialects = {entry['name'] for entry in self.spsFormatList}
        dialect = preferredDialect if preferredDialect is not None else self.spsDialect
        if dialect not in availableDialects:
            dialect = self.spsFormatList[0]['name'] if self.spsFormatList else ''
        self.spsDialect = dialect

    def activate(self):
        setActiveAppSettings(self)


def cloneAppSettings(appSettings: AppSettings) -> AppSettings:
    return AppSettings(
        binAreaColor=appSettings.binAreaColor,
        cmpAreaColor=appSettings.cmpAreaColor,
        recAreaColor=appSettings.recAreaColor,
        srcAreaColor=appSettings.srcAreaColor,
        binAreaPen=QPen(appSettings.binAreaPen),
        cmpAreaPen=QPen(appSettings.cmpAreaPen),
        recAreaPen=QPen(appSettings.recAreaPen),
        srcAreaPen=QPen(appSettings.srcAreaPen),
        analysisCmap=appSettings.analysisCmap,
        foldDispCmap=appSettings.foldDispCmap,
        rpsBrushColor=appSettings.rpsBrushColor,
        rpsPointSymbol=appSettings.rpsPointSymbol,
        rpsSymbolSize=appSettings.rpsSymbolSize,
        spsBrushColor=appSettings.spsBrushColor,
        spsPointSymbol=appSettings.spsPointSymbol,
        spsSymbolSize=appSettings.spsSymbolSize,
        spsParallel=appSettings.spsParallel,
        spsDialect=appSettings.spsDialect,
        spsFormatList=copy.deepcopy(appSettings.spsFormatList),
        xpsFormatList=copy.deepcopy(appSettings.xpsFormatList),
        rpsFormatList=copy.deepcopy(appSettings.rpsFormatList),
        recBrushColor=appSettings.recBrushColor,
        recPointSymbol=appSettings.recPointSymbol,
        recSymbolSize=appSettings.recSymbolSize,
        srcBrushColor=appSettings.srcBrushColor,
        srcPointSymbol=appSettings.srcPointSymbol,
        srcSymbolSize=appSettings.srcSymbolSize,
        lod0=appSettings.lod0,
        lod1=appSettings.lod1,
        lod2=appSettings.lod2,
        lod3=appSettings.lod3,
        kraStack=QVector3D(appSettings.kraStack),
        kxyStack=QVector3D(appSettings.kxyStack),
        kxyArray=QVector3D(appSettings.kxyArray),
        debug=appSettings.debug,
        debugpy=appSettings.debugpy,
        useNumba=appSettings.useNumba,
        useRelativePaths=appSettings.useRelativePaths,
        showUnfinished=appSettings.showUnfinished,
        showSummaries=appSettings.showSummaries,
    )


def setActiveAppSettings(appSettings: AppSettings) -> AppSettings:
    activeAppSettings = cloneAppSettings(appSettings)
    _activeAppSettingsState['settings'] = activeAppSettings
    setActiveDebugLogging(activeAppSettings.debug)
    setActiveShowUnfinished(activeAppSettings.showUnfinished)
    setActiveShowSummaries(activeAppSettings.showSummaries)
    return activeAppSettings


def getActiveAppSettings() -> AppSettings:
    activeAppSettings = _activeAppSettingsState['settings']
    if activeAppSettings is None:
        activeAppSettings = cloneAppSettings(AppSettings())
        _activeAppSettingsState['settings'] = activeAppSettings
        setActiveDebugLogging(activeAppSettings.debug)
        setActiveShowUnfinished(activeAppSettings.showUnfinished)
        setActiveShowSummaries(activeAppSettings.showSummaries)

    return activeAppSettings
