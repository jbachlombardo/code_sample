# NOTE: As written here this is meant to be run in Jupyter Notebook. (To run in a shell print statements would need to be added to show the various tables produced by the analysis.)

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from glob import glob
from math import sin, cos, sqrt, atan2, radians
import urllib.request, urllib.parse
import json
import re
import networkx as nx

#IRS ZIP CODE INCOME CALCULATION
income = pd.read_excel('/FILEPATH/csv.csv', header = 3, skiprows = 2, usecols = [0, 17, 18], names = ['zipcode', 'returns', 'income'], converters = {0: lambda x: '0' + str(x), 2: lambda x: pd.to_numeric(x * 1000)})
#Notes: Col 0: Leading 0 in zip code dropping off when read in -- this ensures it is maintained; Col 2: IRS reports in 1000s of dollars, was reading in as object so forced reading as number
income = income.dropna().drop_duplicates(subset = 'zipcode', keep = 'first')
#Drops empty rows (dropna) and keeps only the overall zipcode data (drop_duplicates) -- it is reported by overall totals as well as by income bracket, so keeping first only keeps the total data for each zipcode
income['avg_income'] = income['income'] / income['returns']

#GETTING ZIP CODES FOR BIKE STATIONS IN ORDER TO COMBINE INCOME AND BIKE STATION DATA
stations = pd.read_csv('/FILEPATH/csv.csv')
zipcodes = {}
key = 'MY KEY'
base_url = 'https://maps.googleapis.com/maps/api/geocode/json?'
for i in range(1, len(stations)):
    try :
        query_url = base_url + urllib.parse.urlencode({'latlng': str(stations.iloc[i, 2]) + ',' + str(stations.iloc[i, 3]), 'key': key})
        result = urllib.request.urlopen(query_url)
        data = result.read().decode()
        js_data = json.loads(data)
        address = js_data['results'][0]['formatted_address']
        zipcodes[stations.iloc[i]['Station ID']] = re.findall('(\d{5})', address)[0]
        #On the first debugging run, which parsed the JSON result to the zipcode component of the returned data, a number of the zip codes were not found because the returned JSON dictionary had a variable number of elements between results. Instead needed to use this approach of using regex to pull the zipcode from the full address associated with the lat/lon, which was consistently returned.
    except :
        zipcodes[stations.iloc[i]['Station ID']] = 'Zipcode not found'
stations['zipcode'] = stations['Station ID'].map(zipcodes)

#MERGE INCOME AND STATION INFO
stations_income = stations.merge(income[['zipcode', 'avg_income']])
stat_inc_scatter = stations_income.groupby('zipcode').agg({'Station ID': 'count', 'avg_income': 'mean'}).rename(columns = {'Station ID': '# of stations'})
print ('I was curious if there was a pattern to the distribution of the Hubway network, similar to what has been seen in the layout of bus networks across the country.')
print ('Based on the current station network, there does not appear to be a pattern.')
print ('Number of Hubway stations by zipcode, sorted by average income per zipcode:')
print (stat_inc_scatter.sort_values(by = 'avg_income', ascending = False))

#CALCULATE LINE OF BEST FIT FOR SCATTERPLOT
s, i = np.polyfit(stat_inc_scatter['avg_income'], stat_inc_scatter['# of stations'], 1)
print ('There is no discernible pattern related to income about the distribution of Hubway stations.')
print ('The slope of the best fit line is tiny: ' + str(s))
plt.figure()
plt.xlabel('Average income by zipcode')
plt.ylabel('# of stations by zipcode')
plt.scatter(x = stat_inc_scatter['avg_income'], y = stat_inc_scatter['# of stations'], alpha = '0.5', color = 'green', label = None)
plt.plot([stat_inc_scatter['avg_income'].min(), stat_inc_scatter['avg_income'].max()], [s * stat_inc_scatter['# of stations'].min() + i, s * stat_inc_scatter['# of stations'].max() + i], color = 'firebrick', alpha = 0.5, label = 'Best fit')
plt.legend()
plt.show()

#LOOKING AT RIDES OVER THE PAST 3 YEARS AND ASSESSING TRENDS

#Hubway publishes travel data monthly. The following analysis looks at information from 2015 through March 2018.

def ride_dist(row) :
    """A function to calculate a ride's distance based on the provided starting point and endpoint."""
    try :
        lon_start = radians(row['start station longitude'])
        lon_end = radians(row['end station longitude'])
        lat_start = radians(row['start station latitude'])
        lat_end = radians(row['end station latitude'])
        dist_lon = lon_end - lon_start
        dist_lat = lat_end - lat_start
        R = 3959
        a = sin(dist_lat / 2) ** 2 + cos(lat_start) * cos(lat_end) * sin(dist_lon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        dist = R * c
        return dist
    except :
        return float('NaN')
filenames = glob('FILEPATH/*-tripdata.csv') #Uses glob to pull in 38 csv filepaths, corresponding to each month
dataframes = []
for f in filenames :
    df = pd.read_csv(f, na_values = '\\N', parse_dates = ['starttime', 'stoptime'])
    dataframes.append(df)
rides = pd.concat(dataframes)
rides = rides.loc[((rides['start station longitude'] != 0) | (rides['start station latitude'] != 0)) & ((rides['end station longitude'] != 0) | (rides['end station latitude'] != 0))]
rides['Distance traveled'] = rides.apply(ride_dist, axis = 1)
rides_oneway = rides.loc[(rides['start station longitude'] != rides['end station longitude']) & (rides['start station latitude'] != rides['end station latitude'])]
all_trips = len(rides)
ow_trips = len(rides_oneway)
print ('There were ' + '{:,}'.format(all_trips) + ' trips made from January 2015 through March 2018.')
print ('{:,}'.format(all_trips - ow_trips) + ' of those trips began and ended at the same station.')

print ('The median trip length was ' + str(round(rides['Distance traveled'].median(), 2)) + ' miles.')
print ('Round trips are represented by trips of 0 miles in the histogram below.')
fig, ax = plt.subplots()
ax.set_title('Distribution of trip lengths')
ax.set_xlabel('Length of trip (mi)')
rides['Distance traveled'].hist(bins = 100, ax = ax)
plt.show()

print ('The median trip duration was ' + str(pd.to_datetime(rides['tripduration'].median(), unit = 's'))[-5:] + ' minutes.')
print ('However, a deeper look into these trip durations could be warranted as a small number of very large datapoints skew results, as demonstrated by the enormous gaps between the 75th percentile, the top whisker (set here at the 95th percentile), and the max:')
fig, ax = plt.subplots()
ax.set_title('Trip duration distribution, no fliers shown (except max)')
ax.set_yscale('log')
ax.set_ylabel('Trip duration (in seconds)')
ax.boxplot(rides['tripduration'], showfliers = False, whis = [5, 95])
ax.plot([0.9, 1.1], [rides['tripduration'].max(), rides['tripduration'].max()], c = 'k')
ax.annotate(s = 'Trip duration max', xy = (1, rides['tripduration'].max()), xytext = (1, (rides['tripduration'].mean() + 1000000)), arrowprops = {'arrowstyle': '->'})
plt.show()

#RESAMPLING DATA TO BE MONTHLY

# This resamples the data to show monthly trends. One dataset was missing on the Hubway website (December 2016) so this has been interpolated.

plotter = rides.set_index('starttime').resample('M').agg({'Distance traveled': 'median', 'tripduration': 'median'}).interpolate()
plotter['Trip duration_minutes'] = pd.to_datetime(plotter['tripduration'], unit = 's').dt.time
print ('Trip traits oscillate as expected: Shorter in the winter and longer in the summer.')
fig, (ax1, ax2) = plt.subplots(nrows = 2)
plotter['tripduration'].plot(c = 'purple', label = 'Trip duration', ax = ax1)
ax1.set_title('Average trip duration by month')
ax1.set_ylabel('Trip duration (min)')
ax1.set_yticks([plotter['tripduration'].min(), plotter['tripduration'].max()])
ax1.set_yticklabels([plotter['Trip duration_minutes'].min(), plotter['Trip duration_minutes'].max()])
ax1.set_xlabel('')
ax2.set_title('Average trip length by month')
plotter['Distance traveled'].plot(c = 'green', label = 'Trip distance', ax = ax2)
ax2.set_ylabel('Trip length (mi)')
ax2.set_yticks([plotter['Distance traveled'].min(), plotter['Distance traveled'].max()])
ax2.set_xlabel('')
plt.tight_layout()
plt.show()

#STATION-LEVEL NETWORK ANALYSIS

#Looking at the overall network to find the most central hubs, using a multi-directional graph

station_counts_all = rides.groupby('start station id').agg({'tripduration': 'count'}).rename(columns = {'tripduration': 'num_trips_all'}).reset_index()
station_counts_oneway = rides_oneway.groupby('start station id').agg({'tripduration': 'count'}).rename(columns = {'tripduration': 'num_trips_oneway'}).reset_index()
station_counts = station_counts_all.merge(station_counts_oneway, on = 'start station id')
station_counts['num_round_trips'] = station_counts['num_trips_all'] - station_counts['num_trips_oneway']
station_counts = station_counts.merge(rides[['start station id', 'start station name']], on = 'start station id', how = 'left').drop_duplicates(subset = 'start station id', keep = 'first')
G = nx.from_pandas_dataframe(rides, 'start station id', 'end station id', create_using = nx.MultiDiGraph())
dict_centrality = nx.degree_centrality(G)
centrality = pd.DataFrame(list(dict_centrality.items()), columns = ['Station ID', 'Degree centrality']).sort_values(by = 'Degree centrality', ascending = False)
station_cent = station_counts.merge(centrality, left_on = 'start station id', right_on = 'Station ID')
print ('The 25 most popular hubs in the Hubway, by degree centrality and number of trips originating from the station:')
station_cent.set_index(['start station id', 'start station name'])[['Degree centrality', 'num_trips_all', 'num_round_trips']].sort_values(by = 'Degree centrality', ascending = False).head(25)

#BIKE-LEVEL ANALYSIS

# Resampling and grouping the data to find the most distance traveled by a bike on a single day, and following its journey.

daily_rides = rides.set_index('starttime').groupby([pd.Grouper(freq = 'D'), 'bikeid'])['Distance traveled'].sum().reset_index().rename(columns = {'starttime': 'Date'})
print ('The furthest traveled by a bike in a day (top 25):')
daily_rides.set_index('bikeid').sort_values(by = 'Distance traveled', ascending = False).head(25)

time_mask = (rides['starttime'] >= '2017-07-17 00:00:00') & (rides['starttime'] < '2017-07-18 00:00:00')
day_in_the_life = rides.loc[time_mask & (rides['bikeid'] == 1398)].sort_values(by = 'starttime')
print ("Here's bike 1398's work for July 17, 2017:")
day_in_the_life['Trip duration_minutes'] = pd.to_datetime(day_in_the_life['tripduration'], unit = 's').dt.time
day_in_the_life[['start station name', 'starttime', 'end station name', 'Distance traveled', 'Trip duration_minutes']]
