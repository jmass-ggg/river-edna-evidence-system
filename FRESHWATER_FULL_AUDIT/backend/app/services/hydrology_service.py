"""
Hydrology service for business logic orchestration.

Coordinates HydrologyEngine to provide river network analysis operations.
"""
from typing import Optional

from fastapi import HTTPException

from app.scientific.interfaces import HydrologyEngine
from app.domain.models import RiverReach


class HydrologyService:
    """
    Service for hydrology-related business logic.
    
    Orchestrates hydrology operations, delegates to hydrology engine,
    and provides error handling and validation.
    """
    
    def __init__(self, hydrology_engine: HydrologyEngine):
        """
        Initialize the service with required engine.
        
        Args:
            hydrology_engine: Engine for river network analysis
        """
        self.hydrology_engine = hydrology_engine
    
    def query_upstream_reaches(self, hyriv_id: int) -> list[int]:
        """
        Query all reaches that flow toward the specified reach.
        
        Args:
            hyriv_id: The target reach identifier
            
        Returns:
            list[int]: List of HYRIV_IDs that are upstream
            
        Raises:
            HTTPException: 404 if HYRIV_ID does not exist
        """
        try:
            upstream_reaches = self.hydrology_engine.get_upstream_reaches(hyriv_id)
            return upstream_reaches
        except ValueError as e:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "InvalidHyrivIdError",
                    "message": f"HYRIV_ID {hyriv_id} not found in loaded network data",
                    "hyriv_id": hyriv_id
                }
            )
    
    def query_downstream_path(
        self,
        start_hyriv_id: int,
        stop_hyriv_id: Optional[int] = None
    ) -> list[int]:
        """
        Query the downstream path from start to stop (or terminus).
        
        Args:
            start_hyriv_id: Starting reach identifier
            stop_hyriv_id: Optional stopping reach identifier
            
        Returns:
            list[int]: Ordered list of HYRIV_IDs along the path
            
        Raises:
            HTTPException: 404 if HYRIV_ID does not exist
            HTTPException: 400 if stop is not downstream of start
        """
        try:
            path = self.hydrology_engine.get_downstream_path(
                start_hyriv_id,
                stop_hyriv_id
            )
            return path
        except ValueError as e:
            error_message = str(e)
            # Distinguish between not found and invalid path
            if "not found" in error_message.lower():
                raise HTTPException(
                    status_code=404,
                    detail={
                        "type": "InvalidHyrivIdError",
                        "message": error_message,
                        "start_hyriv_id": start_hyriv_id,
                        "stop_hyriv_id": stop_hyriv_id
                    }
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "type": "InvalidPathError",
                        "message": error_message,
                        "start_hyriv_id": start_hyriv_id,
                        "stop_hyriv_id": stop_hyriv_id
                    }
                )
    
    def check_upstream(self, source_hyriv_id: int, target_hyriv_id: int) -> bool:
        """
        Check if source reach flows toward target reach.
        
        Args:
            source_hyriv_id: Potential upstream reach
            target_hyriv_id: Potential downstream reach
            
        Returns:
            bool: True if source is upstream of target
            
        Raises:
            HTTPException: 404 if either HYRIV_ID does not exist
        """
        try:
            is_upstream = self.hydrology_engine.is_upstream(
                source_hyriv_id,
                target_hyriv_id
            )
            return is_upstream
        except ValueError as e:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "InvalidHyrivIdError",
                    "message": str(e),
                    "source_hyriv_id": source_hyriv_id,
                    "target_hyriv_id": target_hyriv_id
                }
            )
    
    def find_convergence(
        self,
        hyriv_id_a: int,
        hyriv_id_b: int
    ) -> Optional[int]:
        """
        Find where two branches converge.
        
        Args:
            hyriv_id_a: First reach identifier
            hyriv_id_b: Second reach identifier
            
        Returns:
            Optional[int]: HYRIV_ID of convergence point, or None if never converge
            
        Raises:
            HTTPException: 404 if either HYRIV_ID does not exist
        """
        try:
            convergence = self.hydrology_engine.first_common_downstream(
                hyriv_id_a,
                hyriv_id_b
            )
            return convergence
        except ValueError as e:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "InvalidHyrivIdError",
                    "message": str(e),
                    "hyriv_id_a": hyriv_id_a,
                    "hyriv_id_b": hyriv_id_b
                }
            )
    
    def calculate_network_distance(
        self,
        from_hyriv_id: int,
        to_hyriv_id: int
    ) -> Optional[float]:
        """
        Calculate network distance with validation.
        
        Args:
            from_hyriv_id: Source reach identifier
            to_hyriv_id: Target reach identifier
            
        Returns:
            Optional[float]: Distance in kilometers, or None if not connected
            
        Raises:
            HTTPException: 404 if either HYRIV_ID does not exist
            HTTPException: 400 if distance is requested but reaches are not connected
        """
        try:
            distance = self.hydrology_engine.network_distance_km(
                from_hyriv_id,
                to_hyriv_id
            )
            
            # If distance is None, reaches are not connected
            if distance is None:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "type": "NotConnectedError",
                        "message": f"Reach {from_hyriv_id} is not upstream of reach {to_hyriv_id}",
                        "from_hyriv_id": from_hyriv_id,
                        "to_hyriv_id": to_hyriv_id
                    }
                )
            
            return distance
        except ValueError as e:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "InvalidHyrivIdError",
                    "message": str(e),
                    "from_hyriv_id": from_hyriv_id,
                    "to_hyriv_id": to_hyriv_id
                }
            )
    
    def get_reach(self, hyriv_id: int) -> RiverReach:
        """
        Retrieve reach metadata by HYRIV_ID.
        
        Args:
            hyriv_id: The reach identifier
            
        Returns:
            RiverReach: Reach with all metadata
            
        Raises:
            HTTPException: 404 if HYRIV_ID does not exist
        """
        try:
            reach = self.hydrology_engine.get_reach(hyriv_id)
            return reach
        except ValueError as e:
            raise HTTPException(
                status_code=404,
                detail={
                    "type": "InvalidHyrivIdError",
                    "message": f"HYRIV_ID {hyriv_id} not found in loaded network data",
                    "hyriv_id": hyriv_id
                }
            )
