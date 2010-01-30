#!/usr/bin/python
# -*- coding: utf-8  -*-
"""
Builds the database for Eclectus.

This is derived from the buildcjkdb script from cjklib.

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
import types
import sys
import os
import re
import itertools
import xml.sax
import bz2
from datetime import datetime

from sqlalchemy import Table, Column, Integer, String, Text, DateTime, Index
from sqlalchemy.sql import and_, or_, not_
from sqlalchemy import select

from cjklib import characterlookup
from cjklib.reading import ReadingFactory
from cjklib.build import builder, cli, warn
from cjklib import exception
from cjklib.util import UnicodeCSVFileIterator, CharacterRangeIterator

from libeclectus import util

class UpdateVersionBuilder(builder.EntryGeneratorBuilder):
    """Table for keeping track of which date the release was."""
    PROVIDES = 'UpdateVersion'
    COLUMNS = ['TableName', 'ReleaseDate']
    PRIMARY_KEYS = ['TableName']
    COLUMN_TYPES = {'TableName': String(255), 'ReleaseDate': DateTime()}

    def getGenerator(self):
        return iter([])


class KanaExtendedCharacterSetBuilder(object):
    BASE_BUILDER_CLASS = None

    def toTuple(self, iterator):
        for char in iterator:
            yield (char, )

    def getGenerator(self):
        base = self.BASE_BUILDER_CLASS.getGenerator(self)

        kanaRanges = []
        kanaRanges.extend(util.UNICODE_SCRIPT_CLASSES['Hiragana'])
        kanaRanges.extend(util.UNICODE_SCRIPT_CLASSES['Katakana'])
        kana = CharacterRangeIterator(kanaRanges)

        return itertools.chain(self.toTuple(kana), base)


class JISX0208SetExtendedBuilder(KanaExtendedCharacterSetBuilder,
    builder.JISX0208SetBuilder):
    """
    Extends the set of the builder for X{JIS X 0208} by Kanas.
    """
    BASE_BUILDER_CLASS = builder.JISX0208SetBuilder


class JISX0208_0213SetExtendedBuilder(KanaExtendedCharacterSetBuilder,
    builder.JISX0208_0213SetBuilder):
    """
    Extends the set of the builder for X{JIS X 0208} and X{JIS X 0213} by Kanas.
    """
    BASE_BUILDER_CLASS = builder.JISX0208_0213SetBuilder


class SimilarCharactersBuilder(builder.CSVFileLoader):
    """
    Builds a list of characters with similar visual appearance.
    """
    PROVIDES = 'SimilarCharacters'

    TABLE_CSV_FILE_MAPPING = 'similarcharacters.csv'
    TABLE_DECLARATION_FILE_MAPPING = 'similarcharacters.sql'


class RadicalNamesZHCMNBuilder(builder.CSVFileLoader):
    """
    Builds a list of kangxi radical names for Mandarin Chinese.
    """
    PROVIDES = 'RadicalNames_zh_cmn'

    TABLE_CSV_FILE_MAPPING = 'radicalnames_zh-cmn.csv'
    TABLE_DECLARATION_FILE_MAPPING = 'radicalnames_zh-cmn.sql'


class BeidaHSKVocabularyBuilder(builder.CSVFileLoader):
    """
    Builds a table of HSK (Hanyu Shuiping Kaoshi, Chinese proficiency test) by
    loading its data from a list of comma separated values (CSV) provided in the
    format of 《汉语水平（词汇）等级大纲》电子版（李红印提供） from
    U{http://hanyu.pku.edu.cn/info/article.asp?articleid=282}.
    """
    PROVIDES = 'HSKVocabulary'

    FILE_NAMES = [u'汉语水平词汇与汉字等级大纲8822词.csv', 'HSK.csv']
    """Names of file containing the HSK word list."""
    LEVELS = {u'甲': 1, u'乙': 2, u'丙': 3, u'丁': 4}
    """Names of HSK Levels"""

    def build(self):
        import codecs
        import os.path as path
        filePath = self.findFile(self.FILE_NAMES, "HSK table")
        fileHandle = codecs.open(filePath, 'r', 'utf8')

        # get create statement
        table = self.buildTableObject(self.PROVIDES, ['Headword', 'Level'],
            {'Headword': String(255), 'Level': Integer()}, ['Headword'])
        table.create()

        # write table content
        currentLevel = None     # current level 1-4
        seenHeadwords = set()   # already saved headwords
        doubleEntryCount = 0    # double/tripple entries
        multiEntryCount = 0     # lines with mutiple headwords
        for line in UnicodeCSVFileIterator(fileHandle):
            # check for level boundary
            if line[0] == '':
                if line[1][0] in self.LEVELS.keys():
                    currentLevel = self.LEVELS[line[1][0]]
                elif not self.quiet and not re.match(r'^[a-zA-Z]$', line[1]):
                    # skip categories A, B, ... but warn on other content
                    warn("Errorneous line: '" + "', '".join(line) + "'")
                continue

            if currentLevel == None and not self.quiet:
                warn("No level information found, skipping line: '" \
                    + "', '".join(line) + "'")
                continue

            # create entry, take care of mutiple entries in one line:
            headwords = line[1].split('/')
            # if includes terms in brackets split entry into two
            if line[1].find(u'(') >= 0:
                newHeadwords = []
                for headword in headwords:
                    if headword.find(u'(') >= 0:
                        # one with all words
                        newHeadwords.append(re.sub(u'[\(\)]', headword, ''))
                        # one without chars in brackets
                        newHeadwords.append(re.sub(u'\([\)]*\)', headword, ''))
                    else:
                        newHeadwords.append(headword)
                headwords = newHeadwords

            if len(headwords) > 1:
                multiEntryCount = multiEntryCount + 1
            for headword in headwords:
                # skip headwords already seen
                if headword in seenHeadwords:
                    doubleEntryCount = doubleEntryCount + 1
                    continue
                else:
                    seenHeadwords.add(headword)

                entry = {'Headword': headword, 'Level': currentLevel}

                try:
                    self.db.execute(table.insert().values(**entry))
                except sqlalchemy.exceptions.IntegrityError, e:
                    warn(unicode(e))
                    #warn(unicode(insertStatement))
                    raise

        if not self.quiet:
            if doubleEntryCount:
                warn("Found " + str(doubleEntryCount) + " repeated entries")
            if multiEntryCount:
                warn("Found " + str(multiEntryCount) \
                    + " lines with multiple entries")


class WiktionaryHSKVocabularyBuilder(builder.CSVFileLoader):
    """
    Builds a table of HSK (Hanyu Shuiping Kaoshi, Chinese proficiency test) by
    loading its data from a list of comma separated values (CSV) provided from
    en.wiktionary.org.
    """
    PROVIDES = 'HSKVocabulary'

    FILE_NAMES = ['hsk.csv']
    """Names of file containing the HSK word list."""
    LEVELS = {u'甲': 1, u'乙': 2, u'丙': 3, u'丁': 4}
    """Names of HSK Levels"""

    def build(self):
        import codecs
        import os.path as path
        filePath = self.findFile(self.FILE_NAMES, "HSK table")
        fileHandle = codecs.open(filePath, 'r', 'utf8')

        # get create statement
        table = self.buildTableObject(self.PROVIDES,
            ['HeadwordTraditional', 'HeadwordSimplified', 'Level'],
            {'HeadwordTraditional': String(255),
                'HeadwordSimplified': String(255), 'Level': Integer()},
            ['HeadwordTraditional'])
        table.create()

        # read entries, check for double entries
        traditionalHeadwordLevelDict = {} # headword to level mapping
        tradSimpHeadwordDict = {} # traditional to simplified
        doubleEntryCount = 0 # double/tripple entries
        for headwordTrad, headwordSimp, level \
            in UnicodeCSVFileIterator(fileHandle):
            # skip headwords already seen
            if headwordTrad in traditionalHeadwordLevelDict:
                doubleEntryCount = doubleEntryCount + 1
                if level \
                    < self.LEVELS[traditionalHeadwordLevelDict[headwordTrad]]:
                    traditionalHeadwordLevelDict[headwordTrad] = level
                    tradSimpHeadwordDict[headwordTrad] = headwordSimp
            else:
                traditionalHeadwordLevelDict[headwordTrad] = level
                tradSimpHeadwordDict[headwordTrad] = headwordSimp

        # write table content
        for headwordTrad in traditionalHeadwordLevelDict:
            headwordSimp = tradSimpHeadwordDict[headwordTrad]
            level = self.LEVELS[traditionalHeadwordLevelDict[headwordTrad]]
            try:
                self.db.execute(table.insert().values(
                    HeadwordTraditional=headwordTrad,
                    HeadwordSimplified=headwordSimp, Level=level))
            except sqlalchemy.exceptions.IntegrityError, e:
                warn(unicode(e))
                #warn(unicode(insertStatement))
                raise

        # get create index statement
        for index in self.buildIndexObjects(self.PROVIDES,
            [['HeadwordSimplified']]):
            index.create()

        if not self.quiet:
            if doubleEntryCount:
                warn("Found " + str(doubleEntryCount) \
                    + " repeated entries")


class WeightedEDICTFormatBuilder(builder.EDICTFormatBuilder):
    """
    Provides an abstract class for loading EDICT formatted dictionaries together
    with a weight attached to each entry provided by an additional.

    One column will be provided for the headword, one for the reading (in EDICT
    that is the Kana) and one for the translation.
    """
    class WeightedEntryGenerator:
        """Generates the dictionary entries."""

        def __init__(self, dictionaryEntryGenerator, weightFunc):
            """
            Initialises the TableGenerator.

            @type fileHandle: file
            @param fileHandle: handle of file to read from
            @type weightFunc: func
            @param weightFunc: columns from dictionary used to get weights
            """
            self.dictionaryEntryGenerator = dictionaryEntryGenerator
            self.weightFunc = weightFunc

        def generator(self):
            """Provides the weighted dictionary entries."""
            for entry in self.dictionaryEntryGenerator:
                entry['Weight'] = self.weightFunc(entry)

                yield entry

    class PrependGenerator:
        def __init__(self, lines, data):
            """
            The first line red for guessing format has to be reinserted.
            """
            self.lines = lines
            self.data = data
            self.index = -1

        def __iter__(self):
            line = self.readline()
            while line:
                yield line
                line = self.readline()

        def readline(self):
            if self.lines:
                line = self.lines[0]
                del self.lines[0]
                return line
            else:
                return self.data.readline()

    COLUMNS = ['Headword', 'Reading', 'Translation', 'Weight']
    INDEX_KEYS = [['Headword'], ['Reading'], ['Weight']]
    COLUMN_TYPES = {'Headword': String(255), 'Reading': String(255),
        'Translation': Integer(), 'Weight': Integer()}

    WEIGHT_TABLE = None
    """The table from which the weight will be deduced."""
    WEIGHT_COLUMN = None
    """Column of weight table holding the weight."""
    JOIN_COLUMNS = None
    """
    Dict of column pairs used in joining of dictionary and weight table, e.g.
    {dictCol1: weightCol1, dictCol2: weightCol2}
    """

    def getGenerator(self):
        if self.WEIGHT_TABLE:
            # get weight entries
            dictionaryColumns = self.JOIN_COLUMNS.keys()
            weightColumns = [self.JOIN_COLUMNS[c] for c in dictionaryColumns]
            weightColumns.append(self.WEIGHT_COLUMN)
            weightDict = {}

            table = self.db.tables[self.WEIGHT_TABLE]
            for cells in self.db.selectRows(select(
                [table.c[column] for column in weightColumns],
                distinct=True)):

                weightDict[tuple(cells[:-1])] = cells[-1]

            weightFunc = lambda entry: self.getWeight(weightDict,
                dictionaryColumns, entry)
        else:
            weightFunc = lambda entry: None

        # create generator, and put on top of the super init method's generator
        return WeightedEDICTFormatBuilder.WeightedEntryGenerator(
            builder.EDICTFormatBuilder.getGenerator(self), weightFunc)\
                .generator()

    def getFileHandle(self, filePath):
        handle = super(WeightedEDICTFormatBuilder, self).getFileHandle(filePath)

        readLines = []
        # find version
        for idx, line in enumerate(handle):
            readLines.append(line)
            if not line.strip().startswith('#') and idx >= self.IGNORE_LINES:
                break
            version = self.extractVersion(line)
            if version:
                self.insertVersion(version)
                break

        return WeightedEDICTFormatBuilder.PrependGenerator(readLines, handle)

    def getWeight(self, weightDict, keys, entry):
        """
        Gets the weight for the dictionary entry given in the weightDict using
        the specified keys.

        @type weightDict: dict
        @param weightDict: dict of weights
        @type keys: list of str
        @param keys: a list of keys from the entry used to access the weightDict
        @type entry: dict
        @param entry: dictionary entry
        """
        weightKey = []
        for dictColumn in keys:
            weightKey.append(entry[dictColumn])

        weightKey = tuple(weightKey)
        if weightKey in weightDict:
            return weightDict[weightKey]
        else:
            return None

    def remove(self):
        builder.EDICTFormatBuilder.remove(self)

        self.removeVersion()

    def removeVersion(self):
        if not self.db.mainHasTable('UpdateVersion'):
            return

        table = self.db.tables['UpdateVersion']
        try:
            self.db.execute(table.delete().where(
                table.c.TableName == self.PROVIDES))
        except sqlalchemy.exceptions.IntegrityError, e:
            warn(unicode(e))
            #warn(unicode(insertStatement))
            raise

    def insertVersion(self, date):
        if not self.db.mainHasTable('UpdateVersion'):
            return

        self.removeVersion()

        table = self.db.tables['UpdateVersion']
        try:
            self.db.execute(table.insert().values(TableName=self.PROVIDES,
                ReleaseDate=date))
        except sqlalchemy.exceptions.IntegrityError, e:
            warn(unicode(e))
            #warn(unicode(insertStatement))
            raise

    def extractVersion(self, line):
        pass


class WeightedEDICTBuilder(WeightedEDICTFormatBuilder, builder.EDICTBuilder):
    """
    Provides an class for loading the EDICT dictionary together with a weight
    attached to each entry provided by an additional source.
    @todo Impl: Create a weight table and include here.
    """
    #DEPENDS = ['']

    #WEIGHT_TABLE = ''
    #WEIGHT_COLUMN = ''
    #JOIN_COLUMNS = {'Headword': 'HeadwordTraditional'}

    def extractVersion(self, line):
        matchObj = re.search(u'^？？？？ /EDICT(?:.+)/Created: (.+)/$',
            line.strip())
        # Example: /Created: 2008-01-22/
        if matchObj:
            try:
                return datetime.strptime(matchObj.group(1), '%Y-%m-%d')
            except ValueError:
                pass


class WeightedCEDICTGRBuilder(WeightedEDICTFormatBuilder,
    builder.CEDICTGRBuilder):
    """
    Provides an class for loading the CEDICT-GR dictionary from GR  Junction
    together with a weight attached to each entry provided by an additional
    source.
    """
    DEPENDS = ['HSKVocabulary']

    WEIGHT_TABLE = 'HSKVocabulary' # TODO 'Level' ascending while 'Weight' should be descending
    WEIGHT_COLUMN = 'Level'
    JOIN_COLUMNS = {'Headword': 'HeadwordTraditional'}

    def extractVersion(self, line):
        # CEDICT-GR has seen no development and there is no date available from
        #   the file itself so use a static date.
        return datetime(2001, 2, 16)


class WeightedCEDICTFormatBuilder(WeightedEDICTFormatBuilder):
    """
    Provides an abstract class for loading CEDICT formatted dictionaries
    together with a weight attached to each entry provided by an additional
    source.

    Two column will be provided for the headword (one for traditional and
    simplified writings each), one for the reading (e.g. in CEDICT Pinyin) and
    one for the translation.
    @todo Impl: Proper collation for Translation and Reading columns.
    """
    COLUMNS = ['HeadwordTraditional', 'HeadwordSimplified', 'Reading',
        'Translation', 'Weight']
    INDEX_KEYS = [['HeadwordTraditional'], ['HeadwordSimplified'], ['Reading'],
        ['Weight']]
    COLUMN_TYPES = {'HeadwordTraditional': String(255),
        'HeadwordSimplified': String(255), 'Reading': String(255),
        'Translation': Text(), 'Weight': Integer()}

    def __init__(self, **options):
        self.ENTRY_REGEX = \
            re.compile(r'\s*(\S+)(?:\s+(\S+))?\s*\[([^\]]*)\]\s*(/.*/)\s*$')
        super(WeightedCEDICTFormatBuilder, self).__init__(**options)


class WeightedMandarinCEDICTFormatBuilder(WeightedCEDICTFormatBuilder):
    DEPENDS = ['HSKVocabulary']

    WEIGHT_TABLE = 'HSKVocabulary' # TODO 'Level' ascending while 'Weight' should be descending
    WEIGHT_COLUMN = 'Level'
    JOIN_COLUMNS = {'HeadwordTraditional': 'HeadwordTraditional'}


class WeightedCEDICTBuilder(WeightedMandarinCEDICTFormatBuilder,
    builder.CEDICTBuilder):
    """
    Builds the CEDICT dictionary with weights attached to each entry.
    """
    def extractVersion(self, line):
        matchObj = re.search(u'#! date=(.+)\s*$', line.strip())
        # Example: 2009-01-20T05:51:40Z
        if matchObj:
            try:
                return datetime.strptime(matchObj.group(1),
                    '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                pass


class WeightedTimestampedCEDICTFormatBuilder(
    WeightedMandarinCEDICTFormatBuilder):
    """
    Shared functionality for dictionaries whose content includes a timestamp.
    """
    EXTRACT_HEADER_TIMESTAMP = None
    """Regular expression to extract the timestamp from the dict's header."""

    def extractVersion(self, line):
        matchObj = re.search(self.EXTRACT_HEADER_TIMESTAMP, line.strip())
        # Example: Sun Jan 18 00:34:02 2009
        if matchObj:
            try:
                # Weekday and Month is encoded in English, use C locale
                timeLocale = None
                try:
                    timeLocale = locale.getlocale(locale.LC_TIME)
                    locale.setlocale(locale.LC_TIME, 'C')
                except locale.Error:
                    pass
                return datetime.strptime(matchObj.group(1).strip(),
                    '%a %b %d %H:%M:%S %Y')
                try:
                    if timeLocale:
                        locale.setlocale(locale.LC_TIME, timeLocale)
                except locale.Error:
                    pass
            except ValueError, e:
                pass


class WeightedHanDeDictBuilder(WeightedTimestampedCEDICTFormatBuilder,
    builder.HanDeDictBuilder):
    """
    Builds the HanDeDict dictionary with weights attached to each entry.
    """
    EXTRACT_HEADER_TIMESTAMP = ur'# HanDeDict ([^\;]+); Copyright'


class WeightedCFDictBuilder(WeightedTimestampedCEDICTFormatBuilder,
    builder.CFDICTBuilder):
    """
    Builds the CFDICT dictionary with weights attached to each entry.
    """
    EXTRACT_HEADER_TIMESTAMP = ur'# CFDICT ([^\;]+); Copyright'


class HanDeDictRadicalTableBuilder(builder.EntryGeneratorBuilder):
    """
    Builds a radical table with index, reading and meaning using the dictionary
    HanDeDict.
    @todo Fix: Reading superfluous.
    """
    class RadicalEntryGenerator:
        """Generates the entries of the radical table."""
        def __init__(self, dbConnectInst):
            """
            Initialises the RadicalEntryGenerator.

            @type dbConnectInst: object
            @param dbConnectInst: instance of a L{DatabaseConnector}.
            """
            self.cjk = characterlookup.CharacterLookup('T',
                dbConnectInst=dbConnectInst)
            self.meaningRegex = re.compile(
                '/Radikal Nr\. \d+(?: = ((?:\([^\)]*\)|[^\(\)\/])+))')
            # TODO more sophisticated filtering needed
            self.removeParts = re.compile('\(Varianten?: [^\)]+\)|\(u\.E\.\)|' \
                + u'\((S|V|Adj|Zähl|Eig)[^\)]*\)|' + r'(; Bsp.: [^/]+?--[^/]+)')

        def generator(self):
            """Provides all data of one character per entry."""
            table = self.cjk.db.tables['HanDeDict']
            for radicalIdx in range(1, 215):
                form = self.cjk.getKangxiRadicalForm(radicalIdx)
                char = self.cjk.getRadicalFormEquivalentCharacter(form)
                dictEntries = self.cjk.db.selectRows(
                    select([table.c.Reading, table.c.Translation],
                        or_(table.c.HeadwordTraditional == char,
                            table.c.HeadwordSimplified == char)))

                newEntryDict = {'RadicalIndex': radicalIdx}
                for reading, translation in dictEntries:
                    matchObj = self.meaningRegex.search(translation)
                    if matchObj:
                        meaning = matchObj.group(1).strip()
                        filteredMeaning = self.removeParts.sub('', meaning)
                        newEntryDict['Meaning'] = filteredMeaning
                        newEntryDict['Reading'] = reading
                        yield newEntryDict
                        break

    PROVIDES = 'RadicalTable_zh_cmn__de'
    DEPENDS = ['KangxiRadical', 'RadicalEquivalentCharacter', 'HanDeDict']
    COLUMNS = ['RadicalIndex', 'Reading', 'Meaning']
    PRIMARY_KEYS = ['RadicalIndex']
    COLUMN_TYPES = {'RadicalIndex': Integer(), 'Reading': String(255),
        'Meaning': Text()}

    def getGenerator(self):
        return HanDeDictRadicalTableBuilder.RadicalEntryGenerator(self.db)\
            .generator()


class EnglishCSVRadicalTableBuilder(builder.CSVFileLoader):
    """
    Builds a radical table with index, reading and meaning using a CSV file.
    """
    PROVIDES = 'RadicalTable_zh_cmn__en'

    TABLE_CSV_FILE_MAPPING = 'radicals_en.csv'
    TABLE_DECLARATION_FILE_MAPPING = 'radicals_en.sql'


class CombinedEnglishRadicalTableBuilder(EnglishCSVRadicalTableBuilder,
    builder.EntryGeneratorBuilder):
    """
    Builds a radical table with index, reading using a CSV source, adding
    names as defined by Unicode.
    """
    PROVIDES = 'RadicalTable_zh_cmn__en'

    COLUMNS = ['RadicalIndex', 'Reading', 'Meaning']
    PRIMARY_KEYS = ['RadicalIndex']
    COLUMN_TYPES = {'RadicalIndex': Integer(), 'Reading': String(255),
        'Meaning': Text()}

    def build(self):
        return builder.EntryGeneratorBuilder.build(self)

    def getGenerator(self):
        contentFile = self.findFile([self.TABLE_CSV_FILE_MAPPING], "table")

        # write table content
        if not self.quiet:
            warn("Reading table '" + self.PROVIDES + "' from file '" \
                + contentFile + "'")
        import codecs
        fileHandle = codecs.open(contentFile, 'r', 'utf-8')

        radicalEntries = {}
        for line in UnicodeCSVFileIterator(fileHandle):
            if len(line) == 1 and not line[0].strip():
                continue
            radicalIdx, reading, meaning = line
            radicalEntries[int(radicalIdx)] = (reading, meaning.split(','))

        # add unicode ones
        import unicodedata
        for i in range(0, 214):
            radicalIdx = i + 1
            if radicalIdx in radicalEntries:
                reading, meanings = radicalEntries[radicalIdx]
            else:
                reading = None
                meanings = []
            try:
                name = unicodedata.name(unichr(int('2f00', 16) + i))
                name = name.replace('KANGXI RADICAL ', '').lower()
                if name not in meanings:
                    meanings += [name]
            except ValueError:
                pass

            if meanings:
                yield({'RadicalIndex': radicalIdx, 'Reading': reading,
                    'Meaning': ', '.join(meanings)})


class KanjidicEnRadicalTableBuilder(builder.EntryGeneratorBuilder):
    """
    Builds a radical table with index, radical name and meaning using Kanjidic.
    """
    class RadicalEntryGenerator:
        """Generates the entries of the radical table."""
        def __init__(self, dbConnectInst):
            """
            Initialises the RadicalEntryGenerator.

            @type dbConnectInst: object
            @param dbConnectInst: instance of a L{DatabaseConnector}.
            """
            self.cjk = characterlookup.CharacterLookup('T',
                dbConnectInst=dbConnectInst)
            self.meaningRegex = re.compile('/([^/]+) \(no\. \d+\)')

        def generator(self):
            """Provides all data of one character per entry."""
            for radicalIdx in range(1, 215):
                form = self.cjk.getKangxiRadicalForm(radicalIdx)
                char = self.cjk.getRadicalFormEquivalentCharacter(form)
                dictEntries = self.cjk.db.select('Kanjidic',
                    ['RadicalName',
                        KanjidicEnRadicalTableBuilder.MEANING_SOURCE],
                    {'ChineseCharacter': char})

                newEntryDict = {'RadicalIndex': radicalIdx}
                for name, translation in dictEntries:
                    matchObj = self.meaningRegex.search(translation)
                    if matchObj:
                        meaning = matchObj.group(1).strip()
                        filteredMeaning \
                            = KanjidicEnRadicalTableBuilder.REMOVE_PARTS.sub('',
                                meaning)
                        newEntryDict['Meaning'] = filteredMeaning
                        newEntryDict['Name'] = name
                        yield newEntryDict
                        break

    PROVIDES = 'RadicalTable_ja__en'
    DEPENDS = ['KangxiRadical', 'RadicalEquivalentCharacter', 'Kanjidic']
    COLUMNS = ['RadicalIndex', 'Name', 'Meaning']
    PRIMARY_KEYS = ['RadicalIndex']
    COLUMN_TYPES = {'RadicalIndex': Integer(), 'Name': String(255),
        'Meaning': Text()}

    MEANING_SOURCE = 'Meaning_en'
    REMOVE_PARTS = re.compile(' radical( variant)?')

    def getGenerator(self):
        return KanjidicEnRadicalTableBuilder.RadicalEntryGenerator(self.db)\
            .generator()


class KanjidicFrRadicalTableBuilder(KanjidicEnRadicalTableBuilder):
    """
    Builds a radical table with index, radical name and meaning using Kanjidic.
    """
    PROVIDES = 'RadicalTable_ja__fr'

    MEANING_SOURCE = 'Meaning_fr'
    REMOVE_PARTS = re.compile('radical (variant )?')


class KangxiRadicalTableBuilder(builder.EntryGeneratorBuilder):
    """
    Builds a Kangxi radical table with index, radical form (traditional radical
    form, locale dependant radical form and variants), type of radical form
    (main 'F'orm/'L'ocale dependant form/'V'ariant) and locale.
    """
    class RadicalEntryGenerator:
        """Generates the entries of the radical table."""
        KANGXI_RADICAL_SPECIAL_FORMS = {39: [u'孑'], 47: [u'川'], 93: [u'牜']}
        """Special forms of Kangxi radicals."""

        KANGXI_VARIANT_FORMS = [(9, u'⺅', 'TCJKV'), (18, u'⺉', 'TCJKV'),
            (26, u'⺋', 'TCJKV'), (47, u'川', 'CJKV'), (58, u'⺔', 'TCJKV'),
            (61, u'⺗', 'TCJKV'), (61, u'⺖', 'TCJKV'), (64, u'⺘', 'TCJKV'),
            (66, u'⺙', 'TCJKV'), (71, u'⺛', 'TCJKV'), (85, u'⺡', 'TCJKV'),
            (85, u'⺢', 'TCJKV'), (86, u'⺣', 'TCJKV'), (87, u'⺥', 'TCJKV'),
            (93, u'牜', 'CJKV'), (94, u'⺨', 'TCJKV'), (96, u'⺩', 'TCJKV'),
            (109, u'⺫', 'TCJKV'), (113, u'⺭', 'TCJKV'), (118, u'⺮', 'TCJKV'),
            (120, u'⺰', 'C'), (120, u'⺯', 'TJKV'), (122, u'⺲', 'TCJKV'),
            (130, u'⺼', 'TCJKV'), (140, u'⺿', 'TJKV'), (140, u'⺾', 'C'),
            (145, u'⻂', 'TCJKV'), (146, u'⻃', 'TCJKV'), (149, u'⻈', 'C'),
            (157, u'⻊', 'TCJKV'), (162, u'⻌', 'C'), (162, u'⻎', 'TJKV'),
            (163, u'⻏', 'TCJKV'), (167, u'⻐', 'C'), (168, u'⻒', 'TJKV'),
            (170, u'⻖', 'TCJKV'), (173, u'⻗', 'TCJKV'), (184, u'⻠', 'C'),
            (184, u'⻟', 'TJKV')]
        """
        List of selected radical variants, following Chao's 'Mandarin Primer'.
        Missing is the variant for Radical 75 (small form of 木) though.
        Forms 川 and 牜 are not encoded in the Unicode Radical range. Another
        radical like form outside the radical range is 孑, which is not included
        here.
        """

        def __init__(self, dbConnectInst):
            """
            Initialises the RadicalEntryGenerator.

            @type dbConnectInst: object
            @param dbConnectInst: instance of a L{DatabaseConnector}.
            """
            self.cjkDict = {}
            for loc in ['T', 'C', 'J', 'K', 'V']:
                self.cjkDict[loc] = characterlookup.CharacterLookup(loc,
                    dbConnectInst=dbConnectInst)

            self.variantLookup = {}
            for radicalIdx, form, locale in self.KANGXI_VARIANT_FORMS:
                if radicalIdx not in self.variantLookup:
                    self.variantLookup[radicalIdx] = []
                self.variantLookup[radicalIdx].append((form, locale))

        def generator(self):
            """Provides all data of one character per entry."""
            for radicalIdx in range(1, 215):
                radicalForm = self.cjkDict['T'].getKangxiRadicalForm(radicalIdx)
                yield(radicalIdx, radicalForm, 'F', 'TCJKV')

                localeDependantForms = {}
                # get locale main form
                for locale in 'CJKV':
                    radicalLocaleForm \
                        = self.cjkDict[locale].getKangxiRadicalForm(radicalIdx)
                    if radicalForm != radicalLocaleForm:
                        if radicalLocaleForm not in localeDependantForms:
                            localeDependantForms[radicalLocaleForm] = []

                        localeDependantForms[radicalLocaleForm].append(locale)

                for localeDependantForm in localeDependantForms:
                    yield(radicalIdx, localeDependantForm, 'L',
                        ''.join(localeDependantForms[localeDependantForm]))

                ## get variants # Use this if you want to have all Unicode
                #   encoded forms.
                #localeDependantVariants = {}
                #for locale in 'TCJKV':
                    #for variant \
                        #in self.cjk.getKangxiRadicalVariantForms(radicalIdx,
                            #locale):
                        #if variant not in localeDependantVariants:
                            #localeDependantVariants[variant] = []

                        #localeDependantVariants[variant].append(locale)
                #for localeDependantForm in localeDependantVariants:
                    #yield(radicalIdx, localeDependantForm, 'V',
                        #''.join(localeDependantVariants[localeDependantForm]))

                # add variant forms from table
                if radicalIdx in self.variantLookup:
                    for variant, locale in self.variantLookup[radicalIdx]:
                        yield(radicalIdx, variant, 'V', locale)

    PROVIDES = 'KangxiRadicalTable'
    DEPENDS = ['KangxiRadical']
    COLUMNS = ['RadicalIndex', 'Form', 'Type', 'Locale']
    PRIMARY_KEYS = ['RadicalIndex', 'Form']
    INDEX_KEYS = [['Locale']]
    COLUMN_TYPES = {'RadicalIndex': Integer(), 'Form': String(1),
        'Type': String(1), 'Locale': String(6)}

    def getGenerator(self):
        return KangxiRadicalTableBuilder.RadicalEntryGenerator(self.db)\
            .generator()


class KangxiRadicalStrokeCountBuilder(builder.EntryGeneratorBuilder):
    """
    Builds a table with the stroke count of all Kangxi radical main forms.
    """
    class RadicalEntryGenerator:
        """Generates the entries of the radical table."""

        def __init__(self, dbConnectInst):
            """
            Initialises the RadicalEntryGenerator.

            @type dbConnectInst: object
            @param dbConnectInst: instance of a L{DatabaseConnector}.
            """
            self.cjk = characterlookup.CharacterLookup('T',
                dbConnectInst=dbConnectInst)

        def generator(self):
            """Provides all data of one character per entry."""
            for radicalIdx in range(1, 215):
                radicalForm = self.cjk.getKangxiRadicalForm(radicalIdx)
                try:
                    strokeCount = self.cjk.getStrokeCount(radicalForm)
                except exception.NoInformationError:
                    try:
                        equivForm = self.cjk.getRadicalFormEquivalentCharacter(
                            radicalForm)
                        strokeCount = self.cjk.getStrokeCount(equivForm)
                    except exception.NoInformationError:
                        strokeCount = 0
                yield(radicalIdx, strokeCount)

    PROVIDES = 'KangxiRadicalStrokeCount'
    DEPENDS = ['KangxiRadical', 'StrokeCount', 'RadicalEquivalentCharacter']
    COLUMNS = ['RadicalIndex', 'StrokeCount']
    PRIMARY_KEYS = ['RadicalIndex']
    COLUMN_TYPES = {'RadicalIndex': Integer(), 'StrokeCount': Integer()}

    def getGenerator(self):
        return KangxiRadicalStrokeCountBuilder.RadicalEntryGenerator(self.db)\
            .generator()


class SwacAudioCollectionBuilder(builder.EntryGeneratorBuilder):
    """
    Builds an index on a swac audio collection.
    """
    class SwacXMLIndexHandler(xml.sax.ContentHandler):
        """Extracts a list of pronunciation and file name pairs."""
        def __init__(self, fileList):
            self.fileList = fileList

        def startDocument(self):
            self.currentFilePath = None

        def startElement(self, name, attrs):
            if name == 'file':
                self.currentFilePath = None
                for key, value in attrs.items():
                    if key == 'path':
                        self.currentFilePath = value
            elif name == 'tag':
                if self.currentFilePath:
                    pronunciation = None
                    for key, value in attrs.items():
                        if key == 'swac_pron_phon':
                            pronunciation = value
                    if pronunciation:
                        self.fileList.append(
                            (pronunciation, self.currentFilePath))

    class SwaxIndexGenerator:
        """Generates the index table."""

        def __init__(self, dataPath, baseFolderName, quiet):
            """
            Initialises the SwaxIndexGenerator.

            @type dataPath: list of str
            @param dataPath: optional list of paths to the data file(s)
            @type baseFolderName: str
            @param baseFolderName: name of package's basic folder
            @type quiet: bool
            @param quiet: if true no status information will be printed to
                stderr
            """
            self.dataPath = dataPath
            self.baseFolderName = baseFolderName
            self.quiet = quiet

        def generator(self):
            """Provides a pronunciation and a path to the audio file."""
            for path in self.dataPath:
                filePath = os.path.join(os.path.expanduser(path),
                    self.baseFolderName)
                if os.path.exists(filePath):
                    break
            else:
                raise IOError("No package found for '" + self.baseFolderName \
                    + "' under path(s)'" + "', '".join(self.dataPath) + "'")

            try:
                xmlFile = bz2.BZ2File(os.path.join(filePath, 'index.xml.bz2'))
            except IOError:
                raise IOError("Index file 'index.xml.bz2' not found under '" \
                    + filePath + "'")

            fileList = []
            indexHandler = SwacAudioCollectionBuilder.SwacXMLIndexHandler(
                fileList)

            saxparser = xml.sax.make_parser()
            saxparser.setContentHandler(indexHandler)
            # don't check DTD as this raises an exception
            saxparser.setFeature(xml.sax.handler.feature_external_ges, False)
            saxparser.parse(xmlFile)

            seenPronunciations = set()
            doubletteCount = 0
            for pronunciation, filePath in fileList:
                relativePath = os.path.join(self.baseFolderName, filePath)
                if pronunciation not in seenPronunciations:
                    yield(pronunciation, relativePath)
                else:
                    doubletteCount += 1

                seenPronunciations.add(pronunciation)

            if not self.quiet and doubletteCount:
                warn("Found " + str(doubletteCount) \
                    + " similar pronunciations, omitted")

    COLUMNS = ['Pronunciation', 'AudioFilePath']
    PRIMARY_KEYS = ['Pronunciation']
    COLUMN_TYPES = {'Pronunciation': String(255), 'AudioFilePath': Text()}

    BASE_DIRECTORY_NAME = None
    """Name of the base folder of the set as supplied in the .tar file."""

    def getGenerator(self):
        return SwacAudioCollectionBuilder.SwaxIndexGenerator(self.dataPath,
            self.BASE_DIRECTORY_NAME, self.quiet).generator()


class SwacChiBalmHsk1Builder(SwacAudioCollectionBuilder):
    """
    Builds an index on the chi-balm-hsk1 audio collection.
    """
    PROVIDES = 'Pronunciation_zh_cmn'

    BASE_DIRECTORY_NAME = 'chi-balm-hsk1_ogg'


class SwacCmnCaenTanBuilder(SwacAudioCollectionBuilder):
    """
    Builds an index on the cmn-caen-tan audio collection.
    """
    PROVIDES = 'Pronunciation_zh_cmn'

    BASE_DIRECTORY_NAME = 'cmn-caen-tan_ogg'


class GlobbingPronunciationBuilder(builder.EntryGeneratorBuilder):
    """
    Provides an abstract builder for creating an index on a directory of
    pronunciation files following a given mapping from file name to reading.
    """
    BASE_DIRECTORY_NAME = None
    """Directory including the files."""

    FILE_EXTENSIONS = ['.mp3', '.wav']
    """List of file extensions of the audio files."""

    COLUMNS = ['Pronunciation', 'AudioFilePath']
    PRIMARY_KEYS = ['Pronunciation']
    COLUMN_TYPES = {'Pronunciation': String(255), 'AudioFilePath': Text()}

    class FileNameEntryGenerator:
        """Generates the index table."""

        def __init__(self, dataPath, baseFolderName, fileExtensions,
            mappingFunc=lambda x:x, quiet=False):
            """
            Initialises the FileNameEntryGenerator.

            @type dataPath: list of str
            @param dataPath: optional list of paths to the data file(s)
            @type baseFolderName: str
            @param baseFolderName: name of package's basic folder
            @type fileExtensions: list of str
            @param fileExtensions: file name extensions used for globbing
            @type mappingFunc: func
            @param mappingFunc: mapping function for generating the reading
                entry
            @type quiet: bool
            @param quiet: if true no status information will be printed to
                stderr
            """
            self.dataPath = dataPath
            self.baseFolderName = baseFolderName
            self.fileExtensions = fileExtensions
            self.mappingFunc = mappingFunc
            self.quiet = quiet

        def generator(self):
            """Provides a pronunciation and a path to the audio file."""
            for path in self.dataPath:
                filePath = os.path.join(os.path.expanduser(path),
                    self.baseFolderName)
                if os.path.exists(filePath):
                    break
            else:
                raise IOError("No package found for '" + self.baseFolderName \
                    + "' under path(s)'" + "', '".join(self.dataPath) + "'")

            seenPronunciations = set()
            doubletteCount = 0

            import glob
            try:
                for extension in self.fileExtensions:
                    it = glob.iglob(os.path.join(filePath, '*' + extension))
                    for filePath in it:
                        baseName = os.path.basename(filePath)
                        pronunciation = self.mappingFunc(baseName)

                        relativePath = os.path.join(self.baseFolderName,
                            baseName)
                        if pronunciation:
                            if pronunciation not in seenPronunciations:
                                yield(pronunciation, relativePath)
                            else:
                                doubletteCount += 1

                            seenPronunciations.add(pronunciation)
                        elif not self.quiet:
                            warn("No reading gathered from '" \
                                + str(relativePath) + "',  ommitting")

            except IOError:
                raise IOError("Error reading directory '" + filePath + "'")

            if not self.quiet and doubletteCount:
                warn("Found " + str(doubletteCount) \
                    + " similar pronunciations, omitted")

    def getGenerator(self):
        return GlobbingPronunciationBuilder.FileNameEntryGenerator(
            self.dataPath, self.BASE_DIRECTORY_NAME, self.FILE_EXTENSIONS,
            self.getReadingFromFileName, quiet=quiet).generator()

    def getReadingFromFileName(self, fileName):
        raise NotImplementedError


class ChineseLessonsComCantonesePronunciation(GlobbingPronunciationBuilder):
    """
    Builds an index on pronunciation files for Cantonese provided by
    chinese-lessions.com.
    """
    PROVIDES = "Pronunciation_zh_yue"
    DEPENDS = ['CantoneseYaleSyllables']

    BASE_DIRECTORY_NAME = "chineselessionscom_yue"

    TONE_ABBREV = {'HT': '1stToneLevel', 'HF': '1stToneFalling',
        'MR': '2ndTone', 'MT': '3rdTone', 'LF': '4thTone', 'LR': '5thTone',
        'LT': '6thTone'}

    def __init__(self, **options):
        super(ChineseLessonsComCantonesePronunciation, self).__init__(**options)

        self.readingFactory = ReadingFactory()

    def getReadingFromFileName(self, fileName):
        fileRoot, _ = os.path.splitext(fileName)
        matchObj = re.match('([a-z]+)(HT|HF|MR|MT|LF|LR|LT)$', fileRoot)
        if matchObj:
            plainSyllable, toneMarker = matchObj.groups([1, 2])
            toneNumber = self.TONE_ABBREV[toneMarker]
            try:
                return self.readingFactory.getTonalEntity(plainSyllable,
                    toneNumber, 'CantoneseYale')
            except exception.UnsupportedError:
                pass
            except exception.ConversionError:
                pass


class ChineseLessonsComMandarinPronunciation(GlobbingPronunciationBuilder):
    """
    Builds an index on pronunciation files for Mandarin provided by
    chinese-lessions.com.
    """
    PROVIDES = "Pronunciation_zh_cmn"
    DEPENDS = ['PinyinSyllables']

    BASE_DIRECTORY_NAME = "chineselessionscom_cmn"

    def __init__(self, **options):
        super(ChineseLessonsComMandarinPronunciation, self).__init__(**options)

        self.readingFactory = ReadingFactory()

    def getReadingFromFileName(self, fileName):
        fileRoot, _ = os.path.splitext(fileName)
        try:
            return self.readingFactory.convert(fileRoot, 'Pinyin', 'Pinyin',
                sourceOptions={'toneMarkType': 'numbers'})
        except exception.UnsupportedError:
            pass
        except exception.ConversionError:
            pass


class EduTwStrokeOrderIndexBuilder(builder.CSVFileLoader):
    """
    Builds an index for accessing stroke order images on edu.tw.
    """
    PROVIDES = 'EduTwIndex'

    TABLE_CSV_FILE_MAPPING = 'edutw_strokeorderindex.csv'
    TABLE_DECLARATION_FILE_MAPPING = 'edutw_strokeorderindex.sql'


class EclectusCommandLineBuilder(cli.CommandLineBuilder):
    DESCRIPTION = """Builds the database for Eclectus.
Example: \"%prog build allAvail\""""

    BUILD_GROUPS = {
        # source based
        'data': ['SimilarCharacters', 'HSKVocabulary',
            'KangxiRadicalTable', 'RadicalNames_zh_cmn',
            'RadicalTable_zh_cmn__de', 'RadicalTable_zh_cmn__en',
            'KangxiRadicalStrokeCount', 'EDICT', 'CEDICT', 'CEDICTGR', 'CFDICT',
            'HanDeDict', 'UpdateVersion', 'Pronunciation_zh_cmn',
            'Pronunciation_zh_yue', 'JISX0208Set', 'JISX0208_0213Set',
            'EduTwIndex'],
        'base': ['SimilarCharacters', 'KangxiRadicalTable',
            'KangxiRadicalStrokeCount', 'RadicalTable_zh_cmn__en',
            'EduTwIndex'],
        'zh-cmn': ['RadicalNames_zh_cmn', 'Pronunciation_zh_cmn'],
        'ja': ['RadicalTable_ja__en', 'JISX0208Set', 'JISX0208_0213Set'],
        'EDICT_related': ['UpdateVersion'],
        'CEDICT_related': ['UpdateVersion'],
        'CEDICTGR_related': ['UpdateVersion'],
        'HanDeDict_related': ['RadicalTable_zh_cmn__de', 'UpdateVersion'],
        'CFDICT_related': ['UpdateVersion'],
    }

    DB_PREFER_BUILDERS = ['WiktionaryHSKVocabularyBuilder',
        'WeightedCEDICTBuilder', 'WeightedCFDictBuilder',
        'WeightedHanDeDictBuilder', 'WeightedCEDICTGRBuilder',
        'WeightedEDICTBuilder', 'CombinedEnglishRadicalTableBuilder',
        'JISX0208SetExtendedBuilder', 'JISX0208_0213SetExtendedBuilder']
    """Builders prefered for build process."""
    # TODO 'SwacCmnCaenTanBuilder'

    @classmethod
    def getDefaultOptions(cls):
        options = cli.CommandLineBuilder.getDefaultOptions()
        options['databaseUrl'] = util.getDatabaseUrl()
        # dataPath
        options['dataPath'] = ['.']
        # Eclectus path
        buildModulePath = os.path.dirname(os.path.abspath(__file__))
        options['dataPath'].append(os.path.join(buildModulePath, 'data'))
        # cjklib path
        cjklibBuildModule = __import__("cjklib.build")
        cjklibBuildModulePath = os.path.dirname(os.path.abspath(
            cjklibBuildModule.__file__))
        options['dataPath'].append(os.path.join(cjklibBuildModulePath, 'data'))

        # prefer
        options['prefer'] = cls.DB_PREFER_BUILDERS
        options['additionalBuilders'] = cls.getTableBuilderClasses()
        return options

    @classmethod
    def getTableBuilderClasses(cls):
        """
        Gets all classes in module that implement L{TableBuilder}.

        @rtype: list
        @return: list of all classes inheriting form L{TableBuilder} that
            provide a table (i.d. non abstract implementations), with its name
            as key
        """
        return [clss for clss in globals().values() \
            if type(clss) == types.TypeType \
            and issubclass(clss, builder.TableBuilder) \
            and clss.PROVIDES]

        return tableBuilderClasses


if __name__ == "__main__":
    if not EclectusCommandLineBuilder().run():
        sys.exit(1)
