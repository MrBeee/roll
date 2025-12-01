from PyQt5.QtWidgets import QApplication

from .my_group import MyGroupParameter, MyGroupParameterItem

### class MySpsFormatListParameter #######################################################


class MySpsFormatListParameter(MyGroupParameter):

    itemClass = MyGroupParameterItem

    def __init__(self, **opts):

        opts['context'] = {'addNew': 'Add new SPS format'}
        opts['tip'] = 'Right click to add a new SPS format'

        MyGroupParameter.__init__(self, **opts)
        if 'children' in opts:
            raise KeyError('Cannot set "children" argument in MySpsFormatListParameter opts')

        self.spsFormatList = []
        self.spsFormatList = opts.get('value', self.spsFormatList)

        if not isinstance(self.spsFormatList, list):
            raise ValueError("Need 'list' instance at this point")

        with self.treeChangeBlocker():
            for spsFormat in self.spsFormatList:
                self.addChild(dict(name=spsFormat.name, type='mySpsFormat', value=spsFormat, default=spsFormat, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))

        self.sigContextMenu.connect(self.contextMenu)
        self.sigChildAdded.connect(self.onChildAdded)
        self.sigChildRemoved.connect(self.onChildRemoved)

        QApplication.processEvents()

    def value(self):
        return self.spsFormatList

    def contextMenu(self, name=None):

        if name == 'addNew':
            n = len(self.names) + 1
            newName = f'Pattern-{n}'
            while newName in self.names:
                n += 1
                newName = f'Pattern-{n}'

            spsFormat = RollSpsFormat(newName)

            self.spsFormatList.append(spsFormat)
            self.addChild(dict(name=newName, type='mySpsFormat', value=spsFormat, default=spsFormat, expanded=False, renamable=True, flat=True, decimals=5, suffix='m'))
            self.sigAddNew.emit(self, name)

            self.sigValueChanging.emit(self, self.value())

        QApplication.processEvents()

    def onChildAdded(self, *_):                                                 # child, index unused and replaced by *_
        # myPrint(f'>>>{lineNo():5d} spsFormatList.ChildAdded <<<')
        ...

    def onChildRemoved(self, _):                                                # child unused and replaced by _
        # myPrint(f'>>>{lineNo():5d} spsFormatList.ChildRemoved <<<')
        ...

