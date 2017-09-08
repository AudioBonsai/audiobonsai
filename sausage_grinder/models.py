from django.db import models, IntegrityError
from django.utils import timezone
from datetime import datetime, timedelta
from pprint import pprint
import re

# Create your models here.


REMIX_REGEX = re.compile('.*remix.*', re.IGNORECASE)
REMASTER_REGEX = re.compile('.*remaster.*', re.IGNORECASE)
REISSUE_REGEX = re.compile('.*reissue.*', re.IGNORECASE)


class ReleaseSet(models.Model):
    week_date = models.DateField(auto_now=False, auto_now_add=False,
                                 default=timezone.now)
    sampler_uri = models.CharField(max_length=255, default='', blank=True)
    jesse_vote_uri = models.CharField(max_length=255, default='', blank=True)
    moksha_vote_uri = models.CharField(max_length=255, default='', blank=True)
    adam_vote_uri = models.CharField(max_length=255, default='', blank=True)

    #def determine_popularities(self):
    #    for release in Release.objects.filter(week=self.id):
    #        release.determine_popularity()

    def delete_ineligible_releases(self):
        ineligible_list = Release.objects.filter(eligible=False, week=self)
        [ineligible.delete() for ineligible in ineligible_list]

    def __str__(self):
        return self.week_date.strftime('%c')

    def __repr__(self):
        return self.week_date.strftime('%c')


class Genre(models.Model):
    name = models.CharField(max_length=255, primary_key=True)

    def __str__(self):
        return self.name


class Artist(models.Model):
    spotify_uri = models.CharField(max_length=255, default='')
    name = models.CharField(max_length=255, default='', blank=True)
    popularity = models.IntegerField(default=0)
    followers = models.IntegerField(default=0)
    release_day_pop = models.IntegerField(default=0)
    release_day_foll = models.IntegerField(default=0)
    max_pop = models.IntegerField(default=0)
    max_foll = models.IntegerField(default=0)
    processed = models.BooleanField(default=False)
    genres = models.ManyToManyField(Genre)
    image_640 = models.URLField(null=True)
    image_600 = models.URLField(null=True)
    image_300 = models.URLField(null=True)
    image_64 = models.URLField(null=True)

    def __str__(self):
        return self.name


    def set_popularity(self, pop, release_day=False):
        self.popularity = pop
        if release_day:
            self.release_day_pop = pop
        if pop > self.max_pop:
            self.max_pop = pop
        self.save()

    def set_followers(self, followers, release_day=False):
        self.followers = followers
        if release_day:
            self.release_day_foll = followers
        if followers > self.max_foll:
            self.max_foll = followers
        self.save()

    def release_list(self, type='PRIMARY'):
        artistrelease_list = ArtistRelease.objects.filter(artist=self,
                                                          type=type)
        return [artistrelease.release for artistrelease in artistrelease_list]
        #if len(artistrelease_list) == 0:
        #    return ''
        #formatted_list = ['<a href="release?id={}">{}</a> from {}'.format(
        #                  artistrelease.release_id, artistrelease.release, artistrelease.release.week.week_date)
        #                  for artistrelease in artistrelease_list]
        #if len(formatted_list) > 1:
        #    formatted_string = ' '.join([', '.join(formatted_list[:-1]), 'and',
        #                                 formatted_list[-1]])
        #else:
        #    formatted_string = formatted_list[0]
        #return formatted_string

    def process(self, sp, artist_dets):
        self.set_popularity(artist_dets[u'popularity'], True)
        pprint(artist_dets)
        self.set_followers(artist_dets[u'followers']['total'], True)
        if self.processed:
            return

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

            link = ArtistRelease.objects.get(artist=self, release=release)
            if link.type == 'PRIMARY':
                self.process_album(sp, release)
            release.save()

        self.processed = True
        self.save()

    def process_album(self, sp, release):
        artist_singles = sp.artist_albums(self.spotify_uri,
                                          album_type='single', country='US')
        single_uris = []
        for single in artist_singles[u'items']:
            if single[u'uri'] == release.spotify_uri:
                continue
            single_uris.append(single[u'uri'])

        if len(single_uris) > 0:
            single_dets = sp.albums(single_uris)

            for single in single_dets[u'albums']:
                try:
                    release_date = datetime.strptime(single[u'release_date'],
                                                     '%Y-%m-%d').date()
                except ValueError:
                    continue
                if release.week.week_date - release_date > timedelta(days=120):
                    continue
                try:
                    release_tracks = release.track_set.filter(title=single[u'name'])
                    for release_track in release_tracks:
                        release_track.single_release_date = release_date
                        release_track.save()
                        release.has_single = True
                        release.save()
                except Track.DoesNotExist:
                    # None Found
                    for single_track in single[u'tracks'][u'items']:
                        try:
                            release_tracks = release.track_set.filter(title=single_track[u'name'])
                            for release_track in release_tracks:
                                release_track.single_release_date = release_date
                                release_track.save()
                                release.has_single = True
                                release.save()
                        except Track.DoesNotExist:
                            # No matches
                            pass


class Release(models.Model):
    sorting_hat_track_num = models.IntegerField(default=0)
    sorting_hat_rank = models.IntegerField(default=0)
    popularity = models.IntegerField(default=0)
    artist_popularity = models.IntegerField(default=0)
    popularity_class = models.CharField(max_length=255, default='',
                                        choices=(('top', 'Top 50'),
                                                 ('verge', 'On the Verge'),
                                                 ('unheralded', 'Unheralded'),
                                                 ('underground', 'Underground'),
                                                 ('unknown', 'Unknown')))
    eligible = models.BooleanField(default=True)
    processed = models.BooleanField(default=False)
    has_single = models.BooleanField(default=False)
    is_sample = models.BooleanField(default=False)
    is_freshcut = models.BooleanField(default=False)
    spotify_uri = models.CharField(max_length=255, default='')
    batch = models.IntegerField(default=0)
    week = models.ForeignKey(ReleaseSet, on_delete=models.CASCADE)
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
        formatted_list = ['<a href="artist?id={}">{}</a>'.format(
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
        return Track.objects.filter(release=self).order_by('disc_number', 'track_number')

    def __str__(self):
        if len(self.title) == 0:
            return '{0} Rank:{1:6d}, Tracks:{2:2d}'.format(self.spotify_uri,
                                                           self.sorting_hat_rank,
                                                           self.sorting_hat_track_num)
        else:
            return self.title + ' by ' + ', '.join([artist.name for artist in
                                                    self.artists.all()])

    def mark_ineligible(self):
        self.eligible = False
        self.processed = True
        self.save()

    def check_eligility(self, album_dets):
        if album_dets[u'release_date_precision'] != 'day' or \
            (len(album_dets[u'available_markets']) > 0 and \
            'US' not in album_dets[u'available_markets']):
            self.mark_ineligible()
            return False
        elif self.release_date > self.week.week_date or self.week.week_date - self.release_date > timedelta(days=7):
            self.mark_ineligible()
            return False
        elif REMIX_REGEX.match(self.title) or REISSUE_REGEX.match(self.title) or REMASTER_REGEX.match(self.title):
            self.mark_ineligible()
            return False
        '''
        elif album_dets[u'album_type'] == 'single' and len(album_dets[u'tracks'][u'items']) < 4:
            total_time = 0
            for track in album_dets[u'tracks'][u'items']:
                if not REMIX_REGEX.match(track[u'name']):
                    total_time += track[u'duration_ms']

            if total_time < 900000:
                self.mark_ineligible()
                return (False, None)
        '''
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
            print(album_dets[u'name'])
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
                print('- ' + artist[u'name'])
                artist_obj.save()
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
        for track in album_dets[u'tracks'][u'items']:
            track_obj = Track(spotify_uri=track[u'uri'])
            track_obj.process_track(track, self)
            track_list.append(track_obj)

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
