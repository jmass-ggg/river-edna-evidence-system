"""
SQLAlchemy database models for the eDNA Evidence Investigator system.

These models define the database schema and relationships.
They are separate from domain models to maintain clean architecture.
"""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    String,
    Integer,
    Float,
    Date,
    DateTime,
    ForeignKey,
    Text,
    ARRAY,
    JSON,
    UniqueConstraint,
    ForeignKeyConstraint,
    Index,
    Boolean,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import TypeDecorator
import json
from uuid import UUID as PyUUID

from app.db.base import Base


def uuid_json_serializer(obj):
    """Custom JSON serializer that handles UUID objects."""
    if isinstance(obj, PyUUID):
        return str(obj)
    elif isinstance(obj, list):
        return [uuid_json_serializer(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: uuid_json_serializer(v) for k, v in obj.items()}
    return obj


# Type adapters for cross-database compatibility
class JSONType(TypeDecorator):
    """JSON type that uses JSONB for PostgreSQL and JSON for other databases."""
    impl = JSON
    
    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(JSON())
    
    cache_ok = True


class ArrayType(TypeDecorator):
    """Array type that uses ARRAY for PostgreSQL and JSON for other databases."""
    impl = JSON

    def __init__(self, item_type=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.item_type = item_type
    
    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql' and self.item_type is not None:
            return dialect.type_descriptor(ARRAY(self.item_type))
        else:
            return dialect.type_descriptor(JSON())
    
    def process_bind_param(self, value, dialect):
        """Convert Python list to JSON, handling UUID serialization."""
        if value is None:
            return value
        if dialect.name == 'postgresql' and self.item_type is not None:
            return value
        # Convert UUIDs to strings before JSON serialization.
        return uuid_json_serializer(value)
    
    def process_result_value(self, value, dialect):
        """Convert JSON back to Python list, attempting UUID conversion."""
        if value is None:
            return value
        # Try to convert string UUIDs back to UUID objects
        def deserialize_uuids(obj):
            if isinstance(obj, str):
                # Try to parse as UUID
                try:
                    return PyUUID(obj)
                except (ValueError, AttributeError):
                    return obj
            elif isinstance(obj, list):
                return [deserialize_uuids(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: deserialize_uuids(v) for k, v in obj.items()}
            return obj
        
        return deserialize_uuids(value)
    
    cache_ok = True


class ContextExecutionModel(Base):
    """Provider execution history, separate from scientific evidence."""
    __tablename__ = "context_executions"
    detection_context_id: Mapped[Optional[PyUUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    __table_args__ = (ForeignKeyConstraint(["detection_context_id", "case_id"],
        ["detection_contexts.id", "detection_contexts.case_id"], name="fk_context_executions_detection_context"),)

    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    evidence_id: Mapped[Optional[PyUUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence_items.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(200), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    data: Mapped[Optional[dict]] = mapped_column(JSONType(), nullable=True)
    provenance: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    limitations: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    request: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class CaseModel(Base):
    """
    Database model for eDNA investigation cases.
    
    Represents an investigation of an eDNA detection at a specific site
    for a specific taxon.
    """
    __tablename__ = "cases"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    target_taxon: Mapped[str] = mapped_column(String(200), nullable=False)
    observation_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    detection_site_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sampling_sites.id"),
        nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    # Written only by the trusted reference loader, never from case metadata.
    reference_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
    reference_provenance: Mapped[Optional[dict]] = mapped_column(JSONType(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    meta: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    
    # Relationships
    detection_site: Mapped["SamplingSiteModel"] = relationship(
        "SamplingSiteModel",
        foreign_keys=[detection_site_id],
        back_populates="cases_as_detection"
    )
    sampling_sites: Mapped[list["SamplingSiteModel"]] = relationship(
        "SamplingSiteModel",
        foreign_keys="SamplingSiteModel.case_id",
        back_populates="case",
        cascade="all, delete-orphan"
    )
    candidate_zones: Mapped[list["CandidateZoneModel"]] = relationship(
        "CandidateZoneModel",
        back_populates="case",
        cascade="all, delete-orphan"
    )
    evidence_items: Mapped[list["EvidenceItemModel"]] = relationship(
        "EvidenceItemModel",
        back_populates="case",
        cascade="all, delete-orphan"
    )
    sampling_decisions: Mapped[list["SamplingDecisionModel"]] = relationship(
        "SamplingDecisionModel",
        back_populates="case",
        cascade="all, delete-orphan"
    )
    follow_up_samples: Mapped[list["FollowUpSampleModel"]] = relationship(
        "FollowUpSampleModel", back_populates="case", cascade="all, delete-orphan"
    )
    investigation_runs: Mapped[list["InvestigationRunModel"]] = relationship(
        "InvestigationRunModel", back_populates="case", cascade="all, delete-orphan"
    )


class SamplingSiteModel(Base):
    """
    Database model for sampling sites.
    
    Represents a location proposed for sampling or where detection occurred.
    """
    __tablename__ = "sampling_sites"
    detection_context_id: Mapped[Optional[PyUUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    __table_args__ = (ForeignKeyConstraint(["detection_context_id", "case_id"],
        ["detection_contexts.id", "detection_contexts.case_id"], name="fk_sampling_sites_detection_context"),)

    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    case_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id"),
        nullable=True
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    hyriv_id: Mapped[int] = mapped_column(Integer, nullable=False)
    site_type: Mapped[str] = mapped_column(String(50), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(50), nullable=False)
    network_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    network_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    snap_distance_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    meta: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    
    # Relationships
    case: Mapped[Optional["CaseModel"]] = relationship(
        "CaseModel",
        foreign_keys=[case_id],
        back_populates="sampling_sites"
    )
    cases_as_detection: Mapped[list["CaseModel"]] = relationship(
        "CaseModel",
        foreign_keys="CaseModel.detection_site_id",
        back_populates="detection_site"
    )


class CandidateZoneModel(Base):
    """
    Database model for candidate zones.
    
    Represents a hypothetical source region in the river network.
    """
    __tablename__ = "candidate_zones"
    detection_context_id: Mapped[Optional[PyUUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    __table_args__ = (ForeignKeyConstraint(["detection_context_id", "case_id"],
        ["detection_contexts.id", "detection_contexts.case_id"], name="fk_candidate_zones_detection_context"),)

    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    case_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id"),
        nullable=False
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    root_hyriv_id: Mapped[int] = mapped_column(Integer, nullable=False)
    reach_ids: Mapped[list[int]] = mapped_column(
        ArrayType(Integer()),
        nullable=False
    )
    validation_status: Mapped[str] = mapped_column(String(50), nullable=False)
    meta: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    
    # Relationships
    case: Mapped["CaseModel"] = relationship(
        "CaseModel",
        back_populates="candidate_zones"
    )


class EvidenceItemModel(Base):
    """
    Database model for evidence items.
    
    Represents a piece of data that supports, contradicts, or is neutral
    regarding a hypothesis.
    """
    __tablename__ = "evidence_items"
    detection_context_id: Mapped[Optional[PyUUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    __table_args__ = (ForeignKeyConstraint(["detection_context_id", "case_id"],
        ["detection_contexts.id", "detection_contexts.case_id"], name="fk_evidence_items_detection_context"),)

    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    case_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id"),
        nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    observed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    quality: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    provenance: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    
    # Relationships
    case: Mapped["CaseModel"] = relationship(
        "CaseModel",
        back_populates="evidence_items"
    )


class SamplingDecisionModel(Base):
    """
    Database model for sampling decisions.
    
    Represents a decision about which sampling sites to prioritize.
    """
    __tablename__ = "sampling_decisions"
    detection_context_id: Mapped[Optional[PyUUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    __table_args__ = (ForeignKeyConstraint(["detection_context_id", "case_id"],
        ["detection_contexts.id", "detection_contexts.case_id"], name="fk_sampling_decisions_detection_context"),)

    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    case_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id"),
        nullable=False
    )
    candidate_scope: Mapped[str] = mapped_column(String(50), nullable=False, default="REGISTERED_SITES", server_default="REGISTERED_SITES")
    candidate_snapshot: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    recommended_site_ids: Mapped[list] = mapped_column(
        ArrayType(UUID(as_uuid=True)),
        nullable=False
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    
    # Relationships
    case: Mapped["CaseModel"] = relationship(
        "CaseModel",
        back_populates="sampling_decisions"
    )
    decision_traces: Mapped[list["DecisionTraceModel"]] = relationship(
        "DecisionTraceModel",
        back_populates="decision",
        cascade="all, delete-orphan"
    )


class DecisionTraceModel(Base):
    """
    Database model for decision traces.
    
    Represents an audit trail showing how a decision was made.
    """
    __tablename__ = "decision_traces"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    decision_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sampling_decisions.id"),
        nullable=False
    )
    evidence_used: Mapped[list] = mapped_column(
        ArrayType(UUID(as_uuid=True)),
        nullable=False
    )
    rules_applied: Mapped[list[str]] = mapped_column(
        ArrayType(String()),
        nullable=False
    )
    hydrology_checks: Mapped[list] = mapped_column(
        JSONType(),
        nullable=False
    )
    assumptions: Mapped[list[str]] = mapped_column(
        ArrayType(String()),
        nullable=False
    )
    limitations: Mapped[list[str]] = mapped_column(
        ArrayType(String()),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow
    )
    
    # Relationships
    decision: Mapped["SamplingDecisionModel"] = relationship(
        "SamplingDecisionModel",
        back_populates="decision_traces"
    )


class FollowUpSampleModel(Base):
    """Structured follow-up sample and its linked uninterpreted evidence."""

    __tablename__ = "follow_up_samples"
    detection_context_id: Mapped[Optional[PyUUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    __table_args__ = (ForeignKeyConstraint(["detection_context_id", "case_id"],
        ["detection_contexts.id", "detection_contexts.case_id"], name="fk_follow_up_samples_detection_context"),)


    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False
    )
    sampling_site_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sampling_sites.id"), nullable=True
    )
    candidate_reference: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    hyriv_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sampled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    replicate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    positive_replicates: Mapped[int] = mapped_column(Integer, nullable=False)
    concentration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    concentration_unit: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    assay: Mapped[str] = mapped_column(String(200), nullable=False)
    controls_status: Mapped[str] = mapped_column(String(100), nullable=False)
    collector_source: Mapped[str] = mapped_column(String(200), nullable=False)
    provenance: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("evidence_items.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    case: Mapped["CaseModel"] = relationship("CaseModel", back_populates="follow_up_samples")


class InvestigationRunModel(Base):
    __tablename__ = "investigation_runs"
    detection_context_id: Mapped[Optional[PyUUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    __table_args__ = (ForeignKeyConstraint(["detection_context_id", "case_id"],
        ["detection_contexts.id", "detection_contexts.case_id"], name="fk_investigation_runs_detection_context"),)


    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_evidence_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence_items.id"), nullable=True)
    trigger_follow_up_sample_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("follow_up_samples.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_decision_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("sampling_decisions.id"), nullable=True)
    new_decision_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("sampling_decisions.id"), nullable=True)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hypothesis_snapshot: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    candidate_snapshot: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    decision_snapshot: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    case: Mapped["CaseModel"] = relationship("CaseModel", back_populates="investigation_runs")
    hypothesis_states: Mapped[list["HypothesisStateModel"]] = relationship("HypothesisStateModel", back_populates="run", cascade="all, delete-orphan")
    candidate_snapshots: Mapped[list["GeneratedCandidateSnapshotModel"]] = relationship("GeneratedCandidateSnapshotModel", back_populates="run", cascade="all, delete-orphan")


class HypothesisStateModel(Base):
    __tablename__ = "hypothesis_states"
    detection_context_id: Mapped[Optional[PyUUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    __table_args__ = (ForeignKeyConstraint(["detection_context_id", "case_id"],
        ["detection_contexts.id", "detection_contexts.case_id"], name="fk_hypothesis_states_detection_context"),)


    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    investigation_run_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("investigation_runs.id"), nullable=False)
    case_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    zone_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("candidate_zones.id"), nullable=False)
    zone_label: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    support_count: Mapped[int] = mapped_column(Integer, nullable=False)
    contradict_count: Mapped[int] = mapped_column(Integer, nullable=False)
    neutral_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unknown_count: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_ids: Mapped[list] = mapped_column(ArrayType(), nullable=False)
    rule_ids: Mapped[list[str]] = mapped_column(ArrayType(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    run: Mapped["InvestigationRunModel"] = relationship("InvestigationRunModel", back_populates="hypothesis_states")


class GeneratedCandidateSnapshotModel(Base):
    __tablename__ = "generated_candidate_snapshots"
    detection_context_id: Mapped[Optional[PyUUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    __table_args__ = (ForeignKeyConstraint(["detection_context_id", "case_id"],
        ["detection_contexts.id", "detection_contexts.case_id"], name="fk_generated_candidate_snapshots_detection_context"),)


    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    investigation_run_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("investigation_runs.id"), nullable=False)
    case_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    hyriv_id: Mapped[int] = mapped_column(Integer, nullable=False)
    signature: Mapped[list[int]] = mapped_column(ArrayType(), nullable=False)
    pair_separation_score: Mapped[int] = mapped_column(Integer, nullable=False)
    equivalence_class: Mapped[str] = mapped_column(String(200), nullable=False)
    equivalent_hyriv_ids: Mapped[list[int]] = mapped_column(ArrayType(), nullable=False)
    network_distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    selection_reason: Mapped[str] = mapped_column(Text, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    run: Mapped["InvestigationRunModel"] = relationship("InvestigationRunModel", back_populates="candidate_snapshots")


class TargetSpeciesModel(Base):
    __tablename__ = "target_species"
    __table_args__ = (UniqueConstraint("case_id", "taxon", name="uq_species_case_taxon"),
                     UniqueConstraint("id", "case_id", name="uq_species_id_case"))
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    taxon: Mapped[str] = mapped_column(String(200), nullable=False)


class DetectionContextModel(Base):
    __tablename__ = "detection_contexts"
    __table_args__ = (
        ForeignKeyConstraint(["species_id", "case_id"], ["target_species.id", "target_species.case_id"]),
        UniqueConstraint("id", "case_id", name="uq_detection_context_id_case"),
        UniqueConstraint("case_id", "species_id", "site_id", "sampled_on", "event_label", name="uq_detection_event"),
        Index("uq_primary_detection_context", "case_id", unique=True,
              postgresql_where=text("is_primary = true"),
              sqlite_where=text("is_primary = 1")),
    )
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)
    species_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sampling_sites.id"), nullable=False)
    sampled_on: Mapped[datetime] = mapped_column(Date, nullable=False)
    event_label: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class ReplicateObservationModel(Base):
    __tablename__ = "replicate_observations"
    __table_args__ = (
        ForeignKeyConstraint(["detection_context_id", "case_id"], ["detection_contexts.id", "detection_contexts.case_id"]),
        UniqueConstraint("evidence_id", "replicate_index", name="uq_evidence_replicate"),
    )
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    detection_context_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    evidence_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evidence_items.id"), nullable=False)
    replicate_index: Mapped[int] = mapped_column(Integer, nullable=False)
    result: Mapped[str] = mapped_column(String(20), nullable=False)

class AIReportModel(Base):
    """Append-only AI drafts, separate from deterministic scientific results."""
    __tablename__ = "ai_reports"
    __table_args__ = (
        ForeignKeyConstraint(["detection_context_id", "case_id"],
                             ["detection_contexts.id", "detection_contexts.case_id"]),
        Index("ix_ai_reports_case_context_generated", "case_id", "detection_context_id", "generated_at"),
    )
    id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False)
    detection_context_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    decision_id: Mapped[PyUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sampling_decisions.id"), nullable=False)
    investigation_run_id: Mapped[Optional[PyUUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("investigation_runs.id"), nullable=True)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(150), nullable=False)
    narrative: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    sources: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False, default="VALIDATED")
    review_status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")


from app.db import detection_events  # noqa: E402,F401
