# coding=utf-8
import importlib.util
import os
import sys
import types

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(TEST_DIR)
FAKE_PACKAGE = 'roll_testpkg'
TEST_SETTINGS_ORGANIZATION = 'Duijndam.Dev.Tests'
TEST_SETTINGS_APPLICATION = 'Roll.Tests'


def _ensureTestSettingsNamespace():
    qualifiedName = f'{FAKE_PACKAGE}.config'
    if qualifiedName in sys.modules:
        configModule = sys.modules[qualifiedName]
    else:
        filePath = os.path.join(PLUGIN_ROOT, 'config.py')
        spec = importlib.util.spec_from_file_location(qualifiedName, filePath)
        configModule = importlib.util.module_from_spec(spec)
        sys.modules[qualifiedName] = configModule
        spec.loader.exec_module(configModule)

    configModule.organization = TEST_SETTINGS_ORGANIZATION
    configModule.application = TEST_SETTINGS_APPLICATION
    return configModule


def loadPluginModule(moduleName):
    if FAKE_PACKAGE not in sys.modules:
        package = types.ModuleType(FAKE_PACKAGE)
        package.__path__ = [PLUGIN_ROOT]
        sys.modules[FAKE_PACKAGE] = package

    _ensureTestSettingsNamespace()

    qualifiedName = f'{FAKE_PACKAGE}.{moduleName}'
    if qualifiedName in sys.modules:
        return sys.modules[qualifiedName]

    filePath = os.path.join(PLUGIN_ROOT, f'{moduleName}.py')
    spec = importlib.util.spec_from_file_location(qualifiedName, filePath)
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualifiedName] = module
    spec.loader.exec_module(module)
    return module
