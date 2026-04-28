# coding=utf-8
import unittest

from .plugin_loader import loadPluginModule

helpersModule = loadPluginModule('parameter_list_helpers')

appendManagedParameterItem = helpersModule.appendManagedParameterItem
moveManagedParameterItem = helpersModule.moveManagedParameterItem
nextManagedChildName = helpersModule.nextManagedChildName
removeManagedParameterItem = helpersModule.removeManagedParameterItem
swapManagedParameterItems = helpersModule.swapManagedParameterItems


class _FakeSignal:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


class _FakeItem:
    def __init__(self, name=None):
        self.removed = False
        self._name = name

    def remove(self):
        self.removed = True

    def name(self):
        return self._name


class _FakeParent:
    def __init__(self):
        self.addCalls = []
        self.callbackCalls = []
        self.insertCalls = []
        self.childs = []
        self.sigAddNew = _FakeSignal()
        self.sigChildRemoved = _FakeSignal()
        self.sigValueChanging = _FakeSignal()

    def addChild(self, childDict):
        self.addCalls.append(childDict)

    def insertChild(self, index, childDict):
        self.insertCalls.append((index, childDict))

    def value(self):
        return ['value']

    def mark(self, *args):
        self.callbackCalls.append(args)


class ParameterListHelpersTest(unittest.TestCase):
    def testRemoveManagedParameterItemRemovesAndEmits(self):
        item = _FakeItem()
        parent = _FakeParent()
        collection = ['a', 'b', 'c']

        removed = removeManagedParameterItem(item, parent, collection, 1, confirmRemoval=lambda: True)

        self.assertTrue(removed)
        self.assertTrue(item.removed)
        self.assertEqual(collection, ['a', 'c'])
        self.assertEqual(parent.sigChildRemoved.calls, [(item, parent)])

    def testRemoveManagedParameterItemSkipsWhenNotConfirmed(self):
        item = _FakeItem()
        parent = _FakeParent()
        collection = ['a', 'b']

        removed = removeManagedParameterItem(item, parent, collection, 0, confirmRemoval=lambda: False)

        self.assertFalse(removed)
        self.assertFalse(item.removed)
        self.assertEqual(collection, ['a', 'b'])
        self.assertEqual(parent.sigChildRemoved.calls, [])

    def testRemoveManagedParameterItemRunsAfterRemoveCallback(self):
        item = _FakeItem()
        parent = _FakeParent()
        collection = ['a', 'b', 'c']

        removeManagedParameterItem(
            item,
            parent,
            collection,
            2,
            confirmRemoval=lambda: True,
            afterRemove=lambda index: parent.mark('removed', index),
        )

        self.assertEqual(parent.callbackCalls, [('removed', 2)])

    def testMoveManagedParameterItemMovesAndReinserts(self):
        item = _FakeItem()
        parent = _FakeParent()
        collection = ['a', 'b', 'c']

        moved = moveManagedParameterItem(
            item,
            parent,
            collection,
            1,
            offset=-1,
            childFactory=lambda value: {'name': value.upper()},
        )

        self.assertTrue(moved)
        self.assertTrue(item.removed)
        self.assertEqual(collection, ['b', 'a', 'c'])
        self.assertEqual(parent.insertCalls, [(0, {'name': 'B'})])

    def testMoveManagedParameterItemSkipsOutOfRangeMove(self):
        item = _FakeItem()
        parent = _FakeParent()
        collection = ['a', 'b']

        moved = moveManagedParameterItem(
            item,
            parent,
            collection,
            0,
            offset=-1,
            childFactory=lambda value: {'name': value},
        )

        self.assertFalse(moved)
        self.assertFalse(item.removed)
        self.assertEqual(collection, ['a', 'b'])
        self.assertEqual(parent.insertCalls, [])

    def testMoveManagedParameterItemRunsAfterMoveCallback(self):
        item = _FakeItem()
        parent = _FakeParent()
        collection = ['a', 'b', 'c']

        moveManagedParameterItem(
            item,
            parent,
            collection,
            0,
            offset=1,
            childFactory=lambda value: {'name': value},
            afterMove=lambda oldIndex, newIndex, value: parent.mark('moved', oldIndex, newIndex, value),
        )

        self.assertEqual(parent.callbackCalls, [('moved', 0, 1, 'a')])

    def testSwapManagedParameterItemsSwapsValuesAndPreservesSlotNames(self):
        parent = _FakeParent()
        parent.childs = [_FakeItem('Planes'), _FakeItem('Lines'), _FakeItem('Points')]
        collection = ['plane-value', 'line-value', 'point-value']

        swapped = swapManagedParameterItems(
            parent,
            collection,
            1,
            offset=-1,
            childFactory=lambda name, value: {'name': name, 'value': value},
        )

        self.assertTrue(swapped)
        self.assertTrue(parent.childs[0].removed)
        self.assertTrue(parent.childs[1].removed)
        self.assertEqual(collection, ['line-value', 'plane-value', 'point-value'])
        self.assertEqual(
            parent.insertCalls,
            [
                (0, {'name': 'Planes', 'value': 'line-value'}),
                (1, {'name': 'Lines', 'value': 'plane-value'}),
            ],
        )

    def testSwapManagedParameterItemsSkipsOutOfRangeSwap(self):
        parent = _FakeParent()
        parent.childs = [_FakeItem('Planes'), _FakeItem('Lines')]
        collection = ['plane-value', 'line-value']

        swapped = swapManagedParameterItems(
            parent,
            collection,
            0,
            offset=-1,
            childFactory=lambda name, value: {'name': name, 'value': value},
        )

        self.assertFalse(swapped)
        self.assertFalse(parent.childs[0].removed)
        self.assertFalse(parent.childs[1].removed)
        self.assertEqual(collection, ['plane-value', 'line-value'])
        self.assertEqual(parent.insertCalls, [])

    def testNextManagedChildNameSkipsExistingNames(self):
        newName = nextManagedChildName({'Seed-1': None, 'Seed-2': None, 'Seed-4': None}, 'Seed')

        self.assertEqual(newName, 'Seed-3')

    def testAppendManagedParameterItemAppendsAddsAndEmits(self):
        parent = _FakeParent()
        collection = ['a']

        appended = appendManagedParameterItem(
            parent,
            collection,
            'b',
            name='Seed-2',
            childFactory=lambda name, value: {'name': name, 'value': value},
            menuName='addNew',
        )

        self.assertEqual(appended, 'b')
        self.assertEqual(collection, ['a', 'b'])
        self.assertEqual(parent.addCalls, [{'name': 'Seed-2', 'value': 'b'}])
        self.assertEqual(parent.sigAddNew.calls, [(parent, 'addNew')])
        self.assertEqual(parent.sigValueChanging.calls, [(parent, ['value'])])

    def testAppendManagedParameterItemRunsAfterAppendCallback(self):
        parent = _FakeParent()
        collection = []

        appendManagedParameterItem(
            parent,
            collection,
            'pattern',
            name='Pattern-1',
            childFactory=lambda name, value: {'name': name, 'value': value},
            menuName='addNew',
            afterAppend=lambda value: parent.mark('appended', value),
        )

        self.assertEqual(parent.callbackCalls, [('appended', 'pattern')])


if __name__ == '__main__':
    unittest.main()
