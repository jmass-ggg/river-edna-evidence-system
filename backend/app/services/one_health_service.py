"""Conservative evidence-linked One Health relevance pathways."""
from uuid import UUID
from datetime import datetime, time

from app.db.models import CaseModel, EvidenceItemModel, SamplingSiteModel
from app.domain.enums import OneHealthClaimStatus
from app.repositories.evidence import EvidenceRepository


FRAMEWORK = [
    "Monitoring Finding",
    "Ecological Relevance",
    "Animal-Health Relevance",
    "Community / Management Relevance",
    "Possible Monitoring Action",
]

FS_TB_SOURCES = [
    {
        "authors": ["D. J. Morris", "A. Adams"],
        "year": 2007,
        "title": (
            "Sacculogenesis and sporogony of Tetracapsuloides bryosalmonae "
            "within the bryozoan host Fredericella sultana"
        ),
        "journal": "Parasitology Research",
        "doi": "10.1007/s00436-006-0371-0",
        "pmid": "17205353",
        "supports": "F. sultana is a freshwater bryozoan host of T. bryosalmonae.",
    },
    {
        "authors": ["A. Sudhagar", "G. Kumar", "M. El-Matbouli"],
        "year": 2020,
        "title": (
            "The Malacosporean Myxozoan Parasite Tetracapsuloides "
            "bryosalmonae: A Threat to Wild Salmonids"
        ),
        "journal": "Pathogens",
        "doi": "10.3390/pathogens9010016",
        "pmid": "31877926",
        "supports": (
            "T. bryosalmonae causes proliferative kidney disease in salmonids; "
            "temperature can affect parasite and disease biology generally."
        ),
    },
]


def _claim(status: OneHealthClaimStatus, statement: str, refs=None) -> dict:
    return {
        "status": status,
        "statement": statement,
        "evidence_references": list(refs or []),
    }


class OneHealthService:
    def __init__(self, db):
        self.db = db
        self.evidence_repository = EvidenceRepository(db)

    def assess(self, case_id: UUID) -> dict | None:
        case = self.db.get(CaseModel, case_id)
        if case is None:
            return None
        pathways = []
        historical = (case.meta or {}).get("historical_observation", {})
        from app.repositories.detection_contexts import selected_context
        detection = selected_context(self.db, case_id)
        verified = (detection is None or detection.is_primary) and self._is_verified_fs_case(case, historical)
        if verified:
            pathways.append(self._fs_tb_pathway(case_id, historical))
        return {
            "case_id": case_id,
            "framework": FRAMEWORK,
            "pathways": pathways,
            "scientific_logic_implemented": True,
            "observation_provenance": "VERIFIED_REFERENCE" if verified else "UNVERIFIED_USER_REPORTED",
            "reference_evidence_id": (case.reference_provenance or {}).get("historical_evidence_id") if verified else None,
            "limitations": [] if verified else [
                "Caller-supplied observations and metadata do not establish Carraro H001 provenance."
            ],
        }

    def _is_verified_fs_case(self, case: CaseModel, historical: dict) -> bool:
        """Require a server-created linkage and revalidate the frozen sources.

        Neither a copied demo identifier nor copied provenance in ``meta`` can
        write the dedicated reference columns or establish this linkage.
        """
        from app.scientific.data_loader import CarraroHistoricalLoader, WiggerPreflightLoader
        from config import config

        provenance = case.reference_provenance or {}
        if case.reference_key != "wigger-carraro-h001-v1" or provenance.get("loader") != case.reference_key:
            return False
        try:
            loader = CarraroHistoricalLoader(config.CARRARO_DATA_DIR)
            hashes = loader.validate_frozen_reference()
            reference = loader.load_h001()
            network = WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR)
            if (provenance.get("historical_artifact_sha256") != hashes
                    or provenance.get("artifact_sha256") != network.validate_frozen_reference()):
                return False
            evidence = self.db.get(EvidenceItemModel, UUID(provenance["historical_evidence_id"]))
            detection = self.db.get(SamplingSiteModel, case.detection_site_id)
            expected_metadata = {**reference, "date": reference["date"].isoformat()}
            expected_value = {key: expected_metadata[key] for key in (
                "station", "species_code", "species", "observation_index", "concentration_mol_l", "state", "date")}
            site_a = network.load_site_a()
            return bool(
                case.target_taxon == reference["species"] and case.observation_date == reference["date"]
                and historical == expected_metadata
                and detection is not None and detection.case_id == case.id
                and detection.latitude == site_a["transformed_coordinate"]["latitude"]
                and detection.longitude == site_a["transformed_coordinate"]["longitude"]
                and detection.hyriv_id == site_a["network_representation"]["hyriv_id"]
                and evidence is not None and evidence.case_id == case.id
                and evidence.evidence_type == "historical_edna_measurement"
                and evidence.source == reference["provenance"]["edna_source"]
                and evidence.quality == "SOURCE_VERIFIED"
                and evidence.observed_at is not None
                and evidence.observed_at == datetime.combine(reference["date"], time.min)
                and evidence.value == expected_value
                and evidence.provenance == {**reference["provenance"],
                    "demo_evidence_key": "carraro-h001-fs-s1-observation-4", "observation_class": "OBSERVED"}
            )
        except (ValueError, OSError, KeyError, TypeError):
            return False

    def _fs_tb_pathway(self, case_id: UUID, historical: dict) -> dict:
        context = []
        for item in self.evidence_repository.get_evidence_by_case(case_id):
            if item.evidence_type == "context_historical_weather":
                context.append(_claim(
                    OneHealthClaimStatus.OBSERVED,
                    "Historical temperature and precipitation are environmental context only; temperature does not diagnose or predict PKD and precipitation does not prove eDNA transport.",
                    [str(item.id)],
                ))
        observation_ref = "case.metadata.historical_observation"
        return {
            "pathway_id": "fredericella_sultana_tb_monitoring_relevance.v1",
            "triggering_evidence": [observation_ref],
            "monitoring_finding": _claim(
                OneHealthClaimStatus.OBSERVED,
                "Fredericella sultana eDNA was detected in Carraro H001 at S1 on 2014-06-25.",
                [observation_ref],
            ),
            "ecological_relevance": _claim(
                OneHealthClaimStatus.SUPPORTED_RELATIONSHIP,
                "Fredericella sultana is a freshwater bryozoan host relevant to Tetracapsuloides bryosalmonae biology.",
                ["doi:10.1007/s00436-006-0371-0"],
            ),
            "animal_health_relevance": _claim(
                OneHealthClaimStatus.SUPPORTED_RELATIONSHIP,
                "Tetracapsuloides bryosalmonae causes proliferative kidney disease in salmonids.",
                ["doi:10.3390/pathogens9010016"],
            ),
            "community_management_relevance": _claim(
                OneHealthClaimStatus.POSSIBLE_RELEVANCE,
                "The host relationship makes the Fs finding potentially relevant to fish-health monitoring; it does not establish local parasite or disease presence.",
                ["doi:10.1007/s00436-006-0371-0", "doi:10.3390/pathogens9010016"],
            ),
            "possible_monitoring_action": _claim(
                OneHealthClaimStatus.POSSIBLE_RELEVANCE,
                "F. sultana evidence establishes potential relevance for targeted parasite/fish-health monitoring.",
            ),
            "parasite_presence": _claim(
                OneHealthClaimStatus.UNKNOWN,
                "Tetracapsuloides bryosalmonae presence has not been established by the Fs observation.",
            ),
            "fish_disease_status": _claim(
                OneHealthClaimStatus.UNKNOWN,
                "Proliferative kidney disease and salmonid infection status have not been established.",
            ),
            "human_health_impact": _claim(
                OneHealthClaimStatus.UNKNOWN,
                "No direct human-health impact is established by this pathway.",
            ),
            "contextual_evidence": context,
            "scientific_sources": FS_TB_SOURCES,
            "assumptions": [
                "The pathway uses the frozen Carraro H001 Fs observation associated with the Wigger demonstration."
            ],
            "limitations": [
                "Fs eDNA does not demonstrate T. bryosalmonae presence.",
                "Fs eDNA does not demonstrate PKD or infection in salmonids.",
                "Temperature context is not a diagnosis, probability, or disease-risk score.",
                "The pathway expresses monitoring relevance rather than a causal health prediction.",
            ],
            "provenance": {
                "pathway_version": "1.0.0",
                "case_id": str(case_id),
                "historical_observation_provenance": historical.get("provenance", {}),
                "source_dois": [source["doi"] for source in FS_TB_SOURCES],
            },
        }
