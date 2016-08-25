from django.contrib.auth.models import User
from django.db import models

# Create your models here.


class SpotifyUser(models.Model):
    spotify_username = models.CharField(max_length=255, blank=True, default='')
    spotify_token = models.CharField(max_length=255, blank=True, default='')
    return_path = models.CharField(max_length=255, blank=True, default='')
    user = models.OneToOneField(User, on_delete=models.CASCADE)



