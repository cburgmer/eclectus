forms:
	mkdir forms
	touch forms/__init__.py

	pykdeuic4 -o forms/UpdateUI.py ui/Update.ui

	patch ui/HandwritingPage.ui ui/HandwritingPage.ui.patch
	pykdeuic4 -o forms/HandwritingPageUI.py ui/HandwritingPage.ui
	patch -R ui/HandwritingPage.ui ui/HandwritingPage.ui.patch

	pykdeuic4 -o forms/ComponentPageUI.py ui/ComponentPage.ui

	pykdeuic4 -o forms/RadicalPageUI.py ui/RadicalPage.ui

	pykdeuic4 -o forms/VocabularyPageUI.py ui/VocabularyPage.ui
	patch forms/VocabularyPageUI.py ui/VocabularyPageUI.py.patch
