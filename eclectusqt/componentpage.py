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

from libeclectus.componentview import ComponentView
from libeclectus.util import decodeBase64

class ComponentPage(QWidget, ComponentPageUI.Ui_Form):
    def __init__(self, mainWindow, renderThread, pluginConfig=None):
        QWidget.__init__(self, mainWindow)
        self.mainWindow = mainWindow
        self.renderThread = renderThread
        self.pluginConfig = pluginConfig

        # set up UI
        self.setupUi(self)

        self.databaseUrl = None
        if self.pluginConfig:
            self.includeSimilar = util.readConfigString(self.pluginConfig,
                "Component include similar", str(True)) != "False"
            self.includeVariants = util.readConfigString(self.pluginConfig, 
                "Component include variants", str(True)) != "False"

            self.databaseUrl = util.readConfigString(self.pluginConfig,
                "Update database url", None)

            splitterState = util.readConfigString(self.pluginConfig,
                "Component splitter", "")
            self.componentSplitter.restoreState(QByteArray.fromBase64(
                str(splitterState)))
        else:
            self.includeSimilar = True
            self.includeVariants = True

        if not self.databaseUrl:
            self.databaseUrl = unicode('sqlite:///'
                + util.getLocalData('dictionaries.db'))

        self.includeSimilarButton.setChecked(self.includeSimilar)
        self.includeVariantsButton.setChecked(self.includeVariants)

        self.componentViewScroll = 0
        self.selectedComponents = []
        self.language = None
        self.characterDomain = None

        # connect to main window
        self.connect(self.mainWindow, SIGNAL("settingsChanged()"),
            self.slotSettingsChanged)
        self.connect(self.mainWindow, SIGNAL("writeSettings()"),
            self.writeSettings)

        self.connect(self.renderThread, SIGNAL("jobFinished"),
            self.contentRendered)

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

            self.slotSettingsChanged()

            id = self.renderThread.enqueue(ComponentView,
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
            char = decodeBase64(re.match('lookup\(([^\)]+)\)', cmd).group(1))
            self.emit(SIGNAL('inputReceived(const QString &)'), char)

    def componentClicked(self, url):
        self.clearOldSearchJobs()

        cmd = unicode(url.toString()).replace('about:blank#', '')
        if cmd.startswith('component'):
            char = decodeBase64(re.match('component\(([^\)]+)\)', cmd).group(1))

            # map forms to reqular equivalent ones
            char = self._equivalentFormsMap.get(char, char)

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

            # TODO sort components, to optimize caching
            self.selectedComponents = components

            self.updateComponentView()

    def updateComponentView(self):
        # update component view
        self.componentViewScroll \
            = self.componentView.page().mainFrame().scrollBarValue(Qt.Vertical)
        id = self.renderThread.enqueue(ComponentView,
            'getComponentSearchTable', components=self.selectedComponents,
            includeEquivalentRadicalForms=self.includeVariants,
            includeSimilarCharacters=self.includeSimilar)
        self.checkForJob(id, 'getComponentSearchTable')

        # update component result view
        if self.selectedComponents:
            id = self.renderThread.enqueue(ComponentView,
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
        self.renderThread.dequeueMethod(ComponentView,
            'getComponentSearchTable')
        self.renderThread.dequeueMethod(ComponentView,
            'getComponentSearchResult')

    def checkForJob(self, id, method):
        """
        Signal might be emitted before actual job id is returned. This message
        serves to check for the job being in the cache.
        """
        if self.renderThread.hasCachedContentForId(id):
            self.doJob(id, method, self.renderThread.getCachedContentForId(id))

    def contentRendered(self, id, classObject, method, args, param, content):
        if classObject == ComponentView:
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

    def reload(self):
        self.clearOldSearchJobs()

        if self.selectedComponents:
            id = self.renderThread.enqueue(ComponentView,
                'getComponentSearchResult', components=self.selectedComponents,
                includeEquivalentRadicalForms=self.includeVariants,
                includeSimilarCharacters=self.includeSimilar)
            self.checkForJob(id, 'getComponentSearchResult')
        else:
            self.componentResultLabel.setText(i18n("Results:"))
            self.componentResultView.setHtml('')

        id = self.renderThread.enqueue(ComponentView,
            'getComponentSearchTable', components=self.selectedComponents,
            includeEquivalentRadicalForms=self.includeVariants,
            includeSimilarCharacters=self.includeSimilar)
        self.checkForJob(id, 'getComponentSearchTable')

    def slotSettingsChanged(self):
        if not self.initialised:
            return

        settings = self.mainWindow.settings()

        language = settings.get('language', 'zh-cmn-Hans')
        characterDomain = settings.get('characterDomain', 'Unicode')

        if self.language != language or self.characterDomain != characterDomain:
            self.renderThread.setCachedObject(ComponentView,
                databaseUrl=self.databaseUrl, language=language,
                characterDomain=characterDomain)

            self.language = language
            self.characterDomain = characterDomain

            componentView = self.renderThread.getObjectInstance(ComponentView)
            self._equivalentFormsMap \
                = componentView.radicalFormEquivalentCharacterMap

            self.reload()
