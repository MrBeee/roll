# coding=utf-8
import unittest
import warnings

import numpy as np

from .plugin_loader import loadPluginModule

rdpModule = loadPluginModule('rdp')

dist2 = rdpModule.dist2
filterRdp = rdpModule.filterRdp


class RdpTest(unittest.TestCase):
    def testDist2MatchesExpectedPerpendicularDistance(self):
        points = np.array([[1.0, 1.0], [2.0, 0.0]], dtype=np.float64)
        start = np.array([0.0, 0.0], dtype=np.float64)
        end = np.array([2.0, 0.0], dtype=np.float64)

        result = dist2(points, start, end)

        np.testing.assert_allclose(result, np.array([1.0, 0.0], dtype=np.float64))

    def testFilterRdpDoesNotEmitTwoDimensionalCrossWarning(self):
        points = np.array([[0.0, 0.0], [1.0, 0.2], [2.0, 0.0]], dtype=np.float64)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            mask = filterRdp(points, threshold=0.1)

        self.assertEqual(mask.tolist(), [True, True, True])
        deprecations = [warning for warning in caught if issubclass(warning.category, DeprecationWarning)]
        self.assertEqual(deprecations, [])


if __name__ == '__main__':
    unittest.main()
