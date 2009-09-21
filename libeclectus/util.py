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

import gettext
import base64
import os.path

# base64 encoding

def encodeBase64(string):
    return base64.b64encode(string.encode('utf8'))

def decodeBase64(string):
    return base64.b64decode(string).decode('utf8')

# font availablitiy

_hasQt = None
_hasFontAvailability = None
def hasFontAvailability():
    global _hasFontAvailability, _hasQt
    if _hasQt is None:
        try:
            from PyQt4.QtCore import QCoreApplication
            from PyQt4.QtGui import QFont, QFontMetrics
            _hasQt = True
        except ImportError:
            _hasQt = False
            _hasFontAvailability = False

    if _hasQt and not _hasFontAvailability:
        from PyQt4.QtCore import QCoreApplication
        fontCapabilities = QCoreApplication.instance() is not None

    return fontCapabilities

_currentFontFamily = None
_currentFontMetrics = None

def fontExists(fontFamily):
    if not hasFontAvailability():
        return False
    from PyQt4.QtGui import QFont

    return QFont(fontFamily).exactMatch()

def fontHasChar(fontFamily, char):
    if not hasFontAvailability():
        return False
    from PyQt4.QtGui import QFont, QFontMetrics
    from PyQt4.QtCore import QString

    global _currentFontFamily
    global _currentFontMetrics

    if not _currentFontFamily or _currentFontFamily != fontFamily:
        _currentFontFamily = fontFamily
        font = QFont(fontFamily)
        oldStrategy = font.styleStrategy()
        font.setStyleStrategy(oldStrategy and QFont.NoFontMerging)
        _currentFontMetrics = QFontMetrics(font)
    return _currentFontMetrics.inFont(QString(char).at(0))

# i18n

def getLocaleDir():
    base = os.path.dirname(os.path.abspath(__file__))
    localeDir = os.path.join(base, "locale")
    if not os.path.exists(localeDir):
        localeDir = "/usr/share/locale"
    return localeDir

def getTranslation(localLanguage):
    if localLanguage:
        t = gettext.translation('libeclectus', getLocaleDir(),
            languages=[localLanguage], fallback=False)
    else:
        t = gettext.translation('libeclectus', getLocaleDir(),
            fallback=False)
    return t

# database

def getDatabaseUrl():
    from cjklib.util import getConfigSettings
    configuration = getConfigSettings('Connection')
    return configuration['url']
    # TODO use own database once build support for several databases is given
    #base = os.path.dirname(os.path.abspath(__file__))
    #databaseFile = os.path.join(base, "libeclectus.db")
    #if not os.path.exists(databaseFile):
        #databaseFile = "/var/lib/libeclectus/libeclectus.db"
    #return 'sqlite:///%s' % databaseFile
