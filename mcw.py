import pymongo
from pymongo.read_preferences import ReadPreference
from pymongo.errors import ConnectionFailure
import threading
import time
import sys
import os

NUMWRITERS = 100
NUMREADERS = 0
QUERY_COUNT=2000
HOST = 'cluster-30.knuckleboys.com'
PORT = 27017

class MyThread(threading.Thread):
    def __init__(self, writer, threadNumber=None):
        threading.Thread.__init__(self)
        self._writer = writer
        self._threadNumber = threadNumber
        if writer:
            self._numWrites = 0

    def run(self):
        while True:
            try:
                #print "starting %s thread: %s" % ("writer" if self._writer else "reader", threading.currentThread().name)
                conn = pymongo.MongoReplicaSetClient(host=HOST,port=PORT,ssl=True,replicaSet='cluster-30', max_pool_size=1)
                db = conn.cranky
            except ConnectionFailure, e:
                sys.stderr.write("Could not connect to MongoDB: %s" % e)
                return 1
            if self._writer:
                for i in range(QUERY_COUNT):
                    obj = {'writer':self._threadNumber, 'num':self._numWrites, 'str':'Goddamnit y u no work?'}
                    self._numWrites += 1
                    # print "%s writing: %s" % (str(self._threadNumber), str(obj))
                    db.foo.insert(obj)
            else:
                conn.read_preference = ReadPreference.SECONDARY
                for i in range(QUERY_COUNT):
                    doc = db.foo.find({'writer':self._threadNumber})
                    # print "%s read: %s" % (str(self._threadNumber), str(doc))
                    getl = list(doc)
            conn.disconnect()
            #print "sleeping %s thread: %s" % ("writer" if self._writer else "reader", threading.currentThread().name)
            time.sleep(1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        HOST = str(sys.argv[1])
    if len(sys.argv) > 2:
        PORT = int(sys.argv[2])
    numThreads = NUMREADERS + NUMWRITERS
    even = True
    while (NUMREADERS + NUMWRITERS > 0):
        if NUMWRITERS > 0:
            print "Launching writer ", NUMWRITERS 
            thread = MyThread(True, NUMWRITERS)
            NUMWRITERS -= 1
        if NUMREADERS > 0:
            print "Launching reader ", NUMREADERS 
            thread = MyThread(False, NUMREADERS + numThreads)
            NUMREADERS -= 1

        thread.setDaemon(True)
        thread.start()
        time.sleep(.01) # Start threads gradually
    while True:
        time.sleep(10) # Keep process running
        print "Still running"
	if (threading.activeCount() < (numThreads *.95)):
		print "lost too many threads, canning it"
		sys.exit()
