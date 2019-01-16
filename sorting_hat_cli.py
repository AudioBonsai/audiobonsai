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
from urllib.request import urlopen


EVERYNOISE_URL = 'http://everynoise.com/spotify_new_releases.html'
CREATE_CANDIDATE_TABLE = """ CREATE TABLE IF NOT EXISTS candidates (
                                spotify_uri text PRIMARY KEY,
                                add_date DATE,
                                json_text TEXT
                             ) """
GROUP_TEXT = 'spotify:album:.* .* albumid=(spotify:album:.*) nolink=true ' \
             + 'onclick="playmeta.*'


def todays_dir():
    print('{}: Creating data dir'.format(datetime.now().strftime("%H:%M:%S")))
    data_dir = Path('./data')
    if not data_dir.is_dir():
        os.mkdir(data_dir)

    today = datetime.now().strftime("%Y%m%d")
    today_dir = Path(os.path.join(data_dir, today))
    if not today_dir.is_dir():
        os.mkdir(today_dir)
    print('{}: Data dir created'.format(datetime.now().strftime("%H:%M:%S")))
    return today_dir


def download_everynoise(today_dir):
    print('{}: Retrieving everynoise'.format(
        datetime.now().strftime("%H:%M:%S")))
    everynoise_file = Path(os.path.join(today_dir, 'everynoise.html'))
    if everynoise_file.exists():
        with codecs.open(everynoise_file, 'r', 'utf-8-sig') as f:
            print('{}: Reading from disk'.format(
                datetime.now().strftime("%H:%M:%S")))
            return f.read()
    else:
        print('{}: Downloading everynoise'.format(
            datetime.now().strftime("%H:%M:%S")))
        response = urlopen(EVERYNOISE_URL)
        print('{}: Download complete'.format(
            datetime.now().strftime("%H:%M:%S")))
        html = response.read().decode("utf-8")
        print('{}: Decoded everynoise'.format(
            datetime.now().strftime("%H:%M:%S")))
        with codecs.open(everynoise_file, 'w', 'utf-8-sig') as f:
            f.write(html)
        print('{}: Everynoise written to disk'.format(
            datetime.now().strftime("%H:%M:%S")))
        return html


def find_candidates(html):
    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    print(today)
    match_string = re.compile('(spotify:album:.*)')
    group_string = re.compile(GROUP_TEXT)
    candidate_list = set()
    print('{}: Splitting HTML'.format(datetime.now().strftime("%H:%M:%S")))
    releases = html.split('</div><div class=')
    print('{}: Processing {:d} rows'.format(
      datetime.now().strftime("%H:%M:%S"), len(releases)))
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
    print("{}: Found {:d} candidates".format(
      datetime.now().strftime("%H:%M:%S"), len(candidate_list)))
    return candidate_list


def create_connection(today_dir):
    print('{}: Creating database'.format(datetime.now().strftime("%H:%M:%S")))
    try:
        conn = sqlite3.connect(Path(os.path.join(today_dir, 'db.sqlite3')))
        print('{}: Database created'.format(
          datetime.now().strftime("%H:%M:%S")))
        return conn
    except sqlError as e:
        print(e)


def insert_candidates(conn, candidate_list):
    insert_statement = 'INSERT INTO candidates VALUES(?,?,?)'
    try:
        print('{}: Creating table'.format(
          datetime.now().strftime("%H:%M:%S")))
        conn.execute(CREATE_CANDIDATE_TABLE)
        print('{}: Loading candidates'.format(
          datetime.now().strftime("%H:%M:%S")))
        conn.executemany(insert_statement, candidate_list)
        conn.commit()
        print('{}: Candidates inserted'.format(
          datetime.now().strftime("%H:%M:%S")))
    except Exception as e:
        print(e)
        dir(e)


if __name__ == '__main__':
    token = spotipy.util.prompt_for_user_token(
      settings.SPOTIFY_USERNAME, settings.SPOTIFY_SCOPE,
      client_id=settings.SPOTIPY_CLIENT_ID,
      client_secret=settings.SPOTIPY_CLIENT_SECRET,
      redirect_uri=settings.SPOTIPY_REDIRECT_URI)
    sp = spotipy.Spotify(auth=token)
    
    today_dir = todays_dir()
    html = download_everynoise(today_dir)
    candidates = find_candidates(html)
    db_conn = create_connection(today_dir)
    try:
        cursor = db_conn.cursor()
        insert_candidates(db_conn, candidates)
    except Exception as e:
        print(e)
    finally:
        db_conn.close()
    db_conn.close()
