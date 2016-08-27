from django.db import models
from django.utils import timezone
from datetime import datetime
from pprint import pprint

# Create your models here.


class CandidateSet(models.Model):
    week_date = models.DateField(auto_now=False, auto_now_add=False, default=timezone.now)

    def __str__(self):
        return self.week_date.strftime('%c')

    def __repr__(self):
        return self.week_date.strftime('%c')


class CandidateRelease(models.Model):
    sorting_hat_track_num = models.IntegerField(default=0)
    sorting_hat_rank = models.IntegerField(default=0)
    spotify_uri = models.CharField(max_length=255, default='', primary_key=True)
    batch = models.IntegerField(default=0)
    week = models.ForeignKey(CandidateSet, on_delete=models.CASCADE)
    release_date = models.DateField(auto_now=False, auto_now_add=False, null=True)
    title = models.CharField(max_length=255, default='', blank=True)
    processed = models.BooleanField(default=False)

    def __str__(self):
        return '{0} Rank:{1:6d}, Tracks:{2:2d}'.format(self.spotify_uri, self.sorting_hat_rank,
                                                       self.sorting_hat_track_num)

    def process(self, sp):
        if self.processed:
            return
        album_dets = sp.album(self.spotify_uri)
        if album_dets[u'release_date_precision'] != 'day':
            self.processed=True
            self.save()
            return
        pprint(album_dets)
        self.release_date = datetime.strptime(album_dets[u'release_date'], '%Y-%m-%d')
        self.title = album_dets[u'name']
        self.processed = True
        self.save()
