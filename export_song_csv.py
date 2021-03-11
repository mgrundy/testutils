#!/usr/bin/python

from __future__ import absolute_import
from __future__ import print_function
import csv
import itertools
import json
import sys
import optparse
import urllib.request


def main():
    parser = optparse.OptionParser(usage="""\
                %prog [url] [collection] [filename]
                import fukko""")

    # add in command line options. Add mongo host/port combo later
    parser.add_option("-f", "--fields", dest="fields",
                      help="names of fields to export",
                      default=None)
    parser.add_option("-o", "--filename", dest="fname",
                      help="name of file to import",
                      default=None)
    parser.add_option("-u", "--url", dest="url",
                      help="name of url",
                      default=None)
    (options, args) = parser.parse_args()

    if options.url is None:
        print("\nERROR: Must specify url \n")
        sys.exit(-1)

    if options.fname is None:
        print("\nERROR: Must specify name of file to import\n")
        sys.exit(-1)

    response = urllib.request.urlopen(options.url)

    data = json.loads(response.read())

    try:
        csvfile = open(options.fname, 'w')
        fieldList = "artist,asset_tags,genre,length,self,tags,title,mood,label,intent,tempo,instrumental,segment,popular".split(",")
        #fieldList = options.fields.split(",")
        print(fieldList)
        # create a dictionary of fieldname:1
        dbwriter = csv.DictWriter(csvfile, fieldList,
                                  delimiter=',', quotechar='"', 
                                  quoting=csv.QUOTE_NONNUMERIC)
        dbwriter.writeheader()
        for row in data["songs"]:
            for tagl in row["tags"]:
                tag = tagl["tag"]
                #print(tag["kind"])
                if tag["kind"] in row:
                    if tag["kind"] == "genre":
                        continue
                    #print(row[tag["kind"]])
                    #print("append", tag["kind"], tag["name"])
                    row[tag["kind"]].append(tag["name"])
                else:
                    #print("new", tag["kind"], tag["name"])
                    row[tag["kind"]] = [tag["name"]]
            del row["tags"]
            dbwriter.writerow(row)

    except: 
        print(sys.exc_info())
        sys.exit(1)


if __name__ == "__main__":
    main()
