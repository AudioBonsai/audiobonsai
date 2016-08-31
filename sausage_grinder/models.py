from django.db import models
from django.utils import timezone
from datetime import datetime, timedelta
from pprint import pprint

# Create your models here.


class CandidateSet(models.Model):
    week_date = models.DateField(auto_now=False, auto_now_add=False, default=timezone.now)

    def __str__(self):
        return self.week_date.strftime('%c')

    def __repr__(self):
        return self.week_date.strftime('%c')


class Genre(models.Model):
    name = models.CharField(max_length=255, primary_key=True)


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
    release_date = models.DateField(auto_now=False, auto_now_add=False, null=True)
    title = models.CharField(max_length=255, default='', blank=True)
    image_640 = models.URLField(null=True)
    image_300 = models.URLField(null=True)
    image_64 = models.URLField(null=True)

    def __str__(self):
        return '{0} Rank:{1:6d}, Tracks:{2:2d}'.format(self.spotify_uri, self.sorting_hat_rank,
                                                       self.sorting_hat_track_num)

    def mark_ineligible(self):
        self.eligible = False
        self.processed = True
        self.save()

    def check_eligility(self, album_dets):
        if album_dets[u'release_date_precision'] != 'day' or 'US' not in album_dets[u'available_markets']:
            self.mark_ineligible()
            return False
        elif  self.release_date > self.week.week_date or self.week.week_date - self.release_date > timedelta(days=7):
            self.mark_ineligible()
            return False
        elif album_dets[u'album_type'] == 'single' and len(album_dets[u'tracks'][u'items']) < 4:
            total_time = 0
            for track in album_dets[u'tracks'][u'items']:
                total_time += track[u'duration_ms']
            if total_time < 900000:
                self.mark_ineligible()
                return False
        return True

    def process(self, sp, album_dets):
        if self.processed:
            return

        self.release_date = datetime.strptime(album_dets[u'release_date'], '%Y-%m-%d').date()
        if not self.check_eligility(album_dets):
            return

        pprint(album_dets)
        self.title = album_dets[u'name']
        self.popularity = album_dets[u'popularity']
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
        self.processed = True
        self.save()
