"""
Demo API route for loading Wigger case data.

Provides an endpoint that loads the validated Wigger case preflight data
and creates all entities (case, sites, zones) in the database.
"""
from datetime import date, datetime, time, timezone
import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.repositories.cases import CaseRepository
from app.repositories.evidence import EvidenceRepository
from app.repositories.sampling import SamplingRepository
from app.scientific.data_loader import CarraroHistoricalLoader, WiggerPreflightLoader
from app.scientific.hydrology.engine import HydrologyEngine
from app.services.case_service import CaseService
from app.domain.enums import CaseStatus, SiteType, ValidationStatus
from config import config


router = APIRouter(prefix="/demo", tags=["demo"])
DEMO_KEY = "wigger-carraro-h001-v1"


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


class WiggerMapResponse(BaseModel):
    """Validated preflight geometry and site records for map presentation."""

    crs: str
    river_network: dict[str, Any]
    source_zones: dict[str, Any]
    sites: list[dict[str, Any]]
    provenance: dict[str, Any]


@router.get(
    "/wigger/map",
    response_model=WiggerMapResponse,
    status_code=status.HTTP_200_OK,
    summary="Get validated Wigger map data",
)
def get_wigger_map() -> WiggerMapResponse:
    """Return frozen Wigger GeoJSON and sites without creating database rows."""
    loader = WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR)
    river_path = config.PREFLIGHT_DATA_DIR / "upstream_reaches_real.geojson"
    zones_path = config.PREFLIGHT_DATA_DIR / "candidate_zones_real.geojson"
    river_network = json.loads(river_path.read_text(encoding="utf-8"))
    source_zones = json.loads(zones_path.read_text(encoding="utf-8"))
    sites_frame = loader.load_sampling_sites()
    sites = []
    for row in sites_frame.to_dict(orient="records"):
        sites.append({
            "label": str(row["site"]),
            "role": str(row["role"]),
            "hyriv_id": int(row["HYRIV_ID"]),
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "network_latitude": float(row["network_latitude"]),
            "network_longitude": float(row["network_longitude"]),
            "snap_distance_m": float(row["snap_distance_m"]),
            "zone": str(row["zone"]),
            "network_distance_to_site_a_km": float(
                row["network_distance_to_site_a_km"]
            ),
            "selection_reason": str(row["selection_reason"]),
            "validation_status": str(row["validation_status"]),
        })
    return WiggerMapResponse(
        crs="EPSG:4326",
        river_network=river_network,
        source_zones=source_zones,
        sites=sites,
        provenance={
            "river_network": str(river_path),
            "source_zones": str(zones_path),
            "sites": str(config.PREFLIGHT_DATA_DIR / "candidate_sampling_sites.csv"),
            "status": "validated preflight artifacts",
        },
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
    loader = WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR)
    historical_loader = CarraroHistoricalLoader(config.CARRARO_DATA_DIR)
    
    # Load preflight data
    site_a_data = loader.load_site_a()
    zones_gdf = loader.load_zones()
    sampling_sites_df = loader.load_sampling_sites()
    validation_metadata = loader.load_validation_metadata()
    historical_observation = historical_loader.load_h001()
    historical_metadata = {
        **historical_observation,
        "date": historical_observation["date"].isoformat(),
    }

    # GET remains safe to repeat: locate the single persisted demonstration
    # before creating any database records. Older demo rows are recognized by
    # their exact frozen H001 provenance and upgraded with the stable key.
    from app.db.models import CaseModel
    existing = None
    for candidate in db.scalars(select(CaseModel)).all():
        meta = candidate.meta or {}
        observed = meta.get("historical_observation", {})
        if meta.get("demo_key") == DEMO_KEY or (
            candidate.target_taxon == historical_observation["species"]
            and candidate.observation_date == historical_observation["date"]
            and observed.get("station") == "S1"
            and observed.get("observation_index") == 4
        ):
            existing = candidate
            break
    if existing is not None:
        existing.meta = {
            **(existing.meta or {}),
            "demo_key": DEMO_KEY,
            "name": "Wigger River Investigation",
        }
        db.commit()
        sampling_repository = SamplingRepository(db)
        zones = sampling_repository.get_zones_by_case(existing.id)
        sites = sampling_repository.get_sites_by_case(existing.id)
        _ensure_wigger_evidence(
            db, existing.id, historical_observation, loader, zones,
            site_a_data["network_representation"]["hyriv_id"],
        )
        return WiggerDemoResponse(
            case_id=existing.id,
            target_taxon=existing.target_taxon,
            observation_date=existing.observation_date,
            detection_site_id=existing.detection_site_id,
            sites_created=len(sites),
            zones_created=len(zones),
            summary={
                "sites": [site.label for site in sites],
                "zones": [zone.label for zone in zones],
                "validation_status": "All data verified from preflight artifacts",
                "historical_observation": historical_observation,
                "network_metadata_source": str(config.PREFLIGHT_DATA_DIR / "site_a.json"),
                "data_source": str(config.PREFLIGHT_DATA_DIR),
                "idempotent_reuse": True,
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
            "doi": site_a_data["doi"],
            "metadata_role": "NETWORK_REPRESENTATION",
            "network_source": str(config.PREFLIGHT_DATA_DIR / "site_a.json"),
        }
    )
    
    # Create case with detection site
    case = case_service.create_case(
        target_taxon=historical_observation["species"],
        observation_date=historical_observation["date"],
        detection_site_id=detection_site.id,
        status=CaseStatus.ACTIVE,
        metadata={
            "demo_key": DEMO_KEY,
            "name": "Wigger River Investigation",
            "study": site_a_data["study"],
            "doi": site_a_data["doi"],
            "historical_observation": historical_metadata,
            "network_representation": {
                "hyriv_id": network["hyriv_id"],
                "source": str(config.PREFLIGHT_DATA_DIR / "site_a.json"),
            },
        }
    )
    
    # Update detection site with case_id
    # We need to do this manually since we created the site before the case
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

    _ensure_wigger_evidence(
        db, case.id, historical_observation, loader,
        sampling_repository.get_zones_by_case(case.id), network["hyriv_id"],
    )
    
    # Build summary
    summary = {
        "sites": site_labels,
        "zones": zone_labels,
        "validation_status": "All data verified from preflight artifacts",
        "historical_observation": historical_observation,
        "network_metadata_source": str(config.PREFLIGHT_DATA_DIR / "site_a.json"),
        "convergence_point": validation_metadata.get("convergence_verification", {}).get(
            "convergence_reach_id", None
        ),
        "data_source": str(config.PREFLIGHT_DATA_DIR),
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


def _ensure_wigger_evidence(
    db: Session, case_id: UUID, historical: dict[str, Any],
    loader: WiggerPreflightLoader, zones: list, site_a_hyriv_id: int,
) -> None:
    """Idempotently persist the observed H001 record and validated topology."""
    repository = EvidenceRepository(db)
    existing = repository.get_evidence_by_case(case_id)
    keys = {item.provenance.get("demo_evidence_key") for item in existing}
    historical_key = "carraro-h001-fs-s1-observation-4"
    if historical_key not in keys:
        repository.add_evidence(
            case_id=case_id,
            evidence_type="historical_edna_measurement",
            source=historical["provenance"]["edna_source"],
            value={
                "station": historical["station"],
                "species_code": historical["species_code"],
                "species": historical["species"],
                "observation_index": historical["observation_index"],
                "date": historical["date"].isoformat(),
                "concentration_mol_l": historical["concentration_mol_l"],
                "state": historical["state"],
            },
            observed_at=datetime.combine(historical["date"], time.min, timezone.utc),
            quality="SOURCE_VERIFIED",
            provenance={
                **historical["provenance"],
                "demo_evidence_key": historical_key,
                "observation_class": "OBSERVED",
            },
        )
    hydrology = HydrologyEngine(loader.load_reaches(), loader.load_edges())
    for zone in zones:
        evidence_key = f"hydrorivers-{zone.label}-to-site-a"
        if evidence_key in keys:
            continue
        repository.add_evidence(
            case_id=case_id,
            evidence_type="directed_hydrological_connectivity",
            source="HydroRIVERS NEXT_DOWN traversal",
            value={
                "zone_root_hyriv_id": zone.root_hyriv_id,
                "site_hyriv_id": site_a_hyriv_id,
                "can_contribute": hydrology.can_contribute(
                    zone.root_hyriv_id, site_a_hyriv_id
                ),
                "network_validation_status": ValidationStatus.MATCHED.value,
            },
            quality="VERIFIED",
            provenance={
                "demo_evidence_key": evidence_key,
                "network_source": str(
                    config.PREFLIGHT_DATA_DIR / "upstream_edges.csv"
                ),
                "zone_label": zone.label,
                "observation_class": "DERIVED_VALIDATED_TOPOLOGY",
            },
        )


def reuse_wigger_reference(db: Session, case_id: UUID) -> dict[str, Any]:
    """Reuse frozen hypotheses/sites only for the exact Site A demonstration location.

    This imports topology, never Carraro observations or biological validation.
    Existing manual definitions are never upgraded or overwritten.
    """
    from app.api.routes.sampling import _get_case
    from app.db.models import CaseModel
    # Serialize repeated imports for a case on PostgreSQL.
    db.execute(select(CaseModel).where(CaseModel.id == case_id).with_for_update()).scalar_one_or_none()
    case = _get_case(db, case_id)
    repository = SamplingRepository(db)
    detection = repository.get_site_by_id(case.detection_site_id)
    try:
        loader = WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR)
        hashes = loader.validate_frozen_reference()
    except (ValueError, OSError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    validation = loader.detection_reference(detection.latitude, detection.longitude, detection.hyriv_id)
    if validation["validation_status"] == ValidationStatus.NOT_VERIFIED.value:
        raise HTTPException(status_code=422, detail=validation["metadata"]["validation_reason"])
    if detection.case_id != case_id:
        raise HTTPException(status_code=409, detail="Detection site does not belong to this investigation")
    zones = repository.get_zones_by_case(case_id)
    sites = repository.get_sites_by_case(case_id)
    source = "frozen-wigger-reference-v1"
    original_demo = case.metadata.get("demo_key") == DEMO_KEY
    # The original demo has older provenance fields; retain those records only
    # after checking their frozen definitions and original validation below.
    def original_zone(zone):
        return original_demo and zone.metadata.get("source") == "preflight_candidate_zones_real_geojson"

    # Refuse conflicts instead of silently verifying user-entered data.
    if any(zone.metadata.get("reference_key") != source and not original_zone(zone) for zone in zones):
        raise HTTPException(status_code=409, detail="Existing manual hypotheses conflict with the frozen Wigger reference; they remain NOT_VERIFIED")
    definitions = loader.load_zones()
    rows = loader.load_sampling_sites()
    for zone in zones:
        group = definitions[definitions["zone"] == zone.label]
        if (group.empty or zone.validation_status != ValidationStatus.VERIFIED
                or (zone.metadata.get("artifact_sha256") != hashes and not original_zone(zone))
                or set(zone.reach_ids) != {int(value) for value in group["HYRIV_ID"]}
                or zone.root_hyriv_id != int(group.loc[group["UPLAND_SKM"].idxmax()]["HYRIV_ID"])):
            raise HTTPException(status_code=409, detail="Existing hypotheses do not match verified frozen provenance; no records were imported")
    for _, row in rows.iterrows():
        if row["site"] == "A":
            continue
        for site in sites:
            if (site.label == f"Site {row['site']}" or site.hyriv_id == int(row["HYRIV_ID"])) and (
                    (site.metadata.get("reference_key") != source and not original_demo)
                    or (site.metadata.get("artifact_sha256") != hashes and not original_demo)
                    or site.validation_status != ValidationStatus(row["validation_status"])
                    or site.hyriv_id != int(row["HYRIV_ID"])
                    or site.latitude != float(row["latitude"])
                    or site.longitude != float(row["longitude"])
                    or site.network_latitude != float(row["network_latitude"])
                    or site.network_longitude != float(row["network_longitude"])
                    or site.snap_distance_m != float(row["snap_distance_m"])
                    or site.role != row["role"]
                    or site.metadata.get("selection_reason") != row["selection_reason"]
                ):
                raise HTTPException(status_code=409, detail="Existing field site conflicts with Wigger reference; no records were imported")
    try:
        from app.db.models import SamplingSiteModel
        stored_detection = db.get(SamplingSiteModel, detection.id)
        stored_detection.validation_status = validation["validation_status"]
        stored_detection.network_latitude = validation["network_latitude"]
        stored_detection.network_longitude = validation["network_longitude"]
        stored_detection.snap_distance_m = validation["snap_distance_m"]
        stored_detection.meta = {**(stored_detection.meta or {}), **validation["metadata"]}
        for label in ["Z1", "Z2", "Z3"]:
            if any(zone.label == label for zone in zones):
                continue
            group = definitions[definitions["zone"] == label]
            root = group.loc[group["UPLAND_SKM"].idxmax()]
            repository.create_zone(case_id, label, int(root["HYRIV_ID"]),
                                   [int(value) for value in group["HYRIV_ID"]], ValidationStatus.VERIFIED,
                                   metadata={"reference_key": source, "artifact_sha256": hashes}, commit=False)
        for _, row in rows.iterrows():
            label = f"Site {row['site']}"
            if row["site"] == "A" or any(site.label == label for site in sites):
                continue
            repository.create_site(case_id=case_id, label=label, latitude=float(row["latitude"]),
                longitude=float(row["longitude"]), hyriv_id=int(row["HYRIV_ID"]),
                site_type=SiteType.SHARED_TRUNK if "trunk" in row["role"].lower() else SiteType.BRANCH_SPECIFIC,
                validation_status=ValidationStatus(row["validation_status"]), role=row["role"],
                network_latitude=float(row["network_latitude"]), network_longitude=float(row["network_longitude"]),
                snap_distance_m=float(row["snap_distance_m"]),
                metadata={"reference_key": source, "artifact_sha256": hashes, "selection_reason": row["selection_reason"], "zone": row["zone"], "network_distance_to_site_a_km": float(row["network_distance_to_site_a_km"])}, commit=False)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"case_id": str(case_id), "reference_key": source,
            "limitations": "Frozen topology demonstration only; recorded evidence remains user-entered. Detection network MATCHED status is reused only for the frozen Site A observation coordinates and reach."}
