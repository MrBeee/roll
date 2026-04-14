# coding=utf-8

from dataclasses import dataclass, field

import numpy as np

from .sps_io_and_qc import (calcMaxXPStraces, calculateLineStakeTransform,
                            convertCrs, findRecOrphans, findSrcOrphans,
                            markUniqueRPSrecords, markUniqueSPSrecords,
                            markUniqueXPSrecords, pntType1, readRpsLine,
                            readSpsLine, readXpsLine, relType2)


@dataclass
class ImportBatchResult:
    spsImport: np.ndarray | None = None
    xpsImport: np.ndarray | None = None
    rpsImport: np.ndarray | None = None
    spsRead: int = 0
    xpsRead: int = 0
    rpsRead: int = 0
    cancelled: bool = False
    cancelMessage: str | None = None


@dataclass
class ImportQcResult:
    messages: list[str] = field(default_factory=list)
    showRpsList: bool = False
    showSpsList: bool = False


class ImportService:
    def importTextData(
        self,
        *,
        spsData=None,
        xpsData=None,
        rpsData=None,
        spsFormat=None,
        xpsFormat=None,
        rpsFormat=None,
        shouldCancel=None,
        progressCallback=None,
    ) -> ImportBatchResult:
        result = ImportBatchResult()

        result.spsImport, result.spsRead, cancelled = self._importPointData(
            data=spsData,
            dtype=pntType1,
            reader=readSpsLine,
            formatSpec=spsFormat,
            label='SPS',
            shouldCancel=shouldCancel,
            progressCallback=progressCallback,
        )
        if cancelled:
            result.cancelled = True
            result.cancelMessage = 'Import : importing SPS data canceled by user.'
            return result

        result.xpsImport, result.xpsRead, cancelled = self._importPointData(
            data=xpsData,
            dtype=relType2,
            reader=readXpsLine,
            formatSpec=xpsFormat,
            label='XPS',
            shouldCancel=shouldCancel,
            progressCallback=progressCallback,
        )
        if cancelled:
            result.cancelled = True
            result.cancelMessage = 'Import : importing XPS data canceled by user.'
            return result

        result.rpsImport, result.rpsRead, cancelled = self._importPointData(
            data=rpsData,
            dtype=pntType1,
            reader=readRpsLine,
            formatSpec=rpsFormat,
            label='RPS',
            shouldCancel=shouldCancel,
            progressCallback=progressCallback,
        )
        if cancelled:
            result.cancelled = True
            result.cancelMessage = 'Import : importing RPS data canceled by user.'
            return result

        return result

    def runQualityChecks(self, *, rpsImport=None, spsImport=None, xpsImport=None, importCrs=None, surveyCrs=None, progressCallback=None) -> ImportQcResult:
        result = ImportQcResult()

        nQcSteps = 0
        if rpsImport is not None:
            nQcSteps += 1
        if spsImport is not None:
            nQcSteps += 1
        if xpsImport is not None:
            nQcSteps += 1
        if spsImport is not None and xpsImport is not None:
            nQcSteps += 1
        if rpsImport is not None and xpsImport is not None:
            nQcSteps += 1

        nQcStep = 0
        nQcIncrement = 100 // nQcSteps if nQcSteps > 0 else 0

        if rpsImport is not None:
            self._reportQcProgress(progressCallback, nQcStep, nQcSteps, nQcIncrement, 'analysing rps-records')
            nQcStep += 1
            nImport = rpsImport.shape[0]
            nUnique = markUniqueRPSrecords(rpsImport, sort=True)
            result.messages.append(f'Import : . . . analysed rps-records; found {nUnique:,} unique records and {(nImport - nUnique):,} duplicates')

            convertCrs(rpsImport, importCrs, surveyCrs)
            origX, origY, pMin, lMin, dPint, dLint, dPn, dLn, angle1 = calculateLineStakeTransform(rpsImport)
            result.messages.extend(self._lineTransformMessages(origX, origY, pMin, lMin, dPint, dLint, dPn, dLn, angle1))
            result.showRpsList = True

        if spsImport is not None:
            self._reportQcProgress(progressCallback, nQcStep, nQcSteps, nQcIncrement, 'analysing sps-records')
            nQcStep += 1
            nImport = spsImport.shape[0]
            nUnique = markUniqueSPSrecords(spsImport, sort=True)
            result.messages.append(f'Import : . . . analysed sps-records; found {nUnique:,} unique records and {(nImport - nUnique):,} duplicates')

            convertCrs(spsImport, importCrs, surveyCrs)
            origX, origY, pMin, lMin, dPint, dLint, dPn, dLn, angle1 = calculateLineStakeTransform(spsImport)
            result.messages.extend(self._lineTransformMessages(origX, origY, pMin, lMin, dPint, dLint, dPn, dLn, angle1))
            result.showSpsList = True

        if xpsImport is not None:
            self._reportQcProgress(progressCallback, nQcStep, nQcSteps, nQcIncrement, 'analysing xps-records')
            nQcStep += 1
            nImport = xpsImport.shape[0]
            nUnique = markUniqueXPSrecords(xpsImport, sort=True)
            result.messages.append(f'Import : . . . analysed xps-records; found {nUnique:,} unique records and {(nImport - nUnique):,} duplicates')

            traces = calcMaxXPStraces(xpsImport)
            result.messages.append(f'Import : . . . the xps-records define a maximum of {traces:,} traces')

        if spsImport is not None and xpsImport is not None:
            self._reportQcProgress(progressCallback, nQcStep, nQcSteps, nQcIncrement, 'analysing sps-xps orphans')
            nQcStep += 1
            nSpsOrphans, nXpsOrphans = findSrcOrphans(spsImport, xpsImport)
            result.messages.append(f'Import : . . . sps-records contain {nXpsOrphans:,} xps-orphans')
            result.messages.append(f'Import : . . . xps-records contain {nSpsOrphans:,} sps-orphans')

        if rpsImport is not None and xpsImport is not None:
            self._reportQcProgress(progressCallback, nQcStep, nQcSteps, nQcIncrement, 'analysing xps-rps orphans')
            nRpsOrphans, nXpsOrphans = findRecOrphans(rpsImport, xpsImport)
            result.messages.append(f'Import : . . . rps-records contain {nXpsOrphans:,} xps-orphans')
            result.messages.append(f'Import : . . . xps-records contain {nRpsOrphans:,} rps-orphans')

        return result

    def _importPointData(self, *, data, dtype, reader, formatSpec, label, shouldCancel=None, progressCallback=None):
        if not data:
            return (None, 0, False)

        lines = len(data)
        imported = np.zeros(shape=lines, dtype=dtype)
        importedCount = 0
        oldProgress = 0

        if progressCallback is not None:
            progressCallback(f'Importing {lines} lines of {label} data...', 0)

        for lineNumber, line in enumerate(data):
            if shouldCancel is not None and shouldCancel():
                return (None, 0, True)

            progress = (100 * lineNumber) // lines if lines > 0 else 100
            if progress > oldProgress:
                oldProgress = progress
                if progressCallback is not None:
                    progressCallback(f'Importing {lines} lines of {label} data...', progress)

            importedCount += reader(importedCount, line, imported, formatSpec)

        if progressCallback is not None:
            progressCallback(f'Importing {lines} lines of {label} data...', 100)

        if importedCount < lines:
            imported.resize(importedCount, refcheck=False)

        return (imported, importedCount, False)

    def _reportQcProgress(self, progressCallback, stepIndex, totalSteps, increment, suffix):
        if progressCallback is None:
            return

        progressCallback(f'Import QC step : ({stepIndex + 1} / {totalSteps}) {suffix}', increment * stepIndex)

    def _lineTransformMessages(self, origX, origY, pMin, lMin, dPint, dLint, dPn, dLn, angle1):
        return [
            f'Import : . . . . . . Origin: (E{origX:.2f}m, N{origY:.2f}m) @ (pnt{pMin:.1f}, lin{lMin:.1f})',
            f'Import : . . . . . . Orientation {angle1:,.3f}deg for lines &#8741; x-axis',
            f'Import : . . . . . . Intervals for (line, point) in design (lin{dLint:,.2f}m, pnt{dPint:,.2f}m)',
            f'Import : . . . . . . Increments for (line, point) in grid (lin{dLn:,.2f}m, pnt{dPn:,.2f}m)',
        ]
