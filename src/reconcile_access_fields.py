"""Conservative three-state reconciliation from current evidence and prior references.

Prior audit values never become current truth merely because names match. Explicit
current field statements can resolve missing tags only for finished records.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
import re
import pandas as pd
from .parse_attributes import clean_token


ACCESS_TAGS = {
    "near_public_transit": "Near Public Transit",
    "free_entry_parking": "Free Entry / Parking",
    "restrooms_available": "Restrooms Available",
    "accessible_parking": "Accessible Parking",
    "accessible_restroom": "Accessible Restroom",
    "wheelchair_stroller_friendly_trail": "Wheelchair / Stroller Friendly Trail",
}
PROFILE_ORDER = ["Transit + free parking", "Transit only", "Free parking only", "Neither", "Unknown / unresolved"]


def normalize_state(value):
    text = str(value).strip().casefold()
    if text in {"1", "1.0", "true", "yes", "y"}:
        return "YES"
    if text in {"0", "0.0", "false", "no", "n"}:
        return "NO"
    return "UNKNOWN"


def transportation_profile(transit, parking):
    transit, parking = normalize_state(transit), normalize_state(parking)
    return {("YES", "YES"): PROFILE_ORDER[0], ("YES", "NO"): PROFILE_ORDER[1],
            ("NO", "YES"): PROFILE_ORDER[2], ("NO", "NO"): PROFILE_ORDER[3]}.get((transit, parking), PROFILE_ORDER[4])


def _sentences(text):
    return [clean_token(sentence) for sentence in re.split(r"(?<=[.!?])\s+|[\r\n]+", str(text or "")) if sentence.strip()]


def _evidence_clauses(text):
    # Contrast clauses can describe different places. Keep each assertion scoped.
    return [clean_token(clause) for sentence in _sentences(text)
            for clause in re.split(r";\s*(?:however,?\s*)?|\bhowever,?\s*|,\s*but\s+", sentence, flags=re.I)
            if clause.strip()]


def _remote_facility(clause):
    return bool(re.search(
        r"\b(?:lead|leads|leading|walk|travel|go)\b.{0,100}\b(?:main|another|different|other) entrance\b"
        r"|\b(?:at|in|inside|from) (?:an? |the )?(?:another|different|other|nearby) (?:entrance|section|park|station|business|restaurant)\b"
        r"|\b(?:miles?|kilomet(?:er|re)s?) (?:away|from (?:here|this))\b", clause, re.I))


def narrative_evidence(field, text):
    """Return only narrowly explicit positive/negative field assertions.

    Flat surfaces never prove wheelchair suitability; bus mentions never prove
    the half-mile rule; free admission alone never proves free designated parking.
    """
    yes, no = [], []
    for sentence in _evidence_clauses(text):
        lower = sentence.casefold()
        if field in ("restrooms_available", "accessible_restroom") and _remote_facility(sentence):
            continue
        if field == "near_public_transit":
            # Official spatial calculation is the primary independent verification.
            continue
        elif field == "free_entry_parking":
            negative = bool(re.search(r"\b(?:parking|admission|entrance|entry) (?:fees? (?:apply|are required)|(?:is |requires? )?(?:paid|not free|a fee))\b|\b(?:paid parking|parking (?:is [^.]{0,25} )?for a fee|no (?:designated |on[- ]site )?parking\b(?! (?:fees?|costs?|charges?|restrictions?)))\b", lower))
            positive = bool(re.search(r"\b(?:free (?:entry|admission) and (?:free )?parking|(?:entry|admission) and parking (?:are |is )?(?:both )?free|parking and (?:entry|admission) (?:are |is )?(?:both )?free)\b", lower))
            # Seasonal/resident-only discounts do not satisfy the always-free policy.
            if positive and re.search(r"\b(?:residents? only|off[- ]season|weekdays? only|except|sometimes)\b", lower):
                positive = False
        elif field == "accessible_parking":
            negative = bool(re.search(r"\b(?:no |without |(?:do not|does not|don't|doesn't) (?:have|include) (?:a )?)(?:designated |marked )?(?:accessible|handicap(?:ped)?) (?:parking|spaces?|spots?)\b|\baccessible parking (?:is )?(?:not available|unavailable|absent)\b", lower))
            positive = bool(re.search(r"\b(?:designated|marked) (?:accessible|handicap(?:ped)?) (?:parking|spaces?|spots?)\b|\b(?:accessible|handicap(?:ped)?) parking (?:spaces? |spots? )?(?:is |are )?(?:available|provided)\b", lower) or (re.search(r"\b(?:accessible|handicap(?:ped)?) (?:parking|spaces?)\b", lower) and re.search(r"\baccess aisles?\b", lower))) and not negative
        elif field == "accessible_restroom":
            negative = bool(re.search(r"\b(?:no|not an?|without an?) (?:accessible|ada[- ](?:accessible|compliant)) (?:restrooms?|bathrooms?|toilets?)\b|\b(?:restrooms?|bathrooms?|toilets?) (?:are |is )?not (?:wheelchair )?accessible\b", lower))
            positive = bool(re.search(r"\b(?:accessible|ada[- ](?:accessible|compliant)) (?:restrooms?|bathrooms?|toilets?)\b|\b(?:restrooms?|bathrooms?) with accessible stalls\b", lower)) and not negative
            if re.search(r"\b(?:porta[- ]?potty|porta[- ]?potties|portable (?:toilets?|restrooms?|bathrooms?))\b", lower):
                positive = False
        elif field == "restrooms_available":
            negative = bool(re.search(r"\b(?:no|not an?|without an?) (?:public |permanent |on[- ]site )?(?:restrooms?|bathrooms?|toilets?)\b|\b(?:restrooms?|bathrooms?) (?:are |is )?(?:not available|unavailable|absent)\b", lower))
            positive = bool(re.search(r"\b(?:(?:public|accessible) )?(?:restrooms?|bathrooms?) (?:are |is )?(?:available|located|provided)\b|\b(?:includes?|has|have|offers?) (?:an? |public |accessible )*(?:restrooms?|bathrooms?)\b|\ban? (?:accessible |public )?(?:restroom|bathroom)\b", lower)) and not negative
            if re.search(r"\b(?:porta[- ]?potty|porta[- ]?potties|portable (?:toilets?|restrooms?|bathrooms?)|nearby (?:station|business|restaurant))\b", lower):
                positive = False
        elif field == "wheelchair_stroller_friendly_trail":
            negative = bool(re.search(r"\b(?:trail|path)s? (?:are |is )?not (?:wheelchair|stroller)[- ](?:accessible|friendly)\b|\bno wheelchair[- ]accessible (?:trail|path)\b", lower))
            positive = bool(re.search(r"\b(?:wheelchair|stroller)[- ](?:accessible|friendly) (?:trail|path)\b|\b(?:trail|path)s? (?:are |is )?(?:wheelchair|stroller)[- ](?:accessible|friendly)\b", lower)) and not negative
        else:
            continue
        if negative:
            no.append(sentence)
        if positive:
            yes.append(sentence)
    if yes and no:
        return "CONFLICT", " | ".join(dict.fromkeys([*yes, *no]))
    if yes:
        return "YES", " | ".join(dict.fromkeys(yes))
    if no:
        return "NO", " | ".join(dict.fromkeys(no))
    return "UNKNOWN", ""


def _identity(row):
    return tuple(clean_token(row.get(field, "")).casefold() for field in ["asset_name", "site_name", "municipality"])


def _load_previous_audits(root, config):
    audit_dir = Path(root) / config.get("paths", {}).get("previous_audits", "reference/previous_audits")
    frames = []
    # CSV and XLSX pairs are alternate representations; prefer CSV and avoid double counting.
    files = sorted(audit_dir.glob("*.csv")) if audit_dir.exists() else []
    if not files and audit_dir.exists():
        files = sorted(audit_dir.glob("*.xlsx"))
    for path in files:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False) if path.suffix == ".csv" else pd.read_excel(path, dtype=str).fillna("")
        if not {"asset_name", "site_name"}.issubset(frame.columns):
            continue
        frame["_audit_file"] = path.relative_to(root).as_posix()
        frames.extend(frame.to_dict("records"))
    return frames


def reconcile_access_fields(df, root, config=None):
    config = config or {}
    result = df.copy()
    references = _load_previous_audits(Path(root), config)
    by_id, by_name = {}, {}
    for reference in references:
        if reference.get("asset_id"):
            by_id.setdefault(str(reference["asset_id"]), []).append(reference)
        by_name.setdefault(_identity(reference), []).append(reference)
    audit_rows, output_rows = [], []
    for row in result.to_dict("records"):
        matches = by_id.get(str(row["asset_id"]), []) or by_name.get(_identity(row), [])
        match_status = "exact_unique_match" if len(matches) == 1 else "ambiguous_exact_match" if len(matches) > 1 else "no_match"
        reference = matches[0] if len(matches) == 1 else {}
        candidates = []
        if not matches and row.get("record_status") == "accepted":
            identity = _identity(row)
            for prior in references:
                prior_identity = _identity(prior)
                if identity[1:] == prior_identity[1:] and SequenceMatcher(None, identity[0], prior_identity[0]).ratio() >= 0.88:
                    candidates.append(prior.get("asset_name", ""))
        row["previous_audit_match_status"] = match_status
        row["previous_audit_candidate_names"] = sorted(set(candidates))
        tags = {clean_token(tag).casefold() for tag in row.get("attribute_list", [])}
        narrative = "\n".join(str(row.get(field, "") or "") for field in ["field_description", "accessibility_description"])
        aisle_quotes = [s for s in _sentences(narrative) if re.search(r"\baccess aisles?\b", s, re.I)]
        row["accessible_parking_qualification"] = (
            "Access-aisle observation (separate from the presence of designated spaces; no compliance determination): "
            + " | ".join(aisle_quotes)) if aisle_quotes else ""
        remote_quotes = [s for s in _evidence_clauses(narrative)
                         if _remote_facility(s) and re.search(r"\b(restrooms?|bathrooms?|toilets?)\b", s, re.I)]
        row["restrooms_available_context_note"] = (
            "Other-location evidence excluded from this asset's restroom value: " + " | ".join(remote_quotes)) if remote_quotes else ""
        for field, tag in ACCESS_TAGS.items():
            original = "YES" if tag.casefold() in tags else "UNKNOWN"
            audited = original
            status = "structured_tag_only" if original == "YES" else "unknown"
            evidence = f"Current structured MAPC tag: {tag}" if original == "YES" else "Structured tag absent; absence does not prove No."
            source = f"{row.get('source_file', '')} CSV record {row.get('source_record_index', '')}"
            narrative_value, narrative_quote = narrative_evidence(field, narrative)
            finished = row.get("field_validated") is True
            if narrative_value != "UNKNOWN" and finished:
                if narrative_value == "CONFLICT" or (original == "YES" and narrative_value == "NO"):
                    audited, status = "UNKNOWN", "conflict_needs_review"
                    evidence = "Current source conflict: " + narrative_quote
                else:
                    audited = narrative_value
                    status = "field_narrative_verified" if original == narrative_value else "corrected_from_field_narrative"
                    evidence = narrative_quote
                source += "; current finished-record field narrative"
            elif narrative_value != "UNKNOWN":
                evidence += " Unfinished-record narrative candidate (not applied): " + narrative_quote
            if row.get("record_status") != "accepted":
                audited, status = "UNKNOWN", "unknown"
                evidence = "Record quarantined: " + str(row.get("record_issue", ""))
            # Keep both verbose and audit-compatible suffixes, never silently replacing originals.
            row[field] = audited
            row[field + "_original_value"] = original
            row[field + "_audited_value"] = audited
            row[field + "_verification_status"] = status
            row[field + "_evidence"] = evidence
            row[field + "_source"] = source
            prior_value = reference.get(field + "_audited", reference.get(field + "_audited_value", ""))
            prior_outcome = "no_matching_prior_reference"
            if reference:
                prior_outcome = "agrees_with_current_evidence" if normalize_state(prior_value) == audited else "not_applied_requires_current_evidence"
            audit_rows.append({
                "source_record_key": row["source_record_key"], "source_row_uid": row["source_row_uid"],
                "source_row_number": row["source_row_number"], "asset_id": row["asset_id"],
                "asset_name": row["asset_name"], "site_name": row["site_name"], "field": field,
                "original_value": original, "audited_value": audited, "verification_status": status,
                "evidence": evidence, "source": source, "narrative_candidate_value": narrative_value,
                "prior_match_status": match_status, "prior_audited_value": prior_value,
                "prior_verification_status": reference.get(field + "_verification_status", ""),
                "prior_evidence": reference.get(field + "_evidence", ""),
                "prior_source": reference.get(field + "_source", ""),
                "prior_audit_file": reference.get("_audit_file", ""), "prior_reassessment": prior_outcome,
                "prior_fuzzy_candidates_review_only": " | ".join(sorted(set(candidates))),
            })
        row["transportation_access_profile"] = transportation_profile(row["near_public_transit"], row["free_entry_parking"])
        output_rows.append(row)
    return pd.DataFrame(output_rows), pd.DataFrame(audit_rows)
