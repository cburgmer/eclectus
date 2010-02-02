#!/usr/bin/python
# -*- coding: utf-8  -*-
"""
High level dictionary access.
"""

import re

from sqlalchemy.sql import and_, or_

from cjklib.dictionary import ExactSearchStrategy, TonelessReadingSearchStrategy
from cjklib.dictionary import EDICT, CEDICT, CEDICTGR, HanDeDict, CFDICT
from cjklib.reading import ReadingFactory
from cjklib import exception
from cjklib.util import cross

from libeclectus import util

class HeadwordEntitySearchStrategy(ExactSearchStrategy):
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


class HeadwordEntityReadingSearchStrategy(HeadwordEntitySearchStrategy):
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

            entities = [entity for entity in entities if entity != ' ']

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
        chars = [char for char, _ in pairs]
        readingEntities = [entity for _, entity in pairs]

        return and_(headwordColumn.in_(chars),
            readingColumn.in_(readingEntities))

    def getMatchFunction(self, headwordStr, readingStr, **options):
        pairs = self._getCharacters(headwordStr, readingStr, **options)
        return lambda headword, reading: (headword, reading) in pairs


class SimilarReadingSearchStrategy(TonelessReadingSearchStrategy):
    """
    Reading based search strategy with support similar readings. For tonal
    readings other tonal combinations will be searched and if supported,
    syllable initials and finals will be exchanged with ambiguous or easy to
    misunderstand forms.
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

    def __init__(self):
        TonelessReadingSearchStrategy.__init__(self)
        self._getSimilarReadingsOptions = None

    def _getPlainForms(self, searchStr, **options):
        def isPlainReadingEntity(entity, cache={}):
            if entity not in cache:
                cache[entity] = self._readingFactory.isPlainReadingEntity(
                    entity, self._dictInstance.READING,
                    **self._dictInstance.READING_OPTIONS)
            return cache[entity]

        def getPlainEntity(entity, cache={}):
            if entity not in cache:
                try:
                    cache[entity], _ = self._readingFactory.splitEntityTone(
                        entity, self._dictInstance.READING,
                        **self._dictInstance.READING_OPTIONS)
                except (exception.InvalidEntityError,
                    exception.UnsupportedError):
                    cache[entity] = None
            return cache[entity]

        if self._getSimilarReadingsOptions != (searchStr, options):

            decompositionEntities \
                = TonelessReadingSearchStrategy._getPlainForms(self, searchStr,
                    **options)
            # TODO Optimize for Pinyin to remove decompositions with single 'n'
            #   or 'ng'

            isTonal = (self._readingFactory.isReadingOperationSupported(
                    'isPlainReadingEntity', self._dictInstance.READING)
                and self._readingFactory.isReadingOperationSupported(
                    'splitEntityTone', self._dictInstance.READING))

            self._similarDecompositions = []
            for decomposition in decompositionEntities:

                similarEntities = []
                for entity in decomposition:
                    if isinstance(entity, basestring):
                            similarEntities.append([entity])
                            continue

                    _, plainEntity, _ = entity

                    # TODO the following is not independent of reading and really slow
                    similar = [plainEntity]
                    if self._dictInstance.READING in self.AMBIGUOUS_INITIALS:
                        for key in self.AMBIGUOUS_INITIALS[
                            self._dictInstance.READING]:
                            for tpl in self.AMBIGUOUS_INITIALS[
                                self._dictInstance.READING][key]:
                                a, b = tpl
                                if re.match(a + u'[aeiouü]', plainEntity):
                                    similar.append(b + plainEntity[len(a):])
                                elif re.match(b + u'[aeiouü]', plainEntity):
                                    similar.append(a + plainEntity[len(b):])
                    # for all initial derived forms change final
                    if self._dictInstance.READING in self.AMBIGUOUS_FINALS:
                        for modEntity in similar[:]:
                            for key in self.AMBIGUOUS_FINALS[
                                self._dictInstance.READING]:
                                for tpl in self.AMBIGUOUS_FINALS[
                                    self._dictInstance.READING][key]:
                                    a, b = tpl
                                    if re.search(u'[^aeiouü]' + a + '$',
                                        modEntity):
                                        similar.append(modEntity[:-len(a)] + b)
                                    elif re.search(u'[^aeiouü]' + b + '$',
                                        modEntity):
                                        similar.append(modEntity[:-len(b)] + a)

                    # append as plain entity, no tone as we search for all
                    similarEntities.append([(None, s, None) for s in similar])

                similarEntityList = cross(*similarEntities)

                # remove exact hits
                # TODO needs filtering later, too, then document feature
                if (options.get('noExact', False)
                    and entities in similarEntityList):
                    similarEntityList.remove(entities)

                self._similarDecompositions.extend(similarEntityList)

        return self._similarDecompositions


class ExactMultipleSearchStrategy(object):
    """Exact search strategy class matching any strings from a list."""
    def getWhereClause(self, column, searchStrings):
        """
        Returns a SQLAlchemy clause that is the necessary condition for a
        possible match. This clause is used in the database query. Results may
        then be further narrowed by L{getMatchFunction()}.

        @type column: SQLAlchemy column instance
        @param column: column to check against
        @type searchStrings: list of str
        @param searchStrings: search strings
        @return: SQLAlchemy clause
        """
        return column.in_(searchStrings)

    def getMatchFunction(self, searchStrings):
        """
        Gets a function that returns C{True} if the entry's cell content matches
        any of the search strings.

        This method provides the sufficient condition for a match. Note that
        matches from other SQL clauses might get included which do not fulfill
        the conditions of L{getWhereClause()}.

        @type searchStrings: list of str
        @param searchStrings: search strings
        @rtype: function
        @return: function that returns C{True} if the entry is a match
        """
        return lambda cell: cell in searchStrings


class ExtendedDictionarySupport(object):
    """
    Partial class that adds further searching capabilities to dictionaries:
        - Get all entries for single entities of a headword entry
        - Get all entries for substrings of a headword
        - Search for similar pronunciations
    TODO
        - Search for similar pronunciations mixed with headword
        - Get a random entry

    TODO
        - Unify entries with same headword
        - Split entries with different translation fields
    """
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
            self.headwordEntitiesSearchStrategy \
                = HeadwordEntitySearchStrategy()
            """Strategy for searching single headword entities."""
        if hasattr(self.headwordEntitiesSearchStrategy,
            'setDictionaryInstance'):
            self.headwordEntitiesSearchStrategy.setDictionaryInstance(self)

        if 'headwordSubstringSearchStrategy' in options:
            self.headwordSubstringSearchStrategy \
                = options['headwordSubstringSearchStrategy']
        else:
            self.headwordSubstringSearchStrategy \
                = ExactMultipleSearchStrategy()
            """Strategy for searching headword substrings."""
        if hasattr(self.headwordSubstringSearchStrategy,
            'setDictionaryInstance'):
            self.headwordSubstringSearchStrategy.setDictionaryInstance(self)

        if 'readingSimilarSearchStrategy' in options:
            self.readingSimilarSearchStrategy \
                = options['readingSimilarSearchStrategy']
        else:
            self.readingSimilarSearchStrategy = SimilarReadingSearchStrategy()
            """Strategy for searching similar readings."""
        if hasattr(self.readingSimilarSearchStrategy, 'setDictionaryInstance'):
            self.readingSimilarSearchStrategy.setDictionaryInstance(self)

        self.mixedSimilarReadingSearchStrategy = options.get(
            'mixedSimilarReadingSearchStrategy', None) # TODO set one by default
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

    def getForHeadwordEntities(self, headwordStr, readingStr, limit=None,
        orderBy=None, **options):
        # TODO raises conversion error
        clauses, filters = self._getHeadwordEntitiesSearch(headwordStr,
            readingStr, **options)

        return self._search(or_(*clauses), filters, limit, orderBy)

    def _getHeadwordSubstringSearch(self, headwordStr, **options):
        headwordSubstrings = []
        for left in range(0, len(headwordStr)):
            for right in range(len(headwordStr), left, -1):
                headwordSubstrings.append(headwordStr[left:right])

        dictionaryTable = self.db.tables[self.DICTIONARY_TABLE]

        headwordSubstringClause \
            = self.headwordSubstringSearchStrategy.getWhereClause(
                dictionaryTable.c.Headword, headwordSubstrings)

        headwordSubstringMatchFunc \
            = self.headwordSubstringSearchStrategy.getMatchFunction(
                headwordSubstrings)

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


class ExtendedCEDICTStyleSupport(ExtendedDictionarySupport):
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
        headwordSubstrings = []
        for left in range(0, len(headwordStr)):
            for right in range(len(headwordStr), left, -1):
                headwordSubstrings.append(headwordStr[left:right])

        dictionaryTable = self.db.tables[self.DICTIONARY_TABLE]

        clauses = []
        filters = []
        if self.headword != 't':
            clauses.append(self.headwordSubstringSearchStrategy.getWhereClause(
                dictionaryTable.c.HeadwordSimplified, headwordSubstrings))
            filters.append((['HeadwordSimplified'],
                self.headwordSubstringSearchStrategy.getMatchFunction(
                    headwordSubstrings)))
        if self.headword != 's':
            clauses.append(self.headwordSubstringSearchStrategy.getWhereClause(
                dictionaryTable.c.HeadwordTraditional, headwordSubstrings))
            filters.append((['HeadwordTraditional'],
                self.headwordSubstringSearchStrategy.getMatchFunction(
                    headwordSubstrings)))

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


class ExtendedCEDICT(CEDICT, ExtendedCEDICTStyleSupport):
    def __init__(self, **options):
        if 'headwordEntitiesSearchStrategy' not in options:
            options['headwordEntitiesSearchStrategy'] \
                = HeadwordEntityReadingSearchStrategy()
        CEDICT.__init__(self, **options)
        ExtendedCEDICTStyleSupport.__init__(self, **options)

