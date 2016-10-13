from audiobonsai import settings
from django.http import HttpResponse, HttpResponseRedirect
import json
from spotify_helper.helpers import get_spotipy_oauth
from spotify_helper.models import SpotifyUser
import spotipy
from spotipy import oauth2

# Create your views here.


def spotify_ask_user(request):
    html = '<HTML><BODY>The requested operation requires permission to access your Spotify account. Click ' \
           '<a href="http://' + request.get_host() + '/spotify/request_token/">here</a> to give Audio Bonsai Access. ' \
           'Press the back button if you choose not to grant access.</BODY></HTML>'
    return HttpResponse(html)


def spotify_request_token(request):
    sp_oauth = get_spotipy_oauth(request.get_host())
    return_path = None
    try:
        auth_user = request.user.spotifyuser
        return_path = auth_user.return_path
    except:
        auth_user = SpotifyUser(user=request.user)
        auth_user.save()

    if auth_user.spotify_token is None or len(auth_user.spotify_token) == 0:
        return HttpResponseRedirect(sp_oauth.get_authorize_url())
    token_info = json.loads(auth_user.spotify_token.replace('\'', '"'))
    if token_info is None or len(token_info) == 0:
        return HttpResponseRedirect(sp_oauth.get_authorize_url())
    elif sp_oauth._is_token_expired(token_info):
        token_info = sp_oauth._refresh_access_token(token_info['refresh_token'])
        auth_user.spotify_token = token_info
        auth_user.save()

    if return_path is None or len(return_path) == 0:
        # Not sure how we got here, but follow through on login
        return HttpResponseRedirect('http://' + request.get_host() + '/spotify/login')
    return HttpResponseRedirect(return_path)


def spotify_login(request):
    sp_oauth = get_spotipy_oauth(request.get_host())

    token_info = sp_oauth.get_access_token(request.GET.dict()['code'])

    try:
        auth_user = request.user.spotifyuser
        auth_user.spotify_token = token_info
        auth_user.save()
    except:
        auth_user = SpotifyUser(user=request.user, spotify_token=token_info)
        auth_user.save()

    return HttpResponseRedirect('http://' + request.get_host() + '/spotify/confirm_access')


def spotify_confirm_access(request):
    try:
        auth_user = request.user.spotifyuser
        return_path = auth_user.return_path
    except:
        return HttpResponseRedirect('http://' + request.get_host())

    html='<HTML><BODY>Access has been granted (or refreshed). <meta http-equiv="refresh" content="3;url=' \
         + return_path + '"> Click <a href="' + return_path + '">here</a> to return and try your operation again ' \
        'if you are not redirected shortly.  Thanks for using Audio Bonsai!</BODY></HTML>'
    return HttpResponse(html)

def expire_token(request):
    auth_user = request.user.spotifyuser
    token_info = json.loads(auth_user.spotify_token.replace('\'', '"'))
    token_info['expires_at'] = token_info['expires_at'] - 15000
    auth_user.spotify_token = token_info
    auth_user.save()
    sp_oauth = oauth2.SpotifyOAuth(settings.SPOTIPY_CLIENT_ID,
                                   settings.SPOTIPY_CLIENT_SECRET,
                                   'http://' + request.get_host() + '/spotify/ask_user')

    html='<HTML><BODY>_is_token_expired:' + str(sp_oauth._is_token_expired(token_info)) + '</BODY></HTML>'
    return HttpResponse(html)

def test_conn(request):
    auth_user = request.user.spotifyuser
    print(auth_user.spotify_token)
    token_info = json.loads(auth_user.spotify_token.replace('\'', '"'))
    sp = spotipy.Spotify(auth=token_info['access_token'])
    html = '<HTML><BODY>Current User:' + sp.current_user()[u'id'] + '<br/><ul>'
    user_info = sp.user(sp.current_user()[u'id'])
    for key in user_info.keys():
        html += '<li>' + key + ': ' + str(user_info[key]) + '</li>'
    html += '</ul></BODY></HTML>'
    return HttpResponse(html)
