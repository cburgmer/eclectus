#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup
import re
import os
import os.path
import glob
import eclectusqt

VERSION = str(eclectusqt.__version__)
(AUTHOR, EMAIL) = re.match('^(.*?)\s*<(.*)>$', eclectusqt.__author__).groups()
URL = eclectusqt.__url__
LICENSE = eclectusqt.__license__

iconsTarget = os.popen("kde4-config --install icon").read().strip()
dataTarget = os.popen("kde4-config --install data").read().strip()
menuTarget = os.popen("kde4-config --install xdgdata-apps").read().strip()

def mergeLists(*lists):
    resultList = []
    for l in lists:
        resultList.extend(l)
    return resultList

setup(name='eclectus',
    version=VERSION,
    description='Han character dictionary',
    long_description="Eclectus is a small Han character dictionary especially designed for learners of Chinese character based languages like Mandarin Chinese or Japanese.",
    author=AUTHOR,
    author_email=EMAIL,
    url=URL,
    packages=['eclectusqt', 'eclectusqt/forms', 'libeclectus', 'tomoeqt'],
    package_dir={'eclectusqt': 'eclectusqt'},
    package_data={'libeclectus': ['data/*.csv', 'data/*.sql',
        'locale/*/*/libeclectus.mo']},
    scripts=['eclectus'],
    data_files=[('share/doc/eclectus/scripts',
            mergeLists(glob.glob('libeclectus/scripts/*.py'),
                glob.glob('libeclectus/scripts/*.sh'))),
        (os.path.join(dataTarget, 'eclectus'),
            mergeLists(['eclectusqt/eclectusui.rc',
                'eclectusqt/data/style.css'],
                glob.glob('eclectusqt/data/*.png'),
                glob.glob('eclectusqt/data/*.svg'))),
        ('share/doc/eclectus/', ['README', 'changelog', 'COPYING']),
        (os.path.join(iconsTarget, 'eclectus'),
            glob.glob('eclectusqt/data/icons/*.png')),
        (iconsTarget, ['eclectusqt/data/icons/eclectus.png']),
        ('/usr/share/pixmaps/', glob.glob('eclectusqt/data/icons/*.xpm')),
        (menuTarget, ['eclectusqt/eclectus.desktop'])],
    license=LICENSE,
    classifiers=['Intended Audience :: Education',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Education',
        'Intended Audience :: Education',
        'Development Status :: 3 - Alpha',])
