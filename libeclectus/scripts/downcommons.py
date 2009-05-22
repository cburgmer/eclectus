#!/usr/bin/python
# -*- coding: utf8 -*-
#
# Christoph Burgmer, 2008
# Released unter the MIT License.
#

import urllib
import sys
import re
import os

prependURL = "http://commons.wikimedia.org/w/api.php" \
    + "?action=query&prop=imageinfo&iiprop=url&format=xml&titles="
maxFiles = 500

class AppURLopener(urllib.FancyURLopener):
    version="Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)"

urllib._urlopener = AppURLopener()

cat = urllib.quote(sys.argv[1].replace('Category:', ''))
baseUrl = "http://commons.wikimedia.org/w/api.php" \
    + "?action=query&list=categorymembers&cmtitle=Category:" \
    + cat + "&cmnamespace=6&format=xml&cmlimit=" + str(maxFiles)

print "getting cat", cat, "(maximum "+ str(maxFiles) + ")"

continueRegex = re.compile('<query-continue>' \
    + '<categorymembers cmcontinue="([^\>"]+)" />' + '</query-continue>')

continueParam = None

while True:
    if continueParam:
        url = baseUrl + '&cmcontinue=' + urllib.quote(continueParam)
    else:
        url = baseUrl
    print "retrieving category page url", url
    f = urllib.urlopen(url)
    content = f.read()

    for imageName in re.findall(r'<cm[^>]+title="([^\>"]+)" />', content):
        imageDescriptionUrl = prependURL + imageName
        matchObj = re.search("File:([^/]+)$", imageName)
        if matchObj:
            fileName = matchObj.group(1).strip("\n")
            if os.path.exists(fileName):
                print "skipping", fileName
            else:
                print "getting file description page", imageName
                d = urllib.urlopen(imageDescriptionUrl)
                matchObj = re.search('<ii[^>]*?url="([^\>"]+)[^>]*>', d.read())
                if matchObj:
                    fileUrl = matchObj.group(1)
                    print "getting", fileName, fileUrl
                    urllib.urlretrieve(fileUrl, fileName)

    matchObj = continueRegex.search(content)
    if matchObj:
        continueParam = matchObj.group(1)
    else:
        break

