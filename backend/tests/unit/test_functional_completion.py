"""Functional boundary, reproducibility and provider-history regressions."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import json
import os
import subprocess
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from tests.unit.test_case_creation_integration import _post_json
from sqlalchemy import func, select

from app.api.dependencies import get_hydrology_engine
from app.api.routes.demo import load_wigger_demo
from app.api.routes.sampling import get_sampling_service, evaluate_sampling_decision, persist_sampling_candidates
from app.context.interfaces import ProviderResult
from app.context.service import ContextCollectionService
from app.db.models import ContextExecutionModel, EvidenceItemModel, FollowUpSampleModel, InvestigationRunModel, SamplingDecisionModel
from app.db.session import get_db
from app.domain.enums import ContextProviderStatus
from app.main import app
from app.repositories.cases import CaseRepository
from app.repositories.evidence import EvidenceRepository
from app.repositories.follow_up_samples import FollowUpSampleRepository
from app.services.evidence_service import EvidenceService
from app.services.follow_up_sample_service import FollowUpSampleService
from app.services.investigation_service import InvestigationService
from app.services.scientific_results import canonical_scientific_result
from tests.unit.test_context_infrastructure import _request
from tests.unit.test_investigation_runs import _service
from tests.unit.test_wigger_workflow_repairs import create


def sample_payload(site_id=None, candidate_reference=None, reach=20446064):
    return dict(sampling_site_id=site_id,candidate_reference=candidate_reference,hyriv_id=reach,
        sampled_at=datetime(2024,1,1),replicate_count=3,positive_replicates=1,
        assay="Synthetic regression assay",controls_status="PASS",collector_source="test team",
        provenance={"synthetic":True})


@pytest.mark.parametrize("mode,status", [("unpersisted",404),("cross_case",404),("mismatch",409),("malformed",400)])
def test_candidate_reference_boundary(db_session,mode,status):
    demo=load_wigger_demo(db_session)
    sampling=get_sampling_service(db_session)
    service=FollowUpSampleService(FollowUpSampleRepository(db_session),sampling.hydrology_engine)
    if mode=="unpersisted":
        reference="HYRIV_ID:20450127"
    elif mode=="malformed":
        reference="candidate-without-identity"
    else:
        candidates=persist_sampling_candidates(demo.case_id,db_session,sampling)
        reference=str(candidates.candidates[0].site_id)
    case_id=create(db_session).id if mode=="cross_case" else demo.case_id
    with pytest.raises(HTTPException) as error:
        service.create(case_id,**sample_payload(candidate_reference=reference,reach=20446064))
    assert error.value.status_code==status
    assert db_session.scalar(select(func.count()).select_from(FollowUpSampleModel))==0


def test_candidate_reference_resolves_persisted_case_representative(db_session):
    demo=load_wigger_demo(db_session)
    sampling=get_sampling_service(db_session)
    candidates=persist_sampling_candidates(demo.case_id,db_session,sampling)
    candidate=candidates.candidates[0]
    service=FollowUpSampleService(FollowUpSampleRepository(db_session),sampling.hydrology_engine)
    sample=service.create(demo.case_id,**sample_payload(candidate_reference=f"HYRIV_ID:{candidate.hyriv_id}",reach=candidate.hyriv_id))
    assert sample.candidate_reference==str(candidate.site_id)
    evidence=db_session.get(EvidenceItemModel,sample.evidence_id)
    assert evidence.value["candidate_reference"]==sample.candidate_reference
    from app.scientific.evidence.engine import EvidenceCompatibilityEngineImpl
    from app.repositories.sampling import SamplingRepository
    zone=SamplingRepository(db_session).get_zones_by_case(demo.case_id)[0]
    item=next(item for item in EvidenceRepository(db_session).get_evidence_by_case(demo.case_id) if item.id==sample.evidence_id)
    assessment=EvidenceCompatibilityEngineImpl().assess_evidence_for_zone(CaseRepository(db_session).get_case_by_id(demo.case_id),zone,[item],[])[0]
    assert assessment.compatibility.value=="UNKNOWN" and assessment.strength.value=="UNASSESSED"


def test_follow_up_evidence_failure_rolls_back_sample(db_session,monkeypatch):
    demo=load_wigger_demo(db_session)
    service=FollowUpSampleService(FollowUpSampleRepository(db_session),get_sampling_service(db_session).hydrology_engine)
    original=db_session.flush
    def fail_on_evidence(*args,**kwargs):
        if any(isinstance(row,EvidenceItemModel) and row.evidence_type=="follow_up_edna_sample" for row in db_session.new):
            raise RuntimeError("evidence storage failure")
        return original(*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(db_session,"flush",fail_on_evidence)
        with pytest.raises(RuntimeError):service.create(demo.case_id,**sample_payload(site_id=demo.detection_site_id))
    assert db_session.scalar(select(func.count()).select_from(FollowUpSampleModel))==0
    assert not any(item.evidence_type=="follow_up_edna_sample" for item in EvidenceRepository(db_session).get_evidence_by_case(demo.case_id))


@pytest.mark.parametrize("kind",["context_gbif_occurrence","sampling_field_plan","directed_hydrological_connectivity","arbitrary"])
def test_non_observations_cannot_unlock_assessment_or_decisions(db_session,kind):
    case=create(db_session,initial_evidence=[])
    EvidenceRepository(db_session).add_evidence(case.id,kind,"test",{"replicate_results":["Positive"]},provenance={"entry_method":"manual"})
    with pytest.raises(HTTPException) as error:InvestigationService.require_decision_prerequisites(db_session,case)
    assert error.value.status_code==422
    from app.api.routes.evidence import assess_evidence,get_evidence_service
    with pytest.raises(HTTPException) as error:assess_evidence(case.id,db_session,get_evidence_service(db_session))
    assert error.value.status_code==422


@pytest.mark.parametrize("change",[{"provenance":{}},{"value":{"replicate_results":["Invalid"]}},{"value":{"replicate_results":["invented"]}}])
def test_observation_prerequisites_require_results_and_provenance(change):
    item=SimpleNamespace(source="test",provenance={"source":"test"},evidence_type="edna_observation",value={"replicate_results":["Positive"]})
    for key,value in change.items():setattr(item,key,value)
    assert not EvidenceService.qualifying_observation(item)


def test_follow_up_api_status_codes_and_server_rollback(db_session,monkeypatch):
    demo=load_wigger_demo(db_session)
    app.dependency_overrides[get_db]=lambda:db_session
    app.dependency_overrides[get_hydrology_engine]=lambda:get_sampling_service(db_session).hydrology_engine
    try:
        payload=sample_payload(site_id=demo.detection_site_id)
        payload["sampled_at"]=payload["sampled_at"].isoformat()
        payload["sampling_site_id"]=str(payload["sampling_site_id"])
        base=f"/cases/{demo.case_id}/follow-up-samples"
        assert _post_json(base,{**payload,"candidate_reference":"HYRIV_ID:20450127"})[0]==422
        assert _post_json(base,{**payload,"provenance":{}})[0]==422
        assert _post_json(base,{**payload,"sampling_site_id":str(uuid4())})[0]==404
        assert _post_json(base,{**payload,"hyriv_id":20450127})[0]==409
        assert _post_json(f"/cases/{uuid4()}/evidence-assessment",{},method="GET")[0]==404
        with monkeypatch.context() as patch:
            patch.setattr(FollowUpSampleRepository,"add",lambda *a,**kw:(_ for _ in ()).throw(RuntimeError("injected server failure")))
            status,body=_post_json(base,payload)
            assert status==500 and body["error"]["type"]=="RuntimeError"
        assert _post_json(base,payload)[0]==201
    finally:app.dependency_overrides.clear()


def test_equivalent_reinvestigations_keep_canonical_results_and_real_audit_ids(db_session):
    demo=load_wigger_demo(db_session)
    service=_service(db_session)
    first=service.reinvestigate(demo.case_id)
    second=service.reinvestigate(demo.case_id)
    assert first["scientific_result"]==second["scientific_result"]
    assert first["scientific_result"]["rules"][0]["id"]
    assert first["investigation_run_id"]!=second["investigation_run_id"]
    assert first["new_decision_id"]!=second["new_decision_id"]
    assert first["started_at"]!=second["started_at"]
    assert second["change_comparison_status"]=="AVAILABLE" and not second["changed"]["overall"]
    changed=deepcopy(first["scientific_result"])
    changed["candidate_generation"]["candidates"][0]["pair_separation_score"]+=1
    assert canonical_scientific_result(changed)!=canonical_scientific_result(first["scientific_result"])
    run=db_session.get(InvestigationRunModel,first["investigation_run_id"])
    run.candidate_snapshot={}
    db_session.commit()
    assert service.detail(demo.case_id,second["investigation_run_id"])["change_comparison_status"]=="UNAVAILABLE_HISTORY"


def test_field_choice_preserves_decision_and_is_not_observation(db_session):
    demo=load_wigger_demo(db_session)
    decision=evaluate_sampling_decision(demo.case_id,db_session,get_sampling_service(db_session))
    from app.api.routes.evidence import get_evidence_service
    service=get_evidence_service(db_session)
    before=deepcopy(decision.candidate_snapshot)
    note=service.add_evidence(demo.case_id,"sampling_field_plan","test researcher",{
        "decision_id":str(decision.id),"site_id":str(decision.recommended_site_ids[0]),
        "researcher_selected":True,"accessibility":"Synthetic access note","pair_separation_score":999,
    },provenance={"synthetic":True})
    assert not EvidenceService.qualifying_observation(note)
    assert "pair_separation_score" not in note.value
    persisted=db_session.get(SamplingDecisionModel,decision.id)
    assert persisted.status=="TIE" and persisted.candidate_snapshot==before
    other=create(db_session)
    with pytest.raises(HTTPException) as error:service.add_evidence(other.id,"sampling_field_plan","test",note.value,provenance={"synthetic":True})
    assert error.value.status_code==404


@pytest.mark.parametrize("status,data,error",[("SUCCESS",{},None),("PARTIAL",{"count":1},"truncated"),("UNAVAILABLE",None,"unsupported"),("ERROR",None,"offline")])
def test_context_execution_status_survives_without_fabricated_evidence(db_session,status,data,error):
    demo=load_wigger_demo(db_session)
    provider=Mock(name="fixture provider");provider.name="fixture"
    provider.collect.return_value=ProviderResult(provider="fixture",evidence_type="context_gbif_occurrence",status=ContextProviderStatus(status),data=data,error=error,limitations=["Synthetic provider result"])
    service=ContextCollectionService(EvidenceRepository(db_session),[provider])
    outcomes=service.collect(demo.case_id,_request())
    stored=service.get_context(demo.case_id)
    assert stored[0]["status"].value==status and stored[0]["error"]==error
    assert stored[0]["execution_id"]==outcomes[0]["execution_id"]
    assert stored[0]["evidence_id"] is None if status!="PARTIAL" else stored[0]["evidence_id"] is not None
    assert stored[0]["compatibility"].value=="UNKNOWN" and stored[0]["strength"].value=="UNASSESSED"


@pytest.mark.parametrize("failure,status",[(NotImplementedError("not configured"),"UNAVAILABLE"),(TimeoutError("provider timeout"),"ERROR")])
def test_context_exceptions_remain_retrievable(db_session,failure,status):
    demo=load_wigger_demo(db_session)
    provider=Mock();provider.name="fixture";provider.collect.side_effect=failure
    service=ContextCollectionService(EvidenceRepository(db_session),[provider])
    service.collect(demo.case_id,_request())
    stored=service.get_context(demo.case_id)
    assert stored[0]["status"].value==status and stored[0]["error"]==str(failure)
    assert stored[0]["evidence_id"] is None


def test_fresh_http_reproductions_have_equal_science_and_different_audit(tmp_path):
    root=Path(__file__).resolve().parents[3]
    env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1","HYPOTHESIS_STORAGE_DIRECTORY":str(tmp_path/"hypotheses")}
    for name in ("first","second"):
        subprocess.run([str(root/"venv/bin/python"),"-B",str(root/"scripts/reproduce_wigger.py"),"--isolated","--output-dir",str(tmp_path/name)],cwd=root,env=env,check=True,capture_output=True,text=True)
    read=lambda name,file:json.loads((tmp_path/name/file).read_text())
    assert read("first","wigger_scientific_result.json")==read("second","wigger_scientific_result.json")
    assert read("first","wigger_audit.json")["case"]["id"]!=read("second","wigger_audit.json")["case"]["id"]
    assert read("first","wigger_audit.json")["one_health"]["pathways"][0]["provenance"]["case_id"]==read("first","wigger_audit.json")["case"]["id"]
