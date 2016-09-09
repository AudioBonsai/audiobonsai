from audiobonsai import settings
from django.contrib import admin
from django.http import HttpResponseRedirect
import json
from pprint import pprint
import re
from sausage_grinder.models import CandidateSet, CandidateRelease, Genre, CandidateTrack, CandidateArtist
from spotify_helper.models import SpotifyUser
import spotipy

from urllib.request import urlopen

# Register your models here.


def get_spotify_conn(request):
    return_path = request.path
    try:
        auth_user = request.user.spotifyuser
        auth_user.return_path = return_path
        auth_user.save()
    except:
        print('USER EXCEPTION. DAFUQ?')
        auth_user = SpotifyUser(user=request.user, return_path=return_path)
        auth_user.save()
        return HttpResponseRedirect(
            'http://' + request.get_host() + '/spotify/ask_user')

    if auth_user.spotify_token is None or len(auth_user.spotify_token) == 0:
        return HttpResponseRedirect(
            'http://' + request.get_host() + '/spotify/ask_user')

    sp_oauth = spotipy.oauth2.SpotifyOAuth(settings.SPOTIPY_CLIENT_ID,
                                           settings.SPOTIPY_CLIENT_SECRET,
                                           'http://' + request.get_host() + '/spotify/ask_user')

    token_info = None
    if len(auth_user.spotify_token) > 0:
        token_info = json.loads(auth_user.spotify_token.replace('\'', '"'))
        if sp_oauth._is_token_expired(token_info):
            return HttpResponseRedirect(
                'http://' + request.get_host() + '/spotify/request_token')


    return spotipy.Spotify(auth=token_info['access_token'])


class GenreAdmin(admin.ModelAdmin):
    list_display = ['name']
    fields = ['name']


class CandidateTrackAdmin(admin.ModelAdmin):
    list_display = ['title', 'single_release_date', 'release', 'disc_number', 'track_number', 'duration', 'spotify_uri']
    ordering = ['release', 'disc_number', 'track_number']


class CandidateArtistAdmin(admin.ModelAdmin):
    list_display = ['name', 'spotify_uri', 'popularity', 'followers']
    ordering = ['-popularity', '-followers', 'name']
    list_filter = ['processed', 'popularity', 'genres']
    actions = ['process_artist']

    @staticmethod
    def handle_artist_list(sp, query_list):
        artist_dets_list = sp.artists(query_list)
        for artist_dets in artist_dets_list[u'artists']:
            if artist_dets is None:
                print('Unable to retrieve information on one of the provided albums.')
                continue
            artist = CandidateArtist.objects.get(spotify_uri=artist_dets[u'uri'])
            artist.process(sp, artist_dets)

    def process_artist(self, request, queryset):
        sp = get_spotify_conn(request)
        if type(sp) is HttpResponseRedirect:
            return sp
        query_list = []
        for artist in queryset:
            if len(query_list) < 20:
                query_list.append(artist.spotify_uri)
            else:
                self.handle_artist_list(sp, query_list)
                query_list = [artist.spotify_uri]
        self.handle_artist_list(sp, query_list)
        return

class CandidateSetAdmin(admin.ModelAdmin):
    list_display = ['week_date']
    ordering = ['week_date']
    actions = ['parse_sorting_hat']

    def parse_sorting_hat(self, request, queryset):
        week = queryset[0]
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

        for release in releases:
            for match in match_string.findall(release):
                bits = group_string.match(match)
                if bits is None:
                    continue
                candidate = CandidateRelease(spotify_uri=bits.group(2), sorting_hat_track_num=int(bits.group(3)),
                                             week=week, batch=len(candidate_list) % settings.GRINDER_BATCHES)
                if bits.group(1) != '-':
                    candidate.sorting_hat_rank = int(bits.group(1))
                candidate_list.append(candidate)

        CandidateRelease.objects.bulk_create(candidate_list)
        self.message_user(request, '{0:d} tracks added to {1}'.format(len(candidate_list), set))
        return


class CandidateReleaseAdmin(admin.ModelAdmin):
    list_display = ['title', 'spotify_uri', 'sorting_hat_rank', 'sorting_hat_track_num', 'batch']
    list_filter = ['batch', 'processed', 'eligible', 'genres']
    ordering = ['-sorting_hat_rank', 'batch', 'processed', 'title']
    actions = ['process_album']

    @staticmethod
    def handle_album_list(sp, query_list):
        track_list = []
        album_dets_list = sp.albums(query_list)
        if album_dets_list is None:
            return
        for album_dets in album_dets_list[u'albums']:
            if album_dets is None:
                print('Unable to retrieve information on one of the provided albums.')
                continue
            album = CandidateRelease.objects.get(spotify_uri=album_dets[u'uri'])
            track_list += album.process(sp, album_dets)
        CandidateTrack.objects.bulk_create(track_list)
        return

    def process_album(self, request, queryset):
        sp = get_spotify_conn(request)
        if type(sp) is HttpResponseRedirect:
            return sp
        query_list = []
        for album in queryset:
            if len(query_list) < 20:
                query_list.append(album.spotify_uri)
            else:
                self.handle_album_list(sp, query_list)
                query_list = [album.spotify_uri]
        self.handle_album_list(sp, query_list)
        return



# Register your models here.
admin.site.register(CandidateArtist, CandidateArtistAdmin)
admin.site.register(CandidateRelease, CandidateReleaseAdmin)
admin.site.register(CandidateSet, CandidateSetAdmin)
admin.site.register(CandidateTrack, CandidateTrackAdmin)
admin.site.register(Genre, GenreAdmin)
