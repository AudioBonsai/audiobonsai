import pandas as pd

from ab_util import create_connection
from datetime import datetime, timedelta
from math import floor

if __name__ == '__main__':
    db_conn = create_connection()
    today_date = datetime.now()  # - timedelta(days=6)
    today_name = today_date.strftime("%Y%m%d")
    weekago_date = datetime.now() - timedelta(days=7)
    weekago_name = weekago_date.strftime("%Y%m%d")
    select_albums = 'SELECT spotify_uri, add_date, trade_rec from albums'
    select_artists = 'SELECT spotify_uri as artist_uri, add_date, orig_pop,' \
                     + ' orig_foll, current_pop, current_foll from artists'
    select_join = 'SELECT * from album_artists'
    select_today = 'SELECT * from pop_foll_{}'.format(today_name)
    select_weekago = 'SELECT * from pop_foll_{}'.format(weekago_name)
    album_df = pd.read_sql(select_albums, db_conn).set_index('spotify_uri')
    # print(album_df.head(10))
    artist_df = pd.read_sql(select_artists, db_conn).set_index('artist_uri')
    # print(artist_df.head(10))
    join_df = pd.read_sql(select_join, db_conn).set_index('artist_uri')
    # print(join_df.head(10))
    today_df = pd.read_sql(select_today, db_conn).set_index('artist_uri')
    # print(today_df.head(10))
    weekago_df = pd.read_sql(select_weekago, db_conn).set_index('artist_uri')
    # print(weekago_df.head(10))

    joined_df = artist_df.join(join_df).join(today_df, rsuffix='_today')
    joined_df = joined_df.join(weekago_df, rsuffix='_weekago')
    joined_df = joined_df.set_index('album_uri')
    joined_df = joined_df.join(album_df, rsuffix='_album')

    print(joined_df.head(10))
    joined_df['total_pop_diff'] = joined_df['current_pop'] - joined_df['orig_pop']
    joined_df['total_foll_diff'] = joined_df['current_foll'] - joined_df['orig_foll']
    joined_df['sixday_pop_diff'] = joined_df['pop_{}'.format(today_name)] - joined_df['pop_{}'.format(weekago_name)]
    joined_df['sixday_foll_diff'] = joined_df['foll_{}'.format(today_name)] - joined_df['foll_{}'.format(weekago_name)]
    joined_df['sixday_foll_diff_pct'] = (joined_df['sixday_foll_diff']/joined_df['pop_{}'.format(weekago_name)])*100
    joined_df['sixday_foll_diff_pct'] = joined_df['sixday_foll_diff_pct'].apply(lambda x: '{:.0f}'.format(x))
    print(joined_df.columns)
    # joined_df.to_csv('all_joined.csv')
    print('Total albums: {}'.format(len(joined_df)))
    total_pos = joined_df[joined_df['sixday_pop_diff'] > 0]
    total_pos = total_pos[total_pos['sixday_foll_diff'] > 0]
    print('Albums with total positive pop: {}'.format(len(total_pos)))
    print(total_pos.groupby('current_pop').count())
    # weekago_pop_pos = joined_df[joined_df['sixday_pop_diff'] > 3]
    # weekago_pop_pos = weekago_pop_pos.reset_index()
    # print(weekago_pop_pos.columns)
    # print(weekago_pop_pos.head(10))
    # weekago_pop_pos['url'] = weekago_pop_pos['index'].apply(lambda x: 'https://open.spotify.com/album/{}'.format(x[14:]))
    # print(weekago_pop_pos.head(10))
    # print('Albums with six day positive pop: {}'.format(len(weekago_pop_pos)))
    # print(weekago_pop_pos.groupby('sixday_pop_diff').count())
    # weekago_pop_pos.to_csv('all_joined.csv')
    trade_recs = total_pos[total_pos['trade_rec'] == 1]
    print(trade_recs.head(10))
    print('Albums with trade_recs: {}'.format(len(trade_recs)))
    print(trade_recs.groupby('current_pop').count())

    total_pos = total_pos[total_pos['current_pop'] > 20]
    total_pos = total_pos[total_pos['current_pop'] < 65]
    print('Albums with total positive pop with pop between 20 and 65: {}'.format(len(total_pos)))

    trade_recs = trade_recs[trade_recs['current_pop'] >= 20]
    trade_recs = trade_recs[trade_recs['current_pop'] <= 65]
    print('Albums with trade_recs with pop between 20 and 65: {}'.format(len(trade_recs)))
    # print(trade_recs.groupby('sixday_pop_diff').count())
    # print(trade_recs.groupby('sixday_foll_diff_pct').count())
