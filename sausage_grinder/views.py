from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.template import loader
from sausage_grinder.models import ReleaseSet, Release, Artist, ArtistRelease, \
    Track, Genre

# Create your views here.


def sausage_grinder_index(request):
    context = {
        'release_count': Release.objects.count(),
        'processed_releases': Release.objects.filter(processed=True).count(),
        'eligible_releases': Release.objects.filter(eligible=True).count(),
        'ineligible_releases': Release.objects.filter(eligible=False).count(),
        'artist_count': Artist.objects.count(),
        'processed_artists': Artist.objects.filter(processed=True).count(),
        'genre_count': Genre.objects.count(),
    }
    template = loader.get_template('sausage_grinder/index.html')
    return HttpResponse(template.render(context, request))