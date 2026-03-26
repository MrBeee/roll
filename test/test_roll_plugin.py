# coding=utf-8
"""Minimal plugin entry-point tests."""

__author__ = 'Bart.Duijndam@ziggo.nl'
__date__ = '2026-03-13'
__copyright__ = 'Copyright 2022, Duijndam.Dev'

import importlib.util
import os
import sys
import types
import unittest

from .utilities import getQgisApp

QGIS_APP, _, IFACE, _ = getQgisApp()

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(TEST_DIR)
FAKE_PACKAGE = 'roll_testpkg'


def loadPluginModule(moduleName):
    if FAKE_PACKAGE not in sys.modules:
        package = types.ModuleType(FAKE_PACKAGE)
        package.__path__ = [PLUGIN_ROOT]
        sys.modules[FAKE_PACKAGE] = package

    qualifiedName = f'{FAKE_PACKAGE}.{moduleName}'
    if qualifiedName in sys.modules:
        return sys.modules[qualifiedName]

    filePath = os.path.join(PLUGIN_ROOT, f'{moduleName}.py')
    spec = importlib.util.spec_from_file_location(qualifiedName, filePath)
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualifiedName] = module
    spec.loader.exec_module(module)
    return module


rollModule = loadPluginModule('roll')
rollMainWindowModule = loadPluginModule('roll_main_window')

Roll = rollModule.Roll
RollMainWindow = rollMainWindowModule.RollMainWindow


class RollPluginTest(unittest.TestCase):
    """Test the current plugin entry point."""

    def setUp(self):
        self.plugin = Roll(IFACE)

    def tearDown(self):
        if self.plugin.mainWindow is not None:
            self.plugin.mainWindow.close()
            self.plugin.mainWindow.deleteLater()
        self.plugin = None

    def testInitGuiAddsPluginAction(self):
        self.plugin.initGui()

        self.assertTrue(self.plugin.firstStart)
        self.assertEqual(len(self.plugin.actions), 1)

    def testRunCreatesMainWindow(self):
        self.plugin.initGui()
        self.plugin.run()

        self.assertIsNotNone(self.plugin.mainWindow)
        self.assertIsInstance(self.plugin.mainWindow, RollMainWindow)
        self.assertFalse(self.plugin.firstStart)


if __name__ == '__main__':
    unittest.main()
