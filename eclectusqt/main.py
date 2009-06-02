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

__author__ = "Christoph Burgmer <cburgmer@ira.uka.de>"
__license__ = 'GNU General Public License v3'
__url__ = "http://code.google.com/p/eclectus"
__version__ = "0.1alpha"

import sys
import re
import os
import signal
import locale

from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import Qt, SIGNAL, QCoreApplication, QVariant, QString, QSize
from PyQt4.QtCore import QByteArray, QUrl
from PyQt4.QtGui import QSizePolicy, QAction, QListWidgetItem, QClipboard
from PyQt4.QtGui import QMainWindow, QApplication, QIcon, QFont, QImage
from PyQt4.QtGui import QCursor

from PyKDE4 import kdeui
from PyKDE4.kdecore import ki18n, i18n, KCmdLineArgs, KCmdLineOptions
from PyKDE4.kdecore import KAboutData, KConfig, KConfigGroup
from PyKDE4.kdeui import KConfigDialog, KConfigSkeleton, KMessageBox
from PyKDE4.kdeui import KApplication, KXmlGuiWindow, KShortcut, KIcon
from PyKDE4.kdeui import KAction, KStandardAction, KToggleAction, KSelectAction
from PyKDE4.kdeui import KStandardShortcut, KStandardGuiItem, KHistoryComboBox

from eclectusqt import update           # load first so we throw out warning if
                                        #   cjklib is missing
from eclectusqt import dictionarypage
from eclectusqt import radicalpage
from eclectusqt import componentpage
from eclectusqt import handwritingpage
from eclectusqt import vocabularypage
from eclectusqt import renderthread
from eclectusqt import util

from libeclectus import characterinfo
from libeclectus import htmlview

doDebug = 1

class MainWindow(KXmlGuiWindow):
    READING_NAMES = {'Pinyin': i18n('Pinyin'), 'WadeGiles': i18n('Wade-Giles'),
        'MandarinIPA': i18n('IPA'), 'GR': i18n('Gwoyeu Romatzyh'),
        'Jyutping': i18n('Jyutping'), 'CantoneseYale': i18n('Yale'),
        'Hangul': i18n('Hangul'), 'Kana': i18n('Kana')}

    LANGUAGE_NAMES = {'zh-cmn-Hant': i18n('Mandarin (Traditional)'),
        'zh-cmn-Hans': i18n('Mandarin (Simplified)'),
        'zh-yue': i18n('Cantonese'), 'ko': i18n('Korean'),
        'ja': i18n('Japanese')}

    # TODO in update.py
    DICTIONARY_NAMES = {'CEDICT': i18n('English-Chinese (CEDICT)'),
        'CEDICTGR': i18n('English-Chinese (CEDICT, GR version)'),
        'HanDeDict': i18n('German-Chinese (HanDeDict)'),
        'EDICT': i18n('English-Japanese (EDICT)')}

    EXT_DICTIONARY_NAMES = {
        ('zh-cmn-Hans', 'CEDICT'): i18n('Simplified Chinese-English (CEDICT)'),
        ('zh-cmn-Hant', 'CEDICT'): i18n('Traditional Chinese-English (CEDICT)'),
        ('zh-cmn-Hant', 'CEDICTGR'): \
            i18n('Traditional Chinese-English for Gwoyeu Romatzyh (CEDICTGR)'),
        ('zh-cmn-Hans', 'HanDeDict'): \
            i18n('Simplified Chinese-German (HanDeDict)'),
        ('zh-cmn-Hant', 'HanDeDict'): \
            i18n('Traditional Chinese-German (HanDeDict)'),
        ('ja', 'EDICT'): i18n('Japanese-English (EDICT)')}

    CHOOSER_PLUGINS = [
        (radicalpage.RadicalPage, i18n('&Radicals')),
        (componentpage.ComponentPage, i18n('&Components')),
        (handwritingpage.HandwritingPage, i18n('Hand&writing')),
        (vocabularypage.VocabularyPage, i18n('&Vocabulary')),
        ]
    """Plugins loaded into the side panel."""

    def __init__(self):
        QMainWindow.__init__(self)

        self.miniMode = False

        # start rendering thread
        language = unicode(DictionaryConfig.readEntry("Language", None))
        reading = unicode(DictionaryConfig.readEntry("Transcription", None))
        dictionary = unicode(DictionaryConfig.readEntry("Dictionary", None))
        htmlViewSettings = htmlview.HtmlView.readSettings(
            dict([(unicode(key), unicode(value)) \
                for key, value in DictionaryConfig.entryMap().items()]))

        self.renderThread = renderthread.SQLRenderThread(g_app)
        self.connect(g_app, SIGNAL("aboutToQuit()"),
            self.renderThread.quit)
        self.renderThread.start()

        self.renderThread.setCachedObject(characterinfo.CharacterInfo, language,
            reading, dictionary)
        charInfo = self.renderThread.getObjectInstance(
            characterinfo.CharacterInfo)
        self.renderThread.setCachedObject(htmlview.HtmlView, charInfo,
            **htmlViewSettings)

        # set up UI
        self.setupUi()
        self.setupActions()

        self.connect(self.renderThread, SIGNAL("objectCreated"),
            self.objectCreated)
        self.connect(self.renderThread, SIGNAL("queueEmpty"),
            self.queueEmpty)
        self.connect(self.renderThread, SIGNAL("jobEnqueued"),
            self.jobEnqueued)
        self.connect(self.renderThread, SIGNAL("jobErrorneous"),
            lambda jobId, classObject, method, args, param, e, stacktrace: \
                showDebug(stacktrace.decode('utf8')))

        # finally build gui
        xmlFile = os.path.join(os.getcwd(), 'eclectusqt', 'eclectusui.rc')
        if os.path.exists(xmlFile):
            self.setupGUI(KXmlGuiWindow.StandardWindowOption(
                KXmlGuiWindow.Default ^ KXmlGuiWindow.StatusBar), xmlFile)
        else:
            self.setupGUI(KXmlGuiWindow.StandardWindowOption(
                KXmlGuiWindow.Default ^ KXmlGuiWindow.StatusBar))

        self.restoreWindowState()

        if GeneralConfig.readEntry("Show installer on startup", 'True') \
            == 'True':
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

            self.characterChooser.addItem(page, heading)
            self.connect(page, SIGNAL('inputReceived(const QString &)'),
                self.dictionaryPage.load)

            self.plugins.append(page)

        self.updateDialog = update.UpdateDialog(self, self.renderThread)

        self.setCentralWidget(self.splitterFrame)

    def setupActions(self):
        """Sets up all actions (signal/slot combinations)."""
        # standard action
        KStandardAction.quit(g_app.quit, self.actionCollection())

        # dictionary actions
        self.dictionaryPage.findAction(self.actionCollection())
        self.dictionaryPage.findNextAction(self.actionCollection())
        self.dictionaryPage.findPrevAction(self.actionCollection())
        self.dictionaryPage.copyAction(self.actionCollection())
        self.dictionaryPage.backwardAction(self.actionCollection())
        self.dictionaryPage.forwardAction(self.actionCollection())
        self.dictionaryPage.helpPageAction(self.actionCollection())
        self.dictionaryPage.lookupSelectionAction(self.actionCollection())
        self.dictionaryPage.sectionChooserAction(self.actionCollection())
        self.miniModeAction = self.dictionaryPage.miniModeAction(
            self.actionCollection())
        self.lookupClipboardAction = self.dictionaryPage.lookupClipboardAction(
            self.actionCollection())
        self.lookupClipboardAction.setGlobalShortcut(
            KShortcut(Qt.CTRL + Qt.ALT + Qt.Key_N))

        # update dictionaries
        self.updateAction = self.updateDialog.updateAction(
            self.actionCollection())
        # optimise database
        self.updateDialog.optimiseAction(self.actionCollection())

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

        # dictionary chooser
        self.dictChooserAction = KSelectAction(i18n("&Dictionary"), self)
        self.dictChooserAction.setWhatsThis(i18n("Select a dictionary"))
        self.actionCollection().addAction("dictchooser", self.dictChooserAction)
        self.updateDictionarySelector()

        self.connect(self.dictChooserAction, SIGNAL("triggered(int)"),
            self.dictionaryChanged)

        # reading chooser
        self.readingChooserAction = KSelectAction(i18n("&Pronunciation"), self)
        self.readingChooserAction.setWhatsThis(
            i18n("Select the transcription/romanisation for giving the character's pronunciation"))
        self.actionCollection().addAction("readingchooser",
            self.readingChooserAction)
        self.updateReadingSelector()

        self.connect(self.readingChooserAction,
            SIGNAL("triggered(const QString)"), self.transcriptionChanged)

    def restoreWindowState(self):
        # get saved settings
        lastReadings = [unicode(s) for s in \
            DictionaryConfig.readEntry("Last readings", [])]
        self.LAST_READING = {}
        for entry in lastReadings:
            entryLang, entryDict, entryReading = entry.split(':', 2)
            if entryDict == '':
                entryDict = None
            self.LAST_READING[(entryLang, entryDict)] = entryReading

        # GUI settings
        self.characterCombo.insertItems(GeneralConfig.readEntry("Url History",
            []))
        self.historyLength = int(GeneralConfig.readEntry("History Length", "20"))
        self.autoLookup = GeneralConfig.readEntry(
            "Auto-Lookup clipboard", str(False)) != "False"
        self.autoLookupAction.setChecked(self.autoLookup)
        self.onlyAutoLookupChineseCharacters = GeneralConfig.readEntry(
            "Auto-Lookup only Chinese characters", str(False)) != "False"

        self.splitterFrame.restoreState(QByteArray.fromBase64(
            GeneralConfig.readEntry("Splitter", "").toAscii()))
        self.splitterSizes = [int(i) for i \
            in GeneralConfig.readEntry("Splitter sizes", "220,426").split(',')]

        self.toolbarOriginalState = QByteArray.fromBase64(
            GeneralConfig.readEntry("Toolbar original state", "").toAscii())
        self.restoreState(self.toolbarOriginalState)
        self.menuBar().setVisible(True)

        self.characterChooser.setCurrentIndex(
            int(GeneralConfig.readEntry("Toolbox current", "0")))

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

        w = GeneralConfig.readEntry("Width", "640")
        h = GeneralConfig.readEntry("Height", "420")
        self.defaultWindowSize = QSize(int(w), int(h))
        x = GeneralConfig.readEntry("LastX", "0")
        y = GeneralConfig.readEntry("LastY", "0")

        mini_w = GeneralConfig.readEntry("Mini-mode Width", "400")
        mini_h = GeneralConfig.readEntry("Mini-mode Height", "200")
        self.miniModeWindowSize = QSize(int(mini_w), int(mini_h))

        self.setGeometry(int(x), int(y), int(w), int(h))

    def queryClose(self):
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
            str(self.onlyAutoLookupChineseCharacters))

        # toolbox
        if self.characterChooser.isVisible():
            self.splitterSizes = self.splitterFrame.sizes()
        GeneralConfig.writeEntry("Splitter sizes", ",".join(
            [str(i) for i in self.splitterSizes]))

        GeneralConfig.writeEntry("Toolbar original state",
            QByteArray.toBase64(self.toolbarOriginalState))

        GeneralConfig.writeEntry("Toolbox current",
            str(self.characterChooser.currentIndex()))
        GeneralConfig.writeEntry("Toolbox visibile",
            str(self.characterChooserOriginalVisibility))

        charInfo = self.renderThread.getObjectInstance(
            characterinfo.CharacterInfo)
        DictionaryConfig.writeEntry("Language", charInfo.language)
        DictionaryConfig.writeEntry("Transcription", charInfo.reading)
        DictionaryConfig.writeEntry("Dictionary", charInfo.dictionary)

        htmlView = self.renderThread.getObjectInstance(htmlview.HtmlView)
        for key, value in htmlView.settings().items():
            DictionaryConfig.writeEntry(key, unicode(value))

        self.LAST_READING[(charInfo.language, charInfo.dictionary)] \
            = charInfo.reading
        lastReadings = []
        for language, dictionary in self.LAST_READING.keys():
            reading = self.LAST_READING[(language, dictionary)]
            if dictionary == None:
                dictionary = ''
            lastReadings.append(':'.join([language, dictionary, reading]))
        DictionaryConfig.writeEntry("Last readings", lastReadings)

        return True

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
            miniModeShortcut = unicode(i18n(
                self.miniModeAction.shortcut().toString()))
            text = unicode(i18n("Mini-mode hides your menubar and toolbars. Press %1 again to get back to normal mode.", miniModeShortcut))
            lookupShortcut = self.lookupClipboardAction.globalShortcut().toString()
            if lookupShortcut:
                text = text + "\n\n" \
                    + unicode(i18n("You may look up entries by selecting a word and pressing %1. Alternatively you can turn on auto-lookup or paste from the clipboard by pressing the middle mouse button.",
                    i18n(lookupShortcut)))

            KMessageBox.information(self, text, i18n("Mini-mode"),
                "show_mini-mode_notice")

    def updateDictionarySelector(self):
        languages = self.LANGUAGE_NAMES.keys()
        languages.sort()

        charInfo = self.renderThread.getObjectInstance(
            characterinfo.CharacterInfo)
        dictionaries = charInfo.getAvailableDictionaries()
        dictionaries.sort()
        currentLanguage = charInfo.language
        currentDictionary = charInfo.dictionary

        seenLanguages = set()
        self.dictionaryList = []
        currentIndex = None
        for dictionary in dictionaries:
            _, _, _, lang, _, _ \
                = characterinfo.CharacterInfo.DICTIONARY_INFO[dictionary]
            for language in languages:
                if language.startswith(lang):
                    seenLanguages.add(language)
                    if currentDictionary == dictionary \
                        and currentLanguage == language:
                        currentIndex = len(self.dictionaryList)

                    if (language, dictionary) in self.EXT_DICTIONARY_NAMES:
                        name = self.EXT_DICTIONARY_NAMES[(language, dictionary)]
                    else:
                        name = self.LANGUAGE_NAMES[language] + name
                    self.dictionaryList.append((name, language, dictionary))

        # add languages without dictionaries
        for language in languages:
            if language not in seenLanguages:
                if currentLanguage == language:
                    currentIndex = len(self.dictionaryList)
                self.dictionaryList.append(
                    (self.LANGUAGE_NAMES[language], language, None))

        self.dictChooserAction.setItems(
            [name for name, _, _ in self.dictionaryList])
        if currentIndex != None:
            self.dictChooserAction.setCurrentItem(currentIndex)

    def updateReadingSelector(self):
        # update readings
        charInfo = self.renderThread.getObjectInstance(
            characterinfo.CharacterInfo)
        readings = charInfo.getCompatibleReadings(charInfo.language)
        readingNames = [self.READING_NAMES[reading] for reading in readings]
        self.readingChooserAction.setItems(readingNames)

        readingName = self.READING_NAMES[charInfo.reading]
        currentIndex = readingNames.index(readingName)
        self.readingChooserAction.setCurrentItem(currentIndex)

        self.readingNameLookup = dict([(name, reading) for reading, name \
            in self.READING_NAMES.items()])

    def _reloadObjects(self, language, reading, dictionary):
        """Reload objects hold by render thread."""
        self.renderThread.setCachedObject(characterinfo.CharacterInfo, language,
            reading, dictionary)

        charInfo = self.renderThread.getObjectInstance(
            characterinfo.CharacterInfo)
        htmlView = self.renderThread.getObjectInstance(
            htmlview.HtmlView)
        htmlViewSettings = htmlView.settings()
        self.renderThread.setCachedObject(htmlview.HtmlView, charInfo,
            **htmlViewSettings)

        return charInfo.language, charInfo.reading, charInfo.dictionary

    def dictionaryChanged(self, index):
        _, language, dictionary = self.dictionaryList[index]

        if (language, dictionary) in self.LAST_READING:
            reading = self.LAST_READING[(language, dictionary)]
        else:
            reading = None

        _, reading, _ = self._reloadObjects(language, reading, dictionary)

        if reading:
            self.LAST_READING[(language, dictionary)] = reading

    def transcriptionChanged(self, transcription):
        charInfo = self.renderThread.getObjectInstance(
            characterinfo.CharacterInfo)
        reading = self.readingNameLookup[transcription]
        if reading == charInfo.reading:
            return

        language = charInfo.language
        dictionary = charInfo.dictionary
        _, reading, _ = self._reloadObjects(language, reading, dictionary)

        self.LAST_READING[(language, dictionary)] = reading

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

            if self.onlyAutoLookupChineseCharacters:
                clipboardText = unicode(QApplication.clipboard().text(
                    QClipboard.Selection).simplified()).strip()
                if not MainWindow.hasChineseCharacter(clipboardText):
                    return

            self.lookupClipboardAction.trigger()
            # make window flash in taskbar
            self.activateWindow()

    @staticmethod
    def hasChineseCharacter(string):
        """
        Simple function for telling if a Chinese character is present.
        """
        for char in string:
            # CJK RADICAL REPEAT
            if char >= u'⺀':
                return True
        return False

    def slotPageChanged(self, pageName):
        # dictionary page changed
        self.emit(SIGNAL("pageRequested(const QString &)"), pageName)

        self.characterCombo.setEditText(pageName) # TODO mask page type

    def slotVocabularyAdded(self, headword, reading, translation, audio):
        self.emit(SIGNAL("vocabularyAdded(const QString &, const QString &, const QString &, const QString &)"),
            headword, reading, translation, audio)
        if self.vocabularyPlugin != None:
            self.characterChooser.setCurrentIndex(self.vocabularyPlugin)

    def objectCreated(self, id, classObject):
        if classObject == characterinfo.CharacterInfo:
            self.updateDictionarySelector()
            self.updateReadingSelector()

    def queueEmpty(self):
        QApplication.restoreOverrideCursor()

    def jobEnqueued(self, jobId):
        if not QApplication.overrideCursor():
            QApplication.setOverrideCursor(QCursor(Qt.BusyCursor))


def showDebug(message):
    _, system_encoding = locale.getdefaultlocale()
    if doDebug:
        print >>sys.stderr, message.encode(system_encoding, 'ignore')

def run():
    appName     = "eclectus"
    catalog     = ""
    programName = ki18n("Eclectus")
    version     = __version__
    description = ki18n("Han character dictionary")
    license     = KAboutData.License_GPL_V3
    copyright   = ki18n("(c) 2008-2009 Christoph Burgmer")
    text        = ki18n(
        "Eclectus is a small Han character dictionary for learners.")
    homePage    = __url__
    bugEmail    = "cburgmer@ira.uka.de"

    bugAddress = "http://code.google.com/p/eclectus/issues/list"
    aboutData = KAboutData(appName, catalog, programName, version, description,
        license, copyright, text, homePage, bugEmail)
    aboutData.addAuthor(ki18n("Christoph Burgmer"), ki18n("Developer"),
        "cburgmer@ira.uka.de", "http://www.stud.uni-karlsruhe.de/~uyhc")
    aboutData.setCustomAuthorText(ki18n("Please use %1 to report bugs.")\
            .subs(bugAddress),
        ki18n('Please use %1 to report bugs.')\
            .subs('<a href="%s">%s</a>' % (bugAddress, bugAddress)))
    aboutData.addCredit(ki18n(''), ki18n("Arrr, Eclectus sits on the shoulders of some fine pirates:"))
    aboutData.addCredit(ki18n("Jim Breen and contributors"), ki18n("EDICT"), '',
        'http://www.csse.monash.edu.au/~jwb/j_edict.html')
    aboutData.addCredit(ki18n("Paul Denisowski and current contributors"),
        ki18n("CEDICT"), '', 'http://www.mdbg.net/chindict/chindict.php')
    aboutData.addCredit(ki18n("HanDeDict team"), ki18n("HanDeDict"), '',
        'http://www.chinaboard.de/chinesisch_deutsch.php')
    aboutData.addCredit(ki18n("Tomoe developers"),
        ki18n("Tomoe handwriting recognition"),
        'tomoe-devel@lists.sourceforge.net', 'http://tomoe.sourceforge.jp')
    aboutData.addCredit(ki18n("Unicode Consortium and contributors"),
        ki18n("Unihan database"), '', 'http://unicode.org/charts/unihan.html')
    aboutData.addCredit(ki18n("Commons Stroke Order Project"),
        ki18n("Stroke order pictures"), '',
        'http://commons.wikimedia.org/wiki/Commons:Stroke_Order_Project')
    aboutData.addCredit(ki18n("Tim Eyre and the Wadoku Project"),
        ki18n("Kanji stroke order font"), '',
        'http://sites.google.com/site/nihilistorguk/')
    aboutData.addCredit(ki18n("Wei Gao, Vion Nicolas and the Shtooka Project"),
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