#!/usr/bin/python
# -*- coding: utf-8 -*-
u"""
Utility methods.

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
import sys

from PyQt4.QtCore import SIGNAL, QUrl
from PyQt4.QtWebKit import QWebPage

from PyKDE4.kdecore import KStandardDirs

# read local path so that eclectus can run from the local directory
localDataDir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
if not os.path.exists(localDataDir):
    localDataDir = None

def getIcon(fileName):
    global localDataDir

    absPath = unicode(KStandardDirs.locate('icon',
        os.path.join('eclectus', fileName)))
    if absPath:
        return absPath
    elif localDataDir:
        return os.path.join(localDataDir, 'icons', fileName)

def getData(fileName):
    global localDataDir

    absPath = unicode(KStandardDirs.locate('data',
        os.path.join('eclectus', fileName)))
    if absPath:
        return absPath
    elif localDataDir:
        return os.path.join(localDataDir, fileName)

def getLocalData(fileName):
    return KStandardDirs.locateLocal('data', os.path.join('eclectus', fileName))

def getDataPaths():
    paths = []
    absPath = unicode(KStandardDirs.installPath('data'))
    if absPath:
        paths.append(os.path.join(absPath, 'eclectus', 'data'))
    if localDataDir:
        paths.append(localDataDir)
    return paths

# config

def readConfigString(config, option, default=None):
    value = config.readEntry(option)
    if not value:
	return default
    elif hasattr(value, "toString"):
	return value.toString()
    else:
	return unicode(value)

def _readConfig(config, option, default, conversionFunc):
    return conversionFunc(readConfigString(config, option, default))

def readConfigInt(config, option, default=None):
    return _readConfig(config, option, default, int)


class HandyWebpage(QWebPage):
    def __init__(self, parent):
        QWebPage.__init__(self, parent)
        self.setLinkDelegationPolicy(QWebPage.DelegateAllLinks)

    def javaScriptConsoleMessage(self, message, lineNumber, sourceID):
        print >>sys.stderr, unicode('Javascript: ' + message).encode('utf8')

    def javaScriptAlert(self, frame, msg):
        # TODO ugly workaround for webkit not recognizing url changed done by
        #   javascript
        if unicode(msg).startswith('navigate:'):
            url = unicode(msg).replace('navigate:', '')
            self.emit(SIGNAL("linkClicked(const QUrl &)"), QUrl(url))
        else:
            QWebPage.javaScriptAlert(self, frame, msg)
