from audiobonsai import settings
from datetime import datetime
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


def handle_albums(sp):
    candidate_list = CandidateRelease.objects.filter(processed=False)
    offset = 0
    while offset < len(candidate_list):
        sp_uri_list = [candidate.spotify_uri for candidate in candidate_list[offset:offset + 20]]
        handle_album_list(sp, sp_uri_list)
        offset += 20


def handle_artist_list(sp, query_list):
    artist_dets_list = sp.artists(query_list)
    for artist_dets in artist_dets_list[u'artists']:
        if artist_dets is None:
            print('Unable to retrieve information on one of the provided albums.')
            continue
        try:
            artist = CandidateArtist.objects.get(spotify_uri=artist_dets[u'uri'])
            artist.process(sp, artist_dets)
        except CandidateArtist.DoesNotExist:
            print('Artist returned not in the database already, skipping.')
            continue

def handle_artists(sp):
    candidate_list = CandidateArtist.objects.filter(processed=False)
    offset = 0
    while offset < len(candidate_list):
        sp_uri_list = [candidate.spotify_uri for candidate in candidate_list[offset:offset + 20]]
        handle_artist_list(sp, sp_uri_list)
        offset += 20
    return True


def delete_ineligible_releases():
    ineligible_list = CandidateRelease.objects.filter(eligible=False)
    [ineligible.delete() for ineligible in ineligible_list]


def delete_artists_with_no_release():
    artists = CandidateArtist.objects.all()
    [artist.delete() for artist in artists if len(artist.candidaterelease_set.all()) == 0]


def delete_empty_genres():
    genres = Genre.objects.all()
    [genre.delete() for genre in genres if len(genre.candidaterelease_set.all()) == 0 and
     len(genre.candidateartist_set.all()) == 0]


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
        self.message_user(request, '{}: parse_sorting_hat'.format(datetime.now()))
        sp = get_spotify_conn(request)
        if type(sp) is HttpResponseRedirect:
            return sp

        week = queryset[0]
        if len(CandidateRelease.objects.all()) == 0:
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

            # Shorten list for debugging
            # candidate_list = candidate_list[0:50]
            CandidateRelease.objects.bulk_create(candidate_list)
            self.message_user(request, '{0:d} releases processed to {1}'.format(len(candidate_list), week))
            print('{0:d} candidate releases'.format(len(candidate_list)))

        self.message_user(request, '{}: handle_albums'.format(datetime.now()))
        handle_albums(sp)
        self.message_user(request, '{}: delete_ineligible_releases'.format(datetime.now()))
        delete_ineligible_releases()
        print('{0:d} candidate releases eligible'.format((len(CandidateRelease.objects.all()))))
        self.message_user(request, '{0:d} releases eligible to {1}'.format(len(CandidateRelease.objects.all()), week))
        print('{0:d} candidate artists'.format((len(CandidateArtist.objects.all()))))
        self.message_user(request, '{}: delete_artists_with_no_release'.format(datetime.now()))
        delete_artists_with_no_release()
        self.message_user(request, '{}: handle_artists'.format(datetime.now()))
        handle_artists(sp)
        print('{0:d} candidate artists with a release'.format((len(CandidateArtist.objects.all()))))
        self.message_user(request, '{0:d} aritists added to {1}'.format(len(CandidateArtist.objects.all()), week))
        print('{0:d} genres'.format((len(Genre.objects.all()))))
        self.message_user(request, '{}: delete_empty_genres'.format(datetime.now()))
        delete_empty_genres()
        print('{0:d} genres with a release or artist'.format((len(Genre.objects.all()))))
        self.message_user(request, '{0:d} genres added to {1}'.format(len(Genre.objects.all()), week))
        self.message_user(request, '{}: done'.format(datetime.now()))
        return


class CandidateReleaseAdmin(admin.ModelAdmin):
    list_display = ['title', 'artist_popularity', 'popularity_class', 'has_single']
    list_filter = ['popularity_class', 'has_single', 'batch', 'processed', 'eligible', 'genres']
    ordering = ['-artist_popularity', '-sorting_hat_rank', 'batch', 'processed', 'title']
    actions = ['process_album']

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
