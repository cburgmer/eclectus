#!/usr/bin/python
# -*- coding: utf-8 -*-
u"""
Rendering thread. General implementation of a threading helper that can enqueue
operations on other objects and report once those operations are done,
delivering the returned content.

Copyright (C) 2009 Christoph Burgmer
(cburgmer@ira.uka.de)

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""

import sys
import signal
import traceback

from PyQt4.QtCore import Qt, SIGNAL
from PyQt4.QtCore import QThread, QMutex, QMutexLocker, QWaitCondition
from PyQt4 import QtGui

class RenderThread(QThread):
    """
    Thread object that takes control over an actual object exposing thoses
    methods with immediate return with delayed responses.
    """
    def __init__(self, parent):
        QThread.__init__(self, parent)

        self.classObjectLock = QMutex(QMutex.Recursive)
        self.classParamDict = {}
        self.classInstanceDict = {}

        self.queueLock = QMutex(QMutex.Recursive)
        self.queueHasJobsLock = QMutex()      # lock lighter than queueLock
                                              #   while waiting for this lock no
                                              #   lock on the latter can be hold
        self.queueHasJobsCondition = QWaitCondition()
        self.renderQueue = []                 # contains all render requests
        self.newestId = 0                     # newest job Id

        self.renderingLock = QMutex(QMutex.Recursive)
        self.renderingFinishedLock = QMutex() # lock lighter than renderingLock
                                              #   while waiting for this lock no
                                              #   lock on the latter can be hold
        self.renderingFinishedCondition = QWaitCondition()
        self.currentlyRenderingJob = None

    def quit(self):
        self.dequeueAll()

        while self.classInstanceDict:
            classObject = self.classInstanceDict.keys()[0]
            self.removeObject(classObject)

        # enqueue meta command
        self.enqueue(None, 'quit')
        self.wait()

    def setObject(self, classObject, *args, **param):
        """Add or reset a class handled by this render thread."""
        if not self.isRunning():
            raise Exception(
                "Thread needs to be running before objects can be created.")

        self.classObjectLock.lock()
        if classObject in self.classParamDict:
            # TODO remove, or change reloadObject()
            #if self.classParamDict[classObject] == (args, param):
                #self.classObjectLock.unlock()
                ## no changes done
                #return

            self.removeObject(classObject)

        self.classParamDict[classObject] = (args, param)
        self.classInstanceDict[classObject] = None

        self.enqueueWait(classObject, '__init__', *args, **param)
        #self.enqueue(classObject, '__init__', *args, **param)

        ## return only once object is created
        #self.renderingFinishedLock.lock()
        #while not self.classInstanceDict[classObject]:
            #self.renderingFinishedCondition.wait(self.renderingFinishedLock)
        #self.renderingFinishedLock.unlock()
        #self.classObjectLock.unlock()

    def reloadObject(self, classObject):
        """Reloads a class object."""
        self.classObjectLock.lock()
        if classObject not in self.classParamDict:
            self.classObjectLock.unlock()
            raise Exception("Object not set")

        args, param = self.classParamDict[classObject]
        self.setObject(classObject, *args, **param)
        self.classObjectLock.unlock()

    def hasObject(self, classObject):
        """returns the object's instance created by the thread."""
        QMutexLocker(self.classObjectLock)
        return classObject in self.classInstanceDict

    def getObjectInstance(self, classObject):
        """returns the object's instance created by the thread."""
        QMutexLocker(self.classObjectLock)
        return self.classInstanceDict[classObject]

    def removeObject(self, classObject):
        """
        Removes the given object's instance from the render thread, removing all
        affiliated jobs from the queue and canceling an eventually current
        rendered method.
        """
        self.classObjectLock.lock()
        self.queueHasJobsLock.lock()
        self.queueLock.lock()
        # clear all not yet rendered content from the queue
        newQueue = []
        for entry in self.renderQueue:
            jobId, entryClassObject, _, _, _ = entry
            if classObject != entryClassObject:
                newQueue.append(entry)
            else:
                self.emit(SIGNAL("jobDequeued"), jobId)

        self.renderQueue = newQueue

        # interrupt currently rendering
        self.renderingLock.lock()
        if self.currentlyRenderingJob:
            _, entryClassObject, _, _, _ = self.currentlyRenderingJob
            if classObject == entryClassObject:
                self.cancelCurrentJob()
        self.renderingLock.unlock()

        del self.classParamDict[classObject]
        del self.classInstanceDict[classObject]

        self.queueHasJobsLock.unlock()
        self.queueLock.unlock()
        self.classObjectLock.unlock()

    def enqueue(self, classObject, method, *args, **param):
        self.classObjectLock.lock()
        if classObject and classObject not in self.classParamDict:
            self.classObjectLock.unlock()
            raise Exception("Object not set")

        self.queueHasJobsLock.lock()
        self.queueLock.lock()

        self.newestId = (self.newestId + 1) % sys.maxint

        jobId = self.newestId
        self.renderQueue.append((jobId, classObject, method, args, param))

        self.queueLock.unlock()

        self.queueHasJobsCondition.wakeAll()
        self.queueHasJobsLock.unlock()
        self.classObjectLock.unlock()

        if classObject:
            self.emit(SIGNAL("jobEnqueued"), jobId)
            return jobId

    def enqueueWait(self, classObject, method, *args, **param):
        """Enqueues a job and waits until it finishes."""
        def inQueue(jobId):
            QMutexLocker(self.queueLock)
            for qjobId, _, _, _, _ in self.renderQueue:
                if jobId == qjobId:
                    return True

            QMutexLocker(self.renderingLock)
            if self.currentlyRenderingJob:
                qjobId, _, _, _, _ = self.currentlyRenderingJob
                if jobId == qjobId:
                    return True
            return False

        jobId = self.enqueue(classObject, method, *args, **param)
        if jobId == None:
            return

        # return only once method has finished
        self.renderingFinishedLock.lock()
        while inQueue(jobId):
            self.renderingFinishedCondition.wait(self.renderingFinishedLock)
        self.renderingFinishedLock.unlock()
        return jobId

    def getJobEntry(self, jobId):
        self.queueLock.lock()
        for idx, entry in enumerate(self.renderQueue):
            entryJobId, _, _, _, _ = entry
            if entryJobId == jobId:
                break
        else:
            entryJobId = None

        self.queueLock.unlock()
        return entryJobId

    def dequeue(self, jobId):
        QMutexLocker(self.queueHasJobsLock)
        QMutexLocker(self.queueLock)
        # search for entry
        jobEntry = self.getJobEntry(jobId)
        if jobEntry:
            idx = self.renderQueue.index(jobEntry)
            del self.renderQueue[idx]
            self.emit(SIGNAL("jobDequeued"), jobId)

            return True
        else:
            # interrupt currently rendering
            QMutexLocker(self.renderingLock)
            if self.currentlyRenderingJob:
                entryJobId, _, _, _, _ = self.currentlyRenderingJob
                if entryJobId == jobId:
                    self.cancelCurrentJob()
                    return True

            return False

    def dequeueMethod(self, classObject, method):
        self.queueHasJobsLock.lock()
        self.queueLock.lock()
        # clear all not yet rendered content from the queue
        newQueue = []

        for entry in self.renderQueue:
            jobId, entryClassObject, entryMethod, _, _ = entry
            if classObject != entryClassObject or method != entryMethod:
                newQueue.append(entry)
            else:
                self.emit(SIGNAL("jobDequeued"), jobId)

        self.renderQueue = newQueue

        # interrupt currently rendering
        self.renderingLock.lock()
        if self.currentlyRenderingJob:
            _, entryClassObject, entryMethod, _, _ = self.currentlyRenderingJob
            if classObject == entryClassObject and method == entryMethod:
                self.cancelCurrentJob()
        self.renderingLock.unlock()

        self.queueLock.unlock()
        self.queueHasJobsLock.unlock()

    def dequeueAll(self):
        self.queueHasJobsLock.lock()
        self.queueLock.lock()
        # signal all
        for jobId, _, _, _, _ in self.renderQueue:
            self.emit(SIGNAL("jobDequeued"), jobId)

        self.renderQueue = []

        # interrupt currently rendering
        self.renderingLock.lock()
        if self.currentlyRenderingJob:
            self.cancelCurrentJob()

        self.renderingLock.unlock()
        self.queueLock.unlock()
        self.queueHasJobsLock.unlock()

    def isRendering(self):
        self.queueLock.lock()
        self.renderingLock.lock()
        rendering = len(self.renderQueue) > 0 \
            or self.currentlyRenderingJob != None
        self.renderingLock.unlock()
        self.queueLock.unlock()
        return rendering

    def cancelCurrentJob(self):
        """
        This method is called when the currently rendered job should be
        canceled. The default implementation doesn't handle any object specific
        cancel operations and by default returns False. An actual implementation
        should call the current object's cancel routine and then call
        clearCurrentJob() to clear the current job and finally return True.
        """
        return False

    def clearCurrentJob(self):
        """
        This method needs to be called before the current job is canceled.
        """
        self.renderingLock.lock()
        self.currentlyRenderingJob = None
        self.renderingLock.unlock()

    def run(self):
        while True:
            self.queueHasJobsLock.lock()

            hasJobWaiting = len(self.renderQueue) > 0
            while not hasJobWaiting:
                self.emit(SIGNAL("queueEmpty"))
                self.queueHasJobsCondition.wait(self.queueHasJobsLock)
                hasJobWaiting = len(self.renderQueue) > 0

            self.queueLock.lock()
            self.renderingLock.lock()
            self.currentlyRenderingJob = self.renderQueue.pop(0)
            jobId, entryClassObject, method, args, param \
                = self.currentlyRenderingJob

            self.renderingLock.unlock()
            self.queueLock.unlock()
            self.queueHasJobsLock.unlock()

            if entryClassObject != None:
                if method == '__init__':
                    classInstance = entryClassObject(*args, **param)
                    self.classInstanceDict[entryClassObject] = classInstance

                    self.emit(SIGNAL("objectCreated"), jobId, entryClassObject)
                else:
                    classInstance = self.classInstanceDict[entryClassObject]
                    try:
                        content = getattr(classInstance, method)(*args, **param)
                        self.finishJob(jobId, entryClassObject, method, args,
                            param, content)
                    except BaseException, e:
                        if self.currentlyRenderingJob:
                            stacktrace = traceback.format_exc()
                            self.emit(SIGNAL("jobErrorneous"), jobId,
                                entryClassObject, method, args, param, e,
                                stacktrace)
                        else:
                            # job got canceled
                            self.emit(SIGNAL("jobCanceled"), jobId,
                                entryClassObject, method, args, param)

            self.renderingFinishedLock.lock()
            self.clearCurrentJob()
            self.renderingFinishedCondition.wakeAll()
            self.renderingFinishedLock.unlock()

            if entryClassObject == None and method == 'quit':
                return

    def finishJob(self, jobId, classObject, method, args, param, content):
        """
        Needs to be called by the rendering thread once the job has been
        rendered.
        Emits an event that the job was finished. This event can be emitted even
        before the enqueueing process returns.
        """
        self.emit(SIGNAL("jobFinished"), jobId, classObject, method, args,
            param, content)


class CachedRenderThread(RenderThread):
    """
    Provides a chached version of the RenderThread.
    Methods already successfully finished will not be recalled as long they
    are in the local cache.
    @todo Impl: Use cache for methods submitted before the predecessor is
        finished.
    """
    def __init__(self, parent=0):
        RenderThread.__init__(self, parent)

        self.cacheLock = QMutex(QMutex.Recursive)
        self.classObjectCache = {} # use same locks for cache as for object dict
        self.jobIdLookup = {}

    def setCachedObject(self, classObject, *args, **param):
        """Add or reset a cached class handled by this render thread."""
        self.classObjectLock.lock()
        self.cacheLock.lock()

        self.setObject(classObject, *args, **param)

        self.classObjectCache[classObject] = {}

        self.cacheLock.unlock()
        self.classObjectLock.unlock()

    def reloadObject(self, classObject):
        self.classObjectLock.lock()
        if classObject not in self.classParamDict:
            self.classObjectLock.unlock()
            raise Exception("Object not set")

        args, param = self.classParamDict[classObject]
        if classObject in self.classObjectCache:
            self.setCachedObject(classObject, *args, **param)
        else:
            self.setObject(classObject, *args, **param)

        self.classObjectLock.unlock()

    @staticmethod
    def _getHashableCopy(data):
        """
        Constructs a unique hashable deep-copy for a given instance, replacing
        non-hashable datatypes C{set}, C{dict} and C{list} recursively.

        @param data: non-hashable object
        @return: hashable object, C{set} converted to a C{frozenset}, C{dict}
            converted to a C{frozenset} of key-value-pairs (tuple), and C{list}
            converted to a C{tuple}.
        """
        if type(data) == type([]) or type(data) == type(()):
            newList = []
            for entry in data:
                newList.append(CachedRenderThread._getHashableCopy(entry))
            return tuple(newList)
        elif type(data) == type(set([])):
            newSet = set([])
            for entry in data:
                newSet.add(CachedRenderThread._getHashableCopy(entry))
            return frozenset(newSet)
        elif type(data) == type({}):
            newDict = {}
            for key in data:
                newDict[key] = CachedRenderThread._getHashableCopy(data[key])
            return frozenset(newDict.items())
        else:
            return data

    def setCacheInvalid(self):
        """Clears the whole cache and forces later calls to be rerendered."""
        self.cacheLock.lock()
        self.classObjectCache = {}
        self.cacheLock.unlock()

    def cleanCacheFromRemovedObject(self, classObject):
        self.cacheLock.lock()
        if classObject in self.classObjectCache:
            del self.classObjectCache[classObject]
        self.cacheLock.unlock()

    def hasCachedContent(self, classObject, method, *args, **param):
        request = (method, CachedRenderThread._getHashableCopy(args),
            CachedRenderThread._getHashableCopy(param))

        self.cacheLock.lock()
        hasContent = classObject in self.classObjectCache \
            and request in self.classObjectCache[classObject]
        self.cacheLock.unlock()
        return hasContent

    def hasCachedContentForId(self, jobId):
        self.cacheLock.lock()
        if jobId in self.jobIdLookup:
            classObject, method, args, param = self.jobIdLookup[jobId]
            hasContent = self.hasCachedContent(classObject, method, *args,
                **param)
        else:
            hasContent = False
        self.cacheLock.unlock()
        return hasContent

    def getCachedContent(self, classObject, method, *args, **param):
        """
        Gets the cached content for the given request, returns None if None.
        """
        request = (method, CachedRenderThread._getHashableCopy(args),
            CachedRenderThread._getHashableCopy(param))

        QMutexLocker(self.classObjectLock)
        QMutexLocker(self.cacheLock)
        if classObject in self.classParamDict \
            and request in self.classObjectCache[classObject]:
            return self.classObjectCache[classObject][request]
        else:
            raise ValueError('No cached content available')

    def getCachedContentForId(self, jobId):
        QMutexLocker(self.cacheLock)
        if jobId in self.jobIdLookup:
            classObject, method, args, param = self.jobIdLookup[jobId]
            return self.getCachedContent(classObject, method, *args, **param)

    def postFromCache(self, classObject, method, *args, **param):
        """
        Tries to answer the method request using cache contents.
        If no so far rendered content can be found -1 is returned, in case of
        success an event emitted, a new id is generated and returned.
        """
        self.classObjectLock.lock()
        self.cacheLock.lock()
        if classObject not in self.classParamDict:
            self.cacheLock.unlock()
            self.classObjectLock.unlock()
            raise Exception("Object not set")

        jobId = -1

        if classObject in self.classObjectCache:
            request = (method, CachedRenderThread._getHashableCopy(args),
                CachedRenderThread._getHashableCopy(param))
            if request in self.classObjectCache[classObject]:
                self.queueLock.lock()

                self.newestId = (self.newestId + 1) % sys.maxint
                jobId = self.newestId

                self.queueLock.unlock()

                content = self.classObjectCache[classObject][request]

                self.finishJob(jobId, classObject, method, args, param, content)

        self.cacheLock.unlock()
        self.classObjectLock.unlock()

        return jobId

    def removeObject(self, classObject):
        RenderThread.removeObject(self, classObject)
        self.cleanCacheFromRemovedObject(classObject)

    def enqueue(self, classObject, method, *args, **param):
        if classObject and method != '__init__':
            jobId = self.postFromCache(classObject, method, *args, **param)
            if jobId >= 0:
                return jobId

        return RenderThread.enqueue(self, classObject, method, *args, **param)

    def finishJob(self, jobId, classObject, method, args, param, content):
        if method != '__init__':
            self.cacheLock.lock()
            #if classObject not in self.classObjectCache:
                #self.classObjectCache[classObject] = {}
            if classObject in self.classObjectCache:
                request = (method, CachedRenderThread._getHashableCopy(args),
                    CachedRenderThread._getHashableCopy(param))
                self.classObjectCache[classObject][request] = content
                self.jobIdLookup[jobId] = (classObject, method, args, param)
            self.cacheLock.unlock()

        RenderThread.finishJob(self, jobId, classObject, method, args,
            param, content)


class UniqueMethodRenderThread(CachedRenderThread):
    """RenderThread that only renders one method at a time."""
    # TODO what's the usecase?
    def cleanExpiredMethod(self, classObject, method, *args, **param):
        """
        Remove all old results of the given object for the given method that
        were not generated with the given parameters.
        """
        self.classObjectLock.lock()
        request = (method, CachedRenderThread._getHashableCopy(args),
            CachedRenderThread._getHashableCopy(param))
        if classObject in self.classObjectCache:
            for entryRequest in self.classObjectCache[classObject].copy():
                entryMethod, _, _ = entryRequest
                if entryMethod == method and entryRequest != request:
                    del self.classObjectCache[classObject][entryRequest]
        self.classObjectLock.unlock()

    def enqueue(self, classObject, method, *args, **param):
        if classObject:
            # remove all same methods with different parameters
            self.dequeueMethod(classObject, method)
            # clear cache from old content
            self.cleanExpiredMethod(classObject, method, *args, **param)
        CachedRenderThread.enqueue(self, classObject, method, *args, **param)


class SQLRenderThread(CachedRenderThread):
    """
    RenderThread extending the UniqueMethodRenderThread by supplying a cancel
    method for classes with database access. The database object needs to be
    given either on the object as .db subobject or explicitly by
    setObjectDBObject().
    The database object needs to have a 'connection' attribute which supports an
    interrupt() method.
    """
    def __init__(self, parent=0):
        self.dbObjectLock = QMutex(QMutex.Recursive)
        self.dbObject = {}
        CachedRenderThread.__init__(self, parent)

    def setObject(self, classObject, *args, **param):
        self.dbObjectLock.lock()
        if classObject in self.dbObject:
            del self.dbObject[classObject]
        self.dbObjectLock.unlock()
        CachedRenderThread.setObject(self, classObject, *args, **param)

    def setObjectDBObject(self, classObject, db):
        self.dbObjectLock.lock()
        self.dbObject[classObject] = db
        self.dbObjectLock.unlock()

    def cancelCurrentJob(self):
        QMutexLocker(self.renderingLock)
        if self.currentlyRenderingJob:
            _, classObject, _, _, _ = self.currentlyRenderingJob
            try:
                QMutexLocker(self.dbObjectLock)
                if classObject in self.dbObject:
                    db = self.dbObject[classObject]
                else:
                    classObjectInst = self.getObjectInstance(classObject)
                    if hasattr(classObjectInst, 'db'):
                        db = classObjectInst.db
                    else:
                        return False

                self.clearCurrentJob()
                db.connection.interrupt()
                return True
            except KeyError:
                return False


def main():
    class Worker:
        classInstCount = 0

        def __init__(self, name=None):
            self.classInstCount += 1
            if name != None:
                self.name = name
            else:
                self.name = "Worker" + str(self.classInstCount)

        def work(self, text=None):
            import time
            time.sleep(2)
            if text:
                print self.name, text
            else:
                print self.name, "working"

    def status(text, params):
        print 'status', text, repr(params)

    # create applicaton
    app = QtGui.QApplication(sys.argv)

    #renderThread = RenderThread(app)
    renderThread = CachedRenderThread(app)
    #renderThread = UniqueMethodRenderThread(app)
    #renderThread = SQLRenderThread(app)

    app.connect(renderThread, SIGNAL("jobEnqueued"),
        lambda *x: status("jobEnqueued", x))
    app.connect(renderThread, SIGNAL("jobDequeued"),
        lambda *x: status("jobDequeued", x))
    app.connect(renderThread, SIGNAL("objectCreated"),
        lambda *x: status("objectCreated", x))
    app.connect(renderThread, SIGNAL("jobFinished"),
        lambda *x: status("jobFinished", x))
    app.connect(renderThread, SIGNAL("jobErrorneous"),
        lambda *x: status("jobErrorneous", x))
    app.connect(renderThread, SIGNAL("jobCanceled"),
        lambda *x: status("jobCanceled", x))

    renderThread.start()

    renderThread.setObject(Worker)
    worker1 = renderThread.getObjectInstance(Worker)
    renderThread.enqueue(Worker, 'work')
    renderThread.enqueue(Worker, 'work', text='working too')
    renderThread.setObject(Worker, name="WorkerX")
    worker2 = renderThread.getObjectInstance(Worker)
    renderThread.enqueue(Worker, 'work')

    #renderThread.setObject(Worker)
    #worker1 = renderThread.getObjectInstance(Worker)
    #renderThread.enqueue(Worker, 'work')
    #import time
    #time.sleep(3)
    #renderThread.enqueue(Worker, 'work', text='working too')
    #renderThread.enqueue(Worker, 'work', text='working too')
    #time.sleep(5)
    #renderThread.enqueue(Worker, 'work', text='working too')
    #renderThread.enqueue(Worker, 'work', text='working too')
    #renderThread.enqueue(Worker, 'work', text='working too')


    #from cjklib.reading import ReadingFactory
    #renderThread.setObject(ReadingFactory)

    #renderThread.enqueue(ReadingFactory, 'decompose', u"tiān'ānmén", 'Pinyin')
    #renderThread.enqueue(ReadingFactory, 'decompose', u"tiān'ānmén", 'Pinyin')

    #from cjklib.characterlookup import CharacterLookup
    #renderThread.setObject(CharacterLookup)

    #renderThread.enqueue(CharacterLookup, 'getCharactersForComponents',
        #componentList=[u'口'], locale='C')


    #from cjklib.build import DatabaseBuilder
    #renderThread.setObject(DatabaseBuilder, dbConnectInst=db, dataPath=[])

    #renderThread.enqueue(DatabaseBuilder, 'build',
        #tables=[u'StrokeCount'])
    #renderThread.enqueue(DatabaseBuilder, 'build',
        #tables=[u'StrokeCount'])
    #renderThread.enqueue(DatabaseBuilder, 'build',
        #tables=[u'StrokeCount'])
    #renderThread.enqueue(DatabaseBuilder, 'build',
        #tables=[u'StrokeCount'])

    # react to CTRL+C on the command line
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app.exec_()


if __name__ == '__main__':
    main()
