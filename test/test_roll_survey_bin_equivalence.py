# coding=utf-8
"""
Equivalence regression tests for binFromGeometry8() vs binFromGeometry10().

binFromGeometry10() is an in-place optimization of binFromGeometry8() that
replaces:
  * the per-shot boolean OR-scan of the full recGeom in
    selectReceiversForSourceRelationSlice() with a contiguous-slice
    receiver lookup, and
  * the per-point QTransform.map() loop in
    updateBinOutputsForValidCmpPoints() with a 2x3 affine matmul.

Both differences are pure performance changes; the resulting binOutput,
minOffset, maxOffset and anaOutput arrays must be identical to those of
binFromGeometry8() on the same inputs. This test pins that contract so a
future regression in either path is caught immediately.

binFromGeometry9() (Numba batch-parallel kernel) is intentionally NOT
compared here: it is known to diverge semantically from #8 (CMP-only,
no InUse gating, no rctOutput / rctOffsets / radOffsets filters, no
azimuth write).
"""

import unittest

import numpy as np
from qgis.core import QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QRectF

from .plugin_loader import loadPluginModule
from .utilities import getQgisApp

QGIS_APP = getQgisApp()

rollSurveyModule = loadPluginModule('roll_survey')

RollSurvey = rollSurveyModule.RollSurvey
BinningType = rollSurveyModule.BinningType
pntType1 = rollSurveyModule.pntType1
relType2 = rollSurveyModule.relType2


class BinFromGeometryEquivalenceTest(unittest.TestCase):
    """Compare binFromGeometry8() and binFromGeometry10() on identical inputs."""

    def buildSurvey(self):
        """Configure a small CMP survey covering a 100x100 area on a 10x10 bin grid."""
        survey = RollSurvey('Bin-Equivalence-Test')
        survey.crs = QgsCoordinateReferenceSystem('EPSG:23095')
        survey.grid.orig.setX(0.0)
        survey.grid.orig.setY(0.0)
        survey.grid.angle = 0.0
        survey.grid.scale.setX(1.0)
        survey.grid.scale.setY(1.0)
        survey.grid.binSize.setX(10.0)
        survey.grid.binSize.setY(10.0)
        survey.grid.stakeOrig.setX(1000.0)
        survey.grid.stakeOrig.setY(1000.0)
        survey.grid.stakeSize.setX(10.0)
        survey.grid.stakeSize.setY(10.0)
        survey.grid.fold = 16
        survey.output.rctOutput = QRectF(0.0, 0.0, 100.0, 100.0)
        survey.offset.rctOffsets = QRectF(-100.0, -100.0, 200.0, 200.0)
        survey.offset.radOffsets.setX(0.0)
        survey.offset.radOffsets.setY(0.0)
        survey.binning.method = BinningType.cmp
        survey.binning.vint = 0.0
        return survey

    def populateGeometry(self, survey):
        """
        Build a synthetic survey:
          * 3 sources on line 1001 at points 1001..1003, LocX 10/20/30, LocY 70.
          * 6 receivers on line 2001 at points 3001..3006, LocX 0..50 step 10, LocY 30.
          * one relation record per source covering the full receiver line.
        All Index, Line, Point, LocX/LocY values are deterministic so any
        divergence between #8 and #10 will be visible in the output arrays.
        """
        srcGeom = np.zeros(shape=(3,), dtype=pntType1)
        for i in range(3):
            srcGeom[i]['Index'] = 1
            srcGeom[i]['Line'] = 1001
            srcGeom[i]['Point'] = 1001 + i
            srcGeom[i]['LocX'] = 10.0 * (i + 1)
            srcGeom[i]['LocY'] = 70.0
            srcGeom[i]['Elev'] = 0.0
            srcGeom[i]['East'] = srcGeom[i]['LocX']
            srcGeom[i]['North'] = srcGeom[i]['LocY']
            srcGeom[i]['InUse'] = 1
            srcGeom[i]['Uniq'] = 1
            srcGeom[i]['InXps'] = 1
            srcGeom[i]['Code'] = 'E1'

        recGeom = np.zeros(shape=(6,), dtype=pntType1)
        for j in range(6):
            recGeom[j]['Index'] = 1
            recGeom[j]['Line'] = 2001
            recGeom[j]['Point'] = 3001 + j
            recGeom[j]['LocX'] = 10.0 * j
            recGeom[j]['LocY'] = 30.0
            recGeom[j]['Elev'] = 0.0
            recGeom[j]['East'] = recGeom[j]['LocX']
            recGeom[j]['North'] = recGeom[j]['LocY']
            recGeom[j]['InUse'] = 1
            recGeom[j]['Uniq'] = 1
            recGeom[j]['InXps'] = 1
            recGeom[j]['Code'] = 'G1'

        relGeom = np.zeros(shape=(3,), dtype=relType2)
        for i in range(3):
            relGeom[i]['SrcInd'] = 1
            relGeom[i]['SrcLin'] = 1001
            relGeom[i]['SrcPnt'] = 1001 + i
            relGeom[i]['RecInd'] = 1
            relGeom[i]['RecLin'] = 2001
            relGeom[i]['RecMin'] = 3001
            relGeom[i]['RecMax'] = 3006
            relGeom[i]['RecNum'] = 6
            relGeom[i]['Uniq'] = 1
            relGeom[i]['InSps'] = 1
            relGeom[i]['InRps'] = 1

        survey.output.srcGeom = srcGeom
        survey.output.recGeom = recGeom
        survey.output.relGeom = relGeom
        survey.nShotPoints = srcGeom.shape[0]

    def runBinning(self, binFnName, fullAnalysis):
        """Build a fresh survey, run the chosen binner, return the output arrays."""
        survey = self.buildSurvey()
        self.populateGeometry(survey)
        survey.calcTransforms(createArrays=True)

        # binFromGeometry8/10 read self.binning.slowness when computing
        # anaOutput[..., 9]. setupBinFromGeometry() normally sets it from
        # vint; bypass that by setting it explicitly so the binners can
        # be invoked directly.
        survey.binning.slowness = 0.0

        if fullAnalysis:
            nx, ny = survey.output.binOutput.shape
            survey.output.anaOutput = np.zeros(
                shape=(nx, ny, survey.grid.fold, 16), dtype=np.float32
            )

        binFn = getattr(survey, binFnName)
        success = binFn(fullAnalysis)
        self.assertTrue(success, f'{binFnName} returned False')

        return survey

    def testBinFromGeometry10MatchesBinFromGeometry8FastPath(self):
        """fullAnalysis=False: binOutput / minOffset / maxOffset must match exactly."""
        survey8 = self.runBinning('binFromGeometry8', False)
        survey10 = self.runBinning('binFromGeometry10', False)

        # Some traces must actually land in the bin grid - otherwise this test
        # would pass trivially on two empty arrays.
        self.assertGreater(int(survey8.output.binOutput.sum()), 0)

        np.testing.assert_array_equal(
            survey8.output.binOutput, survey10.output.binOutput
        )
        np.testing.assert_allclose(
            survey8.output.minOffset, survey10.output.minOffset, rtol=0, atol=1e-5
        )
        np.testing.assert_allclose(
            survey8.output.maxOffset, survey10.output.maxOffset, rtol=0, atol=1e-5
        )

        self.assertEqual(survey8.output.maximumFold, survey10.output.maximumFold)
        self.assertEqual(survey8.output.minimumFold, survey10.output.minimumFold)

    def testBinFromGeometry10MatchesBinFromGeometry8FullAnalysis(self):
        """
        fullAnalysis=True: binOutput / minOffset / maxOffset / anaOutput must match.

        anaOutput per-bin trace ordering depends on receiver iteration order.
        binFromGeometry8 collapses receivers via a boolean OR (preserving
        recGeom array order); binFromGeometry10 uses np.unique on indices
        (also preserving order). On identical inputs both produce identical
        orderings, so we compare with assert_array_equal directly. If a future
        change introduces a legitimate reorder (e.g. parallelism), switch to
        np.sort(..., axis=2) before comparing.
        """
        survey8 = self.runBinning('binFromGeometry8', True)
        survey10 = self.runBinning('binFromGeometry10', True)

        np.testing.assert_array_equal(
            survey8.output.binOutput, survey10.output.binOutput
        )
        np.testing.assert_allclose(
            survey8.output.minOffset, survey10.output.minOffset, rtol=0, atol=1e-5
        )
        np.testing.assert_allclose(
            survey8.output.maxOffset, survey10.output.maxOffset, rtol=0, atol=1e-5
        )

        self.assertIsNotNone(survey8.output.anaOutput)
        self.assertIsNotNone(survey10.output.anaOutput)
        self.assertEqual(survey8.output.anaOutput.shape, survey10.output.anaOutput.shape)

        # Column 9 is the (currently unused) travel-time placeholder; both
        # paths leave it at zero. Compare every column verbatim.
        np.testing.assert_allclose(
            survey8.output.anaOutput,
            survey10.output.anaOutput,
            rtol=0,
            atol=1e-4,
        )

    def testBinFromGeometry10HonorsRadialOffsetFilter(self):
        """
        Radial offset filtering is one of the semantic features that
        binFromGeometry9 silently drops. Pin the contract that #10 still
        applies it, and that #8 and #10 agree under that filter.
        """
        survey8 = self.buildSurvey()
        survey8.offset.radOffsets.setX(15.0)   # min radius
        survey8.offset.radOffsets.setY(45.0)   # max radius
        self.populateGeometry(survey8)
        survey8.calcTransforms(createArrays=True)
        survey8.binning.slowness = 0.0
        self.assertTrue(survey8.binFromGeometry8(False))

        survey10 = self.buildSurvey()
        survey10.offset.radOffsets.setX(15.0)
        survey10.offset.radOffsets.setY(45.0)
        self.populateGeometry(survey10)
        survey10.calcTransforms(createArrays=True)
        survey10.binning.slowness = 0.0
        self.assertTrue(survey10.binFromGeometry10(False))

        np.testing.assert_array_equal(
            survey8.output.binOutput, survey10.output.binOutput
        )
        np.testing.assert_allclose(
            survey8.output.minOffset, survey10.output.minOffset, rtol=0, atol=1e-5
        )
        np.testing.assert_allclose(
            survey8.output.maxOffset, survey10.output.maxOffset, rtol=0, atol=1e-5
        )

        # The radial filter must actually have rejected at least one trace
        # (the closest src/rec pair has hypot < 15), otherwise we are not
        # really exercising the filter.
        unfilteredSurvey = self.buildSurvey()
        self.populateGeometry(unfilteredSurvey)
        unfilteredSurvey.calcTransforms(createArrays=True)
        unfilteredSurvey.binning.slowness = 0.0
        self.assertTrue(unfilteredSurvey.binFromGeometry8(False))
        self.assertGreater(
            int(unfilteredSurvey.output.binOutput.sum()),
            int(survey10.output.binOutput.sum()),
        )


if __name__ == '__main__':
    unittest.main()
