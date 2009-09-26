#!/bin/bash

UIC="/usr/lib/pymodules/python2.5/PyQt4/uic/pykdeuic4.py"
#UIC="python /usr/share/kde4/apps/pykde4/pykdeuic4.py"

mkdir -p forms
touch forms/__init__.py

$UIC -o forms/UpdateUI.py ui/Update.ui

patch ui/HandwritingPage.ui ui/HandwritingPage.ui.patch
$UIC -o forms/HandwritingPageUI.py ui/HandwritingPage.ui
patch -R ui/HandwritingPage.ui ui/HandwritingPage.ui.patch

$UIC -o forms/ComponentPageUI.py ui/ComponentPage.ui

$UIC -o forms/RadicalPageUI.py ui/RadicalPage.ui

$UIC -o forms/VocabularyPageUI.py ui/VocabularyPage.ui
patch forms/VocabularyPageUI.py ui/VocabularyPageUI.py.patch
