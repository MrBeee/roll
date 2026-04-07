# coding=utf-8
import unittest
import warnings

import numpy as np


class RollSurveyNumpyApiTest(unittest.TestCase):
    def testPublicRecFromArraysBuildsSortableKeyWithoutCoreDeprecation(self):
        relSrcIndI = np.array([2, 1, 1], dtype=np.int32)
        relSrcLinI = np.array([20, 10, 10], dtype=np.int32)
        relSrcPntI = np.array([200, 100, 101], dtype=np.int32)
        srcIndI = np.array([1, 2], dtype=np.int32)
        srcLinI = np.array([10, 20], dtype=np.int32)
        srcPntI = np.array([100, 200], dtype=np.int32)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            relKey = np.rec.fromarrays([relSrcIndI, relSrcLinI, relSrcPntI], names='Ind,Lin,Pnt')
            srcKey = np.rec.fromarrays([srcIndI, srcLinI, srcPntI], names='Ind,Lin,Pnt')

            relKey.sort()
            srcKey.sort()
            relLeft = np.searchsorted(relKey, srcKey, side='left')
            relRight = np.searchsorted(relKey, srcKey, side='right')

        np.testing.assert_array_equal(relLeft, np.array([0, 2]))
        np.testing.assert_array_equal(relRight, np.array([1, 3]))

        deprecations = [warning for warning in caught if issubclass(warning.category, DeprecationWarning)]
        self.assertEqual(deprecations, [])


if __name__ == '__main__':
    unittest.main()