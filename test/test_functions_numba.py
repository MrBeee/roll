# coding=utf-8
import unittest

import numpy as np

from .plugin_loader import loadPluginModule

functionsNumbaModule = loadPluginModule('functions_numba')

numbaNdft1D = functionsNumbaModule.numbaNdft1D
numbaNdft2D = functionsNumbaModule.numbaNdft2D
numbaOffInline = functionsNumbaModule.numbaOffInline
numbaOffXline = functionsNumbaModule.numbaOffXline


class FunctionsNumbaTest(unittest.TestCase):
    def testNumbaNdft1DReturnsFiniteValuesForZeroAmplitudeResponse(self):
        slice3D = np.zeros((1, 2, 13), dtype=np.float32)
        slice3D[0, 0, 10] = 0.0
        slice3D[0, 1, 10] = 1.0
        include3D = np.ones((1, 2), dtype=np.bool_)

        response = numbaNdft1D(1.0, 0.5, slice3D, include3D)

        self.assertTrue(np.isfinite(response).all())
        self.assertLess(response[0, 1], 0.0)

    def testNumbaNdft2DReturnsFiniteValuesForZeroAmplitudeResponse(self):
        offsetX = np.array([0.0, 1.0], dtype=np.float32)
        offsetY = np.array([0.0, 0.0], dtype=np.float32)

        response = numbaNdft2D(0.0, 1.0, 0.5, offsetX, offsetY)

        self.assertTrue(np.isfinite(response).all())
        self.assertLess(response[1, 0], 0.0)

    def testNumbaOffPlotsCanSelectAbsoluteInlineOrXlineComponents(self):
        slice2D = np.zeros((2, 13), dtype=np.float32)
        slice2D[:, 7] = np.array([100.0, 200.0], dtype=np.float32)
        slice2D[:, 8] = np.array([300.0, 400.0], dtype=np.float32)
        slice2D[:, 3] = np.array([10.0, 20.0], dtype=np.float32)
        slice2D[:, 4] = np.array([1.0, 2.0], dtype=np.float32)
        slice2D[:, 5] = np.array([14.0, 29.0], dtype=np.float32)
        slice2D[:, 6] = np.array([6.0, 11.0], dtype=np.float32)
        slice2D[:, 10] = np.array([99.0, 199.0], dtype=np.float32)

        _, absInline = numbaOffInline(slice2D, 5.0, 0)
        _, inlineInline = numbaOffInline(slice2D, 5.0, 1)
        _, xlineInline = numbaOffInline(slice2D, 5.0, 2)

        _, absXline = numbaOffXline(slice2D, 5.0, 0)
        _, inlineXline = numbaOffXline(slice2D, 5.0, 1)
        _, xlineXline = numbaOffXline(slice2D, 5.0, 2)

        np.testing.assert_array_equal(absInline[0::2], np.array([99.0, 199.0], dtype=np.float32))
        np.testing.assert_array_equal(inlineInline[0::2], np.array([4.0, 9.0], dtype=np.float32))
        np.testing.assert_array_equal(xlineInline[0::2], np.array([5.0, 9.0], dtype=np.float32))

        np.testing.assert_array_equal(absXline[0::2], np.array([99.0, 199.0], dtype=np.float32))
        np.testing.assert_array_equal(inlineXline[0::2], np.array([4.0, 9.0], dtype=np.float32))
        np.testing.assert_array_equal(xlineXline[0::2], np.array([5.0, 9.0], dtype=np.float32))


if __name__ == '__main__':
    unittest.main()
