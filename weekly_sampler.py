from audiobonsai import wsgi, settings
from datetime import datetime
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
import pandas as pd
from pprint import pprint
from sausage_grinder.models import Artist, ReleaseSet
from spotify_helper.models import SpotifyUser
from spotipy import SpotifyException
from spotify_helper.helpers import get_user_conn


def attr_score(val, factor):
    return (val//factor)**2


def stat_score(df, in_col, out_col, multiplier=1):
    in_min = df[in_col].min()
    in_max = df[in_col].max()
    in_col_temp = in_col + "_temp"
    df.loc[:, in_col_temp] = df[in_col].apply(lambda x: x - in_min)
    factor = (in_max - in_min) // 25
    df.loc[:, out_col] = df[in_col_temp].apply(lambda x: attr_score(x, factor) * multiplier)
    return df


def build_artists_dict(week):
    artists = Artist.objects.filter(weeks=week)
    artists_dict = {}
    for artist in artists:
        release = artist.week_release(week)
        if release is None:
            print('No release found for {} in week {}'.format(artist, week))
            continue
        if release.release_type == 'single':
            continue
        #print('{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{}'.format(artist.popularity, artist.release_day_pop, artist.pop_change_from_release, artist.pop_change_pct_from_release, artist.followers, artist.release_day_foll, artist.followers_change_from_release, artist.followers_change_pct_from_release, artist))
        if artist.release_day_foll <= 100 and artist.followers_change_pct_from_release >= 100:
            #print('{}: foll pct reset'.format(artist))
            #print('{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{}'.format(artist.popularity, artist.release_day_pop, artist.pop_change_from_release, artist.pop_change_pct_from_release, artist.followers, artist.release_day_foll, artist.followers_change_from_release, artist.followers_change_pct_from_release, artist))
            artist.followers_change_pct_from_release = min(artist.followers_change_from_release, 100)
            #print('{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{}'.format(artist.popularity, artist.release_day_pop, artist.pop_change_from_release, artist.pop_change_pct_from_release, artist.followers, artist.release_day_foll, artist.followers_change_from_release, artist.followers_change_pct_from_release, artist))
        if artist.release_day_pop <= 10 and artist.pop_change_pct_from_release >= 100:
            #print('{}: pop pct reset'.format(artist))
            #print('{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{}'.format(artist.popularity, artist.release_day_pop, artist.pop_change_from_release, artist.pop_change_pct_from_release, artist.followers, artist.release_day_foll, artist.followers_change_from_release, artist.followers_change_pct_from_release, artist))
            artist.pop_change_pct_from_release = min(artist.pop_change_from_release*10, 100)
            #print('{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{:d}\t{}'.format(artist.popularity, artist.release_day_pop, artist.pop_change_from_release, artist.pop_change_pct_from_release, artist.followers, artist.release_day_foll, artist.followers_change_from_release, artist.followers_change_pct_from_release, artist))
        artists_dict[artist.spotify_uri] = {
            'obj': artist,
            'name': artist.name,
            'pop': artist.popularity,
            'pop_change': artist.pop_change_from_release,
            'pop_change_pct': artist.pop_change_pct_from_release,
            'foll': artist.followers,
            'foll_change': artist.followers_change_from_release,
            'foll_change_pct': artist.followers_change_pct_from_release,
            'release_day_foll': artist.release_day_foll,
            'release_day_pop': artist.release_day_pop,
            'release': release
        }
    return artists_dict


def build_artists_df(week):
    artists_dict = build_artists_dict(week)
    artists_df = pd.DataFrame.from_dict(artists_dict, orient='index')
    artists_df = stat_score(artists_df, 'pop', 'pop_score')
    artists_df = stat_score(artists_df, 'pop_change', 'pop_change_score')
    artists_df = stat_score(artists_df, 'pop_change_pct', 'pop_change_pct_score')
    artists_df = stat_score(artists_df, 'foll', 'foll_score')
    artists_df = stat_score(artists_df, 'foll_change', 'foll_change_score')
    artists_df = stat_score(artists_df, 'foll_change_pct', 'foll_change_score_pct')
    artists_df['final_score'] = artists_df['pop_score'] + \
                                artists_df['foll_score'] + \
                                artists_df['pop_change_pct_score'] + \
                                artists_df['pop_change_score'] + \
                                artists_df['foll_change_score'] + \
                                artists_df['foll_change_score_pct']
    return artists_df


if __name__ == '__main__':
    weeks = ReleaseSet.objects.all().order_by('-week_date')
    week = weeks[0]
    artists_df = build_artists_df(week)
    artists_df['category'] = pd.cut(artists_df['release_day_pop'], 10)
    #artists_df['category'] = pd.qcut(artists_df['release_day_foll'], 5, duplicates='drop')
    #top100_df = artists_df.sort_values(by='final_score', ascending=False)
    #top100_df = top100_df.drop_duplicates(subset='release', keep='first').head(200)
    #print(top100_df)

    playlist_name = 'Fresh Cuts: {}'.format(week.week_date.strftime('%b %d, %Y'))
    user = User.objects.get(username=settings.SPOTIFY_USERNAME)
    spotify_user = SpotifyUser.objects.get(user=user)
    track_list = []
    sp = get_user_conn(spotify_user, '127.0.0.1:8000')
    category_num = 1
    for category in sorted(artists_df['category'].unique()):
        category_df = artists_df[artists_df['category'] == category]
        category_df = category_df.sort_values(by='final_score', ascending=False)
        category_df = category_df.drop_duplicates(subset='release', keep='first')
        print('\nCategory {:d}'.format(category_num))
        print('{}: Min {:10d}, Max {:10d}, Count {:10d}'.format(category, category_df['release_day_pop'].min(), category_df['release_day_pop'].max(), len(category_df)))
        category_df = category_df.head(20)
        #print(category_df)
        #print('{}: Min {:10d}, Max {:10d}, Count {:10d}'.format(category, category_df['release_day_foll'].min(), category_df['release_day_foll'].max(), len(category_df)))

        #for release in top100_df['release'].values:
        for release in category_df['release'].values:
            try:
                album_dets = sp.album(release.spotify_uri)
            except requests.exceptions.ConnectionError:
                continue
            print('#{:03d} {:6s}: {}'.format(len(track_list)+1, release.release_type, release))
            if album_dets['type'] == 'single':
                track_list.append(album_dets['tracks']['items'][0]['uri'])
            else:
                track_dict = {}
                for track in album_dets['tracks']['items'][:5]:
                    if track['duration_ms'] not in track_dict.keys():
                        track_dict[track['duration_ms']] = []
                    track_dict[track['duration_ms']].append(track['uri'])
                track_times = sorted(list(track_dict.keys()))
                median_time_key = track_times[int(len(track_times)/2)]
                track_list.append(track_dict[median_time_key][0])
        category_num += 1

    '''
    #playlist = sp.user_playlist_create(user, playlist_name)
    #pprint(playlist)
    sausage_grinder_playlist = 'spotify:user:audiobonsai:playlist:6z8m6hjBXxClAZt3oYONCa'
    batch_size = 100
    offset = 0
    while offset < len(track_list):
        if offset == 0:
            #playlist_tracks = sp.user_playlist_replace_tracks(user, playlist['id'], track_list[offset:offset + batch_size])
            playlist_tracks = sp.user_playlist_replace_tracks(user, sausage_grinder_playlist, track_list[offset:offset + batch_size])
        else:
            #playlist_tracks = sp.user_playlist_add_tracks(user, playlist['id'], track_list[offset:offset + batch_size])
            playlist_tracks = sp.user_playlist_add_tracks(user, sausage_grinder_playlist, track_list[offset:offset + batch_size])
        offset += batch_size
        pprint(playlist_tracks)
    '''
