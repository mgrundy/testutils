import unittest
import querysongs
import sqlite3



class SimpleTestCase(unittest.TestCase):

    song_table = """create table ZANGENERICSONG
        (
            Z_PK		        integer primary key,
            Z_ENT		        integer,
            Z_OPT		        integer,
            ZLENGTH		        integer,
            ZRANK		        integer,
            ZFKANLIBRARYSONGTOANALBUM   integer,
            ZFKANLIBRARYSONGTOANARTIST  integer,
            ZFKANLIBRARYSONGTOANGENRE   integer,
            ZTITLE		        varchar,
            ZOKEY		        varchar,
            ZVIDEOURL		        varchar,
            ZALBUM		        varchar,
            ZARTIST		        varchar,
            ZBEATTRACKURL		varchar,
            ZLOCALFILEURL		varchar,
            ZLOCALORIGINURL		varchar,
            ZREMOTEASSETURL		varchar
        )"""
    artist_table = """create table ZANARTIST
        (
            Z_PK	integer	primary	key,
            Z_ENT	integer,
            Z_OPT	integer,
            ZNAME	varchar
        ); """
    song_data = [ (3904, 4, 1, 186, 0, None, 945, 23, 'The Slow Life', '8QJklrTz9Lsi0v7y0qWqdw', None, None, None, None, None, None, None),
                  (3905, 4, 1, 205, 0, None, 1263, 34, 'Fools In Love', 'Vl5UJnMfE2iFddr4J0a8sQ', None, None, None, None, None, None, None),
                  (3906, 4, 1, 148, 0, None, 1193, 23, 'We Go Together', 'o70U8HvcbpXcDc1gMI6mwg', None, None, None, None, None, None, None),
                  (3907, 4, 2, 310, 0, None, 1262, 24, 'The Silence', 'Csbii7O01ngvc4hSb4fHDA', None, None, None, None, None, None, None) ]
    artist_data = [ (945, 2, 8, 'Chris Pierce'),
                    (1263, 2, 1, 'Nathan Angelo'),
                    (1193, 2, 3, 'Bamtone'),
                    (1262, 2, 1, 'Silent') ]
    okey_list = [ '8QJklrTz9Lsi0v7y0qWqdw',
                  'Vl5UJnMfE2iFddr4J0a8sQ',
                  'o70U8HvcbpXcDc1gMI6mwg',
                  'Csbii7O01ngvc4hSb4fHDA' ]
    tupl_list = [ ('8QJklrTz9Lsi0v7y0qWqdw',),
                  ('Vl5UJnMfE2iFddr4J0a8sQ',),
                  ('o70U8HvcbpXcDc1gMI6mwg',),
                  ('Csbii7O01ngvc4hSb4fHDA',) ]

    def setUp(self):
        """Call before every test case."""
        self.connection = sqlite3.connect(':memory:')
        cursor = self.connection.cursor()

        cursor.execute(self.song_table)
        cursor.execute(self.artist_table)

        cursor.executemany('insert into ZANGENERICSONG values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', self.song_data)
        cursor.executemany('insert into ZANARTIST values(?, ?, ?, ?)', self.artist_data)

        self.connection.commit()
        cursor.close()

    def tearDown(self):
        """Call after every test case."""
        self.connection.close()

    def testList(self):
        """Test case A. Check that list_songs() returns the right count of songs in table'"""
        assert querysongs.list_songs(self.connection) == len(self.song_data), "list_songs() not counting songs correctly"

    def testCheck(self):
        """Test case B, check that check_okey returns the list of matching okeys"""
        assert querysongs.check_okeys(self.connection, self.okey_list) == self.tupl_list

    def testDelete(self):
        """Test case C, check that delete_songs deletes the right number of songs and they are removed from the database"""
        assert querysongs.delete_songs(self.connection, self.tupl_list) == len(self.tupl_list)
        assert querysongs.check_okeys(self.connection, self.okey_list) == []

    def testError(self):
        """Test case D, check that check_okey fails gracefully on bad connection"""
        self.connection.close()
        with self.assertRaises(sqlite3.ProgrammingError):
            querysongs.check_okeys(self.connection, self.okey_list)

if __name__ == "__main__":
    unittest.main() # run all tests
