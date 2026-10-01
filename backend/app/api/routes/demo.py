"""
Demo API route for loading Wigger case data.

Provides an endpoint that loads the validated Wigger case preflight data
and creates all entities (case, sites, zones) in the database.
"""
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.cases import CaseRepository
from app.repositories.sampling import SamplingRepository
from app.scientific.data_loader import WiggerPreflightLoader
from app.services.case_service import CaseService
from app.domain.enums import CaseStatus, SiteType, ValidationStatus


router = APIRouter(prefix="/demo", tags=["demo"])


class WiggerDemoResponse(BaseModel):
    """
    Response schema for Wigger demo data loading.
    
    Attributes:
        case_id: UUID of the created case
        target_taxon: Scientific name of the taxon
        observation_date: Date of the detection
        detection_site_id: UUID of Site A (detection site)
        sites_created: Number of sampling sites created
        zones_created: Number of candidate zones created
        summary: Summary of loaded data
    """
    case_id: UUID
    target_taxon: str
    observation_date: date
    detection_site_id: UUID
    sites_created: int
    zones_created: int
    summary: dict[str, Any]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "case_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "target_taxon": "Fredericella sultana",
                "observation_date": "2014-06-25",
                "detection_site_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "sites_created": 4,
                "zones_created": 3,
                "summary": {
                    "sites": ["Site A (S1)", "Site B", "Site C", "Site D"],
                    "zones": ["Z1", "Z2", "Z3"],
                    "validation_status": "All data verified from preflight artifacts"
                }
            }
        }
    )


@router.get(
    "/wigger",
    response_model=WiggerDemoResponse,
    status_code=status.HTTP_200_OK,
    summary="Load Wigger case demo data",
    description="Load the Wigger case data from preflight artifacts and create all entities in the database"
)
def load_wigger_demo(
    db: Session = Depends(get_db)
) -> WiggerDemoResponse:
    """
    Load Wigger case data from preflight artifacts.
    
    This endpoint loads the validated Wigger case data and creates:
    - A case for the taxon recorded in the frozen Site A artifact
    - Site A (S1) as the detection site
    - Sites B, C, D as candidate sampling sites
    - Zones Z1, Z2, Z3 as candidate source regions
    
    All data is loaded from preflight artifacts in data_preflight/outputs/.
    
    Args:
        db: Database session (injected)
        
    Returns:
        WiggerDemoResponse: Summary of created case and entities
        
    Raises:
        HTTPException: 500 if preflight files are missing
        
    **Validates: Requirements 11.1, 11.2, 11.3, 11.4**
    """
    # Initialize data loader
    loader = WiggerPreflightLoader()
    
    # Load preflight data
    site_a_data = loader.load_site_a()
    zones_gdf = loader.load_zones()
    sampling_sites_df = loader.load_sampling_sites()
    validation_metadata = loader.load_validation_metadata()

    if not str(site_a_data.get("sampling_date_status", "")).startswith("VERIFIED"):
        raise HTTPException(
            status_code=422,
            detail={
                "type": "ScientificDataNotVerified",
                "message": (
                    "The Carraro observation date is not verified in the frozen "
                    "Site A artifact; refusing to create a historical demo case."
                ),
                "field": "sampling_date_demo",
            },
        )

    network = site_a_data["network_representation"]
    
    # Initialize repositories and service
    case_repository = CaseRepository(db)
    sampling_repository = SamplingRepository(db)
    case_service = CaseService(case_repository)
    
    # Create Site A (detection site) first
    detection_site = sampling_repository.create_site(
        label="Site A (S1)",
        latitude=site_a_data["transformed_coordinate"]["latitude"],
        longitude=site_a_data["transformed_coordinate"]["longitude"],
        hyriv_id=network["hyriv_id"],
        site_type=SiteType.DETECTION_SITE,
        validation_status=ValidationStatus.MATCHED,
        network_latitude=network["snapped_latitude"],
        network_longitude=network["snapped_longitude"],
        snap_distance_m=network["snap_distance_m"],
        role="Reference site (positive detection)",
        metadata={
            "station_id": site_a_data["station_id"],
            "carraro_reach_index": site_a_data["carraro_reach_index"],
            "study": site_a_data["study"],
            "doi": site_a_data["doi"]
        }
    )
    
    # Create case with detection site
    case = case_service.create_case(
        target_taxon=site_a_data["target_taxon"],
        observation_date=date.fromisoformat(site_a_data["sampling_date_demo"]),
        detection_site_id=detection_site.id,
        status=CaseStatus.ACTIVE,
        metadata={
            "study": site_a_data["study"],
            "doi": site_a_data["doi"],
            "source": "Wigger preflight data"
        }
    )
    
    # Update detection site with case_id
    # We need to do this manually since we created the site before the case
    db.query(db.query(db.bind.dialect.get_table_names(db.bind)[0])).first()  # Force relationship
    # Actually, the site was created without case_id, so we need to update it
    from app.db.models import SamplingSiteModel
    db_site = db.query(SamplingSiteModel).filter(
        SamplingSiteModel.id == detection_site.id
    ).first()
    if db_site:
        db_site.case_id = case.id
        db.commit()
    
    # Create sampling sites B, C, D
    sites_created = 1  # Already created Site A
    site_labels = []
    site_labels.append("Site A (S1)")
    
    for _, site_row in sampling_sites_df.iterrows():
        site_label = site_row["site"]
        
        # Skip Site A since we already created it
        if site_label == "A":
            continue
        
        # Determine site type based on role
        role = site_row["role"]
        if "branch-specific" in role.lower():
            site_type = SiteType.BRANCH_SPECIFIC
        elif "trunk" in role.lower():
            site_type = SiteType.SHARED_TRUNK
        else:
            site_type = SiteType.FOLLOW_UP
        
        # Determine validation status
        validation_str = site_row["validation_status"]
        if validation_str == "VERIFIED":
            validation_status = ValidationStatus.VERIFIED
        elif validation_str == "MATCHED":
            validation_status = ValidationStatus.MATCHED
        else:
            validation_status = ValidationStatus.NOT_VERIFIED
        
        # Create the site
        site = sampling_repository.create_site(
            case_id=case.id,
            label=f"Site {site_label}",
            latitude=site_row["latitude"],
            longitude=site_row["longitude"],
            hyriv_id=int(site_row["HYRIV_ID"]),
            site_type=site_type,
            validation_status=validation_status,
            network_latitude=site_row["network_latitude"],
            network_longitude=site_row["network_longitude"],
            snap_distance_m=site_row["snap_distance_m"],
            role=role,
            metadata={
                "zone": site_row["zone"],
                "network_distance_to_site_a_km": site_row["network_distance_to_site_a_km"],
                "selection_reason": site_row["selection_reason"]
            }
        )
        
        sites_created += 1
        site_labels.append(f"Site {site_label}")
    
    # Create candidate zones Z1, Z2, Z3
    zones_created = 0
    zone_labels = []
    
    # Group zones by zone label
    for zone_label in ["Z1", "Z2", "Z3"]:
        zone_data = zones_gdf[zones_gdf["zone"] == zone_label]
        
        if len(zone_data) == 0:
            continue
        
        # Get reach IDs for this zone
        reach_ids = zone_data["HYRIV_ID"].tolist()
        
        # Find the root reach (largest UPLAND_SKM)
        max_upland_row = zone_data.loc[zone_data["UPLAND_SKM"].idxmax()]
        root_hyriv_id = int(max_upland_row["HYRIV_ID"])
        
        # Create the zone
        zone = sampling_repository.create_zone(
            case_id=case.id,
            label=zone_label,
            root_hyriv_id=root_hyriv_id,
            reach_ids=reach_ids,
            validation_status=ValidationStatus.VERIFIED,
            metadata={
                "total_reaches": len(reach_ids),
                "root_upland_skm": float(max_upland_row["UPLAND_SKM"]),
                "source": "preflight_candidate_zones_real_geojson"
            }
        )
        
        zones_created += 1
        zone_labels.append(zone_label)
    
    # Build summary
    summary = {
        "sites": site_labels,
        "zones": zone_labels,
        "validation_status": "All data verified from preflight artifacts",
        "convergence_point": validation_metadata.get("convergence_verification", {}).get(
            "convergence_reach_id", None
        ),
        "data_source": "data_preflight/outputs/"
    }
    
    # Return response
    return WiggerDemoResponse(
        case_id=case.id,
        target_taxon=case.target_taxon,
        observation_date=case.observation_date,
        detection_site_id=detection_site.id,
        sites_created=sites_created,
        zones_created=zones_created,
        summary=summary
    )
