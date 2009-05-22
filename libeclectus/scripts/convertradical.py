#!/usr/bin/python
# -*- coding: utf-8 -*-
u"""
Convert radical name entries to simplified form.
"""

import sys

from cjklib import characterlookup

def getSimplified(charString):
    """
    Gets the Chinese simplified character representation for the given
    character string.

    @type charString: str
    @param charString: string of Chinese characters
    @rtype: list of list of str
    @returns: list of simplified Chinese characters
    """
    simplified = []
    for char in charString:
        simplifiedVariants \
            = set(characterLookup.getCharacterVariants(char, 'S'))
        if isSemanticVariant(char, simplifiedVariants):
            simplifiedVariants.add(char)
        if len(simplifiedVariants) == 0:
            simplified.append(char)
        else:
            simplified.append(list(simplifiedVariants))
    return simplified

def getTraditional(charString):
    """
    Gets the traditional character representation for the given character
    string.

    @type charString: str
    @param charString: string of Chinese characters
    @rtype: list of list of str
    @returns: list of simplified Chinese characters
    @todo Lang: Implementation is too simple to cover all aspects.
    """
    traditional = []
    for char in charString:
        traditionalVariants \
            = set(characterLookup.getCharacterVariants(char, 'T'))
        if isSemanticVariant(char, traditionalVariants):
            traditionalVariants.add(char)
        if len(traditionalVariants) == 0:
            traditional.append(char)
        else:
            traditional.append(list(traditionalVariants))
    return traditional

def isSemanticVariant(char, variants):
    """
    Checks if the character is a semantic variant form of the given
    characters.

    @type char: str
    @param char: Chinese character
    @type variants: list of str
    @param variants: Chinese characters
    @rtype: bool
    @return: C{True} if the character is a semantic variant form of the
        given characters, C{False} otherwise.
    """
    vVariants = []
    for variant in variants:
        vVariants.extend(
            characterLookup.getCharacterVariants(variant, 'M'))
        vVariants.extend(
            characterLookup.getCharacterVariants(variant, 'P'))
    return char in vVariants

def entry2String(entry):
    return ''.join(['/'.join(e) for e in entry])

characterLookup = characterlookup.CharacterLookup()

for line in sys.stdin:
    if not line:
        sys.exit(0)
    line = line.decode('utf8')
    radicalIdx, radicalType, traditionalName, shortTraditionalName, pinyin \
        = line.strip().split(',')
    simplifiedName = entry2String(getSimplified(traditionalName))
    if traditionalName != entry2String(getTraditional(traditionalName)):
        print >>sys.stderr, "warning: input string has mixed simplified and " \
            + "traditional forms", traditionalName
    shortSimplifiedName = entry2String(getSimplified(shortTraditionalName))
    if shortTraditionalName != entry2String(getTraditional(
        shortTraditionalName)):
        print >>sys.stderr, "warning: input string has mixed simplified and " \
            + "traditional forms", shortTraditionalName

    print ','.join([radicalIdx, radicalType, traditionalName, simplifiedName,
        shortTraditionalName, shortSimplifiedName, pinyin]).encode('utf8')
