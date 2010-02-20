#!/usr/bin/python
# -*- coding: utf-8 -*-
u"""
Merge to lists of similar characters.
"""

import sys
import codecs
import csv
from collections import MutableMapping

class OrderedDict(dict, MutableMapping):

    # Methods with direct access to underlying attributes

    def __init__(self, *args, **kwds):
        if len(args) > 1:
            raise TypeError('expected at 1 argument, got %d', len(args))
        if not hasattr(self, '_keys'):
            self._keys = []
        self.update(*args, **kwds)

    def clear(self):
        del self._keys[:]
        dict.clear(self)

    def __setitem__(self, key, value):
        if key not in self:
            self._keys.append(key)
        dict.__setitem__(self, key, value)

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self._keys.remove(key)

    def __iter__(self):
        return iter(self._keys)

    def __reversed__(self):
        return reversed(self._keys)

    def popitem(self):
        if not self:
            raise KeyError
        key = self._keys.pop()
        value = dict.pop(self, key)
        return key, value

    def __reduce__(self):
        items = [[k, self[k]] for k in self]
        inst_dict = vars(self).copy()
        inst_dict.pop('_keys', None)
        return (self.__class__, (items,), inst_dict)

    # Methods with indirect access via the above methods

    setdefault = MutableMapping.setdefault
    update = MutableMapping.update
    pop = MutableMapping.pop
    keys = MutableMapping.keys
    values = MutableMapping.values
    items = MutableMapping.items

    def __repr__(self):
        pairs = ', '.join(map('%r: %r'.__mod__, self.items()))
        return '%s({%s})' % (self.__class__.__name__, pairs)

    def copy(self):
        return self.__class__(self)

    @classmethod
    def fromkeys(cls, iterable, value=None):
        d = cls()
        for key in iterable:
            d[key] = value
        return d

class CSVFileLoader(object):
    def __init__(self, filePath):
        self.filePath = filePath

    def getGroups(self):
        fileHandle = codecs.open(self.filePath, 'r', 'utf-8')
        csvReader = self._getCSVReader(fileHandle)
        csvType = None
        groups = OrderedDict()

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


def findSimilarGroup(originalGroup, newGroups, groupLookup=None):
    # char to group mapping
    if groupLookup is None:
        groupLookup = {}
        for groupIdx, group in enumerate(newGroups):
            for char in group:
                if char not in groupLookup:
                    groupLookup[char] = []
                groupLookup[char].append(groupIdx)

    # possible matches
    possibleSimilarGroups = []
    for char in originalGroup:
        possibleSimilarGroups.extend(groupLookup.get(char, []))

    # best match
    mostSimilar = None
    mostSimilarShares = None
    for groupIdx in possibleSimilarGroups:
        if (not mostSimilarShares
            or len(newGroups[groupIdx] & originalGroup)
                > len(mostSimilarShares)):
            mostSimilarShares = newGroups[groupIdx] & originalGroup
            mostSimilar = groupIdx

    return mostSimilar

originalGroups = []

collection = set()
for _, group in CSVFileLoader(sys.argv[1]).getGroups().items():
    collection.add(frozenset(group))
    originalGroups.append(frozenset(group))

for fileName in sys.argv[2:]:
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

# first try to restore old order
curIdx = 0
for originalGroup in originalGroups:
    newIdx = findSimilarGroup(originalGroup, newCollection)
    if newIdx:
        for char in sorted(newCollection[newIdx]):
            print ('%d,"%s"' % (curIdx, char)).encode('utf8')
        curIdx += 1
        del newCollection[newIdx]

newCollection.sort(cmp=lambda x,y: cmp(min(x), min(y)))
for idx, charGroup in enumerate(newCollection):
    for char in sorted(charGroup):
        print ('%d,"%s"' % (curIdx+idx, char)).encode('utf8')
