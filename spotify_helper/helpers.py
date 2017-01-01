from audiobonsai import settings
from django.http import HttpResponseRedirect
import json
from spotify_helper.models import SpotifyUser
import spotipy
from spotipy import oauth2


def get_spotify_conn(request):
    return_path = request.path
    try:
        auth_user = request.user.spotifyuser
        auth_user.return_path = return_path
        auth_user.save()
        return get_user_conn(auth_user, request.get_host())
    except:
        print('USER EXCEPTION. DAFUQ?')
        auth_user = SpotifyUser(user=request.user, return_path=return_path)
        auth_user.save()
        return HttpResponseRedirect(
            'http://' + request.get_host() + '/spotify/ask_user')


def get_user_conn(auth_user, host):
    if auth_user.spotify_token is None or len(auth_user.spotify_token) == 0:
        return HttpResponseRedirect(
            'http://' + host + '/spotify/ask_user')

    token_info = None
    if len(auth_user.spotify_token) > 0:
        print(type(auth_user.spotify_token))
        print(auth_user.spotify_token)
        token_info = json.loads(auth_user.spotify_token.__str__().replace('\'',
                                                                          '"'))
        sp_oauth = get_spotipy_oauth(host)
        if sp_oauth._is_token_expired(token_info):
            refresh_token = token_info['refresh_token']
            token_info = sp_oauth._refresh_access_token(refresh_token)
            msg = 'Saving spotify_token as type {} from get_user_conn'
            print(msg.format(type(token_info)))
            auth_user.spotify_token = token_info
            auth_user.save()

    return spotipy.Spotify(auth=token_info['access_token'])


def get_spotipy_oauth(host_string):
    callback_url = 'http://' + host_string + '/spotify/login'
    return oauth2.SpotifyOAuth(settings.SPOTIPY_CLIENT_ID,
                               settings.SPOTIPY_CLIENT_SECRET,
                               callback_url,
                               scope=settings.SPOTIFY_SCOPE)
