"""
Image Strategy Validator — deterministic audit of the 10-slot Etsy gallery.

Rejection rules (any failure rejects the strategy):
  1. missing trust image        — no TRUST-intent slot with a proof visual
  2. missing scale clarity      — no slot resolving scale / what-you-get
  3. missing usage demonstration— fewer than 2 lifestyle/mockup usage slots
                                  (lifestyle_mockup + alternate_use_case roles)
  4. duplicate stage coverage   — any psychological stage claimed by >3 slots
  5. low diversity              — <5 distinct intents or <6 distinct visual types
  6. duplicate uncertainty      — slots sharing a primary uncertainty (also
                                  schema-enforced; re-checked here)
  7. prompt hard requirements   — every prompt renders with lighting/camera/
                                  environment/composition/product-focus/realism
                                  and the conversion clause
  8. blocker coverage           — every severity-5 image-resolvable uncertainty
                                  is claimed by some slot

On failure the validator emits precise regeneration feedback; the orchestrator
re-runs the Image Strategy Engine with that feedback until valid (bounded).
"""
from __future__ import annotations

from collections import Counter

from ..schemas import (BDEOutput, CONVERSION_CLAUSE, ImageIntent,
                       ImageStrategy, ValidationCheck, ValidationReport)

TRUST_VISUALS = {"zoom_proof", "process_shot", "comparison_split", "unboxing"}
SCALE_CLARITY_VISUALS = {"scale_reference", "file_grid", "size_chart", "variant_grid", "info_card"}
USAGE_VISUALS = {"lifestyle_scene", "mockup_in_use"}
MIN_USAGE_SLOTS = 2
MAX_STAGE_COVERAGE = 3
MIN_DISTINCT_INTENTS = 5
MIN_DISTINCT_VISUALS = 6


def validate(strategy: ImageStrategy, bde: BDEOutput) -> tuple[bool, list[ValidationCheck], list[str]]:
    slots = strategy.slots
    checks: list[ValidationCheck] = []
    feedback: list[str] = []

    def check(name: str, passed: bool, detail: str, fix: str = "") -> None:
        checks.append(ValidationCheck(check=name, passed=passed, detail=detail))
        if not passed:
            feedback.append(fix or detail)

    # 1. trust image
    trust_slots = [s for s in slots
                   if s.intent == ImageIntent.TRUST or s.required_visual_type in TRUST_VISUALS]
    check("trust_image_present", bool(trust_slots),
          f"{len(trust_slots)} trust-proof slot(s) found." if trust_slots
          else "No trust image: no TRUST-intent slot and no proof visual type.",
          "Add a TRUST slot with a quality-proof visual (zoom_proof, process_shot, or comparison_split).")

    # 2. scale / what-you-get clarity
    scale_slots = [s for s in slots
                   if s.required_visual_type in SCALE_CLARITY_VISUALS
                   or "scale" in s.objective.lower() or "size" in s.objective.lower()
                   or "what you get" in s.objective.lower() or "included" in s.objective.lower()]
    check("scale_clarity_present", bool(scale_slots),
          f"{len(scale_slots)} scale/what-you-get clarity slot(s) found." if scale_slots
          else "No scale clarity: nothing shows size, dimensions, or exactly what's included.",
          "Add a slot with scale_reference, file_grid, or size_chart resolving the size/contents doubt.")

    # 3. usage demonstration (lifestyle_mockup + alternate_use_case roles)
    usage_slots = [s for s in slots if s.required_visual_type in USAGE_VISUALS]
    check("usage_demonstration_present", len(usage_slots) >= MIN_USAGE_SLOTS,
          f"{len(usage_slots)} usage demonstration slot(s) found." if len(usage_slots) >= MIN_USAGE_SLOTS
          else f"Only {len(usage_slots)} usage demonstration slot(s): need at least {MIN_USAGE_SLOTS} "
               "(lifestyle_mockup and alternate_use_case).",
          f"Add lifestyle_scene or mockup_in_use visuals to slots 4 (lifestyle_mockup) and "
          f"5 (alternate_use_case) so the buyer can visualize ownership and a second use case.")

    # 4. duplicate psychological stage coverage
    stage_counts = Counter(s.psychological_stage for s in slots)
    over = {st.value: n for st, n in stage_counts.items() if n > MAX_STAGE_COVERAGE}
    check("no_duplicate_stage_coverage", not over,
          "Stage coverage balanced." if not over
          else f"Stages over-covered (>{MAX_STAGE_COVERAGE} slots): {over}",
          f"Redistribute slots: no psychological stage may be claimed by more than {MAX_STAGE_COVERAGE} slots. Over-covered: {over}")

    # 5. diversity across slots
    n_intents = len({s.intent for s in slots})
    n_visuals = len({s.required_visual_type for s in slots})
    diverse = n_intents >= MIN_DISTINCT_INTENTS and n_visuals >= MIN_DISTINCT_VISUALS
    check("slot_diversity", diverse,
          f"{n_intents} distinct intents, {n_visuals} distinct visual types.",
          f"Increase diversity: need >= {MIN_DISTINCT_INTENTS} distinct intents (have {n_intents}) "
          f"and >= {MIN_DISTINCT_VISUALS} distinct visual types (have {n_visuals}).")

    # 6. unique primary uncertainties
    primaries = [s.primary_uncertainty_id for s in slots]
    dupes = sorted({p for p in primaries if primaries.count(p) > 1})
    valid_ids = {u.id for u in bde.buyer_uncertainty_map}
    bad_ids = sorted(set(primaries) - valid_ids)
    check("unique_uncertainty_mapping", not dupes and not bad_ids,
          "Each slot claims a distinct, valid buyer uncertainty." if not dupes and not bad_ids
          else f"Duplicated primary uncertainty ids: {dupes}; invalid ids: {bad_ids}",
          f"Assign each slot a DIFFERENT primary_uncertainty_id from the provided map. Duplicates: {dupes}, invalid: {bad_ids}")

    # 7. prompt hard requirements (fields are schema-enforced; verify render)
    bad_prompts = []
    for s in slots:
        rendered = s.prompt.render()
        required = ["LIGHTING:", "CAMERA:", "ENVIRONMENT:", "COMPOSITION:",
                    "PRODUCT FOCUS:", "REALISM:", CONVERSION_CLAUSE]
        if not all(r in rendered for r in required):
            bad_prompts.append(s.slot_id)
    check("prompt_hard_requirements", not bad_prompts,
          "All prompts carry lighting/camera/environment/composition/product-focus/realism + conversion clause."
          if not bad_prompts else f"Slots with incomplete prompts: {bad_prompts}",
          f"Rebuild prompts for slots {bad_prompts} with every mandatory specification field.")

    # 8. severity-5 image-resolvable blockers covered
    critical = [u for u in bde.buyer_uncertainty_map
                if u.severity == 5 and "image" in [r.lower() for r in u.resolvable_by]]
    claimed = set(primaries) | {i for s in slots for i in s.secondary_uncertainty_ids}
    unresolved = [u for u in critical if u.id not in claimed]
    check("critical_blockers_covered", not unresolved,
          "All severity-5 image-resolvable doubts are claimed by a slot." if not unresolved
          else "Unclaimed purchase-blocking doubts: " + "; ".join(u.uncertainty for u in unresolved),
          "These severity-5 doubts MUST be claimed by a slot (primary or secondary): "
          + "; ".join(f"[id={u.id}] {u.uncertainty}" for u in unresolved))

    return all(c.passed for c in checks), checks, feedback


def build_report(valid: bool, checks: list[ValidationCheck], attempts: int,
                 all_feedback: list[str]) -> ValidationReport:
    return ValidationReport(valid=valid, checks=checks, attempts=attempts,
                            regeneration_feedback=all_feedback)
