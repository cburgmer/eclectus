# -*- coding: utf-8 -*-
u"""
Provides HTML formatting services for dictionary queries.

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
import os.path
import re
import urllib

from cjklib.dbconnector import getDBConnector

from libeclectus import util
from libeclectus.chardb import CharacterDB
from libeclectus.dictionary import (getDictionary, getDefaultDictionary,
    getAvailableDictionaryNames)
from libeclectus.locale import gettext, ngettext, getTranslationLanguage

class DictionaryView:
    WEB_LINKS = {'all': ['getUnihanLink'],
        'zh-cmn-Hant': ['getCEDICTLink', 'getHanDeDictLink', 'getDictCNLink',
            'getEduTwLink'],
        'zh-cmn-Hans': ['getCEDICTLink', 'getHanDeDictLink', 'getDictCNLink'],
        'ja': [],
        'ko': [],
        'zh-yue-Hant': ['getCantoDictLink', 'getEduTwLink'],
        'zh-yue-Hans': ['getCantoDictLink', 'getEduTwLink'],
        'ja': ['getWWWJDICLink'],
        }
    """Links to websites for a given character string."""

    BIG_STROKE_ORDER_TYPE = 'bw.png.segment'
    """Stroke order type for stroke order category."""

    COMMONS_STROKE_ORDER_FALLBACK = {'zh-cmn-Hant': ['zh-cmn-Hans'],
        'ja': ['zh-cmn-Hant', 'zh-cmn-Hans'],
        'ko': ['zh-cmn-Hans'],
        'zh-yue-Hant': ['zh-cmn-Hans'],
        'zh-yue-Hans': ['zh-cmn-Hant'],
        'zh-cmn-Hans': ['zh-cmn-Hant']}
    """
    Fallback for Wikimedia Commons stroke order images for cases where default
    prefix doesn't exist.
    """

    COMMONS_STROKE_ORDER_PREFIX = {'zh-cmn-Hans': '', 'zh-cmn-Hant': 't',
        'zh-yue-Hant': 't', 'zh-yue-Hans': '', 'ja': 'j', 'ko': 't'}
    """Language dependant Wikimedia Commons stroke order image prefix."""

    @classmethod
    def needsDictionary(cls, method):
        return hasattr(getattr(cls, method), 'needsDictionary')

    def __init__(self, dictionary=None, dbConnectInst=None, databaseUrl=None,
        strokeOrderType=None, showAlternativeHeadwords=True, **options):

        self.db = dbConnectInst or getDBConnector(
            util.getDatabaseConfiguration(databaseUrl))

        self.showAlternativeHeadwords = showAlternativeHeadwords
        self.useExtraReadingInformation = options.get(
            'useExtraReadingInformation', False)

        self.availableDictionaryNames = getAvailableDictionaryNames(self.db)

        # get ditionary
        if dictionary in self.availableDictionaryNames:
            self._dictionary = getDictionary(dictionary, dbConnectInst=self.db,
                ignoreIllegalSettings=True, **options)
        else:
            translationLanguage = getTranslationLanguage()
            self._dictionary = getDefaultDictionary(translationLanguage,
                dbConnectInst=self.db, ignoreIllegalSettings=True, **options)

        self.dictionary = self._dictionary.PROVIDES
        self.reading = self._dictionary.reading
        self.language = self._dictionary.language
        self.characterDomain = self._dictionary.charDB.characterDomain
        self.compatibleCharacterDomains \
            = self._dictionary.charDB.getCompatibleCharacterDomains()

        # stroke order
        availableStrokeOrder = self.getAvailableStrokeOrderTypes()
        if strokeOrderType and strokeOrderType in availableStrokeOrder:
            self.strokeOrderType = strokeOrderType
        else:
            # don't show BIG_STROKE_ORDER_TYPE twice
            if self.BIG_STROKE_ORDER_TYPE in availableStrokeOrder:
                index = availableStrokeOrder.index(self.BIG_STROKE_ORDER_TYPE)
                del availableStrokeOrder[index]
            originalType = self.BIG_STROKE_ORDER_TYPE.replace('.segment', '')
            if originalType in availableStrokeOrder:
                index = availableStrokeOrder.index(originalType)
                del availableStrokeOrder[index]

            if availableStrokeOrder:
                self.strokeOrderType = availableStrokeOrder[0]
            else:
                self.strokeOrderType = None

    def settings(self):
        return {'strokeOrderType': self.strokeOrderType,
            'showAlternativeHeadwords': self.showAlternativeHeadwords,
            'useExtraReadingInformation': self.useExtraReadingInformation,
            'Transcription': self.reading,
            'Dictionary': self.dictionary,
            'Character Domain': self.characterDomain,
            'Update database url': self.db.databaseUrl
            }

    @classmethod
    def readSettings(cls, settingsDict):
        """Reads the settings from a dict of string values."""
        settings = {}
        if 'strokeOrderType' in settingsDict:
            settings['strokeOrderType'] \
                = unicode(settingsDict['strokeOrderType'])
        if 'showAlternativeHeadwords' in settingsDict:
            if settingsDict['showAlternativeHeadwords'] == 'True':
                settings['showAlternativeHeadwords'] = True
            else:
                settings['showAlternativeHeadwords'] = False
        if 'useExtraReadingInformation' in settingsDict:
            if settingsDict['useExtraReadingInformation'] == 'True':
                settings['useExtraReadingInformation'] = True
            else:
                settings['useExtraReadingInformation'] = False

        settings['reading'] = settingsDict.get('Transcription', None)
        settings['dictionary'] = settingsDict.get('Dictionary', None)
        settings['characterDomain'] = settingsDict.get('Character Domain', None)
        settings['databaseUrl'] = settingsDict.get('Update database url', None)

        return settings

    @staticmethod
    def _matchesInput(inputString, charString):
        regexEntities = []
        for entity in re.split('([\?\*])', inputString):
            if entity == '?':
                regexEntities.append('.')
            elif entity == '*':
                regexEntities.append('.*')
            else:
                regexEntities.append(re.escape(entity))
        inputRegex = re.compile(''.join(regexEntities))
        return inputRegex.match(charString)

    @staticmethod
    def _getDisplayCharStringRepresentation(charString, charAltString=None,
        forceBlocksOfFor=True):
        if forceBlocksOfFor:
            entitiesHtml = []
            entities = list(charString)
            for mult in range(0, (len(entities) - 1) / 4 + 1):
                blockOfFor = entities[mult * 4:(mult + 1) * 4]
                entitiesHtml.append('<span class="blockOfFor">%s</span>' \
                    % ''.join(blockOfFor))
            displayCharString = ''.join(entitiesHtml)
        else:
            displayCharString = charString

        if charAltString and charAltString != charString:
            return displayCharString \
                + DictionaryView._getAlternativeStringRepresentation(charAltString)
        else:
            return displayCharString

    @staticmethod
    def _getAlternativeStringRepresentation(charString):
        """
        Add nowrap rules for CJK brackets, something that should actually be
        done by the low level text rendering layer.
        """
        if len(charString) > 2:
            return u'<span style="white-space: nowrap;">（%s</span>' \
                    % charString[0] \
                + charString[1:-1] \
                + u'<span style="white-space: nowrap;">%s）</span>' \
                    % charString[-1]
        else:
            return u'<span style="white-space: nowrap;">（%s）</span>' \
                % charString

    @staticmethod
    def _getReadingRepresentation(string, forceBlocksOfFor=True):
        """
        Add nowrap rules for entities, something that keeps QtWebkit from
        breaking Pinyin syllables.
        """
        if not string:
            return ''
        entitiesHtml = []
        if forceBlocksOfFor:
            entities = string.split(' ')
            for mult in range(0, (len(entities) - 1) / 4 + 1):
                blockOfFor = entities[mult * 4:(mult + 1) * 4]
                entitiesHtml.append('<span class="blockOfFor">' \
                    + ' '.join(blockOfFor) + '</span>')
        else:
            for entity in string.split(' '):
                entitiesHtml.append(
                    '<span class="readingEntity">' + entity + '</span>')

        return ' '.join(entitiesHtml)

    @staticmethod
    def _getTranslationRepresentation(string):
        return string.strip('/').replace('/', u' / ')

    @staticmethod
    def _getVocabularyTable(dictResult, useAltFunc=lambda x, y: False,
        smallSpacing=False):
        htmlList = []
        for charString, charStringAlt, reading, translation in dictResult:
            if charString != charStringAlt \
                and useAltFunc(charString, charStringAlt):
                displayCharString \
                    = DictionaryView._getDisplayCharStringRepresentation(
                        charString, charStringAlt,
                        forceBlocksOfFor=not smallSpacing)
            else:
                displayCharString \
                    = DictionaryView._getDisplayCharStringRepresentation(
                        charString, forceBlocksOfFor=not smallSpacing)

            if len(charString) > 1:
                page = 'word'
            else:
                page = 'character'

            htmlList.append('<tr class="vocabularyEntry">' \
                + '<td class="character">' \
                + '<a class="character" href="#lookup(%s)">%s</a>' \
                    % (util.encodeBase64(page + ':' + charString),
                        displayCharString)
                + '</td>' \
                + '<td class="reading">%s</td>' \
                    % DictionaryView._getReadingRepresentation(reading,
                        forceBlocksOfFor=not smallSpacing) \
                + '<td class="translation">%s</td>' \
                    % DictionaryView._getTranslationRepresentation(translation) \
                + '</tr>')
        return '\n'.join(htmlList)

    # METHODS WITHOUT DATABASE ACCESS

    def getGeneralCharacterSection(self, inputString):
        output = '<span class="headword">%s</span>' % inputString

        if self.strokeOrderType:
            # get stroke order
            strokeOrderFunc, _ = self.STROKE_ORDER_SOURCES[self.strokeOrderType]
            strokeOrder = strokeOrderFunc(self, inputString)
            if strokeOrder:
                output += '<span class="strokeorder %s">%s</span>' \
                    % (self.strokeOrderType.replace('.', '_'), strokeOrder)

        return output

    def getMiniGeneralCharacterSection(self, inputString):
        return '<span class="headwordMini">%s</span>' % inputString

    def getGeneralWordSection(self, inputString):
        characterLinks = []
        for char in inputString:
            characterLinks.append(
                '<a class="character" href="#lookup(%s)">%s</a>' \
                % (util.encodeBase64(char), char))

        return '<span class="headword">%s</span>' % ''.join(characterLinks)

    def getMiniGeneralWordSection(self, inputString):
        characterLinks = []
        for char in inputString:
            characterLinks.append(
                '<a class="character" href="#lookup(%s)">%s</a>' \
                % (util.encodeBase64(char), char))

        return '<span class="headwordMini">%s</span>' % ''.join(characterLinks)

    # STROKE ORDER

    @classmethod
    def getStrokeOrderTypes(cls):
        return cls.STROKE_ORDER_SOURCES.keys()

    @classmethod
    def hasStrokeOrderData(cls, strokeOrderType):
        _, strokeOrderExist = cls.STROKE_ORDER_SOURCES[strokeOrderType]
        return strokeOrderExist(cls)

    @classmethod
    def getAvailableStrokeOrderTypes(cls):
        if not hasattr(cls , '_availableStrokeOrderTypes'):
            cls._availableStrokeOrderTypes = []
            for strokeOrderType in cls.getStrokeOrderTypes():
                if cls.hasStrokeOrderData(strokeOrderType):
                    cls._availableStrokeOrderTypes.append(strokeOrderType)

        return cls._availableStrokeOrderTypes[:]

    def strokeOrderFontSource(fontFamily):
        def getStrokeOrder(self, inputString, fontFamily):
            if util.fontHasChar(fontFamily, inputString):
                return '<span style="font-family:' + fontFamily + '">' \
                    + inputString + '</span>'

        return lambda self, inputString: getStrokeOrder(self, inputString,
            fontFamily)

    def strokeOrderImageSource(imageDirectory, fileType):
        def getStrokeOrder(self, inputString, imageDirectory, fileType):
            strokeOrderPath = util.locatePath(imageDirectory)

            filePath = os.path.join(strokeOrderPath, inputString + fileType)
            if os.path.exists(filePath):
                return '<img src="file://' \
                    + urllib.quote(filePath.encode('utf8')) + '" />'

        return lambda self, inputString: getStrokeOrder(self, inputString,
            imageDirectory, fileType)

    def commonsStrokeOrderImageSource(imageType):
        def getStrokeOrder(self, inputString, imageType):
            languages = [self.language]
            if self.language in self.COMMONS_STROKE_ORDER_FALLBACK:
                languages.extend(
                    self.COMMONS_STROKE_ORDER_FALLBACK[self.language])

            checkedPaths = set([])
            for language in languages:
                if language in self.COMMONS_STROKE_ORDER_PREFIX:
                    prefix = self.COMMONS_STROKE_ORDER_PREFIX[language]
                else:
                    prefix = ''
                strokeOrderPath = util.locatePath(prefix + imageType)
                if not strokeOrderPath:
                    continue
                filePath = os.path.join(strokeOrderPath,
                    inputString + '-' + prefix + imageType)
                if filePath not in checkedPaths and os.path.exists(filePath):
                    return '<img src="file://' \
                        + urllib.quote(filePath.encode('utf8')) + '" />'
                checkedPaths.add(filePath)

        return lambda self, inputString: getStrokeOrder(self, inputString,
            imageType)

    def commonsStrokeOrderImageSegmentedSource(imageType):
        def getStrokeOrder(self, inputString, imageType):
            languages = [self.language]
            if self.language in self.COMMONS_STROKE_ORDER_FALLBACK:
                languages.extend(
                    self.COMMONS_STROKE_ORDER_FALLBACK[self.language])

            checkedPaths = set([])
            for language in languages:
                if language in self.COMMONS_STROKE_ORDER_PREFIX:
                    prefix = self.COMMONS_STROKE_ORDER_PREFIX[language]
                else:
                    prefix = ''
                strokeOrderPath = util.locatePath(
                    prefix + imageType + '.segment')
                if not strokeOrderPath:
                    continue

                baseFilePath = os.path.join(strokeOrderPath,
                    inputString + '-' + prefix + imageType)
                fileRoot, fileExt = os.path.splitext(baseFilePath)
                filePath = fileRoot + '.0' + fileExt
                if filePath not in checkedPaths and os.path.exists(filePath):
                    imgFiles = []
                    for i in range(0, 100):
                        filePath = fileRoot + '.' + str(i) + fileExt
                        if os.path.exists(filePath):
                            imgFiles.append(filePath)
                        else:
                            break
                    return ''.join(['<img class="charactersegments" ' \
                        + 'src="file://' \
                        + urllib.quote(filePath.encode('utf8')) + '" />' \
                            for filePath in imgFiles])
                checkedPaths.add(filePath)

        return lambda self, inputString: getStrokeOrder(self, inputString,
            imageType)

    def strokeOrderFontExists(fontFamily):
        return lambda cls: util.fontExists(fontFamily)

    def strokeOrderImageExists(imageDirectory):
        return lambda cls: util.locatePath(imageDirectory) != None

    STROKE_ORDER_SOURCES = {
        'kanjistrokeorderfont': (strokeOrderFontSource('KanjiStrokeOrders'),
            strokeOrderFontExists('KanjiStrokeOrders')),
        'order.gif': (commonsStrokeOrderImageSource('order.gif'),
            strokeOrderImageExists('order.gif')),
        'red.png': (commonsStrokeOrderImageSource('red.png'),
            strokeOrderImageExists('red.png')),
        'bw.png': (commonsStrokeOrderImageSource('bw.png'),
            strokeOrderImageExists('bw.png')),
        'bw.png.segment': (commonsStrokeOrderImageSegmentedSource('bw.png'),
            strokeOrderImageExists('bw.png.segment')),
        'sod-utf8': (strokeOrderImageSource('sod-utf8', '.png'),
            strokeOrderImageExists('sod-utf8')),
        'soda-utf8': (strokeOrderImageSource('soda-utf8', '.gif'),
            strokeOrderImageExists('soda-utf8')),
    }

    def getStrokeOrderSection(self, inputString):
        strokeOrderFunc, _ \
            = self.STROKE_ORDER_SOURCES[self.BIG_STROKE_ORDER_TYPE]
        strokeOrder = strokeOrderFunc(self, inputString)

        if strokeOrder:
            return '<span class="bigstrokeorder">%s</span>' % strokeOrder
        else:
            return '<span class="meta">%s</span>' % gettext('no information')

    # LINK SECTION

    def getUnihanLink(self, charString):
        if len(charString) == 1:
            link = u'http://www.unicode.org/cgi-bin/GetUnihanData.pl?' \
                + u'codepoint=%s' % hex(ord(charString)).replace('0x', '')
            return link, gettext('Unicode Unihan database')

    def getEduTwLink(self, charString):
        if len(charString) == 1:
            relLink = self._dictionary.charDB.getCharacterIndex(charString, 'EduTwIndex')
            if relLink:
                link = u'http://www.edu.tw/files/site_content/M0001/bishuen/' \
                    + relLink
                return link, (u'常用國字標準字體筆順手冊 (%s)'
                    % gettext('edu.tw stroke order handbook'))

    def getWWWJDICLink(self, charString):
        link = u'http://www.csse.monash.edu.au/~jwb/cgi-bin/' \
            + u'wwwjdic.cgi?1MUJ%s' % charString
        return link, gettext('WWWJDIC Japanese-English dictionary')

    def getCEDICTLink(self, charString):
        link = u'http://us.mdbg.net/chindict/chindict.php?wdqchs=%s' \
            % charString
        return link, gettext('MDBG Chinese-English dictionary')

    def getHanDeDictLink(self, charString):
        link = u'http://www.chinaboard.de/chinesisch_deutsch.php?' \
            + u"sourceid=konqueror-search&skeys=%s" % charString
        return link, gettext('HanDeDict Chinese-German dictionary')

    def getDictCNLink(self, charString):
        link = u'http://dict.cn/%s.htm' % charString
        return link, u'海词词典 (Dict.cn)' # not i18n-able

    def getCantoDictLink(self, charString):
        link = u'http://www.cantonese.sheik.co.uk/dictionary/search/' \
            + '?searchtype=1&text=%s' % charString
        return link, gettext('CantoDict Cantonese-Mandarin-English dictionary')

    def getLinkSection(self, inputString):
        functions = []
        if self.language in self.WEB_LINKS:
            functions.extend(self.WEB_LINKS[self.language])
        if 'all' in self.WEB_LINKS:
            functions.extend(self.WEB_LINKS['all'])

        links = []
        for linkProc in functions:
            content = getattr(self, linkProc)(inputString)
            if content:
                links.append('<a class="crossLink" href="%s">%s</a>' % content)

        return "<ol><li>" + "</li>\n<li>".join(links) + "</li></ol>"

    # FUNCTIONS BASED ON DATABASE

    def getVariantSection(self, inputString):
        variantEntries = self._dictionary.getVariantsForHeadword(inputString)
        variants = [e.Headword for e in variantEntries
            if e.Headword != inputString]

        variantLinks = []
        for variant in variants:
            if variant == inputString:
                # e.g. 台 is listed as it's on variant, Unihan's policy
                continue
            variantLinks.append('<span class="character">' \
                + '<a class="character" href="#lookup(%s)">%s</a>' \
                    % (util.encodeBase64(variant), variant) \
                + '</span>')

        if not variantLinks:
            return ''
        else:
            return '<div class="variantSection">'\
                + '<span class="meta">%s</span> ' \
                    % ngettext("See variant:", "See variants:", len(variants)) \
                + ', '.join(variantLinks) \
                + '</div>'

    def getSimilarsSection(self, inputString):
        """Returns a section of headwords with similar shape."""
        similarEntries = self._dictionary.getSimilarsForHeadword(inputString,
            orderBy=['Reading'])
            #orderBy=['Reading', 'Headword']) # TODO doesn't work for CEDICT
        similars = [e.Headword for e in similarEntries
            if e.Headword != inputString]

        similarLinks = []
        for similar in similars:
            similarLinks.append('<span class="character">' \
                + '<a class="character" href="#lookup(%s)">%s</a>' \
                    % (util.encodeBase64(similar), similar) \
                + '</span>')

        if not similarLinks:
            return ''
        else:
            return '<div class="similarSection">'\
                + '<span class="meta">%s</span> ' \
                    % ngettext("See similar headword:",
                        "See similar headword:", len(similarLinks)) \
                + ', '.join(similarLinks) \
                + '</div>'

    def getMeaningSection(self, inputString):
        """
        Gets a list of entries for the given character string, sorted by reading
        with annotated alternative character writing, audio and vocab handle.
        """
        def getAudio(filePath):
            return (' <a class="audio" href="#play(%s)">%s</a>'
                % (urllib.quote(filePath.encode('utf8')), gettext('Listen')))
                #audioHtml = ' <a class="audio" href="#" onclick="new Audio(\'%s\').play(); return false;">%s</a>' \
                    #% (urllib.quote(filePath.encode('utf8')), gettext('Listen'))
                #audioHtml = ' <audio src="%s" id="audio_%s" autoplay=false></audio><a class="audio" href="#" onClick="document.getElementById(\'audio_%s\').play(); return false;">%s</a>' \
                    #% (urllib.quote(filePath.encode('utf8')), reading, reading, gettext('Listen'))

        readings = []
        translations = {}
        translationIndex = {}
        alternativeHeadwords = []
        alternativeHeadwordIndex = {}

        # TODO index calculation is broken, e.g. 说
        # TODO cache
        dictResult = self._dictionary.getForHeadword(inputString)

        for idx, entry in enumerate(dictResult):
            _, charStringAlt, reading, translation = entry

            # get unique sorted readings
            if reading not in readings:
                readings.append(reading)

            # save translation, take care of double entries
            if reading not in translations:
                translations[reading] = []
                translationIndex[reading] = idx
            if translation not in translations[reading]:
                translations[reading].append(translation)

            # save alternative headword, save link to translation
            if charStringAlt not in alternativeHeadwords:
                alternativeHeadwords.append(charStringAlt)
                alternativeHeadwordIndex[charStringAlt] = []
            # save link to translation
            alternativeHeadwordIndex[charStringAlt].append(
                translations[reading].index(translation))

        htmlList = []
        # show alternative headword when a) several different ones exist,
        #   b) several entries exist, c) different to headword
        if self.showAlternativeHeadwords and alternativeHeadwords \
            and (len(alternativeHeadwords) > 1 \
                or inputString not in alternativeHeadwords):
            altHeadwordHtml = []
            for altHeadword in alternativeHeadwords:
                if len(inputString) > 1:
                    className = "word"
                else:
                    className = "character"

                entry = '<span class="%s">' % className \
                    + '<a class="character" href="#lookup(%s)">%s</a></span>' \
                        % (util.encodeBase64(altHeadword), altHeadword)

                if len(readings) > 1 or len(translations[readings[0]]) > 1:
                    indices = [str(i + 1) for i \
                        in alternativeHeadwordIndex[altHeadword]]
                    altHeadwordHtml.append('<li>' + entry \
                        + '<span class="alternativeHeadwordIndex">%s</span>' \
                            % ' '.join(indices) \
                        + '</li>')
                else:
                    altHeadwordHtml.append('<li>%s</li>' % entry)

            htmlList.append('<p><ul class="alternativeHeadword">%s</ul></p>' \
                % ''.join(altHeadwordHtml))

        # show entries
        if readings:
            htmlList.append('<table class="meaning">')

            for reading in readings:
                # get audio if available
                #filePath, audioHtml = getAudio(reading)
                filePath, audioHtml = ('', '') # TODO
                # get reading
                readingEntry = '<a class="reading" href="#lookup(%s)">%s</a>' \
                    % (util.encodeBase64(reading),
                        self._getReadingRepresentation(reading,
                            forceBlocksOfFor=False))
                # get translations
                translationEntries = []
                for translation in translations[reading]:
                    translationEntries.append('<li class="translation">' \
                        + '<a class="addVocabulary" ' \
                        + 'href="#addvocab(%s;%s;%s;%s)"></a>' \
                            % (util.encodeBase64(inputString),
                                util.encodeBase64(reading),
                                util.encodeBase64(translation),
                                util.encodeBase64(filePath)) \
                        + self._getTranslationRepresentation(translation) \
                        + '</li>')
                translationString = ''.join(translationEntries)
                # create table entry
                htmlList.append('<tr class="meaningEntry">' \
                            + '<td class="reading">%s%s</td>' \
                                % (readingEntry, audioHtml) \
                            + '<td><ol start="%d">%s</ol></td>' \
                                % (translationIndex[reading] + 1,
                                    translationString) \
                            + '</tr>')

            htmlList.append('</table>')
        else:
            htmlList.append('<span class="meta">%s</span>' \
                % gettext('No dictionary entries found'))

        return '\n'.join(htmlList)

    def _getContainedEntitiesSection(self, inputString, dictResult):
        """
        Gets a list of dictionary entries for single characters of the given
        character string.
        """
        def sortDictionaryResults(x, y):
            charStringA, charStringAltA, _, _ = x
            charStringB, charStringAltB, _, _ = y
            a = inputString.find(charStringA)
            if a < 0:
                a = inputString.find(charStringAltA)
            b = inputString.find(charStringB)
            if b < 0:
                b = inputString.find(charStringAltB)
            if a == b:
                return len(charStringA) - len(charStringB)
            else:
                return a - b

        htmlList = []
        if dictResult:
            dictResult.sort(sortDictionaryResults)

            htmlList.append('<table class="containedVocabulary">')
            # don't display alternative if the charString is found
            #   in the given string
            showAlternative = lambda charString, _: \
                    (inputString.find(charString) < 0)
            htmlList.append(self._getVocabularyTable(dictResult,
                useAltFunc=showAlternative, smallSpacing=True))
            htmlList.append('</table>')

        else:
            htmlList.append('<span class="meta">%s</span>' \
                % gettext('No entries found'))

        return '\n'.join(htmlList)

    def _searchDictionaryHeadwordEntities(self, searchString, limit=None):
        #TODO Caching would help here, as the search for the headword
            #is already done somewhere else before.
        #TODO Work on tonal changes for some characters in Mandarin
        #TODO Get proper normalisation or collation for reading column.
        entriesSet = set()
        entries = [(e.Headword, e.Reading)
            for e in self._dictionary.getForHeadword(searchString)]
        if not entries:
            entries = [(searchString, None)]

        for headword, reading in entries:
            entriesSet.update(self._dictionary.getEntitiesForHeadword(
                headword, reading, limit=limit))
        if limit:
            return list(entriesSet)[:limit]
        else:
            return list(entriesSet)

    def getHeadwordContainedCharactersSection(self, inputString):
        """
        Gets a list of dictionary entries for characters of the given character
        string.
        """
        dictResult = self._searchDictionaryHeadwordEntities(inputString)
        return self._getContainedEntitiesSection(inputString, dictResult)

    def getHeadwordContainedVocabularySection(self, inputString):
        """
        Gets a list of dictionary entries for substrings of the given character
        string.
        """
        dictResult = self._dictionary.getSubstringsForHeadword(inputString)
        return self._getContainedEntitiesSection(inputString, dictResult)

    @util.attr('needsDictionary')
    def getVocabularySection(self, inputString):
        # we only need 4 entries, but because of double entries we might end up
        #   with some being merged, also need +1 to show the "more entries"
        #   play safe and select 10
        # TODO true contains
        dictResult = self._dictionary.getForHeadword(
            '*' + inputString + '*', orderBy=['Weight'], limit=10)

        htmlList = []
        if dictResult:
            htmlList.append('<table class="vocabulary">')
            # don't display alternative if the charString is found
            #   in the given string
            showAlternative = lambda charString, _: \
                    (charString.find(inputString) < 0)
            htmlList.append(self._getVocabularyTable(dictResult[:4],
                useAltFunc=showAlternative))
            htmlList.append('</table>')

            if len(dictResult) > 4:
                htmlList.append(
                    '<a class="meta" href="#lookup(%s)">%s</a>' \
                        % (util.encodeBase64('vocabulary' \
                            + ':' + inputString), gettext('All entries...')))
        else:
            htmlList.append('<span class="meta">%s</span>' \
                % gettext('No entries found'))

        return '\n'.join(htmlList)

    @util.attr('needsDictionary')
    def getFullVocabularySection(self, inputString):
        """
        Gets a list of dictionary entries with exact matches and matches
        including the given character string.
        """
        dictResult = self._dictionary.getForHeadword(inputString)

        htmlList = []
        htmlList.append('<table class="fullVocabulary">')

        # exact matches
        htmlList.append('<tr><td colspan="3"><h3>%s</h3></td></tr>' \
            % gettext('Dictionary entries'))
        if dictResult:
            showAlternative = lambda charString, _: (charString != inputString)
            htmlList.append(self._getVocabularyTable(dictResult,
                useAltFunc=showAlternative))
        else:
            htmlList.append(
                '<tr><td colspan="3"><span class="meta">%s</span></td></tr>' \
                    % gettext('No exact matches found'))

        # other matches
        # TODO true contains
        dictResult = self._dictionary.getForHeadword('*' + inputString + '*',
            orderBy=['Reading'])

        if dictResult:
            htmlList.append('<tr><td colspan="3"><h3>%s</h3></td></tr>' \
                % gettext('Other matches'))

            # don't display alternative if the charString is found in the
            #   given string
            showAlternative = lambda charString, _: \
                    (charString.find(inputString) < 0)
            htmlList.append(self._getVocabularyTable(dictResult,
                useAltFunc=showAlternative))

        htmlList.append('</table>')

        return '\n'.join(htmlList)

    def _getDictionaryInfo(self, char, dictResult=None):
        readings = []
        translations = []

        dictResult = (dictResult or self._dictionary.getForHeadword(char))

        if dictResult:
            # separate readings from translation
            for _, _, reading, translation in dictResult:
                if reading not in readings:
                    readings.append(reading)
                if translation and translation not in translations:
                    translations.append(
                        self._getTranslationRepresentation(translation))

        return ' <span class="reading">%s</span>' % ', '.join(readings) \
            + ' <span class="translation">%s</span>' \
                % ' / '.join(translations)

    def getCharacterWithComponentSection(self, inputString):
        """Gets a list of characters with the given character as component."""
        chars = self._dictionary.charDB.getCharactersForComponents([inputString])

        if inputString in chars:
            chars.remove(inputString)

        if chars:
            characterLinks = []
            for char in chars:
                #characterLinks.append(
                    #'<a class="character" href="#lookup(%s)">%s</a>' \
                        #% (util.encodeBase64(char), char))
                characterLinks.append('<li><span class="character">' \
                    + '<a class="character" href="#lookup(%s)">%s</a>' \
                        % (util.encodeBase64(char),  char) \
                    + '</span>%s</li>' % self._getDictionaryInfo(char))
            return '<div class="components"><ul>%s</ul></div>' \
                % ' '.join(characterLinks)
        else:
            return '<span class="meta">%s</span>' % gettext('No entries found')

    def getDecompositionTreeSection(self, inputString):
        """Gets a tree of components included in the given character."""
        def getLayer(decompTree, isSubTree=False):
            if type(decompTree) != type(()):
                char = decompTree
                if char != u'？':
                    if char in seenEntry:
                        return '<span class="entry">' \
                            + '<span class="character">%s</span>' % char \
                            + '</span>'
                    else:
                        seenEntry.add(char)
                        return '<span class="entry"><span class="character">' \
                            + '<a class="character" href="#lookup(%s)">%s</a>' \
                                % (util.encodeBase64(char),  char) \
                            + '</span>%s</span>' % self._getDictionaryInfo(char)
                else:
                    return '<span class="entry meta">%s</span>' \
                        % gettext('unknown')
            else:
                layout, char, tree = decompTree
                if char:
                    if isSubTree:
                        head = layout + '<span class="character">' \
                            + '<a class="character" href="#lookup(%s)">%s</a>' \
                                % (util.encodeBase64(char),  char) \
                            + '</span>' \
                            + self._getDictionaryInfo(char)
                    else:
                        # don't show dictionary information for the root element
                        head = layout \
                            + '<span class="character">%s</span>' % char
                else:
                    head = layout

                subLayer = []
                for idx, entry in enumerate(tree):
                    cssClass = 'decomposition'
                    if idx == len(tree) - 1:
                        cssClass += ' last'
                    subLayer.append('<li class="%s">%s</li>' \
                        % (cssClass, getLayer(entry, isSubTree=True)))
                return '<span class="entry">%s<ul>%s</ul></span>' \
                    % (head, ''.join(subLayer))

        decompTree = self._dictionary.charDB.getCharacterDecomposition(inputString)
        if decompTree:
            seenEntry = set()
            return '<div class="tree">%s</div>' % getLayer(decompTree)
        else:
            return '<span class="meta">%s</span>' % gettext('No entry found')

    def _searchDictionarySamePronunciationAs(self, searchString, limit=None):
        """
        Searches the dictionary for all characters that have the same reading
        as the given headword.
        """
        entriesSet = set()
        # TODO cache
        for e in self._dictionary.getForHeadword(searchString):
            entriesSet.update(self._dictionary.getForReading(
                e.Reading, limit=limit))
        if searchString in entriesSet:
            entriesSet.remove(searchString)
        if limit:
            return list(entriesSet)[:limit]
        else:
            return list(entriesSet)

    def getCharacterWithSamePronunciationSection(self, inputString):
        """Gets a list of characters with the same pronunciation."""
        dictResult = self._searchDictionarySamePronunciationAs(inputString)

        # group by reading and character
        charDict = {}
        for char, charAlt, reading, translation in dictResult:
            if reading not in charDict:
                charDict[reading] = {}
            if char not in charDict[reading]:
                charDict[reading][char] = []
            charDict[reading][char].append(
                (char, charAlt, reading, translation))

        if charDict:
            html = ''
            for reading in sorted(charDict.keys(), reverse=True):
                characterLinks = []
                for char in charDict[reading]:
                    characterLinks.append('<li><span class="character">' \
                        + '<a class="character" href="#lookup(%s)">%s</a>' \
                            % (util.encodeBase64(char),  char) \
                        + '</span>%s</li>' % self._getDictionaryInfo(char,
                            charDict[reading][char]))
                html += '<h3>%s</h3>' % reading \
                    + '<ul>%s</ul>' % ' '.join(characterLinks)

            return '<div class="samereading">' + html + '</div>'
        else:
            return '<span class="meta">%s</span>' % gettext('No entries found')

    def getVocabularySearchSection(self, inputString):
        """
        Gets the search results for the given string including exact maches
        and a shortened list of similar results and results including the given
        string.
        """
        htmlList = []
        htmlList.append('<table class="search">')

        # exact hits
        exactDictResult = self._dictionary.getFor(inputString,
            orderBy=['Weight'])

        if exactDictResult:
            htmlList.append('<tr><td colspan="3"><h3>%s</h3></td></tr>' \
                % gettext('Matches'))
            # match against input string with regular expression
            htmlList.append(self._getVocabularyTable(exactDictResult,
                useAltFunc=lambda x, y: \
                    self._matchesInput(inputString, y) \
                    and not self._matchesInput(inputString, x)))


        # similar pronunciation
        similarDictResult = self._dictionary.getForSimilarReading(
            inputString, orderBy=['Weight'], limit=5)

        if similarDictResult:
            htmlList.append('<tr><td colspan="3"><h3>%s</h3></td></tr>' \
                % gettext('Similar pronunciations'))
            htmlList.append(self._getVocabularyTable(similarDictResult[:4]))

            if len(similarDictResult) > 4:
                htmlList.append('<tr><td colspan="3">' \
                    + '<a class="meta" href="#lookup(%s)">%s</a>' \
                        % (util.encodeBase64('similar' + ':' \
                            + inputString), gettext('All entries...'))
                    + '</td></tr>')


        # other matches
        # TODO optimize and include other matches in exact run, after all
        #   translation will be all searched with LIKE '% ... %'
        otherDictResult = self._dictionary.getFor('*' + inputString + '*',
            orderBy=['Weight'])

        if otherDictResult:
            htmlList.append('<tr><td colspan="3"><h3>%s</h3></td></tr>' \
                % gettext('Other matches'))
            augmentedInput = '*' + inputString + '*'
            htmlList.append(self._getVocabularyTable(otherDictResult[:4],
                useAltFunc=lambda x, y: \
                    self._matchesInput(inputString, y) \
                    and not self._matchesInput(inputString, x)))

            if len(otherDictResult) > 4:
                htmlList.append('<tr><td colspan="3">' \
                    + '<a class="meta" href="#lookup(%s)">%s</a>' \
                        % (util.encodeBase64('othervocabulary' + ':' \
                            + inputString), gettext('All entries...'))
                    + '</td></tr>')

        # handle 0 result cases
        if not exactDictResult:
            if not similarDictResult and not otherDictResult:
                htmlList.append('<tr><td colspan="3">'\
                    + '<span class="meta">%s</span>' \
                        % gettext('No matches found') \
                    + '</td></tr>')
            else:
                htmlList.insert(0, '<tr><td colspan="3">'\
                    + '<span class="meta">%s</span>' \
                        % gettext('No exact matches found') \
                    + '</td></tr>')

        htmlList.append('</table>')

        return '\n'.join(htmlList)

    @util.attr('needsDictionary')
    def getOtherVocabularySearchSection(self, inputString):
        """
        Gets a list of vocabulary entries containing the given inputString.
        """
        htmlList = []

        # TODO use caching
        dictResult = self._dictionary.getFor('*' + inputString + '*',
            orderBy=['Weight'])

        if dictResult:
            htmlList.append('<table class="otherVocabulary">')
            htmlList.append('<tr><td colspan="3"><h3>%s</h3></td></tr>' \
                % gettext('Other matches'))
            augmentedInput = '*' + inputString + '*'
            htmlList.append(self._getVocabularyTable(dictResult,
                useAltFunc=lambda x, y: \
                    self._matchesInput(inputString, y) \
                    and not self._matchesInput(inputString, x)))
            htmlList.append('</table>')

        else:
            htmlList.append('<span class="meta">%s</span>' \
                    % gettext('No matches found'))

        return '\n'.join(htmlList)

    @util.attr('needsDictionary')
    def getSimilarVocabularySearchSection(self, inputString):
        """
        Gets a list of vocabulary entries with pronunciation similar to the
        given string.
        """
        htmlList = []

        dictResult = self._dictionary.getForSimilarReading(inputString,
            orderBy=['Reading'])

        if dictResult:
            htmlList.append('<table class="similarVocabulary">')
            htmlList.append('<tr><td colspan="3"><h3>%s</h3></td></tr>' \
                % gettext('Similar pronunciations'))
            htmlList.append(self._getVocabularyTable(dictResult))
            htmlList.append('</table>')

        else:
            htmlList.append('<span class="meta">%s</span>' \
                % gettext('No matches found'))

        return '\n'.join(htmlList)
