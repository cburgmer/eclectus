#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Handwriting chooser plugin using the Tegaki/Tomoe handwriting recognition
engine.

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

import os
import re

from PyQt4.QtCore import SIGNAL, QTimer
from PyQt4.QtGui import QWidget
from PyQt4.QtWebKit import QWebPage

from PyKDE4.kdeui import KIcon
from PyKDE4.kdecore import i18n

from eclectusqt.forms import HandwritingPageUI
from eclectusqt import util

from libeclectus.chardb import CharacterDB
from libeclectus.util import encodeBase64, decodeBase64

tomoeDictionaryPath = "/usr/local/share/tomoe/recognizer/"

class HandwritingPage(QWidget, HandwritingPageUI.Ui_Form):
    DEFAULT_MAXIMUM_FIELD_SIZE = 200
    DEFAULT_MAXIMUM_RESULTS = 20

    WRITING_MODELS = {
        'ja': {'tomoe': {'dictionary': os.path.join(tomoeDictionaryPath,
            'handwriting-ja.xml')},
            'tegaki': {'recognizer': 'zinnia', 'model': 'Japanese'}},
        'zh-Hans': {'tomoe': {'dictionary': os.path.join(tomoeDictionaryPath,
            'handwriting-zh_CN.xml')},
            'tegaki': {'recognizer': 'zinnia', 'model': 'Simplified Chinese'}},
        'zh-Hant': {
            'tegaki': {'recognizer': 'zinnia', 'model': 'Traditional Chinese'}},
        'zh': {'fallback': {'language': 'zh-Hans'}},
        'zh-cmn-Hans': {'fallback': {'language': 'zh-Hans'}},
        'zh-cmn-Hant': {'fallback': {'language': 'zh-Hant'}},
        'zh-yue': {'fallback': {'language': 'zh-Hant'}},
        'zh-yue-Hans': {'fallback': {'language': 'zh-Hans'}},
        'zh-yue-Hant': {'fallback': {'language': 'zh-Hant'}},
        }

    def __init__(self, mainWindow, renderThread, pluginConfig=None):
        QWidget.__init__(self, mainWindow)
        self.mainWindow = mainWindow
        self.renderThread = renderThread
        self.pluginConfig = pluginConfig

        self.databaseUrl = None
        if self.pluginConfig:
            self.maximumSize = util.readConfigInt(self.pluginConfig,
                "Handwriting maximum field size",
                HandwritingPage.DEFAULT_MAXIMUM_FIELD_SIZE)
            self.maximumResults = util.readConfigInt(self.pluginConfig,
                "Handwriting maximum results",
                HandwritingPage.DEFAULT_MAXIMUM_RESULTS)
            self.databaseUrl = util.readConfigString(self.pluginConfig,
                "Update database url", None)
        else:
            self.maximumSize = HandwritingPage.DEFAULT_MAXIMUM_FIELD_SIZE
            self.maximumResults = HandwritingPage.DEFAULT_MAXIMUM_RESULTS

        if not self.databaseUrl:
            self.databaseUrl = unicode('sqlite:///'
                + util.getLocalData('dictionaries.db'))

        # set up UI
        self.setupUi(self)

        # connect to main window
        self.connect(self.mainWindow, SIGNAL("settingsChanged()"),
            self.slotSettingsChanged)
        self.connect(self.mainWindow, SIGNAL("writeSettings()"),
            self.writeSettings)

        self.connect(self.renderThread, SIGNAL("jobFinished"),
            self.contentRendered)

        self.handwritingView.setMaximumSize(self.maximumSize)

        # connect to the widgets
        self.connect(self.handwritingView, SIGNAL("updated()"),
            self.strokeInputUpdated)
        self.connect(self.handwritingResultView,
            SIGNAL("linkClicked(const QUrl &)"), self.handwritingResultClicked)
        self.handwritingResultView.page().setLinkDelegationPolicy(
            QWebPage.DelegateAllLinks)

        # add connections for clearing stroke input
        self.connect(self.clearButton, SIGNAL("clicked()"),
            self.handwritingView.clear)
        self.connect(self.backButton, SIGNAL("clicked()"),
            self.handwritingView.remove_last_stroke)

        self.clearButton.setIcon(KIcon('edit-clear'))
        self.backButton.setIcon(KIcon('edit-undo'))

        self.language = None
        self.characterDomain = None
        self.initialised = False

    def showEvent(self, event):
        if not self.initialised:
            self.initialised = True

            self.slotSettingsChanged()

            if not self.handwritingView.recognizerAvailable():
                self.handwritingResultView.setHtml(
                    i18n('No recognizer installed.'))
                self.handwritingResultView.setEnabled(False)
                self.handwritingView.setEnabled(False)
                self.clearButton.setEnabled(False)
                self.backButton.setEnabled(False)
            else:
                QTimer.singleShot(10, self._setDictionary)

        QWidget.showEvent(self, event)

    def strokeInputUpdated(self):
        self._setResultView()

    def handwritingResultClicked(self, url):
        cmd = unicode(url.toString()).replace('about:blank#', '')
        if cmd.startswith('lookup'):
            inputString = re.match('lookup\(([^\)]+)\)', cmd).group(1)
            self.emit(SIGNAL('inputReceived(const QString &)'),
                decodeBase64(inputString))

    def writeSettings(self):
        if self.pluginConfig:
            self.pluginConfig.writeEntry("Handwriting maximum field size",
                str(self.maximumSize))
            self.pluginConfig.writeEntry("Handwriting maximum results",
                str(self.maximumResults))

    def slotSettingsChanged(self):
        if not self.initialised:
            return

        settings = self.mainWindow.settings()

        language = settings.get('language', 'zh-cmn-Hans')
        characterDomain = settings.get('characterDomain', 'Unicode')

        if self.language != language or self.characterDomain != characterDomain:
            self.renderThread.setCachedObject(CharacterDB,
                databaseUrl=self.databaseUrl, language=language,
                characterDomain=characterDomain)

            if self.language != language:
                self._setDictionary()
            if self.characterDomain != characterDomain:
                self._setResultView()

            self.language = language
            self.characterDomain = characterDomain

    def _setDictionary(self):
        errorDisplayed = False
        if self.language in self.WRITING_MODELS:
            settings = self.WRITING_MODELS[self.language]
        else:
            # choose random language
            fallbackLanguage = sorted(self.WRITING_MODELS.keys())[0]
            settings = {'fallback': {'language': fallbackLanguage},
                'noisy': True}

        if 'fallback' in settings:
            if 'noisy' in settings['fallback'] \
                and settings['fallback']['noisy']:
                self.handwritingResultView.setHtml(
                    i18n('Sorry, no stroke data currently exists for this locale, falling back to simplified Chinese.'))
                errorDisplayed = True
            settings = self.WRITING_MODELS[settings['fallback']['language']]

        self.handwritingView.setDictionary(settings)

        if not errorDisplayed and not self.handwritingView.strokeCount():
            self.handwritingResultView.setHtml(
                i18n('Draw a character above'))

    def _setResultView(self):
        if not self.handwritingView.strokeCount():
            self.handwritingResultView.setHtml('')
        else:
            resultList = self.handwritingView.results(self.maximumResults)
            chars = [char for char, _ in resultList]

            # TODO weired Tomoe response
            weiredRes = [char for char, _ in resultList if len(char) != 1]
            if weiredRes:
                print "Warning: illegal return from recognizer: ", repr(weiredRes)
                chars = [char for char in chars if len(char) == 1]

            self.renderThread.enqueue(CharacterDB, 'filterDomainCharacters',
                chars)

    def contentRendered(self, id, classObject, method, args, param, content):
        if classObject == CharacterDB:
            if method == 'filterDomainCharacters':
                chars = content

                # render page
                if chars:
                    charLinks = []
                    for char in chars:
                        charLinks.append(
                            '<a class="character" href="#lookup(%s)">%s</a>' \
                                % (encodeBase64(char), char))
                    html = '<span class="character">%s</span>' \
                        % ' '.join(charLinks)
                else:
                    html = '<span class="meta">%s</span>' % unicode(
                        i18n('No results for the selected character domain'))

                self.handwritingResultView.setHtml(
                    '<html><head><title>Results</title>' \
                    + '<link rel="StyleSheet" href="%s" type="text/css" />' \
                        % ('file://' + util.getData('style.css'))
                    + '</head>' \
                    + '<body>%s</body>' % html \
                    + '</html>')
