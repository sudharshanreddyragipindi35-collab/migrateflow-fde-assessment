from dataclasses import dataclass

from app.mapping.models import MappingProposal

POLICY_WARNINGS = {
    "TARGET_COLLISION",
    "AMBIGUOUS_DATE",
    "CONFLICTING_IDENTIFIER",
    "DISPUTED_REQUIRED_FIELD",
    "MODEL_RECOVERY_FALLBACK",
    "PROVIDER_FAILOVER",
}


@dataclass(frozen=True)
class PolicyDecision:
    auto_apply: bool
    reason_code: str


def evaluate_mapping(proposal: MappingProposal) -> PolicyDecision:
    warnings = set(proposal.warnings)
    if proposal.collision or "TARGET_COLLISION" in warnings:
        return PolicyDecision(False, "TARGET_COLLISION")
    if warnings & POLICY_WARNINGS:
        return PolicyDecision(False, sorted(warnings & POLICY_WARNINGS)[0])
    if proposal.target_field is None or proposal.confidence < 0.65:
        return PolicyDecision(False, "LOW_CONFIDENCE_UNMAPPED")
    if proposal.evidence.type_compatibility <= 0:
        return PolicyDecision(False, "TYPE_INCOMPATIBLE")
    if proposal.confidence < 0.90:
        return PolicyDecision(False, "CONFIDENCE_REVIEW")
    return PolicyDecision(True, "HIGH_CONFIDENCE")
