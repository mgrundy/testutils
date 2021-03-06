import pymongo
import threading
import time
import sys
import os

NUMWRITERS = 0
NUMREADERS = 200
HOST = 'localhost'
PORT = 27011

class MyThread(threading.Thread):
    def __init__(self, writer, threadNumber=None):
        threading.Thread.__init__(self)
        self._writer = writer
        self._threadNumber = threadNumber
        if writer:
            self._numWrites = 0

    def run(self):
      while True:
#         print "starting %s thread: %s" % ("writer" if self._writer else "reader",
                       #                   threading.currentThread().name)
         #conn = pymongo.Connection(host=HOST,port=PORT,max_pool_size=200)
         conn = pymongo.Connection(host=HOST,port=PORT)
         db = conn.cranky
#        while True:
#            time.sleep(1)
         if self._writer:
           while True:
             obj = {'writer':self._threadNumber, 'num':self._numWrites, 'str':'Foo Bar Baz'}
             self._numWrites += 1
             # print "%s writing: %s" % (str(self._threadNumber), str(obj))
             db.foo.insert(obj)
         else:
           for i in range(100):
             #doc = db.foo.find_one()
	     doc = db.foo.find().where("this.field123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890 == this.field123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567891 && this.field123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890> " + str(int(i * i)) +";")
             # print "%s read: %s" % (str(self._threadNumber), str(doc))
	     getl = list(doc)
         conn.disconnect()
         #print "sleeping %s thread: %s" % ("writer" if self._writer else "reader", threading.currentThread().name)
#         print  threading.currentThread().name)
         time.sleep(1)


if __name__ == "__main__":
    os.system("ulimit -n 2048")
    if len(sys.argv) > 1:
        HOST = str(sys.argv[1])
    if len(sys.argv) > 2:
        PORT = int(sys.argv[2])
    numThreads = NUMREADERS + NUMWRITERS
    even = True
    for i in range(numThreads):
        if even and NUMWRITERS > 0:
            thread = MyThread(True, i)
            NUMWRITERS -= 1
            even = not even
        else:
            thread = MyThread(False, i)
            even = not even
        thread.setDaemon(True)
        thread.start()
        time.sleep(.01) # Start threads gradually
    while True:
        time.sleep(10) # Keep process running
        print "Still running"
