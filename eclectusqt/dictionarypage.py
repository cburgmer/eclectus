#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Core dictionary module.

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

import re
import urllib
import functools

from PyQt4 import QtGui
from PyQt4.QtCore import Qt, SIGNAL, QObject, QVariant, QUrl
from PyQt4.QtGui import QWidget, QApplication, QDesktopServices, QIcon, QAction
from PyQt4.QtGui import QPrinter, QPrintDialog
from PyQt4.QtWebKit import QWebView, QWebPage
try:
    from PyQt4.phonon import Phonon
    hasPhononSupport = True
except ImportError:
    hasPhononSupport = False
except RuntimeError:
    hasPhononSupport = False

from PyKDE4.kdeui import KIcon, KAction, KToggleAction, KToolBarPopupAction
from PyKDE4.kdeui import KActionCollection, KStandardAction, KStandardShortcut
from PyKDE4.kdeui import KStandardGuiItem, KMessageBox, KFind, KFindDialog
from PyKDE4.kdeui import KMenu, KActionMenu, KSelectAction, KShortcut
from PyKDE4.kdecore import ki18n, i18n

from eclectusqt import util

from libeclectus.dictionaryview import DictionaryView
from libeclectus.util import encodeBase64, decodeBase64, getCJKScriptClass
from libeclectus.dictionary import (getDictionaryLanguage,
    getDictionaryCompatibleLanguages)

class BrowsingHistory(QObject):
    """
    Defines a simple browsing history where strings can be added and navigated
    between. On activation of a item a Qt signal is emitted.
    """
    def __init__(self):
        QObject.__init__(self)
        self.browserHistory = []
        self.curHistoryIdx = -1
        self.lastHistoryIdx = -1

    def emitActivated(self):
        self.emit(SIGNAL("activated(int)"), self.curHistoryIdx)
        self.emit(SIGNAL("activated(const QString)"), self.current())

    def addItem(self, title):
        assert type(title) in [type(u''), type('')]
        # cut forward items
        if self.canGoForward():
            self.browserHistory = self.browserHistory[:self.curHistoryIdx + 1]

        if title != self.current():
            # add to list
            self.lastHistoryIdx = self.curHistoryIdx
            self.curHistoryIdx = len(self.browserHistory)
            self.browserHistory.append(title)

    def current(self):
        if self.curHistoryIdx < 0:
            return None
        return self.browserHistory[self.curHistoryIdx]

    def last(self):
        if self.lastHistoryIdx < 0:
            return None
        return self.browserHistory[self.lastHistoryIdx]

    def canGoBack(self):
        return self.curHistoryIdx > 0

    def canGoForward(self):
        return self.curHistoryIdx < (len(self.browserHistory) - 1)

    def back(self):
        if self.canGoBack():
            self.lastHistoryIdx = self.curHistoryIdx
            self.curHistoryIdx = self.curHistoryIdx - 1
            self.emitActivated()

    def forward(self):
        if self.canGoForward():
            self.lastHistoryIdx = self.curHistoryIdx
            self.curHistoryIdx = self.curHistoryIdx + 1
            self.emitActivated()

    def setCurrent(self, i):
        if i <= 0 and i >= len(self.browserHistory):
            raise ValueError("Illegal index")

        self.lastHistoryIdx = self.curHistoryIdx
        self.curHistoryIdx = i
        self.emitActivated()

    def forwardItems(self, maxItems=10):
        return [(self.browserHistory[idx], idx) for idx \
            in range(self.curHistoryIdx + 1,
                min(self.curHistoryIdx + maxItems, len(self.browserHistory)))]

    def backItems(self, maxItems=10):
        return [(self.browserHistory[idx], idx) for idx \
            in range(self.curHistoryIdx - 1,
                max(self.curHistoryIdx - maxItems, -1), -1)]


class DictionaryPage(QWebView):
    READING_NAMES = {'Pinyin': ki18n('Pinyin'),
        'WadeGiles': ki18n('Wade-Giles'), 'MandarinIPA': ki18n('IPA'),
        'GR': ki18n('Gwoyeu Romatzyh'), 'Jyutping': ki18n('Jyutping'),
        'CantoneseYale': ki18n('Yale'), 'Hangul': ki18n('Hangul'),
        'Kana': ki18n('Kana')}

    LANGUAGE_NAMES = {'zh-cmn': ki18n('Mandarin'), 'zh-yue': ki18n('Cantonese'),
        'ko': ki18n('Korean'), 'ja': ki18n('Japanese')}

    DICTIONARY_NAMES = {'CEDICT': ki18n('English-Chinese (CEDICT)'),
        'CEDICTGR': ki18n('English-Chinese (CEDICT, GR version)'),
        'HanDeDict': ki18n('German-Chinese (HanDeDict)'),
        'CFDICT': ki18n('French-Chinese (CFDICT)'),
        'EDICT': ki18n('English-Japanese (EDICT)')}

    CHARACTER_DOMAINS = {
        'Unicode': ki18n('&all characters'),
        'IICore': ki18n('9810 characters (&International ideographic core)'),
        'GB2312': ki18n('6763 characters (&GB2312)'),
        'BIG5': ki18n('13063 characters (&BIG5)'),
        'BIG5HKSCS': ki18n('17575 characters (BIG5-&HKSCS)'),
        'JISX0208': ki18n('6356 characters (&JIS X 0208)'),
        'JISX0208_0213': ki18n('9748 characters (JIS &X 0208/0213)'),
        }
    """Pretty print strings for character domains."""

    DEFAULT_HIDDEN_SECTIONS = ['getCharacterWithComponentSection',
        'getLinkSection']
    """Sections hidden by default."""

    SECTION_NAMES ={'getMeaningSection': ki18n('Dictionary'),
        'getVariantSection': ki18n('Variant links'),
        'getSimilarsSection': ki18n('Similar character links'),
        'getVocabularySection': ki18n('Vocabulary'),
        'getStrokeOrderSection': ki18n('Stroke order'),
        'getLinkSection': ki18n('Links'),
        'getCharacterWithComponentSection': ki18n('Characters including glyph'),
        'getCharacterWithSamePronunciationSection':
                ki18n('Characters with same pronunciation'),
        'getHeadwordContainedCharactersSection': ki18n('Single characters'),
        'getDecompositionTreeSection': ki18n('Character structure'),
        #'getCombinedContainedVocabularySection': i18n('Contained vocabulary'), # TODO
        }

    DEFAULT_VIEW_SECTIONS = {'character': ['getGeneralCharacterSection',
            'getVariantSection', 'getSimilarsSection', 'getMeaningSection',
            'getVocabularySection', 'getStrokeOrderSection',
            'getDecompositionTreeSection', 'getCharacterWithComponentSection',
            'getCharacterWithSamePronunciationSection', 'getLinkSection'],
        'word': ['getGeneralWordSection', 'getVariantSection',
            'getSimilarsSection', 'getMeaningSection',
            'getHeadwordContainedCharactersSection', 'getVocabularySection',
            'getLinkSection'],
        'search': ['getVocabularySearchSection'],
        'othervocabulary': ['getOtherVocabularySearchSection'],
        'similar': ['getSimilarVocabularySearchSection'],
        'vocabulary': ['getFullVocabularySection']}

    DEFAULT_MINI_VIEW_SECTIONS = {'character': [
            'getMiniGeneralCharacterSection', 'getVariantSection',
            'getSimilarsSection', 'getMeaningSection'],
        'word': ['getMiniGeneralWordSection', 'getVariantSection',
            'getSimilarsSection', 'getHeadwordContainedVocabularySection'],
        'search': ['getVocabularySearchSection'],
        'othervocabulary': ['getOtherVocabularySearchSection'],
        'similar': ['getSimilarVocabularySearchSection'],
        'vocabulary': ['getFullVocabularySection']}

    DEFAULT_SECTION_CONTENT_VISIBILITY = {'getMeaningSection': True,
        'getVocabularySection': True, 'getCharacterWithComponentSection': False,
        'getCharacterWithSamePronunciationSection': False,
        'getHeadwordContainedCharactersSection': True,
        'getLinkSection': True,
        'getDecompositionTreeSection': True, 'getStrokeOrderSection': True,
        #'getContainedVocabularySection': True # TODO
        }

    VIEW_ABBREVIATIONS = {'c': 'character', 'w': 'word', 'v': 'vocabulary',
        'o': 'othervocabulary', 's': 'similar',
        i18n('character'): 'character', i18n('word'): 'word',
        i18n('vocabulary'): 'vocabulary',
        i18n('othervocabulary'): 'othervocabulary',
        i18n('similar'): 'similar',
        i18n('about'): 'about'}

    SEARCH_EXAMPLES = {
        ('zh-cmn-Hans', 'Pinyin'): [u'折衷鹦鹉', u'wulong茶', u'dui?qi'],
        ('zh-cmn-Hant', 'Pinyin'): [u'折衷鸚鵡', u'wulong茶', u'dui?qi'],
        ('zh-cmn-Hant', 'GR'): [u'折衷鸚鵡', u'ulong茶', u'duey?chii'],
        ('zh-cmn-Hans', 'WadeGiles'): [u'折衷鹦鹉', u'wu1lung2茶', u"tui4?ch'i3"],
        ('zh-cmn-Hant', 'WadeGiles'): [u'折衷鸚鵡', u'wu1lung2茶', u"tui4?ch'i3"],
        ('zh-cmn-Hans', 'MandarinIPA'): [u'折衷鹦鹉'],
        ('zh-cmn-Hant', 'MandarinIPA'): [u'折衷鸚鵡'],
        ('zh-yue-Hans', 'CantoneseYale'): [u'龙', u'gwok'],
        ('zh-yue-Hans', 'Jyutping'): [u'龙', u'gwok'],
        ('zh-yue-Hant', 'CantoneseYale'): [u'龍', u'gwok'],
        ('zh-yue-Hant', 'Jyutping'): [u'龍', u'gwok'],
        ('ko', 'Hangul'): [u'龍', u'국'],
        ('ja', 'Kana'): [u'東京', u'とうきょう']}
    """Examples for the help page."""

    WELCOME_PAGE = 'about:help'

    WELCOME_TEXT = {'ja': u'ようこそ', 'ko': u'환영합니다', 'zh-cmn-Hans': u'欢迎',
        'zh-cmn-Hant': u'歡迎', 'zh-yue-Hans': u'欢迎', 'zh-yue-Hant': u'歡迎'}
    """Welcome message on about:help page by language code."""

    POLLY_CHANGE_TEXT_JAVASCRIPT = """<script>
function setText(text) {
    svgdoc = document.getElementById("polly").getSVGDocument();
    textElement = svgdoc.getElementById("bubble").firstChild;
    textElement.nodeValue = text;
}
var link = ''
function setWordLink(headword) {
    link = 'about:blank#lookup(' + headword + ')';
}
//function _go() { document.location = link; }
//function _go() { alert('navigate:' + link); }
function _go() { }
</script>
""" # TODO use _go function instead of workaround with "alert"
    # TODO using alert will currently cause a crash
    """ECMAscript code to change test in svg image."""

    def __init__(self, mainWindow, renderThread, pluginConfig=None):
        QWebView.__init__(self, mainWindow)
        self.renderThread = renderThread
        self.pluginConfig = pluginConfig

        self.initialised = False

        dictionaryViewSettings = {}
        self.hiddenSections = set(self.DEFAULT_HIDDEN_SECTIONS)
        self.findHistory = []
        self.startPage = 'welcome'
        currentString = self.WELCOME_PAGE

        if self.pluginConfig:
            dictionaryViewSettings = DictionaryView.readSettings(
                dict([(unicode(key), unicode(value)) \
                    for key, value in self.pluginConfig.entryMap().items()]))

            hiddenSections = util.readConfigString(self.pluginConfig,
                "Dictionary hidden sections", None)
            if hiddenSections:
                self.hiddenSections = set([unicode(s) for s \
                    in hiddenSections.split(',')])

            findHistory = util.readConfigString(self.pluginConfig,
                "Dictionary find history", None)
            if findHistory:
                self.findHistory = findHistory.split(',')

            self.startPage = util.readConfigString(self.pluginConfig,
                "Dictionary start page", "welcome")
            if self.startPage == 'last':
                lastPage = util.readConfigString(self.pluginConfig,
                    "Dictionary last page", self.WELCOME_PAGE)
                if lastPage:
                    currentString = lastPage
            else:
                currentString = self.WELCOME_PAGE

            lastReadings = util.readConfigString(self.pluginConfig,
                "Last readings", '').split(',')
            self.lastReading = {}
            for entry in lastReadings:
                if not entry: continue
                if entry.count(':') > 2:
                    # compatibility to version 0.2beta
                    _, entryDict, entryReading = entry.split(':', 2)
                else:
                    entryDict, entryReading = entry.split(':', 1)
                self.lastReading[entryDict] = entryReading

            lastLanguage = util.readConfigString(self.pluginConfig,
                "Last languages", '').split(',')
            self.lastLanguage = {}
            for entry in lastLanguage:
                if not entry: continue
                entryDict, entryLanguage = entry.split(':', 1)
                self.lastLanguage[entryDict] = entryLanguage

        if 'databaseUrl' not in dictionaryViewSettings:
            dictionaryViewSettings['databaseUrl'] = unicode('sqlite:///'
                + util.getLocalData('dictionaries.db'))

        self._loadObjects(dictionaryViewSettings)

        self.miniMode = False
        self.sectionContentVisible \
            = self.DEFAULT_SECTION_CONTENT_VISIBILITY.copy()
        self.currentJobs = []
        self.scrollValues = {}
        self.mediaObject = None
        self.findDialog = None
        self.actionCollection = KActionCollection(self)
        self.styleFile = util.getData('style.css')

        self.setPage(util.HandyWebpage(self))
        # set up search history
        self.history = BrowsingHistory()
        self.connect(self.history, SIGNAL("activated(const QString)"),
            self.slotHistoryActivated)
        self.history.addItem(currentString)

        # connect to main window
        self.connect(mainWindow, SIGNAL("writeSettings()"),
            self.writeSettings)
        self.connect(mainWindow, SIGNAL("databaseChanged()"),
            self._reloadObjects)

        self.connect(self.renderThread, SIGNAL("jobFinished"),
            self.contentRendered)

        # connect to the widgets
        self.connect(self.page(), SIGNAL("linkClicked(const QUrl &)"),
            self.slotLinkClicked)
        self.connect(self.page(), SIGNAL("loadFinished(bool)"),
            self.slotPageLoaded)

        self.page().setLinkDelegationPolicy(QWebPage.DelegateAllLinks)

        self.setupActions()

    def showEvent(self, event):
        if not self.initialised:
            self.initialised = True
            self.history.setCurrent(0)

        QWidget.showEvent(self, event)

    def _loadObjects(self, dictionaryViewSettings):
        self.renderThread.setCachedObject(DictionaryView,
            **dictionaryViewSettings)

        dictionaryView = self.renderThread.getObjectInstance(DictionaryView)
        # get settings
        for option in 'language', 'characterDomain', 'dictionary', 'reading':
            setattr(self, option, getattr(dictionaryView, option))

        self.emit(SIGNAL("settingsChanged()"))

    def settings(self):
        settings = {}
        for attr in 'language', 'characterDomain', 'dictionary', 'reading':
            settings[attr] = getattr(self, attr)
        return settings

    def setupActions(self):
        # lookup clipboard action
        self._lookupClipboardAction = KAction(i18n("&Lookup Clipboard"), self)
        self.actionCollection.addAction("lookupclipboard",
            self._lookupClipboardAction)
        self._lookupClipboardAction.setWhatsThis(
            i18n("Lookup the clipboard."))
        self.connect(self._lookupClipboardAction, SIGNAL("triggered(bool)"),
            self.slotLookupClipboard)
        self._lookupClipboardAction.setIcon(
            QIcon(util.getIcon('lookup-clipboard.png')))
        self._lookupClipboardAction.setGlobalShortcut(
            KShortcut(Qt.CTRL + Qt.ALT + Qt.Key_N))

        # lookup selection action
        self._lookupSelectionAction = KAction(i18n("Lookup &Selection"), self)
        self.actionCollection.addAction("lookupselection",
            self._lookupSelectionAction)
        self._lookupSelectionAction.setWhatsThis(
            i18n("Lookup selected text."))
        self.connect(self._lookupSelectionAction, SIGNAL("triggered(bool)"),
            self.slotLookupSelection)
        self._lookupSelectionAction.setShortcut(Qt.CTRL + Qt.Key_N)
        self._lookupSelectionAction.setEnabled(self.selectedText() != '')
        self.connect(self.page(), SIGNAL("selectionChanged()"),
            lambda: self._lookupSelectionAction.setEnabled(
                self.selectedText() != ''))

        # mini mode action
        self._miniModeAction = KToggleAction(i18n("Mini-mode"), self)
        self.actionCollection.addAction("minimode", self._miniModeAction)
        self._miniModeAction.setShortcut(Qt.Key_F10)
        self._miniModeAction.setWhatsThis(
            i18n("Toggles window between normal and small mode which compacts the window's representation."))
        self.connect(self._miniModeAction, SIGNAL("triggered(bool)"),
            self.slotMiniMode)
        self._miniModeAction.setIcon(QIcon(util.getIcon('mini-mode.png')))

        # help page action
        self._helpPageAction = KAction(i18n("Welcome &Page"), self)
        self.actionCollection.addAction("helppage", self._helpPageAction)
        self._helpPageAction.setWhatsThis(i18n("Go to welcome page."))
        self.connect(self._helpPageAction, SIGNAL("triggered(bool)"),
            lambda: self.load('about:help'))

        # Web actions, bridged to KActions
        # copy action
        self._copyAction = self.bridgeWebAction(QWebPage.Copy,
            KStandardAction.copy)

        # selectAll action
        try:
            self._selectAllAction = self.bridgeWebAction(QWebPage.SelectAll,
                KStandardAction.selectAll)
        except AttributeError:
            # supported from Qt 4.5 on
            self._selectAllAction = None

        # forward/backward buttons
        backItem, forwardItem = KStandardGuiItem.backAndForward()

        self._backwardAction = KToolBarPopupAction(
            KIcon(backItem.iconName()), backItem.text(), self)
        self.actionCollection.addAction("go_back", self._backwardAction)
        self._backwardAction.setWhatsThis(
            i18n("Move backwards one step in the browsing history"))
        self._backwardAction.setToolTip(
            i18n("Move backwards one step in the browsing history"))
        self._backwardAction.setShortcut(KStandardShortcut.shortcut(
            KStandardShortcut.Back))
        self.connect(self._backwardAction,
            SIGNAL("triggered(Qt::MouseButtons, Qt::KeyboardModifiers)"),
            self.history.back)
        self.connect(self._backwardAction.menu(), SIGNAL("aboutToShow()"),
            self.slotBackAboutToShow)
        self.connect(self._backwardAction.menu(), SIGNAL("triggered(QAction*)"),
            self.slotForwardBackwardActivated)

        self._forwardAction = KToolBarPopupAction(
            KIcon(forwardItem.iconName()), forwardItem.text(), self)
        self.actionCollection.addAction("go_forward", self._forwardAction)
        self._forwardAction.setWhatsThis(
            i18n("Move forward one step in the browsing history"))
        self._forwardAction.setToolTip(
            i18n("Move forward one step in the browsing history"))
        self._forwardAction.setShortcut(KStandardShortcut.shortcut(
            KStandardShortcut.Forward))
        self.connect(self._forwardAction,
            SIGNAL("triggered(Qt::MouseButtons, Qt::KeyboardModifiers)"),
            self.history.forward)
        self.connect(self._forwardAction.menu(), SIGNAL("aboutToShow()"),
            self.slotForwardAboutToShow)
        self.connect(self._forwardAction.menu(), SIGNAL("triggered(QAction*)"),
            self.slotForwardBackwardActivated)

        self._forwardAction.setEnabled(self.history.canGoForward())
        self._backwardAction.setEnabled(self.history.canGoBack())

        # find actions
        self._findAction = KStandardAction.find(self.slotFind,
            self.actionCollection)
        self._findNextAction = KStandardAction.findNext(self.slotFindNext,
            self.actionCollection)
        self._findPrevAction = KStandardAction.findPrev(self.slotFindPrev,
            self.actionCollection)

        # character domain chooser
        self._simpTradChooserAction = KAction(self)
        self._simpTradChooserAction.setWhatsThis(
            i18n("Toggle between simplified and traditional characters"))
        self._simpTradChooserAction.setObjectName("simptradchooser")
        self.connect(self._simpTradChooserAction, SIGNAL("triggered(bool)"),
            self.simpTradChanged)
        self._simpTradChooserAction.setIcon(
            QIcon(util.getIcon('simplified.png')))

        self.updateSimpTradSelector()

        # dictionary chooser action
        self._dictionaryChooserAction = KSelectAction(i18n("&Dictionary"), self)
        self._dictionaryChooserAction.setWhatsThis(i18n("Select a dictionary"))
        self._dictionaryChooserAction.setObjectName("dictchooser")
        self.connect(self._dictionaryChooserAction, SIGNAL("triggered(int)"),
            self.dictionaryChanged)

        self.updateDictionarySelector()

        # reading chooser
        self._readingChooserAction = KSelectAction(i18n("&Pronunciation"), self)
        self._readingChooserAction.setWhatsThis(
            i18n("Select the transcription/romanisation for giving the character's pronunciation"))
        self._readingChooserAction.setObjectName("readingchooser")
        self.connect(self._readingChooserAction, SIGNAL("triggered(int)"),
            self.readingChanged)

        self.updateReadingSelector()

        # character domain chooser
        self._charDomainChooserAction = KSelectAction(i18n("&Character Domain"),
            self)
        self._charDomainChooserAction.setWhatsThis(
            i18n("Select the character domain to narrow search results"))
        self._charDomainChooserAction.setObjectName("chardomainchooser")
        self.connect(self._charDomainChooserAction, SIGNAL("triggered(int)"),
            self.charDomainChanged)

        self.updateCharDomainSelector()

        # section chooser action
        self._sectionChooserAction = KActionMenu(i18n("&Sections"), self)
        self._sectionChooserAction.setWhatsThis(
            i18n("Selects the sections shown in the various views"))
        self._sectionChooserAction.setObjectName("sectionchooser")

        self.sectionSelectActions = []
        sortedSections = sorted(
            [(k, v.toString()) for k, v in self.SECTION_NAMES.items()],
                key=lambda (key, value): value)
        self.sectionIndex = dict([(idx, section) for idx, (section, _) \
            in enumerate(sortedSections)])

        for idx, section in self.sectionIndex.items():
            sectionName = unicode(self.SECTION_NAMES[section].toString())
            toggleAction = KToggleAction(sectionName.replace('&', '&&'), self)
            self._sectionChooserAction.addAction(toggleAction)
            self.sectionSelectActions.append(toggleAction)

        self.updateSectionSelector()

        for idx in self.sectionIndex:
            toggleAction = self.sectionSelectActions[idx]
            self.connect(toggleAction, SIGNAL("toggled(bool)"),
                functools.partial(self.sectionSelectionChanged, idx))

        # print action
        self._printAction = KStandardAction.print_(self.slotPrint,
            self.actionCollection)

    def bridgeWebAction(self, webActionName, standardAction):
        webAction = self.pageAction(webActionName)
        action = standardAction(
            lambda: self.triggerPageAction(webActionName),
            self.actionCollection)

        action.setEnabled(webAction.isEnabled())
        self.connect(webAction, SIGNAL("changed()"),
            lambda: action.setEnabled(webAction.isEnabled()))
        self.connect(webAction, SIGNAL("triggered()"), action.trigger)

        return action

    def updateSimpTradSelector(self):
        dictionaryLang = getDictionaryLanguage(self.dictionary)

        if self.language.endswith('Hant'):
            self._simpTradChooserAction.setText(i18n("Traditional Cha&racters"))
        else:
            self._simpTradChooserAction.setText(i18n("Simplified Cha&racters"))

        if dictionaryLang in ('zh-cmn', 'zh-yue'):
            self._simpTradChooserAction.setEnabled(True)
            if self.language.endswith('Hant'):
                self._simpTradChooserAction.setIcon(
                    QIcon(util.getIcon('traditional.png')))
            else:
                self._simpTradChooserAction.setIcon(
                    QIcon(util.getIcon('simplified.png')))
        else:
            self._simpTradChooserAction.setEnabled(False)
            self._simpTradChooserAction.setIcon(
                QIcon(util.getIcon('simplified.png')))

    def updateDictionarySelector(self):
        dictionaryView = self.renderThread.getObjectInstance(DictionaryView)

        self.dictionaryList = sorted(dictionaryView.availableDictionaryNames)

        dictionaryNames = []
        currentIndex = None
        for idx, dictionary in enumerate(self.dictionaryList):
            if self.dictionary == dictionary:
                currentIndex = idx

            if dictionary in self.DICTIONARY_NAMES:
                name = self.DICTIONARY_NAMES[dictionary].toString()
            else:
                language = getDictionaryLanguage(dictionary, noScript=True)
                if language in self.LANGUAGE_NAMES:
                    name = self.LANGUAGE_NAMES[language].toString()
                else:
                    # fallback
                    name = language
            dictionaryNames.append(name)

        self._dictionaryChooserAction.setItems(dictionaryNames)
        if currentIndex is not None:
            self._dictionaryChooserAction.setCurrentItem(currentIndex)

    def updateReadingSelector(self):
        self.readingList = getDictionaryCompatibleLanguages(self.dictionary)

        readingNames = []
        currentIndex = None
        for idx, reading in enumerate(self.readingList):
            if self.reading == reading:
                currentIndex = idx

            if reading in self.READING_NAMES:
                name = self.READING_NAMES[reading].toString()
            else:
                # fallback
                name = reading
            readingNames.append(name)

        self._readingChooserAction.setItems(readingNames)
        if currentIndex is not None:
            self._readingChooserAction.setCurrentItem(currentIndex)

    def updateCharDomainSelector(self):
        dictionaryView = self.renderThread.getObjectInstance(DictionaryView)

        self.characterDomainList = dictionaryView.compatibleCharacterDomains[:]

        characterDomainNames = []
        currentIndex = None
        for idx, charDomain in enumerate(self.characterDomainList):
            if self.characterDomain == charDomain:
                currentIndex = idx

            if charDomain in self.CHARACTER_DOMAINS:
                name = self.CHARACTER_DOMAINS[charDomain].toString()
            else:
                # fallback
                name = charDomain
            characterDomainNames.append(name)

        self._charDomainChooserAction.setItems(characterDomainNames)
        if currentIndex is not None:
            self._charDomainChooserAction.setCurrentItem(currentIndex)

    def updateSectionSelector(self):
        for idx, section in self.sectionIndex.items():
            toggleAction = self.sectionSelectActions[idx]
            toggleAction.setChecked(section not in self.hiddenSections)

            toggleAction.setEnabled(self.dictionary != None \
                or not DictionaryView.needsDictionary(section))

    def _reloadObjects(self, **options):
        # read existing settings
        if self.renderThread.hasObject(DictionaryView):
            dictionaryView = self.renderThread.getObjectInstance(DictionaryView)
            for option in ('language', 'characterDomain', 'dictionary',
                'reading'):
                if option not in options:
                    options[option] = getattr(dictionaryView, option)

        self._loadObjects(options)

        self.reload()

        self.updateSimpTradSelector()
        self.updateDictionarySelector()
        self.updateReadingSelector()
        self.updateCharDomainSelector()
        self.updateSectionSelector()

    def simpTradChanged(self, index):
        if self.language.endswith('Hant'):
            language = self.language[:-4] + 'Hans'
            self._reloadObjects(language=language)
        elif self.language.endswith('Hans'):
            language = self.language[:-4] + 'Hant'
            self._reloadObjects(language=language)

        self.lastLanguage[self.dictionary] = self.language

    def dictionaryChanged(self, index):
        dictionary = self.dictionaryList[index]

        language = self.lastLanguage.get(dictionary, None)
        reading = self.lastReading.get(dictionary, None)

        self._reloadObjects(language=language, reading=reading,
            dictionary=dictionary)

        self.lastLanguage[self.dictionary] = self.language
        self.lastReading[self.dictionary] = self.reading

    def readingChanged(self, index):
        reading = self.readingList[index]

        self._reloadObjects(reading=reading)

        self.lastReading[self.dictionary] = self.reading

    def charDomainChanged(self, index):
        characterDomain = self.characterDomainList[index]

        self._reloadObjects(characterDomain=characterDomain)

    def sectionSelectionChanged(self, index, checked):
        section = self.sectionIndex[index]
        if checked:
            if section in self.hiddenSections:
                self.hiddenSections.remove(section)
        else:
            self.hiddenSections.add(section)
        self.reload()

    def mousePressEvent(self, event):
        # allow for middle mouse button paste (Unix style)
        QWebView.mousePressEvent(self, event)
        if event.button() == Qt.MidButton:
            self.slotLookupClipboard()

    def contextMenuEvent(self, event):
        contextMenu = KMenu(self)
        contextMenu.addAction(self._backwardAction)
        contextMenu.addAction(self._forwardAction)
        if self.miniMode:
            contextMenu.addAction(self._miniModeAction)
        contextMenu.addSeparator()
        contextMenu.addAction(self._lookupSelectionAction)
        contextMenu.addAction(self._lookupClipboardAction)
        contextMenu.addSeparator()
        contextMenu.addAction(self._copyAction)

        hitTestResult = self.page().mainFrame().hitTestContent(event.pos())
        #copyImageAction = self.pageAction(QWebPage.CopyImageToClipboard)
        #contextMenu.addAction(copyImageAction)
        #copyImageAction.setEnabled(len(hitTestResult.imageUrl().toString()) > 0)

        copyLinkAction = self.pageAction(QWebPage.CopyLinkToClipboard)
        contextMenu.addAction(copyLinkAction)
        linkUrl = unicode(hitTestResult.linkUrl().toString())
        copyLinkAction.setEnabled(len(linkUrl) > 0 \
            and linkUrl.startswith('http://'))

        if self._selectAllAction:
            contextMenu.addSeparator()
            contextMenu.addAction(self._selectAllAction)

        contextMenu.popup(event.globalPos())

    def copyAction(self, actionCollection):
        actionCollection.addAction(self._copyAction.objectName(),
            self._copyAction)
        return self._copyAction

    def selectAllAction(self, actionCollection):
        if self._selectAllAction:
            actionCollection.addAction(self._selectAllAction.objectName(),
                self._selectAllAction)
        return self._selectAllAction

    def findAction(self, actionCollection):
        actionCollection.addAction(self._findAction.objectName(),
            self._findAction)
        return self._findAction

    def findNextAction(self, actionCollection):
        actionCollection.addAction(self._findNextAction.objectName(),
            self._findNextAction)
        return self._findNextAction

    def findPrevAction(self, actionCollection):
        actionCollection.addAction(self._findPrevAction.objectName(),
            self._findPrevAction)
        return self._findPrevAction

    def lookupClipboardAction(self, actionCollection):
        actionCollection.addAction(self._lookupClipboardAction.objectName(),
            self._lookupClipboardAction)
        return self._lookupClipboardAction

    def lookupSelectionAction(self, actionCollection):
        actionCollection.addAction(self._lookupSelectionAction.objectName(),
            self._lookupSelectionAction)
        return self._lookupSelectionAction

    def miniModeAction(self, actionCollection):
        actionCollection.addAction(self._miniModeAction.objectName(),
            self._miniModeAction)
        return self._miniModeAction

    def helpPageAction(self, actionCollection):
        actionCollection.addAction(self._helpPageAction.objectName(),
            self._helpPageAction)
        return self._helpPageAction

    def backwardAction(self, actionCollection):
        actionCollection.addAction(self._backwardAction.objectName(),
            self._backwardAction)
        return self._backwardAction

    def forwardAction(self, actionCollection):
        actionCollection.addAction(self._forwardAction.objectName(),
            self._forwardAction)
        return self._forwardAction

    def simpTradChooserAction(self, actionCollection):
        actionCollection.addAction(self._simpTradChooserAction.objectName(),
            self._simpTradChooserAction)
        return self._simpTradChooserAction

    def dictionaryChooserAction(self, actionCollection):
        actionCollection.addAction(self._dictionaryChooserAction.objectName(),
            self._dictionaryChooserAction)
        return self._dictionaryChooserAction

    def readingChooserAction(self, actionCollection):
        actionCollection.addAction(self._readingChooserAction.objectName(),
            self._readingChooserAction)
        return self._readingChooserAction

    def charDomainChooserAction(self, actionCollection):
        actionCollection.addAction(self._charDomainChooserAction.objectName(),
            self._charDomainChooserAction)
        return self._charDomainChooserAction

    def sectionChooserAction(self, actionCollection):
        actionCollection.addAction(self._sectionChooserAction.objectName(),
            self._sectionChooserAction)
        return self._sectionChooserAction

    def printAction(self, actionCollection):
        actionCollection.addAction(self._printAction.objectName(),
            self._printAction)
        return self._printAction

    def registerGlobalActions(self, actionCollection):
        for action in ('findAction', 'findNextAction', 'findPrevAction',
            'copyAction', 'selectAllAction', 'backwardAction', 'forwardAction',
            'helpPageAction', 'lookupSelectionAction', 'printAction',
            'miniModeAction', 'lookupClipboardAction', 'simpTradChooserAction',
            'dictionaryChooserAction', 'readingChooserAction',
            'charDomainChooserAction', 'sectionChooserAction'):
            getattr(self, action)(actionCollection)

    def slotLinkClicked(self, url):
        cmd = unicode(url.toString()).replace('about:blank#', '')

        if cmd.startswith('toggleVisibility'):
            blockName = re.match('toggleVisibility\(([^\)]+)\)', cmd).group(1)

            if blockName in self.sectionContentVisible:
                self.sectionContentVisible[blockName] \
                    = not self.sectionContentVisible[blockName]
            else:
                self.sectionContentVisible[blockName] = False
            self.reload()
        elif cmd.startswith('lookup'):
            inputString = decodeBase64(
                re.match('lookup\(([^\)]+)\)', cmd).group(1))

            self.load(inputString)
        elif cmd.startswith('play'):
            path = re.match('play\(([^\)]+)\)', cmd).group(1)
            realPath = urllib.unquote(path).decode('utf8')
            self.playCharString(realPath)
        elif cmd.startswith('addvocab'):
            params = re.match('addvocab\(([^\)]+)\)', cmd).group(1)
            headword, reading, translation, audio = [decodeBase64(p) \
                for p in params.split(';')]

            self.emit(
                SIGNAL("vocabularyAdded(const QString &, const QString &, const QString &, const QString &)"),
                headword, reading, translation, audio)
        elif cmd.startswith('http://'):
            #os.spawnlp(os.P_NOWAIT, 'xdg-open', 'xdg-open', cmd)
            QDesktopServices.openUrl(url)
        else:
            print "Error", cmd

    def slotLookupClipboard(self):
        clipboardText = unicode(QApplication.clipboard().text(
            QtGui.QClipboard.Selection).simplified())

        # only search for limited text
        if clipboardText and (len(clipboardText) < 20):
            self.load(clipboardText)

    def slotLookupSelection(self):
        if self.selectedText():
            self.load(self.selectedText())

    def slotMiniMode(self, miniMode):
        self.miniMode = miniMode
        self.reload()

        self.emit(SIGNAL("modeChanged(bool)"), miniMode)

    def slotFind(self):
        if not self.findDialog:
            self.findDialog = KFindDialog(self, 0, self.findHistory)
            self.findDialog.setSupportsRegularExpressionFind(False)
            self.findDialog.setSupportsWholeWordsFind(False)
            self.findDialog.setHasCursor(False)

        # TODO
        #self.findDialog.setHasSelection(
            #self.selectedText() != '')
        if self.findDialog.exec_() != QtGui.QDialog.Accepted:
            return

        options = QWebPage.FindFlag(0)
        if self.findDialog.options() & KFind.CaseSensitive:
            options |= QWebPage.FindCaseSensitively
        if self.findDialog.options() & KFind.FindBackwards:
            options |= QWebPage.FindBackward
        # TODO
        #if not self.findDialog.options() & KFind.FromCursor:
            #self.triggerPageAction(
                #QWebPage.MoveToStartOfDocument)
        options |= QWebPage.FindWrapsAroundDocument

        self.doFind(options)

    def slotFindNext(self):
        if not self.findDialog or not self.findDialog.pattern():
            self.slotFind()
        else:
            options = QWebPage.FindFlag(0)
            if self.findDialog.options() & KFind.CaseSensitive:
                options |= QWebPage.FindCaseSensitively
            if self.findDialog.options() & KFind.FindBackwards:
                options |= QWebPage.FindBackward

            self.doFind(options)

    def slotFindPrev(self):
        if not self.findDialog or not self.findDialog.pattern():
            self.slotFind()
        else:
            options = QWebPage.FindFlag(0)
            if self.findDialog.options() & KFind.CaseSensitive:
                options |= QWebPage.FindCaseSensitively
            if not self.findDialog.options() & KFind.FindBackwards:
                options |= QWebPage.FindBackward

            self.doFind(options)

    def doFind(self, options):
        if not self.findText(self.findDialog.pattern(),
            options):
            if options & QWebPage.FindWrapsAroundDocument:
                KMessageBox.information(self,
                    i18n("No matches found for <strong>'%1'</strong>.",
                        self.findDialog.pattern()))
            else:
                if not options & QWebPage.FindBackward:
                    question = i18n('Continue from the beginning?')
                else:
                    question = i18n('Continue from the end?')
                if KMessageBox.questionYesNo(self,
                    i18n("No matches found for <strong>'%1'</strong>.",
                        self.findDialog.pattern()) \
                        + "\n\n" + question, i18n("Find"),
                        KStandardGuiItem.cont()) == KMessageBox.Yes:
                    options |= QWebPage.FindWrapsAroundDocument
                    if not self.findText(
                        self.findDialog.pattern(), options):
                        KMessageBox.information(self,
                            i18n("No matches found for <strong>'%1'</strong>.",
                                self.findDialog.pattern()))

    def slotForwardBackwardActivated(self, action):
        value, _ = action.data().toInt()
        self.history.setCurrent(value)

    def slotForwardAboutToShow(self):
        self._forwardAction.menu().clear()
        self._fillHistoryPopup(self._forwardAction.menu(), True)

    def slotBackAboutToShow(self):
        self._backwardAction.menu().clear()
        self._fillHistoryPopup(self._backwardAction.menu(), False)

    def _fillHistoryPopup(self, popup, forward):
        if forward:
            historyDict = self.history.forwardItems()
        else:
            historyDict = self.history.backItems()

        for title, idx in historyDict:
            title.replace("&", "&&")
            action = QAction(title, popup)
            action.setData(QVariant(idx))
            popup.addAction(action)

    def slotPrint(self):
        printer = QPrinter(QPrinter.HighResolution)

        dialog = QPrintDialog(printer, self)
        if dialog.exec_() == QtGui.QDialog.Accepted:
            self.print_(printer)

    def slotPageLoaded(self, ok):
        if self.history.current() in self.scrollValues:
            self.page().mainFrame().setScrollBarValue(Qt.Vertical,
                self.scrollValues[self.history.current()])
        if self.title() == 'One word a day':
            self.page().mainFrame().evaluateJavaScript(
                "setText('%s');" % i18n('The word:'))
            self.renderThread.enqueue(DictionaryView,
                'getRandomDictionaryEntry')

    def playCharString(self, path):
        if not hasPhononSupport:
            KMessageBox.information(self,
                i18n('Please install Phonon to play audio files.'))
            return

        if self.mediaObject == None:
            self.mediaObject = Phonon.MediaObject(self)
            audioOutput = Phonon.AudioOutput(Phonon.MusicCategory, self)
            Phonon.createPath(self.mediaObject, audioOutput)

        if self.mediaObject:
            self.mediaObject.setCurrentSource(Phonon.MediaSource(path))
            self.mediaObject.play()

        # reload page otherwise Qt will asume lokal link is still shown
        self.reload() # TODO is there a nice way around this without blanking the page?

    def getErrorPage(self):
        return '<html><head><title>Error</title>' \
            + '<link rel="StyleSheet" href="file://%s" type="text/css" />' \
                % self.styleFile \
            + '</head>' \
            + '<body class="error">' \
            + '<h2>%s</h2><span class="meta">%s</span>' \
                % (i18n("Error"), i18n('The given request was errorneous.')) \
            + '</body></html>'

    def getOneWordADayPage(self):
        return '<html><head><title>One word a day</title>' \
            + '<link rel="StyleSheet" href="file://%s" type="text/css" />' \
                % self.styleFile \
            + self.POLLY_CHANGE_TEXT_JAVASCRIPT \
            + '</head>' \
            + '<body class="wordaday">' \
            + '<object id="polly" data="file://%s"></object>' \
                % util.getData('eclectus_bigbuble.svg') \
            + '</body></html>'

    def getHelpPage(self):
        if self.dictionary:
            searchMessage = \
                i18n('Use <tt>?</tt> and <tt>*</tt> for fuzzy searching.')
        else:
            searchMessage = ''

        # examples
        key = (self.language, self.reading)
        if key in self.SEARCH_EXAMPLES:
            examples = []
            for example in self.SEARCH_EXAMPLES[key]:
                examples.append(
                    u'<li><a href="about:blank#lookup(%s)">%s</a></li>' \
                        % (encodeBase64(example), example))

            exampleMessage = '<p>%s <ul>%s</ul></p>' \
                % (i18n("Examples:"), ''.join(examples))
        else:
            exampleMessage = ''

        # about looking up selected text
        lookupShortcut = self._lookupClipboardAction.globalShortcut().toString(
            QtGui.QKeySequence.NativeText)
        if lookupShortcut:
            shortcutMessage = '<p>%s</p>' \
                % i18n(u"Use the dictionary together with other software by hitting <em>%1</em> on a selected item or enable <em>Auto-lookup</em> to automatically lookup selected text.",
                lookupShortcut)
        else:
            shortcutMessage = ''

        # TODO
            #+ '<object data="file://%s" height="170" width="325">' % imagePath \
            #+ 'Your browser does not support embedded svg.</object>'
            #+ '<img src="file://%s" align="right"/>' \
                #% util.getData('eclectus_big.png') \
        if self.language in self.WELCOME_TEXT:
            welcomeText = self.WELCOME_TEXT[self.language]
        else:
            welcomeText = i18n('Welcome')

        return '<html><head><title>Help</title>' \
            + '<link rel="StyleSheet" href="file://%s" type="text/css" />' \
                % self.styleFile \
            + self.POLLY_CHANGE_TEXT_JAVASCRIPT \
            + '</head>' \
            + u'<body class="help" onload="setText(\'%s\');">' % welcomeText \
            + '<object id="polly" data="file://%s"></object>' \
                % util.getData('eclectus_buble.svg') \
            + '<p>%s %s</p>' \
                % (i18n('Welcome to <em>Eclectus</em>. Search the dictionary by entering characters, their pronunciation or a translation.'),
                    searchMessage) \
            + exampleMessage + shortcutMessage \
            + '</body></html>'

    def slotHistoryActivated(self, pageName):
        pageName = unicode(pageName)
        if self.history.last():
            self.scrollValues[self.history.last()] \
                = self.page().mainFrame().scrollBarValue(Qt.Vertical)

        self.loadPage(pageName)

    def load(self, pageName):
        pageName = self.getPageName(unicode(pageName))
        if pageName != self.history.current():
            if self.history.current():
                self.scrollValues[self.history.current()] \
                    = self.page().mainFrame().scrollBarValue(Qt.Vertical)
            self.history.addItem(pageName)
            self.loadPage(pageName)

    def loadPage(self, pageName):
        assert type(pageName) in [type(u''), type('')]
        pageType, value = pageName.split(':', 1)

        if pageType == 'about':
            if value == 'help':
                self.setHtml(self.getHelpPage(), QUrl('file:///'))
            elif value == 'wordaday':
                self.setHtml(self.getOneWordADayPage(), QUrl('file:///'))
            else:
                self.setHtml(self.getErrorPage(), QUrl('file:///'))
        elif not self.isValidPageType(pageType) \
            or (pageType == 'character' and len(value) > 1) \
            or re.match('[\*\?]*$', value):
            self.setHtml(self.getErrorPage(), QUrl('file:///'))
        else:
            self.setHtml('')
            self.requestSections(pageType, value)

        self._forwardAction.setEnabled(self.history.canGoForward())
        self._backwardAction.setEnabled(self.history.canGoBack())
        self.emit(SIGNAL('pageChanged(const QString &)'), pageName)

    def requestSections(self, pageType, value):
        if self.miniMode:
            sections = self.DEFAULT_MINI_VIEW_SECTIONS[pageType]
        else:
            sections = self.DEFAULT_VIEW_SECTIONS[pageType]

        self.currentJobs = []
        for method in sections:
            if ((not self.dictionary.startswith('PSEUDO_')
                or not DictionaryView.needsDictionary(method))
                and method not in self.hiddenSections):

                if (method not in self.sectionContentVisible
                    or self.sectionContentVisible[method]):
                    # render only if visible
                    self.renderThread.enqueue(DictionaryView, method, value)
                    self.currentJobs.append((method, value))
                else:
                    self.currentJobs.append((method, None))

        self.setHtml(self.renderPage())

    def isValidPageType(self, pageType):
        if self.miniMode:
            return pageType in self.DEFAULT_MINI_VIEW_SECTIONS
        else:
            return pageType in self.DEFAULT_VIEW_SECTIONS

    def reload(self):
        if self.history.current():
            self.scrollValues[self.history.current()] \
                = self.page().mainFrame().scrollBarValue(Qt.Vertical)
            self.loadPage(self.history.current())

    def back(self):
        self._backwardAction.trigger()

    def forward(self, actionCollection):
        self._forwardAction.trigger()

    def getPageName(self, inputString):
        # strip of whitespaces and split into type and search string
        inputString = inputString.strip()
        matchObj = re.match('(\w+)\:(.*)$', inputString)
        if matchObj:
            pageType = matchObj.group(1)
            value = matchObj.group(2)
        elif self.hasNonChineseCharacter(inputString) \
            or inputString.find('*') != -1 or inputString.find('?') != -1:
            pageType = 'search'
            value = inputString
        elif len(inputString) == 1:
            pageType = 'character'
            value = inputString
        else:
            pageType = 'word'
            value = inputString
        if pageType in self.VIEW_ABBREVIATIONS:
            pageType = self.VIEW_ABBREVIATIONS[pageType]

        return pageType + ':' + value

    @staticmethod
    def hasNonChineseCharacter(string):
        """
        Simple function for telling if a non Chinese character is present.
        """
        for char in string:
            if getCJKScriptClass(char) != 'Han':
                return True
        return False

    def renderPage(self):
        htmlList = []

        for method, value in self.currentJobs:
            if value == None:
                # content hidden and not rendered
                htmlList.append(self.constructHeading(method,
                    unicode(self.SECTION_NAMES[method].toString())))
            else:
                if method in self.sectionContentVisible:
                    htmlList.append(self.constructHeading(method,
                        unicode(self.SECTION_NAMES[method].toString())))

                if self.renderThread.hasCachedContent(DictionaryView, method,
                    value):
                    content = self.renderThread.getCachedContent(
                        DictionaryView, method, value)
                    htmlList.append(unicode(content))

        return '<html><head><title>Dictionary</title>' \
            + '<link rel="StyleSheet" href="file://%s" type="text/css" />' \
                % self.styleFile \
            + '</head>' \
            + '<body class="dictionary">%s</body>' % '\n'.join(htmlList) \
            + '</html>'

    def constructHeading(self, tag, text):
        return '<a class="headingLink" href="#toggleVisibility(' + tag + ')">' \
            + '<h2>' + text + '</h2></a>'

    def writeSettings(self):
        if self.pluginConfig:
            self.pluginConfig.writeEntry("Dictionary hidden sections",
                ','.join(self.hiddenSections))

            if self.findDialog:
                self.pluginConfig.writeEntry("Dictionary find history",
                    self.findDialog.findHistory())
            else:
                self.pluginConfig.writeEntry("Dictionary find history",
                    self.findHistory)

            self.pluginConfig.writeEntry("Dictionary start page",
                self.startPage)
            if self.startPage == 'last':
                self.pluginConfig.writeEntry("Dictionary last page",
                    unicode(self.history.current()))
            else:
                self.pluginConfig.writeEntry("Dictionary last page", '')

            dictionaryView = self.renderThread.getObjectInstance(DictionaryView)
            for key, value in dictionaryView.settings().items():
                self.pluginConfig.writeEntry(key, unicode(value))

            self.lastReading[self.dictionary] = self.reading
            lastReadings = []
            for dictionary, reading in self.lastReading.items():
                lastReadings.append(':'.join([dictionary, reading]))
            self.pluginConfig.writeEntry("Last readings", lastReadings)

            self.lastLanguage[self.dictionary] = self.language
            lastLanguage = []
            for dictionary, language in self.lastLanguage.items():
                lastLanguage.append(':'.join([dictionary, language]))
            self.pluginConfig.writeEntry("Last languages", lastLanguage)

    def contentRendered(self, id, classObject, method, args, param, content):
        if classObject == DictionaryView \
            and args and (method, args[0]) in self.currentJobs:
            self.setHtml(self.renderPage())
        elif classObject == DictionaryView \
            and method == 'getRandomDictionaryEntry':
            if content and self.title() == 'One word a day':
                headword, _, _, _ = content[0]
                self.page().mainFrame().evaluateJavaScript(
                    "setText('%s'); setWordLink('%s');" \
                        % (headword, encodeBase64(headword)))
