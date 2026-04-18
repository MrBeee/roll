# coding=utf-8
import unittest

from .plugin_loader import loadPluginModule

enumsModule = loadPluginModule('enums_and_int_flags')
rollSeedModule = loadPluginModule('roll_seed')

SeedType = enumsModule.SeedType
RollSeed = rollSeedModule.RollSeed


class RollSeedTest(unittest.TestCase):
    def testTypeAssignmentNormalizesIntToSeedType(self):
        seed = RollSeed()

        seed.type = 2

        self.assertIsInstance(seed.type, SeedType)
        self.assertEqual(seed.type, SeedType.circle)


if __name__ == '__main__':
    unittest.main()
