#!/usr/bin/python
# -*- coding: utf-8  -*-
"""
Character information.
"""

from sqlalchemy import select
from sqlalchemy.sql import and_

from cjklib.characterlookup import CharacterLookup
from cjklib import exception

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

    def __init__(self, language, characterDomain=None, dbConnectInst=None,
        ignoreIllegalSettings=False):
        dbConnectInst = dbConnectInst or getDBConnector()
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
