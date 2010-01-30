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

# file paths

FILE_PATHS = {'default': [u'/usr/local/share/eclectus',
        u'/usr/share/eclectus'],
    'cmn-caen-tan_ogg': [u'/usr/local/share/eclectus/cmn-caen-tan',
        u'/usr/share/eclectus/cmn-caen-tan'],
    'chi-balm-hsk1_ogg': [u'/usr/local/share/eclectus/chi-balm-hsk1',
        u'/usr/share/eclectus/chi-balm-hsk1'],
    'bw.png.segment': [
        u'/usr/local/share/eclectus/bw.png.segment/bw.png.segment',
        u'/usr/share/eclectus/bw.png.segment/bw.png.segment'],
    'jbw.png.segment': [
        u'/usr/local/share/eclectus/bw.png.segment/jbw.png.segment',
        u'/usr/share/eclectus/bw.png.segment/jbw.png.segment'],
    'tbw.png.segment': [
        u'/usr/local/share/eclectus/bw.png.segment/tbw.png.segment',
        u'/usr/share/eclectus/bw.png.segment/tbw.png.segment'],
    'bw.png': [u'/usr/local/share/eclectus/bw.png/bw.png',
        u'/usr/share/eclectus/bw.png/bw.png'],
    'jbw.png': [u'/usr/local/share/eclectus/bw.png/jbw.png',
        u'/usr/share/eclectus/bw.png/jbw.png'],
    'tbw.png': [u'/usr/local/share/eclectus/bw.png/tbw.png',
        u'/usr/share/eclectus/bw.png/tbw.png'],
    'order.gif': [u'/usr/local/share/eclectus/order.gif/order.gif',
        u'/usr/share/eclectus/order.gif/order.gif'],
    'jorder.gif': [u'/usr/local/share/eclectus/order.gif/jorder.gif',
        u'/usr/share/eclectus/order.gif/jorder.gif'],
    'torder.gif': [u'/usr/local/share/eclectus/order.gif/torder.gif',
        u'/usr/share/eclectus/order.gif/torder.gif'],
    'red.png': [u'/usr/local/share/eclectus/red.png/red.png',
        u'/usr/share/eclectus/red.png/red.png'],
    'jred.png': [u'/usr/local/share/eclectus/red.png/jred.png',
        u'/usr/share/eclectus/red.png/jred.png'],
    }
"""
File path map. The file paths will be checked in the order given.
'default' serves as a fall back given special semantics as the search key
is added to the given default path.
"""

def locatePath(name):
    """
    Locates a external file using a list of paths given in FILE_PATHS. Falls
    back to subdirectory 'files' in location of this module if no match is
    found. Returns None if no result
    """
    global FILE_PATHS
    if name in FILE_PATHS:
        paths = FILE_PATHS[name]
    else:
        paths = [os.path.join(path, name) \
            for path in FILE_PATHS['default']]

    for path in paths:
        if os.path.exists(path):
            return path
    else:
        modulePath = os.path.dirname(os.path.abspath(__file__))
        localPath = os.path.join(modulePath, 'files', name)
        if os.path.exists(localPath):
            return localPath

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
            languages=[localLanguage], fallback=True)
    else:
        t = gettext.translation('libeclectus', getLocaleDir(),
            fallback=True)
    return t

# script classes

UNICODE_SCRIPT_CLASSES = {'Han': [('2E80', '2E99'), ('2E9B', '2EF3'),
        ('2F00', '2FD5'), '3005', '3007', ('3021', '3029'),
        ('3038', '303A'), '303B', ('3400', '4DB5'), ('4E00', '9FCB'),
        ('F900', 'FA2D'), ('FA30', 'FA6D'), ('FA70', 'FAD9'),
        ('20000', '2A6D6'), ('2A700', '2B734'), ('2F800', '2FA1D')],
    'Hiragana': [('3041', '3096'), ('309D', '309E'), '309F'],
    'Katakana': [('30A1', '30FA'), ('30FD', '30FE'), '30FF',
        ('31F0', '31FF'), ('32D0', '32FE'), ('3300', '3357'),
        ('FF66', 'FF6F'), ('FF71', 'FF9D')],
    'Hangul': [('1100', '1159'), ('115F', '11A2'), ('11A8', '11F9'),
        ('3131', '318E'), ('3200', '321E'), ('3260', '327E'),
        ('AC00', 'D7A3'), ('FFA0', 'FFBE'), ('FFC2', 'FFC7'),
        ('FFCA', 'FFCF'), ('FFD2', 'FFD7'), ('FFDA', 'FFDC')],
    'Bopomofo': [('3105', '312D'), ('31A0', '31B7')],
}
"""
Mapping of CJK scripts to Unicode character ranges taken from
U{http://www.unicode.org/Public/5.1.0/ucd/Scripts.txt}.

Tuples are ranges C{from} C{to} and single entries reprsent single
characters.
"""

_codepointRangeDict = None

def getCJKScriptClass(char):
    """
    Returns the character's CJK-script, C{None} if not known or not a CJK
    script.
    """
    global _codepointRangeDict, UNICODE_SCRIPT_CLASSES
    if _codepointRangeDict is None:
        _codepointRangeDict = {}
        for scriptClass, ranges in UNICODE_SCRIPT_CLASSES.items():
            for charRange in ranges:
                if type(charRange) == type(()):
                    rangeFrom, rangeTo = charRange
                else:
                    rangeFrom, rangeTo = (charRange, charRange)
                _codepointRangeDict[(int(rangeFrom, 16),
                    int(rangeTo, 16))] = scriptClass

    for charRange, scriptClass in _codepointRangeDict.items():
        rangeFrom, rangeTo = charRange
        if rangeFrom <= ord(char) and ord(char) <= rangeTo:
            return scriptClass
    else:
        return None

# database

def getDatabaseUrl():
    try:
        from cjklib.util import getConfigSettings
        configuration = getConfigSettings('Connection')
        return configuration['url']
    except KeyError:
        print "Cannot find parameter 'url' in config file of cjklib."
        print "Please check /etc/cjklib.conf or ~/.cjklib.conf"
    # TODO use own database once build support for several databases is given
    #base = os.path.dirname(os.path.abspath(__file__))
    #databaseFile = os.path.join(base, "libeclectus.db")
    #if not os.path.exists(databaseFile):
        #databaseFile = "/var/lib/libeclectus/libeclectus.db"
    #return 'sqlite:///%s' % databaseFile
