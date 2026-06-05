# coding=utf-8
import unittest

from .plugin_loader import loadPluginModule

rollCfpModule = loadPluginModule('roll_cfp')
RollCfp = rollCfpModule.RollCfp


class RollCfpFrequencyParsingTest(unittest.TestCase):
    def testParseFrequencyListInputAcceptsStandardSeparators(self):
        values, isValid = RollCfp.parseFrequencyListInput('10, 20; 30 40')

        self.assertTrue(isValid)
        self.assertEqual(values, [10.0, 20.0, 30.0, 40.0])

    def testParseFrequencyListInputRejectsColonSeparator(self):
        values, isValid = RollCfp.parseFrequencyListInput('10:20:30:40')

        self.assertFalse(isValid)
        self.assertEqual(values, [])

    def testNormalizeFrequencyListSortsAscending(self):
        values = RollCfp.normalizeFrequencyList([30.0, 10.0, 20.0])

        self.assertEqual(values, [10.0, 20.0, 30.0])

    def testWriteFrequencyListDisplayUsesSpaceSeparatedSortedValues(self):
        display = RollCfp.writeFrequencyListDisplay([30.0, 10.0, 20.0])

        self.assertEqual(display, '10 20 30')

    def testWriteFrequencyListKeepsSemicolonSeparatedXmlFormat(self):
        xmlValue = RollCfp.writeFrequencyList([30.0, 10.0, 20.0])

        self.assertEqual(xmlValue, '10;20;30')


if __name__ == '__main__':
    unittest.main()
