import os

from pyqtgraph import functions as fn
from pyqtgraph.parametertree import registerParameterType
from pyqtgraph.parametertree.parameterTypes import (GroupParameter,
                                                    GroupParameterItem)
from pyqtgraph.parametertree.parameterTypes.basetypes import ParameterItem
from pyqtgraph.Qt import mkQApp
from qgis.PyQt.QtGui import QColor, QIcon
from qgis.PyQt.QtWidgets import (QHBoxLayout, QMenu, QSizePolicy, QSpacerItem,
                                 QWidget)

from . import config  # used to pass initial settings
from .aux_functions import lineNo, myPrint
from .my_preview_label import MyPreviewLabel

current_dir = os.path.dirname(os.path.abspath(__file__))
resource_dir = os.path.join(current_dir, 'resources')

#  helper function to check if all parents have been expanded. In that case the preview label should be shown
def expandedParents(param):
    expanded = True
    parent = param.parent()
    while parent is not None:
        if parent.opts.get('expanded', False) is False or parent.opts.get('visible', False) is False:
            expanded = False
            break
        parent = parent.parent()
    return expanded


class MyGroupParameterItem(GroupParameterItem):
    def __init__(self, param, depth):
        super().__init__(param, depth)

        self.contextMenu = None
        self.previewLabel = None
        self.itemWidget = QWidget()

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)                                   # call the parent method first
        tw = self.treeWidget()
        if tw is None:
            return
        tw.setItemWidget(self, 1, self.itemWidget)

    def createAndInitPreviewLabel(self, param):
        # we can skip creating the preview label if config.showSummaries is False, or param is None

        if not config.showSummaries or param is None:                           # no need to do any real work (yet)
            return

        # at this point, we know param is valid, and a preview label is needed. Does it exist ?
        if self.previewLabel is None:                                           # label does not exist yet
            layout = QHBoxLayout()                                              # do the "initialization work" here
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)                                                # spacing between elements

            spacerItem = QSpacerItem(5, 5, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            layout.addSpacerItem(spacerItem)

            self.previewLabel = MyPreviewLabel()
            layout.addWidget(self.previewLabel)
            self.itemWidget.setLayout(layout)                                   # ready doing the "initialization work"

        self.showPreviewInformation(param)                                      # show the preview information (subclassed routine)

    def showPreviewInformation(self, param):
        raise NotImplementedError()

    def onValueChanging(self, param, _):                                        # val unused and replaced  by _
        if config.showSummaries:
            self.createAndInitPreviewLabel(param)                             # create the preview label if needed
            # self.showPreviewInformation(param)
        myPrint(f'>>>{lineNo():5d} MyGroupParameterItem.ValueChanging <<<')

    def onTreeStateChanged(self, param, _):                                     # unused changes replaced by _
        if config.showSummaries:
            self.createAndInitPreviewLabel(param)                             # create the preview label if needed
            # self.showPreviewInformation(param)
        myPrint(f'>>>{lineNo():5d} MyGroupParameterItem.TreeStateChanged <<<')

    def updateDepth(self, depth):
        """Change set the item font to bold and increase the font size on outermost groups if desired."""

        app = mkQApp()
        palette = app.palette()
        background = palette.base().color()

        h, s, l, a = background.getHslF()
        lightness = 0.5 + (l - 0.5) * 0.8
        altBackground = QColor.fromHslF(h, s, lightness, a)

        flat = self.param.opts.get('flat', False)
        brush = self.param.opts.get('brush', None)

        for c in [0, 1]:
            font = self.font(c)
            if not flat:
                font.setBold(True)
            if depth == 0:
                if brush is not None:
                    self.setBackground(c, fn.mkColor(brush))
                elif not flat:
                    self.setBackground(c, background)
                    font.setPointSize(self.pointSize() + 1)
            else:
                if brush is not None:
                    self.setBackground(c, fn.mkColor(brush))
                elif not flat:
                    self.setBackground(c, altBackground)

            self.setForeground(c, palette.text().color())
            self.setFont(c, font)
        self.titleChanged()  # sets the size hint for column 0 which is based on the new font

    def contextMenuEvent(self, ev):
        """method overloaded to allow for icons in the context menu"""
        opts = self.param.opts

        if not 'context' in opts:
            return

        ## Generate context menu for renaming / removing parameter
        self.contextMenu = QMenu()   # Put in global name space to prevent garbage collection
        self.contextMenu.addSeparator()

        # context menu
        context = opts.get('context', None)
        if isinstance(context, list):
            for name in context:
                self.contextMenu.addAction(name).triggered.connect(self.contextMenuTriggered(name))
        elif isinstance(context, dict):
            for name, title in context.items():
                if name == 'separator':
                    self.contextMenu.addSeparator()
                    continue

                iconFile = name + 'Icon.svg'
                iconFile = os.path.join(resource_dir, iconFile)
                if os.path.exists(iconFile):
                    if name == 'rename':
                        self.contextMenu.addAction(QIcon(iconFile), title).triggered.connect(self.editName)
                        continue

                    self.contextMenu.addAction(QIcon(iconFile), title).triggered.connect(self.contextMenuTriggered(name))
                else:
                    if name == 'rename':
                        self.contextMenu.addAction(title).triggered.connect(self.editName)
                        continue

                    self.contextMenu.addAction(title).triggered.connect(self.contextMenuTriggered(name))

        self.contextMenu.popup(ev.globalPos())


class MyGroupParameter(GroupParameter):
    """
    ============== ========================================================
    **Options**
    flat           Defaults to False. Set True to avoid bold font usage
    brush:         Defaults to None.  Set color to change background color
    ============== ========================================================
    """

    itemClass = MyGroupParameterItem


registerParameterType('myGroup', MyGroupParameter, override=True)
