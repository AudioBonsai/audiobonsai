import pandas as pd

from ab_util import create_connection
from datetime import datetime, timedelta

if __name__ == '__main__':
    db_conn = create_connection()
    today_date = datetime.now() - timedelta(days=6)
    today_name = today_date.strftime("%Y%m%d")
    sixago_date = datetime.now() - timedelta(days=7)
    sixago_name = sixago_date.strftime("%Y%m%d")
    select_albums = 'SELECT spotify_uri, add_date, trade_rec from albums'
    select_artists = 'SELECT spotify_uri as artist_uri, add_date, orig_pop,' \
                     + ' orig_foll, current_pop, current_foll from artists'
    select_join = 'SELECT * from album_artists'
    select_today = 'SELECT * from pop_foll_{}'.format(today_name)
    select_sixago = 'SELECT * from pop_foll_{}'.format(sixago_name)
    album_df = pd.read_sql(select_albums, db_conn).set_index('spotify_uri')
    # print(album_df.head(10))
    artist_df = pd.read_sql(select_artists, db_conn).set_index('artist_uri')
    # print(artist_df.head(10))
    join_df = pd.read_sql(select_join, db_conn).set_index('artist_uri')
    # print(join_df.head(10))
    today_df = pd.read_sql(select_today, db_conn).set_index('artist_uri')
    # print(today_df.head(10))
    sixago_df = pd.read_sql(select_sixago, db_conn).set_index('artist_uri')
    # print(sixago_df.head(10))

    joined_df = artist_df.join(join_df).join(today_df, rsuffix='_today')
    joined_df = joined_df.join(sixago_df, rsuffix='_sixago')
    joined_df = joined_df.set_index('album_uri')
    joined_df = joined_df.join(album_df, rsuffix='_album')

    print(joined_df.head(10))
    joined_df['total_pop_diff'] = joined_df['current_pop'] - joined_df['orig_pop']
    joined_df['total_foll_diff'] = joined_df['current_foll'] - joined_df['orig_foll']
    joined_df['sixday_pop_diff'] = joined_df['pop_{}'.format(today_name)] - joined_df['pop_{}'.format(sixago_name)]
    joined_df['sixday_foll_diff'] = joined_df['foll_{}'.format(today_name)] - joined_df['foll_{}'.format(sixago_name)]
    print(joined_df.columns)
    # joined_df.to_csv('all_joined.csv')
    print('Total albums: {}'.format(len(joined_df)))
    # total_pop_pos = joined_df[joined_df['total_pop_diff'] > 0]
    # print('Albums with total positive pop: {}'.format(len(total_pop_pos)))
    # print(total_pop_pos.groupby('total_pop_diff').count())
    sixago_pop_pos = joined_df[joined_df['sixday_pop_diff'] > 3]
    sixago_pop_pos = sixago_pop_pos.reset_index()
    print(sixago_pop_pos.columns)
    print(sixago_pop_pos.head(10))
    sixago_pop_pos['url'] = sixago_pop_pos['index'].apply(lambda x: 'https://open.spotify.com/album/{}'.format(x[14:]))
    print(sixago_pop_pos.head(10))
    print('Albums with six day positive pop: {}'.format(len(sixago_pop_pos)))
    print(sixago_pop_pos.groupby('sixday_pop_diff').count())
    sixago_pop_pos.to_csv('all_joined.csv')
