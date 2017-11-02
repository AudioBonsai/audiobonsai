from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse
from django.template import loader
from sausage_grinder.models import ReleaseSet, Release, Artist, \
    ArtistRelease, Track, Genre

# Create your views here.


def sausage_grinder_index(request):
    week_page = request.GET.get('week_page')
    pop_page = request.GET.get('pop_page')
    foll_page = request.GET.get('foll_page')
    week_p = Paginator(ReleaseSet.objects.order_by('-week_date'), 10)
    try:
        weeks = week_p.page(week_page)
    except PageNotAnInteger:
        weeks = week_p.page(1)
    except EmptyPage:
        weeks = week_p.page(week_p.num_pages)

    pop_p = Paginator(Artist.objects.order_by('-pop_change'), 10)
    try:
        pop_change = pop_p.page(pop_page)
    except PageNotAnInteger:
        pop_change = pop_p.page(1)
    except EmptyPage:
        pop_change = pop_p.page(pop_p.num_pages)

    foll_p = Paginator(Artist.objects.order_by('-followers_change', '-followers_change_pct'), 10)
    try:
        follower_change = foll_p.page(foll_page)
    except PageNotAnInteger:
        follower_change = foll_p.page(1)
    except EmptyPage:
        follower_change = foll_p.page(foll_p.num_pages)
    context = {
        #'release_count': Release.objects.count(),
        #'processed_releases': Release.objects.filter(processed=True).count(),
        #'eligible_releases': Release.objects.filter(eligible=True).count(),
        #'ineligible_releases': Release.objects.filter(eligible=False).count(),
        #'artist_count': Artist.objects.count(),
        #'processed_artists': Artist.objects.filter(processed=True).count(),
        #'genre_count': Genre.objects.count(),
        'pop_change': pop_change,
        'follower_change': follower_change,
        'weeks': weeks,
    }
    template = loader.get_template('sausage_grinder/index.html')
    return HttpResponse(template.render(context, request))


def week(request):
    week_date = request.GET.get('id')
    try:
        week = ReleaseSet.objects.get(week_date=week_date)
    except ReleaseSet.DoesNotExist:
        return HttpResponse('Well fuuuuuuuck.')

    page_no = request.GET.get('page')
    artists = Artist.objects.filter(weeks=week)
    artists2 = artists.filter(followers__lte=150000).order_by('-followers_change')
    p = Paginator(artists2, 10)
    try:
        artists = p.page(page_no)
    except PageNotAnInteger:
        artists = p.page(1)
    except EmptyPage:
        artists = p.page(p.num_pages)
    context = {
        'week': week,
        'artists': artists

    }
    template = loader.get_template('sausage_grinder/week.html')
    return HttpResponse(template.render(context, request))


def genre(request):
    genre_name = request.GET.get('name')
    if genre_name is  None or len(genre_name) == 0:
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
