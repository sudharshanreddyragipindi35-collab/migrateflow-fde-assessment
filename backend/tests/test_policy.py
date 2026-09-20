from app.agent.policy import evaluate_mapping
from app.mapping.models import MappingProposal, ScoreComponents


def proposal(confidence: float, **changes: object) -> MappingProposal:
    payload = dict(
        source_file="x.csv", source_column="Email", target_field="email", confidence=confidence,
        alternatives=[], reasoning="test",
        evidence=ScoreComponents(name_similarity=1, alias_match=1, type_compatibility=1, value_pattern=1, uniqueness=1, model_proposal=1),
        warnings=[], requires_human=confidence < .9, collision=False, provider="test",
    )
    payload.update(changes)
    return MappingProposal(**payload)


def test_policy_auto_applies_only_high_confidence_safe_mapping() -> None:
    assert evaluate_mapping(proposal(.95)).auto_apply
    assert not evaluate_mapping(proposal(.89)).auto_apply
    assert not evaluate_mapping(proposal(.99, collision=True)).auto_apply
    assert not evaluate_mapping(proposal(.99, warnings=["AMBIGUOUS_DATE"])).auto_apply
    assert not evaluate_mapping(proposal(.99, warnings=["MODEL_RECOVERY_FALLBACK"])).auto_apply
    assert not evaluate_mapping(proposal(.99, warnings=["PROVIDER_FAILOVER"])).auto_apply


def test_low_confidence_remains_unmapped() -> None:
    decision = evaluate_mapping(proposal(.4, target_field=None, requires_human=True))
    assert not decision.auto_apply
    assert decision.reason_code == "LOW_CONFIDENCE_UNMAPPED"
