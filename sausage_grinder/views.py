from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse
from django.template import loader
from sausage_grinder.models import Release, Artist, Genre

# Create your views here.


def sausage_grinder_index(request):
    artist_page = request.GET.get('page')

    artist_p = Paginator(Artist.objects.all(), 10)
    try:
        artists = artist_p.page(artist_page)
    except PageNotAnInteger:
        artists = artist_p.page(1)
    except EmptyPage:
        artists = artist_p.page(artist_p.num_pages)

    context = {
        'artists': artists,
    }
    template = loader.get_template('sausage_grinder/index.html')
    return HttpResponse(template.render(context, request))


def genre(request):
    genre_name = request.GET.get('name')
    if genre_name is None or len(genre_name) == 0:
        return genres(request)
    try:
        genre = Genre.objects.get(name=genre_name)
    except Genre.DoesNotExist:
        return genres(request, '{} not found'.format(genre_name))

    page_no = request.GET.get('page')
    p = Paginator(Release.objects.filter(genres=genre).order_by('-artist_popularity'), 10)
    try:
        releases = p.page(page_no)
    except PageNotAnInteger:
        releases = p.page(1)
    except EmptyPage:
        releases = p.page(p.num_pages)
    context = {
        'genre': genre,
        'releases': releases

    }
    template = loader.get_template('sausage_grinder/genre.html')
    return HttpResponse(template.render(context, request))


def genres(request, err_msg=None):
    template = loader.get_template('sausage_grinder/genres.html')
    return HttpResponse(template.render(context, request))


def artist(request):
    artist_id = request.GET.get('id')
    try:
        artist = Artist.objects.get(id=artist_id)
    except Artist.DoesNotExist:
        return HttpResponse('Well fuuuuuuuck.')
    context = {
        'artist': artist
    }
    template = loader.get_template('sausage_grinder/artist.html')
    return HttpResponse(template.render(context, request))


def release(request):
    release_id = request.GET.get('id')
    try:
        release = Release.objects.get(id=release_id)
    except Release.DoesNotExist:
        return HttpResponse('Well fuuuuuuuuck.')
    context = {
        'release': release,
    }
    template = loader.get_template('sausage_grinder/release.html')
    return HttpResponse(template.render(context, request))


def track(request):
    context = {}
    template = loader.get_template('sausage_grinder/track.html')
    return HttpResponse(template.render(context, request))
