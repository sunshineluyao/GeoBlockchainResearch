import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import numpy as np
import os


def load_tweets(file_path, dictionary, gdf_countries):

    df = pd.read_parquet(file_path)
    df = df.reset_index(drop=True)
    print('Number of tweets:', len(df))

    # Filter out tweets by negative words
    all_negative_words = []
    for key, value in dictionary.items():
        try:
            negative_words = value['Negative Word'].dropna().tolist()
            all_negative_words += negative_words
        except:
            pass
    all_negative_words = list(set(all_negative_words))
    pattern = '|'.join(all_negative_words)
    df = df[~df['text'].str.contains(pattern, case=False, na=False)]
    print('Number of tweets without negative words:', len(df))

    # Use longitude and latitude as geometry
    df['geometry'] = df.apply(lambda row: Point(row['longitude'], row['latitude']), axis=1)
    gdf = gpd.GeoDataFrame(df, geometry='geometry')
    gdf = gdf.set_crs(epsg=4326)
    gdf['longitude'] = gdf['longitude'].astype(float)
    gdf['latitude'] = gdf['latitude'].astype(float)

    # Assign specific country to each tweet
    gdf = gpd.sjoin(gdf, gdf_countries, how="left", op="within")

    return gdf


def retrieve_tweets_by_keywords(topics, dictionary, gdf):

  keywords = []

  for key in topics:
    new_keywords = dictionary[key]['Word'].tolist()
    new_keywords = [i.strip() for i in new_keywords]
    new_keywords = "|".join(new_keywords)
    new_keywords = new_keywords.split("|")
    keywords.extend(new_keywords)

  keywords = list(set(keywords))

  pattern = '|'.join(keywords)
  gdf_filter = gdf[gdf['text'].str.contains(pattern, case=False, na=False)]
  print('Number of retrived tweets: ', len(gdf_filter))

  return gdf_filter


def spatial_aggregation_country(gdf_topic, gdf_countries, output_dir, output_name):

  # Calculate the number of tweets with keyword in each country
  point_count = gdf_topic.groupby('ISO_A3').size().reset_index(name='tweets_count')
  gdf_topic_countries = gdf_countries.merge(point_count, on='ISO_A3', how='left')

  # Calculate the mean sentiment score of tweents with keyword in each country
  gdf_topic['score'] = gdf_topic['score'].astype(float)
  mean_score = gdf_topic.groupby('ISO_A3')['score'].mean().reset_index(name='score')
  gdf_topic_countries = gdf_topic_countries.merge(mean_score, on='ISO_A3', how='left')

  # Save as a geojson file
  gdf_topic_countries.to_file(output_dir + output_name + '_country.geojson', driver='GeoJSON')


def temporal_aggregation(df_timeseries, output_dir, output_name):

  df_timeseries = df_timeseries.sort_index()
  df_timeseries['score'] = df_timeseries['score'].astype(float)

  ## Group by country ('ADMIN') and date (daily), then aggregate
  daily_data = df_timeseries.groupby(['ADMIN', pd.Grouper(level='date', freq='D')])
  df_daily = daily_data.size().reset_index(name='tweets_num')
  df_daily['score'] = daily_data['score'].mean().reset_index()['score']

  ## Group by country ('ADMIN') and date (monthly), then aggregate
  monthly_data = df_timeseries.groupby(['ADMIN', pd.Grouper(level='date', freq='M')])
  df_monthly = monthly_data.size().reset_index(name='tweets_num')
  df_monthly['score'] = monthly_data['score'].mean().reset_index()['score']

  ## Save as csv files
  df_daily.to_csv(output_dir + output_name + '_daily.csv')
  df_monthly.to_csv(output_dir + output_name + '_monthly.csv')


def main(dictionary, gdf_countries, gdf, output_dir):
    
    topics_options = {
        'All': list(dictionary.keys()),
        'Blockchain_NFT_Crypto': ['blockchain', 'NFT', 'crypto'],
        'Bitcoin': ['Bitcoin'],
        'Ethereum': ['Ethereum'],
        'Binance': ['Binance'],
        'Dogecoin': ['Dogecoin'],
        'Ripple': ['Ripple'],
        'Litecoin': ['Litecoin'],
        'USD Coin': ['USD Coin'],
        'Tether': ['Tether'],
        'Cardano': ['Cardano'],
        'Solana': ['Solana'],
        'TRON': ['TRON']
    }

    for key, value in topics_options.items():

        # Retrieve tweets by topics
        output_name = key.lower()
        topics = value

        if key == 'All':
            gdf_topic = gdf
        else:
            gdf_topic = retrieve_tweets_by_keywords(topics, dictionary, gdf)

        # Spatial aggregation
        spatial_aggregation_country(gdf_topic, gdf_countries, output_dir, output_name)

        # Temporal aggregation
        temporal_aggregation(gdf_topic, output_dir, output_name)


if __name__ == '__main__':

    dictionary = pd.read_excel('./dictionary/dictionary.xlsx', sheet_name=None)
    gdf_countries = gpd.read_file('./data/geo/countries.geojson')
    # Please change the path to the Parquet file
    gdf = load_tweets('Path_to_Parquet_File', dictionary, gdf_countries)
    output_dir = './data/tweets_aggregation/'
    main(dictionary, gdf_countries, gdf, output_dir)