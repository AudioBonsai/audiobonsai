import re
from audiobonsai import wsgi, settings
from datetime import datetime, date
from random import randint
from datetime import timedelta
from urllib.request import urlopen
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from pprint import pprint
from sausage_grinder.models import ReleaseSet, Release, Genre, Artist, Recommendation, Track
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
            print('Unable to retrieve information on one of the provided albums.')
            continue
        try:
            album = Release.objects.get(spotify_uri=album_dets[u'uri'])
        except Release.MultipleObjectsReturned:
            print('Repeat album? {}, SKIPPING'.format(album_dets[u'uri']))
            continue
        track_list += album.process(sp, album_dets, all_eligible)
    #Track.objects.bulk_create(track_list)
    return


def handle_albums(sp, all_eligible=False):
    candidate_list = Release.objects.filter(processed=False)
    print('CANDIDATE LIST LENGTH: {0:d}'.format(len(candidate_list)))
    offset = 0
    while offset < len(candidate_list):
        sp_uri_list = [candidate.spotify_uri for candidate in candidate_list[offset:offset + 20]]
        handle_album_list(sp, sp_uri_list, all_eligible)
        offset += 20


def handle_artist_list(sp, query_list):
    artist_dets_list = sp.artists(query_list)
    for artist_dets in artist_dets_list[u'artists']:
        if artist_dets is None:
            print('Unable to retrieve information on one of the provided albums.')
            continue
        try:
            artist = Artist.objects.get(spotify_uri=artist_dets[u'uri'])
            artist.process(sp, artist_dets)
        except Artist.DoesNotExist:
            print('Artist returned not in the database already, skipping.')
            continue

def handle_artists(sp):
    candidate_list = Artist.objects.filter(processed=False)
    offset = 0
    while offset < len(candidate_list):
        sp_uri_list = [candidate.spotify_uri for candidate in candidate_list[offset:offset + 20]]
        handle_artist_list(sp, sp_uri_list)
        offset += 20
    return True


def get_current_release_set():
    prev_friday_adjustment = {
        0: timedelta(days=3),
        1: timedelta(days=4),
        2: timedelta(days=5),
        3: timedelta(days=6),
        4: timedelta(days=0),
        5: timedelta(days=1),
        6: timedelta(days=2)
    }
    prev_friday = prev_friday = date.today() - \
        prev_friday_adjustment[date.today().weekday()]
    try :
        week = ReleaseSet.objects.get(week_date=prev_friday)
    except ReleaseSet.DoesNotExist:
        week = ReleaseSet(week_date=prev_friday)
        week.save()
    return week


def parse_sorting_hat():
    print('{}: parse_sorting_hat'.format(datetime.now()))
    print(settings.SPOTIFY_USERNAME)
    user = User.objects.get(username=settings.SPOTIFY_USERNAME)
    print(user)
    spotify_user = SpotifyUser.objects.get(user=user)
    print(spotify_user)
    sp = get_user_conn(spotify_user, '127.0.0.1:8000')
    if type(sp) is HttpResponseRedirect:
        return sp

    print('{}: Downloading Sorting Hat and creating releases'.format(datetime.now()))
    response = urlopen('http://everynoise.com/spotify_new_releases.html')
    html = response.read().decode("utf-8")
    releases = html.split('</div><div class=')
    match_string = re.compile(' title="artist rank:.*')
    group_text = ' title="artist rank: ([0-9,-]+)"><a onclick=".*" href="(spotify:album:.*)">' \
                 '<span class=.*>.*</span> <span class=.*>.*</span></a> ' \
                 '<span class="play trackcount" albumid=spotify:album:.* nolink=true onclick=".*">' \
                 '([0-9]+)</span>'
    group_string = re.compile(group_text)
    candidate_list = []
    week = get_current_release_set()
    print(week.week_date.strftime('%A, %B %d, %Y'))

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
                candidate = Release(week=week, spotify_uri=bits.group(2),
                                    sorting_hat_track_num=int(bits.group(3)))
                if bits.group(1) != '-':
                    candidate.sorting_hat_rank = int(bits.group(1))
                candidate_list.append(candidate)

    # Shorten list for debugging
    #candidate_list = candidate_list[0:50]
    #print(candidate_list)
    Release.objects.bulk_create(candidate_list)
    print('{0:d} releases processed'.format(len(candidate_list)))
    print('{0:d} candidate releases'.format(len(candidate_list)))

    try:
        print('{}: handle_albums'.format(datetime.now()))
        handle_albums(sp, True)
        print('{}: delete_ineligible_releases'.format(datetime.now()))
        week.delete_ineligible_releases()
        print('{0:d} releases eligible to {1}'.format(len(Release.objects.filter(week=week)), week))
        print('{0:d} candidate artists'.format((len(Artist.objects.filter(processed=False)))))
        print('{}: handle_artists'.format(datetime.now()))
        handle_artists(sp)
        print('{}: done'.format(datetime.now()))
    except SpotifyException:
        parse_sorting_hat()
    return

if __name__ == '__main__':
    parse_sorting_hat()
