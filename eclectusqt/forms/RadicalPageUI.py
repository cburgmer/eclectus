#!/usr/bin/env python
# coding=UTF-8
#
# Generated by pykdeuic4 from ui/RadicalPage.ui on Fri May 22 22:42:17 2009
#
# WARNING! All changes to this file will be lost.
from PyKDE4 import kdecore
from PyKDE4 import kdeui
from PyQt4 import QtCore, QtGui

class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(273, 331)
        self.verticalLayout = QtGui.QVBoxLayout(Form)
        self.verticalLayout.setObjectName("verticalLayout")
        self.radicalOptions = QtGui.QStackedWidget(Form)
        self.radicalOptions.setObjectName("radicalOptions")
        self.page = QtGui.QWidget()
        self.page.setObjectName("page")
        self.horizontalLayout_2 = QtGui.QHBoxLayout(self.page)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.gotoLabel = QtGui.QLabel(self.page)
        self.gotoLabel.setObjectName("gotoLabel")
        self.horizontalLayout_2.addWidget(self.gotoLabel)
        self.gotoEdit = KLineEdit(self.page)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.gotoEdit.sizePolicy().hasHeightForWidth())
        self.gotoEdit.setSizePolicy(sizePolicy)
        self.gotoEdit.setUrlDropsEnabled(False)
        self.gotoEdit.setProperty("showClearButton", QtCore.QVariant(True))
        self.gotoEdit.setObjectName("gotoEdit")
        self.horizontalLayout_2.addWidget(self.gotoEdit)
        self.gotoNextButton = QtGui.QToolButton(self.page)
        self.gotoNextButton.setObjectName("gotoNextButton")
        self.horizontalLayout_2.addWidget(self.gotoNextButton)
        self.gotoButton = QtGui.QToolButton(self.page)
        self.gotoButton.setObjectName("gotoButton")
        self.horizontalLayout_2.addWidget(self.gotoButton)
        self.radicalOptions.addWidget(self.page)
        self.page_2 = QtGui.QWidget()
        self.page_2.setObjectName("page_2")
        self.horizontalLayout = QtGui.QHBoxLayout(self.page_2)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.toRadicalTableButton = QtGui.QToolButton(self.page_2)
        self.toRadicalTableButton.setArrowType(QtCore.Qt.NoArrow)
        self.toRadicalTableButton.setObjectName("toRadicalTableButton")
        self.horizontalLayout.addWidget(self.toRadicalTableButton)
        spacerItem = QtGui.QSpacerItem(76, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.nonKangxiRadicalButton = QtGui.QToolButton(self.page_2)
        self.nonKangxiRadicalButton.setCheckable(True)
        self.nonKangxiRadicalButton.setAutoRaise(True)
        self.nonKangxiRadicalButton.setArrowType(QtCore.Qt.NoArrow)
        self.nonKangxiRadicalButton.setObjectName("nonKangxiRadicalButton")
        self.horizontalLayout.addWidget(self.nonKangxiRadicalButton)
        self.groupRadicalFormsButton = QtGui.QToolButton(self.page_2)
        self.groupRadicalFormsButton.setEnabled(False)
        self.groupRadicalFormsButton.setCheckable(True)
        self.groupRadicalFormsButton.setAutoRaise(True)
        self.groupRadicalFormsButton.setArrowType(QtCore.Qt.NoArrow)
        self.groupRadicalFormsButton.setObjectName("groupRadicalFormsButton")
        self.horizontalLayout.addWidget(self.groupRadicalFormsButton)
        self.radicalOptions.addWidget(self.page_2)
        self.verticalLayout.addWidget(self.radicalOptions)
        self.radicalView = QtWebKit.QWebView(Form)
        self.radicalView.setBaseSize(QtCore.QSize(0, 0))
        self.radicalView.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        self.radicalView.setUrl(QtCore.QUrl("about:blank"))
        self.radicalView.setObjectName("radicalView")
        self.verticalLayout.addWidget(self.radicalView)
        self.gotoLabel.setBuddy(self.gotoEdit)

        self.retranslateUi(Form)
        self.radicalOptions.setCurrentIndex(0)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        Form.setWindowTitle(kdecore.i18n("Form"))
        self.gotoLabel.setText(kdecore.i18n("Go &to:"))
        self.gotoEdit.setToolTip(kdecore.i18n("Enter the radical\'s name, the radical\'s form, its stroke count or its index (e.g. #10) to jump to the radical\'s entry."))
        self.gotoEdit.setWhatsThis(kdecore.i18n("Enter the radical\'s name, the radical\'s form, its stroke count or its index (e.g. #10) to jump to the radical\'s entry."))
        self.gotoNextButton.setToolTip(kdecore.i18n("Go to next match"))
        self.gotoNextButton.setWhatsThis(kdecore.i18n("Go to the next match in the table."))
        self.gotoButton.setToolTip(kdecore.i18n("Go to radical page"))
        self.gotoButton.setWhatsThis(kdecore.i18n("Go to radical page"))
        self.toRadicalTableButton.setToolTip(kdecore.i18n("Go back to radical table"))
        self.toRadicalTableButton.setStatusTip(kdecore.i18n("Go back to radical table"))
        self.nonKangxiRadicalButton.setToolTip(kdecore.i18n("Show all characters"))
        self.nonKangxiRadicalButton.setWhatsThis(kdecore.i18n("Show all characters including this radical form."))
        self.groupRadicalFormsButton.setToolTip(kdecore.i18n("Group characters by radical place"))
        self.groupRadicalFormsButton.setStatusTip(kdecore.i18n("Group characters by radical placement in glyph."))

from PyQt4 import QtWebKit
from PyKDE4.kdeui import KLineEdit
