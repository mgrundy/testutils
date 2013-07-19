import pymongo
import sys
import time
import os
HOST = 'localhost'
PORT = 27011
role=1
numWrites=0

if __name__ == "__main__":
    print str(sys.argv[0]), "starting"
    if str(sys.argv[0]) == "reader.py":
    	role=0
    if len(sys.argv) > 1:
	    HOST = str(sys.argv[1])
    if len(sys.argv) > 2:
	    PORT = int(sys.argv[2])
    #  while True:
    for nom in range(1):
      print "starting %s process: %s" % ("writer" if role else "reader", os.getpid())
      conn = pymongo.Connection(host=HOST,port=PORT)
      db = conn.cranky
      for i in range(1):
	 if role:
	     numWrites += 1
      	     obj = {'writer':os.getpid(), 'num':numWrites, 'str':'Foo tar Baz'}
	     # print "%s writing: %s" % (str(self._threadNumber), str(obj))
	     db.foo.insert(obj)
         else:
	     doc = db.foo.find().where("this.field1 == " + str(int(i * i)) +";")
	     #doc = db.foo.find({"field1":i})
	     print i
#	     print "%s read: %s" % (str(os.getpid()), list(doc))
	     getl = list(doc)
         conn.disconnect()
#      time.sleep(10)
