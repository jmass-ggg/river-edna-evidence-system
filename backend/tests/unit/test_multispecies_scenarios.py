
import pytest
from datetime import date
from sqlalchemy import select, func

from app.api.routes.demo import load_wigger_demo
from app.api.routes.detection_contexts import (
    register_species, register_detection_context, record_observation,
    register_detection_site
)
from app.schemas.detection_contexts import (
    SpeciesCreate, DetectionContextCreate, DetectionSiteCreate, ObservationCreate
)
from app.repositories.detection_contexts import detection_scope
from app.repositories.evidence import EvidenceRepository
from app.repositories.cases import CaseRepository
from app.repositories.sampling import SamplingRepository
from app.db.models import TargetSpeciesModel, DetectionContextModel, ReplicateObservationModel


def test_scenario_a_brown_trout_new_location(db_session):
    """Test A: Salmo trutta at 47.23836/7.96164 -> reach 20448315, date 2026-10-01."""
    demo = load_wigger_demo(db_session)

    site = register_detection_site(
        demo.case_id,
        DetectionSiteCreate(label="Brown Trout Site", latitude=47.23836, longitude=7.96164,
                            hyriv_id=20448315, confirmed=True),
        db_session
    )
    assert site.validation_status.value == "MATCHED"
    assert site.hyriv_id == 20448315

    species = register_species(demo.case_id, SpeciesCreate(taxon="Salmo trutta"), db_session)
    assert species["taxon"] == "Salmo trutta"

    ctx = register_detection_context(
        demo.case_id,
        DetectionContextCreate(species_id=species["id"], site_id=site.id, sampled_on=date(2026, 10, 1)),
        db_session
    )
    assert ctx["target_taxon"] == "Salmo trutta"
    assert str(ctx["sampled_on"]) == "2026-10-01"
    assert ctx["site_label"] == "Brown Trout Site"
    assert ctx["id"] is not None

    obs = record_observation(
        demo.case_id, ctx["id"],
        ObservationCreate(source="Synthetic Test A",
                          replicate_results=["Positive", "Negative", "Negative"],
                          provenance={"synthetic": True}),
        db_session
    )
    assert obs["replicate_results"] == ["Positive", "Negative", "Negative"]

    # Context isolation: scoped query only returns this context's evidence
    with detection_scope(db_session, ctx["id"]):
        evidence = EvidenceRepository(db_session).get_evidence_by_case(demo.case_id)
        assert len(evidence) == 1
        assert evidence[0].value["replicate_results"] == ["Positive", "Negative", "Negative"]
        scoped_case = CaseRepository(db_session).get_case_by_id(demo.case_id)
        assert scoped_case.target_taxon == "Salmo trutta"
        assert str(scoped_case.observation_date) == "2026-10-01"
        assert scoped_case.detection_site_id == site.id

    # Primary context still intact
    primary_case = CaseRepository(db_session).get_case_by_id(demo.case_id)
    assert primary_case.target_taxon == "Fredericella sultana"


def test_scenario_b_rainbow_trout_new_location(db_session):
    """Test B: Oncorhynchus mykiss at 47.13750/7.95833 -> reach 20451169, date 2026-09-21."""
    demo = load_wigger_demo(db_session)

    site = register_detection_site(
        demo.case_id,
        DetectionSiteCreate(label="Rainbow Trout Site", latitude=47.13750, longitude=7.95833,
                            hyriv_id=20451169, confirmed=True),
        db_session
    )
    assert site.validation_status.value == "MATCHED"
    assert site.hyriv_id == 20451169

    species = register_species(demo.case_id, SpeciesCreate(taxon="Oncorhynchus mykiss"), db_session)

    ctx = register_detection_context(
        demo.case_id,
        DetectionContextCreate(species_id=species["id"], site_id=site.id, sampled_on=date(2026, 9, 21)),
        db_session
    )
    assert ctx["target_taxon"] == "Oncorhynchus mykiss"
    assert str(ctx["sampled_on"]) == "2026-09-21"
    assert ctx["id"] is not None

    obs = record_observation(
        demo.case_id, ctx["id"],
        ObservationCreate(source="Synthetic Test B",
                          replicate_results=["Negative", "Positive", "Positive"],
                          provenance={"synthetic": True}),
        db_session
    )
    assert obs["replicate_results"] == ["Negative", "Positive", "Positive"]

    with detection_scope(db_session, ctx["id"]):
        evidence = EvidenceRepository(db_session).get_evidence_by_case(demo.case_id)
        assert len(evidence) == 1
        assert evidence[0].value["replicate_results"] == ["Negative", "Positive", "Positive"]
        scoped_case = CaseRepository(db_session).get_case_by_id(demo.case_id)
        assert scoped_case.target_taxon == "Oncorhynchus mykiss"
        assert str(scoped_case.observation_date) == "2026-09-21"
        assert scoped_case.detection_site_id == site.id


def test_scenario_c_wigger_regression_fredericella(db_session):
    """Test C: Fredericella sultana at canonical Site A, date 2014-06-25, original Wigger reference."""
    demo = load_wigger_demo(db_session)
    assert demo.target_taxon == "Fredericella sultana"
    assert str(demo.observation_date) == "2014-06-25"
    assert demo.sites_created == 4  # A + B + C + D
    assert demo.zones_created == 3  # Z1 + Z2 + Z3

    from app.api.routes.sampling import get_sampling_service, generate_sampling_candidates
    generated = generate_sampling_candidates(
        case_id=demo.case_id, db=db_session,
        sampling_service=get_sampling_service(db_session)
    )
    assert generated.decision_status.value == "TIE"
    # Verify pair-separation score == 2 for each representative site B/C/D
    for candidate in generated.candidates:
        if candidate.pair_separation_score is not None:
            assert candidate.pair_separation_score == 2, (
                f"reach {candidate.hyriv_id} pair_separation_score={candidate.pair_separation_score}, expected 2"
            )


def test_multi_context_three_detections_one_investigation(db_session):
    """Create parent investigation with: Salmo trutta@SiteD, Oncorhynchus@SiteC, Salmo trutta second event."""
    demo = load_wigger_demo(db_session)

    # Salmo trutta at Site D equivalent (reach 20448315)
    site_d = register_detection_site(
        demo.case_id,
        DetectionSiteCreate(label="Site D", latitude=47.23836, longitude=7.96164,
                            hyriv_id=20448315, confirmed=True),
        db_session
    )
    # Oncorhynchus at Site C (reach 20451169)
    site_c = register_detection_site(
        demo.case_id,
        DetectionSiteCreate(label="Site C", latitude=47.13750, longitude=7.95833,
                            hyriv_id=20451169, confirmed=True),
        db_session
    )

    sp_trutta = register_species(demo.case_id, SpeciesCreate(taxon="Salmo trutta"), db_session)
    sp_mykiss = register_species(demo.case_id, SpeciesCreate(taxon="Oncorhynchus mykiss"), db_session)

    ctx1 = register_detection_context(
        demo.case_id,
        DetectionContextCreate(species_id=sp_trutta["id"], site_id=site_d.id,
                               sampled_on=date(2026, 10, 1), event_label="Event 1"),
        db_session
    )
    ctx2 = register_detection_context(
        demo.case_id,
        DetectionContextCreate(species_id=sp_mykiss["id"], site_id=site_c.id,
                               sampled_on=date(2026, 9, 21), event_label="Event 2"),
        db_session
    )
    ctx3 = register_detection_context(
        demo.case_id,
        DetectionContextCreate(species_id=sp_trutta["id"], site_id=site_d.id,
                               sampled_on=date(2026, 8, 15), event_label="Event 3"),
        db_session
    )

    # All three contexts created with distinct IDs
    assert ctx1["id"] != ctx2["id"] != ctx3["id"]
    assert ctx1["target_taxon"] == "Salmo trutta"
    assert ctx2["target_taxon"] == "Oncorhynchus mykiss"
    assert ctx3["target_taxon"] == "Salmo trutta"
    # Different dates for trout events
    assert str(ctx1["sampled_on"]) == "2026-10-01"
    assert str(ctx3["sampled_on"]) == "2026-08-15"

    # Add observations to each
    obs1 = record_observation(demo.case_id, ctx1["id"],
        ObservationCreate(source="Syn1", replicate_results=["Positive", "Negative", "Negative"], provenance={"s": 1}), db_session)
    obs2 = record_observation(demo.case_id, ctx2["id"],
        ObservationCreate(source="Syn2", replicate_results=["Negative", "Positive", "Positive"], provenance={"s": 2}), db_session)
    obs3 = record_observation(demo.case_id, ctx3["id"],
        ObservationCreate(source="Syn3", replicate_results=["Positive", "Positive", "Negative"], provenance={"s": 3}), db_session)

    # Context isolation: each context sees only its own evidence
    for ctx, expected_results in [(ctx1, ["Positive", "Negative", "Negative"]),
                                   (ctx2, ["Negative", "Positive", "Positive"]),
                                   (ctx3, ["Positive", "Positive", "Negative"])]:
        with detection_scope(db_session, ctx["id"]):
            evidence = EvidenceRepository(db_session).get_evidence_by_case(demo.case_id)
            assert len(evidence) == 1, f"Context {ctx['id']} leaked: got {len(evidence)} items"
            assert evidence[0].value["replicate_results"] == expected_results

    # Site reuse: both Salmo trutta contexts use the same physical site_d without duplication
    sites = SamplingRepository(db_session).get_sites_by_case(demo.case_id)
    site_d_detectors = [s for s in sites if s.hyriv_id == 20448315 and s.label == "Site D"
                        and s.site_type.value == "DETECTION_SITE"]
    assert [site.id for site in site_d_detectors] == [site_d.id]
    assert any(s.hyriv_id == 20448315 and s.label == "Site D"
               and s.site_type.value != "DETECTION_SITE" for s in sites)

    # DB counts
    total_contexts = db_session.scalar(
        select(func.count()).select_from(DetectionContextModel).where(
            DetectionContextModel.case_id == demo.case_id,
            DetectionContextModel.is_primary.is_(False)
        )
    )
    assert total_contexts == 3

    total_replicates = db_session.scalar(
        select(func.count()).select_from(ReplicateObservationModel).where(
            ReplicateObservationModel.case_id == demo.case_id
        )
    )
    # 3 replicate observations per context = 9 new, plus primary demo evidence
    assert total_replicates >= 9


def test_geographic_validation_negative_cases():
    """Geographic validation boundary checks: unsupported, wrong reach, ambiguous."""
    from app.services.location_matching import LocationMatchingService
    from fastapi import HTTPException
    svc = LocationMatchingService()

    # Out-of-network coordinates
    result = svc.match(0.0, 0.0)
    assert result["status"] == "UNSUPPORTED"
    assert result["alternatives"] == []
    try:
        svc.confirm(0.0, 0.0, 20446064, True)
        assert False, "Should have raised"
    except HTTPException as e:
        assert e.status_code == 422

    # Wrong reach ID for known-good coordinates (Test A coords with Site A reach)
    try:
        svc.confirm(47.23836, 7.96164, 20446064, True)
        assert False, "Should have raised for wrong reach"
    except HTTPException as e:
        assert e.status_code == 422

    # Ambiguous junction: must select one alternative explicitly
    result_amb = svc.match(47.310416676985575, 7.90208334110692)
    assert result_amb["status"] == "AMBIGUOUS"
    assert len(result_amb["alternatives"]) >= 2
    # Confirm without selection flag raises
    try:
        svc.confirm(result_amb["latitude"], result_amb["longitude"],
                    result_amb["alternatives"][0]["hyriv_id"], False)
        assert False, "Unconfirmed ambiguous should raise"
    except HTTPException as e:
        assert e.status_code == 422
    # Confirming with True succeeds
    reviewed = svc.confirm(result_amb["latitude"], result_amb["longitude"],
                           result_amb["alternatives"][0]["hyriv_id"], True)
    assert reviewed["validation_status"] == "MATCHED"


def test_primary_context_unaffected_by_additional_contexts(db_session):
    """Primary Wigger reference must not be altered by adding multispecies contexts."""
    demo = load_wigger_demo(db_session)
    from app.api.routes.sampling import get_sampling_service, evaluate_sampling_decision
    original_decision = evaluate_sampling_decision(demo.case_id, db_session, get_sampling_service(db_session))
    assert original_decision.status == "TIE"

    # Add two unrelated contexts
    site = register_detection_site(
        demo.case_id,
        DetectionSiteCreate(label="Extra", latitude=47.23836, longitude=7.96164,
                            hyriv_id=20448315, confirmed=True),
        db_session
    )
    for taxon, d in [("Salmo trutta", date(2026, 10, 1)), ("Oncorhynchus mykiss", date(2026, 9, 21))]:
        sp = register_species(demo.case_id, SpeciesCreate(taxon=taxon), db_session)
        ctx = register_detection_context(
            demo.case_id,
            DetectionContextCreate(species_id=sp["id"], site_id=site.id, sampled_on=d),
            db_session
        )
        record_observation(demo.case_id, ctx["id"],
            ObservationCreate(source="Syn", replicate_results=["Negative", "Negative"],
                              provenance={"synthetic": True}), db_session)

    # Primary decision unchanged — no context ID means primary scope
    from app.repositories.sampling import SamplingRepository
    primary_decision = SamplingRepository(db_session).get_latest_decision_for_case(demo.case_id)
    assert primary_decision.id == original_decision.id
    assert primary_decision.status == "TIE"

    # Primary taxon unchanged
    primary_case = CaseRepository(db_session).get_case_by_id(demo.case_id)
    assert primary_case.target_taxon == "Fredericella sultana"
    assert str(primary_case.observation_date) == "2014-06-25"
