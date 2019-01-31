import codecs
import json
import os
import pandas as pd
import re
import sqlite3
import spotipy

from audiobonsai import settings
from datetime import datetime, timedelta
from math import floor
from pathlib import Path
from pprint import pprint
from sqlite3 import Error as sqlError
from spotipy import util as sp_util
from urllib.request import urlopen


EVERYNOISE_URL = 'http://everynoise.com/spotify_new_releases.html'
CREATE_ALBUM_TABLE = """ CREATE TABLE IF NOT EXISTS albums (
                                spotify_uri text PRIMARY KEY,
                                add_date DATE,
                                json_text TEXT,
                                artists_extracted BOOLEAN default 0,
                                release_date DATE
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
GROUP_TEXT = 'spotify:album:.* .* albumid=(spotify:album:.*) nolink=true ' \
             + 'onclick="playmeta.*'
TODAY = datetime.now().strftime("%Y-%m-%d 00:00:00.000000")


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


def todays_dir():
    """
    Create the data dir for taday
    """
    log('Creating data dir')
    data_dir = Path('./data')
    if not data_dir.is_dir():
        os.mkdir(data_dir)

    today = datetime.now().strftime("%Y%m%d")
    today_dir = Path(os.path.join(data_dir, today))
    if not today_dir.is_dir():
        os.mkdir(today_dir)
    log('Data dir created')
    return today_dir


def download_everynoise(today_dir):
    """
    Get the current version of everynoise's release listing unless we already
    got it for the day in question

    Keyword arguments:
    today_dir -- path to the the directory for "today"
    """
    log('Retrieving everynoise')
    everynoise_file = Path(os.path.join(today_dir, 'everynoise.html'))
    if everynoise_file.exists():
        with codecs.open(everynoise_file, 'r', 'utf-8-sig') as f:
            log('Reading from disk')
            return f.read()
    else:
        log('Downloading everynoise')
        response = urlopen(EVERYNOISE_URL)
        log('Download complete')
        html = response.read().decode("utf-8")
        log('Decoded everynoise')
        with codecs.open(everynoise_file, 'w', 'utf-8-sig') as f:
            f.write(html)
        log('Everynoise written to disk')
        return html


def find_albums(html):
    """
    Parse the HTML and extract spotify uris for albums

    Keyword arguments:
    html -- the html text to parse
    """
    match_string = re.compile('(spotify:album:.*)')
    group_string = re.compile(GROUP_TEXT)
    candidate_list = set()
    log('Splitting HTML')
    releases = html.split('</div><div class=')
    log('Processing {:d} rows'.format(len(releases)))
    for release in releases:
        # print("Release: {}".format(release))
        for match in match_string.findall(release):
            # print("Match: {}".format(match))
            bits = group_string.match(match)
            if bits is None:
                continue
            spotify_uri = bits.group(1)
            candidate_list.add((spotify_uri, TODAY, ''))
            # print("Spotify URI: {}".format(spotify_uri))
    log("Found {:d} albums".format(len(candidate_list)))
    return candidate_list


def create_connection():
    """
    Create and/or connect to a sqlite database
    """
    log('Creating database')
    try:
        conn = sqlite3.connect(Path(os.path.join('./data', 'db.sqlite3')))
        log('Database created')
        return conn
    except sqlError as e:
        print(e)
        print(type(e))


def insert_albums(conn, album_list):
    insert_stmt = 'INSERT INTO albums (spotify_uri, add_date, json_text)' \
                  + ' VALUES(?,?,?)'
    try:
        log('Creating table')
        conn.execute(CREATE_ALBUM_TABLE)
        conn.execute(CREATE_ARTIST_TABLE)
        conn.execute(CREATE_ALBUM_ARTIST_TABLE)
        #conn.execute(CREATE_POP_FOLL_TABLE)
        log('Loading albums')
        for album in album_list:
            try:
                conn.execute(insert_stmt, album)
            except sqlite3.IntegrityError:
                # Ignore duplicates
                pass
        conn.commit()
        log('Albums inserted')
    except Exception as e:
        print(e)
        print(type(e))
        dir(e)


def get_album_json(db_conn, sp_conn):
    select_stmt = 'SELECT spotify_uri from albums where json_text = ""'
    update_stmt = 'UPDATE albums set json_text = ? where spotify_uri = ?'
    log('Retrieving albums to update')
    try:
        db_cursor = db_conn.cursor()
        db_cursor.execute(select_stmt)
        albums = db_cursor.fetchall()
    except Exception as e:
        print(e)
        print(type(e))

    offset = 0
    batch_size = 20
    update_list = set()
    log('Requesting JSON for {:d} albums'.format(len(albums)))
    while offset < len(albums):
        sp_uri_list = [album[0] for album in
                       albums[offset:offset + batch_size]]
        try:
            album_dets_list = sp_conn.albums(sp_uri_list)
            for album_dets in album_dets_list[u'albums']:
                try:
                    update_list.add((json.dumps(album_dets),
                                     album_dets[u'uri']))
                except TypeError as te:
                    pass
        except Exception as e:
            print(e)
            print(type(e))
        if offset > 0 and offset % 1000 == 0:
            log('-> {} albums retrieved'.format(offset))
        offset += batch_size
        try:
            db_conn.executemany(update_stmt, update_list)
            db_conn.commit()
            update_list = set()
        except Exception as e:
            print(e)
            print(type(e))
    log('Album JSON updated in database')
    log('Album JSON retrieved')


def extract_artists(db_conn, sp_conn):
    select_stmt = 'SELECT spotify_uri, json_text from albums ' \
                  + 'where artists_extracted = 0 and json_text is not ""'
    update_stmt = 'UPDATE albums set artists_extracted = 1, ' \
                  + 'release_date = ? where spotify_uri = ?'
    insert_artist_stmt = 'INSERT INTO artists (spotify_uri, add_date)' \
                         + ' VALUES(?, ?)'
    insert_album_artists_stmt = 'INSERT INTO album_artists (artist_uri, ' \
                                + 'album_uri) VALUES(?, ?)'
    log('Retrieving albums to extract artists from')
    try:
        db_cursor = db_conn.cursor()
        db_cursor.execute(select_stmt)
        albums = db_cursor.fetchall()
    except Exception as e:
        print(e)
        print(type(e))

    artists = set()
    all_album_artists = set()
    update_albums = set()
    for album in albums:
        try:
            album_artists = set()
            album_json = json.loads(album[1])
            album_uri = album[0]
            release_date = album_json[u'release_date']
            release_date_precision = album_json[u'release_date_precision']
            formatted_release_date = None
            if release_date_precision == 'year':
                formatted_release_date = datetime.strptime(release_date, '%Y')
            elif release_date_precision == 'month':
                formatted_release_date = datetime.strptime(release_date,
                                                           '%Y-%m')
            elif release_date_precision == 'day':
                formatted_release_date = datetime.strptime(release_date,
                                                           '%Y-%m-%d')
            update_albums.add((formatted_release_date, album_uri))
            for artist in album_json[u'artists']:
                album_artists.add((artist[u'uri']))
            for track in album_json['tracks'][u'items']:
                for artist in track[u'artists']:
                    album_artists.add((artist[u'uri']))
            for artist in album_artists:
                all_album_artists.add((artist, album_uri))
                artists.add((artist, TODAY))
        except Exception as e:
            pprint(album)
            print(e)
            print(type(e))
            raise(e)
    try:
        log('Loading artists')
        for artist in artists:
            try:
                db_conn.execute(insert_artist_stmt, artist)
            except sqlite3.IntegrityError:
                # Ignore duplicates
                pass
        log('Artists inserted')
        log('Loading album<->artists')
        for album_artist in all_album_artists:
            try:
                db_conn.execute(insert_album_artists_stmt, album_artist)
            except sqlite3.IntegrityError:
                # Ignore duplicates
                pass
        log('Album<->artists inserted')
        db_conn.executemany(update_stmt, update_albums)
        db_conn.commit()
        log('Number of artists: {:d}'.format(len(artists)))
        log('Number of album-artist pairings: {:d}'.format(
            len(all_album_artists)))
    except Exception as e:
        print(e)
        print(type(e))
        raise(e)


def get_artist_json(db_conn, sp_conn):
    today_name = datetime.now().strftime("%Y%m%d")
    select_stmt = 'SELECT spotify_uri from artists where last_json_date ' \
                  + 'is not "' + TODAY + '"'
    update_stmt = 'UPDATE artists set json_text = ?, last_json_date = ?, ' \
                  + ' current_pop = ?, current_foll = ? where spotify_uri = ?'
    create_pop_foll = 'CREATE TABLE IF NOT EXISTS pop_foll_' + today_name \
                      + ' ( artist_uri TEXT, foll_' + today_name \
                      + ' INTEGER, pop_' + today_name + ' INTEGER, ' \
                      + 'FOREIGN KEY (artist_uri) ' \
                      + '  REFERENCES artist(spotify_uri) ON DELETE CASCADE ' \
                      + 'PRIMARY KEY (artist_uri))'
    insert_pop_foll = 'INSERT INTO pop_foll_' + today_name + ' (artist_uri,' \
                      + ' foll_' + today_name + ', pop_' + today_name \
                      + ') VALUES(?, ?, ?)'
    log('Retrieving albums to update')
    try:
        db_conn.execute(create_pop_foll)
        db_conn.commit()
        db_cursor = db_conn.cursor()
        db_cursor.execute(select_stmt)
        artists = db_cursor.fetchall()
    except Exception as e:
        print(e)
        print(type(e))

    offset = 0
    batch_size = 50
    update_list = set()
    insert_pop_foll_list = set()
    log('Requesting JSON for {:d} artists'.format(len(artists)))
    while offset < len(artists):
        sp_uri_list = [artist[0] for artist in
                       artists[offset:offset + batch_size]]
        try:
            artist_dets_list = sp_conn.artists(sp_uri_list)
            for artist_dets in artist_dets_list[u'artists']:
                try:
                    uri = artist_dets[u'uri']
                    followers = artist_dets[u'followers'][u'total']
                    popularity = artist_dets[u'popularity']
                    update_list.add((json.dumps(artist_dets), TODAY,
                                     popularity, followers, uri))
                    insert_pop_foll_list.add((uri, followers,
                                              popularity))
                except TypeError as te:
                    print(te)
                    print(type(te))
                    raise(te)
                    pass
        except Exception as e:
            print(e)
            print(type(e))
        if offset > 0 and offset % 1000 == 0:
            log('-> {} artists retrieved'.format(offset))
            try:
                db_conn.executemany(update_stmt, update_list)
                for pop_foll_entry in insert_pop_foll_list:
                    try:
                        db_conn.execute(insert_pop_foll, pop_foll_entry)
                    except sqlite3.IntegrityError:
                        # Ignore duplicates
                        pass
                db_conn.commit()
                update_list = set()
            except Exception as e:
                print(e)
                print(type(e))
        offset += batch_size
    log('Artist JSON updated in database')
    log('Artist JSON retrieved')


def attr_score(val, factor):
    return (val//factor)**2


def stat_score(df, in_col, out_col):
    in_min = df[in_col].min()
    in_max = df[in_col].max()
    in_col_temp = in_col + "_temp"
    df.loc[:, in_col_temp] = df[in_col].apply(lambda x: x - in_min)
    factor = (in_max - in_min) // 25
    df.loc[:, out_col] = df[in_col_temp].apply(lambda x: attr_score(x, factor))
    return df


def set_category(prev_pop):
    if prev_pop == 0:
        return 0
    elif prev_pop > 0 and prev_pop <= 5:
        return 1
    elif prev_pop > 5 and prev_pop <= 15:
        return 2
    elif prev_pop > 15 and prev_pop <= 30:
        return 3
    elif prev_pop > 30 and prev_pop <= 45:
        return 4
    elif prev_pop > 45 and prev_pop <= 60:
        return 5
    else:
        return 6


def select_top_tracks(db_conn, table_name, previous_date, num_tracks=100):
    today_pop = 'pop_{}'.format(datetime.now().strftime("%Y%m%d"))
    today_foll = 'foll_{}'.format(datetime.now().strftime("%Y%m%d"))
    prev_pop = 'pop_{}'.format(previous_date)
    prev_foll = 'foll_{}'.format(previous_date)
    df = pd.read_sql('SELECT * from {}'.format(table_name), db_conn)
    df['category'] = df[prev_pop].apply(lambda x: set_category(x))
    df[today_pop] = df[today_pop]
    df[prev_pop] = df[prev_pop]
    df[today_foll] = df[today_foll]
    df[prev_pop] = df[prev_pop]
    df['pop_diff'] = df[today_pop] - df[prev_pop]
    # df['pop_diff_pct'] = (df['pop_diff']/df[prev_pop])*100
    # df['pop_diff_pct'] = df['pop_diff_pct'].apply(lambda x: min(100, x))
    # df = stat_score(df, 'pop_diff_pct', 'pop_diff_score')
    df['foll_diff'] = df[today_foll] - df[prev_foll]
    # df['foll_diff_pct'] = (df['foll_diff']/df[prev_foll])*100
    # df['foll_diff_pct'] = df['foll_diff_pct'].apply(lambda x: min(100, x))
    # df = stat_score(df, 'foll_diff_pct', 'foll_diff_score')
    df['final_score'] = df['pop_diff'] + df['foll_diff']
    # df['category'] = pd.cut(df[prev_pop], 25)
    df = df.sort_values(by='final_score', ascending=False)

    categories = df['category'].unique()
    category_num = 1
    artist_uris = set()
    for category in sorted(categories):
        category_df = df[df['category'] == category]
        num_albums = 5
        if category == 3:
            num_albums = 10
        elif category == 4 or category == 5:
            num_albums = 15
        category_df = category_df.head(num_albums)
        print(category_df.loc[:, ['artist_uri', 'category', prev_pop,
                                  prev_foll, 'foll_diff', 'pop_diff',
                                  'final_score']])
        artist_uris.update(category_df['artist_uri'].tolist())
        category_num += 1
    return artist_uris


def pop_change_tables(db_conn, sp_conn):
    playlist = 'spotify:user:audiobonsai:playlist:5CmD30dzQjCujR4CAnL8qc'
    today_table_name = 'pop_foll_' + datetime.now().strftime("%Y%m%d")
    yesterday_date = datetime.now() - timedelta(days=1)
    yesterday_table = 'pop_foll_{}'.format(yesterday_date.strftime("%Y%m%d"))
    weekago_date = datetime.now() - timedelta(days=7)
    weekago_table = 'pop_foll_{}'.format(weekago_date.strftime("%Y%m%d"))
    monthago_date = datetime.now() - timedelta(days=30)
    monthago_table = 'pop_foll_{}'.format(monthago_date.strftime("%Y%m%d"))
    get_album_from_artist = 'SELECT albums.json_text FROM album_artists ' \
                            + 'INNER JOIN albums ON album_artists.album_uri ' \
                            + '= albums.spotify_uri WHERE ' \
                            + 'album_artists.artist_uri = "{}" ' \
                            + 'ORDER BY albums.add_date DESC LIMIT 1'
    get_album_artists = 'SELECT albums.spotify_uri, albums.add_date FROM ' \
                        + 'album_artists INNER JOIN albums ON ' \
                        + 'album_artists.album_uri = albums.spotify_uri ' \
                        + 'WHERE album_artists.artist_uri = "{}" ' \
                        + 'ORDER BY albums.add_date DESC'

    drop_yesterday_table = 'DROP TABLE IF EXISTS yesterday_diff'
    create_yesterday_table = 'create table yesterday_diff as select * FROM ' \
                             + yesterday_table + ' INNER JOIN ' \
                             + today_table_name + ' as today ON ' \
                             + yesterday_table + '.artist_uri = ' \
                             + 'today.artist_uri'
    drop_weekago_table = 'DROP TABLE IF EXISTS weekago_diff'
    create_weekago_table = 'create table weekago_diff as select * FROM ' \
                           + weekago_table + ' INNER JOIN ' \
                           + today_table_name + ' as today ON ' \
                           + weekago_table + '.artist_uri = ' \
                           + 'today.artist_uri'
    drop_monthago_table = 'DROP TABLE IF EXISTS monthago_diff'
    create_monthago_table = 'create table monthago_diff as select * FROM ' \
                            + monthago_table + ' INNER JOIN ' \
                            + today_table_name + ' as today ON ' \
                            + monthago_table + '.artist_uri = ' \
                            + 'today.artist_uri'
    print(create_yesterday_table)
    try:
        log('Creating yesterday diff join')
        db_conn.execute(drop_yesterday_table)
        db_conn.commit()
        db_conn.execute(create_yesterday_table)
        db_conn.commit()
        ystdy_artists = select_top_tracks(db_conn, 'yesterday_diff',
                                          yesterday_date.strftime("%Y%m%d"),
                                          50)
        top_tracks = set()
        for artist_uri in ystdy_artists:
            db_cursor = db_conn.cursor()
            db_cursor.execute(get_album_artists.format(artist_uri))
            # print('ARIST_URI: {}'.format(artist_uri))
            # print(db_cursor.fetchall())
            db_cursor.execute(get_album_from_artist.format(artist_uri))
            result = db_cursor.fetchone()
            if result is None:
                log('{} ARTIST URI NOT FOUND IN DB!'.format(artist_uri))
                continue
            album_json = json.loads(result[0])
            album_tracks = album_json[u'tracks']
            durations = list()
            for track in album_tracks[u'items']:
                durations.append(track[u'duration_ms'])
            sorted_durations = sorted(durations)
            median_duration = sorted_durations[floor(len(durations)/2)]
            track_diffs = {}
            track_durations = {}

            for track in album_tracks[u'items']:
                for artist in track[u'artists']:
                    if artist_uri == artist[u'uri']:
                        track_diffs[abs(track[u'duration_ms'] -
                                    median_duration)] = track[u'uri']
                        track_durations[track[u'uri']] = track[u'duration_ms']
                if len(track_diffs.keys()) == 3:
                    break
            if len(track_diffs.keys()) > 0:
                track_uri = track_diffs[sorted(track_diffs.keys())[0]]
                top_tracks.add(track_uri)
                # log('{}: {} ({}) - {} ({})'.format(artist_uri,
                #                                    album_json[u'uri'],
                #                                    median_duration, track_uri,
                #                                    track_durations[track_uri]))
        sp_conn.user_playlist_replace_tracks(settings.SPOTIFY_USERNAME,
                                             playlist, top_tracks)
        log('Creating week ago diff join')
        db_conn.execute(drop_weekago_table)
        db_conn.commit()
        db_conn.execute(create_weekago_table)
        db_conn.commit()
        # log('Creating month ago diff join')
        # db_conn.execute(drop_monthago_table)
        # db_conn.commit()
        # db_conn.execute(create_monthago_table)
        # db_conn.commit()
    except Exception as e:
        print(e)
        print(type(e))
        raise(e)


if __name__ == '__main__':
    today_dir = todays_dir()
    # Get sorting hat and scrape album uris
    try:
        html = download_everynoise(today_dir)
        albums = find_albums(html)
    except Exception as e:
        print(e)
        print(type(e))
        raise(e)

    db_conn = create_connection()
    # Load albums into database
    try:
        cursor = db_conn.cursor()
        insert_albums(db_conn, albums)
    except Exception as e:
        print(e)
        print(type(e))
        raise(e)

    try:
        sp_conn = get_spotify_conn()
        get_album_json(db_conn, sp_conn)
    except Exception as e:
        print(e)
        print(type(e))
        raise(e)

    try:
        sp_conn = get_spotify_conn()
        extract_artists(db_conn, sp_conn)
    except Exception as e:
        print(e)
        print(type(e))
        raise(e)

    try:
        sp_conn = get_spotify_conn()
        get_artist_json(db_conn, sp_conn)
    except Exception as e:
        print(e)
        print(type(e))
        raise(e)

    try:
        update_orig_pop_foll = 'UPDATE artists SET orig_pop = current_pop, ' \
                               + 'orig_foll = current_foll ' \
                               + 'where orig_pop is NULL'
        db_conn.execute(update_orig_pop_foll)
        db_conn.commit()
    except Exception as e:
        print(e)
        print(type(e))
        raise(e)

    try:
        sp_conn = get_spotify_conn()
        pop_change_tables(db_conn, sp_conn)
    except Exception as e:
        print(e)
        print(type(e))
        raise(e)

    db_conn.close()
