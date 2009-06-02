#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Qt widget integrating Tegaki/Tomoe handwriting character recognition for
Japanese Kanji and Chinese Hanzi.

Includes a QApplication demonstrating the wiget.

10.02.2009 Christoph Burgmer (cburgmer@ira.uka.de)

History:
    * 11.02.2009, show boundaries and keep handwriting within them, resizeable.
    * 12.02.2009, dictionary setting method, stroke count, maximum size,
                  graceful import failure
    * 02.06.2009, ported to also work with Tegaki

Released under the LGPL (http://www.gnu.org/licenses/lgpl.html).
"""

import sys
import os
import signal

# imports needed by tomoe widget
from PyQt4 import QtGui, QtCore
try:
    from tegaki.recognizer import Recognizer
    from tegaki.character import Writing
    recognizerType = 'tegaki'
except ImportError:
    try:
        from tomoe import Recognizer, Writing, Dict
        recognizerType = 'tomoe'
    except ImportError:
        recognizerType = None


class HandwritingWidget(QtGui.QGraphicsView):
    """
    Qt widget integrating Tegaki/Tomoe handwriting character recognition for
    Japanese Kanji and Chinese Hanzi.

    Example:
        dictionary = os.path.join("/usr/local/share/tomoe/recognizer/",
            'handwriting-zh_CN.xml')
        settings = {'tomoe': {'dictionary'; dictionary}}
        widget = HandwritingWidget(mainWindow, dictionary, 200, 200)
        connect(widget, QtCore.SIGNAL("updated()"), showResults)
    """
    class LineDrawingGraphicsScene(QtGui.QGraphicsScene):
        """Graphics scene for drawing strokes and handling recognizer."""
        def __init__(self, parent, recognizerSettings={}, size=100):
            QtGui.QGraphicsScene.__init__(self, parent)

            self.size = 100

            # set pen for handwriting
            self.pen = QtGui.QPen()
            self.pen.setWidth(3)

            self.strokeItemGroups = []
            self.currentStrokeItems = []

            self.setSize(size)
            self.setDictionary(recognizerSettings)

        def setDictionary(self, recognizerSettings={}):
            self.clear_strokes()

            #initialize the default dictionary and a simple recognizer
            if recognizerType == 'tomoe' \
                and 'tomoe' in recognizerSettings \
                and 'dictionary' in recognizerSettings['tomoe']:
                tomoeDict = Dict("XML",
                    filename=recognizerSettings['tomoe']['dictionary'])
                self.recognizer = Recognizer('Simple',
                    dictionary=tomoeDict)

                # will encapsulate stroke data
                self.writing = Writing()
            elif recognizerType == 'tegaki':
                recognizers = Recognizer.get_available_recognizers()
                if not recognizers:
                    raise Exception('No recognizer available')

                if 'tegaki' in recognizerSettings \
                    and 'regognizer' in recognizerSettings['tegaki']:
                    engine = recognizerSettings['tegaki']['regognizer']
                    if engine not in recognizers:
                        raise Exception('recognizer not available')
                else:
                    engine = recognizers.keys()[0]
                recognizer_klass = recognizers[engine]
                self.recognizer = recognizer_klass()

                if 'tegaki' in recognizerSettings \
                    and 'model' in recognizerSettings['tegaki']:
                    model = recognizerSettings['tegaki']['model']
                    if model not in recognizer_klass.get_available_models():
                        raise Exception('Model not available')
                else:
                    model = recognizer_klass.get_available_models().keys()[0]

                self.recognizer.set_model(model)

                # will encapsulate stroke data
                self.writing = Writing()
            else:
                self.writing = None

        def enabled(self):
            return True
            # TODO bug return self.writing != None

        def setSize(self, size):
            for group in self.strokeItemGroups:
                for item in group:
                    self.removeItem(item)

            self.clear()

            self.setSceneRect(0, 0, size, size)

            # draw character grid
            self.setBackgroundBrush(QtCore.Qt.lightGray)
            self.addRect(-1, -1, size+2, size+2,
                QtCore.Qt.white, QtCore.Qt.white).setZValue(-1)
            self.addRect(0.1 * size, 0.1 * size, 0.8 * size, 0.8 * size)
            self.addLine(0.5 * size, 0.1 * size, 0.5 * size, 0.9 * size,
                QtGui.QPen(QtCore.Qt.DashLine))
            self.addLine(0.1 * size, 0.5 * size, 0.9 * size, 0.5 * size,
                QtGui.QPen(QtCore.Qt.DashLine))

            # recalculate drawn strokes
            scaleFactor = 1.0 * size / self.size
            for group in self.strokeItemGroups:
                for item in group:
                    self.addItem(item)
                    line = item.line()
                    line.setLine(line.x1() * scaleFactor,
                        line.y1() * scaleFactor, line.x2() * scaleFactor,
                        line.y2() * scaleFactor)
                    item.setLine(line)

            self.size = size

        def clear_strokes(self):
            """Removes all strokes and clears the drawing area."""
            if self.strokeItemGroups:
                for group in self.strokeItemGroups:
                    for item in group:
                        self.removeItem(item)

                self.strokeItemGroups = []
                if self.writing:
                    self.writing.clear()

        def remove_last_stroke(self):
            """Removes the latest stroke."""
            if self.strokeItemGroups:
                for item in self.strokeItemGroups.pop():
                    self.removeItem(item)

                if self.writing:
                    self.writing.remove_last_stroke()

        def strokeCount(self):
            return self.writing.get_n_strokes()

        def doSearch(self, maxResults=10):
            """Searches for the current stroke input and returns the results."""
            if self.writing and self.writing.get_n_strokes() > 0:
                if recognizerType == 'tomoe':
                    res = self.recognizer.search(self.writing)

                    if maxResults != None:
                        res = res[:min(maxResults, len(res))]

                    return [(r.get_char().get_utf8().decode('utf8'),
                        r.get_score()) for r in res]

                elif recognizerType == 'tegaki':
                    return [(c.decode('utf8'), score) for c, score \
                        in self.recognizer.recognize(self.writing, maxResults)]
            else:
                return []

        def mouseReleaseEvent(self, mouseEvent):
            if mouseEvent.button() & QtCore.Qt.LeftButton:
                # left button released

                #pos = mouseEvent.scenePos()
                #self.keepBounds(pos)
                #self.writing.line_to(pos.x() * 1000 / self.size,
                    #pos.y() * 1000 / self.size)

                self.strokeItemGroups.append(self.currentStrokeItems)
                self.currentStrokeItems = []
                self.emit(QtCore.SIGNAL("strokeAdded()"))

        def mousePressEvent(self, mouseEvent):
            if mouseEvent.button() & QtCore.Qt.LeftButton:
                # left button pressed
                pos = mouseEvent.scenePos()
                self.keepBounds(pos)

                self.writing.move_to(int(pos.x() * 1000 / self.size),
                    int(pos.y() * 1000 / self.size))

        def mouseMoveEvent(self, mouseEvent):
            if mouseEvent.buttons() & QtCore.Qt.LeftButton:
                # mouse is moved with the left button hold down
                lastPos = mouseEvent.lastScenePos()
                self.keepBounds(lastPos)
                pos = mouseEvent.scenePos()
                self.keepBounds(pos)
                self.currentStrokeItems.append(
                    self.addLine(QtCore.QLineF(lastPos, pos), self.pen))

                # tomoe seems to use a 1000x1000 pixel grid
                self.writing.line_to(int(pos.x() * 1000 / self.size),
                    int(pos.y() * 1000 / self.size))

        def keepBounds(self, point):
            """Keep the coordinates inside the scene rectangle."""
            point.setX(min(max(0, point.x()), self.size))
            point.setY(min(max(0, point.y()), self.size))

    def __init__(self, parent, recognizerSettings={}, size=100):
        self.scene = HandwritingWidget.LineDrawingGraphicsScene(parent,
            recognizerSettings, size)

        QtGui.QGraphicsView.__init__(self, self.scene, parent)
        self.setRenderHints(QtGui.QPainter.Antialiasing)

        self.connect(self.scene, QtCore.SIGNAL("strokeAdded()"),
            lambda: self.emit(QtCore.SIGNAL("updated()")))

        self.setInteractive(self.recognizerAvailable())
        self.setMaximumSize(0)

    @staticmethod
    def recognizerAvailable():
        return recognizerType != None

    def setDictionary(self, recognizerSettings):
        self.scene.setDictionary(recognizerSettings)
        self.setInteractive(self.recognizerAvailable())

    def setMaximumSize(self, size):
        self.maximumSize = size

    def results(self, maxResults=None):
        """
        Returns the results for the current strokes with at maximum maxResults.
        """
        if self.scene.enabled():
            return self.scene.doSearch()

    def strokeCount(self):
        if self.scene.enabled():
            return self.scene.strokeCount()

    def clear(self):
        """Removes all strokes and clears the drawing area."""
        if self.scene.enabled():
            self.scene.clear_strokes()
            self.emit(QtCore.SIGNAL("updated()"))

    def remove_last_stroke(self):
        """Removes the latest stroke."""
        if self.scene.enabled():
            self.scene.remove_last_stroke()
            self.emit(QtCore.SIGNAL("updated()"))

    def resizeEvent(self, event):
        QtGui.QGraphicsView.resizeEvent(self, event)
        size = event.size()
        minSize = min(size.width(), size.height())
        if self.maximumSize:
            minSize = min(minSize, self.maximumSize)
        self.scene.setSize(minSize)


class MainWindow(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)

        # this is all you need to get the widget working
        tomoeDictionary = os.path.join("/usr/local/share/tomoe/recognizer/",
            'handwriting-zh_CN.xml')
        recognizerSettings = {'tomoe': {'dictionary': tomoeDictionary},
            'tegaki': {}}
        self.widget = HandwritingWidget(self, recognizerSettings, 200)
        self.connect(self.widget, QtCore.SIGNAL("updated()"), self.showResults)

        # add some nice layout and buttons to clear strokes
        self.centralwidget = QtGui.QWidget(self)
        self.verticalLayout = QtGui.QVBoxLayout(self.centralwidget)
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.clearButton = QtGui.QPushButton(self.centralwidget)
        self.clearButton.setText('&Clear')
        self.backButton = QtGui.QPushButton(self.centralwidget)
        self.backButton.setText('&Back')
        self.resultLabel = QtGui.QLineEdit(self.centralwidget)
        self.horizontalLayout.addWidget(self.clearButton)
        self.horizontalLayout.addWidget(self.backButton)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.verticalLayout.addWidget(self.widget)
        self.verticalLayout.addWidget(self.resultLabel)

        # add connections for clearing stroke input
        self.connect(self.clearButton, QtCore.SIGNAL("clicked()"),
            self.widget.clear)
        self.connect(self.backButton, QtCore.SIGNAL("clicked()"),
            self.widget.remove_last_stroke)

        self.setCentralWidget(self.centralwidget)

    def showResults(self):
        resultList = self.widget.results(10)
        #self.resultLabel.setText(
            #', '.join([char + ' (' + str(s) + ')' for char, s in resultList]))
        self.resultLabel.setText(''.join([char for char, _ in resultList]))


def main():
    # create applicaton
    app = QtGui.QApplication(sys.argv)

    # create main window
    window = MainWindow()
    window.show()

    # react to CTRL+C on the command line
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app.exec_()


if __name__ == '__main__':
    main()
