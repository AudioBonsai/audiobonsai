import re
from audiobonsai import settings
from datetime import datetime, date
from datetime import timedelta
from urllib.request import urlopen
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from pprint import pprint
from sausage_grinder.models import Release, Artist
from spotify_helper.models import SpotifyUser
from spotipy import SpotifyException
from spotify_helper.helpers import get_user_conn


def handle_album_list(sp, query_list, all_eligible=False):
    track_list = []
    album_dets_list = sp.albums(query_list)
    if album_dets_list is None:
        return
    for album_dets in album_dets_list[u'albums']:
        if album_dets is None:
            print('Unable to retrieve information on one of the provided \
                   albums.')
            continue
        try:
            album = Release.objects.get(spotify_uri=album_dets[u'uri'])
        except Release.MultipleObjectsReturned:
            print('Repeat album? {}, SKIPPING'.format(album_dets[u'uri']))
            continue
        track_list += album.process(sp, album_dets, all_eligible)
    # Track.objects.bulk_create(track_list)
    return


def handle_albums(sp, all_eligible=False):
    candidate_list = Release.objects.filter(processed=False)
    print('CANDIDATE LIST LENGTH: {0:d}'.format(len(candidate_list)))
    offset = 0
    batch_size = 20
    while offset < len(candidate_list):
        sp_uri_list = [candidate.spotify_uri for candidate in
                       candidate_list[offset:offset + batch_size]]
        handle_album_list(sp, sp_uri_list, all_eligible)
        if offset % 1000 == 0:
            print('{}: -> {} albums processed'.format(datetime.now(), offset))
        offset += batch_size


def handle_artist_list(sp, query_list):
    artist_dets_list = sp.artists(query_list)
    for artist_dets in artist_dets_list[u'artists']:
        if artist_dets is None:
            print('Unable to retrieve information on one of the provided \
                   albums.')
            continue
        try:
            artist = Artist.objects.get(spotify_uri=artist_dets[u'uri'])
            artist.process(sp, artist_dets)
        except Artist.DoesNotExist:
            print('Artist returned not in the database already, skipping.')
            continue


def handle_artists(sp):
    candidate_list = Artist.objects.all()
    offset = 0
    batch_size = 50
    while offset < len(candidate_list):
        sp_uri_list = [candidate.spotify_uri for candidate in
                       candidate_list[offset:offset + batch_size]]
        handle_artist_list(sp, sp_uri_list)
        if offset % 1000 == 0:
            print('{}: -> {} artists processed'.format(datetime.now(), offset))
        offset += batch_size
    return True


def parse_sorting_hat():
    print('{}: parse_sorting_hat'.format(datetime.now()))
    user = User.objects.get(username=settings.SPOTIFY_USERNAME)
    spotify_user = SpotifyUser.objects.get(user=user)
    sp = get_user_conn(spotify_user, '127.0.0.1:8000')
    if type(sp) is HttpResponseRedirect:
        print('User {} not authed'.format(settings.SPOTIFY_USERNAME))
        exit(-1)

    print('{}: Downloading Sorting Hat and creating \
               releases'.format(datetime.now()))
    response = urlopen('http://everynoise.com/spotify_new_releases.html')
    html = response.read().decode("utf-8")
    releases = html.split('</div><div class=')
    match_string = re.compile(' title="artist rank:.*')
    group_text = ' title="artist rank: ([0-9,-]+)"><a onclick=".*" '\
                 'href="(spotify:album:.*)"><span class=.*>.*</span> '\
                 '<span class=.*>.*</span></a> <span class="play trackcount" '\
                 'albumid=spotify:album:.* nolink=true onclick=".*">' \
                 '([0-9]+)</span>'
    group_string = re.compile(group_text)
    candidate_list = []

    for release in releases:
        for match in match_string.findall(release):
            bits = group_string.match(match)
            if bits is None:
                continue
            try:
                candidate = Release.objects.get(spotify_uri=bits.group(2))
            except Release.MultipleObjectsReturned:
                pass
            except Release.DoesNotExist:
                candidate = Release(spotify_uri=bits.group(2),
                                    sorting_hat_track_num=int(bits.group(3)))
                if bits.group(1) != '-':
                    candidate.sorting_hat_rank = int(bits.group(1))
                candidate_list.append(candidate)

    # Shorten list for debugging
    candidate_list = candidate_list[0:50]
    print(candidate_list)
    Release.objects.bulk_create(candidate_list)
    print('{0:d} releases processed'.format(len(candidate_list)))
    print('{0:d} candidate releases'.format(len(candidate_list)))

    '''
    done = False
    while not done:
        try:
            print('{}: handle_albums'.format(datetime.now()))
            handle_albums(sp, False)
        except SpotifyException:
            sp = get_user_conn(spotify_user, '127.0.0.1:8000')
            continue
        done = True

    done = False
    while not done:
        try:
            print('{}: delete_ineligible_releases'.format(datetime.now()))
        except SpotifyException:
            sp = get_user_conn(spotify_user, '127.0.0.1:8000')
            continue
        done = True

    done = False
    while not done:
        try:
            print('{}: handle_artists'.format(datetime.now()))
            handle_artists(sp)
        except SpotifyException:
            sp = get_user_conn(spotify_user, '127.0.0.1:8000')
            continue
        print('{}: done'.format(datetime.now()))
        done = True
    '''
    return

if __name__ == '__main__':
    parse_sorting_hat()
