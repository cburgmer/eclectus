#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Radical plugin for accessing characters by their radical.

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

from PyQt4.QtCore import Qt, SIGNAL, QUrl
from PyQt4.QtGui import QWidget

from PyKDE4.kdeui import KIcon
from PyKDE4.kdecore import i18n

from eclectusqt.forms import RadicalPageUI
from eclectusqt import util

from libeclectus import htmlview
from libeclectus import characterinfo

class RadicalPage(QWidget, RadicalPageUI.Ui_Form):
    SELECTED_RADICAL_CSS_CLASS = 'selectedRadicalEntry'

    CLICKABLE_ROW_JAVASCRIPT = """
//function _go(url) { document.location = url; }
_go = alert;
function curry (fn) {
    var args = [];
    for (var i=2, len = arguments.length; i <len; ++i) {
        args.push(arguments[i]);
    };
    return function() {
            fn.apply(window, args);
    };
}
String.prototype.startsWith = function(str) {return (this.match("^"+str)==str)}
gotoRadical = function(radical) {_go("navigate:radical(" + radical + ")"); };

trs = document.getElementsByTagName("tr");
for(var i = 0; i < trs.length; i++)
{
    var elem = trs[i];
    if (elem.id.startsWith("radical"))
    {
        radicalId = elem.id.replace("radical", "");
        elem.onclick = curry(gotoRadical, window, radicalId);
    }
}
""" # TODO use _go function instead of workaround with "alert"

    def __init__(self, mainWindow, renderThread, pluginConfig=None):
        QWidget.__init__(self, mainWindow)
        self.renderThread = renderThread
        self.pluginConfig = pluginConfig

        # set up UI
        self.setupUi(self)

        self.radicalView.setPage(util.HandyWebpage(self))

        if self.pluginConfig:
            self.includeAllRadicals = self.pluginConfig.readEntry(
                "Radical include all", str(True)) != "False"
        else:
            self.includeAllRadicals = True

        self.nonKangxiRadicalButton.setChecked(self.includeAllRadicals)
        self.radicalOptions.setCurrentIndex(0)

        self.strokeCountRegex = re.compile(r'\s*(\d+)\s*$')
        self.radicalIndexRegex = re.compile(r'\s*[#RrIi](\d*)\s*$')

        self.radicalTableViewScroll = 0
        self.currentRadicalIndex = None
        self.currentSelectedEntry = None
        self.radicalEntryDict = None
        self.currentLocale = None

        # connect to main window
        self.connect(mainWindow, SIGNAL("writeSettings()"),
            self.writeSettings)

        self.connect(self.renderThread, SIGNAL("jobFinished"),
            self.contentRendered)
        self.connect(self.renderThread, SIGNAL("objectCreated"),
            self.objectCreated)

        # connect to the radical table widgets
        self.connect(self.gotoEdit, SIGNAL("textChanged(const QString &)"),
            self.gotoEditChanged)
        self.connect(self.gotoEdit, SIGNAL("returnPressed()"),
            self.lookupSelectedRadical)
        self.connect(self.gotoEdit, SIGNAL("clearButtonClicked()"),
            self.gotoEditCleared)
        self.connect(self.gotoNextButton, SIGNAL("clicked(bool)"),
            self.gotoNextClicked)
        self.connect(self.gotoButton, SIGNAL("clicked(bool)"),
            lambda x: self.lookupSelectedRadical())
        # connect to the character table widgets
        self.connect(self.toRadicalTableButton, SIGNAL("clicked(bool)"),
            self.showRadicalTable)
        self.connect(self.nonKangxiRadicalButton, SIGNAL("clicked(bool)"),
            self.toggleIncludeAllRadicals)

        self.connect(self.radicalView.page(),
            SIGNAL("linkClicked(const QUrl &)"), self.radicalClicked)
        self.connect(self.radicalView, SIGNAL("loadFinished(bool)"),
            self.radicalViewLoaded)

        self.gotoNextButton.setEnabled(False)
        self.gotoButton.setEnabled(False)
        self.groupRadicalFormsButton.setVisible(False) # TODO implement functionality

        self.initialised = False
        self.maximumStrokeCount = None

    def showEvent(self, event):
        if not self.initialised:
            self.initialised = True
            self.gotoNextButton.setIcon(KIcon('go-down-search'))
            self.gotoButton.setIcon(KIcon('go-next'))
            self.toRadicalTableButton.setIcon(KIcon('go-previous'))
            self.nonKangxiRadicalButton.setIcon(KIcon('')) # TODO
            self.groupRadicalFormsButton.setIcon(KIcon('format-list-ordered'))

            self.radicalView.setHtml(i18n('Loading...'))
            self.renderThread.enqueue(htmlview.HtmlView, 'getRadicalTable')
            self.renderThread.enqueue(characterinfo.CharacterInfo,
                'getRadicalForms')

        QWidget.showEvent(self, event)

    def showRadicalTable(self, show=None):
        self.renderThread.enqueue(htmlview.HtmlView, 'getRadicalTable')
        self.radicalOptions.setCurrentIndex(0)
        self.gotoEdit.setFocus()

    def showRadicalCharacters(self, radicalIndex):
        self.currentRadicalIndex = radicalIndex

        self.radicalTableViewScroll \
            = self.radicalView.page().mainFrame().scrollBarValue(
                Qt.Vertical)
        self.radicalView.setHtml('')
        self.radicalOptions.setCurrentIndex(1)
        # save scroll value of the character view in radical table
        self.radicalCharactersViewRelativeScroll = 0

        self.renderThread.enqueue(htmlview.HtmlView, 'getCharacterForRadical',
            radicalIndex=self.currentRadicalIndex,
            includeAllComponents=self.includeAllRadicals)

        self.radicalView.setFocus()

    def toggleIncludeAllRadicals(self, include):
        self.includeAllRadicals = include
        # save rel. position of scroll bar
        frame = self.radicalView.page().mainFrame()
        maxScroll = frame.scrollBarMaximum(Qt.Vertical)
        if maxScroll > 0:
            self.radicalCharactersViewRelativeScroll \
                = 1.0 * frame.scrollBarValue(Qt.Vertical) / maxScroll
        else:
            self.radicalCharactersViewRelativeScroll = 0
        self.renderThread.enqueue(htmlview.HtmlView, 'getCharacterForRadical',
            radicalIndex=self.currentRadicalIndex,
            includeAllComponents=self.includeAllRadicals)

    def radicalViewLoaded(self, ok):
        if self.radicalView.title() == 'Radicals':
            # reselect entry
            if self.currentSelectedEntry:
                radicalIndex = self.currentSelectedEntry
                self.currentSelectedEntry = None
                self.selectRadicalEntry(radicalIndex)
            self.radicalView.page().mainFrame().setScrollBarValue(Qt.Vertical,
                self.radicalTableViewScroll)
        else:
            # set absolute position of scroll bar
            frame = self.radicalView.page().mainFrame()
            maxScroll = frame.scrollBarMaximum(Qt.Vertical)
            if maxScroll > 0 and self.radicalCharactersViewRelativeScroll:
                absScroll = self.radicalCharactersViewRelativeScroll * maxScroll
                frame.setScrollBarValue(Qt.Vertical, int(absScroll))

    def radicalClicked(self, url):
        cmd = unicode(url.toString()).replace('about:blank#', '')

        if cmd.startswith('radical'):
            radicalIndex = int(re.match('radical\(([^\)]+)\)', cmd).group(1))
            self.currentSelectedEntry = radicalIndex
            self.showRadicalCharacters(radicalIndex)
        elif cmd.startswith('lookup'):
            inputString = re.match('lookup\(([^\)]+)\)', cmd).group(1)
            self.emit(SIGNAL('inputReceived(const QString &)'),
                util.decodeBase64(inputString))

    def gotoEditChanged(self, inputString):
        self.gotoNextButton.setEnabled(False)
        self.gotoEdit.setStyleSheet("")

        inputString = unicode(inputString).lower()
        if not inputString:
            self.gotoEditCleared()
            return

        # check for stroke count
        matchObj = self.strokeCountRegex.match(inputString)
        if matchObj:
            try:
                strokeCount = int(matchObj.group(1))
                if not self.maximumStrokeCount \
                    or strokeCount <= self.maximumStrokeCount:
                    script = 'document.getElementById("' + 'strokecount' \
                        + str(strokeCount) + '").scrollIntoView();'
                    self.radicalView.page().mainFrame().evaluateJavaScript(
                        script)
                    return
            except ValueError:
                pass

        # check for radical index preceded by #
        matchObj = self.radicalIndexRegex.match(inputString)
        radicalIndex = None
        if matchObj:
            if matchObj.group(1):
                radicalIndex = int(matchObj.group(1))
                # select entry
                self.selectRadicalEntry(radicalIndex)
            return

        # check for radical form, name...
        if self.radicalEntryDict:
            for radicalIndex in range(1,
                max(self.radicalEntryDict.keys()) + 1):
                chars, meaning = self.radicalEntryDict[radicalIndex]
                if (meaning and meaning.lower().find(inputString) >= 0) \
                    or inputString in chars:
                    # select entry
                    self.selectRadicalEntry(radicalIndex)
                    self.gotoNextButton.setEnabled(True)
                    return

        # nothing found
        self.selectRadicalEntry(None)
        self.gotoEdit.setStyleSheet(
            "QLineEdit { background-color: #E85752; }")

    def lookupSelectedRadical(self):
        if self.currentSelectedEntry:
            self.showRadicalCharacters(self.currentSelectedEntry)

    def gotoEditCleared(self):
        script = 'document.getElementById("radicaltable").scrollIntoView();'
        self.radicalView.page().mainFrame().evaluateJavaScript(script)
        self.selectRadicalEntry(None)

    def gotoNextClicked(self, enabled):
        endRadical = max(self.radicalEntryDict.keys()) + 1

        if self.currentSelectedEntry:
            startRadical = self.currentSelectedEntry + 1
        else:
            startRadical = 1
        inputString = unicode(self.gotoEdit.text()).lower()
        searchRange = range(startRadical, endRadical)
        searchRange.extend(range(1, startRadical))

        for radicalIndex in searchRange:
            chars, meaning = self.radicalEntryDict[radicalIndex]
            if (meaning and meaning.lower().find(inputString) >= 0) \
                or inputString in chars:
                self.selectRadicalEntry(radicalIndex)
                break

    def selectRadicalEntry(self, radicalIndex):
        # deselect old entry
        if self.currentSelectedEntry:
            script = 'elem = document.getElementById("' + 'radical' \
                + str(self.currentSelectedEntry) + '");' \
                + 'elem.className = elem.className.replace(" ' \
                + self.SELECTED_RADICAL_CSS_CLASS + '", "");'
            self.radicalView.page().mainFrame().evaluateJavaScript(
                script)
        # select new entry
        if radicalIndex != None:
            script = 'elem = document.getElementById("' + 'radical' \
                + str(radicalIndex) + '");' \
                + 'elem.className = elem.className.concat(" ", "' \
                + self.SELECTED_RADICAL_CSS_CLASS + '");'
            self.radicalView.page().mainFrame().evaluateJavaScript(
                script)

            # put entry into view
            script = 'document.getElementById("' + 'radical' \
                + str(radicalIndex) + '").scrollIntoView();'
            self.radicalView.page().mainFrame().evaluateJavaScript(
                script)
        self.currentSelectedEntry = radicalIndex
        self.gotoButton.setEnabled(self.currentSelectedEntry != None)

    def writeSettings(self):
        if self.pluginConfig:
            self.pluginConfig.writeEntry("Radical include all",
                str(self.includeAllRadicals))

    def contentRendered(self, id, classObject, method, args, param, content):
        if classObject == htmlview.HtmlView and method == 'getRadicalTable':
            htmlCode, self.radicalEntryDict = content
            self.radicalView.setHtml('<html><head><title>Radicals</title>' \
                + '<link rel="StyleSheet" href="file://%s" type="text/css" />' \
                    % util.getData('style.css')
                + '</head>' \
                + '<body>%s</body>' % htmlCode \
                + '</html>')

            self.radicalView.page().mainFrame().evaluateJavaScript(
                self.CLICKABLE_ROW_JAVASCRIPT)
        elif classObject == htmlview.HtmlView \
            and method == 'getCharacterForRadical':
            self.radicalView.setHtml('<html><head><title>Results</title>' \
                + '<link rel="StyleSheet" href="file://%s" type="text/css" />' \
                    % util.getData('style.css')
                + '</head>' \
                + '<body>%s</body>' % content \
                + '</html>')
        elif classObject == characterinfo.CharacterInfo \
            and method == 'getRadicalForms':
                self.maximumStrokeCount = max([strokeCount \
                    for _, strokeCount, _ in content.values()])

    def objectCreated(self, id, classObject):
        if classObject == htmlview.HtmlView:
            if self.radicalView.title() == 'Radicals':
                self.renderThread.enqueue(htmlview.HtmlView, 'getRadicalTable')
            elif self.radicalView.title() == 'Results':
                self.toggleIncludeAllRadicals(self.includeAllRadicals)
