#!/usr/bin/python
# -*- coding: utf-8 -*-
u"""
Eclectus is a small Han character dictionary.

Copyright (C) 2009 Christoph Burgmer
(cburgmer@ira.uka.de)

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

import sys
import re
import os
import signal
import locale

from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import Qt, SIGNAL, QVariant, QSize, QByteArray
from PyQt4.QtGui import QSizePolicy, QAction, QListWidgetItem, QClipboard
from PyQt4.QtGui import QMainWindow, QApplication, QIcon, QFont, QImage
from PyQt4.QtGui import QCursor, QLabel

from PyKDE4 import kdeui
from PyKDE4.kdecore import ki18n, i18n, KCmdLineArgs, KCmdLineOptions, KGlobal
from PyKDE4.kdecore import KAboutData, KLocalizedString, KConfig, KConfigGroup
from PyKDE4.kdecore import KStandardDirs
from PyKDE4.kdeui import KConfigDialog, KConfigSkeleton, KMessageBox
from PyKDE4.kdeui import KApplication, KXmlGuiWindow, KShortcut, KIcon
from PyKDE4.kdeui import KAction, KStandardAction, KToggleAction, KSelectAction
from PyKDE4.kdeui import KStandardShortcut, KStandardGuiItem, KHistoryComboBox

try:
    import cjklib
    try:
        # check version
        from distutils import version
        cjklibVersion = version.LooseVersion(cjklib.__version__)
        if (cjklibVersion != '0.3'
            and cjklibVersion <= version.LooseVersion('0.2')):
            import logging
            logging.warn('Your cjklib version is too old.')
    except ImportError:
        pass
except ImportError:
    print >>sys.stderr, \
        "Please install cjklib from http://code.google.com/p/cjklib"
    sys.exit(1)


from eclectusqt import update
from eclectusqt import dictionarypage
from eclectusqt import radicalpage
from eclectusqt import componentpage
from eclectusqt import handwritingpage
from eclectusqt import vocabularypage
from eclectusqt import renderthread
from eclectusqt import util
import eclectusqt

from libeclectus.locale import setTranslationLanguage
from libeclectus.util import getCJKScriptClass

doDebug = 1

class MainWindow(KXmlGuiWindow):
    CHOOSER_PLUGINS = [
        # TODO reenable
        (radicalpage.RadicalPage, ki18n('&Radicals')),
        (componentpage.ComponentPage, ki18n('&Components')),
        (handwritingpage.HandwritingPage, ki18n('Hand&writing')),
        (vocabularypage.VocabularyPage, ki18n('&Vocabulary')),
        ]
    """Plugins loaded into the side panel."""

    def __init__(self):
        QMainWindow.__init__(self)

        self.miniMode = False
        self.initialised = False

        # set i18n language for libeclectus
        setTranslationLanguage(unicode(KGlobal.locale().language()))

        # start rendering thread
        self.renderThread = renderthread.SQLRenderThread(g_app)
        self.connect(g_app, SIGNAL("aboutToQuit()"),
            self.renderThread.quit)
        self.renderThread.start()

        self.connect(self.renderThread, SIGNAL("queueEmpty"), self.queueEmpty)
        self.connect(self.renderThread, SIGNAL("jobEnqueued"), self.jobEnqueued)
        self.connect(self.renderThread, SIGNAL("jobErrorneous"),
            lambda jobId, classObject, method, args, param, e, stacktrace: \
                showDebug(stacktrace.decode('utf8')))

        self.updateDialog = update.UpdateDialog(self, self.renderThread)
        #self.updateDialog = None # set to None to disable updating
        if self.updateDialog:
            self.connect(self.updateDialog, SIGNAL("databaseChanged()"),
                lambda: self.emit(SIGNAL("databaseChanged()")))

        # set up UI
        self.setupUi()
        self.setupActions()

        # finally build gui
        xmlFile = os.path.join(os.getcwd(), 'eclectusqt', 'eclectusui.rc')
        if os.path.exists(xmlFile):
            self.setupGUI(KXmlGuiWindow.StandardWindowOption(
                KXmlGuiWindow.Default ^ KXmlGuiWindow.StatusBar), xmlFile)
        else:
            self.setupGUI(KXmlGuiWindow.StandardWindowOption(
                KXmlGuiWindow.Default ^ KXmlGuiWindow.StatusBar))

        self.restoreWindowState()

        self.setCentralWidget(self.splitterFrame)
        self.splitterFrame.setVisible(True)

        self.initialised = True

        if (GeneralConfig.readEntry("Show installer on startup", 'True')
            == 'True') and self.updateAction:
            self.updateAction.trigger()

    def setupUi(self):
        self.setWindowIcon(QIcon(util.getIcon('eclectus.png')))

        self.splitterFrame = QtGui.QSplitter(self)
        self.splitterFrame.setOrientation(QtCore.Qt.Horizontal)
        self.characterChooser = QtGui.QToolBox(self.splitterFrame)
        self.characterChooser.setFrameShape(QtGui.QFrame.StyledPanel)

        self.dictionaryPage = dictionarypage.DictionaryPage(self,
            self.renderThread, PluginConfig)
        self.connect(self.dictionaryPage,
            SIGNAL('pageChanged(const QString &)'), self.slotPageChanged)
        # forward settingsChanged
        self.connect(self.dictionaryPage, SIGNAL("settingsChanged()"),
            lambda: self.emit(SIGNAL("settingsChanged()")))
        # TODO make this modular
        self.connect(self.dictionaryPage,
            SIGNAL("vocabularyAdded(const QString &, const QString &, const QString &, const QString &)"),
            self.slotVocabularyAdded)
        self.connect(self.dictionaryPage, SIGNAL("modeChanged(bool)"),
            self.slotMiniMode)

        self.splitterFrame.addWidget(self.characterChooser)
        self.splitterFrame.addWidget(self.dictionaryPage)

        # load sidebar plugins
        self.plugins = []
        self.vocabularyPlugin = None
        for classObj, heading in self.CHOOSER_PLUGINS:
            page = classObj(self, self.renderThread, PluginConfig)
            if not self.vocabularyPlugin \
                and isinstance(page, vocabularypage.VocabularyPage):
                self.vocabularyPlugin = len(self.plugins)

            self.characterChooser.addItem(page, heading.toString())
            self.connect(page, SIGNAL('inputReceived(const QString &)'),
                self.dictionaryPage.load)

            self.plugins.append(page)

        self.splitterFrame.setVisible(False)
        self.setCentralWidget(QLabel(i18n('Installing basic tables...')))

    def setupActions(self):
        """Sets up all actions (signal/slot combinations)."""
        # standard action
        KStandardAction.quit(g_app.quit, self.actionCollection())

        # dictionary actions
        self.dictionaryPage.registerGlobalActions(self.actionCollection())
        # update dictionaries
        if self.updateDialog:
            self.updateAction = self.updateDialog.updateAction(
                self.actionCollection())
            # optimise database
            self.updateDialog.optimiseAction(self.actionCollection())
        else:
            self.updateAction = None

        # search bar
        self.characterCombo = KHistoryComboBox()
        self.characterCombo.setSizePolicy(QSizePolicy.Expanding,
            QSizePolicy.Fixed)
        font = QFont()
        font.setPointSize(13)
        self.characterCombo.setFont(font)
        self.characterCombo.setObjectName("characterCombo")
        self.connect(self.characterCombo, SIGNAL("activated(const QString &)"),
            self.slotCharacterComboActivated)

        comboAction = KAction(self)
        comboAction.setText(i18n("Search bar"))
        comboAction.setShortcut(Qt.Key_F6)
        self.connect(comboAction, SIGNAL("triggered()"),
            self.slotSearchComboActivated)
        comboAction.setDefaultWidget(self.characterCombo)
        comboAction.setWhatsThis(
            i18n("<html>Search bar<br/><br/>Enter character of search string</html>"))
        self.actionCollection().addAction("searchbar", comboAction)

        goUrl = self.actionCollection().addAction("go_search")
        goUrl.setIcon(KIcon("go-jump-locationbar"))
        goUrl.setText(i18n("Go"))
        self.connect(goUrl, SIGNAL("triggered()"),
            lambda: self.slotCharacterComboActivated(
                self.characterCombo.currentText()))
        goUrl.setWhatsThis(
            i18n("<html>Go<br /><br />Searches for the string given in the search bar.</html>"))

        # clear search bar action
        clearLocationAction = KAction(KIcon("edit-clear-locationbar-ltr"),
            i18n("Clear &Location Bar"), self)
        clearLocationAction.setShortcut(Qt.CTRL + Qt.Key_L)
        clearLocationAction.setWhatsThis(
            i18n("Clears the location bar and places the cursor inside"))
        self.actionCollection().addAction("clearlocationbar",
            clearLocationAction)
        self.connect(clearLocationAction, SIGNAL("triggered(bool)"),
            self.characterCombo.clearEditText)
        self.connect(clearLocationAction, SIGNAL("triggered(bool)"),
            self.characterCombo.setFocus)

        # show/hide character page
        self.toggleToolboxAction = KToggleAction(KIcon("view-sidetree"),
            i18n("Show Character Toolbox"), self)
        self.toggleToolboxAction.setShortcut(Qt.Key_F9)
        self.toggleToolboxAction.setWhatsThis(
            i18n("Shows and Hides the character choosing toolbox"))
        self.actionCollection().addAction("showtoolbox",
            self.toggleToolboxAction)
        self.connect(self.toggleToolboxAction, SIGNAL("triggered(bool)"),
            self.slotToggleToolbox)

        # auto-lookup clipboard
        self.autoLookupAction = KToggleAction(i18n("&Auto-Lookup"), self)
        self.autoLookupAction.setToolTip(
            i18n("Automatically look up text selected by the mouse cursor."))
        self.autoLookupAction.setWhatsThis(
            i18n("Automatically look up text selected by the mouse cursor."))
        self.actionCollection().addAction("autolookup", self.autoLookupAction)
        self.connect(self.autoLookupAction, SIGNAL("triggered(bool)"),
            self.setAutoLookup)
        self.autoLookupAction.setIcon(
            QIcon(util.getIcon('auto-lookup-selection.png')))

        self.connect(QApplication.clipboard(), SIGNAL("selectionChanged()"),
            self.slotSelectionChanged)

    def restoreWindowState(self):
        # GUI settings
        history = util.readConfigString(GeneralConfig, "Url History", '')\
            .split(',')
        self.characterCombo.insertItems(history)
        self.historyLength = util.readConfigInt(GeneralConfig, "History Length",
            20)
        self.autoLookup = util.readConfigString(GeneralConfig,
            "Auto-Lookup clipboard", str(False)) != "False"
        self.autoLookupAction.setChecked(self.autoLookup)
        self.onlyAutoLookupCJKCharacters = util.readConfigString(GeneralConfig,
            "Auto-Lookup only Chinese characters", str(False)) != "False"

        self.splitterFrame.restoreState(QByteArray.fromBase64(
            str(util.readConfigString(GeneralConfig, "Splitter", ""))))
        self.splitterSizes = [int(i) for i \
            in util.readConfigString(GeneralConfig, "Splitter sizes",
                "220,426").split(',')]

        self.toolbarOriginalState = QByteArray.fromBase64(
            str(util.readConfigString(GeneralConfig, "Toolbar original state",
                "")))
        self.restoreState(self.toolbarOriginalState)
        self.menuBar().setVisible(True)

        self.characterChooser.setCurrentIndex(util.readConfigInt(GeneralConfig,
            "Toolbox current", 0))

        visible = GeneralConfig.readEntry("Toolbox visibile", str(True))
        if visible == "False":
            self.characterChooserOriginalVisibility = False
        else:
            self.splitterFrame.setSizes(self.splitterSizes)
            self.characterChooserOriginalVisibility = True
        self.characterChooser.setVisible(
            self.characterChooserOriginalVisibility)
        self.toggleToolboxAction.setChecked(
            self.characterChooserOriginalVisibility)

        w = util.readConfigInt(GeneralConfig, "Width", 640)
        h = util.readConfigInt(GeneralConfig, "Height", 420)
        self.defaultWindowSize = QSize(w, h)
        x = util.readConfigInt(GeneralConfig, "LastX", 0)
        y = util.readConfigInt(GeneralConfig, "LastY", 0)

        mini_w = util.readConfigInt(GeneralConfig, "Mini-mode Width", 400)
        mini_h = util.readConfigInt(GeneralConfig, "Mini-mode Height", 200)
        self.miniModeWindowSize = QSize(mini_w, mini_h)

        self.setGeometry(x, y, w, h)

    def queryExit(self):
        """
        save config data before exiting
        """
        self.emit(SIGNAL("writeSettings()"))

        if self.miniMode:
            self.miniModeWindowSize = self.size()
        else:
            self.defaultWindowSize = self.size()

        GeneralConfig.writeEntry("Width", str(self.defaultWindowSize.width()))
        GeneralConfig.writeEntry("Height", str(self.defaultWindowSize.height()))
        GeneralConfig.writeEntry("LastX", str(self.x()))
        GeneralConfig.writeEntry("LastY", str(self.y()))
        GeneralConfig.writeEntry("Mini-mode Width",
            str(self.miniModeWindowSize.width()))
        GeneralConfig.writeEntry("Mini-mode Height",
            str(self.miniModeWindowSize.height()))

        GeneralConfig.writeEntry("Show installer on startup", 'False')
        GeneralConfig.writeEntry("Url History",
            self.characterCombo.historyItems()[:self.historyLength])
        GeneralConfig.writeEntry("Splitter",
            QByteArray.toBase64(self.splitterFrame.saveState()))

        GeneralConfig.writeEntry("Auto-Lookup clipboard", str(self.autoLookup))
        GeneralConfig.writeEntry("Auto-Lookup only Chinese characters",
            str(self.onlyAutoLookupCJKCharacters))

        # toolbox
        if self.characterChooser.isVisible():
            self.splitterSizes = self.splitterFrame.sizes()
        GeneralConfig.writeEntry("Splitter sizes", ",".join(
            [str(i) for i in self.splitterSizes]))

        if not self.miniMode:
            self.toolbarOriginalState = self.saveState(0)
        GeneralConfig.writeEntry("Toolbar original state",
            QByteArray.toBase64(self.toolbarOriginalState))

        GeneralConfig.writeEntry("Toolbox current",
            str(self.characterChooser.currentIndex()))
        GeneralConfig.writeEntry("Toolbox visibile",
            str(self.characterChooserOriginalVisibility))

        return True

    def settings(self):
        return self.dictionaryPage.settings()

    def slotToggleToolbox(self, show):
        if not self.miniMode:
            self.showToolbox(show)

            self.characterChooserOriginalVisibility = show

    def showToolbox(self, show):
        # save / restore size as hiding makes Qt forget
        if self.characterChooser.isVisible():
            self.splitterSizes = self.splitterFrame.sizes()
        else:
            self.splitterFrame.setSizes(self.splitterSizes)

        self.characterChooser.setVisible(show)

    def slotMiniMode(self, miniMode):
        self.miniMode = miniMode

        if not self.miniMode:
            # restore original state if given
            if self.toolbarOriginalState:
                self.restoreState(self.toolbarOriginalState, 0)
            self.menuBar().setVisible(True)

            self.showToolbox(self.characterChooserOriginalVisibility)

            self.miniModeWindowSize = self.size()
            self.resize(self.defaultWindowSize)
        else:
            # save original state of toolbars
            self.toolbarOriginalState = self.saveState(0)
            for toolbar in self.toolBars():
                toolbar.setVisible(False)
            self.menuBar().setVisible(False)

            self.characterChooserOriginalVisibility \
                = self.characterChooser.isVisible()
            self.showToolbox(False)

            self.defaultWindowSize = self.size()
            self.resize(self.miniModeWindowSize)

            # tell user what to do
            # TODO renable
            #miniModeShortcut = unicode(i18n(
                #self.miniModeAction.shortcut().toString()))
            #text = unicode(i18n("Mini-mode hides your menubar and toolbars. Press %1 again to get back to normal mode.", miniModeShortcut))
            #lookupShortcut = self.lookupClipboardAction.globalShortcut()\
                #.toString(QtGui.QKeySequence.NativeText)
            #if lookupShortcut:
                #text = text + "\n\n" \
                    #+ unicode(i18n("You may look up entries by selecting a word and pressing %1. Alternatively you can turn on auto-lookup or paste from the clipboard by pressing the middle mouse button.",
                    #i18n(lookupShortcut)))

            #KMessageBox.information(self, text, i18n("Mini-mode"),
                #"show_mini-mode_notice")

    def slotCharacterComboActivated(self, inputString):
        self.characterCombo.addToHistory(inputString)
        self.dictionaryPage.load(inputString)
        self.dictionaryPage.setFocus()

    def slotSearchComboActivated(self):
        self.characterCombo.setFocus()
        self.characterCombo.lineEdit().selectAll()

    def setAutoLookup(self, selected):
        self.autoLookup = selected

    def slotSelectionChanged(self):
        if self.autoLookup:
            # don't auto lookup when user is editing one of our edit widgets
            focusWidget = QApplication.focusWidget()
            if focusWidget:
                for editWidgetCls in [kdeui.KHistoryComboBox, kdeui.KLineEdit]:
                    if isinstance(focusWidget, editWidgetCls):
                        return

            clipboardText = unicode(QApplication.clipboard().text(
                QClipboard.Selection).simplified()).strip()
            if not clipboardText or len(clipboardText) >= 20:
                return
            if (self.onlyAutoLookupCJKCharacters and
                not MainWindow.hasCJKCharacter(clipboardText)):
                    return

            self.dictionaryPage.load(clipboardText)
            # make window flash in taskbar
            self.activateWindow()

    @staticmethod
    def hasCJKCharacter(string):
        """
        Simple function for telling if a Chinese character or other CJK script
        is present.
        """
        for char in string:
            if getCJKScriptClass(char) != None:
                return True
        return False

    def slotPageChanged(self, pageName):
        # dictionary page changed
        self.emit(SIGNAL("pageRequested(const QString &)"), pageName)

        # Temporarily hide default internal pageTypes
        if unicode(pageName).count(':'):
            pageType, page = unicode(pageName).split(':')
        if pageType in ['character', 'word']:
            pageName = page
        self.characterCombo.setEditText(pageName) # TODO mask page type

    def slotVocabularyAdded(self, headword, reading, translation, audio):
        self.emit(SIGNAL("vocabularyAdded(const QString &, const QString &, const QString &, const QString &)"),
            headword, reading, translation, audio)
        if self.vocabularyPlugin != None:
            self.characterChooser.setCurrentIndex(self.vocabularyPlugin)

    def queueEmpty(self):
        QApplication.restoreOverrideCursor()

    def jobEnqueued(self, jobId):
        if not QApplication.overrideCursor():
            QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))


def showDebug(message):
    _, system_encoding = locale.getdefaultlocale()
    if doDebug:
        print >>sys.stderr, message.encode(system_encoding, 'ignore')

def linehere():
    import inspect
    return 'line %s in %r'%tuple(inspect.getframeinfo(inspect.currentframe().f_back)[1:3])

def run():
    appName     = "eclectus"
    catalog     = "eclectusqt"
    programName = ki18n("Eclectus")
    version     = eclectusqt.__version__
    description = ki18n("Han character dictionary")
    license     = KAboutData.License_GPL_V3
    copyright   = ki18n("(c) 2008-2009 Christoph Burgmer")
    text        = ki18n(
        "Eclectus is a small Han character dictionary for learners.")
    homePage    = eclectusqt.__url__
    bugEmail    = "cburgmer@ira.uka.de"

    bugAddress = "http://code.google.com/p/eclectus/issues/list"
    aboutData = KAboutData(appName, catalog, programName, version, description,
        license, copyright, text, homePage, bugEmail)
    aboutData.addAuthor(ki18n("Christoph Burgmer"), ki18n("Developer"),
        "cburgmer@ira.uka.de", "http://cburgmer.nfshost.com/")
    aboutData.setCustomAuthorText(ki18n("Please use %1 to report bugs.")\
            .subs(bugAddress),
        ki18n('Please use %1 to report bugs.')\
            .subs('<a href="%s">%s</a>' % (bugAddress, bugAddress)))
    aboutData.addCredit(KLocalizedString(), ki18n("Arrr, Eclectus sits on the shoulders of some fine pirates:"))
    aboutData.addCredit(ki18n("Jim Breen and contributors"), ki18n("EDICT"), '',
        'http://www.csse.monash.edu.au/~jwb/j_edict.html')
    aboutData.addCredit(ki18n("Paul Denisowski and current contributors"),
        ki18n("CEDICT"), '', 'http://www.mdbg.net/chindict/chindict.php')
    aboutData.addCredit(ki18n("HanDeDict team"), ki18n("HanDeDict"), '',
        'http://www.chinaboard.de/chinesisch_deutsch.php')
    aboutData.addCredit(ki18n("Tomoe developers"),
        ki18n("Tomoe handwriting recognition"),
        'tomoe-devel@lists.sourceforge.net', 'http://tomoe.sourceforge.jp')
    aboutData.addCredit(ki18n("Mathieu Blondel and the Tegaki contributors"),
        ki18n("Tegaki handwriting recognition"),
        u'mathieu ÂT mblondel DÔT org'.encode('utf8'),
        'http://tegaki.sourceforge.net')
    aboutData.addCredit(ki18n("Unicode Consortium and contributors"),
        ki18n("Unihan database"), '', 'http://unicode.org/charts/unihan.html')
    aboutData.addCredit(ki18n("Commons Stroke Order Project"),
        ki18n("Stroke order pictures"), '',
        'http://commons.wikimedia.org/wiki/Commons:Stroke_Order_Project')
    aboutData.addCredit(ki18n("Tim Eyre, Ulrich Apel and the Wadoku Project"),
        ki18n("Kanji stroke order font"), '',
        'http://sites.google.com/site/nihilistorguk/')
    aboutData.addCredit(
        ki18n("Yue Tan, Wei Gao, Vion Nicolas and the Shtooka Project"),
        ki18n("Pronunciation examples for Mandarin"), '',
        'http://shtooka.net')

    # find logo file, don't directly use util.getData(), KApplication not
    #   created yet
    aboutLogoFile = u'/usr/share/kde4/apps/eclectus/eclectus_about.png'
    if not os.path.exists(aboutLogoFile):
        modulePath = os.path.dirname(os.path.abspath(__file__))
        aboutLogoFile = os.path.join(modulePath, 'data', 'eclectus_about.png')
        if not os.path.exists(aboutLogoFile):
            aboutLogoFile = util.getData('eclectus_about.png')
    if aboutLogoFile:
        aboutData.setProgramLogo(QVariant(QImage(aboutLogoFile)))

    KCmdLineArgs.init(sys.argv, aboutData)

    # create applicaton
    global g_app
    g_app = KApplication()

    # TODO how to access local .mo file?
    #base = os.path.dirname(os.path.abspath(__file__))
    #localeDir = os.path.join(base, "locale")
    #print localeDir
    #if os.path.exists(localeDir):
        #print KGlobal.dirs().addResourceDir('locale', localeDir + '/', True)
    #print KGlobal.dirs().findResource('locale', 'de/LC_MESSAGES/eclectusqt.mo')

    # read config file and make global
    global GeneralConfig
    global DictionaryConfig
    global PluginConfig
    config = KConfig()
    GeneralConfig = KConfigGroup(config, "General")
    DictionaryConfig = KConfigGroup(config, "Dictionary")
    PluginConfig = KConfigGroup(config, "Plugin")

    # create main window
    MainWindow().show()

    # react to CTRL+C on the command line
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    g_app.exec_()
