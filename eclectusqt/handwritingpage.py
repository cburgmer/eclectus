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

from libeclectus import characterinfo
from libeclectus.util import encodeBase64, decodeBase64

tomoeDictionaryPath = "/usr/local/share/tomoe/recognizer/"

class HandwritingPage(QWidget, HandwritingPageUI.Ui_Form):
    DEFAULT_MAXIMUM_FIELD_SIZE = 200
    DEFAULT_MAXIMUM_RESULTS = 20

    WRITING_MODELS = {
        'ja': {'tomoe': {'dictionary': os.path.join(tomoeDictionaryPath,
            'handwriting-ja.xml')}},
        'zh-Hans': {'tomoe': {'dictionary': os.path.join(tomoeDictionaryPath,
            'handwriting-zh_CN.xml')},
            'tegaki': {'recognizer': 'zinnia', 'model': 'Simplified Chinese'}},
        'zh': {'fallback': {'language': 'zh-Hans'}},
        'zh-cmn-Hans': {'fallback': {'language': 'zh-Hans'}},
        'zh-cmn-Hant': {'fallback': {'language': 'zh-Hans', 'noisy': True}},
        'zh-Hant': {'fallback': {'language': 'zh-Hans', 'noisy': True}},
        'zh-yue': {'fallback': {'language': 'zh-Hans', 'noisy': True}},
        'zh-yue-Hans': {'fallback': {'language': 'zh-Hans'}},
        'zh-yue-Hant': {'fallback': {'language': 'zh-Hans', 'noisy': True}},
        }

    def __init__(self, mainWindow, renderThread, pluginConfig=None):
        QWidget.__init__(self, mainWindow)
        self.renderThread = renderThread
        self.pluginConfig = pluginConfig

        if self.pluginConfig:
            self.maximumSize = util.readConfigInt(self.pluginConfig,
                "Handwriting maximum field size",
		HandwritingPage.DEFAULT_MAXIMUM_FIELD_SIZE)
            self.maximumResults = util.readConfigInt(self.pluginConfig,
                "Handwriting maximum results",
                HandwritingPage.DEFAULT_MAXIMUM_RESULTS)
        else:
            self.maximumSize = HandwritingPage.DEFAULT_MAXIMUM_FIELD_SIZE
            self.maximumResults = HandwritingPage.DEFAULT_MAXIMUM_RESULTS

        # set up UI
        self.setupUi(self)

        # connect to main window
        self.connect(mainWindow, SIGNAL("writeSettings()"),
            self.writeSettings)

        self.connect(self.renderThread, SIGNAL("jobFinished"),
            self.contentRendered)
        self.connect(self.renderThread, SIGNAL("objectCreated"),
            self.objectCreated)

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

        self.currentLanguage = None
        self.initialised = False

    def showEvent(self, event):
        if not self.initialised:
            self.initialised = True

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

    def objectCreated(self, id, classObject):
        if not self.initialised:
            return
        if classObject == characterinfo.CharacterInfo:
            charInfo = self.renderThread.getObjectInstance(
                characterinfo.CharacterInfo)
            if not self.currentLanguage \
                or self.currentLanguage != charInfo.language:
                self._setDictionary()
            else:
                self._setResultView()

    def _setDictionary(self):
        errorDisplayed = False
        charInfo = self.renderThread.getObjectInstance(
            characterinfo.CharacterInfo)
        self.currentLanguage = charInfo.language

        if self.currentLanguage in self.WRITING_MODELS:
            settings = self.WRITING_MODELS[self.currentLanguage]
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

        if not errorDisplayed:
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

            self.renderThread.enqueue(characterinfo.CharacterInfo,
                'filterDomainCharacters', chars)

    def contentRendered(self, id, classObject, method, args, param, content):
        if classObject == characterinfo.CharacterInfo:
            if method == 'filterDomainCharacters':
                chars = content

                # render page
                if chars:
                    charLinks = []
                    for char in chars:
                        charLinks.append(
                            '<a class="character" href="#lookup(%s)">%s</a>' \
                                % (encodeBase64(char), char))
                    html = ' '.join(charLinks)
                else:
                    html = '<p class="meta">%s</p>' % unicode(
                        i18n('No results for the selected character domain'))

                self.handwritingResultView.setHtml(
                    '<html><head><title>Results</title>' \
                    + '<link rel="StyleSheet" href="file://%s" type="text/css" />' \
                        % util.getData('style.css')
                    + '</head>' \
                    + '<body><span class="character">%s</span></body>' % html \
                    + '</html>')
