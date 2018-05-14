from audiobonsai import wsgi, settings
from datetime import datetime
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
import json
from sausage_grinder.models import Artist, ArtistRelease, Release, ReleaseSet
from spotify_helper.models import SpotifyUser
from spotipy import SpotifyException
from spotify_helper.helpers import get_user_conn

def update_artist(artist_dets):
    if artist_dets is None:
        print('Unable to update {}'.format(artist_uri))
        return
    try:
        artist = Artist.objects.get(spotify_uri=artist_dets[u'uri'])
        artist.set_popularity(artist_dets[u'popularity'],
                              artist_dets[u'followers']['total'])
    except Artist.DoesNotExist:
        print('Artist {} returned not in the database already, skipping.'.format(artist_dets[u'name']))


def handle_artist_list(sp, query_list):
    try:
        artist_dets_list = sp.artists(query_list)
    except SpotifyException:
        user = User.objects.get(username=settings.SPOTIFY_USERNAME)
        spotify_user = SpotifyUser.objects.get(user=user)
        sp = get_user_conn(spotify_user, '127.0.0.1:8000')
        artist_dets_list = sp.artists(query_list)
    except json.decoder.JSONDecodeError:
        for artist_uri in query_list:
            try:
                artist_dets = sp.artist(artist_uri)
                update_artist(artist_dets)
            except json.decoder.JSONDecodeError:
                print('Unable to update {}'.format(artist_uri))
                continue
        return sp

    for artist_dets in artist_dets_list[u'artists']:
        update_artist(artist_dets)
    # in case sp refreshed
    return sp


def process_week(week, sp):
    '''
    release_list = Release.objects.filter(week=week)
    print ('{}: found {} releases from week {}...'.format(datetime.now(), len(release_list), week.week_date))
    offset = 0
    artist_count = 0
    for release in release_list:
        artist_list = ArtistRelease.objects.filter(release=release)
        for artist_release in artist_list:
            artist = artist_release.artist
            artist.weeks.add(week)
            artist.save()
            artist_count += 1
        offset += 1
        if offset%1000==0:
            print('{}: -> {} releases updated ({} artists)'.format(datetime.now(), offset, artist_count))
    '''
    candidate_list = Artist.objects.filter(weeks=week)
    print('{}: updating {} artists from week {}...'.format(datetime.now(), len(candidate_list), week.week_date))
    batch_size = 50
    offset = 0
    while offset < len(candidate_list):
        sp_uri_list = [candidate.spotify_uri for candidate in candidate_list[offset:offset + batch_size]]
        # in case sp refreshed
        sp = handle_artist_list(sp, sp_uri_list)
        if offset%1000==0:
            print('{}: -> {} artists updated'.format(datetime.now(), offset))
        offset += batch_size

    print('{}: {} artists updated'.format(datetime.now(), len(candidate_list)))
    return True


def update_artists():
    print('{}: update_artists'.format(datetime.now()))
    user = User.objects.get(username=settings.SPOTIFY_USERNAME)
    print(user)
    spotify_user = SpotifyUser.objects.get(user=user)
    sp = get_user_conn(spotify_user, '127.0.0.1:8000')
    if type(sp) is HttpResponseRedirect:
        print('User {} not authed'.format(settings.SPOTIFY_USERNAME))
        exit(-1)

    weeks = ReleaseSet.objects.all().order_by('-week_date')
    for week in weeks[:1]:
        process_week(week, sp)

if __name__ == '__main__':
    update_artists()
