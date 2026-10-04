"""Geographic matching within frozen Wigger geometry; no biological validation."""
import os
from functools import lru_cache
from hashlib import sha256
from math import isfinite
from pathlib import Path

from fastapi import HTTPException
from pyproj import Transformer
from shapely.geometry import Point
from app.scientific.data_loader import WiggerPreflightLoader
from config import config


@lru_cache(maxsize=1)
def validated_geometry():
    loader = WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR)
    hashes = loader.validate_frozen_reference()
    source = Path(config.PREFLIGHT_DATA_DIR) / 'upstream_reaches_real.geojson'
    frame = loader.load_reach_geometries().to_crs('EPSG:2056')
    reaches = loader.load_reaches()
    next_down = {int(row.HYRIV_ID):int(row.NEXT_DOWN) for row in reaches.itertuples()}
    geometries = {int(row.HYRIV_ID):row.geometry for row in frame.itertuples()}
    return geometries, next_down, {'geometry_source':str(source), 'geometry_sha256':sha256(source.read_bytes()).hexdigest(),
        'artifact_sha256':hashes, 'metric_crs':'EPSG:2056','input_crs':'EPSG:4326',
        'method':'nearest point on validated Wigger HydroRIVERS geometry'}


class LocationMatchingService:
    def match(self, latitude, longitude):
        if not isfinite(latitude) or not isfinite(longitude) or not -90<=latitude<=90 or not -180<=longitude<=180:
            raise HTTPException(422,detail={'type':'ValidationError','message':'Finite WGS84 latitude and longitude are required'})
        geometries, downstream, provenance = validated_geometry()
        forward=Transformer.from_crs('EPSG:4326','EPSG:2056',always_xy=True)
        reverse=Transformer.from_crs('EPSG:2056','EPSG:4326',always_xy=True)
        point=Point(*forward.transform(longitude,latitude))
        close=float(os.environ.get('WIGGER_MATCH_CLOSE_M','100'))
        maximum=float(os.environ.get('WIGGER_MATCH_MAX_M','500'))
        ambiguity=float(os.environ.get('WIGGER_MATCH_AMBIGUITY_M','20'))
        if not 0 < close <= maximum or ambiguity < 0 or not all(isfinite(value) for value in (close,maximum,ambiguity)):
            raise ValueError('Wigger matching thresholds must be finite: 0 < close <= maximum, ambiguity >= 0')
        ranked=sorted(((point.distance(geometry),identifier,geometry) for identifier,geometry in geometries.items()),key=lambda item:(item[0],item[1]))[:5]
        candidates=[]
        for distance,identifier,geometry in ranked:
            snapped=geometry.interpolate(geometry.project(point))
            lon,lat=reverse.transform(snapped.x,snapped.y)
            fraction=None
            # Determine upstream-to-downstream orientation from the mapped successor.
            successor=geometries.get(downstream.get(identifier))
            if geometry.geom_type=='LineString' and successor is not None and geometry.length>0:
                start,end=Point(geometry.coords[0]),Point(geometry.coords[-1])
                start_gap,end_gap=start.distance(successor),end.distance(successor)
                if min(start_gap,end_gap)<=100 and abs(start_gap-end_gap)>1:
                    original=geometry.project(snapped)/geometry.length
                    fraction=float(original if end_gap<start_gap else 1-original)
            candidates.append({'hyriv_id':identifier,'snapped_latitude':lat,'snapped_longitude':lon,
                'snap_distance_m':distance,'fraction_along_reach':fraction,
                'fraction_method':'metric geometry projection; successor endpoint gap <=100 m and orientation margin >1 m' if fraction is not None else None,
                'fraction_uncertainty':'Geometry-derived position, not surveyed river-chainage.' if fraction is not None else 'Direction-aware fraction could not be established from available successor geometry (endpoint gap <=100 m and orientation margin >1 m required).',
                'network_member':True})
        nearest=candidates[0]['snap_distance_m'] if candidates else float('inf')
        alternatives=[item for item in candidates if item['snap_distance_m']<=maximum and item['snap_distance_m']-nearest<=ambiguity]
        status='UNSUPPORTED' if nearest>maximum else 'AMBIGUOUS' if len(alternatives)>1 else 'CLOSE' if nearest<=close else 'DISTANT'
        return {'latitude':latitude,'longitude':longitude,'status':status,'review_required':True,
            'candidates':candidates,'alternatives':alternatives,
            'thresholds':{'close_m':close,'maximum_m':maximum,'ambiguity_margin_m':ambiguity},
            'provenance':provenance,'limitations':['Matching covers only the frozen Wigger geometry; it does not establish coverage outside that network.',
            'Thresholds are configurable geographic screening criteria, not validated biological rules.',
            'A confirmed geographic match is MATCHED, never independently scientifically VERIFIED.']}

    def confirm(self, latitude, longitude, hyriv_id, confirmed):
        result=self.match(latitude,longitude)
        candidate=next((item for item in result['alternatives'] if item['hyriv_id']==hyriv_id),None)
        if not confirmed or result['status']=='UNSUPPORTED' or candidate is None:
            raise HTTPException(422,detail={'type':'LocationReviewRequired','message':'Review and explicitly confirm a supported matching alternative'})
        # Retain the frozen Site A representation and provenance if exactly matched.
        frozen=WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR).detection_reference(latitude,longitude,hyriv_id)
        if frozen['validation_status']!='NOT_VERIFIED':
            return frozen
        return {'validation_status':'MATCHED','network_latitude':candidate['snapped_latitude'],
            'network_longitude':candidate['snapped_longitude'],'snap_distance_m':candidate['snap_distance_m'],
            'metadata':{'location_match':result,'selected_match':candidate,'review_confirmed':True,
                        'validation_method':'reviewed_wigger_geometry_match',
                        'validation_reason':'Researcher-confirmed geographic network match; species presence and source origin remain unverified.'}}
