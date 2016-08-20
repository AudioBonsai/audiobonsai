from audiobonsai import settings
from django.contrib import admin
import re
from sausage_grinder.models import CandidateSet, CandidateRelease
import spotipy
from urllib.request import urlopen

# Register your models here.


class CandidateSetAdmin(admin.ModelAdmin):
    list_display = ['week_date']
    ordering = ['week_date']
    fields = ['week_date']
    actions = ['parse_sorting_hat']

    def parse_sorting_hat(self, request, queryset):
        week = queryset[0]
        response = urlopen('http://everynoise.com/spotify_new_releases.html')
        html = response.read().decode("utf-8")
        track_items = html.split('</div><div class=')
        match_string = re.compile(' title="artist rank:.*')
        group_text = ' title="artist rank: ([0-9,-]+)"><a onclick=".*" href="(spotify:album:.*)">' \
                     '<span class=.*>.*</span> <span class=.*>.*</span></a> ' \
                     '<span class="play trackcount" albumid=spotify:album:.* nolink=true onclick=".*">' \
                     '([0-9]+)</span>'
        group_string = re.compile(group_text)
        candidate_list = []

        for track in track_items:
            for match in match_string.findall(track):
                bits = group_string.match(match)
                if bits is None:
                    continue
                if int(bits.group(3)) > 2:
                    candidate = CandidateRelease(spotify_uri=bits.group(2), sorting_hat_track_num=int(bits.group(3)),
                                                 week=week, batch=len(candidate_list) % settings.GRINDER_BATCHES)
                    if bits.group(1) != '-':
                        candidate.sorting_hat_rank = int(bits.group(1))
                    candidate_list.append(candidate)

        CandidateRelease.objects.bulk_create(candidate_list)
        self.message_user(request, '{0:d} tracks added to {1}'.format(len(candidate_list), set))
        return


class CandidateReleaseAdmin(admin.ModelAdmin):
    list_display = ['batch', 'spotify_uri', 'sorting_hat_rank', 'sorting_hat_track_num']
    list_filter = ['batch']
    ordering = ['batch', 'sorting_hat_rank', 'spotify_uri']
    fields = ['spotify_uri']
    actions = ['process_album']

    def process_album(self, request, queryset):
        #token = sputil.prompt_for_user_token(settings.SPOTIFY_USERNAME, settings.SPOTIFY_SCOPE)
        #sp = spotipy.Spotify(auth=token)
        return

# Register your models here.
admin.site.register(CandidateRelease, CandidateReleaseAdmin)
admin.site.register(CandidateSet, CandidateSetAdmin)
