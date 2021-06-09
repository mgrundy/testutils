#!/usr/bin/python3
# Utility to read in a provided file of song okeys and see if they are in the
# sqlite database. Can also delete found songsr.
# Usage example:
# scripts/querysongs.py -f tskill.list -d slideshow/appServiceClient/Assets/AnimotoMobileIPhone_v2.0.sqlite

import sys, re
import optparse
import datetime
import time
import sqlite3


def main():
    delete_list = []
    query_list = []
    songs_deleted = 0

    options = parse_commandline()

    # create sqlite connection
    try:
        connection = sqlite3.connect(options.database)
    except sqlite3.Error as e:
        sys.stderr.write("Could not open database: %s" % e)
        sys.exit(1)

    if options.listsongs:
        count = list_songs(connection)
        print("Total songs found: ", count)
    else:
        query_list = read_okey_list(options.filename)
        delete_list = check_okeys(connection, query_list)

        if options.killsongs:
            songs_deleted = delete_songs(connection, delete_list)
            connection.commit()

        print("\nokeys checked:", len(query_list), " okeys found in db:", len(delete_list), " songs deleted:", songs_deleted)

    connection.close()

def read_okey_list(okeyfile):
    """
    Returns a list of string read in from provided file.

        Parameters:
            okeyfile (string): Path and filename of a file containing okey strings to read in.

        Returns:
            okey_list (list): List of strings read in from provided file.
    """
    okey_list = []
    for okey in open(okeyfile, 'r'):
        okey_list.append(okey.rstrip())
    return okey_list

def check_okeys(connection, okey_list):
    """
    Returns list of tuples containing okeys found in the ZGENERICSONG table.

        Parameters:
            connection (sqlite3.Connection): sqlite3 database connection instance
            okey_list (list): List of okey strings to search for

        Returns:
            found_list (list): of tuples with found okeys.
    """
    found_list = []
    # get a handle to the database
    cursor = connection.cursor()
    # open up list of okeys and lets go
    for okey in okey_list:
        try:
            cursor.execute('select ZANGENERICSONG.ZOKEY, '
                           'ZANGENERICSONG.ZTITLE, '
                           'ZANARTIST.ZNAME '
                           'from ZANGENERICSONG '
                           'Inner Join ZANARTIST on '
                           'ZANGENERICSONG.ZFKANLIBRARYSONGTOANARTIST=ZANARTIST.Z_PK '
                           'where ZANGENERICSONG.ZOKEY=?', (okey,))
            for result in cursor:
                print(result[0], "\t%-40s\t" % result[2], result[1])
                found_list.append(result[:1])
        except sqlite3.Error as e:
            print(sys.exc_info())
            print(e)
            sys.exit(1)
    cursor.close()
    return found_list


def list_songs(connection):
    """
    Returns total number of rows found in ZGENERICSONG table.
    Prints ZOKEY and ZTITLE fields for all rows in ZGENERICSONG table.

        Parameters:
            connection (sqlite3.Connection): sqlite3 database connection instance

        Returns:
            count (int): Total number of rows found in ZGENERICSONG table
    """
    # get a handle to the database
    cursor = connection.cursor()
    count = 0
    try:
            cursor.execute('select ZANGENERICSONG.ZOKEY, ' \
                                  'ZANGENERICSONG.ZTITLE, '\
                                  'ZANARTIST.ZNAME '       \
                           'from ZANGENERICSONG    '       \
                               'Inner Join ZANARTIST on ZANGENERICSONG.ZFKANLIBRARYSONGTOANARTIST=ZANARTIST.Z_PK ')

            for result in cursor:
                print(result[0], "\t%-40s\t" %  result[2], result[1])
                count += 1
    except sqlite3.Error as e:
        print(e)
        sys.exit(1)
    cursor.close()
    return count

# deletes okeys in list of tuples provided, returns deleted count
def delete_songs(connection, delete_list):
    """
    Returns total number of rows deleted from the ZGENERICSONG table.

        Parameters:
            connection (sqlite3.Connection): sqlite3 database connection instance
            delete_list (list): List of tuples containing the ZOKEY values to delete

        Returns:
            count (int): Total number of rows deleted from the ZGENERICSONG table
    """
    cursor = connection.cursor()
    try:
        cursor.executemany('delete from ZANGENERICSONG where ZOKEY=?', delete_list)
    except sqlite3.Error as e:
        sys.stderr.write("Could not complete operation: %s" % e)
        sys.exit(1)
    cursor.close()
    return cursor.rowcount

def parse_commandline():
    """
    Parses command line and returns options object.

        Returns:
            options (object): Object containing all of the program options set
            on the command line
    """
    parser = optparse.OptionParser(usage="""\
            %prog -d database -f filename [-r]
                            query songs database for okeys from file """)

    # add in command line options. Add mongo host/port combo later
    parser.add_option("-f", "--filename", dest="filename",
            help="name of file with list of okeys to query/delete",
            default=None)
    parser.add_option("-d", "--database", dest="database",
            help="path/filename of database",
            default=None)
    parser.add_option("-r", "--remove", action="store_true", dest="killsongs",
            help="delete found songs from database",
            default=False)
    parser.add_option("-l", "--list", action="store_true", dest="listsongs",
            help="delete found songs from database",
            default=False)
    (options, args) = parser.parse_args()

    if options.database is None:
        print("\nERROR: Must specify database filename \n")
        parser.print_help()
        sys.exit(-1)

    if options.filename is None and options.listsongs is False:
        print("\nERROR: Must specify name of file to with okeys to check\n")
        parser.print_help()
        sys.exit(-1)
    return options

if __name__ == "__main__":
    main()
