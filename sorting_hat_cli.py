import add_trade_rec
import codecs
import json
import os
import pandas as pd
import re
import sqlite3

from ab_util import log, get_spotify_conn, create_connection
from audiobonsai import settings
from datetime import datetime, timedelta
from math import floor
from pathlib import Path
from pprint import pprint
from spotipy import SpotifyException
from urllib.request import urlopen


EVERYNOISE_URL = 'http://everynoise.com/spotify_new_releases.html'
GROUP_TEXT = 'spotify:album:.* .* albumid=(spotify:album:.*) nolink=true ' \
             + 'onclick="playmeta.*'
TODAY = datetime.now().strftime("%Y-%m-%d 00:00:00.000000")
DAILY_SAMPLER = 'spotify:user:audiobonsai:playlist:5CmD30dzQjCujR4CAnL8qc'
WEEKLY_SAMPLER = 'spotify:user:audiobonsai:playlist:1FPe3BebdleEhyjPVmDgbr'
GRAB_BAG = 'spotify:user:audiobonsai:playlist:1NHFxGhB8klgXaie2ylyzp'


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


def insert_albums(conn, album_list):
    insert_stmt = 'INSERT INTO albums (spotify_uri, add_date, json_text)' \
                  + ' VALUES(?,?,?)'
    try:
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


def get_album_json(db_conn):
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
    sp_conn = get_spotify_conn()
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
                    log(te)
                    log(type(te))
                    log('Error caused by album details {}'.format(album_dets))
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


def extract_artists(db_conn):
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
                try:
                    for artist in track[u'artists']:
                        album_artists.add((artist[u'uri']))
                except TypeError as te:
                    log('TypeError on {} processing tracks'.format(album_uri))
                    continue
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


def get_artist_json(db_conn):
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
    sp_conn = get_spotify_conn()
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
                except SpotifyException as se:
                    # one of the URIs failed
                    print(se)
                    print(type(se))
                    for sp_uri in sp_uri_list:
                        try:
                            artist_dets = sp_conn.artist(sp_uri)
                            uri = artist_dets[u'uri']
                            followers = artist_dets[u'followers'][u'total']
                            popularity = artist_dets[u'popularity']
                            update_list.add((json.dumps(artist_dets), TODAY,
                                             popularity, followers, uri))
                            insert_pop_foll_list.add((uri, followers,
                                                      popularity))
                        except SpotifyException as se:
                            log('Failed getting artist {}'.format(sp_uri))
                            print(se)
                            print(type(se))
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


def select_grab_bag(db_conn, table_name, today_date, previous_date):
    today_pop = 'pop_{}'.format(today_date)
    today_foll = 'foll_{}'.format(today_date)
    prev_pop = 'pop_{}'.format(previous_date)
    prev_foll = 'foll_{}'.format(previous_date)
    df = pd.read_sql('SELECT * from {}'.format(table_name), db_conn)
    df['pop_diff'] = df[today_pop] - df[prev_pop]
    df['foll_diff'] = df[today_foll] - df[prev_foll]
    df['foll_diff_pct'] = (df['foll_diff']/df[prev_foll])*100
    print(len(df))
    #df = df[df['pop_diff'] > 0]
    #print(len(df))
    df = df[df['foll_diff'] > 0]
    print(len(df))
    rand_100 = df.sample(150)
    rand_100 = rand_100.head(100)
    return rand_100['artist_uri'].tolist()


def select_top_tracks(db_conn, table_name, today_date, previous_date):
    today_pop = 'pop_{}'.format(today_date)
    today_foll = 'foll_{}'.format(today_date)
    prev_pop = 'pop_{}'.format(previous_date)
    prev_foll = 'foll_{}'.format(previous_date)
    df = pd.read_sql('SELECT * from {}'.format(table_name), db_conn)
    df['pop_diff'] = df[today_pop] - df[prev_pop]
    df['foll_diff'] = df[today_foll] - df[prev_foll]
    df['foll_diff_pct'] = (df['foll_diff']/df[prev_foll])*100
    df['final_score'] = ((df['pop_diff'] * 100) + df['foll_diff']
                         + (df['curator_rec'] * 500))
    df = df.sort_values(by='final_score', ascending=False)
    df = df.drop_duplicates('album_uri', keep='first')
    df['category'] = pd.cut(df[prev_pop], 10)

    categories = df['category'].unique()
    artist_uris = set()
    num_albums = 6
    for category in sorted(categories):
        category_df = df[df['category'] == category]
        category_df = category_df.head(num_albums)
        print(category_df.loc[:, ['orig_pop', today_pop, 'current_pop',
                                  prev_pop, 'pop_diff',
                                  'orig_foll', today_foll, 'current_foll',
                                  prev_foll, 'foll_diff',
                                  'curator_rec', 'final_score']])
        artist_uris.update(category_df['artist_uri'].tolist())
    return artist_uris


def rebuild_playlist(db_conn, table_name, prev_artists, playlist,
                     type, today_date):
    get_album_from_artist = 'SELECT albums.json_text, albums.spotify_uri ' \
                            + 'FROM album_artists ' \
                            + 'INNER JOIN albums ON album_artists.album_uri ' \
                            + '= albums.spotify_uri WHERE ' \
                            + 'album_artists.artist_uri = "{}" ' \
                            + 'ORDER BY albums.release_date DESC LIMIT 1'
    insert_into_log = 'INSERT INTO ' + type + '_log (album_uri, ' + type + \
                      '_list) VALUES(?, ?)'
    top_tracks = set()
    for artist_uri in prev_artists:
        db_cursor = db_conn.cursor()
        db_cursor.execute(get_album_from_artist.format(artist_uri))
        result = db_cursor.fetchone()
        if result is None:
            log('{} ARTIST URI NOT FOUND IN DB!'.format(artist_uri))
            continue
        try:
            album_uri = result[1]
            album_json = json.loads(result[0])
        except json.decoder.JSONDecodeError as jsde:
            log('Error processing JSON of {} by {}'.format(album_uri,
                                                           artist_uri))
            print(jsde)
            continue
        album_tracks = album_json[u'tracks']
        durations = list()
        for track in album_tracks[u'items']:
            if track is None:
                continue
            durations.append(track[u'duration_ms'])
        if len(durations) == 0:
            continue
        sorted_durations = sorted(durations)
        median_duration = sorted_durations[floor(len(durations)/2)]
        track_diffs = {}
        track_durations = {}

        try:
            for track in album_tracks[u'items']:
                for artist in track[u'artists']:
                    if artist_uri == artist[u'uri']:
                        track_diffs[abs(track[u'duration_ms'] -
                                    median_duration)] = track[u'uri']
                        track_durations[track[u'uri']] = track[u'duration_ms']

                if len(track_diffs.keys()) == 3:
                    break
        except TypeError as te:
            err_str = 'The JSON for {} by {} had missing info, not included'
            log(err_str.format(album_uri, artist_uri))
            print(te)
            continue
        if len(track_diffs.keys()) > 0:
            track_uri = track_diffs[sorted(track_diffs.keys())[0]]
            top_tracks.add(track_uri)
            if type in ['daily', 'weekly']:
                today_string = today_date.strftime("%Y-%m-%d 00:00:00.000000")
                try:
                    db_conn.execute(insert_into_log, (album_uri, today_string))
                except sqlite3.IntegrityError as ie:
                    # Skip existing entry
                    pass
    db_conn.commit()
    sp_conn = get_spotify_conn()
    sp_conn.user_playlist_replace_tracks(settings.SPOTIFY_USERNAME,
                                         playlist, top_tracks)


def pop_change_tables(db_conn):
    today_date = datetime.now()
    today_table_name = 'pop_foll_{}'.format(today_date.strftime("%Y%m%d"))
    yesterday_date = datetime.now() - timedelta(days=1)
    yesterday_table = 'pop_foll_{}'.format(yesterday_date.strftime("%Y%m%d"))
    weekago_date = datetime.now() - timedelta(days=7)
    weekago_table = 'pop_foll_{}'.format(weekago_date.strftime("%Y%m%d"))

    drop_grab_bag_table = 'DROP TABLE IF EXISTS grab_bag_diff'
    create_grab_bag_table = 'create table grab_bag_diff as ' \
                            + 'SELECT art.spotify_uri, art.orig_pop, ' \
                            + 'art.orig_foll, art.current_pop, ' \
                            + 'art.current_foll, s4.* from artists AS ' \
                            + 'art INNER JOIN ' \
                            + '(SELECT * FROM ' + today_table_name + ' AS td ' \
                            + 'INNER JOIN ' \
                            + '(SELECT * FROM ' + yesterday_table + ' AS yt ' \
                            + 'INNER JOIN ' \
                            + '(SELECT * from album_artists AS aa INNER JOIN ' \
                            + '(SELECT a.spotify_uri, a.release_date, ' \
                            + 'a.trade_rec, a.curator_rec ' \
                            + 'FROM albums AS a WHERE trade_rec = 0 and ' \
                            + 'curator_rec = 0) ' \
                            + 'AS s1 ON s1.spotify_uri = aa.album_uri) AS s2 ' \
                            + 'ON s2.artist_uri = yt.artist_uri) AS s3 ON ' \
                            + 'td.artist_uri = s3.artist_uri) AS s4 ON ' \
                            + 's4.artist_uri = art.spotify_uri WHERE '\
                            + 'art.current_pop >= 20 AND art.current_pop <= 70'
    drop_yesterday_table = 'DROP TABLE IF EXISTS yesterday_diff'
    create_yesterday_table = 'create table yesterday_diff as ' \
                             + 'SELECT art.spotify_uri, art.orig_pop, ' \
                             + 'art.orig_foll, art.current_pop, ' \
                             + 'art.current_foll, s4.* from artists AS ' \
                             + 'art INNER JOIN ' \
                             + '(SELECT * FROM ' + today_table_name + ' AS td ' \
                             + 'INNER JOIN ' \
                             + '(SELECT * FROM ' + yesterday_table + ' AS yt ' \
                             + 'INNER JOIN ' \
                             + '(SELECT * from album_artists AS aa INNER JOIN ' \
                             + '(SELECT a.spotify_uri, a.release_date, ' \
                             + 'a.trade_rec, a.curator_rec ' \
                             + 'FROM albums AS a WHERE (trade_rec = 1 OR ' \
                             + 'curator_rec = 1) and a.spotify_uri not in (' \
                             + 'select album_uri as spotify_uri from (select ' \
                             + 'album_uri, count(album_uri) as appearences ' \
                             + 'from daily_log group by album_uri) as ' \
                             + 'daily_count where appearences > 6)) ' \
                             + 'AS s1 ON s1.spotify_uri = aa.album_uri) AS s2 ' \
                             + 'ON s2.artist_uri = yt.artist_uri) AS s3 ON ' \
                             + 'td.artist_uri = s3.artist_uri) AS s4 ON ' \
                             + 's4.artist_uri = art.spotify_uri'
    drop_weekago_table = 'DROP TABLE IF EXISTS weekago_diff'
    create_weekago_table = 'create table weekago_diff as ' \
                           + 'SELECT art.spotify_uri, art.orig_pop, ' \
                           + 'art.orig_foll, art.current_pop, ' \
                           + 'art.current_foll, s4.* from artists AS ' \
                           + 'art INNER JOIN ' \
                           + '(SELECT * FROM ' + today_table_name + ' AS td ' \
                           + 'INNER JOIN ' \
                           + '(SELECT * FROM ' + weekago_table + ' AS yt ' \
                           + 'INNER JOIN ' \
                           + '(SELECT * from album_artists AS aa INNER JOIN ' \
                           + '(SELECT a.spotify_uri, a.release_date, ' \
                           + 'a.trade_rec, a.curator_rec ' \
                           + 'FROM albums AS a WHERE (trade_rec = 1 OR ' \
                           + 'curator_rec = 1) and a.spotify_uri not in (' \
                           + 'select album_uri as spotify_uri from (select ' \
                           + 'album_uri, count(album_uri) as appearences ' \
                           + 'from weekly_log group by album_uri) as ' \
                           + 'weekly_count where appearences > 6)) ' \
                           + 'AS s1 ON s1.spotify_uri = aa.album_uri) AS s2 ' \
                           + 'ON s2.artist_uri = yt.artist_uri) AS s3 ON ' \
                           + 'td.artist_uri = s3.artist_uri) AS s4 ON ' \
                           + 's4.artist_uri = art.spotify_uri'
    try:
        log('Creating grab bag diff join')
        db_conn.execute(drop_grab_bag_table)
        db_conn.commit()
        db_conn.execute(create_grab_bag_table)
        db_conn.commit()
        grab_bag_artists = select_grab_bag(db_conn, 'grab_bag_diff',
                                           today_date.strftime("%Y%m%d"),
                                           yesterday_date.strftime("%Y%m%d"))
        rebuild_playlist(db_conn, 'grab_bag_diff', grab_bag_artists,
                         GRAB_BAG, 'grab_bag', today_date)
        log('Creating yesterday diff join')
        db_conn.execute(drop_yesterday_table)
        db_conn.commit()
        db_conn.execute(create_yesterday_table)
        db_conn.commit()
        ystrdy_artists = select_top_tracks(db_conn, 'yesterday_diff',
                                           today_date.strftime("%Y%m%d"),
                                           yesterday_date.strftime("%Y%m%d"))
        rebuild_playlist(db_conn, 'yesterday_diff', ystrdy_artists,
                         DAILY_SAMPLER, 'daily', today_date)
        log('Creating week ago diff join')
        db_conn.execute(drop_weekago_table)
        db_conn.commit()
        db_conn.execute(create_weekago_table)
        db_conn.commit()
        wkago_artists = select_top_tracks(db_conn, 'weekago_diff',
                                          today_date.strftime("%Y%m%d"),
                                          weekago_date.strftime("%Y%m%d"))
        rebuild_playlist(db_conn, 'weekago_diff', wkago_artists,
                         WEEKLY_SAMPLER, 'weekly', today_date)
        log('Playlists updated')
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
        for playlist_id in add_trade_rec.TRADELISTS:
            add_trade_rec.add_playlist_recs(playlist_id, get_spotify_conn(),
                                            db_conn, 'trade')
        for playlist_id in add_trade_rec.CURATORLISTS:
            add_trade_rec.add_playlist_recs(playlist_id, get_spotify_conn(),
                                            db_conn, 'curator')
    except Exception as e:
        print(e)
        print(type(e))
        raise(e)

    try:
        get_album_json(db_conn)
    except Exception as e:
        print(e)
        print(type(e))
        raise(e)

    try:
        extract_artists(db_conn)
    except Exception as e:
        print(e)
        print(type(e))
        raise(e)

    cutoff_date = datetime.now() - timedelta(days=30)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d 00:00:00.000000")
    try:
        db_conn.execute('DELETE FROM albums WHERE release_date < "{}"'.format(
                        cutoff_str))
        db_conn.commit()
    except Exception as e:
        print(e)
        print(type(e))
        raise(e)

    try:
        db_conn.execute('DELETE from artists where artists.spotify_uri not '
                        + 'in (select distinct artist_uri from album_artists)')
        db_conn.commit()
    except Exception as e:
        print(e)
        print(type(e))
        raise(e)

    try:
        get_artist_json(db_conn)
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
        pop_change_tables(db_conn)
    except Exception as e:
        print(e)
        print(type(e))
        raise(e)

    try:
        # Clean out artists json_text
        db_conn.execute('UPDATE artists SET json_text = ""')
        db_conn.commit()
    except Exception as e:
        print(e)
        print(type(e))
        raise(e)

    log('VACUUMING')
    db_conn.execute('VACUUM')
    db_conn.commit()
    log('EXITING')
    db_conn.close()
