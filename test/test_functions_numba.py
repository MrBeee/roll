# coding=utf-8
import unittest

import numpy as np

from .plugin_loader import loadPluginModule

functionsNumbaModule = loadPluginModule('functions_numba')

numbaNdft1D = functionsNumbaModule.numbaNdft1D
numbaNdft2D = functionsNumbaModule.numbaNdft2D


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


if __name__ == '__main__':
    unittest.main()
