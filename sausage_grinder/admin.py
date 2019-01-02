from django.contrib import admin
from django.http import HttpResponseRedirect
from pprint import pprint
from sausage_grinder.models import Release, Genre, Artist, Track
from spotify_helper.helpers import get_spotify_conn


# Register your models here.


class GenreAdmin(admin.ModelAdmin):
    list_display = ['name']
    fields = ['name']


class TrackAdmin(admin.ModelAdmin):
    list_display = ['title', 'single_release_date', 'is_sample', 'is_freshcut',
                    'release', 'disc_number', 'track_number', 'duration',
                    'spotify_uri']
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


class ReleaseAdmin(admin.ModelAdmin):
    list_display = ['title', 'has_single', 'is_sample', 'is_freshcut']
    list_filter = ['is_sample', 'is_freshcut', 'has_single', 'batch',
                   'processed', 'eligible', 'genres']
    ordering = ['-sorting_hat_rank', 'batch', 'processed', 'title']
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
admin.site.register(Track, TrackAdmin)
admin.site.register(Genre, GenreAdmin)
