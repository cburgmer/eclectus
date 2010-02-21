#!/usr/bin/python
# -*- coding: utf-8  -*-
"""
High level dictionary access.
"""

import re
import random

from sqlalchemy import select
from sqlalchemy.sql import and_, or_, func

from cjklib.dictionary import EDICT, CEDICT, CEDICTGR, HanDeDict, CFDICT, search
from cjklib.reading import ReadingFactory
from cjklib import exception
from cjklib.util import cross

from libeclectus import util

class HeadwordEntity(search.Exact):
    """
    Exact search strategy class matching any single Chinese character from a
    headword.
    """
    def _getCharacters(self, headword):
        return [char for char in headword
            if util.getCJKScriptClass(char) == 'Han']

    def getWhereClause(self, headwordColumn, readingColumn, headwordStr,
        readingStr):
        """
        Returns a SQLAlchemy clause that is the necessary condition for a
        possible match. This clause is used in the database query. Results may
        then be further narrowed by L{getMatchFunction()}.

        @type headwordColumn: SQLAlchemy column instance
        @param headwordColumn: headword column to check against
        @type readingColumn: SQLAlchemy column instance
        @param readingColumn: reading column to check against
        @type headwordStr: str
        @param headwordStr: headword string
        @type readingStr: str
        @param readingStr: reading string
        @return: SQLAlchemy clause
        """
        characters = self._getCharacters(headwordStr)
        return headwordColumn.in_(characters)

    def getMatchFunction(self, headwordStr, readingStr):
        """
        Gets a function that returns C{True} if the entry matches any of the
        headword's characters.

        This method provides the sufficient condition for a match. Note that
        matches from other SQL clauses might get included which do not fulfill
        the conditions of L{getWhereClause()}.

        @type headwordStr: str
        @param headwordStr: headword string
        @type readingStr: str
        @param readingStr: reading string
        @rtype: function
        @return: function that returns C{True} if the entry is a match
        """
        characters = self._getCharacters(headwordStr)
        return lambda headword, reading: headword in characters


class HeadwordEntityReading(HeadwordEntity):
    """
    Exact search strategy class matching any single Chinese character from a
    headword with the reading as found in the headword.
    """
    def __init__(self):
        self._getCharactersOptions = None

    def setDictionaryInstance(self, dictInstance):
        self._dictInstance = dictInstance
        self._readingFactory = ReadingFactory(
            dbConnectInst=self._dictInstance.db)

        if (not hasattr(self._dictInstance, 'READING')
            or not hasattr(self._dictInstance, 'READING_OPTIONS')):
            raise ValueError('Incompatible dictionary')

    def _getCharacters(self, headwordStr, readingStr, **options):
        if self._getCharactersOptions != (headwordStr, readingStr):

            fromReading = options.get('reading', self._dictInstance.READING)
            try:
                entities = self._readingFactory.decompose(readingStr,
                    fromReading, **options)
                # convert
                convertedEntities = self._readingFactory.convertEntities(
                    entities, fromReading, self._dictInstance.READING,
                    sourceOptions=options,
                    targetOptions=self._dictInstance.READING_OPTIONS)

            except exception.DecompositionError:
                raise exception.ConversionError(
                    "Decomposition failed for '%s'." % readingStr)

            entities = [entity for entity in convertedEntities if entity != ' ']

            if len(entities) != len(headwordStr):
                raise exception.ConversionError(
                    "Mismatch of headword/reading length: '%s' / '%s'"
                        % (headwordStr, "', '".join(entities)))

            pairs = zip(list(headwordStr), entities)

            self._pairs = [(char, entity) for char, entity in pairs
                if util.getCJKScriptClass(char) == 'Han']

        if not self._pairs:
            raise exception.ConversionError("Conversion failed for '%s'/'%s'"
                % (headwordStr, readingStr))

        return self._pairs

    def getWhereClause(self, headwordColumn, readingColumn, headwordStr,
        readingStr, **options):
        pairs = self._getCharacters(headwordStr, readingStr, **options)
        # quick search, will be filtered later
        chars, readingEntities = zip(*pairs)

        return and_(headwordColumn.in_(chars),
            readingColumn.in_(readingEntities))

    def getMatchFunction(self, headwordStr, readingStr, **options):
        pairs = self._getCharacters(headwordStr, readingStr, **options)
        return lambda headword, reading: (headword, reading) in pairs


class _SimilarReadingWildcardBase(search._TonelessReadingWildcardBase):
    """
    Wildcard search base class for similar readings.
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

    @classmethod
    def _getSimilarPlainEntities(cls, plainEntity, reading):
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

    def _getWildcardForms(self, searchStr, **options):
        if self._getWildcardFormsOptions != (searchStr, options):
            decompEntities = self._getPlainForms(searchStr, **options)

            self._wildcardForms = []
            for entities in decompEntities:
                wildcardEntities = []
                for entity in entities:
                    if not isinstance(entity, basestring):
                        entity, plainEntity, _ = entity
                        if plainEntity is not None:
                            similar = self._getSimilarPlainEntities(plainEntity,
                                self._dictInstance.READING)
                            entities = [self._createTonalEntityWildcard(e)
                                    for e in similar]
                            wildcardEntities.append(entities)
                        else:
                            #wildcardEntities.append(entity)
                            wildcardEntities.append([entity])
                    elif self._supportWildcards:
                        #wildcardEntities.extend(
                            #self._parseWildcardString(entity))
                        wildcardEntities.extend([[s] for s in 
                            self._parseWildcardString(entity)])
                    else:
                        searchEntities.extend([[s] for s in list(entity)])

                #TODO Don't use cross product on similar reading instances
                #   directly. Implement that on the SQL side, as to minimize
                #   searches for the match function.
                wildcardEntities = cross(*wildcardEntities)

                # remove exact hits
                # TODO needs filtering later, too, then document feature
                if (options.get('noExact', False)
                    and entities in wildcardEntities):
                    wildcardEntities.remove(entities)

                #self._wildcardForms.append(wildcardEntities)
                self._wildcardForms.extend(wildcardEntities)

        return self._wildcardForms


class SimilarWildcardReading(search.SimpleReading, _SimilarReadingWildcardBase):
    """
    Reading based search strategy with support similar readings. For tonal
    readings other tonal combinations will be searched and if supported,
    syllable initials and finals will be exchanged with ambiguous or easy to
    misunderstand forms.
    """
    def __init__(self, **options):
        search.SimpleReading.__init__(self)
        _SimilarReadingWildcardBase.__init__(self, **options)

    def getWhereClause(self, column, searchStr, **options):
        if self._hasWildcardForms(searchStr, **options):
            queries = self._getWildcardQuery(searchStr, **options)
            return or_(*[self._like(column, query) for query in queries])
        else:
            # exact lookup
            queries = self._getSimpleQuery(searchStr, **options)
            return or_(*[self._equals(column, query) for query in queries])

    def getMatchFunction(self, searchStr, **options):
        if self._hasWildcardForms(searchStr, **options):
            return self._getWildcardMatchFunction(searchStr, **options)
        else:
            # exact matching, 6x quicker in Cpython for 'tian1an1men2'
            return self._getSimpleMatchFunction(searchStr, **options)


class _MixedSimilarReadingWildcardBase(
    search._MixedTonelessReadingWildcardBase, _SimilarReadingWildcardBase):

    def _getWildcardForms(self, readingStr, **options):
        def isReadingEntity(entity, cache={}):
            if entity not in cache:
                cache[entity] = self._readingFactory.isReadingEntity(entity,
                    self._dictInstance.READING,
                    **self._dictInstance.READING_OPTIONS)
            return cache[entity]

        if self._getWildcardFormsOptions != (readingStr, options):
            self._getWildcardFormsOptions = (readingStr, options)

            decompEntities = self._getPlainForms(readingStr, **options)

            # separate reading entities from non-reading ones
            self._wildcardForms = []
            for entities in decompEntities:
                searchEntities = []
                hasReadingEntity = hasHeadwordEntity = False
                for entity in entities:
                    if not isinstance(entity, basestring):
                        hasReadingEntity = True

                        entity, plainEntity, _ = entity
                        if plainEntity is not None:
                            similar = self._getSimilarPlainEntities(plainEntity,
                                self._dictInstance.READING)
                            entities = [self._createTonelessReadingWildcard(e)
                                    for e in similar]
                            searchEntities.append(entities)
                        else:
                            #searchEntities.append(
                                #self._createReadingWildcard(entity))
                            searchEntities.append(
                                [self._createReadingWildcard(entity)])
                    elif self._supportWildcards:
                        parsedEntities = self._parseWildcardString(entity)
                        #searchEntities.extend(parsedEntities)
                        searchEntities.extend([[s] for s in parsedEntities])
                        hasHeadwordEntity = hasHeadwordEntity or any(
                            isinstance(entity, self.HeadwordWildcard)
                            for entity in parsedEntities)
                    else:
                        hasHeadwordEntity = True
                        #searchEntities.extend(
                            #[self._createHeadwordWildcard(c) for c in entity])
                        searchEntities.extend(
                            [[self._createHeadwordWildcard(c)] for c in entity])

                #TODO Don't use cross product on similar reading instances
                #   directly. Implement that on the SQL side, as to minimize
                #   searches for the match function.
                searchEntities = cross(*searchEntities)

                # discard pure reading or pure headword strings as they will be
                #   covered through other strategies
                if hasReadingEntity and hasHeadwordEntity:
                    #self._wildcardForms.append(searchEntities)
                    self._wildcardForms.extend(searchEntities)

        return self._wildcardForms


class MixedSimilarWildcardReading(search.SimpleReading,
    _MixedSimilarReadingWildcardBase):
    """
    Reading search strategy that supplements
    L{SimilarWildcardReading} to allow intermixing of similar readings with
    single characters from the headword. By default wildcard searches are
    supported.

    This strategy complements the basic search strategy. It is not built to
    return results for plain reading or plain headword strings.
    """
    def __init__(self, supportWildcards=True):
        search.SimpleReading.__init__(self)
        _MixedSimilarReadingWildcardBase.__init__(self, supportWildcards)

    def getWhereClause(self, headwordColumn, readingColumn, searchStr,
        **options):
        """
        Returns a SQLAlchemy clause that is the necessary condition for a
        possible match. This clause is used in the database query. Results may
        then be further narrowed by L{getMatchFunction()}.

        @type headwordColumn: SQLAlchemy column instance
        @param headwordColumn: headword column to check against
        @type readingColumn: SQLAlchemy column instance
        @param readingColumn: reading column to check against
        @type searchStr: str
        @param searchStr: search string
        @return: SQLAlchemy clause
        """
        queries = self._getWildcardQuery(searchStr, **options)
        if queries:
            return or_(*[
                    and_(self._like(headwordColumn, headwordQuery),
                        self._like(readingColumn, readingQuery))
                    for headwordQuery, readingQuery in queries])
        else:
            return None

    def getMatchFunction(self, searchStr, **options):
        return self._getWildcardMatchFunction(searchStr, **options)


class ExactMultiple(search.Exact):
    """Exact search strategy class matching any strings from a list."""
    @staticmethod
    def _getSubstrings(headwordStr):
        headwordSubstrings = []
        for left in range(0, len(headwordStr)):
            for right in range(len(headwordStr), left, -1):
                headwordSubstrings.append(headwordStr[left:right])
        return headwordSubstrings

    def getWhereClause(self, column, headwordStr):
        return column.in_(self._getSubstrings(headwordStr))

    def getMatchFunction(self, headwordStr):
        searchStrings = self._getSubstrings(headwordStr)
        return lambda cell: cell in searchStrings


class ExtendedDictionarySupport(object):
    """
    Partial class that adds further searching capabilities to dictionaries:
        - Get all entries for single entities of a headword entry
        - Get all entries for substrings of a headword
        - Search for similar pronunciations
        - Search for similar pronunciations mixed with headword
        - Get a random entry

    TODO
        - Unify entries with same headword
        - Split entries with different translation fields
    """
    DEFAULT_SEARCH_STRATEGIES = {
            'headwordSearchStrategy': search.Wildcard,
            'readingSearchStrategy': search.Wildcard,
            'translationSearchStrategy': search.SimpleWildcardTranslation,
            }

    @classmethod
    def _setDefaults(cls, options, defaults=None):
        defaults = defaults or cls.DEFAULT_SEARCH_STRATEGIES
        for strategy in cls.DEFAULT_SEARCH_STRATEGIES:
            if strategy not in options:
                print cls.DEFAULT_SEARCH_STRATEGIES[strategy]
                options[strategy] = cls.DEFAULT_SEARCH_STRATEGIES[strategy](
                    singleCharacter='?', multipleCharacters='*')

    def __init__(self, **options):
        """
        Initialises the ExtendedDictionarySupport instance.

        @keyword headwordEntitiesSearchStrategy: headword entities search
            strategy instance
        @keyword headwordSubstringSearchStrategy: headword substring search
            strategy instance
        """
        if 'headwordEntitiesSearchStrategy' in options:
            self.headwordEntitiesSearchStrategy \
                = options['headwordEntitiesSearchStrategy']
        else:
            self.headwordEntitiesSearchStrategy = HeadwordEntity()
            """Strategy for searching single headword entities."""
        if hasattr(self.headwordEntitiesSearchStrategy,
            'setDictionaryInstance'):
            self.headwordEntitiesSearchStrategy.setDictionaryInstance(self)

        if 'headwordSubstringSearchStrategy' in options:
            self.headwordSubstringSearchStrategy \
                = options['headwordSubstringSearchStrategy']
        else:
            self.headwordSubstringSearchStrategy = ExactMultiple()
            """Strategy for searching headword substrings."""
        if hasattr(self.headwordSubstringSearchStrategy,
            'setDictionaryInstance'):
            self.headwordSubstringSearchStrategy.setDictionaryInstance(self)

        if 'readingSimilarSearchStrategy' in options:
            self.readingSimilarSearchStrategy \
                = options['readingSimilarSearchStrategy']
        else:
            self.readingSimilarSearchStrategy = None
            """Strategy for searching similar readings."""
        if hasattr(self.readingSimilarSearchStrategy, 'setDictionaryInstance'):
            self.readingSimilarSearchStrategy.setDictionaryInstance(self)

        if 'mixedSimilarReadingSearchStrategy' in options:
            self.mixedSimilarReadingSearchStrategy \
                = options['mixedSimilarReadingSearchStrategy']
        else:
            self.mixedSimilarReadingSearchStrategy = None
            """Strategy for mixed searching of headword/similar reading."""
        if (self.mixedSimilarReadingSearchStrategy
            and hasattr(self.mixedSimilarReadingSearchStrategy,
                'setDictionaryInstance')):
            self.mixedSimilarReadingSearchStrategy.setDictionaryInstance(self)

    def _getHeadwordEntitiesSearch(self, headwordStr, readingStr, **options):
        dictionaryTable = self.db.tables[self.DICTIONARY_TABLE]

        headwordEntitiesClause \
            = self.headwordEntitiesSearchStrategy.getWhereClause(
                dictionaryTable.c.Headword, dictionaryTable.c.Reading,
                headwordStr, readingStr, **options)

        headwordEntitiesMatchFunc \
            = self.headwordEntitiesSearchStrategy.getMatchFunction(
                headwordStr, readingStr, **options)

        return ([headwordEntitiesClause],
            [(['Headword', 'Reading'], headwordEntitiesMatchFunc)])

    def getForHeadwordEntities(self, headwordStr, readingStr=None, limit=None,
        orderBy=None, **options):
        # TODO raises conversion error
        clauses, filters = self._getHeadwordEntitiesSearch(headwordStr,
            readingStr, **options)

        return self._search(or_(*clauses), filters, limit, orderBy)

    def _getHeadwordSubstringSearch(self, headwordStr, **options):
        dictionaryTable = self.db.tables[self.DICTIONARY_TABLE]

        headwordSubstringClause \
            = self.headwordSubstringSearchStrategy.getWhereClause(
                dictionaryTable.c.Headword, headwordStr)

        headwordSubstringMatchFunc \
            = self.headwordSubstringSearchStrategy.getMatchFunction(headwordStr)

        return ([headwordSubstringClause],
            [(['Headword'], headwordSubstringMatchFunc)])

    def getForHeadwordSubstring(self, headwordStr, limit=None, orderBy=None):
        clauses, filters = self._getHeadwordSubstringSearch(headwordStr)

        return self._search(or_(*clauses), filters, limit, orderBy)

    def _getSimilarReadingSearch(self, readingStr, **options):
        dictionaryTable = self.db.tables[self.DICTIONARY_TABLE]

        clauses = []
        filters = []

        # reading search
        readingClause = self.readingSimilarSearchStrategy.getWhereClause(
            dictionaryTable.c.Reading, readingStr, **options)
        clauses.append(readingClause)

        readingMatchFunc = self.readingSimilarSearchStrategy.getMatchFunction(
            readingStr, **options)
        filters.append((['Reading'], readingMatchFunc))

        # mixed search
        if self.mixedSimilarReadingSearchStrategy:
            mixedClause = self.mixedSimilarReadingSearchStrategy.getWhereClause(
                dictionaryTable.c.Headword, dictionaryTable.c.Reading,
                readingStr, **options)
            if mixedClause:
                clauses.append(mixedClause)

                mixedReadingMatchFunc \
                    = self.mixedSimilarReadingSearchStrategy.getMatchFunction(
                        readingStr, **options)
                filters.append((['Headword', 'Reading'],
                    mixedReadingMatchFunc))

        return clauses, filters

    def getForSimilarReading(self, readingStr, limit=None, orderBy=None,
        **options):
        # TODO raises conversion error
        clauses, filters = self._getSimilarReadingSearch(readingStr, **options)

        return self._search(or_(*clauses), filters, limit, orderBy)

    def getRandomEntry(self):
        dictionaryTable = self.db.tables[self.DICTIONARY_TABLE]
        entryCount = self.db.selectScalar(
            select([func.count(dictionaryTable.c[self.COLUMNS[0]])]))

        entryIdx = random.randrange(entryCount)

        # lookup in db
        results = self.db.selectRows(
            select([dictionaryTable.c[col] for col in self.COLUMNS])\
                .offset(entryIdx).limit(1))

        # format readings and translations
        for column, formatStrategy in self.columnFormatStrategies.items():
            columnIdx = self.COLUMNS.index(column)
            for idx in range(len(results)):
                rowList = list(results[idx])
                rowList[columnIdx] = formatStrategy.format(rowList[columnIdx])
                results[idx] = tuple(rowList)

        # format results
        entries = self.entryFactory.getEntries(results)

        return entries


class ExtendedCEDICTStyleSupport(ExtendedDictionarySupport):
    DEFAULT_SEARCH_STRATEGIES = {
            'headwordSearchStrategy': search.Wildcard,
            'readingSearchStrategy': search.TonelessWildcardReading,
            'mixedReadingSearchStrategy': search.MixedTonelessWildcardReading,
            'translationSearchStrategy': search.SimpleWildcardTranslation,
            }

    def __init__(self, **options):
        ExtendedDictionarySupport.__init__(self, **options)
        if 'readingSimilarSearchStrategy' not in options:
            options['readingSimilarSearchStrategy'] = SimilarWildcardReading()
        if 'mixedSimilarReadingSearchStrategy' not in options:
            options['mixedSimilarReadingSearchStrategy'] \
                = MixedSimilarWildcardReading()
        if 'headwordEntitiesSearchStrategy' not in options:
            options['headwordEntitiesSearchStrategy'] = HeadwordEntityReading()

    def _getHeadwordEntitiesSearch(self, headwordStr, readingStr, **options):
        dictionaryTable = self.db.tables[self.DICTIONARY_TABLE]

        clauses = []
        filters = []

        headwordEntitiesMatchFunc \
            = self.headwordEntitiesSearchStrategy.getMatchFunction(
                headwordStr, readingStr, **options)

        if self.headword != 't':
            clauses.append(self.headwordEntitiesSearchStrategy.getWhereClause(
                dictionaryTable.c.HeadwordSimplified,
                dictionaryTable.c.Reading, headwordStr, readingStr, **options))
            filters.append((['HeadwordSimplified', 'Reading'],
                headwordEntitiesMatchFunc))
        if self.headword != 's':
            clauses.append(self.headwordEntitiesSearchStrategy.getWhereClause(
                dictionaryTable.c.HeadwordTraditional,
                dictionaryTable.c.Reading, headwordStr, readingStr, **options))
            filters.append((['HeadwordTraditional', 'Reading'],
                headwordEntitiesMatchFunc))

        return clauses, filters

    def _getHeadwordSubstringSearch(self, headwordStr, **options):
        dictionaryTable = self.db.tables[self.DICTIONARY_TABLE]

        clauses = []
        filters = []
        if self.headword != 't':
            clauses.append(self.headwordSubstringSearchStrategy.getWhereClause(
                dictionaryTable.c.HeadwordSimplified, headwordStr))
            filters.append((['HeadwordSimplified'],
                self.headwordSubstringSearchStrategy.getMatchFunction(
                    headwordStr)))
        if self.headword != 's':
            clauses.append(self.headwordSubstringSearchStrategy.getWhereClause(
                dictionaryTable.c.HeadwordTraditional, headwordStr))
            filters.append((['HeadwordTraditional'],
                self.headwordSubstringSearchStrategy.getMatchFunction(
                    headwordStr)))

        return clauses, filters

    def _getSimilarReadingSearch(self, readingStr, **options):
        dictionaryTable = self.db.tables[self.DICTIONARY_TABLE]

        clauses = []
        filters = []

        # reading search
        readingClause = self.readingSimilarSearchStrategy.getWhereClause(
            dictionaryTable.c.Reading, readingStr, **options)
        clauses.append(readingClause)

        readingMatchFunc = self.readingSimilarSearchStrategy.getMatchFunction(
            readingStr, **options)
        filters.append((['Reading'], readingMatchFunc))

        # mixed search
        if self.mixedSimilarReadingSearchStrategy:
            mixedClauses = []
            if self.headword != 't':
                mixedClauseS \
                    = self.mixedSimilarReadingSearchStrategy.getWhereClause(
                        dictionaryTable.c.HeadwordSimplified,
                        dictionaryTable.c.Reading, readingStr, **options)
                if mixedClauseS: mixedClauses.append(mixedClauseS)
            if self.headword != 's':
                mixedClauseT \
                    = self.mixedSimilarReadingSearchStrategy.getWhereClause(
                        dictionaryTable.c.HeadwordTraditional,
                        dictionaryTable.c.Reading, readingStr, **options)
                if mixedClauseT: mixedClauses.append(mixedClauseT)

            if mixedClauses:
                clauses.extend(mixedClauses)
                mixedReadingMatchFunc \
                    = self.mixedSimilarReadingSearchStrategy.getMatchFunction(
                        readingStr, **options)
                if self.headword != 't':
                    filters.append((['HeadwordSimplified', 'Reading'],
                        mixedReadingMatchFunc))
                if self.headword != 's':
                    filters.append((['HeadwordTraditional', 'Reading'],
                        mixedReadingMatchFunc))

        return clauses, filters


class ExtendedEDICT(EDICT, ExtendedDictionarySupport):
    def __init__(self, **options):
        self._setDefaults(options)
        EDICT.__init__(self, **options)
        ExtendedDictionarySupport.__init__(self, **options)


class ExtendedCEDICTGR(CEDICTGR, ExtendedDictionarySupport):
    # TODO similar reading support for CEDICTGR
    def __init__(self, **options):
        self._setDefaults(options)
        self._setDefaults(options, {
            'translationSearchStrategy': search.CEDICTWildcardTranslation,
            'headwordEntitiesSearchStrategy': HeadwordEntityReading
            })
        CEDICTGR.__init__(self, **options)
        ExtendedDictionarySupport.__init__(self, **options)


class ExtendedCEDICT(CEDICT, ExtendedCEDICTStyleSupport):
    def __init__(self, **options):
        self._setDefaults(options)
        self._setDefaults(options,
            {'translationSearchStrategy': search.CEDICTWildcardTranslation})
        CEDICT.__init__(self, **options)
        ExtendedCEDICTStyleSupport.__init__(self, **options)


class ExtendedHanDeDict(HanDeDict, ExtendedCEDICTStyleSupport):
    def __init__(self, **options):
        self._setDefaults(options)
        self._setDefaults(options,
            {'translationSearchStrategy': search.HanDeDictWildcardTranslation})
        HanDeDict.__init__(self, **options)
        ExtendedCEDICTStyleSupport.__init__(self, **options)


class ExtendedCFDICT(CFDICT, ExtendedCEDICTStyleSupport):
    def __init__(self, **options):
        self._setDefaults(options)
        self._setDefaults(options,
            {'translationSearchStrategy': search.HanDeDictWildcardTranslation})
        CFDICT.__init__(self, **options)
        ExtendedCEDICTStyleSupport.__init__(self, **options)
