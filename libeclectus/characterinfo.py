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
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.sql import and_, or_, func

import cjklib
from cjklib.dbconnector import DatabaseConnector
from cjklib import characterlookup
from cjklib.reading import ReadingFactory
from cjklib import exception
from cjklib.util import cross

from libeclectus import util
from libeclectus.dictionary import (getDictionaryClasses, getDictionary,
    getDefaultDictionary, getAvailableDictionaryNames,
    LANGUAGE_COMPATIBLE_MAPPINGS)
from libeclectus.chardb import CharacterDB

class CharacterInfo:
    """
    Provides lookup method services.
    """
    LANGUAGE_CHAR_LOCALE_MAPPING = {'zh-cmn-Hans': 'C', 'zh-cmn-Hant': 'T',
        'zh-yue-Hant': 'T', 'zh-yue-Hans': 'C', 'ko': 'T', 'ja': 'J', 'vi': 'V'}
    """Mapping table for language to default character locale."""

    LOCALE_LANGUAGE_MAPPING = {'zh': 'zh-cmn-Hans', 'zh_CN': 'zh-cmn-Hans',
        'zh_SG': 'zh-cmn-Hans', 'zh_TW': 'zh-cmn-Hant', 'zh_HK': 'zh-yue',
        'zh_MO': 'zh-yue', 'ja': 'ja', 'ko': 'ko', 'vi': 'vi'}
    """Mapping table for locale to default language."""

    LANGUAGE_DEFAULT_READING = {'zh-cmn-Hans': 'Pinyin',
        'zh-cmn-Hant': 'Pinyin', 'zh-yue-Hant': 'CantoneseYale', 'ko': 'Hangul',
        'ja': 'Kana', 'zh-yue-Hans': 'CantoneseYale'}
    """Character locale's default character reading."""

    DICTIONARY_LANG = {'HanDeDict': 'zh-cmn', 'CFDICT': 'zh-cmn',
        'CEDICT': 'zh-cmn', 'CEDICTGR': 'zh-cmn-Hant', 'EDICT': 'ja'}
    """Dictionaries to CJK language mapping."""

    DICTIONARY_TRANSLATION_LANG = {'HanDeDict': 'de', 'CFDICT': 'fr',
        'CEDICT': 'en', 'CEDICTGR': 'en', 'EDICT': 'en'}
    """Dictionaries to translation language mapping."""

    PRONUNCIATION_READING = {'Pronunciation_zh_cmn': ('Pinyin', {}),
        'Pronunciation_zh_yue': ('CantoneseYale', {})}
    """Table of audio files options."""

    AVAILABLE_READINGS = {
        'zh-cmn-Hans': ['Pinyin', 'WadeGiles', 'MandarinIPA', 'GR'],
        'zh-cmn-Hant': ['Pinyin', 'WadeGiles', 'MandarinIPA', 'GR'],
        'zh-yue-Hans': ['Jyutping', 'CantoneseYale'],
        'zh-yue-Hant': ['Jyutping', 'CantoneseYale'], 'ko': ['Hangul'],
        'ja': ['Kana']}
    """All readings available for a language."""

    INCOMPATIBLE_READINGS = [('Pinyin', 'GR'), ('GR', 'WadeGiles'),
        ('GR', 'MandarinIPA')]
    """Reading conversions incompatible under practical considerations."""

    READING_OPTIONS = {'WadeGiles': {'toneMarkType': 'superscriptNumbers'}}
    """Special reading options for output."""

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

    def __init__(self, language=None, reading=None, dictionary=None,
        characterDomain=None, databaseUrl=None, translationLanguage=None):
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
        self.getAvailableDictionaries()

        self._dictionaryInst = None
        if dictionary:
            self._dictionaryInst = getDictionary(dictionary, reading=reading,
                language=language, characterDomain=characterDomain,
                dbConnectInst=self.db, ignoreIllegalSettings=True)

        # fallback
        if not self._dictionaryInst:
            self._dictionaryInst = getDefaultDictionary(translationLanguage,
                reading=reading, language=language,
                characterDomain=characterDomain, dbConnectInst=self.db,
                ignoreIllegalSettings=True)

        self.dictionary = self._dictionaryInst.PROVIDES
        self.language = self._dictionaryInst.language
        self.reading = self._dictionaryInst.reading

        self.locale = self.LANGUAGE_CHAR_LOCALE_MAPPING[self.language]

        self.characterLookup = CharacterDB(self.language,
            characterDomain=characterDomain, dbConnectInst=self.db,
            ignoreIllegalSettings=True)
        self.characterDomain = self.characterLookup.characterDomain

        self.characterLookupTraditional = characterlookup.CharacterLookup('T',
            dbConnectInst=self.db)

        self.readingFactory = ReadingFactory(dbConnectInst=self.db)

        # get incompatible reading conversions
        self.incompatibleConversions = {}
        for lang in self.AVAILABLE_READINGS:
            for r in self.AVAILABLE_READINGS[lang]:
                self.incompatibleConversions[r] = set()
        for readingA, readingB in self.INCOMPATIBLE_READINGS:
            self.incompatibleConversions[readingA].add(readingB)
            self.incompatibleConversions[readingB].add(readingA)

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

        self._availableCharacterDomains = self.characterLookup.getAvailableCharacterDomains() # TODO
        self.getCompatibleCharacterDomains() # TODO

    #{ Settings

    @staticmethod
    def getLanguage(language):
        languageCodes = language.split('-')
        # return ISO 639-2 and ISO 639-3 code
        return '-'.join([code for code in languageCodes if len(code) < 4])

    def getAvailableDictionaries(self):
        """
        Gets a list of available dictionaries supported.

        @rtype: list of strings
        @return: names of available dictionaries
        """
        if self.availableDictionaries == None:
            self.availableDictionaries = getAvailableDictionaryNames(self.db)
        return self.availableDictionaries

    def getDictionaryVersions(self):
        dictionaries = getAvailableDictionaryNames(self.db, includePseudo=False)
        dictionaryVersions = self.getUpdateVersions(dictionaries)

        versionDict = {}
        for dictionaryClss in getDictionaryClasses():
            dictionaryName = dictionaryClss.DICTIONARY_TABLE
            if dictionaryName in dictionaryVersions:
                versionDict[dictionaryName] = dictionaryVersions[dictionaryName]
            else:
                versionDict[dictionaryName] = None
        return versionDict

    def getCompatibleDictionaries(self, language):
        compatible = []
        for dictionary in self.getAvailableDictionaryNames():
            cjkLang = self.DICTIONARY_LANG[dictionary]
            if language.startswith(cjkLang):
                compatible.append(dictionary)

        compatible.sort(key=str.lower)
        return compatible

    def getCompatibleReadings(self, language):
        return LANGUAGE_COMPATIBLE_MAPPINGS[language]
        #compatible = []
        #if self.dictionary and self._dictionaryInst.READING:
            #dictReading = self._dictionaryInst.READING
            #for reading in self.AVAILABLE_READINGS[language]:
                #if dictReading == reading \
                    #or (self.readingFactory.isReadingConversionSupported(
                        #dictReading, reading) and \
                    #reading not in self.incompatibleConversions[dictReading]):
                    #compatible.append(reading)
        #else:
            #compatible = self.AVAILABLE_READINGS[language]

        #compatible.sort()
        #return compatible

    def getCompatibleCharacterDomains(self):
        if not hasattr(self, 'compatibleCharDomain'):
            self.compatibleCharDomain = self.characterLookup.getCompatibleCharacterDomains()
        return self.compatibleCharDomain

    def getCompatibleReadingsFor(self, language, dictionary):
        compatible = []
        if dictionary and self._dictionaryInst.READING:
            dictReading = self._dictionaryInst.READING
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
        return self._availableCharacterDomains
        #return self.characterLookup.getAvailableCharacterDomains()

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

    def getReadingOptions(self, string, reading=None):
        """
        Guesses the reading options using the given string to support reading
        dialects.

        @type string: string
        @param string: reading string
        @type reading: string
        @param reading: reading name
        @rtype: dictionary
        @returns: reading options
        """
        reading = reading or self.reading
        # guess reading parameters
        if reading:
            classObj = self.readingFactory.getReadingOperatorClass(reading)
            if hasattr(classObj, 'guessReadingDialect'):
                return classObj.guessReadingDialect(string)
        return {}

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
                cjkLang = self.getLanguage(self.language)
                tableName = 'RadicalNames_' + cjkLang.replace('-', '_')
                if self.db.hasTable(tableName):
                    self.radicalNameTableName = tableName
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

    def getRadicalDictionaryEntries(self, targetLang='en'):
        """
        Gets the readings and definitions of all Kangxi radicals.

        @rtype: dict
        @return: radical index, reading and definition
        @todo Fix: Don't use dictionary language, but rather interface language
        """
        # TODO don't use specific language for zh: zh-cmn and zh-yue can share
        if not hasattr(self, '_radicalDictionaryDict'):
            radicalTableName = None
            cjkLang = self.getLanguage(self.language)
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

    def getPronunciationFile(self, pronunciation, reading=None, **options):
        """
        Gets the file name of the pronunciation sound file if it exists.

        @type pronunciation: str/unicode
        @param pronunciation: pronunciation to retrieve the audio file for
        @rtype: unicode
        @return: file name
        """
        reading = reading or self.reading

        if reading not in self.pronunciationLookup:
            return None

        pronunciationTableName = self.pronunciationLookup[reading]
        if not self.db.hasTable(pronunciationTableName):
            return None

        pronunciationTableReading, pronunciationTableOpt \
            = self.PRONUNCIATION_READING[pronunciationTableName]

        try:
            pronunciationConv = self.readingFactory.convert(pronunciation,
                reading, pronunciationTableReading,
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

    def getHeadwordVariants(self, headword):
        """
        Gets a list of variant forms of the given headword.

        @type headword: string
        @param headword: headword
        @rtype: list of strings
        @return: headword variant forms
        """
        variantEntries = self._dictionaryInst.getVariantsForHeadword(headword)
        return [e.Headword for e in variantEntries if e.Headword != headword]

    def getHeadwordSimilars(self, headword):
        """
        Gets a list of similar forms of the given headword.

        @type headword: string
        @param headword: headword
        @rtype: list of strings
        @return: headword variant forms
        """
        similarEntries = self._dictionaryInst.getSimilarsForHeadword(headword,
            orderBy=['Reading'])
            #orderBy=['Reading', 'Headword']) # TODO doesn't work for CEDICT
        return [e.Headword for e in similarEntries if e.Headword != headword]

    #{ Dictionary search

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
        return self._dictionaryInst.getForHeadword(searchString, limit=limit)

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
        entriesSet = set()
        entries = [(e.Headword, e.Reading)
            for e in self._dictionaryInst.getForHeadword(searchString)]
        if not entries:
            entries = [(searchString, None)]

        for headword, reading in entries:
            entriesSet.update(self._dictionaryInst.getEntitiesForHeadword(
                headword, reading, limit=limit))
        if limit:
            return list(entriesSet)[:limit]
        else:
            return list(entriesSet)

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
        # TODO no exact
        return self._dictionaryInst.getForHeadword('*' + searchString + '*',
            orderBy=orderBy, limit=limit)

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
        return self._dictionaryInst.getSubstringsForHeadword(searchString,
            limit=limit)

    def searchDictionaryExactNContaining(self, searchString, readingN=None,
        orderBy=['Reading'], limit=None):

        # TODO where are the containing
        return (self._dictionaryInst.getFor(searchString,
            orderBy=orderBy, limit=limit,
            **self.getReadingOptions(searchString, readingN)),
                self._dictionaryInst.getFor('*' + searchString + '*',
            orderBy=orderBy, limit=limit,
            **self.getReadingOptions(searchString, readingN)))

    def searchDictionarySimilarPronunciation(self, searchString,
        readingN=None, orderBy=['Reading'], limit=None):

        return self._dictionaryInst.getForSimilarReading(searchString,
            orderBy=orderBy, limit=limit,
            **self.getReadingOptions(searchString, readingN))

    def searchDictionarySamePronunciationAs(self, searchString, limit=None):
        """
        Searches the dictionary for all characters that have the same reading
        as the given headword.
        """
        entriesSet = set()
        for e in self._dictionaryInst.getForHeadword(searchString):
            entriesSet.update(self._dictionaryInst.getForReading(
                e.Reading, limit=limit))
        if searchString in entriesSet:
            entriesSet.remove(searchString)
        if limit:
            return list(entriesSet)[:limit]
        else:
            return list(entriesSet)

    def getRandomDictionaryEntry(self):
        """
        Gets a random dictinonary entry.

        @todo Fix: Create a table to cache the table size and get trigger
            to update this in SQLite.
        """
        return self._dictionaryInst.getRandomEntry()
