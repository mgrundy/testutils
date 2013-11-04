#!/usr/bin/python

import json, bson.json_util 
import pprint, sys, re
import optparse
import datetime
import time
from pprint import pprint
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure


def main():
	count = 0
	errors = 0

	parser = optparse.OptionParser(usage="""\
				%prog [database] [collection] [filename]
				export MongoDB log file into MongoDB """)

	# add in command line options. Add mongo host/port combo later
	parser.add_option("-f", "--filename", dest="fname",
			    help="name of file to import",
			    default=None)
	parser.add_option("-d", "--database", dest="database",
			    help="name of database",
			    default=None)
	parser.add_option("-c", "--collection", dest="collection",
			    help="collection name",
			    default=None)
	(options, args) = parser.parse_args()

	if options.database is None:
		print "\nERROR: Must specify database \n"
		sys.exit(-1)

	if options.collection is None:
		print "\nERROR: Must specify collection name\n"
		sys.exit(-1)

	if options.fname is None:
		print "\nERROR: Must specify name of file to import\n"
		sys.exit(-1)

	# connect to mongo
	try:
		connection = MongoClient('localhost', 27017)
	except ConnectionFailure, e:
		sys.stderr.write("Could not connect to MongoDB: %s" % e)
		sys.exit(1)
	# get a handle to the database
	db = connection[options.database]
	# and the collection
	logs = db[options.collection]
	# Format from mongod log files
	format = "%a %m %d %H:%M:%S"
	# open up and lets go
	for line in open(options.fname, 'r'):	
		try:
			data = json.loads(line)
			count += 1
			if 'ts' in data:
				ldate = datetime.datetime.strptime(data['ts'],format)
				ldate=ldate.replace(year=2013)
				data['ts']=ldate
			logs.insert(data)
		except ValueError, e:
			# print sys.exc_info()
			print e
			errors += 1
			colstr = re.findall("\(char (\d+)\)", str(e))
			column = int(colstr[0])
			print line[:column], '>>>>', line[column:]
			#sys.exit(1)

	print "lines imported", count, " errors: ", errors

if __name__ == "__main__":
	main()
