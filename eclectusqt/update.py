#!/usr/bin/python
# -*- coding: utf-8  -*-

"""
Dictionary update plugin.

@todo Fix:  IOError during download process should be delt with.

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
import codecs
import urlparse
import sys
import os
from datetime import date, time, datetime

from sqlalchemy import select
from sqlalchemy.exceptions import OperationalError

from PyQt4.QtCore import Qt, SIGNAL
from PyQt4.QtGui import QWidget, QApplication, QCursor

from PyKDE4.kdecore import ki18n, i18n, KTemporaryFile, KUrl
from PyKDE4.kio import KIO
from PyKDE4.kdeui import KIcon, KMessageBox, KStandardGuiItem, KDialog
from PyKDE4.kdeui import KAction, KActionCollection

from cjklib import build
from cjklib.dbconnector import getDBConnector

from eclectusqt import util
from eclectusqt.forms import UpdateUI

from libeclectus.buildtables import EclectusCommandLineBuilder
from libeclectus.dictionary import getAvailableDictionaryNames
from libeclectus.util import getDatabaseConfiguration

class DictionaryInfo(object):
    def __init__(self, dbConnectInst=None, databaseUrl=None):
        self.db = dbConnectInst or getDBConnector(
            getDatabaseConfiguration(databaseUrl))

    def getDictionaryVersions(self):
        dictionaries = getAvailableDictionaryNames(self.db, includePseudo=False)

        if self.db.hasTable('UpdateVersion'):
            table = self.db.tables['UpdateVersion']
            versionDict = dict(
                [(tableName, datetime.min) for tableName in dictionaries])

            versionDict.update(dict(self.db.selectRows(
                select([table.c.TableName, table.c.ReleaseDate],
                    table.c.TableName.in_(dictionaries)))))

            return versionDict
        else:
            return dict([(table, None) for table in dictionaries])


class UpdateDialog(KDialog):
    def __init__(self, mainWindow, renderThread, pluginConfig=None):
        KDialog.__init__(self, mainWindow)
        self.renderThread = renderThread

        self.databaseUrl = None
        if pluginConfig:
            self.databaseUrl = util.readConfigString(self.pluginConfig,
                "Update database url", None)

        if not self.databaseUrl:
            self.databaseUrl = unicode('sqlite:///'
                + util.getLocalData('dictionaries.db'))

        self.renderThread.setObject(DictionaryInfo,
            databaseUrl=self.databaseUrl)

        self.setCaption(i18n("Install/Update Dictionaries"))
        self.setButtons(KDialog.ButtonCode(KDialog.Close))
        self.enableButton(KDialog.Cancel, False)

        # TODO can we defer the creation of the update widget until the dialog is shown?
        self.updateWidget = UpdateWidget(mainWindow, renderThread, pluginConfig)
        self.connect(self.updateWidget, SIGNAL("working(bool)"),
            self.slotUpdateWorking)
        self.setMainWidget(self.updateWidget)

        self.connect(self, SIGNAL("finished()"), self.slotFinish)

        self.initialised = False

        self.connect(self.renderThread, SIGNAL("jobFinished"),
            self.contentRendered)
        self.connect(self.renderThread, SIGNAL("jobErrorneous"),
            self.renderingFailed)

        self.actionCollection = KActionCollection(self)
        self.setupActions()

    def showEvent(self, event):
        if not self.initialised:
            self.initialised = True
            self.loadDatabaseBuilder()
            self.updateWidget.setup()

    def setupActions(self):
        # update dictionaries
        self._updateAction = KAction(KIcon('system-software-update'),
            i18n("&Update..."), self)
        self.actionCollection.addAction("updatedictionaries",
            self._updateAction)
        self._updateAction.setWhatsThis(
            i18n("Download and update dictionaries."))
        self.connect(self._updateAction, SIGNAL("triggered(bool)"),
            self.exec_)
        # optimise database
        self._optimiseAction = KAction(KIcon('system-run'),
            i18n("&Optimise database"), self)
        self.actionCollection.addAction("optimisedatabase",
            self._optimiseAction)
        self._optimiseAction.setWhatsThis(
            i18n("Rearranges and optimises the database."))
        self._optimiseAction.setEnabled(True) # TODO
        self.connect(self._optimiseAction, SIGNAL("triggered(bool)"),
            self.slotOptimiseDatabase)

    def updateAction(self, actionCollection):
        actionCollection.addAction(self._updateAction.objectName(),
            self._updateAction)
        return self._updateAction

    def optimiseAction(self, actionCollection):
        actionCollection.addAction(self._optimiseAction.objectName(),
            self._optimiseAction)
        return self._optimiseAction

    def slotUpdateWorking(self, working):
        if working:
            self.setButtons(KDialog.ButtonCode(KDialog.Cancel))
        else:
            self.setButtons(KDialog.ButtonCode(KDialog.Close))

    def slotFinish(self):
        if self.updateWidget.isWorking():
            self.updateWidget.cancel()

    def slotOptimiseDatabase(self):
        self.loadDatabaseBuilder()
        dbBuild = self.renderThread.getObjectInstance(build.DatabaseBuilder)
        if dbBuild.isOptimizable():
            if KMessageBox.warningContinueCancel(self,
                i18n("This operation might take some time."),
                i18n("Optimise Database"), KStandardGuiItem.cont(),
                KStandardGuiItem.cancel(), 'database_optimise') \
                    == KMessageBox.Continue:
                QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
                self.currentJob = self.renderThread.enqueue(
                    build.DatabaseBuilder, 'optimize')

    def loadDatabaseBuilder(self):
        if not self.renderThread.hasObject(build.DatabaseBuilder):
            options = EclectusCommandLineBuilder.getDefaultOptions()

            db = getDBConnector(getDatabaseConfiguration(self.databaseUrl))

            self.renderThread.setObject(build.DatabaseBuilder, dbConnectInst=db,
                **options)

    def contentRendered(self, id, classObject, method, args, param, content):
        if classObject == build.DatabaseBuilder and method == 'optimize':
            QApplication.restoreOverrideCursor()

    def renderingFailed(self, id, classObject, method, args, param, e,
            stacktrace):
        if classObject == build.DatabaseBuilder and method == 'optimize':
            print >>sys.stderr, stacktrace
            QApplication.restoreOverrideCursor()


class UpdateWidget(QWidget, UpdateUI.Ui_Form):
    DICTIONARY_NAMES = {'CEDICT': ki18n('English-Chinese (CEDICT)'),
        'CEDICTGR': ki18n('English-Chinese (CEDICT, GR version)'),
        'HanDeDict': ki18n('German-Chinese (HanDeDict)'),
        'CFDICT': ki18n('French-Chinese (CFDICT)'),
        'EDICT': ki18n('English-Japanese (EDICT)')}

    def __init__(self, mainWindow, renderThread, pluginConfig=None):
        QWidget.__init__(self, mainWindow)

        self.renderThread = renderThread
        # set up UI
        self.setupUi(self)

        self.dictionarList = [dictionaryName for dictionaryName \
            in self.DICTIONARY_NAMES.keys() if hasDownloader(dictionaryName)]
        self.currentDictionary = self.dictionarList[0]

        self.dictionaryCombo.addItems(
            [self.DICTIONARY_NAMES[dictionary].toString() \
                for dictionary in self.dictionarList])
        self.dictionaryCombo.setEnabled(False)
        self.connect(self.dictionaryCombo, SIGNAL("activated(int)"),
            self.slotDictionarySelected)
        self.checkVersionButton.setEnabled(False)
        self.connect(self.checkVersionButton, SIGNAL("clicked(bool)"),
            self.slotCheckVersion)
        self.connect(self.installButton, SIGNAL("clicked(bool)"),
            self.installDictionary)
        self.connect(self.removeButton, SIGNAL("clicked(bool)"),
            self.removeDictionary)

        self.checkVersionButton.setIcon(KIcon('view-refresh'))
        self.installButton.setIcon(KIcon('system-software-update'))
        self.removeButton.setIcon(KIcon('edit-delete'))

        self.statusLabel.setText(i18n('Getting current versions...'))
        self.progressBar.setVisible(False)

        self.dictionaryHasNewer = {}
        self.dictionaryCurrentVersion = {}
        self.dictionaryNewerVersion = {}
        self.dictionaryNewerVersionString = {}
        self.downloader = {}
        self.actionCollection = KActionCollection(self)
        self.working = False
        self.currentJob = None

        self.connect(self.renderThread, SIGNAL("jobFinished"),
            self.contentRendered)
        self.connect(self.renderThread, SIGNAL("jobErrorneous"),
            self.renderingFailed)

    def setup(self):
        self.renderThread.enqueue(DictionaryInfo, 'getDictionaryVersions')

    def cancel(self):
        if self.currentJob:
            self.renderThread.dequeue(self.currentJob)

    def getDownloader(self, dictionaryName):
        if dictionaryName not in self.downloader:
            self.downloader[dictionaryName] \
                = getDownloader(dictionaryName, self)

        return self.downloader[dictionaryName]

    def setDictionaryVersions(self, versionDict):
        self.dictionaryCurrentVersion = {}
        for dictionaryName, version in versionDict.items():
            if not hasDownloader(dictionaryName):
                continue
            self.dictionaryCurrentVersion[dictionaryName] = version

        self.dictionaryCombo.setEnabled(True)

        # update version for simple downloader modules
        for dictionaryName in self.dictionarList:
            downloader = self.getDownloader(dictionaryName)

            if not downloader.getDownloadPageLink():
                # we can get the date without downloading
                self.checkVersion(dictionaryName)

        self.slotDictionarySelected(0)

    def getDictionaryCurrentVersion(self, dictionaryName):
        return self.dictionaryCurrentVersion.get(dictionaryName)

    def getDictionaryNewestVersion(self, dictionaryName):
        downloader = self.getDownloader(dictionaryName)

        if downloader.getDownloadPageLink():
            self.statusLabel.setText(i18n('Querying %1',
                downloader.getDownloadPageLink()))

        try:
            return downloader.getDate()
        except IOError, e:
            self.statusLabel.setText(i18n('Error getting download page "%1"',
                unicode(e)))

    def installDictionary(self):
        if self.currentDictionary in self.dictionaryHasNewer \
            and not self.dictionaryHasNewer[self.currentDictionary] \
            and KMessageBox.warningContinueCancel(self,
                i18n("Local version is already up-to-date.\n\nInstall anyway?"),
                i18n("Reinstall"), KStandardGuiItem.cont(),
                KStandardGuiItem.cancel(), 'reinstall_confirmation') \
                == KMessageBox.Cancel:
            return

        downloader = self.getDownloader(self.currentDictionary)

        link = downloader.getDownloadLink()
        if not link:
            self.statusLabel.setText(i18n('Error getting download page "%1"',
                downloader.lastError))
            return

        self.statusLabel.setText(i18n('Downloading from %1...', link))
        self.checkVersionButton.setEnabled(False)
        self.dictionaryCombo.setEnabled(False)
        self.removeButton.setEnabled(False)
        self.installButton.setEnabled(False)
        self.setWorking(True)

        filePath, fileType = downloader.download()
        if filePath:
            self.statusLabel.setText(i18n('Installing...', link))

            dbBuild = self.renderThread.getObjectInstance(build.DatabaseBuilder)
            builderClass = dbBuild.getTableBuilder(self.currentDictionary)
            dbBuild.setBuilderOptions(builderClass, 
                {'filePath': unicode(filePath), 'fileType': unicode(fileType)})

            tables = [self.currentDictionary]

            # look for related tables and install them, too
            relatedKey = self.currentDictionary + '_related'
            if relatedKey in EclectusCommandLineBuilder.BUILD_GROUPS:
                tables.extend(
                    EclectusCommandLineBuilder.BUILD_GROUPS[relatedKey])
            # TODO UpdateVersion might be installed later
            # TODO if for the first time a new language is installed check if
            #  tables in BUILD_GROUPS (zh-cmn, ja) need to be installed

            self.currentJob = self.renderThread.enqueue(build.DatabaseBuilder,
                'build', tables)
        else:
            self.statusLabel.setText(i18n('Error downloading from "%1": "%2"',
                link, downloader.lastError))
            self.dictionaryCombo.setEnabled(True)
            self.setWorking(False)

    def removeDictionary(self):
        # TODO only remove if available in main database
        self.statusLabel.setText(i18n('Removing dictionary...'))
        self.checkVersionButton.setEnabled(False)
        self.dictionaryCombo.setEnabled(False)
        self.removeButton.setEnabled(False)
        self.installButton.setEnabled(False)
        self.setWorking(True)

        self.currentJob = self.renderThread.enqueue(build.DatabaseBuilder,
            'remove', [self.currentDictionary])

    def setWorking(self, working):
        if self.working != working:
            self.working = working
            self.emit(SIGNAL("working(bool)"), self.working)

    def isWorking(self):
        return self.working

    def installFinished(self, success):
        if success:
            # TODO get the version without need to check the website
            if self.currentDictionary in self.dictionaryNewerVersion:
                self.dictionaryCurrentVersion[self.currentDictionary] \
                    = self.dictionaryNewerVersion[self.currentDictionary]
            else:
                # TODO hack
                self.dictionaryCurrentVersion[self.currentDictionary] = 1
            self.dictionaryHasNewer[self.currentDictionary] = False
            self.statusLabel.setText(i18n('Installation complete'))
        else:
            # TODO why failed?
            self.statusLabel.setText(i18n('Installation failed'))

        self.dictionaryCombo.setEnabled(True)
        self.setWorking(False)
        self.removeButton.setEnabled(True)

        self.getDownloader(self.currentDictionary).cleanUp()

    def removeFinished(self, success):
        if success:
            self.dictionaryCurrentVersion[self.currentDictionary] = None
            self.dictionaryHasNewer[self.currentDictionary] = True
            self.statusLabel.setText(i18n('Removal complete'))
        else:
            # TODO why failed?
            self.statusLabel.setText(i18n('Removal failed'))

        self.dictionaryCombo.setEnabled(True)
        self.setWorking(False)
        self.installButton.setEnabled(True)
        self.removeButton.setEnabled(False)

    def checkVersion(self, dictionaryName):
        currentVersion = self.getDictionaryCurrentVersion(dictionaryName)
        newestVersion = self.getDictionaryNewestVersion(dictionaryName)

        self.dictionaryNewerVersionString[dictionaryName] = str(newestVersion)

        if isinstance(newestVersion, date):
            newestVersion = datetime.combine(newestVersion, time(0))

        self.dictionaryHasNewer[dictionaryName] \
            = not currentVersion or (newestVersion \
                and currentVersion < newestVersion)
        self.dictionaryNewerVersion[dictionaryName] = newestVersion

    def slotCheckVersion(self):
        self.checkVersion(self.currentDictionary)

        self.updateStatusLabelVersion()
        self.checkVersionButton.setEnabled(False)
        self.installButton.setEnabled(True)
        #self.installButton.setEnabled(
            #self.dictionaryHasNewer[self.currentDictionary])

    def slotDictionarySelected(self, idx):
        self.currentDictionary = self.dictionarList[idx]
        self.updateStatusLabelVersion()

        haveCurrentVersion = self.getDictionaryCurrentVersion(
            self.currentDictionary) != None
        haveNewerInformation = self.currentDictionary in self.dictionaryHasNewer

        self.checkVersionButton.setEnabled(not haveNewerInformation)
        #self.installButton.setEnabled(haveNewerInformation)
        self.installButton.setEnabled(True)
        self.removeButton.setEnabled(haveCurrentVersion)
        #if haveInformation:
            #self.installButton.setEnabled(
                #self.dictionaryHasNewer[self.currentDictionary])
        #else:
            #self.installButton.setEnabled(False)

    def updateStatusLabelVersion(self):
        if self.currentDictionary not in self.dictionaryHasNewer:
            currentVersion = self.getDictionaryCurrentVersion(
                self.currentDictionary)
            if currentVersion and currentVersion > datetime.min:
                self.statusLabel.setText(i18n('Local version is from %1',
                    str(currentVersion)))
            elif currentVersion is None:
                self.statusLabel.setText(i18n('Not installed'))
            else:
                self.statusLabel.setText(
                    i18n('No information for local version available'))
        elif self.dictionaryHasNewer[self.currentDictionary]:
            currentVersion = self.getDictionaryCurrentVersion(
                self.currentDictionary)
            newerVersion \
                = self.dictionaryNewerVersionString[self.currentDictionary]
            if currentVersion:
                self.statusLabel.setText(i18n(
                    'Upstream has newer version from %1', str(newerVersion)))
            else:
                self.statusLabel.setText(i18n('Install version from %1',
                    str(newerVersion)))
        elif self.currentDictionary in self.dictionaryNewerVersion \
            and self.dictionaryNewerVersion[self.currentDictionary] == None:
            self.statusLabel.setText(
                i18n('Unable to retrieve version information.'))
        else:
            newerVersion \
                = self.dictionaryNewerVersionString[self.currentDictionary]
            self.statusLabel.setText(i18n('Local version from %1 is up-to-date',
                str(newerVersion)))

    def contentRendered(self, id, classObject, method, args, param, content):
        if classObject == DictionaryInfo and method == 'getDictionaryVersions':
            self.setDictionaryVersions(content)

        elif classObject == build.DatabaseBuilder and method == 'build':
            self.emit(SIGNAL("databaseChanged()"))

            self.installFinished(True)
        elif classObject == build.DatabaseBuilder and method == 'remove':
            self.emit(SIGNAL("databaseChanged()"))

            # update menu
            self.removeFinished(True)

    def renderingFailed(self, id, classObject, method, args, param, e,
            stacktrace):
        if classObject == build.DatabaseBuilder \
            and method == 'build':
            self.installFinished(False)
        elif classObject == build.DatabaseBuilder \
            and method == 'remove':
            self.removeFinished(False)


class DictionaryDownloader:
    DOWNLOADER_NAME = 'default'
    DEFAULT_DOWNLOAD_PAGE = None
    DOWNLOAD_REGEX = None

    def __init__(self, parentWidget, downloadPage=None):
        self.parentWidget = parentWidget
        if downloadPage:
            self.downloadPageUrl = downloadPage
        else:
            self.downloadPageUrl = self.DEFAULT_DOWNLOAD_PAGE

        self.downloadPageContent = None
        self.downloadUrl = None
        self.lastError = None

        self.temporaryFiles = []

    def getDownloadPageContent(self):
        if self.downloadPageContent == None:
            if not self.downloadPage():
                raise IOError('cannot get download page:' + self.lastError)

        return self.downloadPageContent

    def getDownloadPageLink(self):
        return self.downloadPageUrl

    def getDownloadLink(self):
        if self.downloadUrl == None:
            matchObj = self.DOWNLOAD_REGEX.search(self.getDownloadPageContent())
            if not matchObj:
                raise IOError('cannot read download page')

            baseUrl = matchObj.group(1)
            self.downloadUrl = urlparse.urljoin(self.getDownloadPageLink(),
                baseUrl)

        return self.downloadUrl

    def getDate(self):
        return None

    def downloadPage(self):
        tempFile = KTemporaryFile()
        tempFile.setPrefix('eclectus/' + self.DOWNLOADER_NAME + '_downloadpage')
        tempFileName = tempFile.fileName()

        if KIO.NetAccess.download(KUrl(self.getDownloadPageLink()),
            tempFileName, self.parentWidget):
            self.lastError = None

            try:
                f = codecs.open(tempFileName, 'r', 'utf8')
                self.downloadPageContent = f.read()
                f.close()
            except IOError, e:
                self.lastError = unicode(e)
                return False

            return True
        else:
            self.lastError = unicode(KIO.NetAccess.lastErrorString())
            return False

    def download(self):
        tempFile = KTemporaryFile()
        tempFile.setAutoRemove(False)
        tempFile.setPrefix('eclectus/' + self.DOWNLOADER_NAME)
        tempFileName = tempFile.fileName()

        if KIO.NetAccess.download(KUrl(self.getDownloadLink()), tempFileName,
            self.parentWidget):
            self.lastError = None

            _, _, onlinePath, _, _ = urlparse.urlsplit(
                self.getDownloadLink())
            fileType = None
            matchObj = re.search('\.(zip|tar|tar\.bz2|tar\.gz|gz|txt)$',
                onlinePath)
            if matchObj:
                fileType = matchObj.group(0)

            return tempFileName, fileType
        else:
            self.lastError = unicode(KIO.NetAccess.lastErrorString())
            return None, None

    def cleanUp(self):
        while len(self.temporaryFiles) > 0:
            filePath = self.temporaryFiles.pop()
            if os.path.exists(filePath):
                try:
                    if os.path.isdir(filePath):
                        os.rmdir(filePath)
                    else:
                        os.unlink(filePath)
                except OSError:
                    pass
                except IOError:
                    pass


class HanDeDictDownloader(DictionaryDownloader):
    DOWNLOADER_NAME = 'HanDeDict'
    DEFAULT_DOWNLOAD_PAGE \
        = u'http://www.chinaboard.de/chinesisch_deutsch.php?mode=dl'
    DOWNLOAD_REGEX = re.compile(
        u'<a href="(handedict/handedict-(?:\d+).tar.bz2)">')

    DATE_REGEX = re.compile(u'<a href="handedict/handedict-(\d+).tar.bz2">')

    def getDate(self):
        matchObj = self.DATE_REGEX.search(self.getDownloadPageContent())
        if matchObj:
            return datetime.strptime(matchObj.group(1), '%Y%m%d').date()


class CFDICTDownloader(DictionaryDownloader):
    DOWNLOADER_NAME = 'CFDICT'
    DEFAULT_DOWNLOAD_PAGE = u'http://www.chinaboard.de/cfdict.php?mode=dl'
    DOWNLOAD_REGEX = re.compile(u'<a href="(cfdict/cfdict-(?:\d+).tar.bz2)">')

    DATE_REGEX = re.compile(u'<a href="cfdict/cfdict-(\d+).tar.bz2">')

    def getDate(self):
        matchObj = self.DATE_REGEX.search(self.getDownloadPageContent())
        if matchObj:
            return datetime.strptime(matchObj.group(1), '%Y%m%d').date()


class CEDICTDownloader(DictionaryDownloader):
    DOWNLOADER_NAME = 'CEDICT'
    DEFAULT_DOWNLOAD_PAGE \
        = u'http://www.mdbg.net/chindict/chindict.php?page=cc-cedict'
    DOWNLOAD_REGEX = re.compile(
        u'<a href="(export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz)">')

    DATE_REGEX = re.compile(
        u'Latest release: <strong>([^<]+)</strong>')

    def getDate(self):
        matchObj = self.DATE_REGEX.search(self.getDownloadPageContent())
        if matchObj:
            return datetime.strptime(matchObj.group(1), '%Y-%m-%d %H:%M:%S %Z')


class CEDICTGRDownloader(DictionaryDownloader):
    DOWNLOADER_NAME = 'CEDICTGR'
    DOWNLOAD_LINK = u'http://home.iprimus.com.au/richwarm/gr/cedictgr.zip'

    def getDownloadPageContent(self):
        return None

    def getDownloadPageLink(self):
        return None

    def getDownloadLink(self):
        return self.DOWNLOAD_LINK

    def getDate(self):
        return date(2001, 2, 16)

    def downloadPage(self):
        return True


class EDICTDownloader(DictionaryDownloader):
    DOWNLOADER_NAME = 'EDICT'
    DOWNLOAD_LINK = u'http://ftp.monash.edu.au/pub/nihongo/edict.gz'

    def getDownloadPageContent(self):
        return None

    def getDownloadPageLink(self):
        return None

    def getDownloadLink(self):
        return self.DOWNLOAD_LINK

    def getDate(self):
        return date.today()

    def downloadPage(self):
        return True


CLASS_DICT = {'CEDICT': CEDICTDownloader, 'HanDeDict': HanDeDictDownloader,
    'CFDICT': CFDICTDownloader, 'CEDICTGR': CEDICTGRDownloader,
    'EDICT': EDICTDownloader}

def getDownloader(dictName, parent):
    downloaderClass = CLASS_DICT[dictName]
    return downloaderClass(parent)

def hasDownloader(dictName):
    return dictName in CLASS_DICT

