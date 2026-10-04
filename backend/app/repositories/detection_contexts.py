"""Persistent detection identity and request-local scientific data scope."""
from contextlib import contextmanager
from uuid import UUID, uuid5, NAMESPACE_URL
from dataclasses import replace

from fastapi import HTTPException
from sqlalchemy import select, or_
from app.db.models import CaseModel, DetectionContextModel, TargetSpeciesModel


def ensure_primary(db, case):
    existing = db.scalar(select(DetectionContextModel).where(
        DetectionContextModel.case_id == case.id, DetectionContextModel.is_primary.is_(True)))
    if existing:
        return existing
    species = db.scalar(select(TargetSpeciesModel).where(TargetSpeciesModel.case_id == case.id,
                                                        TargetSpeciesModel.taxon == case.target_taxon))
    if species is None:
        species = TargetSpeciesModel(id=uuid5(NAMESPACE_URL, f"freshwater-species:{case.id}"),
                                     case_id=case.id, taxon=case.target_taxon)
        db.add(species)
        db.flush()
    context = DetectionContextModel(id=uuid5(NAMESPACE_URL, f"freshwater-primary:{case.id}"),
        case_id=case.id, species_id=species.id, site_id=case.detection_site_id,
        sampled_on=case.observation_date, event_label="Legacy primary observation", is_primary=True)
    db.add(context)
    db.flush()
    return context


def selected_context(db, case_id):
    identifier = db.info.get("detection_context_id")
    if identifier:
        context = db.get(DetectionContextModel, identifier)
        if context is None or context.case_id != case_id:
            raise HTTPException(404, detail={"type":"NotFoundError", "message":"Detection context is unavailable in this investigation"})
        return context
    return db.scalar(select(DetectionContextModel).where(
        DetectionContextModel.case_id == case_id, DetectionContextModel.is_primary.is_(True)))


def context_id(db, case_id):
    context = selected_context(db, case_id)
    return context.id if context else None


def scope_clause(db, model, case_id):
    context = selected_context(db, case_id)
    if context is None:
        return model.detection_context_id.is_(None)
    # Null is accepted only for legacy primary rows, never for additional contexts.
    return or_(model.detection_context_id == context.id, model.detection_context_id.is_(None)) if context.is_primary else model.detection_context_id == context.id


def belongs(db, row, case_id, physical_site=False):
    if row is None or row.case_id != case_id:
        return False
    context = selected_context(db, case_id)
    if physical_site and row.detection_context_id is None:
        return True
    return row.detection_context_id == (context.id if context else None) or (
        context is not None and context.is_primary and row.detection_context_id is None)


def contextual_case(db, case):
    context = selected_context(db, case.id)
    if context is None or context.is_primary:
        return case
    species = db.get(TargetSpeciesModel, context.species_id)
    metadata = {key:value for key,value in case.metadata.items()
                if key not in ("historical_observation", "demo_key", "network_representation")}
    return replace(case, target_taxon=species.taxon, observation_date=context.sampled_on,
                   detection_site_id=context.site_id, metadata=metadata)


@contextmanager
def detection_scope(db, identifier):
    previous = db.info.get("detection_context_id")
    db.info["detection_context_id"] = identifier
    try:
        yield
    finally:
        if previous is None: db.info.pop("detection_context_id", None)
        else: db.info["detection_context_id"] = previous
