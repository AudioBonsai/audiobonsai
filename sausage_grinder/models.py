from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from pprint import pprint
import re

# Create your models here.


REMIX_REGEX = re.compile('.*remix.*', re.IGNORECASE)
MIX_REGEX = re.compile('.*mix\)*$', re.IGNORECASE)
RADIOEDIT_REGEX = re.compile('.*Radio Edit*$', re.IGNORECASE)
REMASTER_REGEX = re.compile('.*remaster.*', re.IGNORECASE)
REISSUE_REGEX = re.compile('.*reissue.*', re.IGNORECASE)


class Genre(models.Model):
    name = models.CharField(max_length=255, primary_key=True)

    def __str__(self):
        return self.name

class Artist(models.Model):
    spotify_uri = models.CharField(max_length=255, default='')
    name = models.CharField(max_length=255, default='', blank=True)
    popularity = models.IntegerField(default=0)
    followers = models.IntegerField(default=0)
    processed = models.BooleanField(default=False)
    genres = models.ManyToManyField(Genre)

    def __str__(self):
        return self.name

    def set_popularity(self, pop, followers, today=timezone.now()):
        try:
            ArtistPopularity.objects.get(artist=self, pop_date=today)
        except ArtistPopularity.DoesNotExist:
            artpop = ArtistPopularity(artist=self, pop_date=today,
                                      popularity=pop, followers=followers)
            artpop.save()

    def most_recent_release(self, type='PRIMARY'):
        artistrelease_list = ArtistRelease.objects.filter(artist=self,
                                                          type=type)
        release = None
        for artistrelease in artistrelease_list:
            if release is None or \
               artistrelease.release.release_date < release.release_date:
                release = artistrelease.release
        return release

    def release_list(self, type='PRIMARY'):
        artistrelease_list = ArtistRelease.objects.filter(artist=self,
                                                          type=type)
        return [artistrelease.release for artistrelease in artistrelease_list]

    def process(self, sp, artist_dets):
        self.set_popularity(artist_dets[u'popularity'],
                            artist_dets[u'followers']['total'])
        # pprint(artist_dets)
        if self.processed:
            return

        self.orig_pop = artist_dets[u'popularity']
        self.orig_followers = artist_dets[u'followers']['total']
        self.orig_date = timezone.now()

        for genre in artist_dets[u'genres']:
            try:
                genre_obj = Genre.objects.get(name=genre)
            except Genre.DoesNotExist:
                genre_obj = Genre(name=genre)
                genre_obj.save()
            self.genres.add(genre_obj)

        for image in artist_dets[u'images']:
            if image[u'height'] == 640 or image[u'width'] == 640:
                self.image_640 = image[u'url']
            elif image[u'height'] == 600 or image[u'width'] == 600:
                self.image_600 = image[u'url']
            elif image[u'height'] == 300 or image[u'width'] == 300:
                self.image_300 = image[u'url']
            elif image[u'height'] == 64 or image[u'width'] == 64:
                self.image_64 = image[u'url']

        releases = self.release_set.all()
        for release in releases:
            for genre in self.genres.all():
                release.genres.add(genre)
            release.save()

        self.processed = True
        self.save()


class ArtistPopularity(models.Model):
    models.ForeignKey(Artist, on_delete=models.CASCADE)
    pop_date = models.DateField(auto_now=False, auto_now_add=False,
                                default=timezone.now)
    popularity = models.IntegerField(default=0)
    followers = models.IntegerField(default=0)


class Release(models.Model):
    sorting_hat_track_num = models.IntegerField(default=0)
    sorting_hat_rank = models.IntegerField(default=0)
    release_type = models.CharField(max_length=255, default='',
                                    choices=(('single', 'Single'),
                                             ('ep', 'EP'),
                                             ('album', 'Album')))
    eligible = models.BooleanField(default=True)
    processed = models.BooleanField(default=False)
    has_single = models.BooleanField(default=False)
    is_sample = models.BooleanField(default=False)
    is_freshcut = models.BooleanField(default=False)
    spotify_uri = models.CharField(max_length=255, default='')
    batch = models.IntegerField(default=0)
    genres = models.ManyToManyField(Genre, blank=True)
    artists = models.ManyToManyField(Artist, through='ArtistRelease',
                                     through_fields=('release', 'artist'))
    release_date = models.DateField(auto_now=False, auto_now_add=False,
                                    null=True)
    title = models.CharField(max_length=255, default='', blank=True)
    image_640 = models.URLField(blank=True)
    image_600 = models.URLField(blank=True)
    image_300 = models.URLField(blank=True)
    image_64 = models.URLField(blank=True)

    def artist_list(self, type='PRIMARY'):
        artistrelease_list = ArtistRelease.objects.filter(release=self,
                                                          type=type)
        if len(artistrelease_list) == 0:
            return ''
        formatted_list = ['<a href="artist?id={}">{}</a> pop: {} (+{}), \
                           followers: {:,d} (+{:,d}) pct change: {}%'.format(
                          artistrelease.artist_id, artistrelease.artist)
                          for artistrelease in artistrelease_list]
        if len(formatted_list) > 1:
            formatted_string = ' '.join([', '.join(formatted_list[:-1]), 'and',
                                         formatted_list[-1]])
        else:
            formatted_string = formatted_list[0]
        return formatted_string

    def recommendation_list(self):
        return Recommendation.objects.filter(release=self)

    def track_list(self):
        return Track.objects.filter(release=self).order_by('disc_number',
                                                           'track_number')

    def __str__(self):
        if len(self.title) == 0:
            return '{0} Rank:{1:6d}, Tracks:{2:2d}'.format(
                                                    self.spotify_uri,
                                                    self.sorting_hat_rank,
                                                    self.sorting_hat_track_num)
        else:
            return self.title + ' by ' + ', '.join([artist.name for artist in
                                                    self.artists.all()])

    def mark_ineligible(self):
        self.eligible = False
        self.processed = True
        self.save()

    def set_release_type(self, album_dets, save=False):
        if album_dets[u'album_type'] == 'album':
            self.release_type = 'album'
        else:
            total_time = 0
            for track in album_dets[u'tracks'][u'items']:
                # pprint(track)
                if not REMIX_REGEX.match(track[u'name']) and \
                   not MIX_REGEX.match(track[u'name']) and \
                   not RADIOEDIT_REGEX.match(track[u'name']):
                    total_time += track[u'duration_ms']
                    # print('{:d} added = {:d}'.format(track[u'duration_ms'],
                    #                                  total_time))

            if total_time <= 600000:
                self.release_type = 'single'
            else:
                self.release_type = 'ep'

        if save:
            self.save()

    def check_eligility(self, album_dets):
        if album_dets[u'release_date_precision'] != 'day' or \
            (len(album_dets[u'available_markets']) > 0 and
             'US' not in album_dets[u'available_markets']):
            self.mark_ineligible()
            return False
        elif REMIX_REGEX.match(self.title) or \
                REISSUE_REGEX.match(self.title) or \
                REMASTER_REGEX.match(self.title):
            self.mark_ineligible()
            return False
        elif album_dets[u'album_type'] == 'single' and \
                len(album_dets[u'tracks'][u'items']) < 4:
            total_time = 0
            for track in album_dets[u'tracks'][u'items']:
                if not REMIX_REGEX.match(track[u'name']):
                    total_time += track[u'duration_ms']

            if total_time < 900000:
                self.mark_ineligible()
                return (False, None)
        return True

    def determine_popularity(self):
        artist_links = ArtistRelease.objects.filter(release_id=self.id,
                                                    type='PRIMARY')
        self.artist_popularity = 0
        for link in artist_links:
            artist = Artist.objects.get(id=link.artist_id)
            if artist.popularity > self.artist_popularity:
                self.artist_popularity = artist.popularity
        self.popularity_class = 'unknown'
        self.artist_popularity = self.popularity
        if self.artist_popularity >= 51:
            self.popularity_class = 'top'
        elif self.artist_popularity >= 26:
            self.popularity_class = 'verge'
        elif self.artist_popularity >= 11:
            self.popularity_class = 'unheralded'
        elif self.artist_popularity >= 1:
            self.popularity_class = 'underground'
        self.save()

    def process(self, sp, album_dets, all_eligible=False):
        track_list = []
        if self.processed:
            return track_list

        try:
            self.release_date = datetime.strptime(album_dets[u'release_date'],
                                                  '%Y-%m-%d').date()
        except ValueError:
            self.mark_ineligible()
            return track_list
        try:
            self.title = album_dets[u'name']
            # print(album_dets[u'name'])
        except UnicodeEncodeError:
            self.mark_ineligible()
            return track_list
        if not (all_eligible or self.check_eligility(album_dets)):
            return track_list

        self.popularity = album_dets[u'popularity']
        for artist in album_dets[u'artists']:
            try:
                artist_obj = Artist.objects.get(spotify_uri=artist[u'uri'])
            except Artist.DoesNotExist:
                artist_obj = Artist(spotify_uri=artist[u'uri'],
                                    name=artist[u'name'])
                artist_obj.save()
                # print('- ' + artist[u'name'])
            ArtistRelease.objects.create(artist=artist_obj, release=self)
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
            elif image[u'height'] == 600 or image[u'width'] == 600:
                self.image_600 = image[u'url']
            elif image[u'height'] == 300 or image[u'width'] == 300:
                self.image_300 = image[u'url']
            elif image[u'height'] == 64 or image[u'width'] == 64:
                self.image_64 = image[u'url']
        '''
        for track in album_dets[u'tracks'][u'items']:
            track_obj = Track(spotify_uri=track[u'uri'])
            track_obj.process_track(track, self)
            track_list.append(track_obj)
        '''
        self.set_release_type(album_dets)
        self.processed = True
        self.save()
        return track_list


class ArtistRelease(models.Model):
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE)
    release = models.ForeignKey(Release, on_delete=models.CASCADE)
    type = models.CharField(max_length=8, default='PRIMARY',
                            choices=(('PRIMARY', 'PRIMARY'),
                                     ('FEATURED', 'FEATURED')))


class Track(models.Model):
    spotify_uri = models.CharField(max_length=255, default='')
    title = models.CharField(max_length=255, default='', blank=True)
    release = models.ForeignKey(Release, on_delete=models.CASCADE)
    duration = models.IntegerField(default=0)
    track_number = models.IntegerField(default=0)
    disc_number = models.IntegerField(default=0)
    is_sample = models.BooleanField(default=False)
    is_freshcut = models.BooleanField(default=False)
    single_release_date = models.DateField(auto_now=False, auto_now_add=False,
                                           null=True)

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
                artist_obj = Artist.objects.get(spotify_uri=artist[u'uri'])
            except Artist.DoesNotExist:
                artist_obj = Artist(spotify_uri=artist[u'uri'],
                                    name=artist[u'name'])
                artist_obj.save()
            if artist_obj not in release.artists.all():
                ArtistRelease.objects.create(artist=artist_obj,
                                             release=release, type='FEATURED')


class Recommendation(models.Model):
    JESSE = 'Jesse'
    JUSTIN = 'Moksha'
    ADAM = 'Adam'
    AUDIOBONSAI = 'Audio Bonsai'
    METACRITIC = 'MC'
    SPOTIFY = 'SP'
    ALLMUSIC = 'AM'
    CONSEQUENCE = 'QOS'
    REC_CHOICES = (
        (JESSE, 'Jesse'),
        (JUSTIN, 'Moksha'),
        (ADAM, 'Adam'),
        (AUDIOBONSAI, 'Audio Bonsai'),
        (METACRITIC, 'Meta Critic'),
        (SPOTIFY, 'Spotify'),
        (ALLMUSIC, 'All Music'),
        (CONSEQUENCE, 'Consequence of Sound')
    )
    type = models.CharField(max_length=25, choices=REC_CHOICES)
    release = models.ForeignKey(Release, on_delete=models.CASCADE)
    track = models.ForeignKey(Track, on_delete=models.CASCADE)
    position = models.IntegerField(default=0)
