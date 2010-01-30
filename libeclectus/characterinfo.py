#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Provides character and dictionary lookup services.

@todo Fix: rewrite and put dictionary-based code into own class

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

import locale
import re
import warnings
import operator
import functools
from datetime import datetime

from sqlalchemy import Table
from sqlalchemy import select, union
from sqlalchemy.sql import and_, or_, not_
from sqlalchemy.sql import text, func

import cjklib
from cjklib.dbconnector import DatabaseConnector
from cjklib import characterlookup
from cjklib.reading import ReadingFactory
from cjklib import exception
from cjklib.util import cross

from libeclectus import util

class CharacterInfo:
    """
    Provides lookup method services.
    """
    LANGUAGE_CHAR_LOCALE_MAPPING = {'zh-cmn-Hans': 'C', 'zh-cmn-Hant': 'T',
        'zh-yue': 'T', 'ko': 'T', 'ja': 'J', 'vi': 'V'}
    """Mapping table for language to default character locale."""

    LOCALE_LANGUAGE_MAPPING = {'zh': 'zh-cmn-Hans', 'zh_CN': 'zh-cmn-Hans',
        'zh_SG': 'zh-cmn-Hans', 'zh_TW': 'zh-cmn-Hant', 'zh_HK': 'zh-yue',
        'zh_MO': 'zh-yue', 'ja': 'ja', 'ko': 'ko', 'vi': 'vi'}
    """Mapping table for locale to default language."""

    LANGUAGE_DEFAULT_READING = {'zh-cmn-Hans': 'Pinyin',
        'zh-cmn-Hant': 'Pinyin', 'zh-yue': 'CantoneseYale', 'ko': 'Hangul',
        'ja': 'Kana'}
    """Character locale's default character reading."""

    DICTIONARY_INFO = {
        'HanDeDict': ('CEDICT', 'Pinyin', {'toneMarkType': 'numbers'}, 'zh-cmn',
            'de', lambda entities: ' '.join(entities)),
        'CFDICT': ('CEDICT', 'Pinyin', {'toneMarkType': 'numbers'}, 'zh-cmn',
            'de', lambda entities: ' '.join(entities)),
        'CEDICT': ('CEDICT', 'Pinyin', {'toneMarkType': 'numbers'}, 'zh-cmn',
            'en', lambda entities: ' '.join(entities)),
        'CEDICTGR': ('EDICT', 'GR', {}, 'zh-cmn-Hant', 'en',
            lambda entities: ' '.join(entities)),
        'EDICT': ('EDICT', 'Kana', {}, 'ja', 'en',
            lambda entities: ''.join(entities))
        }
    """
    Dictionaries with type (EDICT, CEDICT), reading, reading options,
    CJK language and target language.
    """

    PRONUNCIATION_READING = {'Pronunciation_zh_cmn': ('Pinyin', {}),
        'Pronunciation_zh_yue': ('CantoneseYale', {})}
    """Table of audio files options."""

    AVAILABLE_READINGS = {
        'zh-cmn-Hans': ['Pinyin', 'WadeGiles', 'MandarinIPA', 'GR'],
        'zh-cmn-Hant': ['Pinyin', 'WadeGiles', 'MandarinIPA', 'GR'],
        'zh-yue': ['Jyutping', 'CantoneseYale'], 'ko': ['Hangul'],
        'ja': ['Kana']}
    """All readings available for a language."""

    INCOMPATIBLE_READINGS = [('Pinyin', 'GR'), ('GR', 'WadeGiles'),
        ('GR', 'MandarinIPA')]
    """Reading conversions incompatible under practical considerations."""

    TONAL_READING = {'Pinyin': {'toneMarkType': 'None'},
        'WadeGiles': {'toneMarkType': 'None'},
        'Jyutping': {'toneMarkType': 'None'},
        'CantoneseYale': {'toneMarkType': 'None'}}
    """
    Dictionary of tonal readings with reading options to remove tonal features.
    """

    READING_OPTIONS = {'WadeGiles': {'toneMarkType': 'superscriptNumbers'}}
    """Special reading options for output."""

    SPECIAL_TONAL_READINGS = ['GR']
    """List of tonal readings, that can't be easily displayed in plain form."""

    RADICALS_NON_VISUAL_EQUIVALENCE = set([u'⺄', u'⺆', u'⺇', u'⺈', u'⺊',
        u'⺌', u'⺍', u'⺎', u'⺑', u'⺗', u'⺜', u'⺥', u'⺧', u'⺪', u'⺫', u'⺮',
        u'⺳', u'⺴', u'⺶', u'⺷', u'⺻', u'⺼', u'⻏', u'⻕'])
    """
    Radical forms for which we don't want to retrieve a equivalent character as
    it would resemble another radical form.
    """
    RADICALS_NON_INJECTIVE_MAPPING = set([u'⺁', u'⺾', u'⺿', u'⻀', u'⻊',
        u'⻗'])
    """
    Radical forms for which we don't want to retrieve a equivalent character as
    it would make the mapping non injective.
    """

    AMBIGUOUS_INITIALS = {'Pinyin': {
            'alveolar/retroflex': [('z', 'zh'), ('c', 'ch'), ('s', 'sh')],
            'aspirated': [('b', 'p'), ('g', 'k'), ('d', 't'), ('j', 'q'),
                ('z', 'c'), ('zh', 'ch')],
            'other consonants': [('n', 'l'), ('l', 'r'), ('f', 'h'),
                ('f', 'hu')]},
        'CantoneseYale': {
            'initial': [('n', 'l'), ('gwo', 'go'), ('kwo', 'ko'), ('ng', ''),
                ('k', 'h')],
            },
        'Jyutping': {
            'initial': [('n', 'l'), ('gwo', 'go'), ('kwo', 'ko'), ('ng', ''),
                ('k', 'h')],
            },
        }
    """Groups of similar sounding syllable initials."""

    AMBIGUOUS_FINALS = {'Pinyin': {
            'n/ng': [('an', 'ang'), ('uan', 'uang'), ('en', 'eng'),
                ('in', 'ing')],
            'vowel': [('eng', 'ong'), (u'ü', 'i'), (u'üe', 'ie'),
                (u'üan', 'ian'), (u'ün', 'in'), ('uo', 'o'), ('ui', 'ei'),
                ('i', 'u'), ('e', 'o')]},
        'CantoneseYale': {
            'final': [('k', 't'), ('ng', 'n')],
            },
        'Jyutping': {
            'final': [('k', 't'), ('ng', 'n')],
            },
        }
    """Groups of similar sounding syllable finals."""

    def __init__(self, language=None, reading=None, dictionary=None,
        characterDomain=None, databaseUrl=None):
        """
        Initialises the CharacterInfo object.
        """
        configuration = {}
        if databaseUrl:
            configuration['sqlalchemy.url'] = databaseUrl
            if databaseUrl.startswith('sqlite://'):
                configuration['attach'] = ([util.getDatabaseUrl()]
                    + util.getAttachableDatabases())
        else:
            configuration['sqlalchemy.url'] = util.getDatabaseUrl()
            configuration['attach'] = util.getAttachableDatabases()
        #configuration['sqlalchemy.echo'] = True

        self.databaseUrl = configuration['sqlalchemy.url']
        self.db = DatabaseConnector.getDBConnector(configuration)

        self.availableDictionaries = None

        if language and language in self.LANGUAGE_CHAR_LOCALE_MAPPING:
            self.language = language
        else:
            # try to figure out language using locale settings, and existing
            #   dictionary
            language = self.guessLanguage()
            if language:
                self.language = language
            else:
                # take a language from an existing dictionary
                dictionaries = self.getAvailableDictionaries()
                self.language = self.LANGUAGE_CHAR_LOCALE_MAPPING.keys()[0]
                if dictionaries:
                    dictName = dictionaries[0]
                    _, _, _, cjkLang, _, _ = self.DICTIONARY_INFO[dictName]
                    for language in self.LANGUAGE_CHAR_LOCALE_MAPPING:
                        if language.startswith(cjkLang):
                            self.language = language
                            break

        self.locale = self.LANGUAGE_CHAR_LOCALE_MAPPING[self.language]

        self.characterLookup = characterlookup.CharacterLookup(self.locale,
            dbConnectInst=self.db)
        self.characterLookupTraditional = characterlookup.CharacterLookup('T',
            dbConnectInst=self.db)

        # character domain
        if characterDomain and characterDomain \
            in self.characterLookup.getAvailableCharacterDomains():
            self.characterDomain = characterDomain
        else:
            self.characterDomain = 'Unicode'
        self.characterLookup.setCharacterDomain(self.characterDomain)
        self.characterLookupTraditional.setCharacterDomain(self.characterDomain)

        self.readingFactory = ReadingFactory(dbConnectInst=self.db)

        # get incompatible reading conversions
        self.incompatibleConversions = {}
        for lang in self.AVAILABLE_READINGS:
            for r in self.AVAILABLE_READINGS[lang]:
                self.incompatibleConversions[r] = set()
        for readingA, readingB in self.INCOMPATIBLE_READINGS:
            self.incompatibleConversions[readingA].add(readingB)
            self.incompatibleConversions[readingB].add(readingA)

        compatible = self.getCompatibleDictionaries(self.language)
        if not compatible:
            self.dictionary = None
        elif dictionary and dictionary in compatible:
            self.dictionary = dictionary
        else:
            # set a random one
            self.dictionary = compatible[0]

        if self.dictionary:
            _, dictReading, _, _, _, _ \
                = self.DICTIONARY_INFO[self.dictionary]

            compatible = self.getCompatibleReadings(self.language)
            if reading and reading in compatible:
                self.reading = reading
            else:
                if self.language in self.LANGUAGE_DEFAULT_READING \
                    and self.LANGUAGE_DEFAULT_READING[self.language] \
                        in compatible:
                    self.reading = self.LANGUAGE_DEFAULT_READING[self.language]
                else:
                    self.reading = dictReading
        else:
            if self.language in self.LANGUAGE_DEFAULT_READING:
                self.reading = self.LANGUAGE_DEFAULT_READING[self.language]
            else:
                self.reading = self.AVAILABLE_READINGS[self.language][0]

        if self.dictionary:
            # check for FTS3 table (only SQLite)
            self.dictionaryHasFTS3 = self.db.hasTable(self.dictionary + '_Text')

            dictType, _, _, _, _, _ = self.DICTIONARY_INFO[self.dictionary]
            if dictType == 'EDICT':
                self.headwordColumn = 'Headword'
                self.headwordAlternativeColumn = self.headwordColumn
                self.headwordIndexColumn = self.headwordColumn
            elif dictType == 'CEDICT':
                if self.locale == 'C':
                    self.headwordColumn = 'HeadwordSimplified'
                    self.headwordAlternativeColumn = 'HeadwordTraditional'
                else:
                    self.headwordColumn = 'HeadwordTraditional'
                    self.headwordAlternativeColumn = 'HeadwordSimplified'
                self.headwordIndexColumn = 'HeadwordTraditional'

            # check for prefer entries
            if self.dictionaryHasFTS3:
                tableName = self.dictionary + '_Normal'
            else:
                tableName = self.dictionary
            self.dictionaryTable = self.db.tables[self.dictionary]
            self.dictionaryPrefer = 'Weight' in self.dictionaryTable.columns

        self.minimalCharacterComponents = None
        self.radicalForms = None
        self.kangxiRadicalForms = None
        self.radicalFormLookup = None
        self.radicalNameTableName = None

        # create lookup for pronunciation files
        self.pronunciationLookup = {}
        for table in self.PRONUNCIATION_READING:
            pronReading, _ = self.PRONUNCIATION_READING[table]
            self.pronunciationLookup[pronReading] = table

        for availReading in self.AVAILABLE_READINGS[self.language]:
            for pronReading in self.pronunciationLookup.copy():
                if self.readingFactory.isReadingConversionSupported(
                    availReading, pronReading):
                    self.pronunciationLookup[availReading] \
                        = self.pronunciationLookup[pronReading]

    #{ Settings

    def guessLanguage(self):
        """
        Guesses the language using the user's locale settings.

        @rtype: character
        @return: locale
        """
        # get local language and output encoding
        language, _ = locale.getdefaultlocale()

        # get language code
        if language.find('_') >= 0:
            languageCode, _ = language.split('_', 1)
        else:
            languageCode = language

        # get character locale
        if language in self.LOCALE_LANGUAGE_MAPPING \
            and self.getCompatibleDictionaries(language):
            return self.LOCALE_LANGUAGE_MAPPING[language]
        elif languageCode in self.LOCALE_LANGUAGE_MAPPING \
            and self.getCompatibleDictionaries(languageCode):
            return self.LOCALE_LANGUAGE_MAPPING[languageCode]

    def getAvailableDictionaries(self):
        """
        Gets a list of available dictionaries supported.

        @rtype: list of strings
        @return: names of available dictionaries
        """
        if self.availableDictionaries == None:
            self.availableDictionaries = []
            for dictName in self.DICTIONARY_INFO:
                if self.db.hasTable(dictName):
                    self.availableDictionaries.append(dictName)
        return self.availableDictionaries

    def getDictionaryVersions(self):
        dictionaries = self.getAvailableDictionaries()
        dictionaryVersions = self.getUpdateVersions(dictionaries)

        versionDict = {}
        for dictionaryName in self.DICTIONARY_INFO:
            if dictionaryName in dictionaryVersions:
                versionDict[dictionaryName] = dictionaryVersions[dictionaryName]
            else:
                versionDict[dictionaryName] = None
        return versionDict

    def getCompatibleDictionaries(self, language):
        compatible = []
        for dictName in self.getAvailableDictionaries():
            _, _, _, cjkLang, _, _ = self.DICTIONARY_INFO[dictName]
            if language.startswith(cjkLang):
                compatible.append(dictName)

        compatible.sort(key=str.lower)
        return compatible

    def getCompatibleReadings(self, language):
        compatible = []
        if self.dictionary:
            _, dictReading, _, _, _, _ = self.DICTIONARY_INFO[self.dictionary]
            for reading in self.AVAILABLE_READINGS[language]:
                if dictReading == reading \
                    or (self.readingFactory.isReadingConversionSupported(
                        dictReading, reading) and \
                    reading not in self.incompatibleConversions[dictReading]):
                    compatible.append(reading)
        else:
            compatible = self.AVAILABLE_READINGS[language]

        compatible.sort()
        return compatible

    def getCompatibleReadingsFor(self, language, dictionary):
        compatible = []
        if dictionary:
            _, dictReading, _, _, _, _ = self.DICTIONARY_INFO[dictionary]
            for reading in self.AVAILABLE_READINGS[language]:
                if dictReading == reading \
                    or (self.readingFactory.isReadingConversionSupported(
                        dictReading, reading) and \
                    reading not in self.incompatibleConversions[dictReading]):
                    compatible.append(reading)
        else:
            compatible = self.AVAILABLE_READINGS[language]

        compatible.sort()
        return compatible

    def getAvailableCharacterDomains(self):
        return self.characterLookup.getAvailableCharacterDomains()

    def getUpdateVersions(self, tableNames):
        if tableNames and self.db.hasTable('UpdateVersion'):
            table = self.db.tables['UpdateVersion']
            versionDict = dict([(tableName, datetime.min) \
                for tableName in tableNames])
            versionDict.update(dict(self.db.selectRows(
                select([table.c.TableName, table.c.ReleaseDate],
                    table.c.TableName.in_(tableNames)))))
            return versionDict
        else:
            return dict([(table, None) for table in tableNames])

    # Internal worker

    def checkOrderByWeight(self, orderBy):
        if orderBy and 'Weight' in orderBy:
            if self.dictionaryPrefer:
                orderBy[orderBy.index('Weight')] \
                    = func.ifnull(self.dictionaryTable.c['Weight'], 100) # TODO start from 100 down (DESC)
            else:
                orderBy.remove('Weight')

    def getReadingOptions(self, string, readingN):
        """
        Guesses the reading options using the given string to support reading
        dialects.

        @type string: string
        @param string: reading string
        @type readingN: string
        @param readingN: reading name
        @rtype: dictionary
        @returns: reading options
        """
        # guess reading parameters
        classObj = self.readingFactory.getReadingOperatorClass(readingN)
        if hasattr(classObj, 'guessReadingDialect'):
            return classObj.guessReadingDialect(string)
        else:
            return {}

    def getReadingEntities(self, string, readingN=None):
        """
        Gets all possible decompositions for the given string.

        @type string: string
        @param string: reading string
        @type readingN: string
        @param readingN: reading name
        @rtype: list of lists of strings
        @return: decomposition into reading entities.
        """
        def processEntities(decompositions):
            # transform for wildcards, group by entity count
            transformedDecompositions = []
            for entities in decompositions:
                transformedEntities = []
                hasReadingEntity = False
                for entry in entities:
                    if self.readingFactory.isReadingEntity(entry, dictReading,
                        **dictReadOpt):
                        transformedEntities.append(entry)
                        hasReadingEntity = True
                    else:
                        # break down non reading entities to extract wildcards
                        for subentry in re.split('([\*\?])', entry):
                            if subentry == '*' or subentry == '?':
                                transformedEntities.append(subentry)
                            # TODO remove
                            #elif subentry == '?':
                                #transformedEntities.append('_%')
                            elif subentry:
                                i = 0
                                while i < len(subentry):
                                    # look for Chinese characters
                                    oldIndex = i
                                    while i < len(subentry) \
                                        and not subentry[i] > u'⺀':
                                        i = i + 1
                                    if oldIndex != i:
                                        # non Chinese char substring
                                        if subentry[oldIndex:i].strip():
                                            transformedEntities.append(
                                                subentry[oldIndex:i].strip())
                                    # if we didn't reach the end of the input we
                                    #   have a Chinese char
                                    if i < len(subentry):
                                        transformedEntities.append(subentry[i])
                                    i = i + 1

                if hasReadingEntity:
                    # only use decompositions that have reading entities
                    transformedDecompositions.append(transformedEntities)

            return transformedDecompositions

        if not readingN:
            readingN = self.reading
        options = self.getReadingOptions(string, readingN)

        # for all possible decompositions convert to dictionary's reading
        _, dictReading, dictReadOpt, _, _, _ \
            = self.DICTIONARY_INFO[self.dictionary]
        try:
            try:
                decompositions = self.readingFactory.getDecompositions(string,
                    readingN, **options)
            except exception.UnsupportedError:
                decompositions = [self.readingFactory.decompose(string,
                    readingN, **options)]

            if self.readingFactory.isReadingConversionSupported(readingN,
                dictReading):
                decompEntities = []
                for entities in decompositions:
                    try:
                        decompEntities.append(
                            self.readingFactory.convertEntities(entities,
                                readingN, dictReading, sourceOptions=options,
                                targetOptions=dictReadOpt))
                    except exception.ConversionError:
                        # some conversions might fail even others succeed, e.g.
                        #   bei3jing1 might fail for bei3'ji'ng1
                        # TODO throw an exception when all conversions fail?
                        pass

                return processEntities(decompEntities)
            else:
                return processEntities(decompositions)
        except cjklib.exception.DecompositionError:
            pass
        except cjklib.exception.UnsupportedError:
            pass

        return [] # TODO rather throw an exception?

    def joinReadingEntities(self, entities):
        if not entities:
            return []

        entityList = [entities[0]]
        lastEntity = entities[0]
        for entity in entities[1:]: # TODO
            if entity not in ['%', '*', '_'] \
                and lastEntity not in ['%', '*', '_']:
                entityList.append(' ' + entity)
            else:
                entityList.append(entity)
            lastEntity = entity
        return ''.join(entityList)

    def joinReadingEntitiesWC(self, entities):
        # TODO bad implementation
        if self.dictionary == 'EDICT':
            readingString = ''.join(entities)
        else:
            readingString = self.joinReadingEntities(entities)
        return readingString.replace('*', '%').replace('?', '_%')

    def joinCharacters(self, searchString):
        return ''.join(searchString).replace('*', '%').replace('?', '_')

    @staticmethod
    def createSimpleRegex(entry):
        regex = []
        for substr in re.split('([\*\?])', entry):
            if substr in ['*', '%']:
                regex.append('(.*)')
            elif substr in ['?', '_']:
                regex.append('(.)')
            elif substr:
                regex.append('(' + re.escape(substr) + ')')
        return re.compile('^(?i)' + ''.join(regex) + '$')

    @staticmethod
    def createSpacedRegex(entry):
        regex = []
        # TODO substrings = [s for s in re.split('([\*\?_%])', entry) if s]
        substrings = [s for s in re.split('([\*\? ])', entry) if s]
        for i, substr in enumerate(substrings):
            #if substr == '%':
                #regex.append('(.*)')
            #elif substr == '_':
                #regex.append('(.)')
            if substr == '*' and i == 0:
                regex.append('(.*?)')
            elif substr == '*' and i > 0:
                regex.append('((?: .*?)?)')
            elif substr == '?': # TODO and i == 0:
                regex.append('([^ ]+)')
            #elif substr == '?' and i > 0:
                ## following entries are spaced
                #regex.append('( [^ ]+)')
            elif substr == ' ':
                regex.append(' ')
            elif substr:
                regex.append('(' + re.escape(substr).replace('\\_', '.') + ')')
        print 1, entry, '^' + ''.join(regex) + '$'
        return re.compile('^(?i)' + ''.join(regex) + '$')

    def filterResults(self, results, filterList):
        filteredResults = []
        columns = [self.headwordColumn, self.headwordAlternativeColumn,
            'Reading', 'Translation']

        for entry in results:
            entryDict = dict([(column, entry[idx]) \
                for idx, column in enumerate(columns)])
            for filterEntry in filterList:
                if filterEntry(entryDict):
                    filteredResults.append(entry)
                    break
            else:
                print '!', ', '.join(entry)

        return filteredResults

    def getReadingFilter(self, readingEntities):
        return lambda entry: CharacterInfo.createSpacedRegex(
            self.joinReadingEntities(readingEntities))\
                .search(entry['Reading']) != None

    def getCharacterFilter(self, charString, headwordColumn=None):
        if not headwordColumn:
            headwordColumn = self.headwordColumn
        return lambda entry: CharacterInfo.createSimpleRegex(charString)\
                .search(entry[headwordColumn]) != None

    def getTranslationFilter(self, translation):
        searchStr = []
        for subStr in re.split('([\*\?])', translation):
            if subStr == '*':
                searchStr.append('.*')
            elif subStr == '?':
                searchStr.append('.')
            else:
                searchStr.append(re.escape(subStr))
        wordRegex = re.compile(r'(?i)[/,\(\]\[\!\.\?\=]\s*' \
            + ''.join(searchStr) + r'\s*[/,\(\]\[\!\.\?\=]')

        return lambda entry: wordRegex.search(entry['Translation']) != None

    def getCharacterReadingPairFilter(self, characterEntities, readingEntities,
        headwordColumn=None):
        def matchPair(headwordRegex, readingRegex, headword, reading):
            matchObj = headwordRegex.match(headword)
            if not matchObj:
                return False
            headwordParts = matchObj.groups()
            print 'headwordParts', headwordParts
            matchObj = readingRegex.match(reading)
            if not matchObj:
                return False
            readingParts = matchObj.groups()
            print 'readingParts', readingParts
            assert(len(headwordParts) == len(readingParts))

            for idx in range(len(headwordParts)):
                try:
                    print self.matchCharToEntity(headwordParts[idx],
                        readingParts[idx])
                except ValueError:
                    return False

            return True

        if not headwordColumn:
            headwordColumn = self.headwordColumn

        assert(len(characterEntities) == len(readingEntities))
        headwordRegex = CharacterInfo.createSimpleRegex(
            ''.join(characterEntities))
        readingRegex = CharacterInfo.createSpacedRegex(
            self.joinReadingEntities(readingEntities))

        return lambda entry: functools.partial(matchPair, headwordRegex,
            readingRegex)(entry[headwordColumn], entry['Reading'])

    def mixResults(self, results, orderColumn=0, limit=None):
        if not results:
            return []
        sortedResults = sorted(results, key=operator.itemgetter(orderColumn))

        # remove double entries
        lastEntry = sortedResults[0]
        offset = 0
        for idx, entry in enumerate(sortedResults[1:]):
            if entry == lastEntry:
                del sortedResults[idx + 1 - offset]
                offset += 1
            lastEntry = entry

        if limit == None:
            return sortedResults
        else:
            return sortedResults[:limit]

    def getSimilarReadings(self, entities, readingN, explicitEntities=False,
        **options):
        """
        Gets a list of similar pronounced readings for a decompositions.

        @type decompEntities: lists of strings
        @param decompEntities: decomposed reading entities
        @type readingN: string
        @param readingN: name of reading
        @rtype: list of list of strings
        @return: similar entities
        @todo Impl: Pinyin: no use of Erhua yin, input of invalid Pinyin because
            of sound changes (e.g. pong -> peng).
        @todo Impl: Cantonese nasal syllable ng -> m.
        """
        similarEntities = []
        for entity in entities:
            if (readingN in self.TONAL_READING \
                and not self.readingFactory.isPlainReadingEntity(entity,
                    readingN, **options)) \
                or readingN in self.SPECIAL_TONAL_READINGS:
                try:
                    entity, _ = self.readingFactory.splitEntityTone(
                        entity, readingN, **options)
                except exception.InvalidEntityError:
                    similarEntities.append([entity])
                    continue
                except exception.UnsupportedError:
                    similarEntities.append([entity])
                    continue

            similar = [entity]
            if readingN in self.AMBIGUOUS_INITIALS:
                for key in self.AMBIGUOUS_INITIALS[readingN]:
                    for tpl in self.AMBIGUOUS_INITIALS[readingN][key]:
                        a, b = tpl
                        if re.match(a + u'[aeiouü]', entity):
                            similar.append(b + entity[len(a):])
                        elif re.match(b + u'[aeiouü]', entity):
                            similar.append(a + entity[len(b):])
            # for all initial derived forms change final
            if readingN in self.AMBIGUOUS_FINALS:
                for modEntity in similar[:]:
                    for key in self.AMBIGUOUS_FINALS[readingN]:
                        for tpl in self.AMBIGUOUS_FINALS[readingN][key]:
                            a, b = tpl
                            if re.search(u'[^aeiouü]' + a + '$', modEntity):
                                similar.append(modEntity[:-len(a)] + b)
                            elif re.search(u'[^aeiouü]' + b + '$',
                                modEntity):
                                similar.append(modEntity[:-len(b)] + a)
            similarEntities.append(similar)

        similarEntityList = cross(*similarEntities)

        # remove exact hits
        if entities in similarEntityList:
            similarEntityList.remove(entities)

        if readingN in self.TONAL_READING \
            or readingN in self.SPECIAL_TONAL_READINGS:
            exactSimilarEntityList = []

            for similarEntities in similarEntityList:
                fullEntities = []
                for entity in similarEntities:
                    if self.readingFactory.isPlainReadingEntity(entity,
                        readingN, **options):
                        if explicitEntities \
                            or readingN in self.SPECIAL_TONAL_READINGS:
                            fullEntities.append(self._buildTonalEntities(entity,
                                readingN, **options))
                        else:
                            fullEntities.append([entity + '_'])
                    else:
                        fullEntities.append([entity])
                exactSimilarEntityList.extend(cross(*fullEntities))

            if entities in exactSimilarEntityList:
                exactSimilarEntityList.remove(entities)

            return exactSimilarEntityList
        else:
            return similarEntityList

    def buildExactReadings(self, entities, readingN, explicitEntities=False,
        **options):
        # TODO document, explicit generation of tonal entities, were replacement
        #   of tonemarks by SQL placeholder is not appropriate
        if readingN in self.TONAL_READING:
            fullEntities = []
            for entity in entities:
                if self.readingFactory.isPlainReadingEntity(entity, readingN,
                    **options):
                    if explicitEntities:
                        fullEntities.append(self._buildTonalEntities(entity,
                            readingN, **options))
                    else:
                        fullEntities.append([entity + '_'])
                else:
                    fullEntities.append([entity])
            return cross(*fullEntities)

        return [entities]

    def _buildTonalEntities(self, plainEntity, readingN, **options):
        tonalEntities = set()
        for tone in self.readingFactory.getTones(readingN):
            try:
                tonalEntities.add(self.readingFactory.getTonalEntity(
                    plainEntity, tone, readingN, **options))
            except exception.ConversionError, e:
                pass
        return tonalEntities

    def convertCharacterReadings(self, result, readingN, **options):
        # TODO document
        conversionSupported = self.readingFactory.isReadingConversionSupported(
            readingN, self.reading)

        response = []
        for char, charReading in result:
            readingList = []
            for entity in charReading:
                if conversionSupported:
                    try:
                        readingList.append(self.readingFactory.convert(entity,
                            readingN, self.reading, sourceOptions=options))
                    except cjklib.exception.DecompositionError:
                        readingList.append('[' + entity + ']')
                    except cjklib.exception.ConversionError:
                        entity = '[' + entity + ']'
                        readingList.append('[' + entity + ']')
                else:
                    readingList.append(entity)

            response.append((char, readingList))
        return response

    def convertDictionaryResult(self, result):
        """
        Converts the readings of the given dictionary result to the default
        reading.

        @type result: list of tuples
        @param result: database search result
        @rtype: list of tuples
        @return: converted input
        """
        # convert reading
        _, dictReading, dictReadOpt, _, _, _ \
            = self.DICTIONARY_INFO[self.dictionary]
        if self.reading in self.READING_OPTIONS:
            targetOpt = self.READING_OPTIONS[self.reading]
        else:
            targetOpt = {}

        response = []
        conversionSupported = self.readingFactory.isReadingConversionSupported(
            dictReading, self.reading)

        for headword, headwordAlternative, reading, translation in result:
            if conversionSupported:
                try:
                    reading = self.readingFactory.convert(reading, dictReading,
                        self.reading, sourceOptions=dictReadOpt,
                        targetOptions=targetOpt)
                except cjklib.exception.DecompositionError:
                    reading = '[' + reading + ']'
                except cjklib.exception.ConversionError:
                    reading = '[' + reading + ']'

            response.append((headword, headwordAlternative, reading,
                translation))
        return response

    def getEquivalentCharTable(self, componentList,
        includeEquivalentRadicalForms=False, includeSimilarCharacters=False):
        u"""
        Gets a list structure of equivalent chars for the given list of
        characters.

        If option C{includeEquivalentRadicalForms} is set, all equivalent forms
        will be searched for when a Kangxi radical is given.

        If option C{includeSimilarCharacters} is set, characters with similar
        visual forms will be searched for, too.

        @type componentList: list of characters
        @param componentList: list of character components
        @type includeEquivalentRadicalForms: boolean
        @param includeEquivalentRadicalForms: if C{True} then characters in the
            given component list are interpreted as representatives for their
            radical and all radical forms are included in the search. E.g. 肉
            will include ⺼ as a possible component.
        @type includeSimilarCharacters: boolean
        @param includeSimilarCharacters: if C{True} then characters with similar
            visual forms will be included in search.
        @rtype: list of lists of strings
        @return: list structure of equivalent characters
        @todo Impl: Once mapping of similar radical forms exist (e.g. 言 and 訁)
            include here.
        """
        equivCharTable = []
        for component in componentList:
            componentEquivalents = set([component])
            try:
                # check if component is a radical and get index, don't check
                #   locale as we want to convert a radical form either way
                radicalIdx = self.characterLookup.getKangxiRadicalIndex(
                    component)

                if includeEquivalentRadicalForms:
                    # if includeRadicalVariants is set get all forms
                    componentEquivalents.update(self.characterLookup\
                        .getKangxiRadicalRepresentativeCharacters(radicalIdx))
                    if self.locale != 'T':
                        componentEquivalents.update(
                            self.characterLookupTraditional\
                                .getKangxiRadicalRepresentativeCharacters(
                                    radicalIdx))
                else:
                    if self.characterLookup.isRadicalChar(component):
                        if component \
                            not in self.RADICALS_NON_VISUAL_EQUIVALENCE:
                            try:
                                componentEquivalents.add(self.characterLookup\
                                    .getRadicalFormEquivalentCharacter(
                                        component))
                            except cjklib.exception.UnsupportedError:
                                # pass if no equivalent char existent
                                pass
                    else:
                        componentEquivalents.update(set(self.characterLookup\
                            .getCharacterEquivalentRadicalForms(component)) \
                                - self.RADICALS_NON_VISUAL_EQUIVALENCE)
            except ValueError:
                pass

            # get similar characters
            if includeSimilarCharacters:
                table = self.db.tables['SimilarCharacters']
                tableA = table.alias('a')
                tableB = table.alias('b')
                fromObj = tableA.join(tableB,
                    and_(tableA.c.ChineseCharacter != tableB.c.ChineseCharacter,
                        tableA.c.GroupIndex == tableB.c.GroupIndex))

                for char in componentEquivalents.copy():
                    for similarChar in self.db.selectScalars(
                        select([tableB.c.ChineseCharacter],
                            tableA.c.ChineseCharacter == char,
                            from_obj=fromObj)):
                        componentEquivalents.add(similarChar)

                        try:
                            if self.characterLookup.isRadicalChar(similarChar):
                                componentEquivalents.add(self.characterLookup\
                                    .getRadicalFormEquivalentCharacter(
                                        similarChar))
                            else:
                                componentEquivalents.update(
                                    self.characterLookup\
                                        .getCharacterEquivalentRadicalForms(
                                            similarChar))
                        except cjklib.exception.UnsupportedError:
                            pass
                        except ValueError:
                            pass

            equivCharTable.append(list(componentEquivalents))

        return equivCharTable

    def isSemanticVariant(self, char, variants):
        """
        Checks if the character is a semantic variant form of the given
        characters.

        @type char: character
        @param char: Chinese character
        @type variants: list of characters
        @param variants: Chinese characters
        @rtype: boolean
        @return: C{True} if the character is a semantic variant form of the
            given characters, C{False} otherwise.
        """
        vVariants = []
        for variant in variants:
            vVariants.extend(
                self.characterLookup.getCharacterVariants(variant, 'M'))
            vVariants.extend(
                self.characterLookup.getCharacterVariants(variant, 'P'))
        return char in vVariants

    def filterDomainCharacters(self, charList):
        """
        Filters a given list of characters to only match those in the current
        character domain.

        @type charList: list of str
        @param charList: list of characters to filter
        @rtype: list of str
        @return: filtered character list
        """
        if hasattr(self.characterLookup, 'filterDomainCharacters'):
            return self.characterLookup.filterDomainCharacters(charList)
        else:
            return charList

    def matchCharToEntity(self, charString, reading):
        """
        Matches each character to the entities of the given reading string.

        @type charString: string
        @param charString: headword string
        @type reading: string
        @param reading: character string reading
        @rtype: list of tuples
        @return: one character matched to one reading entity each
        """
        _, dictReading, dictReadOpt, _, _, _ \
            = self.DICTIONARY_INFO[self.dictionary]

        try:
            readingEntities = self.readingFactory.decompose(reading,
                dictReading, **dictReadOpt)
        except cjklib.exception.DecompositionError, m:
            return []

        while ' ' in readingEntities:
            readingEntities.remove(' ')

        # TODO more sophisticated search
        if len(readingEntities) != len(charString):
            raise ValueError('Headword/Reading mismatch')

        entryList = []
        for idx, char in enumerate(charString):
            entryList.append((char, readingEntities[idx]))
        return entryList

    #{

    def getCharacterIndex(self, char, indexTable):
        """Returns a distinct index for a character using the given table."""
        if self.db.hasTable(indexTable):
            table = self.db.tables[indexTable]
            return self.db.selectScalar(select(
                    [table.c.CharValue], table.c.ChineseCharacter == char))

    #{ Radical, Components

    def getCharactersForKangxiRadicalIndex(self, radicalIndex,
        includeAllComponents=False, groupByRadicalFormPosition=False):
        """
        Gets all characters for the given Kangxi radical index grouped by
        residual stroke count and if choosen additionally by position and form
        of the radical.

        @type radicalIndex: number
        @param radicalIndex: Kangxi radical index
        @type includeAllComponents: boolean
        @param includeAllComponents: if C{True} characters incorporating a
            radical form of the given radical though beeing included under a
            different radical will be also returned.
        @type groupByRadicalFormPosition: boolean
        @param groupByRadicalFormPosition: if C{True} characters will be grouped
            by the form and the position of the given radical
        @rtype: dict construct
        @return: list of matching Chinese characters grouped by type and
            residual stroke count
        """
        # get characters for Kangxi radical
        if includeAllComponents:
            entryList = self.characterLookup\
                .getResidualStrokeCountForRadicalIndex(radicalIndex)
        else:
            entryList = self.characterLookup\
                .getResidualStrokeCountForKangxiRadicalIndex(radicalIndex)

        characterGroups = {None: {}, 'radical': {}}

        # radicals
        radicalForms = set()
        representativeCharacters = set(self.characterLookup\
            .getKangxiRadicalRepresentativeCharacters(radicalIndex))
        if self.locale != 'T':
            representativeCharacters.update(self.characterLookupTraditional\
                .getKangxiRadicalRepresentativeCharacters(radicalIndex))

        for radicalForm in representativeCharacters:
            if not self.characterLookup.isRadicalChar(radicalForm):
                radicalForms.add(radicalForm)

        seenRadicalForms = set()
        for char, residualStrokeCount in entryList:
            if char in radicalForms:
                if residualStrokeCount not in characterGroups['radical']:
                    characterGroups['radical'][residualStrokeCount] = set()
                characterGroups['radical'][residualStrokeCount].add(char)

                seenRadicalForms.add(char)

        characterGroups['radical'][None] = radicalForms - seenRadicalForms

        # ordinary characters
        if groupByRadicalFormPosition:
            pass # TODO
        else:
            for char, residualStrokeCount in entryList:
                if char in radicalForms:
                    continue

                if residualStrokeCount not in characterGroups[None]:
                    characterGroups[None][residualStrokeCount] = set()

                characterGroups[None][residualStrokeCount].add(char)

        return characterGroups

    def getCharacterDecomposition(self, char):
        """
        Gets a single flattend character decomposition for the given character

        @type char: character
        @param char: Chinese character
        @rtype: tuple structure
        @return: character decomposition
        """
        def splitFlatTree(char, decomposition, idx=0):
            """
            Builds a flat tree by rolling out several sub decompositions on the
            same layer by inserting new layers.
            """
            layout = decomposition[idx]
            if self.characterLookup.isBinaryIDSOperator(layout):
                subCharCount = 2
            else:
                subCharCount = 3
            treeElements = []
            curIndex = idx
            while len(treeElements) < subCharCount:
                curIndex = curIndex + 1
                element = decomposition[curIndex]
                if type(element) != type(()):
                    # ids element -> sub decomposition on same layer,
                    #   break down into sub tree
                    curIndex, tree = splitFlatTree(None, decomposition,
                        curIndex)
                    treeElements.append(tree)
                else:
                    # proper character
                    subChar, zVariant, subDecomposition = element
                    if subDecomposition:
                        _, tree = splitFlatTree(subChar, subDecomposition[0])
                        treeElements.append(tree)
                    else:
                        treeElements.append(subChar)
            return curIndex, (layout, char, treeElements)

        treeList = self.characterLookup.getDecompositionTreeList(char)
        if not treeList:
            return None
        else:
            # TODO more sophisticated, get the "nicest" decomposition
            _, tree = splitFlatTree(char, treeList[0])
            return tree

    def getCharactersForComponents(self, componentList,
        includeEquivalentRadicalForms=False, includeSimilarCharacters=False):
        u"""
        Gets all characters that contain the given components.

        If option C{includeEquivalentRadicalForms} is set, all equivalent forms
        will be searched for when a Kangxi radical is given.

        If option C{includeSimilarCharacters} is set, characters with similar
        visual forms will be searched for, too.

        @type componentList: list of characters
        @param componentList: list of character components
        @type includeEquivalentRadicalForms: boolean
        @param includeEquivalentRadicalForms: if C{True} then characters in the
            given component list are interpreted as representatives for their
            radical and all radical forms are included in the search. E.g. 肉
            will include ⺼ as a possible component.
        @type includeSimilarCharacters: boolean
        @param includeSimilarCharacters: if C{True} then characters with similar
            visual forms will be included in search.
        @rtype: list of tuples
        @return: list of pairs of matching characters and their glyph
        @todo Impl: Once mapping of similar radical forms exist (e.g. 言 and 訁)
            include here.
        """
        equivCharTable = self.getEquivalentCharTable(componentList,
            includeEquivalentRadicalForms, includeSimilarCharacters)

        characters = self.characterLookup.getCharactersForEquivalentComponents(
            equivCharTable, includeAllGlyphs=True)
        seenChars = set()
        charList = []
        for char, _ in characters:
            if char not in seenChars:
                charList.append(char)
            seenChars.add(char)

        return charList

    def getComponentsWithResults(self, componentList,
        includeEquivalentRadicalForms=False, includeSimilarCharacters=False):
        u"""
        Gets a list of minimal components which can be added to the given list
        of components so that the narrower search will still yield results.

        If option C{includeEquivalentRadicalForms} is set, all equivalent forms
        will be searched for when a Kangxi radical is given.

        If option C{includeSimilarCharacters} is set, characters with similar
        visual forms will be searched for, too.

        @type componentList: list of characters
        @param componentList: list of character components
        @type includeEquivalentRadicalForms: boolean
        @param includeEquivalentRadicalForms: if C{True} then characters in the
            given component list are interpreted as representatives for their
            radical and all radical forms are included in the search. E.g. 肉
            will include ⺼ as a possible component.
        @type includeSimilarCharacters: boolean
        @param includeSimilarCharacters: if C{True} then characters with similar
            visual forms will be included in search.
        @rtype: list of tuples
        @return: list of pairs of matching characters and their glyph
        @todo Impl: Once mapping of similar radical forms exist (e.g. 言 and 訁)
            include here.
        @todo Impl: Integrate a table of actual radical forms so we don't
            return *all* components
        @todo Fix: Dont return components for results of non-locale glyphs,
            e.g. ⽰ for 福.
        """
        equivCharTable = self.getEquivalentCharTable(componentList,
            includeEquivalentRadicalForms, includeSimilarCharacters)

        # create where clauses
        lookupTable = self.characterLookup.db.tables['ComponentLookup']
        strokeCountTable = self.characterLookup.db.tables['StrokeCount']

        joinTables = []         # join over all tables by char and glyph
        filters = []            # filter for locale and component

        # generate filter for each component
        for i, characterList in enumerate(equivCharTable):
            lookupTableAlias = lookupTable.alias('s%d' % i)
            joinTables.append(lookupTableAlias)
            # find chars for components, also include 米 for [u'米', u'木'].
            filters.append(or_(lookupTableAlias.c.Component.in_(characterList),
                lookupTableAlias.c.ChineseCharacter.in_(characterList)))

        # chain tables together in a JOIN
        fromObject = joinTables[0]
        for table in joinTables[1:]:
            fromObject = fromObject.outerjoin(table,
                onclause=and_(
                    table.c.ChineseCharacter \
                        == joinTables[0].c.ChineseCharacter,
                    table.c.Glyph == joinTables[0].c.Glyph))
        # constrain to selected character domain
        if self.characterLookup.getCharacterDomain() != 'Unicode':
            domainTblName = self.characterLookup.getCharacterDomain() + 'Set'
            characterDomainTable = self.characterLookup.db.tables[domainTblName]
            fromObject = fromObject.join(characterDomainTable,
                joinTables[-1].c.ChineseCharacter \
                    == characterDomainTable.c.ChineseCharacter)

        # join again to get all possible components
        mainAlias = lookupTable.alias('s')
        fromObject = fromObject.outerjoin(mainAlias,
            onclause=and_(
                mainAlias.c.ChineseCharacter \
                    == joinTables[0].c.ChineseCharacter,
                mainAlias.c.Glyph == joinTables[0].c.Glyph))

        sel = select([mainAlias.c.Component], and_(*filters),
            from_obj=[fromObject], distinct=True)

        result = self.characterLookup.db.selectScalars(sel)

        # augment result with equivalent forms
        # TODO only check for true radical components included in table, save work
        augmentedResult = self.getEquivalentCharTable(result,
            includeEquivalentRadicalForms, includeSimilarCharacters)

        resultSet = set()
        for characterList in augmentedResult:
            resultSet.update(characterList)
        return resultSet
        # TODO
        #return set([self.preferRadicalFormForCharacter(c) for c in result \
            #if c not in flatTable])

    def getMinimalCharacterComponents(self):
        """
        Gets a list of minimal character components grouped by stroke count.

        @rtype: list of list of characters
        @returns: minimal character components
        @todo Impl: Implement a locale/character domain based set of minimal
            components instead of all Kangxi radical forms.
        """
        if not self.minimalCharacterComponents:
            self.minimalCharacterComponents = {}
            radicalForms = self.getRadicalForms()
            for radicalIdx in range(1, 215):
                mainForm, strokeCount, variants = radicalForms[radicalIdx]
                if strokeCount not in self.minimalCharacterComponents:
                    self.minimalCharacterComponents[strokeCount] = set()
                self.minimalCharacterComponents[strokeCount].add(mainForm)
                self.minimalCharacterComponents[strokeCount].update(variants)
        return self.minimalCharacterComponents

    def preferRadicalFormForCharacter(self, char):
        """
        Converts characters to their radical equivalent if one exists.

        @type char: character
        @param char: Chinese character
        @rtype: char
        @return: given character or Radical equivalent form if one exists
        """
        # build character equivalent to radical form lookup
        if not self.radicalFormLookup:
            self.radicalFormLookup = {}

            radicalForms = self.getRadicalForms()
            for radicalIdx in range(1, 215):
                mainForm, _, variants = radicalForms[radicalIdx]
                equiv = self.characterLookupTraditional\
                    .getRadicalFormEquivalentCharacter(mainForm)
                self.radicalFormLookup[equiv] = mainForm
                for variant in variants:
                    # exclude equivalent forms that don't visual resemble and
                    #   non injective mappings
                    if variant not in self.RADICALS_NON_INJECTIVE_MAPPING \
                        and variant not in self.RADICALS_NON_VISUAL_EQUIVALENCE:
                        try:
                            equiv = self.characterLookup\
                                .getRadicalFormEquivalentCharacter(variant)
                            if equiv in self.radicalFormLookup:
                                warnings.warn(
                                    "Warning: overwriting conversion rule: '" \
                                        + equiv + "' has to forms '" \
                                        + self.radicalFormLookup[equiv] \
                                        + "' and '" +  variant + "'")
                            self.radicalFormLookup[equiv] = variant
                        except cjklib.exception.UnsupportedError:
                            pass
                        except ValueError:
                            pass

        if type(char) == type([]):
            result = []
            for c in char:
                if c in self.radicalFormLookup:
                    result.append(self.radicalFormLookup[c])
                else:
                    result.append(c)
            return result
        else:
            if char in self.radicalFormLookup:
                return self.radicalFormLookup[char]
            else:
                return char

    def getRadicalForms(self):
        if self.radicalForms == None:
            self.radicalForms = {}
            table = self.db.tables['KangxiRadicalStrokeCount']
            strokeCountDict = dict(self.db.selectRows(select(
                [table.c.RadicalIndex, table.c.StrokeCount])))
            for radicalIdx in range(1, 215):
                radicalForm = self.characterLookupTraditional\
                    .getKangxiRadicalForm(radicalIdx)

                variants = self.characterLookup.getKangxiRadicalVariantForms(
                    radicalIdx)

                if self.locale != 'T':
                    radicalLocaleForm \
                        = self.characterLookup.getKangxiRadicalForm(radicalIdx)
                    if radicalForm != radicalLocaleForm:
                        variants.insert(0, radicalLocaleForm)
                self.radicalForms[radicalIdx] = (radicalForm,
                    strokeCountDict[radicalIdx], variants)
        return self.radicalForms

    def getKangxiRadicalForms(self):
        """
        Gets a list of Kangxi radicals forms sorted by the radical index. One
        entry consists of the traditional main form, its stroke count and
        radical variant forms (the first entry being the locale dependent main
        form, in case it is different to the traditional form).

        @rtype: dict of tuples
        @returns: kangxi radical forms
        @todo Opt: Optimise, don't create 400 SQL select commands
        """
        if not self.kangxiRadicalForms:
            if self.radicalNameTableName == None:
                # TODO doesn't work for CEDICTGR and for languages without
                #   dictionary
                if self.dictionary:
                    _, _, _, cjkLang, _, _ = self.DICTIONARY_INFO[\
                        self.dictionary]
                    tableName = 'RadicalNames_' + cjkLang.replace('-', '_')
                    if self.db.hasTable(tableName):
                        self.radicalNameTableName = tableName
                    else:
                        self.radicalNameTableName = ''
                else:
                    self.radicalNameTableName = ''

            self.kangxiRadicalForms = {}

            formsDict = {}
            variantsDict = dict([(radIdx, []) for radIdx in range(1, 215)])
            table = self.db.tables['KangxiRadicalStrokeCount']
            strokeCountDict = dict(self.db.selectRows(select(
                [table.c.RadicalIndex, table.c.StrokeCount])))
            # get names of radicals to enhance search
            radicalNamesDict = {}
            if self.radicalNameTableName:
                table = self.db.tables[self.radicalNameTableName]
                entries = self.db.selectRows(select(
                    [table.c.RadicalIndex, table.c.TraditionalName,
                        table.c.SimplifiedName, table.c.TraditionalShortName,
                        table.c.SimplifiedShortName]))
                for entry in entries:
                    radicalIdx = entry[0]
                    names = entry[1:]
                    if radicalIdx not in radicalNamesDict:
                        radicalNamesDict[radicalIdx] = set([])
                    radicalNamesDict[radicalIdx].update(
                        [name for name in names if name])

            table = self.db.tables['KangxiRadicalTable']
            entries = self.db.selectRows(select(
                [table.c.RadicalIndex, table.c.Form, table.c.Type],
                table.c.Locale.like('%' + self.locale + '%')))
            for radicalIdx, form, type in entries:
                if type == 'F':
                    formsDict[radicalIdx] = form
                else:
                    if type == 'L':
                        # locale dependant main form
                        variantsDict[radicalIdx].insert(0, form)
                    else:
                        variantsDict[radicalIdx].append(form)

            # group by stroke count
            for radicalIdx in range(1, 215):
                representativeForms = set(self.characterLookup\
                    .getKangxiRadicalRepresentativeCharacters(radicalIdx))
                if radicalIdx in radicalNamesDict:
                    representativeForms.update(radicalNamesDict[radicalIdx])
                self.kangxiRadicalForms[radicalIdx] = (formsDict[radicalIdx],
                    strokeCountDict[radicalIdx], variantsDict[radicalIdx],
                    representativeForms)

        return self.kangxiRadicalForms

    def getRadicalDictionaryEntries(self):
        """
        Gets the readings and definitions of all Kangxi radicals.

        @rtype: dict
        @return: radical index, reading and definition
        @todo Fix: Don't use dictionary language, but rather interface language
        """
        if not hasattr(self, '_radicalDictionaryDict'):
            radicalTableName = None
            if self.dictionary:
                _, _, _, cjkLang, targetLang, _ \
                    = self.DICTIONARY_INFO[self.dictionary]
                tableName = 'RadicalTable_' + cjkLang.replace('-', '_') \
                    + '__' + targetLang.replace('-', '_')
                if self.db.hasTable(tableName):
                    radicalTableName = tableName

            if not radicalTableName:
                self._radicalDictionaryDict = {}

            else:
                table = self.db.tables[radicalTableName]
                result = self.db.selectRows(select(
                    [table.c.RadicalIndex, table.c.Meaning]))

                entryDict = {}
                for radicalIndex, definition in result:
                #for radicalIndex, reading, definition in result:
                    if not definition:
                        definition = ''

                    # TODO
                    #if reading:
                        #_, dictReading, dictReadOpt, _, _ \
                            #= self.DICTIONARY_INFO[self.dictionary]
                        #try:
                            #reading = self.readingFactory.convert(reading,
                                #dictReading, self.reading,
                                #sourceOptions=dictReadOpt)
                        #except cjklib.exception.DecompositionError:
                            #reading = '[' + reading + ']'
                        #except cjklib.exception.ConversionError:
                            #reading = '[' + reading + ']'

                    #entryDict[radicalIndex] = (reading, definition)
                    entryDict[radicalIndex] = ('', definition)

                self._radicalDictionaryDict = entryDict

        return self._radicalDictionaryDict

    #{ Pronunciation

    def getPronunciationFile(self, pronunciation, **options):
        """
        Gets the file name of the pronunciation sound file if it exists.

        @type pronunciation: str/unicode
        @param pronunciation: pronunciation to retrieve the audio file for
        @rtype: unicode
        @return: file name
        """
        if self.dictionary:
            _, readingN, options, _, _, _ \
                = self.DICTIONARY_INFO[self.dictionary]
        else:
            readingN = self.reading # TODO

        if readingN not in self.pronunciationLookup:
            return None

        pronunciationTableName = self.pronunciationLookup[readingN]
        if not self.db.hasTable(pronunciationTableName):
            return None

        pronunciationTableReading, pronunciationTableOpt \
            = self.PRONUNCIATION_READING[pronunciationTableName]

        try:
            pronunciationConv = self.readingFactory.convert(pronunciation,
                readingN, pronunciationTableReading,
                sourceOptions=options,
                targetOptions=pronunciationTableOpt)
            pronunciationConv = pronunciationConv.replace(' ','').lower()
        except cjklib.exception.DecompositionError:
            return None
        except cjklib.exception.ConversionError:
            return None

        table = self.db.tables[pronunciationTableName]
        return self.db.selectScalar(select([table.c.AudioFilePath],
            table.c.Pronunciation == pronunciationConv))

    #{ Variant

    def getCharacterVariants(self, char):
        """
        Gets a list of variant forms of the given character.

        @type headword: string
        @param headword: headword
        @rtype: list of strings
        @return: headword variant forms
        """
        variants = set(char)
        # get variants from Unihan
        variants.update([c for c, _ in
            self.characterLookup.getAllCharacterVariants(char)])
        # get radical equivalent char
        if self.characterLookup.isRadicalChar(char):
            try:
                equivChar = self.characterLookup\
                    .getRadicalFormEquivalentCharacter(char)
                variants.add(equivChar)
            except cjklib.exception.UnsupportedError:
                # pass if no equivalent char existent
                pass

        return variants

    def getHeadwordVariants(self, headword):
        """
        Gets a list of variant forms of the given headword.

        @type headword: string
        @param headword: headword
        @rtype: list of strings
        @return: headword variant forms
        """
        singleCharacterVariants = [self.getCharacterVariants(char) \
            for char in headword]

        # build word from single characters
        variants = set([''.join(headwordVariant) for headwordVariant \
            in cross(*singleCharacterVariants)])
        variants.remove(headword)

        # if we have a CEDICT type dictionary use additional information
        dictType, _, _, _, _, _ \
            = self.DICTIONARY_INFO[self.dictionary]
        if dictType == 'CEDICT':
            forms = self.db.selectScalars(select(
                [self.dictionaryTable.c[self.headwordColumn]],
                self.dictionaryTable.c[self.headwordAlternativeColumn] == headword,
                distinct=True))

            if headword in forms:
                forms.remove(headword)
            variants.update(forms)

        if variants:
            # filter variants
            return self.db.selectScalars(select(
                [self.dictionaryTable.c[self.headwordColumn]],
                self.dictionaryTable.c[self.headwordColumn].in_(variants),
                distinct=True).order_by('Reading', self.headwordColumn))
        else:
            return []

    def getCharacterSimilars(self, char):
        """
        Gets a list of variant forms of the given character.

        @type headword: string
        @param headword: headword
        @rtype: list of strings
        @return: headword variant forms
        """
        equiv = set(self.getEquivalentCharTable([char],
            includeEquivalentRadicalForms=False,
            includeSimilarCharacters=True)[0])
        if char in equiv:
            equiv.remove(char)
        return equiv

    def getHeadwordSimilars(self, headword):
        """
        Gets a list of similar forms of the given headword.

        @type headword: string
        @param headword: headword
        @rtype: list of strings
        @return: headword variant forms
        """
        similarCharacters = []
        for char in headword:
            similarCharacters.append(self.getEquivalentCharTable([char],
                includeEquivalentRadicalForms=False,
                includeSimilarCharacters=True)[0])

        # build word from single characters
        similar = set([''.join(headwordSimilar) for headwordSimilar \
            in cross(*similarCharacters)])
        similar.remove(headword)

        if similar:
            # filter similar character combinations
            return self.db.selectScalars(select(
                [self.dictionaryTable.c[self.headwordColumn]],
                self.dictionaryTable.c[self.headwordColumn].in_(similar),
                distinct=True).order_by('Reading', self.headwordColumn))
        else:
            return []

    #{ Simple character/reading mapping

    def getCharactersForReading(self, readingString, readingN=None):
        """
        Gets all know characters for the given reading.

        @type readingString: string
        @param readingString: reading entity for lookup
        @type readingN: string
        @param readingN: name of reading
        @rtype: list of chars
        @return: list of characters for the given reading
        @raise ValueError: if invalid reading entity or several entities are
            given.
        @raise UnsupportedError: if no mapping between characters and target
            reading exists.
        @raise ConversionError: if conversion from the internal source reading
            to the given target reading fails.
        """
        if not readingN:
            readingN = self.reading
        options = self.getReadingOptions(readingString, readingN)

        charList = set([])
        charReadingDict = {}
        for entities in self.buildExactReadings([readingString], readingN,
            explicitEntities=True, **options):
            if len(entities) != 1:
                continue
            entity = entities[0]
            try:
                chars = self.characterLookup.getCharactersForReading(
                    entity, readingN, **options)
                charList.update(chars)

                for char in chars:
                    if char not in charReadingDict:
                        charReadingDict[char] = set()
                    charReadingDict[char].add(entity)
            except ValueError:
                pass
            except exception.ConversionError:
                pass
            except exception.UnsupportedError:
                return []

        return self.convertCharacterReadings(
            [(char, charReadingDict[char]) for char in charList], readingN,
            **options)

    def getCharactersForSimilarReading(self, readingString, readingN=None):
        """
        Gets all know characters for the given reading.

        @type readingString: string
        @param readingString: reading entity for lookup
        @type readingN: string
        @param readingN: name of reading
        @rtype: list of tuples of character and pronunciation
        @return: list of characters for the given reading
        @raise ValueError: if invalid reading entity or several entities are
            given.
        @raise UnsupportedError: if no mapping between characters and target
            reading exists.
        @raise ConversionError: if conversion from the internal source reading
            to the given target reading fails.
        @todo Fix: Put similar reading conversion together with dictionary part
        """
        if not readingN:
            readingN = self.reading
        options = self.getReadingOptions(readingString, readingN)

        readingEntity = readingString

        similarEntities = self.getSimilarReadings([readingString], readingN,
            explicitEntities=True, **options)

        # get all characters for the similar readings
        similarReadingCharacters = set()
        charReadingDict = {}
        for entities in similarEntities:
            if len(entities) != 1:
                continue
            entity = entities[0]
            try:
                chars = self.characterLookup.getCharactersForReading(entity,
                    readingN, **options)
                similarReadingCharacters.update(chars)

                for char in chars:
                    if char not in charReadingDict:
                        charReadingDict[char] = set()
                    charReadingDict[char].add(entity)

            except ValueError:
                pass
            except ConversionError:
                pass

        return self.convertCharacterReadings([(char, charReadingDict[char]) \
            for char in similarReadingCharacters], readingN, **options)

    def getReadingForCharacter(self, char):
        """
        Gets a list of readings for a given character.

        @type char: character
        @param char: Chinese character
        @rtype: list of lists of strings
        @return: a list of readings
        @raise exception.UnsupportedError: raised when a translation from
            character to reading is not supported by the given target reading
        @raise exception.ConversionError: if conversion for the string is not
            supported
        @raise ValueError: on other exceptions
        """
        if self.reading in self.READING_OPTIONS:
            targetOpt = self.READING_OPTIONS[self.reading]
        else:
            targetOpt = {}
        try:
            return self.characterLookup.getReadingForCharacter(char,
                self.reading, **targetOpt)
        except exception.ConversionError:
            return []
        except exception.UnsupportedError:
            return []

    def getReadingForCharString(self, charString):
        """
        Gets a list of readings per character in the given string.

        @type charString: string
        @param charString: headword string
        @rtype: list of tuples
        @return: one character matched to one reading entity each
        """
        readings = []
        for char in charString:
            try:
                readings.append(self.characterLookup.getReadingForCharacter(
                    char, self.reading))
            except exception.UnsupportedError:
                readings.append([])

        return readings

    #{ Dictionary search

    def getDictionaryHeadwordSearchSQL(self, searchValue, orderBy=['Reading'],
        limit=None):
        dictType, _, _, _, _, _ = self.DICTIONARY_INFO[self.dictionary]

        self.checkOrderByWeight(orderBy)

        # TODO hack
        if type(searchValue) != type([]):
            searchValue = [searchValue]
        filters = []
        for value in searchValue:
            if '%' in value or '?' in value:
                if dictType == 'EDICT':
                    filters.append(
                        self.dictionaryTable.c.Headword.like(value))
                elif dictType == 'CEDICT':
                    filters.append(
                        self.dictionaryTable.c[self.headwordColumn].like(value))
                    filters.append(
                        self.dictionaryTable.c[self.headwordAlternativeColumn]\
                            .like(value))
            else:
                if dictType == 'EDICT':
                    filters.append(self.dictionaryTable.c.Headword == value)
                elif dictType == 'CEDICT':
                    filters.append(self.dictionaryTable.c[self.headwordColumn] \
                        == value)
                    filters.append(
                        self.dictionaryTable.c[self.headwordAlternativeColumn] \
                            == value)

        if dictType == 'EDICT':
            return select([self.dictionaryTable.c.Headword,
                self.dictionaryTable.c.Headword.label('a'),
                self.dictionaryTable.c.Reading,
                self.dictionaryTable.c.Translation],
                or_(*filters),
                distinct=True).order_by(*orderBy).limit(limit)
        elif dictType == 'CEDICT':
            return select([self.dictionaryTable.c[self.headwordColumn],
                self.dictionaryTable.c[self.headwordAlternativeColumn].label('a'),
                self.dictionaryTable.c.Reading,
                self.dictionaryTable.c.Translation],
                or_(*filters),
                distinct=True).order_by(*orderBy).limit(limit)

    #def doHeadwordDictionarySearch(self, searchValue, orderBy=['Reading'],
        #limit=None):
        #"""
        #Searches the dictionary for entries whose headword match the given
        #searchValue.

        #@type searchString: string or list of srings
        #@param searchString: search value
        #@type limit: number
        #@param limit: maximum number of entries
        #@rtype: list of tuples
        #@return: dictionary entries
        #"""
        #return self.executeSQL(self.getDictionaryHeadwordSearchSQL(searchValue,
            #orderBy, limit))

    def searchDictionaryExactHeadword(self, searchString, limit=None):
        """
        Searches the dictionary for entries whose headword match the given
        string.

        Results are sorted by the headword's reading.

        @type searchString: string
        @param searchString: search string
        @type limit: number
        @param limit: maximum number of entries
        @rtype: list of tuples
        @return: dictionary entries
        """
        results = self.db.selectRows(self.getDictionaryHeadwordSearchSQL(
            searchString, limit=limit))
        return self.convertDictionaryResult(results)

    def searchDictionaryExactHeadwordReading(self, headword, readingEntities,
        limit=None):
        """
        Searches the dictionary for entries whose headword and reading match the
        given input.

        @type headword: string
        @param headword: headword
        @type readingEntities: list of strings
        @param readingEntities: headword reading
        @type limit: number
        @param limit: maximum number of entries
        @rtype: list of tuples
        @return: dictionary entries
        """
        dictType, _, _, _, _, readingFunc \
            = self.DICTIONARY_INFO[self.dictionary]

        if dictType == 'EDICT':
            result = self.db.selectRows(select(
                [self.dictionaryTable.c[self.headwordColumn],
                self.dictionaryTable.c[self.headwordColumn],
                self.dictionaryTable.c.Reading,
                self.dictionaryTable.c.Translation],
                and_(self.dictionaryTable.c[self.headwordColumn] == headword,
                    self.dictionaryTable.c.Reading \
                        == readingFunc(readingEntities)),
                distinct=True))
        elif dictType == 'CEDICT':
            result = self.db.selectRows(select(
                [self.dictionaryTable.c[self.headwordColumn],
                self.dictionaryTable.c[self.headwordColumn],
                self.dictionaryTable.c.Reading,
                self.dictionaryTable.c.Translation],
                and_(self.dictionaryTable.c.Reading \
                        == readingFunc(readingEntities),
                    or_(self.dictionaryTable.c[self.headwordColumn] == headword,
                        self.dictionaryTable.c[self.headwordAlternativeColumn] \
                            == headword)),
                distinct=True))

        return self.convertDictionaryResult(result)

    def searchDictionaryHeadwordEntities(self, searchString, limit=None):
        """
        Searches the dictionary for single entities of the given headword. These
        entities are substrings of the headword (currently single characters)
        and can help with understanding the meaning.

        @type searchString: string
        @param searchString: headword
        @type limit: number
        @param limit: maximum number of entries
        @rtype: list of tuples
        @return: dictionary entries
        @todo Fix: Caching would help here, as the search for the headword
            is already done somewhere else before.
        @todo Fix: Work on tonal changes for some characters in Mandarin
        @todo Fix: Get proper normalisation or collation for reading column.
        """
        searchOptions = []

        _, dictReading, dictReadOpt, _, _, readingFunc \
            = self.DICTIONARY_INFO[self.dictionary]

        results = self.db.selectRows(self.getDictionaryHeadwordSearchSQL(
            searchString))

        for headword, headwordAlt, reading, _ in results:
            # support mixing of different locales
            if headwordAlt == searchString:
                searchHeadword = headwordAlt
                column = self.headwordAlternativeColumn
            else:
                searchHeadword = headword
                column = self.headwordColumn

            try:
                for char, readingEntity in \
                    set(self.matchCharToEntity(searchHeadword, reading)):
                    # TODO tonal?
                    readings = [readingFunc(entities) for entities \
                        in self.buildExactReadings([readingEntity], dictReading,
                            **dictReadOpt)]
                    searchOptions.append(
                        and_(self.dictionaryTable.c.Reading.in_(readings),
                            self.dictionaryTable.c[column] == char))
            except ValueError:
                pass

        if not searchOptions:
            # no headword found, so no reading part for characters, use all
            #   available character results
            searchOptions = [or_(
                self.dictionaryTable.c[self.headwordColumn].in_(
                    list(searchString)),
                self.dictionaryTable.c[self.headwordAlternativeColumn].in_(
                    list(searchString)))]

        result = self.db.selectRows(select(
            [self.dictionaryTable.c[self.headwordColumn],
            self.dictionaryTable.c[self.headwordAlternativeColumn].label('a'),
            self.dictionaryTable.c.Reading,
            self.dictionaryTable.c.Translation],
            or_(*searchOptions), distinct=True))
        # TODO
        #result = self.db.select(self.dictionary,
            #[self.headwordColumn, self.headwordAlternativeColumn, 'Reading',
                #'Translation'], searchOptions, distinctValues=True)

        return self.convertDictionaryResult(result)

    def searchDictionaryContainingHeadword(self, searchString,
        orderBy=['Reading'], limit=None):
        """
        Searches the dictionary for entries whose headword contain the given
        string.

        Results are sorted by the headword's reading.

        @type searchString: string
        @param searchString: search string
        @type limit: number
        @param limit: maximum number of entries
        @rtype: list of tuples
        @return: dictionary entries
        """
        results = self.db.selectRows(self.getDictionaryHeadwordSearchSQL(
            ['%' + searchString + '_%', '_%' + searchString + '%'],
            orderBy=orderBy, limit=limit))

        return self.convertDictionaryResult(results)

    def searchDictionaryHeadwordSubstrings(self, searchString, limit=None):
        """
        Searches the dictionary for entries whose headword is a substring of the
        given string.

        Results are sorted by the headword's reading.

        @type searchString: string
        @param searchString: search string
        @type limit: number
        @param limit: maximum number of entries
        @rtype: list of tuples
        @return: dictionary entries
        """
        subStrings = []
        for left in range(0, len(searchString)):
            for right in range(len(searchString), left, -1):
                # TODO
                #if searchString[left:right] != searchString:
                    #subStrings.append(searchString[left:right])
                subStrings.append(searchString[left:right])

        results = self.db.selectRows(self.getDictionaryHeadwordSearchSQL(
            subStrings, limit=limit))

        return self.convertDictionaryResult(results)

    def getReadingSearchOptions(self, searchEntities):
        searchOptions = []
        filterList = []

        # check for special entity search including chinese characters
        specialSearchOptions = []
        for entities in searchEntities:
            # check for chinese characters
            readingEntities = []
            characterEntities = []
            chineseCharFound = False
            for entry in entities:
                # ⺀ CJK RADICAL REPEAT
                if len(entry) == 1 and entry >= u'⺀' \
                    and ((entry < u'ぁ') or (entry > u'ヿ')): # TODO
                    chineseCharFound = True
                    readingEntities.append('?')
                    characterEntities.append(entry)
                elif entry in ['*', '_']:
                    readingEntities.append(entry)
                    characterEntities.append(entry)
                else:
                    readingEntities.append(entry)
                    characterEntities.append('?')

            if chineseCharFound:
                searchOption = and_(self.dictionaryTable.c.Reading.like(
                    self.joinReadingEntitiesWC(readingEntities)),
                    or_(self.dictionaryTable.c[self.headwordColumn].like(
                        self.joinCharacters(characterEntities)),
                        self.dictionaryTable.c[self.headwordAlternativeColumn].like(
                            self.joinCharacters(characterEntities))))
                filterEntry = [self.getCharacterReadingPairFilter(
                    characterEntities, readingEntities),
                    self.getCharacterReadingPairFilter(
                        characterEntities, readingEntities,
                        headwordColumn=self.headwordAlternativeColumn)]
            else:
                searchOption = self.dictionaryTable.c.Reading.like(
                    self.joinReadingEntitiesWC(readingEntities))
                filterEntry = [self.getReadingFilter(readingEntities)]

            searchOptions.append(searchOption)
            filterList.extend(filterEntry)

        return or_(*searchOptions), filterList
            #if chineseCharFound:
                #specialSearchOptions.append({
                    #'Reading': self.joinReadingEntitiesWC(readingEntities),
                    #self.headwordColumn: ''.join(characterEntities)})
                #filterList.append({
                    #'Reading': self.joinReadingEntities(readingEntities),
                    #self.headwordColumn: ''.join(characterEntities)})

    def doSearchDictionaryMixedReadingCharacter(self, searchString,
        readingN=None, orderBy=['Reading'], limit=None):
        # reading string
        decompEntities = self.getReadingEntities(searchString, readingN)
        print 'decompEntities', decompEntities

        if not decompEntities:
            return []

        _, dictReading, dictReadOpt, _, _, _ \
            = self.DICTIONARY_INFO[self.dictionary]
        self.checkOrderByWeight(orderBy)

        searchEntities = []
        for entities in decompEntities:
            searchEntities.extend(self.buildExactReadings(entities,
                dictReading, **dictReadOpt))

        searchOptions, filterList = self.getReadingSearchOptions(searchEntities)

        result = self.db.selectRows(select(
            [self.dictionaryTable.c[self.headwordColumn],
            self.dictionaryTable.c[self.headwordAlternativeColumn].label('a'),
            self.dictionaryTable.c.Reading, self.dictionaryTable.c.Translation],
            searchOptions, distinct=True).order_by(*orderBy).limit(limit))

        # filtering only needs to take place if the char string includes
        #   a varing length, a '?' will always be substituded with an _
        if searchString.find('*') != -1:
            result = self.filterResults(result, filterList)

        return result

    def searchDictionaryExact(self, searchString, readingN=None,
        orderBy=['Reading'], limit=None):
        """
        Searches the dictionary for exact matches for the given string that
        contain wildcards and a mixture of reading entities and characters.

        @type searchString: string
        @param searchString: search string
        @type readingN: string
        @param readingN: reading name
        @type limit: number
        @param limit: maximum number of entries
        @rtype: list of strings
        @return: SQL commands
        """
        selectQueries = []
        _, dictReading, dictReadOpt, _, _, _ \
            = self.DICTIONARY_INFO[self.dictionary]

        self.checkOrderByWeight(orderBy)

        # Chinese character string
        headwordSearchString = searchString.replace('*', '%').replace('?', '_')
        selectQueries.append(self.getDictionaryHeadwordSearchSQL(
            headwordSearchString, orderBy=[], limit=None))

        # translation string
        wordsTable = Table(self.dictionary + '_Words', self.db.metadata,
            autoload=True)
        table = self.dictionaryTable.join(wordsTable,
            and_(wordsTable.c.Headword \
                == self.dictionaryObject.c[self.headwordIndexColumn],
                wordsTable.c.Reading == self.dictionaryObject.c.Reading))

        selectQueries.append(select([self.headwordColumn,
            self.dictionaryObject.c.Reading,
            self.dictionaryObject.c.Translation],
            wordsTable.c.Word == searchString.lower(),
            from_obj=table, distinct=True))
        #table = self.dictionary + '_Words w JOIN ' + self.dictionary \
            #+ ' d ON (d.' + self.headwordIndexColumn + ' = w.Headword ' \
            #+ 'AND d.Reading = w.Reading)'
        #selectCommands.append(select(table,
            #['d.' + self.headwordColumn, 'd.' + self.headwordAlternativeColumn,
                #'d.Reading', 'Translation'],
            #{'Word': searchString.lower()}, distinctValues=True,
            #orderBy=orderBy, limit=limit))
            # TODO hack: LIMIT and ORDER BY incorporated over last select
            #  statement

        #print ' UNION '.join(selectCommands)
        #result = self.executeSQL(' UNION '.join(selectCommands))
            # TODO hack: LIMIT and ORDER BY incorporated over last select
            #  statement

        result = self.db.selectRows(
            union(*selectQueries).limit(limit).order_by(*orderBy))

        result.extend(self.doSearchDictionaryMixedReadingCharacter(
            searchString, readingN, orderBy=orderBy, limit=limit))

        return self.convertDictionaryResult(
            self.mixResults(result, orderColumn=2, limit=limit))

    def doSearchDictionaryContaining(self, searchString, readingN=None,
        orderBy=['Reading'], limit=None):
        """

        @type searchString: string
        @param searchString: search string
        @type readingN: string
        @param readingN: reading name
        @type limit: number
        @param limit: maximum number of entries
        @rtype: list of strings
        @return: SQL commands
        """
        selectQueries = []
        _, dictReading, dictReadOpt, _, _, _ \
            = self.DICTIONARY_INFO[self.dictionary]

        self.checkOrderByWeight(orderBy)

        # Chinese character string
        headwordSearchString = searchString.replace('*', '%').replace('?', '_')
        if not searchString.endswith('%'):
            headwordSearchString = headwordSearchString + '%'
        if not searchString.startswith('%'):
            headwordSearchString = '%' + headwordSearchString
        selectQueries.append(self.getDictionaryHeadwordSearchSQL(
            headwordSearchString, orderBy=[], limit=None))

        # translation string
        translationTokens = re.findall(ur'(?u)((?:\w|\d)+)',
            searchString.replace('*', '').replace('?', ''))

        if self.dictionaryHasFTS3 \
            and hasattr(self.dictionaryTable.c.Translation, 'match'):
            # dictionary has FTS3 fulltext search on SQLite
            selectQueries.append(select(
                [self.dictionaryTable.c[self.headwordColumn],
                self.dictionaryTable.c[self.headwordAlternativeColumn].label('a'),
                self.dictionaryTable.c.Reading,
                self.dictionaryTable.c.Translation],
                self.dictionaryTable.c.Translation.match(
                    ' '.join(translationTokens)),
                distinct=True))
        else:
            selectQueries.append(select(
                [self.dictionaryTable.c[self.headwordColumn],
                self.dictionaryTable.c[self.headwordAlternativeColumn].label('a'),
                self.dictionaryTable.c.Reading,
                self.dictionaryTable.c.Translation],
                self.dictionaryTable.c.Translation.like('%' + 
                    ' '.join(translationTokens) + '%'),
                distinct=True))
                #distinct=True).order_by(*orderBy))

        # TODO orderby
        #result = self.db.selectRows(
            #union(*selectQueries).limit(limit).order_by(*orderBy))
        result = self.db.selectRows(
            union(*selectQueries).limit(limit))

        # reading
        if not searchString.endswith('*'):
            searchString = searchString + '*'
        if not searchString.startswith('*'):
            searchString = '*' + searchString
        result.extend(self.doSearchDictionaryMixedReadingCharacter(searchString,
            readingN, orderBy=orderBy, limit=limit))

        return self.mixResults(result, orderColumn=2, limit=limit)

    def searchDictionaryExactNContaining(self, searchString, readingN=None,
        orderBy=['Reading'], limit=None):

        print "\n"
        print searchString
        print "\n"

        result = self.doSearchDictionaryContaining(searchString, readingN,
            orderBy, limit)

        # filter for exact headword
        filterList = [self.getCharacterFilter(searchString),
            self.getCharacterFilter(searchString,
                headwordColumn=self.headwordAlternativeColumn)]

        # add filter for exact reading string
        decompEntities = self.getReadingEntities(searchString, readingN)

        if decompEntities:
            _, dictReading, dictReadOpt, _, _, _ \
                = self.DICTIONARY_INFO[self.dictionary]

            searchEntities = []
            for entities in decompEntities:
                searchEntities.extend(self.buildExactReadings(entities,
                    dictReading, **dictReadOpt))

            _, readingFilterList = self.getReadingSearchOptions(searchEntities)
            filterList.extend(readingFilterList)

        # add filter for exact translation
        filterList.append(self.getTranslationFilter(searchString))

        # filter for exact matches
        exactMatches = self.filterResults(result, filterList)

        containingMatches = []
        for entry in result:
            if entry not in exactMatches:
                containingMatches.append(entry)

        return (self.convertDictionaryResult(exactMatches),
            self.convertDictionaryResult(containingMatches))

    def searchDictionarySimilarPronunciation(self, searchString,
        readingN=None, orderBy=['Reading'], limit=None):

        # reading string
        decompEntities = self.getReadingEntities(searchString, readingN)

        if not decompEntities:
            return []

        _, dictReading, dictReadOpt, _, _, _ \
            = self.DICTIONARY_INFO[self.dictionary]
        self.checkOrderByWeight(orderBy)

        similarEntities = []
        for entities in decompEntities:
            similarEntities.extend(self.getSimilarReadings(entities,
                dictReading, **dictReadOpt))

        if similarEntities:
            searchOptions, filterList = self.getReadingSearchOptions(
                similarEntities)

            # TODO
            result = self.db.selectRows(select(
                [self.dictionaryTable.c[self.headwordColumn],
                self.dictionaryTable.c[self.headwordAlternativeColumn].label('a'),
                self.dictionaryTable.c.Reading,
                self.dictionaryTable.c.Translation],
                searchOptions, distinct=True).order_by(*orderBy).limit(limit))

            # filtering only needs to take place if the char string includes
            #   a varing length, a '?' will always be substituded with an _
            if searchString.find('*') != -1:
                result = self.filterResults(result, filterList)

            return self.convertDictionaryResult(result)

        return []

    def searchDictionarySamePronunciationAs(self, searchString):
        """
        Searches the dictionary for all characters that have the same reading
        as the given headword.
        """
        tableA = self.dictionaryTable.alias('a')
        tableB = self.dictionaryTable.alias('b')
        fromObj = tableA.join(tableB, and_(tableA.c.Reading == tableB.c.Reading,
            tableA.c[self.headwordColumn] != tableB.c[self.headwordColumn]))
        result = self.db.selectRows(select(
            [tableA.c[self.headwordColumn],
            tableA.c[self.headwordAlternativeColumn].label('a'),
            tableA.c.Reading, tableA.c.Translation],
            tableB.c[self.headwordColumn] == searchString,
            from_obj=fromObj, distinct=True).order_by(tableA.c.Translation))

        return self.convertDictionaryResult(result)

    def getRandomDictionaryEntry(self):
        """
        Gets a random dictinonary entry.

        @todo Fix: Create a table to cache the table size and get trigger
            to update this in SQLite.
        """
        entryCount = self.db.selectScalar(
            select([func.count(self.dictionaryTable.c[self.headwordColumn])]))

        import random
        entryIdx = int(random.random() * entryCount)

        result = self.db.selectRows(select(
            [self.dictionaryTable.c[self.headwordColumn],
            self.dictionaryTable.c[self.headwordAlternativeColumn].label('a'),
            self.dictionaryTable.c.Reading,
            self.dictionaryTable.c.Translation]).offset(entryIdx).limit(1))
        return self.convertDictionaryResult(result)
