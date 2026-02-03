import sqlite3
import logging
from datetime import datetime
class HashtagDB :
    def __init__ (self ,db_name ="hashtags.db"):
        self .db_name =db_name
        self .init_db ()
    def init_db (self ):
        try :
            with sqlite3 .connect (self .db_name )as conn :
                cursor =conn .cursor ()
                cursor .execute ("""
                    CREATE TABLE IF NOT EXISTS hashtags (
                        hashtag TEXT PRIMARY KEY,
                        max_id TEXT,
                        rank_token TEXT,
                        last_updated TIMESTAMP
                    )
                """)
                conn .commit ()
                logging .info ("Database initialized.")
        except Exception as e :
            logging .error (f"DB Init Error: {e }")
    def get_state (self ,hashtag ):
        try :
            with sqlite3 .connect (self .db_name )as conn :
                cursor =conn .cursor ()
                cursor .execute ("SELECT max_id, rank_token FROM hashtags WHERE hashtag = ?",(hashtag ,))
                row =cursor .fetchone ()
                if row :
                    return {"max_id":row [0 ],"rank_token":row [1 ]}
                return None
        except Exception as e :
            logging .error (f"DB Read Error: {e }")
            return None
    def save_state (self ,hashtag ,max_id ,rank_token ):
        try :
            with sqlite3 .connect (self .db_name )as conn :
                cursor =conn .cursor ()
                cursor .execute ("""
                    INSERT INTO hashtags (hashtag, max_id, rank_token, last_updated)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(hashtag) DO UPDATE SET
                        max_id=excluded.max_id,
                        rank_token=excluded.rank_token,
                        last_updated=excluded.last_updated
                """,(hashtag ,max_id ,rank_token ,datetime .now ()))
                conn .commit ()
        except Exception as e :
            logging .error (f"DB Save Error: {e }")
