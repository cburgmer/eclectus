#!/usr/bin/python
# -*- coding: utf-8  -*-
"""
Character information.
"""

import re

from sqlalchemy import select
from sqlalchemy.sql import and_, or_

from cjklib.dbconnector import getDBConnector
from cjklib.characterlookup import CharacterLookup
from cjklib import exception

from libeclectus.util import cachedproperty, getDatabaseConfiguration

class CharacterDB(CharacterLookup):
    LANGUAGE_CHAR_LOCALE_MAPPING = {'zh-cmn-Hans': 'C', 'zh-cmn-Hant': 'T',
        'zh-yue-Hans': 'C', 'zh-yue-Hant': 'T', 'ko': 'K', 'ja': 'J', 'vi': 'V'}
    """Mapping table for language to default character locale."""

    LANGUAGE_CHAR_DOMAIN_MAPPING = {
        'zh-cmn-Hans': ['GB2312', 'IICore', 'Unicode'],
        'zh-cmn-Hant': ['BIG5', 'IICore', 'Unicode'],
        'zh-yue-Hans': ['GB2312', 'IICore', 'Unicode'],
        'zh-yue-Hant': ['BIG5HKSCS', 'BIG5', 'IICore', 'Unicode'],
        'ko': ['IICore', 'Unicode'],
        'ja': ['JISX0208', 'JISX0208_0213', 'IICore', 'Unicode'],
        'vi': ['IICore', 'Unicode']
        }
    """
    Mapping table for language to (reasonable) character domains. Most
    appropriate first.
    """

    AMBIGUOUS_INITIALS = {'Pinyin': {
            'alveolar/retroflex': [('z', 'zh'), ('c', 'ch'), ('s', 'sh')],
            'aspirated': [('b', 'p'), ('g', 'k'), ('d', 't'), ('j', 'q'),
                ('z', 'c'), ('zh', 'ch')],
            'other consonants': [('n', 'l'), ('l', 'r'), ('f', 'h'),
                ('f', 'hu')]},
        # TODO add long aa -> short a for Cantonese
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
        # TODO maybe add stop finals for Cantonese
        'CantoneseYale': {
            'final': [('k', 't'), ('ng', 'n')],
            },
        'Jyutping': {
            'final': [('k', 't'), ('ng', 'n')],
            },
        }
    """Groups of similar sounding syllable finals."""

    RADICALS_NON_VISUAL_EQUIVALENCE = set([u'⺄', u'⺆', u'⺇', u'⺈', u'⺊',
        u'⺌', u'⺍', u'⺎', u'⺑', u'⺗', u'⺜', u'⺥', u'⺧', u'⺪', u'⺫', u'⺮',
        u'⺳', u'⺴', u'⺶', u'⺷', u'⺻', u'⺼', u'⻏', u'⻕'])
    """
    Radical forms for which we don't want to retrieve a equivalent character as
    it would resemble another radical form.
    """

    @classmethod
    def getSimilarPlainEntities(cls, plainEntity, reading):
        # TODO the following is not independent of reading and really slow
        similar = [plainEntity]
        if reading in cls.AMBIGUOUS_INITIALS:
            for key in cls.AMBIGUOUS_INITIALS[reading]:
                for tpl in cls.AMBIGUOUS_INITIALS[reading][key]:
                    a, b = tpl
                    if re.match(a + u'[aeiouü]', plainEntity):
                        similar.append(b + plainEntity[len(a):])
                    elif re.match(b + u'[aeiouü]', plainEntity):
                        similar.append(a + plainEntity[len(b):])
        # for all initial derived forms change final
        if reading in cls.AMBIGUOUS_FINALS:
            for modEntity in similar[:]:
                for key in cls.AMBIGUOUS_FINALS[reading]:
                    for tpl in cls.AMBIGUOUS_FINALS[reading][key]:
                        a, b = tpl
                        if re.search(u'[^aeiouü]' + a + '$',
                            modEntity):
                            similar.append(modEntity[:-len(a)] + b)
                        elif re.search(u'[^aeiouü]' + b + '$',
                            modEntity):
                            similar.append(modEntity[:-len(b)] + a)
        return similar

    def __init__(self, language, characterDomain=None, databaseUrl=None,
        dbConnectInst=None, ignoreIllegalSettings=False, **options):

        dbConnectInst = dbConnectInst or getDBConnector(
            getDatabaseConfiguration(databaseUrl))

        locale = self.LANGUAGE_CHAR_LOCALE_MAPPING[language]
        CharacterLookup.__init__(self, locale, characterDomain or 'Unicode',
            dbConnectInst=dbConnectInst)

        self.language = language

        # choose a better character domain if non specified
        if (characterDomain
            and characterDomain not in self.LANGUAGE_CHAR_DOMAIN_MAPPING[
                    self.language]):
            if ignoreIllegalSettings:
                characterDomain = None
            else:
                raise ValueError(
                    "Illegal character domain '%s' for language '%s'"
                    % (characterDomain, self.language))
        if not characterDomain:
            self.setCharacterDomain(self._getCharacterDomain())

        if locale != 'T':
            self._characterLookupTraditional = CharacterLookup('T',
                dbConnectInst=self.db)

    def _getCharacterDomain(self):
        availableDomains = self.getAvailableCharacterDomains()
        for domain in self.LANGUAGE_CHAR_DOMAIN_MAPPING[self.language]:
            if domain in availableDomains:
                return domain

        return 'Unicode'

    def getCompatibleCharacterDomains(self):
        availableDomains = self.getAvailableCharacterDomains()
        return [domain for domain
            in self.LANGUAGE_CHAR_DOMAIN_MAPPING[self.language]
            if domain in availableDomains]

    def isLanguage(self, lang):
        return self.language.startswith(lang)

    def getLanguage(self, lang):
        return '-'.join([code for code in lang.split('-') if len(code) < 4])

    def getCharacterVariants(self, char):
        """Gets a list of variant forms of the given character."""
        variants = set(char)
        # get variants from Unihan, exclude Chinese mappings if not Chinese
        variants.update([c for c, t in self.getAllCharacterVariants(char)
            if self.isLanguage('zh') or t not in 'ST'])
        # get radical equivalent char
        if self.isRadicalChar(char):
            try:
                equivChar = self.getRadicalFormEquivalentCharacter(char)
                variants.add(equivChar)
            except exception.UnsupportedError:
                # pass if no equivalent char exists
                pass

        return variants

    def getCharacterSimilars(self, char):
        """Gets a list of similar forms of the given character."""
        return self.getEquivalentCharTable([char],
            includeEquivalentRadicalForms=False,
            includeSimilarCharacters=True)[0]

    #{ radicals and components

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
                radicalIdx = self.getKangxiRadicalIndex(component)

                if includeEquivalentRadicalForms:
                    # if includeRadicalVariants is set get all forms
                    componentEquivalents.update(
                        self.getKangxiRadicalRepresentativeCharacters(
                            radicalIdx))
                    if self.locale != 'T':
                        componentEquivalents.update(
                            self._characterLookupTraditional\
                                .getKangxiRadicalRepresentativeCharacters(
                                    radicalIdx))
                else:
                    if self.isRadicalChar(component):
                        if component \
                            not in self.RADICALS_NON_VISUAL_EQUIVALENCE:
                            try:
                                componentEquivalents.add(
                                    self.getRadicalFormEquivalentCharacter(
                                        component))
                            except exception.UnsupportedError:
                                # pass if no equivalent char existent
                                pass
                    else:
                        componentEquivalents.update(set(
                            self.getCharacterEquivalentRadicalForms(component))
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
                            if self.isRadicalChar(similarChar):
                                componentEquivalents.add(
                                    self.getRadicalFormEquivalentCharacter(
                                        similarChar))
                            else:
                                componentEquivalents.update(
                                    self.getCharacterEquivalentRadicalForms(
                                        similarChar))
                        except exception.UnsupportedError:
                            pass
                        except ValueError:
                            pass

            equivCharTable.append(list(componentEquivalents))

        return equivCharTable

    def getCharacterListForKangxiRadicalIndex(self, radicalIndex,
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
            entryList = self.getResidualStrokeCountForRadicalIndex(radicalIndex)
        else:
            entryList = self.getResidualStrokeCountForKangxiRadicalIndex(
                radicalIndex)

        characterGroups = {None: {}, 'radical': {}}

        # radicals
        radicalForms = set()
        representativeCharacters = set(
            self.getKangxiRadicalRepresentativeCharacters(radicalIndex))
        if self.locale != 'T':
            representativeCharacters.update(self._characterLookupTraditional\
                .getKangxiRadicalRepresentativeCharacters(radicalIndex))

        for radicalForm in representativeCharacters:
            if not self.isRadicalChar(radicalForm):
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

    def getCharactersForComponents(self, componentList,
        includeEquivalentRadicalForms=False, resultIncludeRadicalForms=False,
        includeAllGlyphs=False, includeSimilarCharacters=False):
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
        @type resultIncludeRadicalForms: bool
        @param resultIncludeRadicalForms: if C{True} the result will include
            I{Unicode radical forms} and I{Unicode radical variants}
        @type includeAllGlyphs: bool
        @param includeAllGlyphs: if C{True} all matches will be returned, if
            C{False} only those with glyphs matching the locale's default one
            will be returned
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

        characters = self.getCharactersForEquivalentComponents(equivCharTable,
            resultIncludeRadicalForms=resultIncludeRadicalForms,
            includeAllGlyphs=includeAllGlyphs)

        # TODO once we require use an OrderedSet for this, see
        #   http://code.activestate.com/recipes/576694/
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
        lookupTable = self.db.tables['ComponentLookup']
        strokeCountTable = self.db.tables['StrokeCount']

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
        if self.characterDomain != 'Unicode':
            domainTblName = self.characterDomain + 'Set'
            characterDomainTable = self.db.tables[domainTblName]
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

        result = self.db.selectScalars(sel)

        # augment result with equivalent forms
        # TODO only check for true radical components included in table, save work
        augmentedResult = self.getEquivalentCharTable(result,
            includeEquivalentRadicalForms, includeSimilarCharacters)

        resultSet = set()
        for characterList in augmentedResult:
            resultSet.update(characterList)
        return resultSet

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
            if self.isBinaryIDSOperator(layout):
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

        treeList = self.getDecompositionTreeList(char)
        if not treeList:
            return None
        else:
            # TODO more sophisticated, get the "nicest" decomposition
            _, tree = splitFlatTree(char, treeList[0])
            return tree

    @cachedproperty
    def radicalFormEquivalentCharacterMap(self):
        table = self.db.tables['RadicalEquivalentCharacter']
        equivalentMap = dict(self.db.selectRows(
            select([table.c.EquivalentForm, table.c.Form],
                table.c.Locale.like(self._locale(self.locale)))))

        for radicalForm in self.RADICALS_NON_VISUAL_EQUIVALENCE:
            if radicalForm in equivalentMap:
                del equivalentMap[radicalForm]

        return equivalentMap

    @cachedproperty
    def minimalCharacterComponents(self):
        """
        Gets a list of minimal character components grouped by stroke count.

        @rtype: list of list of characters
        @returns: minimal character components
        @todo Impl: Implement a locale/character domain based set of minimal
            components instead of all Kangxi radical forms.
        """
        table = self.db.tables['KangxiRadicalStrokeCount']
        strokeCountDict = dict(self.db.selectRows(select(
            [table.c.RadicalIndex, table.c.StrokeCount])))

        minimalCharacterComponents = {}

        for radicalIdx in range(1, 215):
            mainForm = self.getKangxiRadicalForm(radicalIdx)

            variants = self.getKangxiRadicalVariantForms(radicalIdx)

            if self.locale != 'T':
                radicalLocaleForm = mainForm
                mainForm = self._characterLookupTraditional\
                    .getKangxiRadicalForm(radicalIdx)
                if mainForm != radicalLocaleForm:
                    variants.insert(0, radicalLocaleForm)
            strokeCount = strokeCountDict[radicalIdx]

            if strokeCount not in minimalCharacterComponents:
                minimalCharacterComponents[strokeCount] = set()
            minimalCharacterComponents[strokeCount].add(mainForm)
            minimalCharacterComponents[strokeCount].update(variants)

        return minimalCharacterComponents

    @cachedproperty
    def kangxiRadicalNameTable(self):
        cjkLang = self.getLanguage(self.language)
        tableName = 'RadicalNames_' + cjkLang.replace('-', '_')
        if self.db.hasTable(tableName):
            return self.db.tables[tableName]
        else:
            return None

    @cachedproperty
    def kangxiRadicalForms(self):
        """
        Gets a list of Kangxi radicals forms sorted by the radical index. One
        entry consists of the traditional main form, its stroke count and
        radical variant forms (the first entry being the locale dependent main
        form, in case it is different to the traditional form).

        @rtype: dict of tuples
        @returns: kangxi radical forms
        """
        kangxiRadicalForms = {}

        formsDict = {}
        variantsDict = dict([(radIdx, []) for radIdx in range(1, 215)])
        table = self.db.tables['KangxiRadicalStrokeCount']
        strokeCountDict = dict(self.db.selectRows(select(
            [table.c.RadicalIndex, table.c.StrokeCount])))

        # get names of radicals to enhance search
        radicalNamesDict = {}
        if self.kangxiRadicalNameTable:
            table = self.kangxiRadicalNameTable
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

        # TODO Optimise, don't create 400 SQL select commands
        # group by stroke count
        for radicalIdx in range(1, 215):
            representativeForms \
                = set(self.getKangxiRadicalRepresentativeCharacters(
                    radicalIdx))
            if radicalIdx in radicalNamesDict:
                representativeForms.update(radicalNamesDict[radicalIdx])
            kangxiRadicalForms[radicalIdx] = (formsDict[radicalIdx],
                strokeCountDict[radicalIdx], variantsDict[radicalIdx],
                representativeForms)

        return kangxiRadicalForms

    def getRadicalDictionaryEntries(self, targetLang='en'):
        """
        Gets the readings and definitions of all Kangxi radicals.

        @rtype: dict
        @return: radical index, reading and definition
        @todo Fix: Don't use dictionary language, but rather interface language
        """
        # TODO targetLang only evaluated once. This method is outside the scope
        #   of this class
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
                    if not definition:
                        definition = ''

                    entryDict[radicalIndex] = ('', definition)

                self._radicalDictionaryDict = entryDict

        return self._radicalDictionaryDict

    #{ other

    def getCharacterIndex(self, char, indexTable):
        """Returns a distinct index for a character using the given table."""
        if self.db.hasTable(indexTable):
            table = self.db.tables[indexTable]
            return self.db.selectScalar(select(
                    [table.c.CharValue], table.c.ChineseCharacter == char))
