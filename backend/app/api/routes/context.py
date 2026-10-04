from app.api.detection_scope import bind_detection_context
"""Case-scoped collection of uninterpreted environmental context."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.context.interfaces import ContextRequest, UnavailableSpatialClient
from app.context.providers.gbif import GbifOccurrenceProvider, UrllibJsonClient
from app.context.providers.urbanization import UrbanizationProvider
from app.context.providers.weather import HistoricalWeatherProvider, OpenMeteoHistoricalClient
from app.context.service import ContextCollectionService
from app.db.models import CaseModel, SamplingSiteModel
from app.db.session import get_db
from app.repositories.evidence import EvidenceRepository
from app.services.case_service import CaseService
from app.repositories.cases import CaseRepository
from app.schemas.context import ContextCollectRequest, ContextProviderResponse


router = APIRouter(prefix="/cases", tags=["context"], dependencies=[Depends(bind_detection_context)])


def get_context_service(db: Session = Depends(get_db)) -> ContextCollectionService:
    return ContextCollectionService(
        EvidenceRepository(db),
        [
            GbifOccurrenceProvider(UrllibJsonClient()),
            UrbanizationProvider(UnavailableSpatialClient(
                "GHSL historical built-up raster and reproducible buffer extraction"
            )),
            HistoricalWeatherProvider(OpenMeteoHistoricalClient(UrllibJsonClient())),
        ],
    )


def _case_and_coordinates(db: Session, case_id: UUID, request: ContextCollectRequest):
    case = CaseService(CaseRepository(db)).get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    site = db.get(SamplingSiteModel, case.detection_site_id)
    latitude = request.latitude if request.latitude is not None else site.latitude
    longitude = request.longitude if request.longitude is not None else site.longitude
    return case, latitude, longitude


@router.post(
    "/{case_id}/context/collect",
    response_model=list[ContextProviderResponse],
    status_code=status.HTTP_200_OK,
)
def collect_context(
    case_id: UUID,
    request: ContextCollectRequest,
    db: Session = Depends(get_db),
    service: ContextCollectionService = Depends(get_context_service),
) -> list[ContextProviderResponse]:
    case, latitude, longitude = _case_and_coordinates(db, case_id, request)
    context_request = ContextRequest(
        query=request.query or case.target_taxon,
        latitude=latitude,
        longitude=longitude,
        observation_date=case.observation_date,
        radius_m=request.radius_m,
        weather_window_days=request.weather_window_days,
        urban_buffer_m=request.urban_buffer_m,
    )
    return [ContextProviderResponse.model_validate(item) for item in service.collect(case_id, context_request)]


@router.get(
    "/{case_id}/context",
    response_model=list[ContextProviderResponse],
    status_code=status.HTTP_200_OK,
)
def get_context(
    case_id: UUID,
    db: Session = Depends(get_db),
    service: ContextCollectionService = Depends(get_context_service),
) -> list[ContextProviderResponse]:
    if db.get(CaseModel, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return [ContextProviderResponse.model_validate(item) for item in service.get_context(case_id)]
