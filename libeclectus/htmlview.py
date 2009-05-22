# -*- coding: utf-8 -*-
u"""
Provides HTML formatting services.

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

from PyKDE4.kdecore import i18n, i18np

from libeclectus import util

class HtmlView:
    FILE_PATHS = {'default': [u'/usr/share/eclectus'],
        'chi-balm-hsk1_ogg': [u'/usr/share/eclectus/chi-balm-hsk1_ogg'],
        'bw.png.segment': [u'/usr/share/eclectus/commons/bw.png.segment'],
        'jbw.png.segment': [u'/usr/share/eclectus/commons/jbw.png.segment'],
        'bw.png': [u'/usr/share/eclectus/commons/bw.png'],
        'jbw.png': [u'/usr/share/eclectus/commons/jbw.png'],
        'order.gif': [u'/usr/share/eclectus/commons/order.gif'],
        'torder.gif': [u'/usr/share/eclectus/commons/torder.gif'],
        'jorder.gif': [u'/usr/share/eclectus/commons/jorder.gif'],
        'red.png': [u'/usr/share/eclectus/commons/red.png'],
        'sod-utf8': [u'/usr/share/eclectus/sod-utf8'],
        'soda-utf8': [u'/usr/share/eclectus/soda-utf8'],
        }
    """
    File path map. The file paths will be checked in the order given.
    'default' servers as a fall back given special semantics as the search key
    is added to the given default path.
    """

    WEB_LINKS = {'all': ['getUnihanLink'],
        'zh-cmn-Hant': ['getCEDICTLink', 'getHanDeDictLink', 'getDictCNLink'],
        'zh-cmn-Hans': ['getCEDICTLink', 'getHanDeDictLink', 'getDictCNLink'],
        'ja': [],
        'ko': [],
        'zh-yue': [],
        'ja': ['getWWWJDICLink'],
        }
    """Links to websites for a given character string."""

    BIG_STROKE_ORDER_TYPE = 'bw.png.segment'
    """Stroke order type for stroke order category."""

    COMMONS_STROKE_ORDER_FALLBACK = {'zh-cmn-Hant': ['zh-cmn-Hans'],
        'ja': ['zh-cmn-Hant', 'zh-cmn-Hans'],
        'ko': ['zh-cmn-Hans'],
        'zh-yue': ['zh-cmn-Hans'],
        'zh-cmn-Hans': ['zh-cmn-Hant']}
    """
    Fallback for Wikimedia Commons stroke order images for cases where default
    prefix doesn't exist.
    """

    COMMONS_STROKE_ORDER_PREFIX = {'zh-cmn-Hans': '', 'zh-cmn-Hant': 't',
        'zh-yue': 't', 'ja': 'j', 'ko': 't'}
    """Language dependant Wikimedia Commons stroke order image prefix."""

    METHODS_NEED_DICTIONARY = ['getVocabularySection',
        'getFullVocabularySection', 'getVocabularySearchSection'
        'getOtherVocabularySearchSection', 'getSimilarVocabularySearchSection']
    """Methods that need a dictionary present to work."""

    def __init__(self, charInfo, strokeOrderType=None,
        showAlternativeHeadwords=True, useExtraReadingInformation=False):
        self.charInfo = charInfo
        self.showAlternativeHeadwords = showAlternativeHeadwords
        self.useExtraReadingInformation = useExtraReadingInformation

        if strokeOrderType and strokeOrderType in self.getStrokeOrderTypes():
            self.strokeOrderType = strokeOrderType
        else:
            available = self.getAvailableStrokeOrderTypes()
            # don't show BIG_STROKE_ORDER_TYPE twice
            if self.BIG_STROKE_ORDER_TYPE in available:
                del available[available.index(self.BIG_STROKE_ORDER_TYPE)]
            if available:
                self.strokeOrderType = available[0]
            else:
                self.strokeOrderType = None

    @classmethod
    def locatePath(cls, name):
        """
        Locates a external file using a list of paths given in FILE_PATHS. Falls
        back to subdirectory 'files' in location of this module if no match is
        found. Returns None if no result
        """
        if name in cls.FILE_PATHS:
            paths = cls.FILE_PATHS[name]
        else:
            paths = [os.path.join(path, name) \
                for path in cls.FILE_PATHS['default']]

        for path in paths:
            if os.path.exists(path):
                return path
        else:
            modulePath = os.path.dirname(os.path.abspath(__file__))
            localPath = os.path.join(modulePath, 'files', name)
            if os.path.exists(localPath):
                return localPath

    def settings(self):
        return {'strokeOrderType': self.strokeOrderType,
            'showAlternativeHeadwords': self.showAlternativeHeadwords,
            'useExtraReadingInformation': self.useExtraReadingInformation}

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
                + HtmlView._getAlternativeStringRepresentation(charAltString)
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
                    = HtmlView._getDisplayCharStringRepresentation(charString,
                        charStringAlt, forceBlocksOfFor=not smallSpacing)
            else:
                displayCharString \
                    = HtmlView._getDisplayCharStringRepresentation(charString,
                        forceBlocksOfFor=not smallSpacing)

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
                    % HtmlView._getReadingRepresentation(reading,
                        forceBlocksOfFor=not smallSpacing) \
                + '<td class="translation">%s</td>' \
                    % HtmlView._getTranslationRepresentation(translation) \
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
            strokeOrderPath = self.locatePath(imageDirectory)

            filePath = os.path.join(strokeOrderPath, inputString + fileType)
            if os.path.exists(filePath):
                return '<img src="file://' \
                    + urllib.quote(filePath.encode('utf8')) + '" />'

        return lambda self, inputString: getStrokeOrder(self, inputString,
            imageDirectory, fileType)

    def commonsStrokeOrderImageSource(imageType):
        def getStrokeOrder(self, inputString, imageType):
            languages = [self.charInfo.language]
            if self.charInfo.language in self.COMMONS_STROKE_ORDER_FALLBACK:
                languages.extend(
                    self.COMMONS_STROKE_ORDER_FALLBACK[self.charInfo.language])

            checkedPaths = set([])
            for language in languages:
                if language in self.COMMONS_STROKE_ORDER_PREFIX:
                    prefix = self.COMMONS_STROKE_ORDER_PREFIX[language]
                else:
                    prefix = ''
                strokeOrderPath = self.locatePath(prefix + imageType)
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
            languages = [self.charInfo.language]
            if self.charInfo.language in self.COMMONS_STROKE_ORDER_FALLBACK:
                languages.extend(
                    self.COMMONS_STROKE_ORDER_FALLBACK[self.charInfo.language])

            checkedPaths = set([])
            for language in languages:
                if language in self.COMMONS_STROKE_ORDER_PREFIX:
                    prefix = self.COMMONS_STROKE_ORDER_PREFIX[language]
                else:
                    prefix = ''
                strokeOrderPath = self.locatePath(
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
        return lambda cls: cls.locatePath(imageDirectory) != None

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
            return '<span class="meta">%s</span>' % i18n('no information')

    # LINK SECTION

    def getUnihanLink(self, charString):
        if len(charString) == 1:
            link = u'http://www.unicode.org/cgi-bin/GetUnihanData.pl?' \
                + u'codepoint=%s' % hex(ord(charString)).replace('0x', '')
            return link, i18n('Unicode Unihan database')

    def getWWWJDICLink(self, charString):
        link = u'http://www.csse.monash.edu.au/~jwb/cgi-bin/' \
            + u'wwwjdic.cgi?1MUJ%s' % charString
        return link, i18n('WWWJDIC Japanese-English dictionary')

    def getCEDICTLink(self, charString):
        link = u'http://us.mdbg.net/chindict/chindict.php?wdqchs=%s' \
            % charString
        return link, i18n('MDBG Chinese-English dictionary')

    def getHanDeDictLink(self, charString):
        link = u'http://www.chinaboard.de/chinesisch_deutsch.php?' \
            + u"sourceid=konqueror-search&skeys=%s" % charString
        return link, i18n('HanDeDict Chinese-German dictionary')

    def getDictCNLink(self, charString):
        link = u'http://dict.cn/%s.htm' % charString
        return link, u'海词词典 (Dict.cn)' # not i18n-able

    def getLinkSection(self, inputString):
        functions = []
        if self.charInfo.language in self.WEB_LINKS:
            functions.extend(self.WEB_LINKS[self.charInfo.language])
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
        if not self.charInfo.dictionary:
            if len(inputString) != 1:
                return ''
            else:
                variants = self.charInfo.getCharacterVariants(inputString) # TODO
        else:
            variants = self.charInfo.getHeadwordVariants(inputString)

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
                    % i18np("See variant:", "See variants:", len(variants)) \
                + ', '.join(variantLinks) \
                + '</div>'

    def getMeaningSection(self, inputString):
        """
        Gets a list of entries for the given character string, sorted by reading
        with annotated alternative character writing, audio and vocab handle.
        """
        def getAudio(reading):
            filePath = ''
            fileName = self.charInfo.getPronunciationFile(reading)
            if fileName:
                baseDir, subFilePath = fileName.split(os.sep, 1)
                prependDir = self.locatePath(baseDir)
                if not prependDir:
                    return '', ''

                path = os.path.join(prependDir, subFilePath)
                if os.path.exists(path):
                    filePath = path
            if filePath:
                audioHtml = ' <a class="audio" href="#play(%s)">%s</a>' \
                    % (urllib.quote(filePath.encode('utf8')), i18n('Listen'))
            else:
                audioHtml = ''
            return filePath, audioHtml

        readings = []
        translations = {}
        translationIndex = {}
        alternativeHeadwords = []
        alternativeHeadwordIndex = {}

        # TODO index calculation is broken, e.g. 说
        if self.charInfo.dictionary:
            dictResult = self.charInfo.searchDictionaryExactHeadword(
                inputString)

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

        if len(inputString) == 1 \
            and (not self.charInfo.dictionary \
                or self.useExtraReadingInformation):
            characterReadings \
                = self.charInfo.getReadingForCharacter(inputString)
            otherPronunciations = list(set(characterReadings) - set(readings))
            otherPronunciations.sort()
        else:
            otherPronunciations = []

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
                filePath, audioHtml = getAudio(reading)
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
        elif self.charInfo.dictionary:
            htmlList.append('<span class="meta">%s</span>' \
                % i18n('No dictionary entries found'))

        # show pronunciations not included in dictionary
        if otherPronunciations:
            pronunciationEntries = []
            for reading in otherPronunciations:
                # get audio if available
                filePath, audioHtml = getAudio(reading)

                pronunciationEntries.append(
                    '<a class="reading" href="#lookup(%s)">%s</a>' \
                        % (util.encodeBase64(reading),
                            self._getReadingRepresentation(reading,
                            forceBlocksOfFor=False)) \
                    + audioHtml \
                    + '<a class="addVocabulary" href="#addvocab(%s;%s;;%s)">' \
                        % (util.encodeBase64(inputString),
                            util.encodeBase64(reading),
                            util.encodeBase64(filePath)) \
                    + '</a>')
            if readings:
                label = i18n('Other pronunciations:')
            else:
                label = i18n('Pronunciations:')
            htmlList.append('<p>' \
                + '<span class="meta">%s</span> ' % label \
                + '<span class="reading">%s</span>' \
                    % ', '.join(pronunciationEntries) \
                + '</p>')
        elif not self.charInfo.dictionary:
            htmlList.append('<span class="meta">%s</span>' \
                % i18n('No entries found'))

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
        if self.charInfo.dictionary:
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
                    % i18n('No entries found'))
        else:
            characterWiseReading \
                = self.charInfo.getReadingForCharString(inputString)
            pronunciationEntries = []
            for idx, readingList in enumerate(characterWiseReading):
                if readingList:
                    pronunciationEntries.append('<tr class="vocabularyEntry">' \
                        + '<td class="character">' \
                        + '<a class="character" href="#lookup(%s)">%s</a>' \
                            % (util.encodeBase64(inputString[idx]),
                                inputString[idx]) \
                        + '</td>' \
                        + '<td class="reading">%s</td>' \
                            % ', '.join(readingList) \
                        + '</tr>')
            if pronunciationEntries:
                htmlList.append('<table class="containedVocabulary">')
                htmlList.extend(pronunciationEntries)
                htmlList.append('</table>')
            else:
                htmlList.append('<span class="meta">%s</span>' \
                    % i18n('No entries found'))

        return '\n'.join(htmlList)

    def getHeadwordContainedCharactersSection(self, inputString):
        """
        Gets a list of dictionary entries for characters of the given character
        string.
        """
        if self.charInfo.dictionary:
            dictResult = self.charInfo.searchDictionaryHeadwordEntities(
                inputString)
        else:
            dictResult = []
        return self._getContainedEntitiesSection(inputString, dictResult)

    def getHeadwordContainedVocabularySection(self, inputString):
        """
        Gets a list of dictionary entries for substrings of the given character
        string.
        """
        if self.charInfo.dictionary:
            dictResult = self.charInfo.searchDictionaryHeadwordSubstrings(
                inputString)
        else:
            dictResult = []
        return self._getContainedEntitiesSection(inputString, dictResult)

    def getVocabularySection(self, inputString):
        if not self.charInfo.dictionary:
            return ''

        # we only need 4 entries, but because of double entries we might end up
        #   with some being merged, also need +1 to show the "more entries"
        #   play safe and select 10
        dictResult = self.charInfo.searchDictionaryContainingHeadword(
            inputString, orderBy=['Weight'], limit=10)

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
                        % (util.encodeBase64(i18n('vocabulary') + ':' \
                            + inputString), i18n('All entries...')))
        else:
            htmlList.append('<span class="meta">%s</span>' \
                % i18n('No entries found'))

        return '\n'.join(htmlList)

    def getFullVocabularySection(self, inputString):
        """
        Gets a list of dictionary entries with exact matches and matches
        including the given character string.
        """
        if not self.charInfo.dictionary:
            return ""

        dictResult = self.charInfo.searchDictionaryExactHeadword(inputString)

        htmlList = []
        htmlList.append('<table class="fullVocabulary">')

        # exact matches
        htmlList.append('<tr><td colspan="3"><h3>%s</h3></td></tr>' \
            % i18n('Dictionary entries'))
        if dictResult:
            showAlternative = lambda charString, _: (charString != inputString)
            htmlList.append(self._getVocabularyTable(dictResult,
                useAltFunc=showAlternative))
        else:
            htmlList.append(
                '<tr><td colspan="3"><span class="meta">%s</span></td></tr>' \
                    % i18n('No exact matches found'))

        # other matches
        dictResult = self.charInfo.searchDictionaryContainingHeadword(
            inputString)

        if dictResult:
            htmlList.append('<tr><td colspan="3"><h3>%s</h3></td></tr>' \
                % i18n('Other matches'))

            # don't display alternative if the charString is found in the
            #   given string
            showAlternative = lambda charString, _: \
                    (charString.find(inputString) < 0)
            htmlList.append(self._getVocabularyTable(dictResult,
                useAltFunc=showAlternative))

        htmlList.append('</table>')

        return '\n'.join(htmlList)

    def getCharacterWithComponentSection(self, inputString):
        """Gets a list of characters with the given character as component."""
        chars = self.charInfo.getCharactersForComponents([inputString])

        if chars:
            characterLinks = []
            for char in chars:
                characterLinks.append(
                    '<a class="character" href="#lookup(%s)">%s</a>' \
                        % (util.encodeBase64(char), char))
            return '<span class="character">%s</span>' \
                % ' '.join(characterLinks)
        else:
            return '<span class="meta">%s</span>' % i18n('No entries found')

    def getDecompositionTreeSection(self, inputString):
        """Gets a tree of components included in the given character."""
        def getDictionaryInfo(char):
            readings = []
            translations = []
            if self.charInfo.dictionary:
                dictResult = self.charInfo.searchDictionaryExactHeadword(char)
                if not dictResult:
                    return ''

                # separate readings from translation
                for _, _, reading, translation in dictResult:
                    if reading not in readings:
                        readings.append(reading)
                    if translation not in translations:
                        translations.append(
                            self._getTranslationRepresentation(translation))

            if not self.charInfo.dictionary or self.useExtraReadingInformation:
                for reading in self.charInfo.getReadingForCharacter(char):
                    if reading not in readings:
                        readings.append(reading)

            return ' <span class="reading">%s</span>' % ', '.join(readings) \
                + ' <span class="translation">%s</span>' \
                    % ' / '.join(translations)

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
                            + '</span>%s</span>' % getDictionaryInfo(char)
                else:
                    return '<span class="entry meta">%s</span>' \
                        % i18n('unknown')
            else:
                layout, char, tree = decompTree
                if char:
                    if isSubTree:
                        head = layout + '<span class="character">' \
                            + '<a class="character" href="#lookup(%s)">%s</a>' \
                                % (util.encodeBase64(char),  char) \
                            + '</span>' \
                            + getDictionaryInfo(char)
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

        decompTree = self.charInfo.getCharacterDecomposition(inputString)
        if decompTree:
            seenEntry = set()
            return '<div class="tree">%s</div>' % getLayer(decompTree)
        else:
            return '<span class="meta">%s</span>' % i18n('No entry found')

    def getCharacterPronunciationSearchSection(self, inputString):
        """
        Gets a list of vocabulary entries with readings similar to the given
        one. This method should be used when no dictionary is available.
        @todo: Warn when multiple entities given
        """
        def fillTable(chars):
            # sort by unicode codepoint
            chars.sort(cmp=lambda x, y: ord(list(x)[0])-ord(list(y)[0]))

            for char, readingList in chars:
                readingList = sorted(readingList)

                htmlList.append('<tr class="vocabularyEntry">' \
                    + '<td class="character">' \
                    + '<a class="character" href="#lookup(%s)">%s</a>' \
                        % (util.encodeBase64(char), char) \
                    + '</td>' \
                    + '<td class="reading">%s</td>' % ', '.join(readingList) \
                    + '</tr>')

        htmlList = []
        htmlList.append('<table class="search">')

        # exact matches
        exactChars = self.charInfo.getCharactersForReading(inputString)
        if exactChars:
            fillTable(exactChars)

        # similar matches
        similarChars = self.charInfo.getCharactersForSimilarReading(inputString)
        if similarChars:
            htmlList.append('<tr><td colspan="2"><h3>%s</h3></td></tr>' \
                % i18n('Similar pronunciations'))
            fillTable(similarChars)

        if not exactChars:
            if not similarChars:
                htmlList.append('<tr><td colspan="3">'\
                    + '<span class="meta">%s</span>' \
                        % i18n('No matches found') \
                    + '</td></tr>')
            else:
                htmlList.insert(0, '<tr><td colspan="3">'\
                    + '<span class="meta">%s</span>' \
                        % i18n('No exact matches found') \
                    + '</td></tr>')
        htmlList.append('</table>')

        return '\n'.join(htmlList)

    def getVocabularySearchSection(self, inputString):
        """
        Gets the search results for the given string including exact maches
        and a shortened list of similar results and results including the given
        string.
        """
        def augmentResults(results, chars):
            hasEntries = set()
            for charString, charStringAlt, reading, _ in results:
                hasEntries.add((charString, reading))
                hasEntries.add((charStringAlt, reading))

            for char, readingList in chars:
                for reading in readingList:
                    if (char, reading) not in hasEntries:
                        results.append((char, char, reading, ''))

        # if no dictionary is available only search for reading
        if not self.charInfo.dictionary:
            return self.getCharacterPronunciationSearchSection(inputString)

        htmlList = []
        htmlList.append('<table class="search">')

        # exact hits
        exactDictResult, otherDictResult \
            = self.charInfo.searchDictionaryExactNContaining(inputString,
                orderBy=['Weight']) # TODO split into two calls

        # augment with results from Unihan
        if self.useExtraReadingInformation:
            chars = self.charInfo.getCharactersForReading(inputString)
            if chars:
                augmentResults(exactDictResult, chars)

        if exactDictResult:
            htmlList.append('<tr><td colspan="3"><h3>%s</h3></td></tr>' \
                % i18n('Matches'))
            # match against input string with regular expression
            htmlList.append(self._getVocabularyTable(exactDictResult,
                useAltFunc=lambda x, y: \
                    self._matchesInput(inputString, y) \
                    and not self._matchesInput(inputString, x)))


        # similar pronunciation
        similarDictResult = self.charInfo.searchDictionarySimilarPronunciation(
            inputString, orderBy=['Weight'], limit=5)

        # augment with results from Unihan
        if self.useExtraReadingInformation and len(similarDictResult) < 5:
            chars = self.charInfo.getCharactersForSimilarReading(inputString)
            if chars:
                augmentResults(similarDictResult, chars)

        if similarDictResult:
            htmlList.append('<tr><td colspan="3"><h3>%s</h3></td></tr>' \
                % i18n('Similar pronunciations'))
            htmlList.append(self._getVocabularyTable(similarDictResult[:4]))

            if len(similarDictResult) > 4:
                htmlList.append('<tr><td colspan="3">' \
                    + '<a class="meta" href="#lookup(%s)">%s</a>' \
                        % (util.encodeBase64(i18n('similar') + ':' \
                            + inputString), i18n('All entries...'))
                    + '</td></tr>')


        # other matches
        if otherDictResult:
            htmlList.append('<tr><td colspan="3"><h3>%s</h3></td></tr>' \
                % i18n('Other matches'))
            augmentedInput = '*' + inputString + '*'
            htmlList.append(self._getVocabularyTable(otherDictResult[:4],
                useAltFunc=lambda x, y: \
                    self._matchesInput(inputString, y) \
                    and not self._matchesInput(inputString, x)))

            if len(otherDictResult) > 4:
                htmlList.append('<tr><td colspan="3">' \
                    + '<a class="meta" href="#lookup(%s)">%s</a>' \
                        % (util.encodeBase64(i18n('othervocabulary') + ':' \
                            + inputString), i18n('All entries...'))
                    + '</td></tr>')

        # handle 0 result cases
        if not exactDictResult:
            if not similarDictResult and not otherDictResult:
                htmlList.append('<tr><td colspan="3">'\
                    + '<span class="meta">%s</span>' \
                        % i18n('No matches found') \
                    + '</td></tr>')
            else:
                htmlList.insert(0, '<tr><td colspan="3">'\
                    + '<span class="meta">%s</span>' \
                        % i18n('No exact matches found') \
                    + '</td></tr>')

        htmlList.append('</table>')

        return '\n'.join(htmlList)

    def getOtherVocabularySearchSection(self, inputString):
        """
        Gets a list of vocabulary entries containing the given inputString.
        """
        if not self.charInfo.dictionary:
            return ""

        htmlList = []

        # TODO use caching
        _, dictResult = self.charInfo.searchDictionaryExactNContaining(
            inputString, orderBy=['Weight'])

        if dictResult:
            htmlList.append('<table class="otherVocabulary">')
            htmlList.append('<tr><td colspan="3"><h3>%s</h3></td></tr>' \
                % i18n('Other matches'))
            augmentedInput = '*' + inputString + '*'
            htmlList.append(self._getVocabularyTable(dictResult,
                useAltFunc=lambda x, y: \
                    self._matchesInput(inputString, y) \
                    and not self._matchesInput(inputString, x)))
            htmlList.append('</table>')

        else:
            htmlList.append('<span class="meta">%s</span>' \
                    % i18n('No matches found'))

        return '\n'.join(htmlList)

    def getSimilarVocabularySearchSection(self, inputString):
        """
        Gets a list of vocabulary entries with pronunciation similar to the
        given string.
        """
        def augmentResults(results, chars):
            hasEntries = set()
            for charString, charStringAlt, reading, _ in results:
                hasEntries.add((charString, reading))
                hasEntries.add((charStringAlt, reading))

            for char, readingList in chars:
                for reading in readingList:
                    if (char, reading) not in hasEntries:
                        results.append((char, char, reading, ''))

        if not self.charInfo.dictionary:
            return ""

        htmlList = []

        dictResult = self.charInfo.searchDictionarySimilarPronunciation(
            inputString)

        # augment with results from Unihan
        if self.useExtraReadingInformation:
            chars = self.charInfo.getCharactersForSimilarReading(inputString)
            if chars:
                augmentResults(similarDictResult, chars)

        if dictResult:
            htmlList.append('<table class="similarVocabulary">')
            htmlList.append('<tr><td colspan="3"><h3>%s</h3></td></tr>' \
                % i18n('Similar pronunciations'))
            htmlList.append(self._getVocabularyTable(dictResult))
            htmlList.append('</table>')

        else:
            htmlList.append('<span class="meta">%s</span>' \
                % i18n('No matches found'))

        return '\n'.join(htmlList)

    # CHARACTER SEARCH VIEWS

    def getComponentSearchTable(self, components=[],
        includeEquivalentRadicalForms=False, includeSimilarCharacters=False):
        """
        Gets a table of minimal components for searching characters by
        component. Annotates given characters and characters that would
        result in zero results if selected.
        """
        componentsByStrokeCount = self.charInfo.getMinimalCharacterComponents()

        selected = set([self.charInfo.preferRadicalFormForCharacter(char) \
            for char in components])

        if components:
            currentResultRadicals = self.charInfo.getComponentsWithResults(
                components,
                includeEquivalentRadicalForms=includeEquivalentRadicalForms,
                includeSimilarCharacters=includeSimilarCharacters)
        else:
            currentResultRadicals = None

        htmlList = []
        htmlList.append('<table class="component">')

        strokeCountList = componentsByStrokeCount.keys()
        strokeCountList.sort()
        for strokeCount in strokeCountList:
            htmlList.append('<tr><th>%d</th><td>' % strokeCount)
            for form in sorted(componentsByStrokeCount[strokeCount]):
                if form in selected:
                    formClass = 'selectedComponent'
                elif currentResultRadicals != None \
                    and form not in currentResultRadicals:
                    formClass = 'zeroResultComponent'
                else:
                    formClass = ''

                formBase64 = util.encodeBase64(form)
                htmlList.append(
                    '<a class="character" href="#component(%s)">' % formBase64 \
                    + '<span class="component %s" id="c%s">%s</span>' \
                        % (formClass, formBase64, form) \
                    + '</a>')
            htmlList.append('</td></tr>')
        htmlList.append('</table>')

        return "\n".join(htmlList)

    def getComponentSearchResult(self, components,
        includeEquivalentRadicalForms=False, includeSimilarCharacters=False):
        """Gets a list of characters containing the given components."""
        chars = self.charInfo.getCharactersForComponents(components,
            includeEquivalentRadicalForms=includeEquivalentRadicalForms,
            includeSimilarCharacters=includeSimilarCharacters)

        if chars:
            charLinks = []
            for char in chars:
                charLinks.append(
                    '<a class="character" href="#lookup(%s)">%s</a>' \
                        % (util.encodeBase64(char), char))
            html = '<span class="character">%s</span>' % ' '.join(charLinks)
        else:
            html = '<p class="meta">%s</p>' % i18n('No entries')

        return html, len(chars)

    def getRadicalTable(self):
        """Gets a table of Kangxi radicals, sorted by radical index."""
        htmlList = []
        htmlList.append('<table id="radicaltable" class="radical">')

        lastStrokeCount = None
        radicalForms = self.charInfo.getKangxiRadicalForms()
        radicalEntryDict = self.charInfo.getRadicalDictionaryEntries()

        for radicalIdx in range(1, 215):
            mainForm, strokeCount, variants, _ = radicalForms[radicalIdx]

            if lastStrokeCount != strokeCount:
                lastStrokeCount = strokeCount
                htmlList.append(
                    '<tr class="strokeCount" id="strokecount%d">' \
                        % strokeCount \
                    + '<td colspan="3"><h2>%s</h2></td>' \
                        % i18np('1 stroke', '%1 strokes', strokeCount)
                    + '</tr>')

            htmlList.append(
                '<tr class="radicalEntry" id="radical%d">' \
                    % radicalIdx \
                + '<td class="radicalIndex">%s</td>' % radicalIdx)

            if variants:
                htmlList.append('<td class="radical">' \
                    + '<a class="character" href="#radical(%s)">' % radicalIdx \
                    + '<span class="radical">%s</span><br/>' % mainForm \
                    + '<span class="radicalVariant">%s</span>' \
                        % ''.join(variants) \
                    + '</a></td>')
            else:
                htmlList.append('<td class="radical">' \
                    + '<a class="character" href="#radical(%s)">' % radicalIdx \
                    + '<span class="radical">%s</span><br/>' % mainForm \
                    + '</a></td>')

            if radicalIdx in radicalEntryDict:
                _, meaning = radicalEntryDict[radicalIdx] # TODO remove reading
                htmlList.append(
                    '<td class="translation">%s</td>' % meaning)
            else:
                htmlList.append('<td class="translation"></td>')

            htmlList.append('</tr>')

        htmlList.append('</table>')

        # TODO
        radicalEntries = {}
        for radicalIdx in range(1, 215):
            if radicalIdx in radicalEntryDict:
                _, meaning = radicalEntryDict[radicalIdx] # TODO remove reading
            else:
                meaning = None
            _, _, _, representatives = radicalForms[radicalIdx]
            radicalEntries[radicalIdx] = (representatives, meaning)

        return "\n".join(htmlList), radicalEntries

    def getCharacterForRadical(self, radicalIndex, includeAllComponents=False):
        """Gets a list of characters classified under the given radical."""
        # group by residual stroke count
        characterGroups = self.charInfo.getCharactersForKangxiRadicalIndex(
            radicalIndex, includeAllComponents=includeAllComponents)

        htmlList = []

        # show main radical form
        htmlList.append('<h3>%s</h3>' % i18n('Radical %1', str(radicalIndex)))

        charLinks = []
        for strokeCount in sorted(characterGroups['radical'].keys()):
            for char in sorted(characterGroups['radical'][strokeCount]):
                charLinks.append('<span class="character">' \
                    + '<a class="character" href="#lookup(%s)">%s</a>' \
                        % (util.encodeBase64(char), char) \
                    + '</span>')

        htmlList.append(' '.join(charLinks))

        radicalForms = self.charInfo.getKangxiRadicalForms()
        _, strokeCount, _, _ = radicalForms[radicalIndex]
        if strokeCount:
            htmlList.append(' (%s)' \
                % i18np('1 stroke', '%1 strokes', strokeCount))

        htmlList.append('<h3>%s</h3>' % i18n('Characters'))

        # list sorted by residual stroke count
        htmlList.append('<table class="searchResult">')
        for strokeCount in sorted(characterGroups[None].keys()):
            if type(strokeCount) != type(0):
                # sort out non stroke count groups
                continue

            htmlList.append('<tr>' \
                + '<th class="strokeCount">+%s</th><td>' % strokeCount)
            charLinks = []
            for char in sorted(characterGroups[None][strokeCount]):
                charLinks.append('<span class="character">' \
                    + '<a class="character" href="#lookup(%s)">%s</a>' \
                        % (util.encodeBase64(char), char) \
                    + '</span>')
            htmlList.append(' '.join(charLinks))

            htmlList.append('</td></tr>')

        # Add characters without stroke count information
        if None in characterGroups[None]:
            htmlList.append('<tr>' \
                + '<th class="strokeCount">%s</th><td>' % i18n('Unknown'))
            charLinks = []
            for char in sorted(characterGroups[None][None]):
                charLinks.append('<span class="character">' \
                    + '<a class="character" href="#lookup(%s)">%s</a>' \
                        % (util.encodeBase64(char), char) \
                    + '</span>')
            htmlList.append(' '.join(charLinks))

            htmlList.append('</td></tr>')

        htmlList.append('</table>')

        return "\n".join(htmlList)
