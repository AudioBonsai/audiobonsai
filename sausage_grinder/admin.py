import re
from datetime import datetime
from urllib.request import urlopen
from django.contrib import admin
from django.http import HttpResponseRedirect
from audiobonsai import settings
from pprint import pprint
from sausage_grinder.models import ReleaseSet, Release, Genre, Artist, Recommendation, Track
from spotipy import SpotifyException
from spotify_helper.helpers import get_spotify_conn


# Register your models here.


def handle_album_list(sp, query_list, all_eligible=False):
    #track_list = []
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
        #track_list += album.process(sp, album_dets, all_eligible)
    #Track.objects.bulk_create(track_list)
    return


def handle_albums(sp, release_set, all_eligible=False):
    candidate_list = Release.objects.filter(processed=False, week=release_set)
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


def delete_artists_with_no_release():
    artists = Artist.objects.all()
    [artist.delete() for artist in artists if len(artist.candidaterelease_set.all()) == 0]


def delete_empty_genres():
    genres = Genre.objects.all()
    [genre.delete() for genre in genres if len(genre.candidaterelease_set.all()) == 0 and
     len(genre.candidateartist_set.all()) == 0]


class GenreAdmin(admin.ModelAdmin):
    list_display = ['name']
    fields = ['name']


class TrackAdmin(admin.ModelAdmin):
    list_display = ['title', 'single_release_date', 'is_sample', 'is_freshcut', 'release', 'disc_number', 'track_number', 'duration', 'spotify_uri']
    list_filter = ['is_sample', 'is_freshcut']
    ordering = ['release', 'disc_number', 'track_number']


class ArtistAdmin(admin.ModelAdmin):
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


class ReleaseSetAdmin(admin.ModelAdmin):
    list_display = ['week_date', 'sampler_uri']
    ordering = ['-week_date']
    actions = ['parse_sorting_hat', 'load_samples', 'process_lists',
               'delete_ineligible_releases', 'determine_popularities']

    def determine_popularities(self, request, queryset):
        for week in queryset:
            week.determine_popularities()

    def delete_ineligible_releases(self):
        ineligible_list = Release.objects.filter(eligible=False, week=self)
        [ineligible.delete() for ineligible in ineligible_list]

    def load_samples(self, request, queryset):
        offset = 0
        list_count = 500
        sp = get_spotify_conn(request)
        if type(sp) is HttpResponseRedirect:
            return sp
        while(offset < list_count):
            output = sp.user_playlists(sp.current_user()[u'id'], offset=offset)
            print('offset:{} limit:{} total:{}'.format(output[u'offset'],
                  output[u'limit'], output[u'total']))

            for item in output[u'items']:
                fc_match = re.match(r'^Fresh Cuts: (.* [0-9]+, [0-9]+)$',
                                    item[u'name'])
                top_ten_match = re.match(r'.* by (.*): (.* [0-9]+, [0-9]+)$',
                                         item[u'name'])

                if fc_match is not None:
                    date_text = fc_match.group(1)
                    fc_date = datetime.strptime(date_text, '%B %d, %Y')
                    try:
                        release_set = ReleaseSet.objects.get(week_date=fc_date)
                    except ReleaseSet.DoesNotExist:
                        release_set = ReleaseSet()
                        release_set.week_date = fc_date
                    release_set.sampler_uri = item[u'uri']
                    release_set.save()
                elif top_ten_match is not None:
                    recommender = top_ten_match.group(1)
                    date_text = top_ten_match.group(2)
                    recommend_date = datetime.strptime(date_text, '%B %d, %Y')
                    try:
                        release_set = ReleaseSet.objects.get(week_date=recommend_date)
                    except ReleaseSet.DoesNotExist:
                        release_set = ReleaseSet()
                        release_set.week_date = recommend_date
                    if recommender.lower() == 'adam':
                        release_set.adam_vote_uri = item[u'uri']
                    elif recommender.lower() == 'moksha':
                        release_set.moksha_vote_uri = item[u'uri']
                    elif recommender.lower() == 'jesse':
                        release_set.jesse_vote_uri = item[u'uri']
                    release_set.save()
                else:
                    print(item[u'name'])
            offset += output[u'limit']
            list_count = output[u'total']

    def process_lists(self, request, queryset):
        for release_set in queryset:
            self.load_sampler(request, release_set)
            self.load_recommendations(request, release_set)

    def load_sampler(self, request, release_set):
        sp = get_spotify_conn(request)
        if type(sp) is HttpResponseRedirect:
            return sp
        offset = 0
        list_count = 500
        albums = {}
        tracks = []
        while (offset < list_count):
            output = sp.user_playlist_tracks(sp.current_user()[u'id'],
                                             release_set.sampler_uri,
                                             offset=offset)
            # pprint(output)
            offset += output[u'limit']
            list_count = output[u'total']
            for item in output[u'items']:
                track = item[u'track']
                if track is None:
                    print('item[u\'track\'] is None for {}'.format(item))
                    continue
                tracks.append(track[u'uri'])
                try:
                    candidate = Release.objects.get(
                                           spotify_uri=track[u'album'][u'uri'])
                except Release.DoesNotExist:
                    candidate = Release(spotify_uri=track[u'album'][u'uri'],
                                        week=release_set)
                    if track[u'album'][u'uri'] not in albums.keys():
                        albums[track[u'album'][u'uri']] = candidate
                candidate.is_sample = True

        Release.objects.bulk_create(albums.values())
        handle_albums(sp, release_set, True)
        handle_artists(sp)
        release_set.determine_popularities()

        for track in tracks:
            try:
                track_obj = Track.objects.get(spotify_uri=track)
                track_obj.is_sample = True
                track_obj.save()
            except Track.DoesNotExist:
                print('TRACK NOT FOUND, OH SHIT! {}'.format(track))
            except Track.MultipleObjectsReturned:
                print('Hey, we already say this one... {}'.format(track))

    def load_recommendations(self, request, release_set):
        if release_set.adam_vote_uri is not None and len(release_set.adam_vote_uri) > 0:
            self.load_recommendation_list(request, release_set,
                                          release_set.adam_vote_uri, 'Adam')
        if release_set.jesse_vote_uri is not None and len(release_set.jesse_vote_uri) > 0:
            self.load_recommendation_list(request, release_set,
                                          release_set.jesse_vote_uri, 'Jesse')
        if release_set.moksha_vote_uri is not None and len(release_set.moksha_vote_uri) > 0:
            self.load_recommendation_list(request, release_set,
                                          release_set.moksha_vote_uri,
                                          'Moksha')

    def load_recommendation_list(self, request, release_set, list_uri,
                                 recommender):
        sp = get_spotify_conn(request)
        if type(sp) is HttpResponseRedirect:
            return sp
        offset = 0
        list_count = 500
        pos = 0
        while (offset < list_count):
            output = sp.user_playlist_tracks(sp.current_user()[u'id'],
                                             list_uri, offset=offset)
            # pprint(output)
            offset += output[u'limit']
            list_count = output[u'total']
            for item in output[u'items']:
                pos += 1
                track = item[u'track']
                album = track[u'album'][u'uri']
                try:
                    track_obj = Track.objects.get(spotify_uri=track[u'uri'])
                    track_obj.is_freshcut = True
                    track_obj.save()
                except Track.DoesNotExist:
                    print('TRACK NOT FOUND, OH SHIT! {}'.format(track[u'uri']))
                    continue
                except Track.MultipleObjectsReturned:
                    print('FOUND TWO VERSIONS OF THE TRACK! {}'.format(
                          track[u'uri']))
                    continue

                try:
                    release = Release.objects.get(spotify_uri=album)
                    release.is_freshcut = True
                    release.save()
                except Release.DoesNotExist:
                    print('ALBUM NOT FOUND, OH SHIT! {}'.format(album))
                except Release.MultipleObjectsReturned:
                    print('FOUND TWO VERSIONS OF THE ALBUM: {}'.format(album))

                if track_obj is not None and release is not None:
                    rec = Recommendation(type=recommender, release=release,
                                         track=track_obj, position=pos)
                    rec.save()

    def parse_sorting_hat(self, request, queryset):
        self.message_user(request, '{}: parse_sorting_hat'.format(datetime.now()))
        sp = get_spotify_conn(request)
        if type(sp) is HttpResponseRedirect:
            return sp

        week = queryset[0]
        if len(Release.objects.all()) == 0:
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
                    candidate = Release(spotify_uri=bits.group(2), sorting_hat_track_num=int(bits.group(3)),
                                        week=week, batch=len(candidate_list) % settings.GRINDER_BATCHES)
                    if bits.group(1) != '-':
                        candidate.sorting_hat_rank = int(bits.group(1))
                    candidate_list.append(candidate)

            # Shorten list for debugging
            candidate_list = candidate_list[0:50]
            Release.objects.bulk_create(candidate_list)
            self.message_user(request, '{0:d} releases processed to {1}'.format(len(candidate_list), week))
            print('{0:d} candidate releases'.format(len(candidate_list)))

        try:
            self.message_user(request, '{}: handle_albums'.format(datetime.now()))
            handle_albums(sp, week)
            self.message_user(request, '{}: delete_ineligible_releases'.format(datetime.now()))
            week.delete_ineligible_releases()
            print('{0:d} candidate releases eligible'.format((len(Release.objects.all()))))
            self.message_user(request, '{0:d} releases eligible to {1}'.format(len(Release.objects.all()), week))
            print('{0:d} candidate artists'.format((len(Artist.objects.all()))))
            self.message_user(request, '{}: delete_artists_with_no_release'.format(datetime.now()))
            delete_artists_with_no_release()
            self.message_user(request, '{}: handle_artists'.format(datetime.now()))
            handle_artists(sp)
            print('{0:d} candidate artists with a release'.format((len(Artist.objects.all()))))
            self.message_user(request, '{0:d} aritists added to {1}'.format(len(Artist.objects.all()), week))
            print('{0:d} genres'.format((len(Genre.objects.all()))))
            self.message_user(request, '{}: delete_empty_genres'.format(datetime.now()))
            delete_empty_genres()
            print('{0:d} genres with a release or artist'.format((len(Genre.objects.all()))))
            self.message_user(request, '{0:d} genres added to {1}'.format(len(Genre.objects.all()), week))
            self.message_user(request, '{}: done'.format(datetime.now()))
        except SpotifyException:
            self.parse_sorting_hat(request, queryset)
        return


class ReleaseAdmin(admin.ModelAdmin):
    list_display = ['title', 'artist_popularity', 'popularity_class', 'has_single', 'is_sample', 'is_freshcut']
    list_filter = ['popularity_class', 'is_sample', 'is_freshcut', 'has_single', 'batch', 'processed', 'eligible',
                   'genres']
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
                handle_album_list(sp, query_list)
                query_list = [album.spotify_uri]
        handle_album_list(sp, query_list)
        return


# Register your models here.
admin.site.register(Artist, ArtistAdmin)
admin.site.register(Release, ReleaseAdmin)
admin.site.register(ReleaseSet, ReleaseSetAdmin)
admin.site.register(Track, TrackAdmin)
admin.site.register(Genre, GenreAdmin)
