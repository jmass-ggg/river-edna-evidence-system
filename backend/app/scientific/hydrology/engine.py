"""
Hydrology engine implementation for river network analysis.

This engine performs deterministic graph operations using HydroRIVERS data
loaded from validated preflight artifacts.
"""

from typing import Any
import pandas as pd

from app.domain.models import RiverReach


class HydrologyEngine:
    """
    River network analysis engine using HydroRIVERS data.
    
    This implementation builds directed graph structures from preflight data
    and provides efficient network queries for reachability, distance, and
    connectivity analysis.
    """
    
    def __init__(self, reaches: pd.DataFrame, edges: pd.DataFrame):
        """
        Initialize the hydrology engine with network data.
        
        Args:
            reaches: DataFrame with columns HYRIV_ID, NEXT_DOWN, LENGTH_KM,
                    UPLAND_SKM, DIS_AV_CMS
            edges: DataFrame with columns upstream, downstream
        """
        self._reaches_df = reaches
        self._edges_df = edges
        
        # Build reach metadata lookup
        self._reaches: dict[int, RiverReach] = {}
        for _, row in reaches.iterrows():
            hyriv_id = int(row['HYRIV_ID'])
            next_down = int(row['NEXT_DOWN']) if pd.notna(row['NEXT_DOWN']) else None
            self._reaches[hyriv_id] = RiverReach(
                hyriv_id=hyriv_id,
                next_down=next_down,
                length_km=float(row['LENGTH_KM']),
                upland_skm=float(row['UPLAND_SKM']),
                dis_av_cms=float(row['DIS_AV_CMS']),
                geometry=None
            )
        
        # Build directed graph: hyriv_id -> next_down
        self._downstream_graph: dict[int, int | None] = {}
        for hyriv_id, reach in self._reaches.items():
            self._downstream_graph[hyriv_id] = reach.next_down
        
        # Build reverse graph for upstream queries: hyriv_id -> list of upstream reaches
        self._upstream_graph: dict[int, list[int]] = {}
        for hyriv_id in self._reaches.keys():
            self._upstream_graph[hyriv_id] = []
        
        # Populate upstream graph from edges
        for _, edge in edges.iterrows():
            upstream = int(edge['upstream'])
            downstream = int(edge['downstream'])
            if downstream in self._upstream_graph:
                self._upstream_graph[downstream].append(upstream)
    
    def get_reach(self, hyriv_id: int) -> RiverReach:
        """
        Retrieve reach metadata by HYRIV_ID.
        
        Args:
            hyriv_id: The HydroRIVERS reach identifier
            
        Returns:
            RiverReach with all metadata
            
        Raises:
            ValueError: If HYRIV_ID does not exist in loaded network
        """
        if hyriv_id not in self._reaches:
            raise ValueError(
                f"HYRIV_ID {hyriv_id} not found in loaded network data"
            )
        return self._reaches[hyriv_id]
    
    def get_upstream_reaches(self, hyriv_id: int) -> list[int]:
        """
        Return all reach IDs that flow toward the specified reach.
        
        Uses graph traversal to find all reaches upstream of the target.
        
        Args:
            hyriv_id: The target reach identifier
            
        Returns:
            List of HYRIV_IDs that are upstream of the target
            
        Raises:
            ValueError: If HYRIV_ID does not exist in loaded network
        """
        if hyriv_id not in self._reaches:
            raise ValueError(
                f"HYRIV_ID {hyriv_id} not found in loaded network data"
            )
        
        # Use BFS to find all upstream reaches
        upstream = []
        visited = set()
        queue = [hyriv_id]
        
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            
            # Add immediate upstream reaches
            for upstream_reach in self._upstream_graph.get(current, []):
                if upstream_reach not in visited:
                    upstream.append(upstream_reach)
                    queue.append(upstream_reach)
        
        return upstream
    
    def get_downstream_path(
        self,
        start_hyriv_id: int,
        stop_hyriv_id: int | None = None
    ) -> list[int]:
        """
        Return ordered reach IDs from start to stop (or terminus).
        
        Follows NEXT_DOWN relationships to build the path.
        
        Args:
            start_hyriv_id: Starting reach identifier
            stop_hyriv_id: Optional stopping reach identifier
            
        Returns:
            Ordered list of HYRIV_IDs from start to stop/terminus
            
        Raises:
            ValueError: If start or stop HYRIV_ID does not exist
            ValueError: If stop is not downstream of start
        """
        if start_hyriv_id not in self._reaches:
            raise ValueError(
                f"HYRIV_ID {start_hyriv_id} not found in loaded network data"
            )
        if stop_hyriv_id is not None and stop_hyriv_id not in self._reaches:
            raise ValueError(
                f"HYRIV_ID {stop_hyriv_id} not found in loaded network data"
            )
        
        path = [start_hyriv_id]
        current = start_hyriv_id
        visited = {start_hyriv_id}
        
        while True:
            next_down = self._downstream_graph.get(current)
            
            if next_down is None or next_down not in self._reaches:
                # Reached the boundary of the loaded network.
                break

            if next_down in visited:
                raise ValueError(
                    f"Cycle detected while traversing downstream from {start_hyriv_id}"
                )
            
            path.append(next_down)
            visited.add(next_down)
            
            if stop_hyriv_id is not None and next_down == stop_hyriv_id:
                # Reached stop point
                break
            
            current = next_down
        
        # Validate that we reached the stop if specified
        if stop_hyriv_id is not None and path[-1] != stop_hyriv_id:
            raise ValueError(
                f"HYRIV_ID {stop_hyriv_id} is not downstream of {start_hyriv_id}"
            )
        
        return path
    
    def is_upstream(self, source_hyriv_id: int, target_hyriv_id: int) -> bool:
        """
        Check if source reach flows toward target reach.
        
        Args:
            source_hyriv_id: Potential upstream reach
            target_hyriv_id: Potential downstream reach
            
        Returns:
            True if source is upstream of target, False otherwise
            
        Raises:
            ValueError: If either HYRIV_ID does not exist
        """
        if source_hyriv_id not in self._reaches:
            raise ValueError(
                f"HYRIV_ID {source_hyriv_id} not found in loaded network data"
            )
        if target_hyriv_id not in self._reaches:
            raise ValueError(
                f"HYRIV_ID {target_hyriv_id} not found in loaded network data"
            )
        
        # If they're the same, source is not upstream of itself
        if source_hyriv_id == target_hyriv_id:
            return False
        
        # Follow downstream path from source and check if we reach target
        current = source_hyriv_id
        visited = set()
        
        while current is not None:
            if current in visited:
                # Cycle detected, stop
                break
            visited.add(current)
            
            next_down = self._downstream_graph.get(current)
            if next_down == target_hyriv_id:
                return True
            current = next_down
        
        return False

    def can_contribute(self, source_hyriv_id: int, site_hyriv_id: int) -> bool:
        """Return whether a source reach can reach a site at reach resolution.

        A source on the same mapped reach is treated as topologically capable
        of contributing. This says nothing about transport or detection.
        """
        self.get_reach(source_hyriv_id)
        self.get_reach(site_hyriv_id)
        return (
            source_hyriv_id == site_hyriv_id
            or self.is_upstream(source_hyriv_id, site_hyriv_id)
        )
    
    def first_common_downstream(
        self,
        hyriv_id_a: int,
        hyriv_id_b: int
    ) -> int | None:
        """
        Find where two branches converge.
        
        Returns the first reach that is downstream of both input reaches.
        
        Args:
            hyriv_id_a: First reach identifier
            hyriv_id_b: Second reach identifier
            
        Returns:
            HYRIV_ID of convergence point, or None if branches never converge
            
        Raises:
            ValueError: If either HYRIV_ID does not exist
        """
        if hyriv_id_a not in self._reaches:
            raise ValueError(
                f"HYRIV_ID {hyriv_id_a} not found in loaded network data"
            )
        if hyriv_id_b not in self._reaches:
            raise ValueError(
                f"HYRIV_ID {hyriv_id_b} not found in loaded network data"
            )
        
        # If they're the same, that's the convergence
        if hyriv_id_a == hyriv_id_b:
            return hyriv_id_a
        
        # Build downstream path from A
        path_a = set()
        current = hyriv_id_a
        while current in self._reaches and current not in path_a:
            path_a.add(current)
            current = self._downstream_graph.get(current)
        
        # Follow downstream from B until we hit something in A's path
        current = hyriv_id_b
        visited_b = set()
        while current in self._reaches and current not in visited_b:
            if current in path_a:
                return current
            visited_b.add(current)
            current = self._downstream_graph.get(current)
        
        return None
    
    def network_distance_km(
        self,
        from_hyriv_id: int,
        to_hyriv_id: int,
        from_fraction: float = 0.5,
        to_fraction: float = 0.5,
    ) -> float | None:
        """
        Calculate network distance using LENGTH_KM.
        
        Uses the remaining fraction of the source reach, complete intermediate
        reaches, and the destination fraction of the target reach. Fractions
        follow the stored upstream-to-downstream direction.
        
        Args:
            from_hyriv_id: Source reach identifier
            to_hyriv_id: Target reach identifier
            from_fraction: Start position on source reach in [0, 1]
            to_fraction: End position on target reach in [0, 1]
            
        Returns:
            Distance in kilometers, or None if not connected
            
        Raises:
            ValueError: If either HYRIV_ID does not exist
        """
        if from_hyriv_id not in self._reaches:
            raise ValueError(
                f"HYRIV_ID {from_hyriv_id} not found in loaded network data"
            )
        if to_hyriv_id not in self._reaches:
            raise ValueError(
                f"HYRIV_ID {to_hyriv_id} not found in loaded network data"
            )
        
        for name, fraction in (
            ("from_fraction", from_fraction),
            ("to_fraction", to_fraction),
        ):
            if not 0.0 <= fraction <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

        # On one reach, only downstream movement is valid.
        if from_hyriv_id == to_hyriv_id:
            if to_fraction < from_fraction:
                return None
            return self._reaches[from_hyriv_id].length_km * (
                to_fraction - from_fraction
            )
        
        # Check if to is downstream of from
        if not self.is_upstream(from_hyriv_id, to_hyriv_id):
            return None
        
        # Get the path and sum lengths
        try:
            path = self.get_downstream_path(from_hyriv_id, to_hyriv_id)
        except ValueError:
            return None
        
        distance = self._reaches[path[0]].length_km * (1.0 - from_fraction)
        for reach_id in path[1:-1]:
            distance += self._reaches[reach_id].length_km
        distance += self._reaches[path[-1]].length_km * to_fraction
        
        return distance
    
    def zone_can_contribute_to_site(
        self,
        zone_reaches: list[int],
        site_hyriv_id: int
    ) -> bool:
        """
        Check if any reach in zone flows to site.
        
        Args:
            zone_reaches: List of HYRIV_IDs comprising the zone
            site_hyriv_id: The site reach identifier
            
        Returns:
            True if at least one zone reach is upstream of site
            
        Raises:
            ValueError: If any HYRIV_ID does not exist
        """
        if site_hyriv_id not in self._reaches:
            raise ValueError(
                f"HYRIV_ID {site_hyriv_id} not found in loaded network data"
            )
        
        for zone_reach in zone_reaches:
            if zone_reach not in self._reaches:
                raise ValueError(
                    f"HYRIV_ID {zone_reach} not found in loaded network data"
                )
            
            if self.can_contribute(zone_reach, site_hyriv_id):
                return True
        
        return False
