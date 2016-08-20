from django.db import models
from django.utils import timezone
from datetime import datetime

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

    def __str__(self):
        return '{0} Rank:{1:6d}, Tracks:{2:2d}'.format(self.spotify_uri, self.sorting_hat_rank,
                                                       self.sorting_hat_track_num)
