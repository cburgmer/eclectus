#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Component chooser plugin for accessing characters by searching for their
components.

@todo Fix: Component view has buggy updates, lesser characters are highlighted than
    actually chosen

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

from PyQt4.QtCore import Qt, SIGNAL, QByteArray
from PyQt4.QtGui import QWidget, QIcon
from PyQt4.QtWebKit import QWebPage

from PyKDE4.kdeui import KIcon
from PyKDE4.kdecore import i18n

from eclectusqt.forms import ComponentPageUI
from eclectusqt import util

from libeclectus import characterinfo
from libeclectus import htmlview

class ComponentPage(QWidget, ComponentPageUI.Ui_Form):
    def __init__(self, mainWindow, renderThread, pluginConfig=None):
        QWidget.__init__(self, mainWindow)
        self.renderThread = renderThread
        self.pluginConfig = pluginConfig

        # set up UI
        self.setupUi(self)

        if self.pluginConfig:
            self.includeSimilar = self.pluginConfig.readEntry(
                "Component include similar", str(True)) != "False"
            self.includeVariants = self.pluginConfig.readEntry(
                "Component include variants", str(True)) != "False"

            splitterState = self.pluginConfig.readEntry("Component splitter",
                "").toAscii()
            self.componentSplitter.restoreState(QByteArray.fromBase64(
                splitterState))
        else:
            self.includeSimilar = True
            self.includeVariants = True

        self.includeSimilarButton.setChecked(self.includeSimilar)
        self.includeVariantsButton.setChecked(self.includeVariants)

        self.componentViewScroll = 0
        self.selectedComponents = []
        self.currentLanguage = None

        # connect to main window
        self.connect(mainWindow, SIGNAL("writeSettings()"),
            self.writeSettings)

        self.connect(self.renderThread, SIGNAL("jobFinished"),
            self.contentRendered)
        self.connect(self.renderThread, SIGNAL("objectCreated"),
            self.objectCreated)

        # connect to the widgets
        self.connect(self.includeVariantsButton, SIGNAL("clicked(bool)"),
            self.componentIncludeVariants)
        self.connect(self.includeSimilarButton, SIGNAL("clicked(bool)"),
            self.componentIncludeSimilar)

        self.connect(self.componentView, SIGNAL("linkClicked(const QUrl &)"),
            self.componentClicked)
        self.connect(self.componentView, SIGNAL("loadFinished(bool)"),
            self.componentViewLoaded)
        self.connect(self.componentResultView,
            SIGNAL("linkClicked(const QUrl &)"), self.componentResultClicked)
        self.connect(self.componentEdit,
            SIGNAL("textChanged(const QString &)"),
            self.componentEditChanged)

        self.componentView.page().setLinkDelegationPolicy(
            QWebPage.DelegateAllLinks)
        self.componentResultView.page().setLinkDelegationPolicy(
            QWebPage.DelegateAllLinks)

        self.initialised = False

    def showEvent(self, event):
        if not self.initialised:
            self.initialised = True
            self.includeSimilarButton.setIcon(
                QIcon(util.getIcon('similarforms.png')))
            self.includeVariantsButton.setIcon(
                QIcon(util.getIcon('radicalvariant.png')))

            id = self.renderThread.enqueue(htmlview.HtmlView,
                'getComponentSearchTable', components=[],
                includeEquivalentRadicalForms=self.includeVariants,
                includeSimilarCharacters=self.includeSimilar)
            self.checkForJob(id, 'getComponentSearchTable')

            self.componentView.setHtml(i18n('Loading...'))
            self.componentResultView.setHtml(i18n('Select components above'))

        QWidget.showEvent(self, event)

    def componentIncludeVariants(self, show):
        self.includeVariants = show
        self.updateComponentView()

    def componentIncludeSimilar(self, show):
        self.includeSimilar = show
        self.updateComponentView()

    def componentViewLoaded(self, ok):
        self.componentView.page().mainFrame().setScrollBarValue(Qt.Vertical,
            self.componentViewScroll)

    def componentResultClicked(self, url):
        cmd = unicode(url.toString()).replace('about:blank#', '')
        if cmd.startswith('lookup'):
            char = util.decodeBase64(
                re.match('lookup\(([^\)]+)\)', cmd).group(1))
            self.emit(SIGNAL('inputReceived(const QString &)'), char)

    def componentClicked(self, url):
        self.clearOldSearchJobs()

        cmd = unicode(url.toString()).replace('about:blank#', '')
        if cmd.startswith('component'):
            char = util.decodeBase64(
                re.match('component\(([^\)]+)\)', cmd).group(1))

            if char in self.selectedComponents:
                self.selectedComponents.remove(char)
            else:
                # TODO sort components, to optimize caching
                self.selectedComponents.append(char)

        self.componentEdit.setText(''.join(self.selectedComponents))
        self.updateComponentView()

    def componentEditChanged(self, text):
        components = list(unicode(text))
        if self.selectedComponents != components:
            self.clearOldSearchJobs()

            # preliminary save until the worker thread updates it
            # TODO sort components, to optimize caching
            self.selectedComponents = components

            if self.selectedComponents:
                # first turn characters into radical forms
                id = self.renderThread.enqueue(characterinfo.CharacterInfo,
                    'preferRadicalFormForCharacter',
                    self.selectedComponents)
                self.checkForJob(id, 'preferRadicalFormForCharacter')

            self.updateComponentView()

    def updateComponentView(self):
        # update component view
        self.componentViewScroll \
            = self.componentView.page().mainFrame().scrollBarValue(Qt.Vertical)
        id = self.renderThread.enqueue(htmlview.HtmlView,
            'getComponentSearchTable', components=self.selectedComponents,
            includeEquivalentRadicalForms=self.includeVariants,
            includeSimilarCharacters=self.includeSimilar)
        self.checkForJob(id, 'getComponentSearchTable')

        # update component result view
        if self.selectedComponents:
            id = self.renderThread.enqueue(htmlview.HtmlView,
                'getComponentSearchResult', components=self.selectedComponents,
                includeEquivalentRadicalForms=self.includeVariants,
                includeSimilarCharacters=self.includeSimilar)
            self.checkForJob(id, 'getComponentSearchResult')
        else:
            self.componentResultLabel.setText(i18n("Results:"))
            self.componentResultView.setHtml('')

    def writeSettings(self):
        if self.pluginConfig:
            self.pluginConfig.writeEntry("Component splitter",
                QByteArray.toBase64(self.componentSplitter.saveState()))
            self.pluginConfig.writeEntry("Component include similar",
                str(self.includeSimilar))
            self.pluginConfig.writeEntry("Component include variants",
                str(self.includeVariants))

    def clearOldSearchJobs(self):
        self.renderThread.dequeueMethod(characterinfo.CharacterInfo,
            'preferRadicalFormForCharacter')
        self.renderThread.dequeueMethod(htmlview.HtmlView,
            'getComponentSearchTable')
        self.renderThread.dequeueMethod(htmlview.HtmlView,
            'getComponentSearchResult')

    def checkForJob(self, id, method):
        """
        Signal might be emitted before actual job id is returned. This message
        serves to check for the job being in the cache.
        """
        if self.renderThread.hasCachedContentForId(id):
            self.doJob(id, method, self.renderThread.getCachedContentForId(id))

    def contentRendered(self, id, classObject, method, args, param, content):
        if classObject == htmlview.HtmlView:
            self.doJob(id, method, content)

    def doJob(self, id, method, content):
        if method == 'getComponentSearchTable':
            self.componentView.setHtml('<html><head><title>Components</title>' \
                + '<link rel="StyleSheet" href="file://%s" type="text/css" />' \
                    % util.getData('style.css')
                + '</head>' \
                + '<body>%s</body>' % content \
                + '</html>')
        elif method == 'getComponentSearchResult':
            htmlCode, count = content
            self.componentResultView.setHtml(
                '<html><head><title>Results</title>' \
                + '<link rel="StyleSheet" href="file://%s" type="text/css" />' \
                    % util.getData('style.css')
                + '</head>' \
                + '<body>%s</body>' % htmlCode \
                + '</html>')
            self.componentResultLabel.setText(i18n("%1 Results:", count))
        elif method == 'preferRadicalFormForCharacter':
            # TODO sort components, to optimize caching
            self.selectedComponents = content[:]
            self.componentEdit.setText(''.join(self.selectedComponents))
            self.updateComponentView()

    def reload(self):
        self.clearOldSearchJobs()

        if self.selectedComponents:
            id = self.renderThread.enqueue(characterinfo.CharacterInfo,
                'preferRadicalFormForCharacter', self.selectedComponents)
            self.checkForJob(id, 'preferRadicalFormForCharacter')

            id = self.renderThread.enqueue(htmlview.HtmlView,
                'getComponentSearchResult', components=self.selectedComponents,
                includeEquivalentRadicalForms=self.includeVariants,
                includeSimilarCharacters=self.includeSimilar)
            self.checkForJob(id, 'getComponentSearchResult')
        else:
            self.componentResultLabel.setText(i18n("Results:"))
            self.componentResultView.setHtml('')

        id = self.renderThread.enqueue(htmlview.HtmlView,
            'getComponentSearchTable', components=self.selectedComponents,
            includeEquivalentRadicalForms=self.includeVariants,
            includeSimilarCharacters=self.includeSimilar)
        self.checkForJob(id, 'getComponentSearchTable')

    def objectCreated(self, id, classObject):
        if classObject == characterinfo.CharacterInfo:
            charInfo = self.renderThread.getObjectInstance(
                characterinfo.CharacterInfo)
            if not self.currentLanguage \
                or self.currentLanguage != charInfo.language:
                self.currentLanguage = charInfo.language

                self.reload()
