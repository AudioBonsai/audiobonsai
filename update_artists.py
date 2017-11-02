from audiobonsai import wsgi, settings
from datetime import datetime
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from sausage_grinder.models import Artist
from spotify_helper.models import SpotifyUser
from spotipy import SpotifyException
from spotify_helper.helpers import get_user_conn

def handle_artist_list(sp, query_list):
    try:
        artist_dets_list = sp.artists(query_list)
    except SpotifyException:
        user = User.objects.get(username=settings.SPOTIFY_USERNAME)
        spotify_user = SpotifyUser.objects.get(user=user)
        sp = get_user_conn(spotify_user, '127.0.0.1:8000')
        artist_dets_list = sp.artists(query_list)
    for artist_dets in artist_dets_list[u'artists']:
        if artist_dets is None:
            print('Unable to retrieve information on one of the provided albums.')
            continue
        try:
            artist = Artist.objects.get(spotify_uri=artist_dets[u'uri'])
            artist.set_popularity(artist_dets[u'popularity'],
                                  artist_dets[u'followers']['total'])
        except Artist.DoesNotExist:
            print('Artist returned not in the database already, skipping.')
            continue
    # in case sp refreshed
    return sp


def update_artists():
    print('{}: update_artists'.format(datetime.now()))
    user = User.objects.get(username=settings.SPOTIFY_USERNAME)
    print(user)
    spotify_user = SpotifyUser.objects.get(user=user)
    sp = get_user_conn(spotify_user, '127.0.0.1:8000')
    if type(sp) is HttpResponseRedirect:
        print('User {} not authed'.format(settings.SPOTIFY_USERNAME))
        exit(-1)

    candidate_list = Artist.objects.all()
    print('{}: updating {} artists...'.format(datetime.now(), len(candidate_list)))
    batch_size = 50
    offset = 0
    while offset < len(candidate_list):
        sp_uri_list = [candidate.spotify_uri for candidate in candidate_list[offset:offset + batch_size]]
        # in case sp refreshed
        sp = handle_artist_list(sp, sp_uri_list)
        if offset%1000==0:
            print('{}: {} artists updated'.format(datetime.now(), offset))
        offset += batch_size

    print('{}: {} artists updated'.format(datetime.now(), len(candidate_list)))
    return True

if __name__ == '__main__':
    update_artists()
