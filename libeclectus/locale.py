# -*- coding: utf-8 -*-
u"""
Provides gettext access for libeclectus.

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

__all__ = ["setTranslationLanguage", "getTranslationLanguage", "gettext",
    "ngettext"]

import os.path
from gettext import translation

# i18n

_gettext = _ngettext = None

def gettext(*args):
    return _gettext(*args)

def ngettext(*args):
    return _ngettext(*args)

_language = None
def getTranslationLanguage():
    """
    Returns the language set with setTranslationLanguage().

    Not necessarily the language of the gettext catalog.
    """
    global _language
    return _language

def getLocaleDir():
    base = os.path.dirname(os.path.abspath(__file__))
    localeDir = os.path.join(base, "locale")
    if not os.path.exists(localeDir):
        localeDir = "/usr/share/locale"
    return localeDir

def setTranslationLanguage(localLanguage=None):
    global _gettext, _ngettext, _language
    _language = localLanguage
    if localLanguage:
        t = translation('libeclectus', getLocaleDir(),
            languages=[localLanguage], fallback=True)
    else:
        t = translation('libeclectus', getLocaleDir(),
            fallback=True)

    _gettext = t.ugettext
    _ngettext = t.ungettext

if _gettext is None:
    setTranslationLanguage()
