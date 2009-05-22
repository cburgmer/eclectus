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

from PyQt4 import QtCore
from PyQt4.QtCore import SIGNAL, QUrl, QString, QByteArray
from PyQt4.QtGui import QFont, QFontMetrics

currentFontFamily = None
currentFontMetrics = None

def encodeBase64(string):
    return unicode(QString(string).toUtf8().toBase64())

def decodeBase64(string):
    return unicode(QString.fromUtf8(QByteArray.fromBase64(
        QString(string).toAscii()).data()))

def fontExists(fontFamily):
    return QFont(fontFamily).exactMatch()

def fontHasChar(fontFamily, char):
    global currentFontFamily
    global currentFontMetrics

    if not currentFontFamily or currentFontFamily != fontFamily:
        currentFontFamily = fontFamily
        font = QFont(fontFamily)
        oldStrategy = font.styleStrategy()
        font.setStyleStrategy(oldStrategy and QFont.NoFontMerging)
        currentFontMetrics = QFontMetrics(font)
    return currentFontMetrics.inFont(QString(char).at(0))
