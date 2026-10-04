"""
Pydantic schemas for hydrology analysis endpoints.

These schemas define request/response structures for hydrology-related API operations.
"""

from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class ReachResponse(BaseModel):
    """
    Response schema for river reach metadata.
    
    Attributes:
        hyriv_id: Unique HydroRIVERS reach identifier
        next_down: HYRIV_ID of the downstream reach (None if terminal)
        length_km: Reach length in kilometers
        upland_skm: Upstream contributing area in square kilometers
        dis_av_cms: Average discharge in cubic meters per second
    """
    hyriv_id: int
    next_down: int | None
    length_km: float
    upland_skm: float
    dis_av_cms: float

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "hyriv_id": 20449905,
                "next_down": 20449906,
                "length_km": 2.5,
                "upland_skm": 450.3,
                "dis_av_cms": 12.7
            }
        }
    )


class UpstreamQueryResponse(BaseModel):
    """
    Response schema for upstream reach queries.
    
    Attributes:
        target_hyriv_id: The reach that was queried
        upstream_reach_ids: List of all reach IDs that flow toward the target
        count: Number of upstream reaches found
    """
    target_hyriv_id: int
    upstream_reach_ids: list[int]
    count: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "target_hyriv_id": 20449905,
                "upstream_reach_ids": [20450127, 20451169, 20449904, 20449903],
                "count": 4
            }
        }
    )


class DownstreamPathResponse(BaseModel):
    """
    Response schema for downstream path queries.
    
    Attributes:
        start_hyriv_id: The starting reach
        stop_hyriv_id: The stopping reach (None if path to terminus)
        path: Ordered list of reach IDs from start to stop
        length: Number of reaches in the path
    """
    start_hyriv_id: int
    stop_hyriv_id: int | None
    path: list[int]
    length: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "start_hyriv_id": 20450127,
                "stop_hyriv_id": 20449905,
                "path": [20450127, 20449906, 20449905],
                "length": 3
            }
        }
    )


class NetworkDistanceResponse(BaseModel):
    """
    Response schema for network distance calculations.
    
    Attributes:
        from_hyriv_id: Starting reach
        to_hyriv_id: Target reach
        distance_km: Network distance in kilometers (None if not connected)
        path: Ordered list of reach IDs in the path (None if not connected)
    """
    from_hyriv_id: int
    to_hyriv_id: int
    distance_km: float | None
    path: list[int] | None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "from_hyriv_id": 20450127,
                "to_hyriv_id": 20449905,
                "distance_km": 8.3,
                "path": [20450127, 20449906, 20449905]
            }
        }
    )
