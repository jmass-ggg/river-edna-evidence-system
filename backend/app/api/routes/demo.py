"""
Demo API route for loading Wigger case data.

Provides an endpoint that loads the validated Wigger case preflight data
and creates all entities (case, sites, zones) in the database.
"""
from datetime import date, datetime, time
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
    """Create or recover one trusted reference case in a single transaction.

    Caller-owned demo metadata is deliberately not used to select a case.
    PostgreSQL serializes creation before the singleton row exists; the unique
    server-only reference key also protects the persisted identity.
    """
    from app.db.models import CaseModel, SamplingSiteModel
    from sqlalchemy import text

    try:
        # Complete all artifact checks before any write or reference promotion.
        loader = WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR)
        hashes = loader.validate_frozen_reference()
        historical_loader = CarraroHistoricalLoader(config.CARRARO_DATA_DIR)
        historical_hashes = historical_loader.validate_frozen_reference()
        historical = historical_loader.load_h001()
        site_a = loader.load_site_a()
        loader.load_zones()
        loader.load_sampling_sites()
        validation = loader.detection_reference(
            site_a["transformed_coordinate"]["latitude"],
            site_a["transformed_coordinate"]["longitude"],
            site_a["network_representation"]["hyriv_id"],
        )
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(1179797320, 1)"))
        existing = db.scalar(select(CaseModel).where(CaseModel.reference_key == DEMO_KEY).with_for_update())
        reused = existing is not None
        repository = SamplingRepository(db)
        historical_metadata = {**historical, "date": historical["date"].isoformat()}
        if existing is None:
            detection = repository.create_site(
                label="Site A (S1)",
                latitude=site_a["transformed_coordinate"]["latitude"],
                longitude=site_a["transformed_coordinate"]["longitude"],
                hyriv_id=site_a["network_representation"]["hyriv_id"],
                site_type=SiteType.DETECTION_SITE,
                validation_status=ValidationStatus.MATCHED,
                network_latitude=validation["network_latitude"],
                network_longitude=validation["network_longitude"],
                snap_distance_m=validation["snap_distance_m"],
                role="Reference site (positive detection)",
                metadata={"station_id": site_a["station_id"], **validation["metadata"]},
                commit=False,
            )
            case = CaseService(CaseRepository(db)).create_case(
                target_taxon=historical["species"], observation_date=historical["date"],
                detection_site_id=detection.id, status=CaseStatus.ACTIVE,
                metadata={"demo_key": DEMO_KEY, "name": "Wigger River Investigation",
                          "study": site_a["study"], "doi": site_a["doi"],
                          "historical_observation": historical_metadata,
                          "network_representation": {"hyriv_id": detection.hyriv_id,
                              "source": str(config.PREFLIGHT_DATA_DIR / "site_a.json")}},
                commit=False,
            )
            existing = db.get(CaseModel, case.id)
            existing.reference_key = DEMO_KEY
            db.get(SamplingSiteModel, detection.id).case_id = case.id
            db.flush()
        elif (existing.target_taxon != historical["species"]
                or existing.observation_date != historical["date"]
                or (existing.meta or {}).get("historical_observation") != historical_metadata):
            raise HTTPException(status_code=409, detail="Trusted demo observation conflicts with frozen H001; no records were changed")

        detection = db.get(SamplingSiteModel, existing.detection_site_id)
        if (detection is None or detection.case_id not in (None, existing.id)
                or detection.site_type != SiteType.DETECTION_SITE.value
                or detection.latitude != site_a["transformed_coordinate"]["latitude"]
                or detection.longitude != site_a["transformed_coordinate"]["longitude"]
                or detection.hyriv_id != site_a["network_representation"]["hyriv_id"]):
            raise HTTPException(status_code=409, detail="Trusted demo detection reference conflicts with frozen Site A")
        # A nullable backlink is the safely repairable old circular-link failure.
        detection.case_id = existing.id
        db.flush()
        reuse_wigger_reference(db, existing.id, commit=False)
        zones = repository.get_zones_by_case(existing.id)
        evidence_id = _ensure_wigger_evidence(db, existing.id, historical, loader, zones, detection.hyriv_id)
        existing.reference_provenance = {
            "loader": "wigger-carraro-h001-v1", "artifact_sha256": hashes,
            "historical_artifact_sha256": historical_hashes,
            "historical_evidence_id": str(evidence_id),
        }
        sites = repository.get_sites_by_case(existing.id)
        response = WiggerDemoResponse(
            case_id=existing.id, target_taxon=existing.target_taxon,
            observation_date=existing.observation_date, detection_site_id=existing.detection_site_id,
            sites_created=len(sites), zones_created=len(zones),
            summary={"sites": [site.label for site in sites], "zones": [zone.label for zone in zones],
                     "validation_status": "All data verified from preflight artifacts",
                     "historical_observation": historical,
                     "network_metadata_source": str(config.PREFLIGHT_DATA_DIR / "site_a.json"),
                     "data_source": str(config.PREFLIGHT_DATA_DIR), "idempotent_reuse": reused},
        )
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


def _ensure_wigger_evidence(
    db: Session, case_id: UUID, historical: dict[str, Any],
    loader: WiggerPreflightLoader, zones: list, site_a_hyriv_id: int,
) -> UUID:
    """Validate existing reference evidence and insert only missing records."""
    repository = EvidenceRepository(db)
    existing = repository.get_evidence_by_case(case_id)
    hydrology = HydrologyEngine(loader.load_reaches(), loader.load_edges())
    expected = [{
        "key": "carraro-h001-fs-s1-observation-4",
        "evidence_type": "historical_edna_measurement",
        "source": historical["provenance"]["edna_source"],
        "value": {key: historical[key] for key in (
            "station", "species_code", "species", "observation_index", "concentration_mol_l", "state")}
                 | {"date": historical["date"].isoformat()},
        # The existing column is timestamp without time zone. H001 supplies a
        # date, not a measurement time; avoid PostgreSQL session-TZ conversion.
        "observed_at": datetime.combine(historical["date"], time.min),
        "quality": "SOURCE_VERIFIED",
        "provenance": {**historical["provenance"],
                       "demo_evidence_key": "carraro-h001-fs-s1-observation-4", "observation_class": "OBSERVED"},
    }]
    for zone in zones:
        key = f"hydrorivers-{zone.label}-to-site-a"
        expected.append({
            "key": key, "evidence_type": "directed_hydrological_connectivity",
            "source": "HydroRIVERS NEXT_DOWN traversal",
            "value": {"zone_root_hyriv_id": zone.root_hyriv_id, "site_hyriv_id": site_a_hyriv_id,
                      "can_contribute": hydrology.can_contribute(zone.root_hyriv_id, site_a_hyriv_id),
                      "network_validation_status": ValidationStatus.MATCHED.value},
            "quality": "VERIFIED", "provenance": {"demo_evidence_key": key,
                "network_source": str(loader.data_dir / "upstream_edges.csv"),
                "zone_label": zone.label, "observation_class": "DERIVED_VALIDATED_TOPOLOGY"},
        })
    historical_id = None
    for item in expected:
        matches = [row for row in existing if row.provenance.get("demo_evidence_key") == item["key"]]
        if len(matches) > 1 or any(
            row.evidence_type != item["evidence_type"] or row.source != item["source"]
            or row.value != item["value"] or row.provenance != item["provenance"]
            or row.quality != item["quality"]
            or ("observed_at" in item and (row.observed_at is None
                or row.observed_at != item["observed_at"]))
            for row in matches
        ):
            raise HTTPException(status_code=409, detail="Existing reference evidence conflicts with frozen provenance")
        values = {key: value for key, value in item.items() if key != "key"}
        row = matches[0] if matches else repository.add_evidence(case_id=case_id, **values, commit=False)
        if item["evidence_type"] == "historical_edna_measurement":
            historical_id = row.id
    return historical_id


def reuse_wigger_reference(db: Session, case_id: UUID, commit: bool = True) -> dict[str, Any]:
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
    if len({zone.label for zone in zones}) != len(zones):
        raise HTTPException(status_code=409, detail="Duplicate reference hypotheses require review; no records were imported")
    for label in ("Site B", "Site C", "Site D"):
        if sum(site.label == label for site in sites) > 1:
            raise HTTPException(status_code=409, detail="Duplicate reference field sites require review; no records were imported")
    source = "frozen-wigger-reference-v1"
    original_demo = db.get(CaseModel, case_id).reference_key == DEMO_KEY
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
        if commit:
            db.commit()
        else:
            db.flush()
    except Exception:
        db.rollback()
        raise
    return {"case_id": str(case_id), "reference_key": source,
            "limitations": "Frozen topology demonstration only; recorded evidence remains user-entered. Detection network MATCHED status is reused only for the frozen Site A observation coordinates and reach."}
