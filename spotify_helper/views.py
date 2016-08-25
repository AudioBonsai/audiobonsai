from audiobonsai import settings
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from spotify_helper.models import SpotifyUser
from spotipy import oauth2

# Create your views here.

def get_spotipy_oauth(host_string):
    callback_url = 'http://' + host_string + '/spotify/login'
    return oauth2.SpotifyOAuth(settings.SPOTIPY_CLIENT_ID,
                                   settings.SPOTIPY_CLIENT_SECRET,
                                   callback_url,
                                   scope=settings.SPOTIFY_SCOPE)


def get_return_path(request):
    try:
        return request.GET.dict()['return_path']
    except:
        return None

def spotify_request_token(request):
    sp_oauth = get_spotipy_oauth(request.get_host())
    return_path = None
    try:
        auth_user = request.user.spotifyuser
        return_path = auth_user.return_path
    except:
        auth_user = SpotifyUser(user=request.user)
        auth_user.save()

    if auth_user.spotify_token is None or len(auth_user.spotify_token):
        return HttpResponseRedirect(sp_oauth.get_authorize_url())
    elif sp_oauth._is_token_expired(auth_user.spotify_token):
        auth_user.spotify_token = sp_oauth._refresh_access_token(auth_user.spotify_token)

    if return_path is None or len(return_path) == 0:
        # Not sure how we got here, but follow through on login
        return HttpResponseRedirect('http://' + request.get_host() + '/spotify/login')
    return HttpResponseRedirect(return_path)


def spotify_login(request):
    sp_oauth = get_spotipy_oauth(request.get_host())

    token_info = sp_oauth.get_access_token(request.GET.dict()['code'])
    return_path = None
    try:
        auth_user = request.user.spotifyuser
        auth_user.spotify_token = token_info
        auth_user.save()
        return_path = auth_user.return_path
    except:
        auth_user = SpotifyUser(user=request.user, spotify_token=token_info)
        auth_user.save()

    if return_path is not None and len(return_path) > 0:
        return HttpResponseRedirect(return_path)
    else:
        html = '<HTML><BODY><H1>SUCCESSFULLY AUTHENTICATED!</H1></BODY></HTML>'
        return HttpResponse(html)
