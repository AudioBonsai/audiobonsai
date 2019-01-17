import codecs
import os
import re
import sqlite3
import spotipy

from audiobonsai import settings
from datetime import datetime
from pathlib import Path
from pprint import pprint
from sqlite3 import Error as sqlError
from spotipy import util as sp_util
from urllib.request import urlopen


EVERYNOISE_URL = 'http://everynoise.com/spotify_new_releases.html'
CREATE_CANDIDATE_TABLE = """ CREATE TABLE IF NOT EXISTS candidates (
                                spotify_uri text PRIMARY KEY,
                                add_date DATE,
                                json_text TEXT
                             ) """
GROUP_TEXT = 'spotify:album:.* .* albumid=(spotify:album:.*) nolink=true ' \
             + 'onclick="playmeta.*'


def log(descriptor):
    print('{}: {}'.format(datetime.now().strftime("%H:%M:%S"), descriptor))


def get_spotify_conn():
    token = sp_util.prompt_for_user_token(
      settings.SPOTIFY_USERNAME, settings.SPOTIFY_SCOPE,
      client_id=settings.SPOTIPY_CLIENT_ID,
      client_secret=settings.SPOTIPY_CLIENT_SECRET,
      redirect_uri=settings.SPOTIPY_REDIRECT_URI)
    return spotipy.Spotify(auth=token)


def todays_dir():
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


def find_candidates(html):
    today = datetime.now().strftime("%Y-%m-%d 00:00:00.000000")
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
            candidate_list.add((spotify_uri, today, ''))
            # print("Spotify URI: {}".format(spotify_uri))
    log("Found {:d} candidates".format(len(candidate_list)))
    return candidate_list


def create_connection(today_dir):
    log('Creating database')
    try:
        conn = sqlite3.connect(Path(os.path.join('./data', 'db.sqlite3')))
        log('Database created')
        return conn
    except sqlError as e:
        print(e)


def insert_candidates(conn, candidate_list):
    insert_stmt = 'INSERT INTO candidates VALUES(?,?,?)'
    try:
        log('Creating table')
        conn.execute(CREATE_CANDIDATE_TABLE)
        log('Loading candidates')
        for candidate in candidate_list:
            try:
                conn.execute(insert_stmt, candidate)
            except sqlite3.IntegrityError:
                # Ignore duplicates
                pass
        conn.commit()
        log('Candidates inserted')
    except Exception as e:
        print(e)
        dir(e)


def get_candidate_json(db_conn, sp_conn):
    select_stmt = 'SELECT spotify_uri from candidates where json_text = ""'
    log('Retrieving album JSON')
    try:
        db_cursor = db_conn.cursor()
        db_cursor.execute(select_stmt)
        albums = db_cursor.fetchall()
    except Exception as e:
        print(e)

    offset = 0
    batch_size = 20
    while offset < len(albums):
        sp_uri_list = [album[0] for album in
                       albums[offset:offset + batch_size]]
        try:
            album_dets_list = sp_conn.albums(sp_uri_list)
            pprint(album_dets_list[u'albums'][0])
        except Exception as e:
            print(e)
        return
        if offset > 0 and offset % 1000 == 0:
            log('-> {} albums retrieved'.format(offset))
        offset += batch_size
    log('Album JSON retrieved')


if __name__ == '__main__':
    today_dir = todays_dir()
    # Get sorting hat and scrape album uris
    try:
        html = download_everynoise(today_dir)
        candidates = find_candidates(html)
    except Exception as e:
        print(e)
        raise(e)

    db_conn = create_connection(today_dir)
    # Load albums into database
    try:
        cursor = db_conn.cursor()
        insert_candidates(db_conn, candidates)
    except Exception as e:
        print(e)
        raise(e)

    try:
        sp_conn = get_spotify_conn()
        get_candidate_json(db_conn, sp_conn)
    except Exception as e:
        print(e)
        raise(e)

    db_conn.close()
