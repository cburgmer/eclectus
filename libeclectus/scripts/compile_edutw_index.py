#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Compiles an index from stroke order images on edu.tw
# Christoph Burgmer, 2009
# Released unter the MIT License.
#

import urllib
import sys
import re

indexURL = "http://www.edu.tw/files/site_content/M0001/bishuen/bi%d.htm?open"

class AppURLopener(urllib.FancyURLopener):
    version="Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)"

urllib._urlopener = AppURLopener()
print >> sys.stderr, "Reading from %s" % indexURL
for radicalIdx in range(1, 215):
    sys.stderr.write('.')
    sys.stderr.flush()

    url = indexURL % radicalIdx
    f = urllib.urlopen(url)
    content = f.read().decode('big5hkscs', 'replace')

    for charEntry in re.findall(
        r'(?i)<a href="(p\d+.\.htm\?open)"><b>(.)</b></a>', content):
        page, char = charEntry
        print ("'%s','%s'" % (char, page)).encode('utf8')

