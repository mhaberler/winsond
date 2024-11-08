#!/usr/bin/env python
 
import pandas as pd
from geojson import Feature, FeatureCollection, Point
import json
import math
import os
import sys

if len(sys.argv) != 2:
    print("Usage: convert <csv file>")
    sys.exit(1)

filename = sys.argv[1]

def replace_extension(filename, new_extension):
    # Split the filename into name and extension
    name, ext = os.path.splitext(filename)
    # Join the name with the new extension
    return name + '.' + new_extension

def calculate_dew_point(pressure, temperature, relative_humidity):
    """
    Calculate the dew point given pressure (in hPa), temperature (in °C), and relative humidity (in %).

    :param pressure: Atmospheric pressure in hectopascals (hPa)
    :param temperature: Air temperature in degrees Celsius (°C)
    :param relative_humidity: Relative humidity in percentage (%)
    :return: Dew point temperature in degrees Celsius (°C)
    """
    # Constants for the Tetens equation
    A = 17.625
    B = 243.04  # in degrees Celsius

    # Calculate saturation vapor pressure over water es(T)
    es = 6.112 * math.exp((A * temperature) / (B + temperature))
    
    # Calculate actual vapor pressure e
    # RH is converted from percentage to fraction
    e = es * (relative_humidity / 100.0)
    
    # Calculate dew point using Tetens' inverted formula
    dew_point = B * (math.log(e / 6.112)) / (A - math.log(e / 6.112))
    
    return dew_point

def compute_bearing(lat1, lon1, lat2, lon2):
    """ Compute the bearing from point 1 to point 2"""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    initial_bearing = math.atan2(y, x)
    # Convert bearing to degrees and normalize to 0-360
    initial_bearing = math.degrees(initial_bearing)
    bearing = (initial_bearing + 360) % 360
    return bearing


def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    returns meters
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1 
    dlon = lon2 - lon1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371000
    return c * r

def dataframe_to_geojson(df, ws, gj):
    features = []
    lasttime = 0
    lastlat = 99
    lastlon = 1000
    distance = 0
    bearing = 0
    speed = 0
    dew_point = 0
    ws.write("Height[m]  Pressure[hPa]  Temperature[°C]  Dewpoint[°C]  Wind direction[°]  Wind speed[m/s]\n")
    for _, row in df.iterrows():
        if row['Lat/PosX'] > 90:
            continue
        ts = float(row['Time'])
        if lasttime:
            delta = ts - lasttime
        else:     
            delta = 0 
        lasttime = ts
        if lastlat < 90:
            distance = haversine(row['Lat/PosX'], row['Long/PosY'], lastlat, lastlon)
            bearing = compute_bearing(row['Lat/PosX'], row['Long/PosY'], lastlat, lastlon)
            speed = distance * 1000/delta
            dew_point = calculate_dew_point(row['Baro'], row['AirT'], row['RH'] )
        lastlat = row['Lat/PosX']
        lastlon = row['Long/PosY']
        feature = Feature(
            geometry=Point((row['Long/PosY'], row['Lat/PosX'], row['Alt/PosZ'])),
            properties={
                'pressure': row['Baro'],
                'hum': row['RH'],
                'temp': row['AirT'],
                'dew_point': dew_point,
                'dT': delta, 
                'distance' : distance,
                'bearing' : bearing,
                'speed' : speed
            }
        )
        if delta:
            features.append(feature)
            ws.write(f"{row['Alt/PosZ']:.1f}\t{row['Baro']:.1f}\t{row['AirT']:.1f}\t{dew_point:.1f}\t{bearing:.1f}\t{speed:.1f}\n")

    feature_collection = FeatureCollection(features)
    gj.write(json.dumps(feature_collection, indent=2))

# Read the CSV file into a DataFrame
df = pd.read_csv(filename, index_col=False, sep=r'[,\*]', engine='python')

# convert the DataFrame into Geojson, decorating with values from CSV 
# and computed values
# write geojson and windsond format files

with open(replace_extension(filename, "windsond"), 'w') as ws:
    with open(replace_extension(filename, "geojson"), 'w') as gj:
        dataframe_to_geojson(df, ws, gj)


