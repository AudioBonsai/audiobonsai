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
    df.loc[:, in_col] = df[in_col].apply(lambda x: x - in_min)
    factor = (in_max - in_min) // 25
    df.loc[:, out_col] = df[in_col].apply(lambda x: attr_score(x, factor) * multiplier)
    return df


def build_artists_dict(week):
    artists = Artist.objects.filter(weeks=week)
    artists_dict = {}
    for artist in artists:
        artists_dict[artist.spotify_uri] = {
            'obj': artist,
            'name': artist.name,
            'pop': artist.popularity,
            'pop_change': artist.pop_change_from_release,
            'pop_change_pct': artist.pop_change_pct_from_release,
            'foll': artist.followers,
            'foll_change': artist.followers_change_from_release,
            'foll_change_pct': artist.followers_change_pct_from_release
        }
    return artists_dict


def build_artists_df(week):
    artists_dict = build_artists_dict(week)
    artists_df = pd.DataFrame.from_dict(artists_dict, orient='index')
    stat_score(artists_df, 'pop', 'pop_score')
    stat_score(artists_df, 'pop_change', 'pop_change_score')
    stat_score(artists_df, 'pop_change_pct', 'pop_change_pct_score')
    stat_score(artists_df, 'foll', 'foll_score')
    stat_score(artists_df, 'foll_change', 'foll_change_score')
    stat_score(artists_df, 'foll_change_pct', 'foll_change_score_pct')
    artists_df['final_score'] = artists_df['pop_score'] + \
                                artists_df['pop_change_score'] + \
                                artists_df['pop_change_pct_score'] + \
                                artists_df['foll_score'] + \
                                artists_df['foll_change_score'] + \
                                artists_df['foll_change_score_pct']
    return artists_df


if __name__ == '__main__':
    weeks = ReleaseSet.objects.all().order_by('-week_date')
    week = weeks[8]
    artists_df = build_artists_df(week)
    top100_df = artists_df.sort_values(by='final_score', ascending=False).head(100)
    top100_df['release'] = top100_df['obj'].apply(lambda x: x.week_release(week))

    playlist_name = 'Fresh Cuts: {}'.format(week.week_date.strftime('%b %d, %Y'))
    user = User.objects.get(username=settings.SPOTIFY_USERNAME)
    spotify_user = SpotifyUser.objects.get(user=user)
    track_list = []
    sp = get_user_conn(spotify_user, '127.0.0.1:8000')
    for release in top100_df['release'].values:
        album_dets = sp.album(release.spotify_uri)
        print(release)
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

    playlist = sp.user_playlist_create(user, playlist_name)
    pprint(playlist)
    playlist_tracks = sp.user_playlist_add_tracks(user, playlist['id'], track_list)
    pprint(playlist_tracks)
