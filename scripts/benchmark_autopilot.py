"""Small real-HTTP responsiveness probe, not a production load benchmark."""
import argparse
import json
import time
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://localhost:8000')
    args = parser.parse_args()
    samples = []
    csv = b'employee_id,first_name,last_name,email,hire_date,department,employment_status\nBENCH1,Ada,Lovelace,ada@example.test,2024-01-15,Engineering,Active\n'
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        runtime = client.get('/api/system/model').json()
        for _ in range(3):
            start = time.perf_counter()
            response = client.post('/api/batches', data={'execution_mode':'AUTOPILOT'}, files=[('files',('benchmark.csv',csv,'text/csv'))])
            response.raise_for_status()
            accepted = time.perf_counter()
            batch = response.json()['batch_id']
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                response = client.get(f'/api/batches/{batch}/pipeline')
                response.raise_for_status()
                state = response.json()['status']
                if state == 'COMPLETED':
                    break
                if state in {'PAUSED','FAILED','PARTIAL_FAILURE'}:
                    raise RuntimeError(f'Benchmark requires unattended success, got {state}')
                time.sleep(.1)
            else:
                raise RuntimeError('Autopilot did not finish within the 30-second probe budget')
            elapsed = time.perf_counter() - start
            writes = client.get(f'/mock-target/migrations/{batch}').json()
            assert len(writes) == 1 and writes[0]['status'] == 'SUCCESS'
            rollback = client.delete(f'/mock-target/migrations/{batch}')
            rollback.raise_for_status()
            assert rollback.json()['rolled_back'] == 1
            samples.append({'upload_response_ms':round((accepted-start)*1000,2),
                            'autopilot_completion_ms':round(elapsed*1000,2),
                            'sent_records':len(writes),'undone_records':1})
    report = {'scope':'three sequential single-record HTTP runs on this machine; includes queue polling',
              'model_mode':runtime['mode'], 'live_model_quality_measured':False, 'samples':samples}
    output = Path(__file__).resolve().parents[1] / 'evaluation/runtime_report.json'
    output.write_text(json.dumps(report,indent=2) + '\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
