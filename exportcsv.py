#!/usr/bin/python

import csv
import itertools
import sys
import optparse
from pymongo import MongoClient


def main():
	parser = optparse.OptionParser(usage="""\
				%prog [database] [collection] [filename]
				import MongoDB log file into MongoDB """)

	# add in command line options. Add mongo host/port combo later
	parser.add_option("-f", "--fields", dest="fields",
			    help="names of fields to export",
			    default=None)
	parser.add_option("-o", "--filename", dest="fname",
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
	# connect to mongoDB
	try:
		connection = MongoClient('localhost', 27017)
	except ConnectionFailure, e:
		sys.stderr.write("Could not connect to MongoDB: %s" % e)
		sys.exit(1)
	# get a handle to the database
	db = connection[options.database]
	# and the collection
	coll = db[options.collection]
	try:
		csvfile = open(options.fname, 'wb')
		fieldList = options.fields.split(",")
		# create a dictionary of fieldname:1
		fields = dict((el,1) for el in fieldList)
		dbwriter = csv.DictWriter(csvfile, fieldList,
				delimiter=',', quotechar='"', 
				quoting=csv.QUOTE_NONNUMERIC)
		dbwriter.writeheader()
		dbwriter.writerows(coll.find({},fields))
	except: 
		print sys.exc_info()
		sys.exit(1)


if __name__ == "__main__":
	main()
