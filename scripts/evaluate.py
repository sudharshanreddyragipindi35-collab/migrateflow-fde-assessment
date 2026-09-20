"""Measured deterministic benchmark; does not claim live-model accuracy."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.agent.policy import evaluate_mapping
from app.cleaning.service import clean_record, reconcile_records
from app.ingestion.models import ColumnProfile, SourceFileProfile
from app.mapping.engine import DeterministicFallback, propose_mappings
from app.mapping.schema import load_target_schema


def ratio(n, d):
    return round(n / d, 4) if d else None


def metrics(outcomes):
    correct = sum(r['predicted'] is not None and r['predicted'] == r['expected'] for r in outcomes)
    safe = sum(r['auto'] and r['expected_auto'] and r['predicted'] == r['expected'] for r in outcomes)
    escalated = sum(not r['auto'] and not r['expected_auto'] for r in outcomes)
    return {
        'mapping_precision': ratio(correct, sum(r['predicted'] is not None for r in outcomes)),
        'mapping_recall': ratio(correct, sum(r['expected'] is not None for r in outcomes)),
        'auto_apply_precision': ratio(safe, sum(r['auto'] for r in outcomes)),
        'auto_apply_recall': ratio(safe, sum(r['expected_auto'] for r in outcomes)),
        'escalation_precision': ratio(escalated, sum(not r['auto'] for r in outcomes)),
        'escalation_recall': ratio(escalated, sum(not r['expected_auto'] for r in outcomes)),
    }


def main():
    started = time.perf_counter()
    cases = json.loads((ROOT / 'evaluation/cases.json').read_text())
    outcomes = []
    for case in cases:
        profile = SourceFileProfile(file_name='evaluation.csv', sheet_name=None, row_count=3,
            duplicate_row_count=0, encoding='utf-8', columns=[ColumnProfile(
                name=case['source_column'], inferred_type=case['source_type'], null_ratio=0,
                unique_ratio=1, masked_samples=['masked'], likely_identifier=True,
                date_patterns=case.get('date_patterns', ['YYYY-MM-DD'] if case['source_type'] == 'date' else []))])
        proposal = propose_mappings([profile], load_target_schema(), DeterministicFallback())[0]
        outcomes.append({'source':case['source_column'], 'expected':case['expected_target'],
            'predicted':proposal.target_field, 'auto':evaluate_mapping(proposal).auto_apply,
            'expected_auto':case['expected_auto_apply']})
    base = {'employee_id':'E1','first_name':'Ada','last_name':'Lovelace','email':'ada@example.com',
            'hire_date':'2024-01-15','department':'Engineering','employment_status':'Active'}
    date_cases = [('2024-01-15','VALID'), ('2024-02-30','ESCALATION'), ('31/01/2024','VALID'),
                  ('01/31/2024','VALID'), ('01/02/2024','ESCALATION'), ('','ESCALATION')]
    date_outcomes = []
    for value, expected in date_cases:
        result = clean_record('dates.csv','1',{**base,'hire_date':value},{key:key for key in base})
        date_outcomes.append({'input':value,'expected':expected,'actual':result.status})
    merge_cases = [([base, dict(base)], 1, 0),
                   ([base, {**base,'email':'other@example.com'}], 2, 1),
                   ([base, {**base,'employee_id':'E2'}], 2, 0)]
    merge_correct = 0
    for records, count, conflicts in merge_cases:
        result = reconcile_records(records)
        merge_correct += len(result.records) == count and len(result.probable_conflicts) == conflicts
    report = {
        'method':'deterministic golden cases; live Ollama quality is evaluated separately',
        **metrics(outcomes), 'case_count':len(outcomes), 'mapping_outcomes':outcomes,
        'date_validation_accuracy':ratio(sum(r['expected'] == r['actual'] for r in date_outcomes),len(date_outcomes)),
        'date_cases':date_outcomes, 'reconciliation_accuracy':ratio(merge_correct,len(merge_cases)),
        'reconciliation_case_count':len(merge_cases),
        'integration_evidence':'Executable API regression tests; no synthetic success metric.',
        'elapsed_seconds':round(time.perf_counter()-started,4),
    }
    (ROOT / 'evaluation/report.json').write_text(json.dumps(report,indent=2) + chr(10))
    print(json.dumps(report,indent=2))
    if any(r['auto'] and (not r['expected_auto'] or r['predicted'] != r['expected']) for r in outcomes):
        raise SystemExit('Unsafe automatic mapping in benchmark')
    if report['date_validation_accuracy'] != 1 or report['reconciliation_accuracy'] != 1:
        raise SystemExit('Deterministic data quality regression')


if __name__ == '__main__':
    main()
