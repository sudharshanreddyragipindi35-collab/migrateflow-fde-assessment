import time
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.agent.jobs import claim, enqueue, execute
from app.cleaning.service import clean_record
from app.config import get_settings
from app.db.database import SessionLocal
from app.db.tables import PipelineJobRow
from app.integration.service import payload_hash
from app.main import app
from app.mapping.engine import ModelMapping, propose_mappings
from app.mapping.schema import load_target_schema
from app.ingestion.profiler import profile_frame
import pandas as pd

HEADER = "employee_id,first_name,last_name,email,hire_date,department,employment_status\n"
GOOD = "E100,Ada,Lovelace,ada@example.com,2024-01-15,Engineering,Active\n"


def upload(client, rows=GOOD, mode="HUMAN_IN_LOOP", header=HEADER):
    response = client.post('/api/batches', data={'execution_mode': mode},
                           files=[('files', ('employees.csv', (header + rows).encode(), 'text/csv'))])
    assert response.status_code == 201
    return response.json()['batch_id']


def map_and_review(client, batch):
    assert client.post(f'/api/batches/{batch}/mapping-proposals?fallback=true').status_code == 200
    client.post(f'/api/batches/{batch}/workflow/start')
    for review in client.get(f'/api/batches/{batch}/escalations').json():
        if review['status'] == 'OPEN':
            assert client.post(f"/api/escalations/{review['escalation_id']}/resolve",
                               json={'action': 'APPROVE', 'actor': 'test'}).status_code == 200


def test_invalid_calendar_date_and_unambiguous_slash_dates():
    invalid = clean_record('a.csv', '1', {'date': '2024-02-30'}, {'date': 'hire_date'})
    assert invalid.status == 'ESCALATION'
    assert invalid.transformed['hire_date'] == '2024-02-30'
    for raw in ['31/01/2024', '01/31/2024']:
        assert clean_record('a.csv', '1', {'date': raw}, {'date': 'hire_date'}).transformed['hire_date'] == '2024-01-31'
    assert clean_record('a.csv', '1', {'date': '01/02/2024'}, {'date': 'hire_date'}).transformed['hire_date'] == '01/02/2024'


def test_reject_all_record_errors_resumes_and_retransform_preserves_decision():
    client = TestClient(app)
    batch = upload(client, GOOD.replace('2024-01-15,Engineering', 'unknown,Unknown'))
    map_and_review(client, batch)
    client.post(f'/api/batches/{batch}/records/transform')
    items = [item for item in client.get(f'/api/batches/{batch}/escalations').json() if item['status'] == 'OPEN']
    assert len(items) >= 2
    result = client.post(f"/api/escalations/{items[0]['escalation_id']}/resolve", json={'action':'REJECT', 'actor':'test'})
    assert result.json()['status'] == 'COMPLETED'
    assert result.json()['open_escalations'] == 0
    assert client.post(f'/api/batches/{batch}/records/transform').json()[0]['status'] == 'REJECTED'


def test_direct_push_cannot_bypass_review_or_cancellation():
    client = TestClient(app)
    batch = upload(client, GOOD + GOOD.replace('E100', 'E101').replace('ada@', 'bob@').replace('2024-01-15', 'unknown'))
    map_and_review(client, batch)
    records = client.post(f'/api/batches/{batch}/records/transform').json()
    record = next(item for item in records if item['status'] == 'VALID')
    request = {'batch_id':batch, 'record_id':record['record_id'], 'source_record_id':record['source_record_id'],
               'idempotency_key':f'{batch}:direct', 'payload_hash':payload_hash(record['transformed'])}
    assert client.post('/mock-target/employees', json=request).status_code == 409
    assert client.post(f'/api/batches/{batch}/pipeline/cancel').status_code == 200
    assert client.post('/mock-target/employees', json=request).status_code == 409


def test_collision_requires_one_source_and_never_overwrites():
    client = TestClient(app)
    batch = upload(client, GOOD.replace('ada@example.com,', 'ada@example.com,other@example.com,'),
                   header=HEADER.replace('email,', 'email,work_email,'))
    client.post(f'/api/batches/{batch}/mapping-proposals?fallback=true')
    client.post(f'/api/batches/{batch}/workflow/start')
    collisions = [item for item in client.get(f'/api/batches/{batch}/escalations').json() if item['reason_code'] == 'TARGET_COLLISION']
    assert len(collisions) == 2
    path = lambda item: f"/api/escalations/{item['escalation_id']}/resolve"
    assert client.post(path(collisions[0]), json={'action':'APPROVE','actor':'test'}).status_code == 200
    assert client.post(path(collisions[1]), json={'action':'APPROVE','actor':'test'}).status_code == 409
    assert client.post(path(collisions[1]), json={'action':'REJECT','actor':'test'}).status_code == 200
    assert client.post(f'/api/batches/{batch}/records/transform').json()[0]['transformed']['email'] == 'ada@example.com'


def test_partial_failure_retry_and_rollback_update_pipeline(monkeypatch):
    monkeypatch.setattr(get_settings(), 'demo_failures', True)
    client = TestClient(app)
    batch = upload(client, GOOD.replace('ada@', 'retry.ada@'), mode='AUTOPILOT')
    client.post(f'/api/batches/{batch}/pipeline/advance?fallback=true')
    pushed = client.post(f'/api/batches/{batch}/pipeline/push-decision', json={'decision':'PUSH'})
    assert pushed.json()['status'] == 'PARTIAL_FAILURE'
    assert client.post(f'/mock-target/migrations/{batch}/retry').status_code == 200
    assert client.get(f'/api/batches/{batch}/pipeline').json()['status'] == 'COMPLETED'
    assert client.delete(f'/mock-target/migrations/{batch}').json()['rolled_back'] == 1
    assert client.get(f'/api/batches/{batch}/pipeline').json()['status'] == 'ROLLED_BACK'
    assert client.post(f'/mock-target/migrations/{batch}/retry').status_code == 409


def test_fast_path_calls_model_only_for_unfamiliar_columns():
    class Model:
        provider = 'test-open-model'
        seen = []
        def propose(self, *args):
            raise AssertionError('Batch calls only')
        def propose_many(self, source_file, columns, schema):
            self.seen.extend(column.name for column in columns)
            return {column.name: ModelMapping(target_field='department', confidence=.8,
                    alternatives=[], reasoning='Semantic match', warnings=[]) for column in columns}
    model = Model()
    frame = pd.DataFrame([{'employee_id':'E1', 'email':'a@example.com', 'organizational_group':'Engineering'}])
    profile = profile_frame(frame, 'safe.csv', 'utf-8', None)
    proposals = propose_mappings([profile], load_target_schema(), model, fast_path=True)
    assert model.seen == ['organizational_group']
    assert [item.provider for item in proposals] == ['verified_alias','verified_alias','test-open-model']
    assert proposals[2].requires_human


def test_expired_job_lease_can_be_reclaimed_once():
    client = TestClient(app)
    batch = upload(client)
    with SessionLocal() as db:
        db.execute(delete(PipelineJobRow))
        db.commit()
        enqueue(db, batch)
        first = claim(db)
        assert first and first[0] == batch
        assert claim(db) is None
        job = db.get(PipelineJobRow, batch)
        job.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
        second = claim(db)
        assert second and second[1] != first[1]
        assert claim(db) is None


def test_background_autopilot_completes_without_browser_advancing():
    with SessionLocal() as db:
        db.execute(delete(PipelineJobRow))
        db.commit()
    with TestClient(app) as client:
        started = time.perf_counter()
        batch = upload(client, mode='AUTOPILOT')
        assert time.perf_counter() - started < 3
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            status = client.get(f'/api/batches/{batch}/pipeline').json()['status']
            if status == 'COMPLETED':
                break
            time.sleep(.1)
        assert status == 'COMPLETED'
        assert client.get(f'/mock-target/migrations/{batch}').json()[0]['status'] == 'SUCCESS'


def test_job_resume_after_human_decision_without_browser_advancing():
    with SessionLocal() as db:
        db.execute(delete(PipelineJobRow))
        db.commit()
    client = TestClient(app)
    batch = upload(client, GOOD.replace('2024-01-15', '2024-02-30'), mode='AUTOPILOT')
    with SessionLocal() as db:
        task = claim(db)
    execute(*task)
    items = [item for item in client.get(f'/api/batches/{batch}/escalations').json() if item['status'] == 'OPEN']
    assert len(items) == 1
    response = client.post(f"/api/escalations/{items[0]['escalation_id']}/resolve",
                           json={'action':'CORRECT','corrected_value':'2024-02-29','actor':'test'})
    assert response.status_code == 200
    with SessionLocal() as db:
        task = claim(db)
    assert task
    execute(*task)
    assert client.get(f'/api/batches/{batch}/pipeline').json()['status'] == 'COMPLETED'
    assert client.get(f'/mock-target/migrations/{batch}').json()[0]['status'] == 'SUCCESS'


def test_evaluation_precision_penalizes_false_automatic_actions():
    import runpy
    from pathlib import Path
    evaluation = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'scripts/evaluate.py'))
    rows = [dict(expected='email', predicted='email', expected_auto=True, auto=True),
            dict(expected=None, predicted='email', expected_auto=False, auto=True),
            dict(expected='hire_date', predicted='hire_date', expected_auto=True, auto=False),
            dict(expected=None, predicted=None, expected_auto=False, auto=False)]
    result = evaluation['metrics'](rows)
    assert result['auto_apply_precision'] == .5
    assert result['escalation_precision'] == .5
    assert result['escalation_recall'] == .5


def test_unknown_column_samples_never_expose_names_or_salary():
    from app.ingestion.models import ColumnProfile
    from app.security import model_safe_column
    column = ColumnProfile(name='custom_value', inferred_type='string', null_ratio=0, unique_ratio=1,
                           masked_samples=['Jane Privateperson', 987654], likely_identifier=False, date_patterns=[])
    rendered = str(model_safe_column(column))
    assert 'Jane Privateperson' not in rendered and '987654' not in rendered


def test_row_limit_and_empty_csv_fail_with_actionable_errors(tmp_path, monkeypatch):
    from app.ingestion.profiler import IngestionError, profile_file
    import pytest
    monkeypatch.setattr(get_settings(), 'max_source_rows', 1)
    source = tmp_path / 'large.csv'
    source.write_text(HEADER + GOOD + GOOD)
    with pytest.raises(IngestionError, match='Split it'):
        profile_file(source, source.name)
    client = TestClient(app)
    response = client.post('/api/batches', files=[('files', ('blank.csv', b'\n\n', 'text/csv'))])
    assert response.status_code == 422


def test_multifile_autopilot_review_then_send():
    from pathlib import Path
    with SessionLocal() as db:
        db.execute(delete(PipelineJobRow))
        db.commit()
    client = TestClient(app)
    root = Path(__file__).resolve().parents[2] / 'sample_data'
    names = ['employees_india.csv', 'employee_master.xlsx', 'new_joiners.csv']
    result = client.post('/api/batches', data={'execution_mode':'AUTOPILOT'},
                         files=[('files',(name,(root/name).read_bytes())) for name in names])
    assert result.status_code == 201
    batch = result.json()['batch_id']
    for _ in range(4):
        with SessionLocal() as db:
            task = claim(db)
        if task:
            execute(*task)
        state = client.get(f'/api/batches/{batch}/pipeline').json()
        if state['status'] == 'COMPLETED':
            break
        items = [item for item in client.get(f'/api/batches/{batch}/escalations').json() if item['status'] == 'OPEN']
        assert items
        for item in items:
            action = 'REJECT' if item['source_context'].get('kind', '').startswith('record_') else 'APPROVE'
            response = client.post(f"/api/escalations/{item['escalation_id']}/resolve",json={'action':action,'actor':'test'})
            assert response.status_code == 200
    assert state['status'] == 'COMPLETED'
    records = client.get(f'/api/batches/{batch}/records').json()
    assert sum(record['transformed'].get('employee_id') == 'IN001' for record in records) == 1
    writes = client.get(f'/mock-target/migrations/{batch}').json()
    assert len(writes) == sum(record['status'] == 'VALID' for record in records)
    assert all(item['status'] == 'SUCCESS' for item in writes)


def test_cancel_during_analysis_never_sends(monkeypatch):
    import threading
    from app.api import pipeline
    with SessionLocal() as db:
        db.execute(delete(PipelineJobRow))
        db.commit()
    entered, release = threading.Event(), threading.Event()
    original = pipeline.create_mapping_proposals
    def slow_mapping(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)
    monkeypatch.setattr(pipeline, 'create_mapping_proposals', slow_mapping)
    with TestClient(app) as client:
        batch = upload(client, mode='AUTOPILOT')
        try:
            assert entered.wait(5)
            assert client.post(f'/api/batches/{batch}/pipeline/cancel').json()['status'] == 'CANCELLED'
        finally:
            release.set()
        time.sleep(.2)
        assert client.get(f'/api/batches/{batch}/pipeline').json()['status'] == 'CANCELLED'
        assert client.get(f'/mock-target/migrations/{batch}').json() == []


def test_named_model_results_are_matched_by_column_not_output_order():
    from app.mapping.engine import _validate_batch_result
    from app.ingestion.models import ColumnProfile
    columns = [ColumnProfile(name=name,inferred_type='string',null_ratio=0,unique_ratio=1,
                             masked_samples=[],likely_identifier=False,date_patterns=[]) for name in ['a','b']]
    result = _validate_batch_result({'mappings':[
        {'source_column':'b','target_field':'email','confidence':.9,'reasoning':'email'},
        {'source_column':'a','target_field':'employee_id','confidence':.9,'reasoning':'identifier'}]},columns)
    assert result['a'].target_field == 'employee_id'
    assert result['b'].target_field == 'email'
