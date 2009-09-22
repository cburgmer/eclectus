# -*- coding: utf-8 -*-
"""
Radical entries from Wikipedia, conveniently taken from:
http://toolserver.org/~kolossos/templatetiger/tt-table4.php\
?template=Kangxi Radical Infobox&lang=enwiki&where=&is=\
&columns=0,uni,pny,meaning&format=csv

Christoph Burgmer (cburgmer@ira.uka.de)
22.09.2009 Release

License: MIT License (source code), CC-by-sa-3.0 (radical entries)

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
entries = u"""
Radical 1	1	4E00	one	yī	
Radical 2	2	4E28	line, stick	gùn	
Radical 212	212	9F8D	dragon	lóng	
Radical 213	213	9F9C	turtle	guī	
Radical 214	214	9FA0	flute	yue	
Radical 211	211	9F52	teeth	chi	
Radical 9	9	4EBA	man	rén
Radical 30	30	53E3	mouth	kǒu	
Radical 61	61	5FC3	heart	xīn	
Radical 3	3	4E36	dot	zhù	
Radical 4	4	4E3F	slash	piě
Radical 5	5	4E59	second, fishing hook	yǐ	
Radical 6	6	4E85	hook	jué	
Radical 7	7	4E8C	two	èr	
Radical 8	8	4EA0	lid, head	tóu
Radical 10	10	513F	legs	ér	
Radical 11	11	5165	enter	rù	
Radical 12	12	516B	eight	bā
Radical 140	140	8278	grass	cǎo
Radical 24	24	5341	ten	shí
Radical 13	13	5182	wide	jiōng
Radical 14	14	5196	cover	mī
Radical 15	15	51AB	ice	bīng
"""

from cjklib.reading import ReadingFactory
f = ReadingFactory()

for line in entries.split('\n'):
    if not line.strip():
        continue
    _, radicalIdx, _, meaning, pinyin = line.strip('\t').split('\t')
    pinyinNumbers = f.convert(pinyin, 'Pinyin', 'Pinyin',
        targetOptions={'toneMarkType': 'numbers'})
    print '%(idx)d,"%(pinyin)s","%(meaning)s"' \
        % {'meaning': meaning, 'idx': int(radicalIdx), 'pinyin': pinyinNumbers}
