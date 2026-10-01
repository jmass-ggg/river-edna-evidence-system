"""Conservative evidence-linked One Health relevance pathways."""
from uuid import UUID

from app.db.models import CaseModel
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
        if self._is_verified_fs_case(case, historical):
            pathways.append(self._fs_tb_pathway(case_id, historical))
        return {
            "case_id": case_id,
            "framework": FRAMEWORK,
            "pathways": pathways,
            "scientific_logic_implemented": True,
        }

    @staticmethod
    def _is_verified_fs_case(case: CaseModel, historical: dict) -> bool:
        return (
            case.target_taxon == "Fredericella sultana"
            and historical.get("species") == "Fredericella sultana"
            and historical.get("station") == "S1"
            and historical.get("date") == "2014-06-25"
            and historical.get("state") == "DETECTED"
        )

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
