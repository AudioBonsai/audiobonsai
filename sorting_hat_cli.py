import os
import re
import sqlite3

from datetime import datetime
from pathlib import Path
from sqlite3 import Error as sqlError
from urllib.request import urlopen


EVERYNOISE_URL = 'http://everynoise.com/spotify_new_releases.html'
CREATE_CANDIDATE_TABLE = """ CREATE TABLE IF NOT EXISTS candidates (
                                spotify_uri text PRIMARY KEY,
                                add_date DATE
                             ) """

def todays_dir():
    data_dir = Path('./data')
    if not data_dir.is_dir():
        os.mkdir(data_dir)

    today = datetime.now().strftime("%Y%m%d")
    today_dir = Path(os.path.join(data_dir, today))
    if not today_dir.is_dir():
        os.mkdir(today_dir)
    return today_dir


def create_connection(today_dir):
    try:
        conn = sqlite3.connect(Path(os.path.join(today_dir, 'db.sqlite3')))
        return conn
    except sqlError as e:
        print(e)


def download_everynoise(today_dir):
    everynoise_file = Path(os.path.join(today_dir, 'everynoise.html'))
    if everynoise_file.exists():
        with open(everynoise_file, 'r') as f:
            return f.read()
    else:
        response = urlopen(EVERYNOISE_URL)
        html = response.read().decode("utf-8")
        with open(everynoise_file, 'w') as f:
            f.write(html)
        return html


def find_candidates(html):
    match_string = re.compile('(spotify:album:.*)')
    #re.compile(' title="artist rank:.*')
    #group_text = ' title="artist rank: ([0-9,-]+)"><a onclick=".*" '\
    #             'href="(spotify:album:.*)"><span class=.*>.*</span> '\
    #             '<span class=.*>.*</span></a> <span class="play trackcount" '\
    #             'albumid=spotify:album:.* nolink=true onclick=".*">' \
    #             '([0-9]+)</span>'
    group_text =  'spotify:album:.* .* albumid=(spotify:album:.*) nolink=true onclick="playmeta.*'
    group_string = re.compile(group_text)
    candidate_list = set()
    releases = html.split('</div><div class=')
    print(len(releases))
    for release in releases:
        #print("Release: {}".format(release))
        for match in match_string.findall(release):
            #print("Match: {}".format(match))
            bits = group_string.match(match)
            if bits is None:
                continue
            spotify_uri = bits.group(1)
            candidate_list.add(spotify_uri)
            #print("Spotify URI: {}".format(spotify_uri))
    print("Found {:d} candidates".format(len(candidate_list)))
    return candidate_list

if __name__ == '__main__':
    today_dir = todays_dir()
    html = download_everynoise(today_dir)
    find_candidates(html)
    db_conn = create_connection(today_dir)
    try:
        cursor = db_conn.cursor()
        cursor.execute(CREATE_CANDIDATE_TABLE)
    except Exception as e:
        print(e)
    finally:
        db_conn.close()
