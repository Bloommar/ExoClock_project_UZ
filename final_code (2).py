
import urllib
import json
import pandas as pd
from astropy.time import Time
from astropy.coordinates import solar_system_ephemeris,  get_body_barycentric, EarthLocation
from astropy import units as u
from astropy.coordinates import SkyCoord, AltAz
import astropy.units as u
from astropy.coordinates import get_sun
import numpy as np


exoclock_planets= pd.read_json("https://www.exoclock.space/database/planets_json")

exoclock_planets.to_csv("all_data.csv",header=True, index=True)
df=exoclock_planets
df = pd.read_csv("all_data.csv", index_col=0, header=1)


min_aperture= 10.0
max_aperture=45.0
r_mag_min=5.0
telescope_latitude=-30.526309016377613

def sexagesimal_to_decimal(sexagesimal_str):
    degrees, minutes, seconds = map(float, sexagesimal_str.split(':'))

    decimal_declination = degrees + minutes/60 + seconds/3600

    return '{:.5f}'.format(decimal_declination)


row_to_convert = df.iloc[56]
decimal_declinations = row_to_convert.apply(sexagesimal_to_decimal)

df.iloc[56] = decimal_declinations

df.to_csv("all_data.csv", header=1, index=True)

def sexagesimal_to_decimal(sexagesimal_str):
    degrees, minutes, seconds = map(float, sexagesimal_str.split(':'))

    decimal_ra = degrees + minutes/60 + seconds/3600

    return '{:.5f}'.format(decimal_ra)


row_to_convert = df.iloc[55]
decimal_ra = row_to_convert.apply(sexagesimal_to_decimal)

df.iloc[55] = decimal_ra

df.to_csv("all_data.csv", header=1, index=True)

transposed_df = df.T

columns_to_convert = ['depth_r_mmag','duration_hours', 'ephem_period','ra_j2000','dec_j2000','r_mag','v_mag','min_telescope_inches','ephem_mid_time','t0_bjd_tdb','period_days']  # Replace with the column names you want to convert

transposed_df[columns_to_convert] = transposed_df[columns_to_convert].astype(float)

new_df= transposed_df[
    ((transposed_df["priority"] == "high") | (transposed_df["priority"] == "medium") | (transposed_df["priority"] == "alert")) &
    (transposed_df["min_telescope_inches"] >= min_aperture) & (transposed_df["min_telescope_inches"] <= max_aperture) & (transposed_df["r_mag"] >= r_mag_min) &
    ((transposed_df["dec_j2000"] + telescope_latitude >= 90) | (transposed_df["dec_j2000"] + telescope_latitude <= -90))
]

new_df.to_csv("all_data.csv", header=1, index=True)

new_column_order = ['priority', 'depth_r_mmag','duration_hours', 'ephem_period', 'ephem_period_units','ra_j2000','dec_j2000','r_mag','v_mag','min_telescope_inches','ephem_mid_time','t0_bjd_tdb','period_days']
new_df_2 = new_df[new_column_order]

new_df_2['transit_start_000']= new_df_2.ephem_mid_time -0.5* new_df_2.ephem_period
new_df_2['transit_end_000']= new_df_2.ephem_mid_time + 0.5* new_df_2.ephem_period

date_time_start = "2023-11-12T12:00:00"

time_start = Time(date_time_start, format='isot', scale='utc')

with solar_system_ephemeris.set('builtin'):
    tdb_start = time_start.tdb.jd

date_time_end = "2023-12-10T12:00:00"
time_end = Time(date_time_end, format='isot', scale='utc')

with solar_system_ephemeris.set('builtin'):
    tdb_end = time_end.tdb.jd

new_df_2['current_epoch']=(tdb_start-new_df_2.t0_bjd_tdb)/new_df_2.ephem_period


def calc_next_eclipses(row, tdb_end_1):
    output_list = []
    m = 0
    while True:
        m = m + 1
        next_eclipse = row['t0_bjd_tdb'] + row['ephem_period'] * (int(row['current_epoch']) + m)
        if next_eclipse > tdb_end_1:
            break
        output_list.append(next_eclipse)
    return output_list

new_df_2['next_eclipse_times'] = new_df_2.apply(lambda row: calc_next_eclipses(row, tdb_end), axis=1)

eclipses_df = pd.DataFrame(new_df_2.next_eclipse_times)

total_period_of_observations=tdb_end-tdb_start


extra_time=0.01389000006

new_df_2['duration_days']=new_df_2.duration_hours/24


def start_eclipse(row, extra_time):
    if not row['next_eclipse_times']:
        return None
    start_of_transit = [ecl - extra_time - 0.5 * row['duration_days'] for ecl in row['next_eclipse_times']]
    return start_of_transit

new_df_2['start_of_transit'] = new_df_2.apply(start_eclipse, extra_time=extra_time, axis=1)

new_df_2 = new_df_2.dropna(subset=['start_of_transit'])

if 'name' in new_df_2.columns:
    new_df_2.set_index('name', header=1, index=True)

def end_eclipse(row, extra_time):
    if not row['next_eclipse_times']:
        return None
    end_of_transit = [ecl + extra_time + 0.5 * row['duration_days'] for ecl in row['next_eclipse_times']]
    return end_of_transit

new_df_2['end_of_transit'] = new_df_2.apply(end_eclipse, extra_time=extra_time, axis=1)

new_df_2 = new_df_2.dropna(subset=['end_of_transit'])

if 'name' in new_df_2.columns:
    new_df_2.set_index('name', header=1, index=True)

altitude_list = []

for index, row in new_df_2.iterrows():
    time_jd = Time(row['start_of_transit'], format='jd')
    bear_mountain = EarthLocation(lat=-30.526309016377613*u.deg, lon=-70.85329602458853*u.deg, height=1700*u.m)

    altitude = SkyCoord(ra=row['ra_j2000'], dec=row['dec_j2000'], unit=(u.hourangle, u.deg))
    altitude = SkyCoord(ra=row['ra_j2000'], dec=row['dec_j2000'], unit=(u.hourangle, u.deg)) \
        .transform_to(AltAz(obstime=time_jd, location=bear_mountain)).alt


    altitude_float = altitude.value
    altitude_list.append(altitude_float)

# Assign the list of altitudes to the DataFrame
new_df_2['start_altitude'] = altitude_list

altitude_list = []

for index, row in new_df_2.iterrows():
    time_jd = Time(row['end_of_transit'], format='jd')
    bear_mountain = EarthLocation(lat=-30.526309016377613*u.deg, lon=-70.85329602458853*u.deg, height=1700*u.m)

    altitude = SkyCoord(ra=row['ra_j2000'], dec=row['dec_j2000'], unit=(u.hourangle, u.deg))
    altitude = SkyCoord(ra=row['ra_j2000'], dec=row['dec_j2000'], unit=(u.hourangle, u.deg)) \
        .transform_to(AltAz(obstime=time_jd, location=bear_mountain)).alt


    altitude_float = altitude.value
    altitude_list.append(altitude_float)

# Assign the list of altitudes to the DataFrame
new_df_2['end_altitude'] = altitude_list

observatory_location = EarthLocation(lat = -30.526309016377613 * u.deg, lon = - 70.85329602458853 * u.deg, height=1700*u.m)

time = Time.now()


sun_coords = get_sun(time)

# Transform the Sun's coordinates to the AltAz frame for your observatory
sun_altaz = sun_coords.transform_to(AltAz(obstime=time, location=observatory_location))

# Access the altitude of the Sun
sun_altitude = sun_altaz.alt


def twilight_before_transit (row, extra_time ):

  sun_altitude_before=[]
  for index,row in new_df_2.iterrows():
    time_jd = Time(row['start_of_transit'], format='jd')
    observatory_location = EarthLocation(lat = -30.526309016377613 * u.deg, lon = - 70.85329602458853 * u.deg, height=1700*u.m)
    sun_altaz = sun_coords.transform_to(AltAz(obstime=time, location=observatory_location))
    sun_altitude_float = altitude.value
    sun_altitude_before.append(sun_altitude_float)

def twilight_before_transit(row, extra_time):
    # Initialize an empty list to store sun altitudes
    sun_altitudes_before = []

    # Iterate over each start_of_transit time in the list
    for transit_time_jd in row['start_of_transit']:
        # Convert the start time of transit to Time object
        time_jd = Time(transit_time_jd, format='jd')

        # Define the observatory location (replace with your observatory's coordinates)
        observatory_location = EarthLocation(lat=-30.526309016377613*u.deg, lon=-70.85329602458853*u.deg, height=1700*u.m)

        # Calculate the Sun's coordinates at the specified time
        sun_coords = get_sun(time_jd)

        # Transform the Sun's coordinates to the AltAz frame for your observatory
        sun_altaz = sun_coords.transform_to(AltAz(obstime=time_jd, location=observatory_location))

        # Access the altitude of the Sun and append to the list
        sun_altitudes_before.append(sun_altaz.alt.value)

    return sun_altitudes_before

new_df_2['sun_altitude_before'] = new_df_2.apply(twilight_before_transit, extra_time=extra_time, axis=1)

def twilight_after_transit(row, extra_time):
    # Initialize an empty list to store sun altitudes
    sun_altitudes_after = []

    # Iterate over each end_of_transit time in the list
    for transit_time_jd in row['end_of_transit']:
        # Convert the end time of transit to Time object
        time_jd = Time(transit_time_jd, format='jd')

        # Define the observatory location (replace with your observatory's coordinates)
        observatory_location = EarthLocation(lat=-30.526309016377613*u.deg, lon=-70.85329602458853*u.deg, height=1700*u.m)

        # Calculate the Sun's coordinates at the specified time
        sun_coords = get_sun(time_jd)

        # Transform the Sun's coordinates to the AltAz frame for your observatory
        sun_altaz = sun_coords.transform_to(AltAz(obstime=time_jd, location=observatory_location))

        # Access the altitude of the Sun and append to the list
        sun_altitudes_after.append(sun_altaz.alt.value)

    return sun_altitudes_after

new_df_2['sun_altitude_after'] = new_df_2.apply(twilight_after_transit, extra_time=extra_time, axis=1)

data2 = pd.read_csv('/content/9mag_recalculated.csv')
data2.columns


df2 = pd.DataFrame(data2)

df2['flux'] = pd.to_numeric(df2['flux']).astype(float)
df2['mag'] = pd.to_numeric(df2['mag']).astype(float)

import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

from pandas.core.frame import DataFrame
df2.sort_values(by='mag', inplace=True)





def exponential_function(x, A, B):
    return A * np.exp(B * x)

x_data=df2['mag']
y_data=df2['flux']
params, covariance = curve_fit(exponential_function, x_data, y_data)
A, B = params
y_fit = exponential_function(x_data, A, B)
plt.scatter(x_data, y_data, label='Data')
plt.plot(x_data, y_fit, label='Fitted Exponential_9', c='red')
plt.legend()
plt.xlabel('R_mag')
plt.ylabel('peak_flux')
plt.title('Exponential Fit')
plt.show()

data3 = pd.read_csv('/content/11mag_recalculated.csv')
data3.columns


df3 = pd.DataFrame(data3)

df3['flux'] = pd.to_numeric(df3['flux']).astype(float)
df3['mag'] = pd.to_numeric(df3['mag']).astype(float)

import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

from pandas.core.frame import DataFrame
df3.sort_values(by='mag', inplace=True)





def exponential_function2(x, C, D):
    return C * np.exp(D * x)

x_data=df3['mag']
y_data=df3['flux']
params, covariance = curve_fit(exponential_function2, x_data, y_data)
C, D = params
y_fit = exponential_function2(x_data, C, D)
plt.scatter(x_data, y_data, label='Data')
plt.plot(x_data, y_fit, label='Fitted Exponential_11', c='red')
plt.legend()
plt.xlabel('R_mag')
plt.ylabel('peak_flux')
plt.title('Exponential Fit')
plt.show()

def exposure_time(new_df_2, df2, df3, A, B, C, D):
    # Assuming r_mag is a column in new_df_2
    r_mag = new_df_2['r_mag']

    # Define the exponential functions
    def exponential_function(x, a, b):
        return a * np.exp(b * x)

    def exponential_function2(x, c, d):
        return c * np.exp(d * x)

    # Calculate exposure time based on conditions
    new_df_2["exp_time"] = np.where(r_mag <= 11.0, (10 * 40000) / exponential_function(r_mag, A, B),
                                    (60 * 40000) / exponential_function2(r_mag, C, D))

    # Return the DataFrame with the added exposure_time column
    return new_df_2

# Apply the function
new_df_2 = exposure_time(new_df_2, df2, df3, A, B, C, D)


def extract_lists(row, columns_with_lists):
    extracted_data = {}
    for col in columns_with_lists:
        extracted_data[col] = row[col]
    return pd.Series(extracted_data)

# Specify the columns in 'new_df_2' that have lists
columns_with_lists = ['ra_j2000','dec_j2000','next_eclipse_times', 'start_of_transit', 'end_of_transit', 'start_altitude', 'end_altitude', 'exp_time',	'sun_altitude_before',	'sun_altitude_after','r_mag']

# Apply the function to create 'new_df_3'
new_df_3 = new_df_2.apply(extract_lists, columns_with_lists=columns_with_lists, axis=1)


data = []

for index, row in new_df_3.iterrows():
    exploded_start_altitude = pd.Series(row['start_altitude']).explode() if isinstance(row['start_altitude'], list) else pd.Series([row['start_altitude']])
    exploded_end_altitude = pd.Series(row['end_altitude']).explode() if isinstance(row['end_altitude'], list) else pd.Series([row['end_altitude']])

    max_length = max(len(row["start_of_transit"]), len(exploded_start_altitude), len(row["end_of_transit"]))

    for i in range(max_length):
        data.append(
            {
                "name": row.name,
                "T_0": row['next_eclipse_times'][i] if isinstance(row['next_eclipse_times'], list) and len(row['next_eclipse_times']) > i else None,
                "start": row['start_of_transit'][i] if isinstance(row['start_of_transit'], list) and len(row['start_of_transit']) > i else None,
                "end": row['end_of_transit'][i] if isinstance(row['end_of_transit'], list) and len(row['end_of_transit']) > i else None,
                "start_altitude": row["start_altitude"][i] ,
                "end_altitude": row["end_altitude"][i],
                "sun_altitude_before": row['sun_altitude_before'][i] if isinstance(row['sun_altitude_before'], list) and len(row['sun_altitude_before']) > i else None,
                "sun_altitude_after": row['sun_altitude_after'][i] if isinstance(row['sun_altitude_after'], list) and len(row['sun_altitude_after']) > i else None,
                "ra_j2000": row.ra_j2000,
                "dec_j2000" : row.dec_j2000,
                "r_mag" : row.r_mag
            }
        )

new_df_3=pd.DataFrame.from_dict(data)

new_df_3=new_df_3[
    ((new_df_3['sun_altitude_before'] <= -12.0) & (new_df_3['sun_altitude_after']<=-12.0))
]


def bjd_to_utc(bjd_value):
    bjd_time = Time(bjd_value, format='jd', scale='tdb')
    return bjd_time.utc.datetime

new_df_3['T_0_utc'] = new_df_3['T_0'].apply(bjd_to_utc)
new_df_3['start_utc'] = new_df_3['start'].apply(bjd_to_utc)
new_df_3['end_utc'] = new_df_3['end'].apply(bjd_to_utc)

new_df_3['start_utc'] = pd.to_datetime(new_df_3['start_utc']).dt.strftime('%Y-%m-%d %H:%M:%S')

new_df_3['end_utc'] = pd.to_datetime(new_df_3['end_utc']).dt.strftime('%Y-%m-%d %H:%M:%S')

new_df_3['start_utc'] = pd.to_datetime(new_df_3['start_utc'])

new_df_3['obs_start_time'] = new_df_3['start_utc'].dt.round('15min')
new_df_3['obs_start_time'] = new_df_3['obs_start_time'].astype(str)

new_df_3[['real_obs_date', 'obs_start_time']] = new_df_3['obs_start_time'].str.split(' ', expand=True)


new_df_3['end_utc'] = pd.to_datetime(new_df_3['end_utc'])

new_df_3['obs_end_time'] = new_df_3['end_utc'].dt.round('15min')
new_df_3['obs_end_time'] = new_df_3['obs_end_time'].astype(str)


new_df_3[['end_date_delete', 'obs_end_time']] = new_df_3['obs_end_time'].str.split(' ', expand=True)

new_df_3['start_utc'] = pd.to_datetime(new_df_3['start_utc'])

new_df_3['obs_night'] = new_df_3['start_utc'].apply(lambda row_dt: row_dt - pd.Timedelta(days=1) if 0 <= row_dt.hour < 12 else row_dt)


new_df_3['obs_night'] = new_df_3['obs_night'].astype(str)

new_df_3[['obs_night', 'obs_time_delete']] = new_df_3['obs_night'].str.split(' ', expand=True)


new_df_3['FILTER']='R'
new_df_3['Focus']=11850
new_df_3['Binning']=2
new_df_3['GAIN']=0

new_df_3['flag']=0
new_df_3['project']='ExoClock UZ'
import numpy as np



new_column_order = ['obs_night','obs_start_time', 'obs_end_time', 'name', 'project','ra_j2000','dec_j2000','FILTER','exp_time','Focus','Binning','GAIN','flag']
new_df_3 = new_df_3[new_column_order]

new_df_3 = new_df_3.sort_values(by='obs_night', ascending=True)
new_df_3.to_csv("all_data.csv", header=1, index=False)
