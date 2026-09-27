"""Exports OSM named POIs to landmarks.csv (technical.md §9 B's geo spec).
Uses OSMnx + Overpass to pull: temples, schools, hospitals, stations, markets, chowks.
Output: name, name_normalized, alt_names, kind, lat, lng
"""
import osmnx as ox
import pandas as pd
import unicodedata
import string
import os

PUNE_BBOX = (18.42, 73.72, 18.63, 73.97)  # south, west, north, east
TAGS = {
    'amenity': ['hospital', 'school', 'college', 'police', 'fire_station', 'place_of_worship'],
    'shop': ['mall', 'supermarket'],
    'public_transport': ['station', 'stop_position'],
    'place': ['suburb', 'neighbourhood'],
}

def normalize_name(name: str) -> str:
    """Lowercase, remove punctuation, normalize Unicode."""
    if not isinstance(name, str):
        return ""
    # Normalize unicode characters
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('utf-8')
    name = name.lower()
    # Remove punctuation
    translator = str.maketrans('', '', string.punctuation)
    name = name.translate(translator)
    return " ".join(name.split())

def export_landmarks(output_path: str = 'data/processed/landmarks.csv') -> None:
    """Pull POIs from Overpass, normalize, export to CSV."""
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Fetch data using OSMnx
    # Bbox in osmnx is (north, south, east, west)
    north = PUNE_BBOX[2]
    south = PUNE_BBOX[0]
    east = PUNE_BBOX[3]
    west = PUNE_BBOX[1]
    
    try:
        pois = ox.features_from_bbox(north, south, east, west, tags=TAGS)
    except Exception as e:
        print(f"Failed to fetch POIs: {e}")
        return
        
    if pois.empty:
        print("No POIs found.")
        return
        
    # Process dataframe
    data = []
    
    for idx, row in pois.iterrows():
        name = row.get('name')
        if pd.isna(name):
            continue
            
        alt_names = []
        if 'alt_name' in row and not pd.isna(row['alt_name']):
            alt_names.append(row['alt_name'])
            
        # Determine kind
        kind = None
        for k in TAGS.keys():
            if k in row and not pd.isna(row[k]):
                kind = row[k]
                break
                
        # Get coordinates
        lat = row.geometry.centroid.y if hasattr(row.geometry, 'centroid') else row.geometry.y
        lng = row.geometry.centroid.x if hasattr(row.geometry, 'centroid') else row.geometry.x
        
        data.append({
            'name': name,
            'name_normalized': normalize_name(name),
            'alt_names': "|".join(alt_names),
            'kind': kind,
            'lat': lat,
            'lng': lng
        })
        
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False)
    print(f"Exported {len(df)} landmarks to {output_path}")

if __name__ == '__main__':
    export_landmarks()
