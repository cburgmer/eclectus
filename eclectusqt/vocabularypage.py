#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Vocabulary plugin offering simple vocabulary management.

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
import locale
import codecs
import os
import sys
import functools
from datetime import date

from PyQt4.QtCore import Qt, SIGNAL, QVariant, QModelIndex, QAbstractListModel
from PyQt4.QtGui import QWidget, QAction, QAbstractItemView, QShortcut, QMenu

from PyKDE4.kdeui import KIcon, KMenu, KStandardAction, KMessageBox
from PyKDE4.kdecore import i18n, KUrl
from PyKDE4.kio import KFileDialog

from eclectusqt.forms import VocabularyPageUI
from eclectusqt import util

from libeclectus import characterinfo

class BaseExporter:
    DEFAULT_FILE_NAME = None
    FILE_TYPES = ['*']

    def __init__(self, pluginConfig=None):
        self.filePath = self.DEFAULT_FILE_NAME
        self.entries = []
        self.pluginConfig = pluginConfig

    def getFileTypes(self):
        """Filter file types used in file save dialog."""
        return self.FILE_TYPES

    def getFilePath(self):
        """Returns current file, None if no file name configuration possible."""
        return self.filePath

    def setFilePath(self, filePath):
        """Sets current file."""
        self.filePath = filePath

    def setEntries(self, entries):
        """Sets current entries and removes previous ones."""
        self.entries = entries


#class YourExporter(BaseExporter):
    #DEFAULT_FILE_NAME = ""
    #"""Default file name to write to"""

    #def write(self):
        #"""Write entries."""
        #try:
            ###f = codecs.open(self.filePath, 'w', 'utf-8')
            ## write entries
            #for entry in self.entries:
                #print entry['Headword'] # Do something
                ## ...

            ## Once finished, register it in the EXPORTER list of the vocabulary
            ##   page class
            #return True
        #except IOError, e:
            #return False


class CSVExporter(BaseExporter):
    DEFAULT_FILE_NAME = "eclectus.csv"
    FILE_TYPES = ['*.csv', '*.txt']

    KEYS = ['Headword', 'Pronunciation', 'Translation', 'AudioFile',
        'HeadwordLanguage', 'TranslationLanguage', 'PronunciationType']

    def __init__(self, pluginConfig=None):
        BaseExporter.__init__(self, pluginConfig)
        self.error = None

    def setFilePath(self, filePath):
        """Sets current file."""
        self.filePath = filePath
        self.pluginConfig.writeEntry("Export file path CSV", self.filePath)

    def write(self):
        """Write entries."""
        try:
            f = codecs.open(self.filePath, 'w', locale.getpreferredencoding())
            # document columns
            for i, key in enumerate(self.KEYS):
                f.write('# Column %d: %s\n' % (i+1, key))
            # write entries
            for entry in self.entries:
                entryList = []
                for key in self.KEYS:
                    if key in entry:
                        entryList.append(entry[key])
                    else:
                        entryList.append('')
                f.write(','.join([
                    '"' + cell.replace('\\', '\\\\').replace('"', '\\"') + '"' \
                    for cell in entryList]) + '\n')
            f.close()
            return True
        except IOError, e:
            self.error = e
            return False
        except UnicodeError, e:
            self.error = e
            return False


class CompactCSVExporter(CSVExporter):
    KEYS = ['Headword', 'Pronunciation', 'Translation', 'AudioFile']


class KVTMLExporter(BaseExporter):
    DEFAULT_FILE_NAME = "eclectus.kvtml"
    FILE_TYPES = ['*.kvtml']

    def __init__(self, pluginConfig=None):
        BaseExporter.__init__(self, pluginConfig)
        self.error = None

    def setFilePath(self, filePath):
        """Sets current file."""
        self.filePath = filePath
        self.pluginConfig.writeEntry("Export file path KVTML", self.filePath)

    def write(self):
        """Write entries."""
        headwordLanguages = set()
        translationLanguages = set()
        for entry in self.entries:
            if 'HeadwordLanguage' in entry:
                headwordLanguages.add(entry['HeadwordLanguage'])
            if 'TranslationLanguage' in entry:
                translationLanguages.add(entry['TranslationLanguage'])

        if len(headwordLanguages) == 1:
            headwordLanguage = headwordLanguages.pop()
        else:
            headwordLanguage = ''
        if len(translationLanguages) == 1:
            translationLanguage = translationLanguages.pop()
        else:
            translationLanguage = ''

        try:
            f = codecs.open(self.filePath, 'w', 'utf-8')
            f.write('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE kvtml PUBLIC "kvtml2.dtd" "http://edu.kde.org/kanagram/kvtml2.dtd">
<kvtml version="2.0" >
  <information>
    <generator>Eclectus %s</generator>
    <title>Export</title>
    <date>%s</date>
  </information>
  <identifiers>
    <identifier id="0" >
      <name>Headword</name>
      <locale>%s</locale>
    </identifier>
    <identifier id="1" >
      <name>Translation</name>
      <locale>%s</locale>
    </identifier>
  </identifiers>
  <entries>
''' % (sys.modules['__main__'].__version__, str(date.today()), headwordLanguage, translationLanguage))

            # write entries
            for idx, entry in enumerate(self.entries):
                if 'Headword' in entry:
                    headword = entry['Headword']
                else:
                    headword = ''
                if 'Pronunciation' in entry:
                    pronunciation = entry['Pronunciation']
                else:
                    pronunciation = ''
                if 'Translation' in entry:
                    translation = entry['Translation']
                else:
                    translation = ''

                f.write('''    <entry id="%d" >
      <translation id="0" >
        <text>%s</text>
        <pronunciation>%s</pronunciation>
      </translation>
      <translation id="1" >
        <text>%s</text>
      </translation>
    </entry>
''' % (idx, headword, pronunciation, translation))

            f.write('''  </entries>
</kvtml>
''')
            f.close()

            return True
        except IOError, e:
            self.error = e
            return False
        except UnicodeError, e:
            self.error = e
            return False


class CSVImporter:
    KEYS = ['Headword', 'Pronunciation', 'Translation', 'AudioFile',
        'HeadwordLanguage', 'TranslationLanguage', 'PronunciationType']

    def __init__(self, pluginConfig=None):
        self.filePath = "eclectus.csv"
        self.error = None

    def getFileTypes(self):
        return ['*.csv', '*.txt']

    def getFilePath(self):
        return self.filePath

    def setFilePath(self, filePath):
        self.filePath = filePath

    def read(self):
        try:
            f = codecs.open(self.filePath, 'r', locale.getpreferredencoding())
            entries = []
            for line in f:
                # skip comments
                if re.match(r'\s*#', line):
                    continue
                cells = re.findall(r'"(\\\\|\\"|[^"\\]+)*"', line)
                entry = {}
                for i, cell in enumerate(cells):
                    entry[self.KEYS[i]] = cell

                if 'Headword' in entry:
                    entries.append(entry)
                else:
                    print >>sys.stderr, ("Error reading line: " \
                        + line.strip()).encode(locale.getpreferredencoding())
            f.close()
            return entries
        except IOError, e:
            self.error = e
            return []
        except UnicodeError, e:
            self.error = e
            return []


class VocabularyModel(QAbstractListModel):
    # TODO implement QItemDelegate
    def __init__(self, parent=0):
        QAbstractListModel.__init__(self, parent)
        self.vocabularyList = []
        self.vocabularyHeadwordIndex = {}

    def _getEntryDict(self, entryVariant):
        if hasattr(entryVariant, 'toMap'):
            entryVariant = entryVariant.toMap()
        newEntry = {}
        for key, value in entryVariant.items():
            if hasattr(value, 'toString'):
                value = value.toString()
            newEntry[unicode(key)] = unicode(value)
        return newEntry

    def _buildVocabularyHeadwordIndex(self):
        self.vocabularyHeadwordIndex = {}
        for i, vocabEntry in enumerate(self.vocabularyList):
            if vocabEntry:
                vocabHeadword = vocabEntry['Headword']
                if vocabHeadword not in self.vocabularyHeadwordIndex:
                    self.vocabularyHeadwordIndex[vocabHeadword] = set()
                self.vocabularyHeadwordIndex[vocabHeadword].add(i)

    def addVocabulary(self, entry):
        entry = self._getEntryDict(entry)
        if 'Headword' not in entry:
            return
        entryIndex = self.find(entry)
        if entryIndex == None:
            if entry['Headword'] in self.vocabularyHeadwordIndex:
                insertRow = max(
                    self.vocabularyHeadwordIndex[entry['Headword']]) + 1
            else:
                insertRow = self.rowCount()
            self.insertRow(insertRow)
            entryIndex = self.index(insertRow)
            self.setData(entryIndex, QVariant(entry), Qt.DisplayRole)

        return entryIndex

    def removeVocabulary(self, entry):
        entryIndex = self.find(entry)
        if entryIndex:
            self.removeRow(entryIndex.row())

    def remove(self, modelIndices):
        rows = [modelIndex.row() for modelIndex in modelIndices]
        rows.sort()

        # get continuous rows
        continuous = []
        startRow = rows[0]
        rowCount = 1
        for row in rows[1:]:
            if row - 1 == startRow:
                rowCount += 1
            else:
                # save start row and row count
                continuous.append((startRow, rowCount))

                startRow = row
                rowCount = 1
        continuous.append((startRow, rowCount))
        continuous.reverse()
        # remove
        for startRow, rowCount in continuous:
            self.removeRows(startRow, rowCount)

    def getVocabulary(self):
        return self.vocabularyList[:]

    def getVocabularyEntry(self, modelIndex):
        return self.vocabularyList[modelIndex.row()].copy()

    def rowCount(self, parent=QModelIndex()):
        if parent == parent.parent():
            return len(self.vocabularyList)

    def setData(self, modelIndex, value, role=Qt.EditRole):
        if role == Qt.DisplayRole:
            self.vocabularyList[modelIndex.row()] \
                = self._getEntryDict(value)
        elif role == Qt.EditRole:
            if hasattr(value, 'toString'):
                value = value.toString()
            translation = unicode(value)
            self.vocabularyList[modelIndex.row()]['Translation'] = translation

        self._buildVocabularyHeadwordIndex()

        self.emit(
            SIGNAL("dataChanged(const QModelIndex &, const QModelIndex &)"),
            modelIndex, modelIndex)
        return True

    def data(self, modelIndex, role=Qt.DisplayRole):
        row = modelIndex.row()
        if role == Qt.DisplayRole:
            if self.vocabularyList[row]:
                headword = self.vocabularyList[row]['Headword']
                pronunciation = self.vocabularyList[row]['Pronunciation']
                translation = self.vocabularyList[row]['Translation']
                return QVariant(headword + ', ' + pronunciation + ', ' \
                    + translation)
            else:
                return QVariant()
            #return QVariant(self.vocabularyList[modelIndex.row()])
        elif role == Qt.EditRole:
            return QVariant(self.vocabularyList[row]['Translation'])
        return QVariant()

    def flags(self, modelindex):
        return QAbstractListModel.flags(self, modelindex) | Qt.ItemIsEditable

    def index(self, row, column=0, parent=QModelIndex()):
        return self.createIndex(row, column, self.vocabularyList[row])

    def find(self, entry):
        # TODO
        for i, e in enumerate(self.vocabularyList):
            for key in entry.keys():
                if key in e and e[key] != entry[key]:
                    break
            else:
                return self.index(i)

    def insertRows(self, row, count, parent=QModelIndex()):
        self.beginInsertRows(parent, row, row+count-1)
        for i in range(row, row + count):
            self.vocabularyList.insert(i, None)
        self.endInsertRows()

        self._buildVocabularyHeadwordIndex()
        return True

    def removeRows(self, row, count, parent=QModelIndex()):
        self.beginRemoveRows(parent, row, row+count-1)
        for i in range(row, row + count):
            del self.vocabularyList[row]
        self.endRemoveRows()

        self._buildVocabularyHeadwordIndex()
        return True


class VocabularyPage(QWidget, VocabularyPageUI.Ui_Form):
    EXPORTERS = [(CompactCSVExporter, i18n('Export as Plain Text (&CSV)...')),
        (KVTMLExporter, i18n('Export as KDE Vocabulary File (&KVTML)...')),
        #(YourExporter, i18n('Export to YOUR EXPORTER...')),
        ]

    def __init__(self, mainWindow, renderThread, pluginConfig=None):
        QWidget.__init__(self, mainWindow)
        self.renderThread = renderThread
        self.pluginConfig = pluginConfig

        # set up UI
        self.setupUi(self)

        self.vocabularyChanged = None # None -> not loaded

        self.vocabularyModel = VocabularyModel(self)
        self.vocabularyListView.setModel(self.vocabularyModel)

        self.exportHistoryButton.setEnabled(False)

        # connect to main window
        self.connect(mainWindow, SIGNAL("writeSettings()"),
            self.writeSettings)
        #self.connect(mainWindow, SIGNAL("pageRequested(const QString &)"),
            #self.slotPageRequested)
        self.connect(mainWindow,
            SIGNAL("vocabularyAdded(const QString &, const QString &, const QString &, const QString &)"),
            self.slotVocabularyAdded)

        # connect to the widgets
        self.connect(self.vocabularyModel,
            SIGNAL("dataChanged(const QModelIndex &, const QModelIndex &)"),
            self.slotDataChanged)
        #self.connect(self.vocabularyModel,
            #SIGNAL("dataChanged(const QModelIndex &, const QModelIndex &)"),
            #lambda: self.exportHistoryButton.setEnabled(
                #self.vocabularyModel.rowCount() != 0))
        self.connect(self.vocabularyModel,
            SIGNAL("rowsInserted(const QModelIndex &, int, int)"),
            lambda: self.exportHistoryButton.setEnabled(
                self.vocabularyModel.rowCount() != 0))
        self.connect(self.vocabularyModel,
            SIGNAL("rowsRemoved(const QModelIndex &, int, int)"),
            lambda: self.exportHistoryButton.setEnabled(
                self.vocabularyModel.rowCount() != 0))

        self.vocabularyListView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.vocabularyListView.editTriggers()
        self.vocabularyListView.setEditTriggers(
            QAbstractItemView.EditKeyPressed)
        self.connect(self.vocabularyListView,
            SIGNAL("customContextMenuRequested(const QPoint &)"),
            self.contextMenuRequested)
        self.connect(self.vocabularyListView,
            SIGNAL("doubleClicked(const QModelIndex)"),
                self.slotDoubleClickOnEntry)

        self.setupActions()

        self.initialised = False

    def setupActions(self):
        self._editAction = QAction(KIcon('document-properties'),
            i18n('&Edit Translation'), self)
        self._editAction.setShortcut(Qt.Key_Return)
        self._editAction.setShortcutContext(Qt.WidgetShortcut)
        self.connect(self._editAction, SIGNAL("triggered(bool)"),
            lambda: self.vocabularyListView.edit(
                self.vocabularyListView.currentIndex()))
        self.connect(self.vocabularyListView, SIGNAL("returnPressed()"),
            self._editAction.trigger) # TODO

        self._selectAllAction = KStandardAction.selectAll(
            self.vocabularyListView.selectAll, self)

        self._removeAction = QAction(KIcon('list-remove'),
            i18n('&Remove Selected'), self)
        #c = QShortcut(self)
        #c.setKey(Qt.Key_Delete)
        #c.setContext(Qt.WidgetShortcut)
        #self.connect(c, SIGNAL("activated()"), self._removeAction.trigger)
        self._removeAction.setShortcut(Qt.Key_Delete)
        self._removeAction.setShortcutContext(Qt.WidgetShortcut)
        self.connect(self.vocabularyListView, SIGNAL("deletePressed()"),
            self._removeAction.trigger) # TODO
        self.connect(self.vocabularyListView.selectionModel(),
            SIGNAL("selectionChanged(const QItemSelection &, const QItemSelection &)"),
            lambda: self._removeAction.setEnabled(
                self.vocabularyListView.selectionModel().hasSelection()))
        self.connect(self._removeAction, SIGNAL("triggered(bool)"),
            lambda: self.vocabularyModel.remove(
                self.vocabularyListView.selectedIndexes()))

    def showEvent(self, event):
        if not self.initialised:
            self.initialised = True

            self.exportHistoryButton.setIcon(KIcon('document-export'))
            exportMenu = QMenu(self.exportHistoryButton)

            for exporter, actionText in self.EXPORTERS:
                exportAction = QAction(actionText, self)
                self.connect(exportAction, SIGNAL("triggered(bool)"),
                    functools.partial(self.doExport, 
                        exporter(pluginConfig=self.pluginConfig)))

                exportMenu.addAction(exportAction)

            self.exportHistoryButton.setMenu(exportMenu)

            self.loadVocabulary()

        QWidget.showEvent(self, event)

    def loadVocabulary(self):
        if self.vocabularyChanged == None:
            csv = csvImporter = CSVImporter(pluginConfig=self.pluginConfig)
            fileName = util.getLocalData('eclectus.csv')
            csv.setFilePath(fileName)
            entries = csv.read()
            self.vocabularyModel.insertRows(0, len(entries))
            for i, entry in enumerate(entries):
                self.vocabularyModel.setData(self.vocabularyModel.index(i),
                    entry, Qt.DisplayRole)

            self.vocabularyChanged = False

    def slotDataChanged(self, modelIndexS, modelIndexE):
        self.vocabularyChanged = True

    def slotVocabularyAdded(self, headword, pronunciation, translation, audio):
        self.loadVocabulary()

        entry = {'Headword': unicode(headword),
            'Pronunciation': unicode(pronunciation),
            'Translation': unicode(translation), 'AudioFile': unicode(audio)}

        charInfo = self.renderThread.getObjectInstance(
            characterinfo.CharacterInfo)
        entry['HeadwordLanguage'] = charInfo.language
        if charInfo.dictionary:
            lang = characterinfo.CharacterInfo.DICTIONARY_TRANSLATION_LANG[
                charInfo.dictionary] # TODO
            entry['TranslationLanguage'] = lang
        entry['PronunciationType'] = charInfo.reading

        # add to history list
        entryIndex = self.vocabularyModel.addVocabulary(entry)
        self.vocabularyListView.setCurrentIndex(entryIndex)

    def doExport(self, exporter):
        filePath = exporter.getFilePath()

        if filePath != None:
            # if a path is set, than it is configurable
            fileTypes = exporter.getFileTypes()
            if fileTypes:
                filterStr = ' '.join(fileTypes)
            else:
                filterStr = ''
            # TODO make remote url work
            fileDialog = KFileDialog(KUrl(filePath), filterStr, self)
            fileDialog.setSelection(os.path.basename(filePath))
            fileDialog.setCaption(i18n('Export Vocabulary'))
            #fileDialog.setConfirmOverwrite(True)
            fileDialog.setOperationMode(KFileDialog.Saving)
            if fileDialog.exec_() != KFileDialog.Accepted:
                return

            filePath = unicode(fileDialog.selectedFile())

            # TODO setConfirmOverwrite() doesn't work right now, so...
            while filePath and os.path.exists(filePath) \
                and KMessageBox.warningYesNo(self,
                    i18n('The given file "%1" already exists. Overwrite?',
                        os.path.basename(filePath))) == KMessageBox.No:

                fileDialog.setSelection(os.path.basename(filePath))
                if fileDialog.exec_() != KFileDialog.Accepted:
                    return
                filePath = unicode(fileDialog.selectedFile())

            if not filePath:
                return

            exporter.setFilePath(unicode(filePath))

        exporter.setEntries(self.vocabularyModel.getVocabulary())
        try:
            if not exporter.write():
                KMessageBox.error(self, i18n('Error saving file'))
        except Exception, e:
            KMessageBox.error(self, i18n('Error saving file: %1', unicode(e)))
            print unicode(e).encode(locale.getpreferredencoding())

    def contextMenuRequested(self, pos):
        modelIndex = self.vocabularyListView.currentIndex()

        contextMenu = KMenu(self)
        contextMenu.addAction(self._editAction)
        contextMenu.addAction(self._selectAllAction)
        contextMenu.addAction(self._removeAction)

        if modelIndex.isValid():
            entry = self.vocabularyModel.getVocabularyEntry(modelIndex)
            if 'Headword' in entry:
                contextMenu.addSeparator()
                lookupAction = QAction(i18n('Lookup %1',
                    entry['Headword'].replace("&", "&&")), contextMenu)
                self.connect(lookupAction, SIGNAL("triggered(bool)"),
                    lambda: self.emit(SIGNAL('inputReceived(const QString &)'),
                        entry['Headword']))
                contextMenu.addAction(lookupAction)

        contextMenu.popup(self.vocabularyListView.mapToGlobal(pos))

    def slotDoubleClickOnEntry(self, modelIndex):
        entry = self.vocabularyModel.getVocabularyEntry(modelIndex)
        if 'Headword' in entry:
            self.emit(SIGNAL('inputReceived(const QString &)'),
                        entry['Headword'])

    def writeSettings(self):
        if self.pluginConfig:
            if self.vocabularyChanged:
                csv = CSVExporter(pluginConfig=self.pluginConfig)
                fileName = util.getLocalData('eclectus.csv')
                csv.setFilePath(fileName)

                csv.setEntries(self.vocabularyModel.getVocabulary())
                try:
                    csv.write()
                    self.vocabularyChanged = False
                except Exception, e:
                    print e.encode(locale.getpreferredencoding())
