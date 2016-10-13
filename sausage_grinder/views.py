from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.template import loader
from sausage_grinder.models import CandidateSet, CandidateRelease, CandidateArtist, CandidateArtistRelease, \
    CandidateTrack, Genre

# Create your views here.


def sausage_grinder_index(request):
    context = {
        'release_count': CandidateRelease.objects.count(),
        'processed_releases': CandidateRelease.objects.filter(processed=True).count(),
        'eligible_releases': CandidateRelease.objects.filter(eligible=True).count(),
        'ineligible_releases': CandidateRelease.objects.filter(eligible=False).count(),
        'artist_count': CandidateArtist.objects.count(),
        'processed_artists': CandidateArtist.objects.filter(processed=True).count(),
        'genre_count': Genre.objects.count(),
    }
    template = loader.get_template('sausage_grinder/index.html')
    return HttpResponse(template.render(context, request))