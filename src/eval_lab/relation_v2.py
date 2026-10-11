"""Private authored relations, exact intent pins and read-only v1 compatibility."""
from typing import Literal
from pydantic import model_validator
from .domain import ARTIFACT_TYPES, RelationClaim, Ref
from .intent_v2 import CheckedValue, Pin, Text, kind, predecessor


class RelationClaimV2(RelationClaim, CheckedValue):
    schema_version: Literal[2] = 2
    intent: Pin
    creative_anchor: tuple[Text, ...] = ()
    epistemic_purpose: Literal["SUPPORT", "RULE_OUT", "DISCRIMINATE", "LOCALIZE", "EXPLAIN", "QUALIFY", "SCOPE", "OPERATIONALIZE"]
    operational_purpose: Literal["SHIP", "REPAIR", "REGENERATE", "REVISE_RUBRIC", "ADD_GOLD", "RETRAIN_SIGNAL", "INVESTIGATE"]
    warrant: Text | None = None
    qualifier: Text | None = None
    rebuttal: Text | None = None
    predecessor: Pin | None = None

    @model_validator(mode="after")
    def relation_contract(self):
        # Override the v1 Ref-based contract without changing any v1 payload.
        predecessor(self)
        kind(self.intent, "IntentSpecV2", "IntentSpec")
        endpoints = {
            "supports": ("Evidence", "Hypothesis"), "contradicts": ("Evidence", "Hypothesis"),
            "motivated_by": ("Hypothesis", "IntentSpec"), "fulfills": ("Evidence", self.intent.ref.kind),
            "violates": ("Evidence", self.intent.ref.kind), "alternative_to": ("Hypothesis", "Hypothesis"),
            "compatible_with": ("Hypothesis", "Hypothesis"), "refines": ("Hypothesis", "Hypothesis"),
        }
        if (self.subject.kind, self.object.kind) != endpoints[self.predicate]:
            raise ValueError("relation domain/range violation")
        if any(ref.kind != "Evidence" for ref in self.evidence):
            raise ValueError("relation evidence must reference Evidence")
        if self.epistemic_status == "observed" and not self.evidence:
            raise ValueError("observed relation needs evidence")
        if self.predicate in ("compatible_with", "refines") and self.subject.id == self.object.id:
            raise ValueError("hypothesis cannot relate to itself")
        if self.predicate not in ("fulfills", "violates") and self.epistemic_status == "observed":
            raise ValueError("hypothesis relations are claims, not observations")
        if self.valid_from.tzinfo is None or (self.valid_until is not None and (self.valid_until.tzinfo is None or self.valid_until <= self.valid_from)):
            raise ValueError("invalid validity interval")
        if self.predicate in ("supports", "contradicts") and self.warrant is None:
            raise ValueError("supports and contradicts require a warrant")
        if len(set(self.creative_anchor)) != len(self.creative_anchor):
            raise ValueError("creative_anchor IDs must be unique")
        return self


def evidence_refs(item):
    return set(item.evidence) | ({item.subject} if item.subject.kind == "Evidence" else set())


def validate_admission(item, get, bindings, media_has_intent):
    """Called with transaction-local retained records after all pin digest checks."""
    intent = get(item.intent.ref)
    if item.intent.ref.kind == "IntentSpec":
        if item.creative_anchor:
            raise ValueError("legacy intent cannot supply creative_anchor IDs")
    elif not set(item.creative_anchor) <= {c.id for c in intent.criteria}:
        raise ValueError("creative_anchor must belong to the exact pinned intent")
    for ref in evidence_refs(item):
        media = get(ref).media
        if item.intent.ref.kind == "IntentSpec":
            if not media_has_intent(media, item.intent.ref):
                raise ValueError("relation evidence is outside declared intent")
        elif not any(b.media.ref == media and b.intent == item.intent for b in bindings):
            raise ValueError("relation evidence requires a retained IntentBinding for exact media and intent")
    for ref in (item.subject, item.object):
        if ref.kind == "Hypothesis" and get(ref).intent != item.intent.ref:
            raise ValueError("relation crosses intent without explicit mapping")
        if ref.kind in ("IntentSpec", "IntentSpecV2") and ref != item.intent.ref:
            raise ValueError("relation intent mismatch")


class LegacyRelationView(CheckedValue):
    """Frozen, unregistered wrapper; canonical bytes always belong to its source."""
    source: RelationClaim
    epistemic_purpose: Literal["UNSPECIFIED"] = "UNSPECIFIED"
    operational_purpose: Literal["UNSPECIFIED"] = "UNSPECIFIED"
    creative_anchor: tuple[()] = ()
    warrant: None = None
    qualifier: None = None
    rebuttal: None = None

    def __getattr__(self, name):
        return getattr(self.source, name)

    def canonical(self):
        return self.source.canonical()


def load_relation(repo, ref: Ref):
    if ref.kind not in ("RelationClaim", "RelationClaimV2"):
        raise ValueError("load_relation requires a relation reference")
    item = repo.get(ref)
    return LegacyRelationView(source=item) if ref.kind == "RelationClaim" else item


def incoming_roots(repo, context, media):
    """One incoming expansion against the original dataset's exact closure only."""
    selected = []
    for item in repo.all("RelationClaimV2"):
        links = {item.subject, item.object, *item.evidence}
        direct = {ref for ref in links if ref.kind not in ("IntentSpec", "IntentSpecV2")}
        evidence_media = {repo.get(ref).media for ref in evidence_refs(item)}
        if direct.intersection(context) or (item.intent.ref in context and evidence_media and evidence_media <= media):
            selected.append(item.ref)
    return selected


ARTIFACT_TYPES["RelationClaimV2"] = RelationClaimV2
