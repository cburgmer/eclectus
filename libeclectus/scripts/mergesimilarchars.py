#!/usr/bin/python
# -*- coding: utf-8 -*-
u"""
Merge to lists of similar characters.
"""

import sys
import codecs
import csv

class CSVFileLoader(object):
    def __init__(self, filePath):
        self.filePath = filePath

    def getGroups(self):
        fileHandle = codecs.open(self.filePath, 'r', 'utf-8')
        csvReader = self._getCSVReader(fileHandle)
        csvType = None
        groups = {}

        for line in csvReader:
            if not csvType:
                if len(line) == 1:
                    csvType = 'groupString'
                else:
                    csvType = 'groupIndex'

            if csvType == 'groupString':
                if len(line) != 1:
                    raise Exception("Invalid mixture of groups")
                groups[str(len(groups))] = list(line[0])

            elif csvType == 'groupIndex':
                if len(line) == 1:
                    raise Exception("Invalid mixture of groups")
                group, char = line
                if group not in groups:
                    groups[group] = []
                groups[group].append(char)

        return groups

    class DefaultDialect(csv.Dialect):
        """Defines a default dialect for the case sniffing fails."""
        quoting = csv.QUOTE_NONE
        delimiter = ','
        lineterminator = '\n'
        quotechar = "'"
        # the following are needed for Python 2.4
        escapechar = "\\"
        doublequote = True
        skipinitialspace = False

    # TODO unicode_csv_reader(), utf_8_encoder(), byte_string_dialect() used
    #  to work around missing Unicode support in csv module
    @staticmethod
    def unicode_csv_reader(unicode_csv_data, dialect, **kwargs):
        # csv.py doesn't do Unicode; encode temporarily as UTF-8:
        csv_reader = csv.reader(CSVFileLoader.utf_8_encoder(unicode_csv_data),
            dialect=CSVFileLoader.byte_string_dialect(dialect), **kwargs)
        for row in csv_reader:
            # decode UTF-8 back to Unicode, cell by cell:
            yield [unicode(cell, 'utf-8') for cell in row]

    @staticmethod
    def utf_8_encoder(unicode_csv_data):
        for line in unicode_csv_data:
            yield line.encode('utf-8')


    @staticmethod
    def byte_string_dialect(dialect):
        class ByteStringDialect(csv.Dialect):
            def __init__(self, dialect):
                for attr in ["delimiter", "quotechar", "escapechar",
                    "lineterminator"]:
                    old = getattr(dialect, attr)
                    if old is not None:
                        setattr(self, attr, str(old))

                for attr in ["doublequote", "skipinitialspace", "quoting"]:
                    setattr(self, attr, getattr(dialect, attr))

                csv.Dialect.__init__(self)

        return ByteStringDialect(dialect)

    def _getCSVReader(self, fileHandle):
        """
        Returns a csv reader object for a given file name.

        The file can start with the character '#' to mark comments. These will
        be ignored. The first line after the leading comments will be used to
        guess the csv file's format.

        @type fileHandle: file
        @param fileHandle: file handle of the CSV file
        @rtype: instance
        @return: CSV reader object returning one entry per line
        """
        def prependLineGenerator(line, data):
            """
            The first line red for guessing format has to be reinserted.
            """
            yield line
            for nextLine in data:
                yield nextLine

        line = '#'
        try:
            while line.strip().startswith('#'):
                line = fileHandle.next()
        except StopIteration:
            return csv.reader(fileHandle)
        try:
            self.fileDialect = csv.Sniffer().sniff(line, ['\t', ','])
            # fix for Python 2.4
            if len(self.fileDialect.delimiter) == 0:
                raise csv.Error()
        except csv.Error:
            self.fileDialect = CSVFileLoader.DefaultDialect()

        content = prependLineGenerator(line, fileHandle)
        #return csv.reader(content, dialect=self.fileDialect) # TODO
        return CSVFileLoader.unicode_csv_reader(content, self.fileDialect)


collection = set()
for fileName in sys.argv[1:]:
    for _, group in CSVFileLoader(fileName).getGroups().items():
        collection.add(frozenset(group))
collection = list(collection)

charGroupMap = {}
for groupIdx, group in enumerate(collection):
    for char in group:
        if char not in charGroupMap:
            charGroupMap[char] = set()
        charGroupMap[char].add(groupIdx)

# remove groups, that are completely covered by a bigger one
newCollection = []
for groupIdx, group in enumerate(collection):
    # Check if we have a group included in another one.
    # Necessary: groups need to intersect
    otherGroups = set()
    for char in group:
        otherGroups.update(charGroupMap[char])
    otherGroups.remove(groupIdx)

    # Sufficient: inclusion
    for otherGroupIdx in otherGroups:
        if group <= collection[otherGroupIdx]:
            for char in group:
                charGroupMap[char].remove(groupIdx)
            break
    else:
        newCollection.append(group)

# find groups that are totally included in other groups
charMultiGroups = [char for char in charGroupMap if len(charGroupMap[char]) > 1]
if charMultiGroups:
    print "Chars in several groups:", ' '.join(charMultiGroups).encode('utf8')

newCollection.sort(cmp=lambda x,y: cmp(min(x), min(y)))
for idx, charGroup in enumerate(newCollection):
    for char in sorted(charGroup):
        print ('%d,"%s"' % (idx, char)).encode('utf8')
