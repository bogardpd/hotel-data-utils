"""Creates a CSV of hotel locations and nights, either by city or by
CBSA metro area."""

import argparse
import datetime
import pandas as pd
import tomllib
from pathlib import Path

from modules.hotel_data_frame import HotelDataFrame

with open(Path(__file__).parent / "data_sources.toml", 'rb') as f:
    sources = tomllib.load(f)
lodging_path = Path(sources['lodging']).expanduser()

def frequency_table(
    by='city',
    start_date=None,
    thru_date=None,
    output_file=None,
    top=None,
    exclude_flights=False,
    rank=False,
):
    mornings = HotelDataFrame().by_morning().loc[start_date:thru_date]
    if exclude_flights:
        mornings = mornings[~mornings.city.str.startswith('FLIGHT/')]
    cities_df = pd.read_excel(
        lodging_path,
        sheet_name='Cities',
    ).set_index('Id')
    mornings = mornings.join(cities_df, on='city')

    if by == 'metro':
        city_mornings = mornings[mornings['CurrentMetro'].isnull()]
        metro_mornings = mornings[mornings['CurrentMetro'].notnull()]
        
        cities_grouped = group_cities(city_mornings)
        metros_grouped = group_metros(metro_mornings)

        grouped = pd.concat([cities_grouped, metros_grouped])
        column_order = [
            'Title',
            'Location',
            'Type',
            'MetroId',
            'Latitude',
            'Longitude',
            'Nights',
        ]
        grouped = grouped[column_order]
    elif by == 'state':
        mornings = mornings[mornings['city'].str.match("US")]
        mornings['state'] = mornings['city'].apply(lambda x:
            str(x).split('/')[1]
        )
        grouped = group_states(mornings)
    else:
        grouped = group_cities(mornings)
    
    grouped = grouped.sort_values(
        by=['Nights','Location'],
        ascending=[False, True],
    )
    if rank:
        grouped['Rank'] = grouped['Nights'] \
            .rank(method='min', ascending=False) \
            .astype('int')
        columns = grouped.columns.to_list()
        columns = columns[-1:] + columns[:-1]
        grouped = grouped[columns]
    
    total_nights = grouped['Nights'].sum()
    if top is not None:
        grouped = grouped.head(top)
    print(grouped)
    print("Total night(s):", total_nights)

    if output_file is not None:
        grouped.to_csv(output_file, index=False)
        print(f"Saved CSV to `{output_file}`.")

def group_cities(mornings):
    if mornings.empty:
        return pd.DataFrame()
    mornings = mornings.assign(type='city')
    mornings.loc[
        mornings['city'].str.startswith('FLIGHT'), 'type'
    ] = 'flight'
    grouped = mornings.groupby('city').agg(
        Location=('Name', 'first'),
        Type=('type', 'first'),
        Latitude=('Latitude', 'first'),
        Longitude=('Longitude', 'first'),
        Nights=('city', 'count'),
    )
    grouped.index.names = ['loc_id']
    return grouped

def group_metros(mornings):
    if mornings.empty:
        return pd.DataFrame()
    mornings = mornings.assign(type='metro')
    metros_df = pd.read_excel(
        lodging_path, sheet_name='Metros'
    ).set_index('Id')
    mornings = mornings.join(metros_df,
        on='CurrentMetro',
        rsuffix='_metro'
    )
    grouped = mornings.groupby('CurrentMetro').agg(
        Title=('Title', 'first'),
        Location=('ShortName', 'first'),
        Type=('type', 'first'),
        MetroId=('CurrentMetro', 'first'),
        Latitude=('Latitude_metro', 'first'),
        Longitude=('Longitude_metro', 'first'),
        Nights=('city', 'count'),
    )
    grouped['MetroId'] = grouped['MetroId'].astype('string')
    grouped.index.names = ['loc_id']
    
    return grouped

def group_states(mornings):
    if mornings.empty:
        return pd.DataFrame()
    mornings = mornings.assign(type='state')
    states_df = pd.read_excel(
        lodging_path,
        sheet_name='USStates',
    ).set_index('Abbrev')
    mornings = mornings.join(states_df,
        on='state',
        rsuffix='_state'
    )
    grouped = mornings.groupby('state').agg(
        Location=('Name_state', 'first'),
        Type=('type', 'first'),
        Latitude=('Latitude', 'first'),
        Longitude=('Longitude', 'first'),
        Nights=('city', 'count'),
    )
    grouped.index.names = ['state']
    return grouped
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create a CSV of hotel locations and nights."
    )
    parser.add_argument('--by',
        help="group by `city`, `metro` or `state`",
        choices=['city','metro','state'],
        default='city',
    )
    parser.add_argument('--start',
        help="the earliest morning to show (inclusive) in YYYY-MM-DD format",
        type=datetime.date.fromisoformat,
        
    )
    parser.add_argument('--thru',
        help="the latest morning to show (inclusive) in YYYY-MM-DD format",
        type=datetime.date.fromisoformat,
    )
    parser.add_argument('--output',
        help="CSV file to write the results to",
        type=Path
    )
    parser.add_argument('--top',
        help="how many results to show",
        type=int
    )
    parser.add_argument('--exclude_flights',
        help="do not include nights on flights",
        action='store_true',
    )
    parser.add_argument('--rank',
        help="show a ranking column",
        action='store_true'
    )
    args = parser.parse_args()
    frequency_table(
        args.by, args.start, args.thru, args.output, args.top, args.exclude_flights, args.rank
    )
