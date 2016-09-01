from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from pprint import pprint
import re

# Create your models here.


REMIX_REGEX = re.compile('.*remix.*', re.IGNORECASE)
REMASTER_REGEX = re.compile('.*remaster.*', re.IGNORECASE)
REISSUE_REGEX = re.compile('.*reissue.*', re.IGNORECASE)


class CandidateSet(models.Model):
    week_date = models.DateField(auto_now=False, auto_now_add=False, default=timezone.now)

    def __str__(self):
        return self.week_date.strftime('%c')

    def __repr__(self):
        return self.week_date.strftime('%c')


class Genre(models.Model):
    name = models.CharField(max_length=255, primary_key=True)


class CandidateArtist(models.Model):
    spotify_uri = models.CharField(max_length=255, default='', primary_key=True)
    name = models.CharField(max_length=255, default='', blank=True)

    def __str__(self):
        return self.name


class CandidateRelease(models.Model):
    sorting_hat_track_num = models.IntegerField(default=0)
    sorting_hat_rank = models.IntegerField(default=0)
    popularity = models.IntegerField(default=0)
    eligible = models.BooleanField(default=True)
    processed = models.BooleanField(default=False)
    spotify_uri = models.CharField(max_length=255, default='', primary_key=True)
    batch = models.IntegerField(default=0)
    week = models.ForeignKey(CandidateSet, on_delete=models.CASCADE)
    genres = models.ManyToManyField(Genre)
    artists = models.ManyToManyField(CandidateArtist, through='CandidateArtistRelease',
                                     through_fields=('release', 'artist'))
    release_date = models.DateField(auto_now=False, auto_now_add=False, null=True)
    title = models.CharField(max_length=255, default='', blank=True)
    image_640 = models.URLField(null=True)
    image_300 = models.URLField(null=True)
    image_64 = models.URLField(null=True)

    def __str__(self):
        if len(self.title) == 0:
            return '{0} Rank:{1:6d}, Tracks:{2:2d}'.format(self.spotify_uri, self.sorting_hat_rank,
                                                           self.sorting_hat_track_num)
        else:
            return self.title + ' by ' + ', '.join([artist.name for artist in self.artists.all()])

    def mark_ineligible(self):
        self.eligible = False
        self.processed = True
        self.save()

    def check_eligility(self, album_dets):
        if album_dets[u'release_date_precision'] != 'day' or 'US' not in album_dets[u'available_markets']:
            self.mark_ineligible()
            return False
        elif self.release_date > self.week.week_date or self.week.week_date - self.release_date > timedelta(days=7):
            self.mark_ineligible()
            return False
        elif REMIX_REGEX.match(self.title) or REISSUE_REGEX.match(self.title) or REMASTER_REGEX.match(self.title):
            self.mark_ineligible()
            return False
        elif album_dets[u'album_type'] == 'single' and len(album_dets[u'tracks'][u'items']) < 4:
            total_time = 0
            for track in album_dets[u'tracks'][u'items']:
                if not REMIX_REGEX.match(track[u'name']):
                    total_time += track[u'duration_ms']

            if total_time < 900000:
                self.mark_ineligible()
                return (False, None)
        return True

    def process(self, sp, album_dets):
        track_list = []
        if self.processed:
            return track_list

        self.release_date = datetime.strptime(album_dets[u'release_date'], '%Y-%m-%d').date()
        self.title = album_dets[u'name']
        if not self.check_eligility(album_dets):
            return track_list

        self.popularity = album_dets[u'popularity']
        for artist in album_dets[u'artists']:
            try:
                artist_obj = CandidateArtist.objects.get(spotify_uri=artist[u'uri'])
            except CandidateArtist.DoesNotExist:
                artist_obj = CandidateArtist(spotify_uri=artist[u'uri'], name=artist[u'name'])
                artist_obj.save()
            CandidateArtistRelease.objects.create(artist=artist_obj, release=self)
        for genre in album_dets[u'genres']:
            try:
                genre_obj = Genre.object.get(name=genre)
            except Genre.DoesNotExist:
                genre_obj = Genre(name=genre)
                genre_obj.save()
            self.genres.add(genre_obj)
        for image in album_dets[u'images']:
            if image[u'height'] == 640 or image[u'width'] == 640:
                self.image_640 = image[u'url']
            elif image[u'height'] == 300 or image[u'width'] == 300:
                self.image_300 = image[u'url']
            elif image[u'height'] == 64 or image[u'width'] == 64:
                self.image_64 = image[u'url']
        for track in album_dets[u'tracks'][u'items']:
            track_obj = CandidateTrack(spotify_uri=track[u'uri'])
            track_obj.process_track(track, self)
            track_list.append(track_obj)

        self.processed = True
        self.save()
        return track_list


class CandidateArtistRelease(models.Model):
    artist = models.ForeignKey(CandidateArtist, on_delete=models.CASCADE)
    release = models.ForeignKey(CandidateRelease, on_delete=models.CASCADE)
    type = models.CharField(max_length=8, default='PRIMARY', choices=(('PRIMARY', 'PRIMARY'), ('FEATURED', 'FEATURED')))


class CandidateTrack(models.Model):
    spotify_uri = models.CharField(max_length=255, default='', primary_key=True)
    title = models.CharField(max_length=255, default='', blank=True)
    release = models.ForeignKey(CandidateRelease, on_delete=models.CASCADE)
    duration = models.IntegerField(default=0)
    track_number = models.IntegerField(default=0)
    disc_number = models.IntegerField(default=0)

    def __str__(self):
        if len(self.title) == 0:
            return self.spotify_uri
        else:
            return self.title

    def process_track(self, track_dets, release):
        self.title = track_dets[u'name']
        self.release = release
        self.duration = track_dets[u'duration_ms']
        self.disc_number = track_dets[u'disc_number']
        self.track_number = track_dets[u'track_number']

        for artist in track_dets[u'artists']:
            try:
                artist_obj = CandidateArtist.objects.get(spotify_uri=artist[u'uri'])
            except CandidateArtist.DoesNotExist:
                artist_obj = CandidateArtist(spotify_uri=artist[u'uri'], name=artist[u'name'])
                artist_obj.save()
            if artist_obj not in release.artists.all():
                CandidateArtistRelease.objects.create(artist=artist_obj, release=release, type='FEATURED')
