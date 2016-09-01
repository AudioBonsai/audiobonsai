from audiobonsai import settings
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
    elif sp_oauth._is_token_expired(auth_user.spotify_token):
        auth_user.spotify_token = sp_oauth._refresh_access_token(auth_user.spotify_token)

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
