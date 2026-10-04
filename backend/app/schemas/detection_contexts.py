"""Normalized species, sampling events and separate replicate inputs."""
from datetime import date
from uuid import UUID
from typing import Literal
from app.schemas.cases import CaseCreateRequest
from pydantic import BaseModel, ConfigDict, Field, field_validator

class SpeciesCreate(BaseModel):
    taxon: str = Field(min_length=1,max_length=200)
    model_config=ConfigDict(str_strip_whitespace=True)

class LocationMatchRequest(BaseModel):
    latitude: float=Field(ge=-90,le=90)
    longitude: float=Field(ge=-180,le=180)
    model_config=ConfigDict(allow_inf_nan=False)

class DetectionSiteCreate(LocationMatchRequest):
    label: str=Field(min_length=1,max_length=100)
    hyriv_id: int=Field(gt=0)
    confirmed: bool=False
    model_config=ConfigDict(str_strip_whitespace=True,allow_inf_nan=False)

class DetectionContextCreate(BaseModel):
    species_id: UUID
    site_id: UUID
    sampled_on: date
    event_label: str=Field(default='',max_length=200)
    model_config=ConfigDict(str_strip_whitespace=True)
    @field_validator('sampled_on')
    @classmethod
    def not_future(cls,value):
        if value>date.today():raise ValueError('Sampling date cannot be in the future')
        return value

class ObservationCreate(BaseModel):
    replicate_results: list[Literal['Positive','Negative','Invalid']]=Field(min_length=1)
    source: str=Field(min_length=1,max_length=200)
    assay_metadata: dict | str | None=None
    provenance: dict=Field(min_length=1)
    model_config=ConfigDict(str_strip_whitespace=True)


class AdditionalDetectionCreate(BaseModel):
    taxon: str=Field(min_length=1,max_length=200)
    sampled_on: date
    event_label: str=Field(default='',max_length=200)
    detection_site: DetectionSiteCreate | None=None
    reuse_site_index: int=Field(default=0,ge=0)
    observation: ObservationCreate | None=None
    model_config=ConfigDict(str_strip_whitespace=True)
    @field_validator('sampled_on')
    @classmethod
    def not_future(cls,value):
        if value>date.today():raise ValueError('Sampling date cannot be in the future')
        return value

class MultiDetectionInvestigationCreate(BaseModel):
    primary: CaseCreateRequest
    additional_contexts: list[AdditionalDetectionCreate]=Field(default_factory=list)
