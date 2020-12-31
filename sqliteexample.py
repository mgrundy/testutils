#!/usr/bin/python3

import sys, re
import optparse
import datetime
import time
import sqlite3


def main():
    okey_total = 0
    deleted_songs = 0
    okey_found = 0
    delete_list = []

    options = parse_commandline()

    # create sqlite connection
    try:
        connection = sqlite3.connect(options.database)
    except sqlite3.Error as e:
        sys.stderr.write("Could not open database: %s" % e)
        sys.exit(1)

    # get a handle to the database
    cursor = connection.cursor()

    # open up list of okeys and lets go
    for okey in open(options.fname, 'r'):

        try:
            cursor.execute('select ZOKEY, ZTITLE from ZANGENERICSONG where ZOKEY=?', (okey.rstrip(),))
            for result in cursor:
                okey_found += 1
                (song_okey, song_name) = result
                print(song_okey, song_name)
                delete_list.append( (song_okey,) )
            okey_total += 1
        except ValueError as e:
            print(sys.exc_info())
            print(e)
            sys.exit(1)

    if options.killsongs:
        try:
            cursor.executemany('delete from ZANGENERICSONG where ZOKEY=?', delete_list)
            deleted_songs = cursor.rowcount
        except sqlite3.Error as e:
            sys.stderr.write("Could not complete operation: %s" % e)
            sys.exit(1)

    print("\nokeys checked:", okey_total, " okeys found in db:", okey_found, " songs deleted:", deleted_songs)
    connection.close()


def parse_commandline():
    parser = optparse.OptionParser(usage="""\
            %prog [database] [filename]
                            query songs database for okeys from file """)

    # add in command line options. Add mongo host/port combo later
    parser.add_option("-f", "--filename", dest="fname",
            help="name of file with list of okeys to query/delete",
            default=None)
    parser.add_option("-d", "--database", dest="database",
            help="path/filename of database",
            default=None)
    parser.add_option("-r", "--remove", action="store_true", dest="killsongs",
            help="delete found songs from database",
            default=False)
    (options, args) = parser.parse_args()

    if options.database is None:
        print("\nERROR: Must specify database filename \n")
        sys.exit(-1)

    if options.fname is None:
        print("\nERROR: Must specify name of file to import\n")
        sys.exit(-1)
    return options

if __name__ == "__main__":
    main()
