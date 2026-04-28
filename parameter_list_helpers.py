def removeManagedParameterItem(item, parent, collection, index, *, confirmRemoval, afterRemove=None):
    if not confirmRemoval():
        return False

    item.remove()
    collection.pop(index)
    parent.sigChildRemoved.emit(item, parent)
    if afterRemove is not None:
        afterRemove(index)
    return True


def moveManagedParameterItem(item, parent, collection, index, *, offset, childFactory, afterMove=None):
    newIndex = index + offset
    if newIndex < 0 or newIndex >= len(collection):
        return False

    item.remove()
    value = collection.pop(index)
    collection.insert(newIndex, value)
    parent.insertChild(newIndex, childFactory(value))
    if afterMove is not None:
        afterMove(index, newIndex, value)
    return True


def swapManagedParameterItems(parent, collection, index, *, offset, childFactory, afterSwap=None):
    newIndex = index + offset
    if newIndex < 0 or newIndex >= len(collection):
        return False

    lowerIndex = min(index, newIndex)
    upperIndex = max(index, newIndex)
    lowerChild = parent.childs[lowerIndex]
    upperChild = parent.childs[upperIndex]
    lowerName = lowerChild.name()
    upperName = upperChild.name()

    upperChild.remove()
    lowerChild.remove()

    collection[index], collection[newIndex] = collection[newIndex], collection[index]

    parent.insertChild(lowerIndex, childFactory(lowerName, collection[lowerIndex]))
    parent.insertChild(upperIndex, childFactory(upperName, collection[upperIndex]))
    if afterSwap is not None:
        afterSwap(index, newIndex, collection[index], collection[newIndex])
    return True


def nextManagedChildName(existingNames, prefix):
    n = len(existingNames) + 1
    newName = f'{prefix}-{n}'
    while newName in existingNames:
        n += 1
        newName = f'{prefix}-{n}'
    return newName


def appendManagedParameterItem(parent, collection, value, *, name, childFactory, menuName, afterAppend=None):
    collection.append(value)
    parent.addChild(childFactory(name, value))
    parent.sigAddNew.emit(parent, menuName)
    parent.sigValueChanging.emit(parent, parent.value())
    if afterAppend is not None:
        afterAppend(value)
    return value
