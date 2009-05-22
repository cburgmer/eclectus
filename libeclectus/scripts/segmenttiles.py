#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
This script cuts an image containing several tiles into single pieces.
Prerequisites:
    - tiles have the same size
    - tiles are separated by a clear background color
    - background is either white or black

Optional information can be provided to optimize segmentation results:
    - manual threshold for selecting segments
    - average tile width/height ratio
    - more specific: average tile size
    - exact grid size

Christoph Burgmer (cburgmer@ira.uka.de)
28.02.2009 Release

License: MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

__version__ = "20090228"

import sys
import re
import os
import locale
import getopt
import codecs

try:
    from PIL import Image, ImageOps, ImageChops, ImageDraw, ImageStat
except ImportError:
    print >>sys.stderr, "Python Imaging Library needed"
    sys.exit(1)

def getCleanEqualSizeGroups(borders):
    """Clean borders to contain equally sized tiles."""
    def recClean(cleanBorders, leftBorders):
        if not leftBorders:
            return [cleanBorders]

        newCleanBorders = []
        if len(cleanBorders) < 2:
            for i in range(0, len(leftBorders)):
                clean = cleanBorders[:]
                clean.append(leftBorders[i])
                newCleanBorders.extend(recClean(clean, leftBorders[i+1:]))

        else:
            gridSizes = [cleanBorders[i] - cleanBorders[i-1] \
                for i in range(1, len(cleanBorders))]
            avgTileSize = sum(gridSizes) / len(gridSizes)

            for i in range(0, len(leftBorders)):
                tileSize = leftBorders[i] - cleanBorders[-1]
                if 0.8 * avgTileSize < tileSize < 1.2 * avgTileSize:
                    clean = cleanBorders[:]
                    clean.append(leftBorders[i])
                    newCleanBorders.extend(recClean(clean,
                        leftBorders[i+1:]))

        return newCleanBorders

    if not borders:
        return []

    return recClean([borders[0]], borders[1:])

def whitespaceBasedSegmentation(projection, threshold=0):
    borders = []
    whiteSpaceStart = None
    for i, v in enumerate(projection):
        if v <= threshold:
            if whiteSpaceStart == None:
                whiteSpaceStart = i
        else:
            if len(borders) == 0:
                borders.append(i / 2)
            elif whiteSpaceStart != None:
                borders.append((i + whiteSpaceStart) / 2)
            whiteSpaceStart = None

    if whiteSpaceStart != None:
        borders.append((len(projection) + whiteSpaceStart) / 2)
    else:
        borders.append(len(projection) - 1)

    return getCleanEqualSizeGroups(borders)

def windowBasedSegmentation(projection, threshold=5, windowSizes=None):
    def findImageBorderWhiteSpace(projection, threshold=0):
        """Get indentation of image from start and end."""
        for left in range(0, len(projection) / 2):
            if projection[left] > threshold:
                break
        for right in range(len(projection)-1, len(projection) / 2, -1):
            if projection[right] > threshold:
                break
        return left, right

    def findWhiteSpaceStart(projection, fromOffset, toOffset, threshold=0):
        """Look for white space region rel. to threshold in given range."""
        if fromOffset < toOffset:
            offsetRange = range(fromOffset, toOffset+1)
        else:
            offsetRange = range(fromOffset, toOffset-1, -1)

        minValue = projection[fromOffset]
        minValueOffset = fromOffset
        for offset in offsetRange:
            if projection[offset] < minValue:
                minValue = projection[offset]
                minValueOffset = offset
            # as soon as we leave the threshold and we have a valid min value,
            #   return
            if projection[offset] > threshold and minValue <= threshold:
                return minValueOffset

        else:
            return fromOffset

    if windowSizes == None:
        minWindowSize = max(1, int(0.015 * len(projection)))
        maxWindowSize = max(minWindowSize, int(0.08 * len(projection)))
        windowSizes = range(minWindowSize, maxWindowSize+1)

    leftWhite, rightWhite = findImageBorderWhiteSpace(projection, 0)

    possibleBorders = []

    for windowSize in windowSizes:
        borders = [0]

        for i in range(0, len(projection) - windowSize + 1):
            lastWindowValue = sum(projection[i-1:i-1 + windowSize])
            windowValue = sum(projection[i:i + windowSize])
            nextWindowValue = sum(projection[i+1:i+1 + windowSize])

            # threshold dependant on rel. window size and average
            #windowDepThreshold = threshold \
                #* sum(projection) / len(projection) \
                #* windowSize / len(projection)
            if lastWindowValue >= windowValue \
                and windowValue < nextWindowValue \
                and windowValue / windowSize <= threshold:
                # find the exact place of the white space as middle of
                #   window doesn't always work
                offset = findWhiteSpaceStart(projection, i,
                    i + windowSize - 1)

                if offset > leftWhite and offset < rightWhite:
                    borders.append(offset)

        borders.append(len(projection) - 1)

        possibleBorders.extend(getCleanEqualSizeGroups(borders))

    return possibleBorders

def getTileBorders(filePath, segmentTiles=windowBasedSegmentation, threshold=5,
    equalTiles=True, gridWidth=None, gridHeight=None, tileWidth=None,
    tileHeight=None, tileRatio=None, background='white', verbose=0):

    def getBordersMinVariance(bordersList):
        """Calculate minimal variance for a list of borders."""
        minVariance = None
        minVarianceBorders = None

        for borders in bordersList:
            cellLengths = [borders[i] - borders[i-1] \
                for i in range(1, len(borders))]

            avg = sum(cellLengths) / len(cellLengths)
            variance = sum([(l - avg) * (l - avg) for l in cellLengths])
            if minVariance == None or variance < minVariance:
                minVariance = variance
                minVarianceBorders = borders

        return minVariance, 100.0 * minVariance / (avg*avg), minVarianceBorders

    def getBorderCandidates(projection, segmentTiles, possibleValues=[],
        threshold=5):
        # get segmented configurations
        borderConfigurations = segmentTiles(projection, threshold=threshold)

        if possibleValues:
            possibleBorders = []
            for borders in borderConfigurations:
                if len(borders) - 1 in possibleValues:
                    possibleBorders.append(borders)
        else:
            possibleBorders = borderConfigurations

        if len(possibleBorders) == 0:
            # only happens if possibleValues are given and restrict len(border) == 2
            if verbose >= 3:
                print 'No segmentation found for allowed values ' \
                    + ', '.join([str(c) for c in possibleValues])
            return []

        elif len(possibleBorders) > 1:
            borderCounts = set([len(border) for border in possibleBorders])

            if len(borderCounts) > 1:
                if verbose >= 3:
                    output = "Found possible configurations: " \
                        + ', '.join([str(count-1) for count in borderCounts])
                    if possibleValues:
                        output += " for allowed values " \
                            + ', '.join([str(c) for c in possibleValues])
                    print output

                # find acceptable variance with most borders
                bestBorders = []
                for value in borderCounts:
                    bordersList = [borders for borders \
                        in possibleBorders if len(borders) == value]

                    if bordersList:
                        variance, relVariance, borders \
                            = getBordersMinVariance(bordersList)
                        if verbose >= 3:
                            print 'Variance ' + str(variance) \
                                + ' (rel variance ' + str(relVariance) \
                                + ') for segmentation ' \
                                + ', '.join([str(b) for b in borders]),

                        if relVariance < 3:
                            bestBorders.append((relVariance, borders))
                            if verbose >= 3:
                                print ', valid'
                        elif verbose >= 3:
                            print ', invalid'

                return bestBorders
            else:
                variance, relVariance, borders = getBordersMinVariance(
                    possibleBorders)
                if verbose >= 3:
                    print 'Variance ' + str(variance) \
                        + ' (rel variance ' + str(relVariance) \
                        + ') for segmentation ' \
                        + ', '.join([str(b) for b in borders])
                return [(relVariance, borders)]

        else:
            bordersList = [borders for borders in possibleBorders]
            variance, relVariance, borders = getBordersMinVariance(
                possibleBorders)
            if verbose >= 3:
                print 'Variance ' + str(variance) \
                    + ' (rel variance ' + str(relVariance) \
                    + ') for segmentation ' \
                    + ', '.join([str(b) for b in borders])
            return [(relVariance, borders)]

    def findWhiteSpaceEnd(projection, fromOffset, toOffset, threshold=0):
        """
        Look for end of white space region rel. to threshold in given range.
        """
        if fromOffset < toOffset:
            offsetRange = range(fromOffset, toOffset+1)
        else:
            offsetRange = range(fromOffset, toOffset-1, -1)

        for offset in offsetRange:
            if projection[offset] > threshold:
                return offset

        else:
            if toOffset == 0 or toOffset == len(projection) - 1:
                return toOffset
            else:
                raise ValueError(
                    "Given position didn't start in white space area:" \
                        + repr([projection[i] for i in offsetRange]))

    def bordersInBounds(borders, bounds):
        """
        Checks if borders are in given bounds, possibly exceding outer image
        borders.
        """
        for i, border in enumerate(borders):
            left, right = bounds[i]
            if i < len(borders) - 1 and border > right:
                False
            elif i > 0 and left > border:
                return False
        else:
            return True

    def findSafeEqualGridSizeBorders(projection, borders, size, threshold=0,
        verbose=0):
        """Try to construct equal grid sizes for given borders."""
        if len(borders) == 2:
            return [0, size-1], size

        # get maximum margin for all tiles
        whiteSpaceAreas = []
        lastBorder = 0
        for i, border in enumerate(borders):
            leftWhiteSpaceEnd = findWhiteSpaceEnd(projection, border,
                lastBorder, threshold)
            if i + 1 == len(borders):
                nextBorder = size-1
            else:
                nextBorder = borders[i+1]
            rightWhiteSpaceEnd = findWhiteSpaceEnd(projection, border,
                nextBorder, threshold)
            whiteSpaceAreas.append((leftWhiteSpaceEnd, rightWhiteSpaceEnd))

        # cut/extend outer left and right whitespace
        whiteSpaceAreaLen = [(right - left) for left, right in whiteSpaceAreas]
        avgInBetweenWhiteSpaceArea \
            = sum(whiteSpaceAreaLen[1:-1]) / len(whiteSpaceAreaLen[1:-1])
        outerWhiteSpaceWidth = int(round(1.0 * avgInBetweenWhiteSpaceArea / 2))
        # left
        firstLeft, firstRight = whiteSpaceAreas[0]
        leftOffset = firstRight - outerWhiteSpaceWidth
        whiteSpaceAreas[0] = (min(firstLeft, leftOffset), firstRight)
        # right
        lastLeft, lastRight = whiteSpaceAreas[-1]
        whiteSpaceAreas[-1] = (lastLeft,
            max(lastRight, lastLeft + outerWhiteSpaceWidth))

        # get tile size
        avgTileSize = int(round(1.0 * (lastLeft - firstRight \
            + 2* outerWhiteSpaceWidth) / (len(borders) - 1)))

        # redistribute borders
        newBorders \
            = [leftOffset + i * avgTileSize for i in range(0, len(borders))]
        # check if in bounds after redistribution
        if bordersInBounds(newBorders, whiteSpaceAreas):
            return newBorders, avgTileSize
        else:
            if verbose:
                areaString = '-' + str(firstRight) + ', ' \
                    + ', '.join([str(l) + '-' + str(r) \
                        for l, r in whiteSpaceAreas[1:-1]]) \
                    + ', ' + str(lastLeft) + '-'
                print "Warning: error finding white space, " \
                    + "cannot distribute tile equally for: " \
                    + ','.join([str(b) for b in newBorders]) + ' in bounds ' \
                    + areaString + " falling back to: " \
                    + ','.join([str(b) for b in borders])
            return borders, None

    def getBestFit(segments):
        """Get minimum variance and ignore non-segmentation solution."""
        if len(segments) > 1:
            _, borders = min([(var, borders) \
                for var, borders in segments if len(borders) > 2])
        else:
            _, borders = segments[0]
        return borders


    # start
    if tileHeight and tileWidth:
        tileRatio = 1.0 * tileWidth / tileHeight

    # load image
    im = Image.open(filePath)
    width, height = im.size

    if background != 'black':
        im = ImageOps.invert(ImageOps.grayscale(im))

    pix = im.load()

    # segment y-axis
    if gridHeight:
        possibleGridHeight = [gridHeight]
    elif tileHeight:
        gridMinHeight = max(int(round(0.6 * height / tileHeight)), 1)
        gridMaxHeight = max(int(round(1.4 * height / tileHeight)), 1)
        possibleGridHeight = range(gridMinHeight, gridMaxHeight + 1)
    else:
        possibleGridHeight = []

    yProjection = []
    for y in range(0, height):
        yProjection.append(sum([pix[x, y] for x in range(0, width)]) / width)

    if verbose >= 3:
        print 'Segmenting along y-axis...'
    ySegments = getBorderCandidates(yProjection, segmentTiles,
        possibleGridHeight, threshold=threshold)

    if not ySegments:
        return [], []

    # segment x-axis
    if gridWidth:
        possibleGridWidth = [gridWidth]
    elif tileWidth:
        gridMinWidth = max(int(round(0.6 * width / tileWidth)), 1)
        gridMaxWidth = max(int(round(1.4 * width / tileWidth)), 1)
        possibleGridWidth = range(gridMinWidth, gridMaxWidth + 1)
    else:
        possibleGridWidth = []

    xProjection = []
    for x in range(0, width):
        xProjection.append(sum([pix[x, y] for y in range(0, height)]) / height)

    if verbose >= 3:
        print 'Segmenting along x-axis...'
    xSegments = getBorderCandidates(xProjection, segmentTiles,
        possibleGridWidth, threshold=threshold)

    if not xSegments:
        return [], []

    # filter best segments
    if tileRatio:
        weightedSegmentations = []
        for i, ySeg in enumerate(ySegments):
            _, yBorders = ySeg
            gridSizeSum = sum([yBorders[b] - yBorders[b-1] \
                for b in range(1, len(yBorders))])
            avgYGridSize = 1.0 * gridSizeSum / (len(yBorders) - 1)

            for j, xSeg in enumerate(xSegments):
                _, xBorders = xSeg
                gridSizeSum = sum([xBorders[b] - xBorders[b-1] \
                    for b in range(1, len(xBorders))])
                avgXGridSize = 1.0 * gridSizeSum / (len(xBorders) - 1)

                ratio = avgXGridSize / avgYGridSize
                variance = (tileRatio - ratio)*(tileRatio - ratio)
                weightedSegmentations.append((variance, yBorders, xBorders))

        # aim for best tile ratio
        if verbose >= 2 and len(weightedSegmentations) > 1:
            print "Found several configurations: " \
                + ', '.join([str(len(xBorders)-1) + 'x' + str(len(yBorders)-1) \
                    for _, yBorders, xBorders in weightedSegmentations]) \
                + '; choosing minimum ratio variance'
        _, yBorders, xBorders = min(weightedSegmentations)

        if equalTiles:
            yBorders, tileSize = findSafeEqualGridSizeBorders(yProjection,
                yBorders, height, threshold=0, verbose=verbose)
            xBorders, tileSize = findSafeEqualGridSizeBorders(xProjection,
                xBorders, width, threshold=0, verbose=verbose)

        return xBorders, yBorders
    elif equalTiles:
        # look for Y-segmentation with equal tile size
        validYSegments = []
        for relativeYVariance, yBorders in ySegments:
            yBorders, equalHeight = findSafeEqualGridSizeBorders(yProjection,
                yBorders, height, threshold=0, verbose=0)
            if equalHeight:
                validYSegments.append((len(yBorders), yBorders))
        # chose the maximum tile count
        if validYSegments:
            if verbose >= 2 and len(validYSegments) > 1:
                print "Found several configurations matching equal tile " \
                    + "height: " \
                    + '; '.join([','.join([str(b) for b in yBorders]) \
                        for _, yBorders in validYSegments]) \
                    + '; choosing maximum tile count'
            _, yBorders = max(validYSegments)
        else:
            if verbose >= 2:
                if len(ySegments) == 1:
                    _, yBorders = ySegments[0]
                    print "Warning: error finding white space, " \
                        + "cannot distribute tile height equally, "\
                        + "falling back to: " \
                        + ','.join([str(b) for b in yBorders])
                else:
                    print "Warning: error finding white space, " \
                        + "cannot distribute tile height equally ," \
                        + "falling back to: " \
                        + '; '.join([','.join([str(b) for b in yBorders]) \
                            for _, yBorders in ySegments]) \
                        + '; choosing minimum size variance for best ' \
                        + 'segmentation'
            # no equal tile size found
            yBorders = getBestFit(ySegments)

        # look for X-segmentation with equal tile size
        validXSegments = []
        for relativeXVariance, xBorders in xSegments:
            xBorders, equalWidth = findSafeEqualGridSizeBorders(xProjection,
                xBorders, width, threshold=0, verbose=0)
            if equalWidth:
                validXSegments.append((relativeXVariance, xBorders))
        # chose the minium variance one
        if validXSegments:
            if verbose >= 2 and len(validXSegments) > 1:
                print "Found several configurations matching equal tile " \
                    + "width: " \
                    + '; '.join([','.join([str(b) for b in xBorders]) \
                        for _, xBorders in validXSegments]) \
                    + '; choosing maximum tile count'
            _, maxBorders = max(validXSegments)
        else:
            if verbose >= 2:
                if len(xSegments) == 1:
                    _, xBorders = xSegments[0]
                    print "Warning: error finding white space, " \
                        + "cannot distribute tile width equally ," \
                        + "falling back to: " \
                        + ','.join([str(b) for b in xBorders])
                else:
                    print "Warning: error finding white space, " \
                        + "cannot distribute tile width equally ," \
                        + "falling back to: " \
                        + '; '.join([','.join([str(b) for b in xBorders]) \
                            for _, xBorders in xSegments]) \
                        + '; choosing minimum size variance for best ' \
                        + 'segmentation'
            # no equal tile size found
            xBorders = getBestFit(xSegments)

        return xBorders, yBorders

    else:
        if verbose >= 2 and len(ySegments) > 1:
            print "Found several configurations for segmenting along y-axis: " \
                + '; '.join([','.join([str(b) for b in yBorders]) \
                    for _, yBorders in ySegments]) \
                + '; choosing minimum size variance'
        yBorders = getBestFit(ySegments)

        if verbose >= 2 and len(xSegments) > 1:
            print "Found several configurations for segmenting along x-axis: " \
                + '; '.join([','.join([str(b) for b in xBorders]) \
                    for _, xBorders in xSegments]) \
                + '; choosing minimum size variance'
        xBorders = getBestFit(xSegments)

        return xBorders, yBorders

def cutImage(filePath, bordersX, bordersY, meanThreshold=253,
    background='white', keepEmpty=False, verbose=0):

    im = Image.open(filePath)
    width, height = im.size

    fileRoot, fileExt = os.path.splitext(filePath)

    if background == 'black':
        fillColor = (0, 0, 0)
    else:
        fillColor = (255, 255, 255)

    if verbose >= 1:
        print "Writing tiles...",
    tileIndex = 0
    offsetY = bordersY[0]
    for y, yBorder in enumerate(bordersY[1:]):
        offsetX = bordersX[0]
        for x, xBorder in enumerate(bordersX[1:]):
            effectiveOffsetX = max(0, offsetX)
            effectiveOffsetY = max(0, offsetY)
            effectiveXBorder = min(width, xBorder)
            effectiveYBorder = min(height, yBorder)

            tile = im.copy().crop((effectiveOffsetX, effectiveOffsetY,
                effectiveXBorder, effectiveYBorder))

            # if effective picture is larger, create a new image obj
            if effectiveOffsetX != offsetX or effectiveOffsetY != offsetY \
                or effectiveXBorder != xBorder or effectiveYBorder != yBorder:
                if verbose >= 2:
                    print "[enlarging tile:]",
                lTile = Image.new(tile.mode,
                    (xBorder - offsetX, yBorder - offsetY), fillColor)
                lTile.paste(tile, (effectiveOffsetX - offsetX,
                    effectiveOffsetY - offsetY))
                tile = lTile

            imageColorMean = ImageStat.Stat(ImageOps.grayscale(tile)).mean[0]
            if keepEmpty \
                or (background == 'black' and imageColorMean >= meanThreshold) \
                or (background != 'black' and imageColorMean <= meanThreshold):
                if verbose >= 1:
                    print str(tileIndex),
                tile.save(fileRoot + '.' + str(tileIndex) + fileExt)
                tileIndex += 1
            else:
                if verbose >= 1:
                    print 'empty',
            offsetX = xBorder
        offsetY = yBorder

    if verbose >= 1:
        print "finished"

def getSegmentationData(fileName):
    baseName = os.path.basename(fileName)
    if baseName not in fileNameLookup:
        return None

    validPaths = []
    for path in fileNameLookup[baseName]:
        if fileName.endswith(path) or path.endswith(fileName):
            validPaths.append(path)
    if len(validPaths) > 1:
        print >>sys.stderr, ('%d matches for file "%s"' % (len(validPaths),
            fileName)).encode(locale.getpreferredencoding())
        return None
    else:
        return segmentationData[validPaths[0]]

def usage():
    """
    Prints the usage for this script.
    """
    print """Usage: python segmenttiles.py [OPTIONS] FILE1 [FILE2 [...]]
segmenttiles.py cuts an image containing several same size tiles into single
pieces.
Prerequisites:
    - tiles have the same size
    - tiles are separated by a clear background color
    - background is either white or black

General commands:
  --segmentation=METHOD      segmentation method: window (default) or whitespace
  --background=(white|black) background color, either white (default) or black
  --ratio=RATIO              average ratio of tiles (width/height)
  --tilesize=WIDTHxHEIGHT    average tile size (more specific than ratio)
  --grid=WIDTHxHEIGHT        exact tile grid of image
  --equaltiles               optimize borders to yield equal size tiles
  --keepempty                don't ommit empty tiles
  --threshold=THRESHOLD      backround color threshold
  --readfrom=FILE            read the segmentation from a file instead
  --test                     write the segmentation data to stdout, don't
                               actually create the tiles
  -v, --verbose=LEVEL        verbosity level
  -V, --version              show version information
  -h, --help                 show this help"""

def version():
    """
    Prints the version of this script.
    """
    print "segmenttiles.py " + str(__version__) \
        + "\nCopyright (C) 2009 Christoph Burgmer, released under MIT License"

def main():
    """
    Main method
    """
    default_encoding = locale.getpreferredencoding()

    # TODO -v/--verbose
    # parse command line parameters
    try:
        opts, args = getopt.getopt(sys.argv[1:],
            "hVv", ["help", "version", "verbose=", "segmentation=",
            "background=", "ratio=", "tilesize=", "grid=",
            "equaltiles", "keepempty", "threshold=", "test", "readfrom="])
    except getopt.GetoptError:
        # print help information and exit
        usage()
        sys.exit(2)

    # start to check parameters
    if len(opts) == 0 and len(args) == 0:
        print "use parameter -h for a short summary on supported functions"
        sys.exit(2)

    segmentationMethods = {'whitespace': (whitespaceBasedSegmentation, 0),
        'window': (windowBasedSegmentation, 5)}
    segmentation, defaultThreshold = segmentationMethods['window']
    background = 'white'
    tileRatio = None
    tileWidth = None
    tileHeight = None
    gridWidth = None
    gridHeight = None
    threshold = None
    verbose = 0
    equalTiles = False
    keepEmpty = False
    readfrom = None
    testRun = False

    for o, a in opts:
        a = a.decode(default_encoding)

        # help screen
        if o in ("-h", "--help"):
            usage()
            sys.exit()

        # version message
        elif o in ("-V", "--version"):
            version()
            sys.exit()

        # verbose reporting
        elif o in ("-v"):
            verbose += 1

        # verbose reporting
        elif o in ("--verbose"):
            try:
                verbose = int(a)
            except ValueError:
                usage()
                sys.exit(2)

        # segmentation methd
        elif o in ("--segmentation"):
            if a not in segmentationMethods:
                usage()
                sys.exit(2)
            segmentation, defaultThreshold = segmentationMethods[a]

        # background color
        elif o in ("--background"):
            if a.lower() not in ['white', 'black']:
                usage()
                sys.exit(2)

            background = a.lower()

        # tile ratio
        elif o in ("--ratio"):
            try:
                tileRatio = float(a)
            except ValueError:
                usage()
                sys.exit(2)

        # tile size
        elif o in ("--tilesize"):
            try:
                width, height = a.split('x')
                tileWidth = float(width)
                tileHeight = float(height)
            except ValueError:
                usage()
                sys.exit(2)

        # grid size
        elif o in ("--grid"):
            try:
                width, height = a.split('x')
                gridWidth = float(width)
                gridHeight = float(height)
            except ValueError:
                usage()
                sys.exit(2)

        # threshold
        elif o in ("--threshold"):
            try:
                threshold = float(a)
            except ValueError:
                usage()
                sys.exit(2)

        # find equal tile size
        elif o in ("--equaltiles"):
            equalTiles = True

        # keep empty tiles
        elif o in ("--keepempty"):
            keepEmpty = True

        # read segmentation from file
        elif o in ("--readfrom"):
            readfrom = a

        # keep empty tiles
        elif o in ("--test"):
            testRun = True

    if threshold == None:
        threshold = defaultThreshold

    fileNames = [name.decode(default_encoding) for name in args]

    if readfrom != None:
        segmentationFile = codecs.open(readfrom, 'r', default_encoding)
        global segmentationData
        segmentationData = {}
        linesIgnoreCount = 0
        for line in segmentationFile:
            matchObj = re.match(
                r'(\S+)\s+\[([\d ,-]+)\],?\s+\[([\d ,-]+)\]\s*$', line)
            if matchObj:
                fileName, xBorderStr, yBorderStr = matchObj.groups([1, 2, 3])
                try:
                    xBorder = [int(e.strip()) for e in xBorderStr.split(',')]
                    yBorder = [int(e.strip()) for e in yBorderStr.split(',')]
                    if fileName in segmentationData:
                        print >>sys.stderr, ('Warning: double entry for "' \
                            + fileName + "'").encode(default_encoding)

                    segmentationData[fileName] = (xBorder, yBorder)
                except ValueError, e:
                    print >>sys.stderr, ('Error reading line "' + line + "'")\
                        .encode(default_encoding)
                    linesIgnoreCount += 1
            else:
                linesIgnoreCount += 1

            # build file name lookup
            global fileNameLookup
            fileNameLookup = {}
            for path in segmentationData:
                baseName = os.path.basename(path)
                if baseName not in fileNameLookup:
                    fileNameLookup[baseName] = []
                fileNameLookup[baseName].append(path)

        print "Read %d entries, ignored %d lines" % (len(segmentationData),
            linesIgnoreCount)
    else:
        segmentationData = None

    for fileName in fileNames:
        if not testRun:
            print ('Processing ' + fileName + '...').encode(default_encoding),
            if verbose >= 1:
                # create new line
                print

        if segmentationData:
            data = getSegmentationData(fileName)
            if not data:
                print 'not data found, skipping'
                continue
            bordersX, bordersY = data
        else:
            bordersX, bordersY = getTileBorders(fileName,
                segmentTiles=segmentation, threshold=threshold,
                equalTiles=equalTiles, gridWidth=gridWidth,
                gridHeight=gridHeight, tileWidth=tileWidth,
                tileHeight=tileHeight, tileRatio=tileRatio,
                background=background, verbose=verbose)
        if testRun:
            if not bordersX or not bordersY:
                print ("%s\tsegmentation failed" % fileName)\
                    .encode(default_encoding)
            else:
                print ("%s\t%s\t%s" % (fileName, repr(bordersX),
                    repr(bordersY))).encode(default_encoding)
        else:
            if not bordersX or not bordersY:
                print "segmentation failed"
                continue

            if verbose >= 1:
                print "Grid " + str(len(bordersX) - 1) + 'x' \
                    + str(len(bordersY) - 1) \
                    + ', (' + ','.join([str(b) for b in bordersX]) + '), (' \
                    + ','.join([str(b) for b in bordersY]) + ')'
            cutImage(fileName, bordersX, bordersY, background=background,
                keepEmpty=keepEmpty, verbose=verbose)
            if verbose == 0:
                print "finished"


if __name__ == '__main__':
    main()
