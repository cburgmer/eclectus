#!/usr/bin/python
# -*- coding: utf-8  -*-
"""
High level dictionary access.
"""
__all__ = [
    "DICTIONARY_LANG", "DICTIONARY_TRANSLATION_LANG",
    "LANGUAGE_COMPATIBLE_MAPPINGS",
    # access methods
    "getDictionaryClasses", "getDictionaryClass", "getDictionary",
    "getDictionaryClassForLang", "getDictionaryForLang",
    # dictionaries
    "ExtendedEDICT", "ExtendedCEDICTGR", "ExtendedCEDICT", "ExtendedHanDeDict",
    "ExtendedCFDICT"]

import re
import random
import types

from sqlalchemy import select
from sqlalchemy.sql import and_, or_, func

from cjklib.dictionary import EDICT, CEDICT, CEDICTGR, HanDeDict, CFDICT
from cjklib.dictionary import search, format, entry
from cjklib.reading import ReadingFactory
from cjklib import exception
from cjklib.util import cross
from cjklib.dbconnector import getDBConnector

from libeclectus.chardb import CharacterDB
from libeclectus import util

DICTIONARY_LANG = {'HanDeDict': 'zh-cmn', 'CFDICT': 'zh-cmn',
    'CEDICT': 'zh-cmn', 'CEDICTGR': 'zh-cmn-Hant', 'EDICT': 'ja'}
"""Dictionaries to (generic) CJK language mapping."""

DICTIONARY_DEFAULT_LANG = {'HanDeDict': 'zh-cmn-Hans', 'CFDICT': 'zh-cmn-Hans',
    'CEDICT': 'zh-cmn-Hans', 'CEDICTGR': 'zh-cmn-Hant', 'EDICT': 'ja'}
"""Dictionaries to default CJK language mapping."""

DICTIONARY_TRANSLATION_LANG = {'HanDeDict': 'de', 'CFDICT': 'fr',
    'CEDICT': 'en', 'CEDICTGR': 'en', 'EDICT': 'en'}
"""Dictionaries to translation language mapping."""

LANGUAGE_COMPATIBLE_MAPPINGS = {
    'zh-cmn-Hant': ['Pinyin', 'WadeGiles', 'MandarinIPA'],
    'zh-cmn-Hans': ['Pinyin', 'WadeGiles', 'MandarinIPA'],
    'zh-yue-Hant': ['Jyutping', 'CantoneseYale'],
    'zh-yue-Hans': ['Jyutping', 'CantoneseYale'],
    'ko': ['Hangul'],
    'ja': ['Kana']}
"""Compatible reading mappings per language."""

def getDictionaryClasses():
    """
    Gets all classes in module that implement L{BaseDictionary}.

    @rtype: set
    @return: list of all classes inheriting form L{BaseDictionary}
    """
    dictionaryModule = __import__("libeclectus.dictionary")
    # get all classes that inherit from BaseDictionary
    return set([clss \
        for clss in dictionaryModule.dictionary.__dict__.values() \
        if type(clss) == types.TypeType \
        and issubclass(clss, _ExtendedDictionarySupport) \
        and hasattr(clss, 'PROVIDES') and clss.PROVIDES])

def getAvailableDictionaryNames(dbConnectInst=None, includePseudo=True):
    """
    Returns a list of available dictionary names for the given database
    connection.

    @type dbConnectInst: instance
    @param dbConnectInst: optional instance of a L{DatabaseConnector}
    @type includePseudo: bool
    @param includePseudo: if C{True} pseudo dictionaries will be included in
        list
    @rtype: list of class
    @return: list of dictionary class objects
    """
    global DICTIONARY_LANG
    dbConnectInst = dbConnectInst or getDBConnector()
    available = []
    languages = []
    for dictionaryClass in getDictionaryClasses():
        if dictionaryClass.available(dbConnectInst):
            available.append(dictionaryClass.PROVIDES)
            lang = DICTIONARY_LANG.get(dictionaryClass.PROVIDES, None)
            if lang:
                languages.append(lang)

    if includePseudo:
        for lang in PseudoDictionary.SUPPORTED_LANG:
            for generalLang in languages:
                if lang.startswith(generalLang):
                    break
            else:
                available.append('PSEUDO_%s' % lang)

    return available

def getDictionaryLanguage(dictionaryName):
    global DICTIONARY_LANG
    if dictionaryName.startswith('PSEUDO_'):
        language = dictionaryName[7:]
    else:
        language = DICTIONARY_LANG[dictionaryName]
    return language

_dictionaryMap = None
def getDictionaryClass(dictionaryName):
    """
    Get a dictionary class by dictionary name.

    @type dictionaryName: str
    @param dictionaryName: dictionary name
    @rtype: type
    @return: dictionary class
    """
    global _dictionaryMap
    if _dictionaryMap is None:
        _dictionaryMap = dict([(dictCls.PROVIDES, dictCls)
            for dictCls in getDictionaryClasses()])

    if dictionaryName.startswith('PSEUDO_'):
        raise ValueError('Pseudo dictionaries not supported')
    elif dictionaryName not in _dictionaryMap:
        raise ValueError('Not a supported dictionary')
    return _dictionaryMap[dictionaryName]

def getDictionary(dictionaryName, dbConnectInst=None, **options):
    """
    Get a dictionary instance by dictionary name. Returns C{None} if the
    dictionary is not available.

    @type dictionaryName: str
    @param dictionaryName: dictionary name
    @rtype: type
    @return: dictionary instance
    """
    dbConnectInst = dbConnectInst or getDBConnector()
    if dictionaryName.startswith('PSEUDO_'):
        language = dictionaryName[7:]
        if 'language' in options:
            if language != options['language']:
                raise ValueError("Invalid language specified")
            else:
                del options['language']
        return PseudoDictionary(language, dbConnectInst=dbConnectInst,
            **options)
    else:
        dictCls = getDictionaryClass(dictionaryName)
        if not dictCls.available(dbConnectInst):
            return None
        else:
            return dictCls(dbConnectInst=dbConnectInst, **options)

_languageMap = None
def _getLanguageMap():
    global _languageMap, DICTIONARY_LANG, DICTIONARY_DEFAULT_LANG
    global DICTIONARY_TRANSLATION_LANG
    if _languageMap is None:
        _languageMap = {}
        for dictName in DICTIONARY_LANG:
            cjkLang = DICTIONARY_LANG[dictName]
            translationLang = DICTIONARY_TRANSLATION_LANG.get(dictName, None)
            if cjkLang not in _languageMap or translationLang == 'en':
                _languageMap[cjkLang] = dictName
            if translationLang:
                _languageMap[(cjkLang, translationLang)] = dictName

        for dictName in DICTIONARY_DEFAULT_LANG:
            cjkLang = DICTIONARY_DEFAULT_LANG[dictName]
            translationLang = DICTIONARY_TRANSLATION_LANG.get(dictName, None)
            _languageMap[cjkLang] = dictName
            _languageMap[(cjkLang, translationLang)] = dictName

    return _languageMap

def getDictionaryClassForLang(cjkLang, translationLang=None):
    """
    Get a dictionary class by dictionary name.

    @type cjkLang: str
    @param cjkLang: CJK language
    @type translationLang: str
    @param translationLang: translation language
    @rtype: type
    @return: dictionary class
    """
    languageMap = _getLanguageMap()

    if translationLang:
        key = (cjkLang, translationLang)
    else:
        key = cjkLang
    if key not in languageMap:
        raise ValueError('No dictionary for given language')
    return getDictionaryClass(languageMap[key])

def hasRealDictionaryForLang(cjkLang, translationLang=None):
    """
    Checks if a dictionary exists for the given language setting.

    @type cjkLang: str
    @param cjkLang: CJK language
    @type translationLang: str
    @param translationLang: translation language
    @rtype: bool
    @return: C{True} if dictionary exists
    """
    if translationLang:
        key = (cjkLang, translationLang)
    else:
        key = cjkLang
    languageMap = _getLanguageMap()
    return key in languageMap and languageMap[key]

def getDictionaryForLang(cjkLang, translationLang=None, **options):
    """
    Get a dictionary instance by dictionary name. If no dictionary is given for
    both the cjk language and the translation language a dictionary is chosen
    that matches the cjk language, and if none is found a pseudo dictionary is
    returned.

    @type cjkLang: str
    @param cjkLang: CJK language
    @type translationLang: str
    @param translationLang: translation language
    @rtype: type
    @return: dictionary instance
    """
    if hasRealDictionaryForLang(cjkLang, translationLang):
        dictCls = getDictionaryClassForLang(cjkLang, translationLang)
        return dictCls(**options)
    elif hasRealDictionaryForLang(cjkLang):
        dictCls = getDictionaryClassForLang(cjkLang)
        return dictCls(**options)
    else:
        return PseudoDictionary(cjkLang, **options)

def getDefaultDictionary(translationLang=None, dbConnectInst=None, **options):
    """
    Tries to choose the best dictionary from a database for the given
    translation language. This method can be used if no more information is
    known about the user's preferences. Translation language can be derived
    from the client's language setting.
    """
    def testAvailability(dictName):
        if dictName in tested:
            return False
        else:
            tested.append(dictName)
            dictClss = getDictionaryClass(dictName)
            return dictClss.available(dbConnectInst)

    global DICTIONARY_TRANSLATION_LANG
    tested = []
    dbConnectInst = dbConnectInst or getDBConnector()

    # choose CEDICT as default
    if (not translationLang
        or (translationLang == 'en' and testAvailability('CEDICT'))):
        return getDictionary('CEDICT', dbConnectInst=dbConnectInst, **options)

    # find dictionary matching the translation language
    if translationLang:
        for dictName, transLang in DICTIONARY_TRANSLATION_LANG.items():
            if transLang == translationLang and testAvailability(dictName):
                return getDictionary(dictName, dbConnectInst=dbConnectInst,
                    **options)

    # fallback, choose random
    for dictName in sorted(DICTIONARY_TRANSLATION_LANG.keys()):
        if testAvailability(dictName):
            return getDictionary(dictName, dbConnectInst=dbConnectInst,
                **options)

    # no dictionary available, use pseudo
    return PseudoDictionary('zh-cmn-Hans', dbConnectInst=dbConnectInst,
        **options)

#{ entry factories

class HeadwordAlternative(entry.UnifiedHeadword):
    """
    Factory adding a simple X{Headword} key for CEDICT style dictionaries to
    provide results compatible with EDICT. An alternative headword is given as
    key 'HeadwordAlternative'.
    """
    def _unifyHeadwords(self, entry):
        entry = list(entry)
        if self.headword == 's':
            headwords = (entry[0], entry[1])
        else:
            headwords = (entry[1], entry[0])

        if headwords[0] == headwords[1]:
            entry.extend((headwords[0], None))
        else:
            entry.extend(headwords)
        return entry

    def setDictionaryInstance(self, dictInstance):
        entry.NamedTuple.setDictionaryInstance(self, dictInstance)
        if not hasattr(dictInstance, 'COLUMNS'):
            raise ValueError('Incompatible dictionary')

        self.columnNames = (dictInstance.COLUMNS
            + ['Headword', 'HeadwordAlternative'])


class EDICTEntry(entry.UnifiedHeadword):
    """
    Factory adding a simple X{Headword} key for CEDICT style dictionaries to
    provide results compatible with EDICT. An alternative headword is given as
    key 'HeadwordAlternative'.
    """
    def _unifyHeadwords(self, entry):
        entry = list(entry)
        entry.insert(1, entry[0])
        return entry

    def setDictionaryInstance(self, dictInstance):
        entry.NamedTuple.setDictionaryInstance(self, dictInstance)
        if not hasattr(dictInstance, 'COLUMNS'):
            raise ValueError('Incompatible dictionary')

        self.columnNames = ['Headword', 'HeadwordAlternative', 'Reading',
            'Translation']


class CEDICTEntry(EDICTEntry):
    """
    Factory adding a simple X{Headword} key for CEDICT style dictionaries to
    provide results compatible with EDICT. An alternative headword is given as
    key 'HeadwordAlternative'.
    """
    def _unifyHeadwords(self, entry):
        entry = list(entry)
        if self.headword == 's':
            headwords = (entry[0], entry[1])
        else:
            headwords = (entry[1], entry[0])

        entry[0:2] = headwords
        return entry

#{ search strategies

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
    # TODO fix to cope with missing reading
    def __init__(self, **options):
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
                self._pairs = None
                raise exception.ConversionError(
                    "Decomposition failed for '%s'." % readingStr)

            entities = [entity for entity in convertedEntities if entity != ' ']

            if len(entities) != len(headwordStr):
                print entities
                print headwordStr
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
                            similar = CharacterDB.getSimilarPlainEntities(
                                plainEntity, self._dictInstance.READING)
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
                            similar = CharacterDB.getSimilarPlainEntities(
                                plainEntity, self._dictInstance.READING)
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


class HeadwordVariant(search.Exact):
    """Search strategy class matching variants of a given headword."""
    def __init__(self, language, **options):
        self.language = language

    def setDictionaryInstance(self, dictInstance):
        search.Exact.setDictionaryInstance(self, dictInstance)
        self._characterDB = CharacterDB(language=self.language,
            characterDomain='Unicode', dbConnectInst=dictInstance.db)

    # TODO cached
    def _getPossibleHeadwordVariants(self, headwordStr):
        singleCharacterVariants = [self._characterDB.getCharacterVariants(char)
            for char in headwordStr]

        variants = set(map(''.join, cross(*singleCharacterVariants)))
        variants.remove(headwordStr)
        return variants

    def getWhereClause(self, column, headwordStr):
        searchStrings = self._getPossibleHeadwordVariants(headwordStr)
        if searchStrings:
            return column.in_(searchStrings)
        else:
            return None

    def getMatchFunction(self, headwordStr):
        searchStrings = self._getPossibleHeadwordVariants(headwordStr)
        return lambda cell: cell in searchStrings


class HeadwordSimilar(search.Exact):
    """Search strategy class matching similar strings of a given headword."""
    def __init__(self, language, **options):
        self.language = language

    def setDictionaryInstance(self, dictInstance):
        search.Exact.setDictionaryInstance(self, dictInstance)
        self._characterDB = CharacterDB(language=self.language,
            characterDomain='Unicode', dbConnectInst=dictInstance.db)

    # TODO cached
    def _getPossibleHeadwordSimilars(self, headwordStr):
        singleCharacterSimilars = [self._characterDB.getCharacterSimilars(char)
            for char in headwordStr]

        variants = set(map(''.join, cross(*singleCharacterSimilars)))
        variants.remove(headwordStr)
        return variants

    def getWhereClause(self, column, headwordStr):
        searchStrings = self._getPossibleHeadwordSimilars(headwordStr)
        if searchStrings:
            return column.in_(searchStrings)
        else:
            return None

    def getMatchFunction(self, headwordStr):
        searchStrings = self._getPossibleHeadwordSimilars(headwordStr)
        return lambda cell: cell in searchStrings

#{ dictionary classes

class _ExtendedDictionarySupport(object):
    """
    Partial class that adds further searching capabilities to dictionaries:
        - Get all entries for single entities of a headword entry
        - Get all entries for substrings of a headword
        - Search for similar pronunciations
        - Search for similar pronunciations mixed with headword
        - Get a random entry

    TODO
    Further features:
        - Unify entries with same headword
        - Split entries with different translation fields
    """
    def __init__(self, **options):
        """
        Initialises the _ExtendedDictionarySupport instance.

        @keyword headwordEntitiesSearchStrategy: headword entities search
            strategy instance
        @keyword headwordSubstringSearchStrategy: headword substring search
            strategy instance
        """
        self.language = options.get('language',
            DICTIONARY_DEFAULT_LANG[self.PROVIDES])

        ignoreIllegalSettings = options.get('ignoreIllegalSettings', False)
        reading = options.get('reading', None)
        if (reading
            and reading not in LANGUAGE_COMPATIBLE_MAPPINGS[self.language]):
            if ignoreIllegalSettings:
                reading = None
            else:
                raise ValueError("Illegal reading '%s' for language '%s'"
                    % (reading, self.language))


        self.reading = reading or self.READING

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

        if 'headwordVariantSearchStrategy' in options:
            self.headwordVariantSearchStrategy \
                = options['headwordVariantSearchStrategy']
        else:
            self.headwordVariantSearchStrategy = HeadwordVariant(self.language)
            """Strategy for searching headword substrings."""
        if hasattr(self.headwordVariantSearchStrategy,
            'setDictionaryInstance'):
            self.headwordVariantSearchStrategy.setDictionaryInstance(self)

        if 'headwordSimilarSearchStrategy' in options:
            self.headwordSimilarSearchStrategy \
                = options['headwordSimilarSearchStrategy']
        else:
            self.headwordSimilarSearchStrategy = HeadwordSimilar(self.language)
            """Strategy for searching headword substrings."""
        if hasattr(self.headwordSimilarSearchStrategy,
            'setDictionaryInstance'):
            self.headwordSimilarSearchStrategy.setDictionaryInstance(self)

        dictionaryTable = self.db.tables[self.DICTIONARY_TABLE]
        self._dictionaryPrefer = 'Weight' in dictionaryTable.columns

    def _checkOrderByWeight(self, orderBy):
        if orderBy and 'Weight' in orderBy:
            if self._dictionaryPrefer:
                dictionaryTable = self.db.tables[self.DICTIONARY_TABLE]

                orderByWeight = func.ifnull(dictionaryTable.c.Weight, 100)
                orderBy[orderBy.index('Weight')] =  orderByWeight
            else:
                orderBy.remove('Weight')

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

    def getEntitiesForHeadword(self, headwordStr, readingStr=None, limit=None,
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

    def getSubstringsForHeadword(self, headwordStr, limit=None, orderBy=None):
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
        if self.readingSimilarSearchStrategy is None:
            return []
        # TODO raises conversion error
        clauses, filters = self._getSimilarReadingSearch(readingStr, **options)

        return self._search(or_(*clauses), filters, limit, orderBy)

    def _getHeadwordVariantSearch(self, headwordStr, **options):
        dictionaryTable = self.db.tables[self.DICTIONARY_TABLE]

        headwordSubstringClause \
            = self.headwordVariantSearchStrategy.getWhereClause(
                dictionaryTable.c.Headword, headwordStr)

        if not headwordSubstringClause:
            return None, None

        headwordSubstringMatchFunc \
            = self.headwordVariantSearchStrategy.getMatchFunction(headwordStr)

        return ([headwordSubstringClause],
            [(['Headword'], headwordSubstringMatchFunc)])

    def getVariantsForHeadword(self, headwordStr, limit=None, orderBy=None,
        **options):
        clauses, filters = self._getHeadwordVariantSearch(headwordStr,
            **options)
        if not clauses:
            return []
        else:
            return self._search(or_(*clauses), filters, limit, orderBy)

    def _getHeadwordSimilarSearch(self, headwordStr, **options):
        dictionaryTable = self.db.tables[self.DICTIONARY_TABLE]

        headwordSubstringClause \
            = self.headwordSimilarSearchStrategy.getWhereClause(
                dictionaryTable.c.Headword, headwordStr)

        if not headwordSubstringClause:
            return None, None

        headwordSubstringMatchFunc \
            = self.headwordSimilarSearchStrategy.getMatchFunction(headwordStr)

        return ([headwordSubstringClause],
            [(['Headword'], headwordSubstringMatchFunc)])

    def getSimilarsForHeadword(self, headwordStr, limit=None, orderBy=None,
        **options):
        clauses, filters = self._getHeadwordSimilarSearch(headwordStr,
            **options)
        if not clauses:
            return []
        else:
            return self._search(or_(*clauses), filters, limit, orderBy)

    def getRandomEntry(self):
        # TODO add constraint that random entry needs to fulfill, e.g.
        #   frequency > 10
        # TODO add offset support to cjklib.dictionary and use _search() here
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


class _ExtendedCEDICTStyleSupport(_ExtendedDictionarySupport):
    def __init__(self, **options):
        if 'readingSimilarSearchStrategy' not in options:
            options['readingSimilarSearchStrategy'] = SimilarWildcardReading()
        if 'mixedSimilarReadingSearchStrategy' not in options:
            options['mixedSimilarReadingSearchStrategy'] \
                = MixedSimilarWildcardReading()
        if 'headwordEntitiesSearchStrategy' not in options:
            options['headwordEntitiesSearchStrategy'] = HeadwordEntityReading()
        _ExtendedDictionarySupport.__init__(self, **options)

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

    def _getHeadwordVariantSearch(self, headwordStr, **options):
        dictionaryTable = self.db.tables[self.DICTIONARY_TABLE]

        clauses = []
        filters = []
        if self.headword != 't':
            clauses.append(self.headwordVariantSearchStrategy.getWhereClause(
                dictionaryTable.c.HeadwordSimplified, headwordStr))
            filters.append((['HeadwordSimplified'],
                self.headwordVariantSearchStrategy.getMatchFunction(
                    headwordStr)))
        if self.headword != 's':
            clauses.append(self.headwordVariantSearchStrategy.getWhereClause(
                dictionaryTable.c.HeadwordTraditional, headwordStr))
            filters.append((['HeadwordTraditional'],
                self.headwordVariantSearchStrategy.getMatchFunction(
                    headwordStr)))

        return clauses, filters

    def _getHeadwordSimilarSearch(self, headwordStr, **options):
        dictionaryTable = self.db.tables[self.DICTIONARY_TABLE]

        clauses = []
        filters = []
        if self.headword != 't':
            clauses.append(self.headwordSimilarSearchStrategy.getWhereClause(
                dictionaryTable.c.HeadwordSimplified, headwordStr))
            filters.append((['HeadwordSimplified'],
                self.headwordSimilarSearchStrategy.getMatchFunction(
                    headwordStr)))
        if self.headword != 's':
            clauses.append(self.headwordSimilarSearchStrategy.getWhereClause(
                dictionaryTable.c.HeadwordTraditional, headwordStr))
            filters.append((['HeadwordTraditional'],
                self.headwordSimilarSearchStrategy.getMatchFunction(
                    headwordStr)))

        return clauses, filters


class _EDICTDictionaryDefaults(object):
    DEFAULT_SEARCH_STRATEGIES = {
            'headwordSearchStrategy': search.Wildcard,
            'readingSearchStrategy': search.Wildcard,
            'translationSearchStrategy': search.SimpleWildcardTranslation,
            }

    @classmethod
    def _setDefaults(cls, options, userdefaults=None):
        userdefaults = userdefaults or {}
        defaults = cls.DEFAULT_SEARCH_STRATEGIES.copy()
        defaults.update(userdefaults)
        for strategy in defaults:
            if strategy not in options:
                options[strategy] = defaults[strategy](singleCharacter='?',
                    multipleCharacters='*')


class ExtendedEDICT(_EDICTDictionaryDefaults, EDICT, _ExtendedDictionarySupport):
    def __init__(self, **options):
        self._setDefaults(options)
        options['entryFactory'] = EDICTEntry() # TODO
        EDICT.__init__(self, **options)
        _ExtendedDictionarySupport.__init__(self, **options)

    def _search(self, whereClause, filters, limit, orderBy):
        self._checkOrderByWeight(orderBy)
        return EDICT._search(self, whereClause, filters, limit, orderBy)


class ExtendedCEDICTGR(_EDICTDictionaryDefaults, CEDICTGR,
    _ExtendedDictionarySupport):
    # TODO similar reading support for CEDICTGR
    def __init__(self, **options):
        defaults = {
            'readingSearchStrategy': search.SimpleWildcardReading,
            'translationSearchStrategy': search.CEDICTWildcardTranslation,
            'headwordEntitiesSearchStrategy': HeadwordEntityReading
            }
        self._setDefaults(options, defaults)

        options['entryFactory'] = EDICTEntry() # TODO
        CEDICTGR.__init__(self, **options)
        _ExtendedDictionarySupport.__init__(self, **options)

    def _search(self, whereClause, filters, limit, orderBy):
        self._checkOrderByWeight(orderBy)
        return CEDICTGR._search(self, whereClause, filters, limit, orderBy)


class _CEDICTDictionaryDefaults(_EDICTDictionaryDefaults):
    DEFAULT_SEARCH_STRATEGIES = {
            'headwordSearchStrategy': search.Wildcard,
            'readingSearchStrategy': search.TonelessWildcardReading,
            'mixedReadingSearchStrategy': search.MixedTonelessWildcardReading,
            'translationSearchStrategy': search.SimpleWildcardTranslation,
            }

    @classmethod
    def _setDefaults(cls, options, userdefaults=None):
        userdefaults = userdefaults or {}
        defaults = cls.DEFAULT_SEARCH_STRATEGIES.copy()
        defaults.update(userdefaults)
        for strategy in defaults:
            if strategy not in options:
                options[strategy] = defaults[strategy](singleCharacter='?',
                    multipleCharacters='*')

        if 'entryFactory' not in options:
            #options['entryFactory'] = HeadwordAlternative()
            options['entryFactory'] = CEDICTEntry()

        reading = options.get('reading', cls.READING)

        columnFormatStrategies = options.get('columnFormatStrategies', {})
        if 'Reading' not in columnFormatStrategies:
            columnFormatStrategies['Reading'] = format.ReadingConversion(
                reading)
            options['columnFormatStrategies'] = columnFormatStrategies


class ExtendedCEDICT(_CEDICTDictionaryDefaults, CEDICT,
    _ExtendedCEDICTStyleSupport):
    def __init__(self, **options):
        defaults = {
            'translationSearchStrategy': search.CEDICTWildcardTranslation
            }
        self._setDefaults(options, defaults)

        CEDICT.__init__(self, **options)
        _ExtendedCEDICTStyleSupport.__init__(self, **options)

    def _search(self, whereClause, filters, limit, orderBy):
        self._checkOrderByWeight(orderBy)
        return CEDICT._search(self, whereClause, filters, limit, orderBy)


class ExtendedHanDeDict(_CEDICTDictionaryDefaults, HanDeDict,
    _ExtendedCEDICTStyleSupport):
    def __init__(self, **options):
        defaults = {
            'translationSearchStrategy': search.HanDeDictWildcardTranslation
            }
        self._setDefaults(options, defaults)

        HanDeDict.__init__(self, **options)
        _ExtendedCEDICTStyleSupport.__init__(self, **options)

    def _search(self, whereClause, filters, limit, orderBy):
        self._checkOrderByWeight(orderBy)
        return HanDeDict._search(self, whereClause, filters, limit, orderBy)


class ExtendedCFDICT(_CEDICTDictionaryDefaults, CFDICT,
    _ExtendedCEDICTStyleSupport):
    def __init__(self, **options):
        defaults = {
            'translationSearchStrategy': search.HanDeDictWildcardTranslation
            }
        self._setDefaults(options, defaults)

        CFDICT.__init__(self, **options)
        _ExtendedCEDICTStyleSupport.__init__(self, **options)

    def _search(self, whereClause, filters, limit, orderBy):
        self._checkOrderByWeight(orderBy)
        return CFDICT._search(self, whereClause, filters, limit, orderBy)


class PseudoDictionary(object):
    """
    Provides a pseudo dictionary that offers only character lookup based on
    character to reading mappings in the absence of real dictionary data.
    """
    # TODO implement limit= for all search routines
    SUPPORTED_LANG = ['zh-cmn-Hans', 'zh-cmn-Hant', 'zh-yue-Hans',
        'zh-yue-Hant', 'ko'] # , 'ja'
    """List of supported CJK languages for pseudo dictionaries."""

    LANGUAGE_LOCALE_MAP = {'zh-cmn-Hant': 'T', 'zh-cmn-Hans': 'C',
        'zh-yue-Hant': 'T', 'zh-yue-Hans': 'S', 'ko': 'K'} #, 'ja': 'J'}
    """Locale for language."""

    LANGUAGE_DEFAULT_READING = {'zh-cmn-Hant': 'Pinyin',
        'zh-cmn-Hans': 'Pinyin', 'zh-yue-Hant': 'Jyutping',
        'zh-yue-Hans': 'Jyutping', 'ko': 'Hangul'} #, 'ja': 'Kana'}
    """
    Default reading for language, following default mappings in
    cjklib.characterlookup.
    """

    # TODO
    COLUMNS = ['Headword', 'HeadwordAlternative', 'Reading', 'Translation']
    #COLUMNS = ['Headword', 'Reading']

    def __init__(self, language, characterDomain=None, reading=None,
        columnFormatStrategies=None, entryFactory=None, dbConnectInst=None,
        ignoreIllegalSettings=False):

        if language not in self.SUPPORTED_LANG:
            raise ValueError("Unknown language '%s'" % language)

        self.language = language
        self.PROVIDES = 'PSEUDO_%s' % self.language
        self.locale = self.LANGUAGE_LOCALE_MAP[language]

        if (reading
            and reading not in LANGUAGE_COMPATIBLE_MAPPINGS[self.language]):
            if ignoreIllegalSettings:
                reading = None
            else:
                raise ValueError("Illegal reading '%s' for language '%s'"
                    % (reading, self.language))

        self.reading = reading or self.LANGUAGE_DEFAULT_READING[language]
        # compatibility with EDICT style dictionaries
        self.READING = self.reading
        self.READING_OPTIONS = {}

        self.db = dbConnectInst or getDBConnector()
        self._readingFactory = ReadingFactory(dbConnectInst=self.db)
        self._characterDB = CharacterDB(language=self.language,
            characterDomain=characterDomain, dbConnectInst=self.db,
            ignoreIllegalSettings=ignoreIllegalSettings)

        # common dictionary settings
        self.columnFormatStrategies = columnFormatStrategies or {}
        for column in self.columnFormatStrategies.values():
            if hasattr(column, 'setDictionaryInstance'):
                column.setDictionaryInstance(self)

        self.entryFactory = entryFactory or entry.NamedTuple()
        if hasattr(self.entryFactory, 'setDictionaryInstance'):
            self.entryFactory.setDictionaryInstance(self)

    def _format(self, results):
        # format readings and translations
        for column, formatStrategy in self.columnFormatStrategies.items():
            columnIdx = self.COLUMNS.index(column)
            for idx in range(len(results)):
                rowList = list(results[idx])
                rowList[columnIdx] = formatStrategy.format(rowList[columnIdx])
                results[idx] = tuple(rowList)

        # format results
        # TODO
        entries = self.entryFactory.getEntries([(h, h, r, '') for h, r in results])
        #entries = self.entryFactory.getEntries(results)

        return entries

    def getForHeadword(self, headwordStr, **options):
        if len(headwordStr) > 1:
            return []

        char = headwordStr
        try:
            readings = self._characterDB.getReadingForCharacter(char,
                self.reading)
        except (exception.ConversionError, exception.UnsupportedError):
            readings = []

        return self._format([(char, reading) for reading in readings])

    def _exactReading(self, readingStr, **options):
        if self._readingFactory.isReadingEntity(readingStr, self.reading,
            **options):
            if self._readingFactory.isReadingConversionSupported(self.reading,
                self.reading):
                try:
                    convertedEntity = self._readingFactory.convertEntities(
                        [readingStr], self.reading, self.reading,
                        sourceOptions=options)[0]
                    return [convertedEntity]
                except exception.ConversionError:
                    return [readingStr]
            else:
                return [readingStr]

        if self._readingFactory.isReadingOperationSupported('getTonalEntity',
            self.reading):
            if not self._readingFactory.isPlainReadingEntity(readingStr,
                self.reading, **options):
                # raise Exception?
                return []

            tonalEntities = []
            for tone in self._readingFactory.getTones(self.reading, **options):
                try:
                    tonalEntities.append(
                        self._readingFactory.getTonalEntity(readingStr, tone,
                            self.reading, **options))
                except (exception.InvalidEntityError,
                    exception.UnsupportedError):
                    pass

            return [self._readingFactory.convertEntities([e], self.reading,
                    self.reading, sourceOptions=options)[0]
                    for e in tonalEntities]

        return []

    def getForReading(self, readingStr, **options):
        entries = []

        for readingEntity in self._exactReading(readingStr, **options):
            try:
                chars = self._characterDB.getCharactersForReading(
                    readingEntity, self.reading)
                entries.extend([(char, readingEntity) for char in chars])
            except (ValueError, exception.ConversionError):
                pass
            except exception.UnsupportedError:
                return []

        return self._format(entries)

    def getFor(self, searchStr, **options):
        entries = set(self.getForReading(searchStr, **options))
        if searchStr and util.getCJKScriptClass(searchStr[0]) == 'Han':
            entries.update(self.getForHeadword(searchStr, **options))

        return entries

    def _similarReading(self, readingStr, **options):
        entity = readingStr
        if self._readingFactory.isReadingOperationSupported(
            'splitEntityTone', self.reading):
            try:
                entity, _ = self._readingFactory.splitEntityTone(entity,
                    self.reading)
            except (exception.InvalidEntityError, exception.UnsupportedError):
                pass

        similar = CharacterDB.getSimilarPlainEntities(entity, self.reading)

        if self._readingFactory.isReadingOperationSupported('getTonalEntity',
            self.reading):
            tonalEntities = []
            for tone in self._readingFactory.getTones(self.reading, **options):
                for similarEntity in similar:
                    try:
                        tonalEntities.append(
                            self._readingFactory.getTonalEntity(similarEntity,
                                tone, self.reading, **options))
                    except (exception.InvalidEntityError,
                        exception.UnsupportedError):
                        pass
            similar = tonalEntities

        if self._readingFactory.isReadingConversionSupported(self.reading,
            self.reading):
            convertedSimilar = []
            for e in similar:
                try:
                    convertedSimilar.append(
                        self._readingFactory.convertEntities([e], self.reading,
                            self.reading, sourceOptions=options)[0])
                except exception.ConversionError:
                    pass
            return convertedSimilar
        else:
            return similar

    def getForSimilarReading(self, readingStr, **options):
        entries = []

        for readingEntity in self._similarReading(readingStr, **options):
            try:
                chars = self._characterDB.getCharactersForReading(
                    readingEntity, self.reading)
                entries.extend([(char, readingEntity) for char in chars])
            except (ValueError, exception.ConversionError):
                pass
            except exception.UnsupportedError:
                return []

        return self._format(entries)

    def getEntitiesForHeadword(self, headwordStr, readingStr=None, **options):
        entries = []
        for char in headwordStr:
            if util.getCJKScriptClass(char) != 'Han':
                continue
            try:
                readings = self._characterDB.getReadingForCharacter(char,
                    self.reading)
            except (exception.ConversionError, exception.UnsupportedError):
                readings = []
            entries.extend([(char, reading) for reading in readings])

        return self._format(entries)

    def getSubstringsForHeadword(self, headwordStr, limit=None, orderBy=None):
        return self.getSubstringsForHeadword(headwordStr, limit, orderBy)

    def getVariantsForHeadword(self, headwordStr, **options):
        # TODO remove radical forms
        if len(headwordStr) != 1:
            return []
        else:
            return self._format([(char, None) for char
                in self._characterDB.getCharacterVariants(headwordStr)])

    def getSimilarsForHeadword(self, headwordStr, **options):
        if len(headwordStr) != 1:
            return []
        else:
            return self._format([(char, None) for char
                in self._characterDB.getCharacterSimilars(headwordStr)])
