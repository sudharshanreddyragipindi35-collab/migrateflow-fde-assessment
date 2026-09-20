from app.cleaning.service import clean_record, reconcile_records
from app.validation.employee import validation_errors


FULL_MAPPING = {
    "ID": "employee_id", "First": "first_name", "Last": "last_name", "Email": "email",
    "Joined": "hire_date", "Dept": "department", "Status": "employment_status",
}


def test_safe_cleaning_is_auditable_and_original_is_immutable() -> None:
    original = {
        "ID": " E-1 ", "First": " aSHA ", "Last": " RAO ", "Email": " ASHA@EXAMPLE.TEST ",
        "Joined": "2024-02-03", "Dept": "Engineering", "Status": "Active",
    }
    snapshot = dict(original)
    preview = clean_record("employees.csv", "1", original, FULL_MAPPING)
    assert preview.status == "VALID"
    assert preview.transformed["email"] == "asha@example.test"
    assert preview.transformed["first_name"] == "Asha"
    assert original == snapshot
    assert {item.field for item in preview.provenance} >= {"email", "hire_date"}


def test_ambiguous_date_is_not_guessed_and_second_failure_escalates() -> None:
    original = {
        "ID": "E-2", "First": "Mina", "Last": "Patel", "Email": "mina@example.test",
        "Joined": "01/02/2026", "Dept": "Support", "Status": "Active",
    }
    preview = clean_record("employees.csv", "2", original, FULL_MAPPING)
    assert preview.transformed["hire_date"] == "01/02/2026"
    assert preview.status == "ESCALATION"
    assert preview.attempt_count == 2


def test_exact_duplicates_merge_and_conflicts_are_not_overwritten() -> None:
    exact = [
        {"employee_id": "E1", "email": "a@example.test", "first_name": "A", "_source": "a.csv"},
        {"employee_id": "E1", "email": "a@example.test", "first_name": "A", "_source": "b.csv"},
    ]
    result = reconcile_records(exact)
    assert result.exact_merges == 1
    assert result.records[0]["_sources"] == ["a.csv", "b.csv"]
    conflict = reconcile_records(exact[:1] + [{"employee_id": "E1", "email": "other@example.test", "_source": "c.csv"}])
    assert conflict.probable_conflicts
    assert len(conflict.records) == 2
    assert conflict.records[0]["email"] == "a@example.test"


def test_missing_required_values_remain_explicit_failures() -> None:
    preview = clean_record("employees.csv", "3", {"ID": "E3"}, FULL_MAPPING)
    assert preview.status == "ESCALATION"
    assert any("email" in item for item in preview.errors)


def test_validation_errors_are_actionable_for_nontechnical_reviewers() -> None:
    payload = {
        "employee_id": 202,
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.test",
        "hire_date": "unknown",
        "department": "Engineering",
        "employment_status": "Active",
    }
    errors = validation_errors(payload)
    assert "employee_id: Enter the employee ID as text, for example EM202" in errors
    assert "hire_date: Enter a real date in YYYY-MM-DD format, for example 2024-01-15" in errors
