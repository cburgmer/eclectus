#!/usr/bin/env python
# coding=UTF-8
#
# Generated by pykdeuic4 from ui/VocabularyPage.ui on Tue Sep 29 11:00:56 2009
#
# WARNING! All changes to this file will be lost.
from PyKDE4 import kdecore
from PyKDE4 import kdeui
from PyQt4 import QtCore, QtGui
class MyQListView(QtGui.QListView):
    # TODO can not catch those keys with a shortcut, why?
    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Delete:
            self.emit(QtCore.SIGNAL("deletePressed()"))
        elif event.key() == QtCore.Qt.Key_Return \
            or event.key() == QtCore.Qt.Key_Enter:
            self.emit(QtCore.SIGNAL("returnPressed()"))
        else:
            QtGui.QListView.keyPressEvent(self, event)


class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(233, 392)
        self.verticalLayout = QtGui.QVBoxLayout(Form)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.exportHistoryButton = QtGui.QToolButton(Form)
        self.exportHistoryButton.setPopupMode(QtGui.QToolButton.InstantPopup)
        self.exportHistoryButton.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.exportHistoryButton.setAutoRaise(True)
        self.exportHistoryButton.setArrowType(QtCore.Qt.NoArrow)
        self.exportHistoryButton.setObjectName("exportHistoryButton")
        self.horizontalLayout.addWidget(self.exportHistoryButton)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.vocabularyListView = MyQListView(Form)
        self.vocabularyListView.setAlternatingRowColors(True)
        self.vocabularyListView.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
        self.vocabularyListView.setWordWrap(True)
        self.vocabularyListView.setObjectName("vocabularyListView")
        self.verticalLayout.addWidget(self.vocabularyListView)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        Form.setWindowTitle(kdecore.i18n("Form"))
        self.exportHistoryButton.setText(kdecore.i18n("&Export ..."))

