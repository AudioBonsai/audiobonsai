import os
import spotipy
import sqlite3

from audiobonsai import settings
from datetime import datetime
from pathlib import Path
from sqlite3 import Error as sqlError
from spotipy import util as sp_util


CREATE_ALBUM_TABLE = """ CREATE TABLE IF NOT EXISTS albums (
                                spotify_uri text PRIMARY KEY,
                                add_date DATE,
                                json_text TEXT,
                                artists_extracted BOOLEAN default 0,
                                release_date DATE,
                                trade_rec BOOLEAN default 0,
                                curator_rec BOOLEAN default 0,
                                daily_appearances INTEGER default 0,
                                weekly_appearances INTEGER default 0
                             ) """
CREATE_ARTIST_TABLE = """ CREATE TABLE IF NOT EXISTS artists (
                                spotify_uri text PRIMARY KEY,
                                add_date DATE,
                                json_text TEXT,
                                last_json_date DATE,
                                orig_foll INTEGER,
                                current_foll INTEGER,
                                daily_foll_change INTEGER,
                                orig_pop INTEGER,
                                current_pop INTEGER,
                                daily_pop_change INTEGER
                            ) """
CREATE_ALBUM_ARTIST_TABLE = """ CREATE TABLE IF NOT EXISTS album_artists (
                                album_uri text,
                                artist_uri text,
                                FOREIGN KEY (album_uri)
                                    REFERENCES album(spotify_uri)
                                    ON DELETE CASCADE,
                                FOREIGN KEY (artist_uri)
                                    REFERENCES artist(spotify_uri)
                                    ON DELETE CASCADE
                                PRIMARY KEY (album_uri, artist_uri)
                            ) """
CREATE_POP_FOLL_TABLE = """ CREATE TABLE IF NOT EXISTS pop_foll (
                            artist_uri TEXT,
                            sample_date DATE,
                            followers INTEGER,
                            popularity INTEGER,
                            FOREIGN KEY (artist_uri)
                                REFERENCES artist(spotify_uri)
                                ON DELETE CASCADE
                            PRIMARY KEY (artist_uri, sample_date)
                        )"""
CREATE_DAILY_LOG_TABLE = """ CREATE TABLE IF NOT EXISTS daily_log (
                             album_uri TEXT,
                             daily_list DATE,
                             PRIMARY KEY (album_uri, daily_list)
                         )"""
CREATE_WEEKLY_LOG_TABLE = """ CREATE TABLE IF NOT EXISTS weekly_log (
                              album_uri TEXT,
                              weekly_list DATE,
                              PRIMARY KEY (album_uri, weekly_list)
                          )"""


def log(descriptor):
    """
    Yes... I should use a standard logging library, but... here we are.

    Keyword arguments:
    descriptor -- the description of the event being logged
    """
    print('{}: {}'.format(datetime.now().strftime("%H:%M:%S"), descriptor))


def get_spotify_conn():
    """
    Use the spotipy utility for command line Spotify oauth All values
    assumed stored in the settings for now... should paramaterize them
    """
    token = sp_util.prompt_for_user_token(
      settings.SPOTIFY_USERNAME, settings.SPOTIFY_SCOPE,
      client_id=settings.SPOTIPY_CLIENT_ID,
      client_secret=settings.SPOTIPY_CLIENT_SECRET,
      redirect_uri=settings.SPOTIPY_REDIRECT_URI)
    return spotipy.Spotify(auth=token)


def create_connection():
    """
    Create and/or connect to a sqlite database
    """
    log('Creating database')
    try:
        conn = sqlite3.connect(Path(os.path.join('./data', 'db.sqlite3')))
        log('Creating album table')
        conn.execute(CREATE_ALBUM_TABLE)
        log('Creating artist table')
        conn.execute(CREATE_ARTIST_TABLE)
        log('Creating album_artist table')
        conn.execute(CREATE_ALBUM_ARTIST_TABLE)
        log('Creating daily_log table')
        conn.execute(CREATE_DAILY_LOG_TABLE)
        log('Creating weekly_log table')
        conn.execute(CREATE_WEEKLY_LOG_TABLE)
        log('Database created')
        return conn
    except sqlError as e:
        print(e)
        print(type(e))
