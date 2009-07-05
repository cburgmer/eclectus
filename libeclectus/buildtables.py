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

import getopt
import locale
import types
import sys
import os
import re
import xml.sax
import bz2
import functools
from datetime import datetime

from sqlalchemy import Table, Column, Integer, String, Text, DateTime, Index
from sqlalchemy.sql import and_, or_, not_
from sqlalchemy import select

from cjklib import characterlookup
from cjklib.reading import ReadingFactory
from cjklib import build
from cjklib import exception

BUILD_GROUPS = {
    # source based
    'data': ['SimilarCharacters', 'HSKVocabulary',
        'KangxiRadicalTable', 'RadicalNames_zh_cmn',
        'RadicalTable_zh_cmn__de', 'RadicalTable_zh_cmn__en',
        'KangxiRadicalStrokeCount', 'EDICT', 'CEDICT', 'CEDICTGR', 'HanDeDict',
        'UpdateVersion', 'Pronunciation_zh_cmn', 'Pronunciation_zh_yue'],
    'base': ['UpdateVersion', 'SimilarCharacters', 'KangxiRadicalTable',
        'KangxiRadicalStrokeCount'],
    'zh-cmn': ['RadicalNames_zh_cmn', 'Pronunciation_zh_cmn'],
    'ja': ['RadicalTable_ja__en'],
    'HanDeDict_related': ['RadicalTable_zh_cmn__de'],
}
"""
Definition of build groups available to the user. Recursive definitions are not
allowed and will lead to a lock up.
"""

DB_PREFER_BUILDERS = ['WiktionaryHSKVocabularyBuilder', 'WeightedCEDICTBuilder',
    'WeightedHanDeDictBuilder', 'WeightedCEDICTGRBuilder',
    'WeightedEDICTBuilder', 'BaseAudioLibreDeMotsChinoisBuilder']
"""Builders prefered for build process."""

class UpdateVersionBuilder(build.EntryGeneratorBuilder):
    """Table for keeping track of which date the release was."""
    PROVIDES = 'UpdateVersion'
    COLUMNS = ['TableName', 'ReleaseDate']
    PRIMARY_KEYS = ['TableName']
    COLUMN_TYPES = {'TableName': String(255), 'ReleaseDate': DateTime()}

    def getGenerator(self):
        return build.ListGenerator([]).generator()


class SimilarCharactersBuilder(build.CSVFileLoader):
    """
    Builds a list of characters with similar visual appearance.
    """
    PROVIDES = 'SimilarCharacters'

    TABLE_CSV_FILE_MAPPING = 'similarcharacters.csv'
    TABLE_DECLARATION_FILE_MAPPING = 'similarcharacters.sql'


class RadicalNamesZHCMNBuilder(build.CSVFileLoader):
    """
    Builds a list of kangxi radical names for Mandarin Chinese.
    """
    PROVIDES = 'RadicalNames_zh_cmn'

    TABLE_CSV_FILE_MAPPING = 'radicalnames_zh-cmn.csv'
    TABLE_DECLARATION_FILE_MAPPING = 'radicalnames_zh-cmn.sql'


class BeidaHSKVocabularyBuilder(build.CSVFileLoader):
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
        for line in self.getCSVReader(fileHandle):
            # check for level boundary
            if line[0] == '':
                if line[1][0] in self.LEVELS.keys():
                    currentLevel = self.LEVELS[line[1][0]]
                elif not self.quiet and not re.match(r'^[a-zA-Z]$', line[1]):
                    # skip categories A, B, ... but warn on other content
                    build.warn("Errorneous line: '" + "', '".join(line) + "'")
                continue

            if currentLevel == None and not self.quiet:
                build.warn("No level information found, skipping line: '" \
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
                build.warn("Found " + str(doubleEntryCount) + " repeated entries")
            if multiEntryCount:
                build.warn("Found " + str(multiEntryCount) \
                    + " lines with multiple entries")


class WiktionaryHSKVocabularyBuilder(build.CSVFileLoader):
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
        for headwordTrad, headwordSimp, level in self.getCSVReader(fileHandle):
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
                build.warn("Found " + str(doubleEntryCount) \
                    + " repeated entries")


class WeightedEDICTFormatBuilder(build.EDICTFormatBuilder):
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

    def __init__(self, dataPath, dbConnectInst, quiet=False):
        super(WeightedEDICTFormatBuilder, self).__init__(dataPath,
            dbConnectInst, quiet)

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
            build.EDICTFormatBuilder.getGenerator(self), weightFunc).generator()

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
        build.EDICTFormatBuilder.remove(self)

        self.removeVersion()

    def removeVersion(self):
        if not self.db.engine.has_table('UpdateVersion'):
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
        if not self.db.engine.has_table('UpdateVersion'):
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


class WeightedEDICTBuilder(WeightedEDICTFormatBuilder, build.EDICTBuilder):
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
    build.CEDICTGRBuilder):
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

    def __init__(self, dataPath, dbConnectInst, quiet=False):
        self.ENTRY_REGEX = \
            re.compile(r'\s*(\S+)(?:\s+(\S+))?\s*\[([^\]]*)\]\s*(/.*/)\s*$')
        super(WeightedCEDICTFormatBuilder, self).__init__(dataPath,
            dbConnectInst, quiet)


class WeightedMandarinCEDICTFormatBuilder(WeightedCEDICTFormatBuilder):
    DEPENDS = ['HSKVocabulary']

    WEIGHT_TABLE = 'HSKVocabulary' # TODO 'Level' ascending while 'Weight' should be descending
    WEIGHT_COLUMN = 'Level'
    JOIN_COLUMNS = {'HeadwordTraditional': 'HeadwordTraditional'}


class WeightedCEDICTBuilder(WeightedMandarinCEDICTFormatBuilder,
    build.CEDICTBuilder):
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


class WeightedHanDeDictBuilder(WeightedMandarinCEDICTFormatBuilder,
    build.HanDeDictBuilder):
    """
    Builds the HanDeDict dictionary with weights attached to each entry.
    """
    def extractVersion(self, line):
        matchObj = re.search(u'# HanDeDict ([^\;]+); Copyright', line.strip())
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


class HanDeDictRadicalTableBuilder(build.EntryGeneratorBuilder):
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

    def __init__(self, dataPath, dbConnectInst, quiet=False):
        super(HanDeDictRadicalTableBuilder, self).__init__(dataPath,
            dbConnectInst, quiet)

    def getGenerator(self):
        return HanDeDictRadicalTableBuilder.RadicalEntryGenerator(self.db)\
            .generator()


class KanjidicEnRadicalTableBuilder(build.EntryGeneratorBuilder):
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

    def __init__(self, dataPath, dbConnectInst, quiet=False):
        super(KanjidicEnRadicalTableBuilder, self).__init__(dataPath,
            dbConnectInst, quiet)

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


class KangxiRadicalTableBuilder(build.EntryGeneratorBuilder):
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

    def __init__(self, dataPath, dbConnectInst, quiet=False):
        super(KangxiRadicalTableBuilder, self).__init__(dataPath,
            dbConnectInst, quiet)

    def getGenerator(self):
        return KangxiRadicalTableBuilder.RadicalEntryGenerator(self.db)\
            .generator()


class KangxiRadicalStrokeCountBuilder(build.EntryGeneratorBuilder):
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
                    strokeCount = 0
                yield(radicalIdx, strokeCount)

    PROVIDES = 'KangxiRadicalStrokeCount'
    DEPENDS = ['KangxiRadical', 'StrokeCount']
    COLUMNS = ['RadicalIndex', 'StrokeCount']
    PRIMARY_KEYS = ['RadicalIndex']
    COLUMN_TYPES = {'RadicalIndex': Integer(), 'StrokeCount': Integer()}

    def __init__(self, dataPath, dbConnectInst, quiet=False):
        super(KangxiRadicalStrokeCountBuilder, self).__init__(dataPath,
            dbConnectInst, quiet)

    def getGenerator(self):
        return KangxiRadicalStrokeCountBuilder.RadicalEntryGenerator(self.db)\
            .generator()


class SwacAudioCollectionBuilder(build.EntryGeneratorBuilder):
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
                build.warn("Found " + str(doubletteCount) \
                    + " similar pronunciations, omitted")

    COLUMNS = ['Pronunciation', 'AudioFilePath']
    PRIMARY_KEYS = ['Pronunciation']
    COLUMN_TYPES = {'Pronunciation': String(255), 'AudioFilePath': Text()}

    BASE_DIRECTORY_NAME = None
    """Name of the base folder of the set as supplied in the .tar file."""

    def __init__(self, dataPath, dbConnectInst, quiet=False):
        super(SwacAudioCollectionBuilder, self).__init__(dataPath,
            dbConnectInst, quiet)

    def getGenerator(self):
        return SwacAudioCollectionBuilder.SwaxIndexGenerator(self.dataPath,
            self.BASE_DIRECTORY_NAME, self.quiet).generator()


class BaseAudioLibreDeMotsChinoisBuilder(SwacAudioCollectionBuilder):
    """
    Builds an index on a swac audio collection
    """
    PROVIDES = 'Pronunciation_zh_cmn'

    BASE_DIRECTORY_NAME = 'chi-balm-hsk1_ogg'


class GlobbingPronunciationBuilder(build.EntryGeneratorBuilder):
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
                            build.warn("No reading gathered from '" \
                                + str(relativePath) + "',  ommitting")

            except IOError:
                raise IOError("Error reading directory '" + filePath + "'")

            if not self.quiet and doubletteCount:
                build.warn("Found " + str(doubletteCount) \
                    + " similar pronunciations, omitted")

    def __init__(self, dataPath, dbConnectInst, quiet=False):
        super(GlobbingPronunciationBuilder, self).__init__(dataPath,
            dbConnectInst, quiet)

    def getGenerator(self):
        return GlobbingPronunciationBuilder.FileNameEntryGenerator(dataPath,
            self.BASE_DIRECTORY_NAME, self.FILE_EXTENSIONS,
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

    def __init__(self, dataPath, dbConnectInst, quiet=False):
        super(ChineseLessonsComCantonesePronunciation, self).__init__(dataPath,
            dbConnectInst, quiet)

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

    def __init__(self, dataPath, dbConnectInst, quiet=False):
        super(ChineseLessonsComMandarinPronunciation, self).__init__(dataPath,
            dbConnectInst, quiet)

        self.readingFactory = ReadingFactory()

    def getReadingFromFileName(self, fileName):
        fileRoot, _ = os.path.splitext(fileName)
        try:
            return self.readingFactory.convert(fileRoot, 'Pinyin', 'Pinyin',
                sourceOptions={'toneMarkType': 'Numbers'})
        except exception.UnsupportedError:
            pass
        except exception.ConversionError:
            pass


# builder
def getTableBuilderClasses():
    """
    Gets all classes in module that implement L{TableBuilder}.

    @rtype: dict
    @return: dictionary of all classes inheriting form L{TableBuilder} that
        provide a table (i.d. non abstract implementations), with its name
        as key
    """
    tableBuilderClasses = dict([(clss.__name__, clss) \
        for clss in globals().values() \
        if type(clss) == types.TypeType \
        and issubclass(clss, build.TableBuilder) \
        and clss.PROVIDES])

    return tableBuilderClasses


def version():
    """
    Prints the version of this script.
    """
    print "buildtables.py " \
        + """\nCopyright (C) 2006-2009 Christoph Burgmer"""

def usage():
    """
    Prints the usage for this script.
    """
    print u"""Usage: buildtables.py COMMAND
buildtables.py builds the database for chinesecharacterview.

The database is stored according to the setting of the cjklib and can be changed
by setting the cjklib.conf. Additionally all SQL commands can be printed to
stdout specifying --dump.

General commands:
  -b, --build=BUILD_GROUPS   adds a build group or a specific table to the build
                               list
  -r, --rebuild              tells the build process to rebuild tables even if
                               they already exist
  -l, --list-groups          list all available build groups and exists
  --dataPath=PATH            path to data files
  --dump                     dumps all SQL statements to stdout; no support for
                             builders that depend on a database being present
  -V, --version              prints the version information and exits
  -h, --help                 prints this help and exits
"""

def printFormattedLine(outputString, lineLength=80, subsequentPrefix=''):
    """
    Formats the given input string to fit to a output with a limited line
    length and prints it to stdout with the systems encoding.

    @type outputString: string
    @param outputString: a string that is formated to fit to the screen
    @type lineLength: integer
    @param lineLength: with of screen
    @type subsequentPrefix: string
    @param subsequentPrefix: prefix used after line break
    """
    outputLines = []
    for line in outputString.split("\n"):
        outputEntityList = line.split()
        outputEntityList.reverse()
        column = 0
        output = ''
        while outputEntityList:
            entity = outputEntityList.pop()
            # if the next entity including one trailing space will reach over,
            # break the line
            if column > 0 and len(entity) + column >= lineLength:
                output = output + "\n" + subsequentPrefix + entity
                column = len(subsequentPrefix) + len(entity)
            else:
                if column > 0:
                    output = output + ' '
                    column = column + 1
                column = column + len(entity)
                output = output + entity
            #if len(column) >= lineLength and outputEntityList:
                #output = output + "\n" + subsequentPrefix
                #column = len(subsequentPrefix)
        outputLines.append(output)
    # get output encoding
    language, system_encoding = locale.getdefaultlocale()
    print ("\n".join(outputLines)).encode(system_encoding)

def main():
    """
    Main method of script
    """
    # parse command line parameters
    try:
        opts, args = getopt.getopt(sys.argv[1:], "b:rlqVh", ["help", "version",
            "dataPath=", "build=", "rebuild", "list-groups", "quiet", "dump"])
    except getopt.GetoptError:
        # print help information and exit
        usage()
        sys.exit(2)

    buildGroupList = []
    dataPathList = []
    rebuild = False
    quiet = False
    dump = False

    # get encoding
    language, system_encoding = locale.getdefaultlocale()
    # start to check parameters
    if len(opts) == 0:
        printFormattedLine("use parameter -h for a short summary on " \
            + "supported parameters")
    for o, a in opts:
        a = a.decode(system_encoding)
        # help screen
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        # version message
        elif o in ("-V", "--version"):
            version()
            sys.exit()
        # build group
        elif o in ("-b", "--build"):
            buildGroupList.extend([groupName.strip() for groupName \
                in a.split(',')])
        # set rebuild mode to true
        elif o in ("-r", "--rebuild"):
            rebuild = True
        # set quiet mode to true
        elif o in ("-q", "--quiet"):
            quiet = True
        # set dump mode to true
        elif o in ("--dump"):
            dump = True
        # list build groups
        elif o in ("-l", "--list-groups"):
            printFormattedLine("Generic groups:\n" \
                + "all, for all tables understood by the build script\n" \
                + "allAvail, for all data available to the build script\n")
            printFormattedLine("Standard groups:")
            groupList = BUILD_GROUPS.keys()
            groupList.sort()
            for groupName in groupList:
                content = []
                # get group content, add apostrophes for "sub"groups
                for member in BUILD_GROUPS[groupName]:
                    if BUILD_GROUPS.has_key(member):
                        content.append("'" + member + "'")
                    else:
                        content.append(member)
                printFormattedLine(groupName + ": " + ', '.join(content),
                    subsequentPrefix='  ')
            printFormattedLine("\nGroup names and table names can either be " \
                "given to the build process.")
            sys.exit()
        # data path
        elif o in ("--dataPath"):
            dataPathList.append(a)

    # if no path set, asume default
    if not dataPathList:
        dataPathList = ['.']
        # Eclectus path
        buildModulePath = os.path.dirname(os.path.abspath(__file__))
        dataPathList.append(os.path.join(buildModulePath, 'data'))
        # cjklib path
        cjklibBuildModule = __import__("cjklib.build")
        cjklibBuildModulePath = os.path.dirname(os.path.abspath(
            cjklibBuildModule.__file__))
        dataPathList.append(os.path.join(cjklibBuildModulePath, 'data'))

    dataPath = []
    for pathEntry in dataPathList:
        dataPath.extend(pathEntry.split(':'))

    if buildGroupList:
        # by default fail if a table couldn't be built
        noFail = False
        if 'all' in buildGroupList or 'allAvail' in buildGroupList:
            if 'allAvail' in buildGroupList:
                if len(buildGroupList) == 1:
                    # don't fail on non available
                    noFail = True
                else:
                    # allAvail not compatible with others, as allAvail means not
                    # failing if build fails, but others will need failing when
                    # explicitly named
                    raise ValueError("group 'allAvail' can't be specified " \
                        + "together with other groups.")
            # if generic group given get list
            buildGroupList = build.DatabaseBuilder.getSupportedTables()

        # unpack groups
        groups = []
        while len(buildGroupList) != 0:
            group = buildGroupList.pop()
            if BUILD_GROUPS.has_key(group):
                buildGroupList.extend(BUILD_GROUPS[group])
            else:
                groups.append(group)

        # create builder instance
        databaseSettings = {}
        if dump:
            databaseSettings = {'dump': True}
        dbBuilder = build.DatabaseBuilder(dataPath=dataPath,
            databaseSettings=databaseSettings, quiet=quiet,
            rebuildExisting=rebuild, noFail=noFail, prefer=DB_PREFER_BUILDERS,
            additionalBuilders=getTableBuilderClasses().values())

        try:
            dbBuilder.build(groups)

            print "finished"
        except exception.UnsupportedError:
            printFormattedLine("error building local tables, some names " \
                + "do not exist")
            raise
        except KeyboardInterrupt:
            print >>sys.stderr, "Keyboard interrupt."

if __name__ == "__main__":
    main()
