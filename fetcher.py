"""
Phase 1: Drug Data Fetcher
Uses OpenFDA and RxNorm APIs (both free, no API key required)
"""

import requests
import re


# ── API base URLs ──────────────────────────────────────────────────────────────
OPENFDA_URL = "https://api.fda.gov/drug/label.json"
RXNORM_URL  = "https://rxnav.nlm.nih.gov/REST"


# ── Text cleaning ──────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    """
    Strip FDA label boilerplate and normalise text for brochure display.
    Removes: section numbers, cross-references, control chars, excess whitespace.
    """
    if not text:
        return ""

    # Remove control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)

    # Remove leading FDA section numbers like "1 ", "2.1 ", "11 " at start of string
    text = re.sub(r"^\s*\d+(\.\d+)?\s+[A-Z]", lambda m: m.group(0).split()[-1], text)

    # Remove inline cross-references: [ see Warnings (5.1) ] style
    text = re.sub(r"\[\s*see[^\]]{0,80}\]", "", text, flags=re.IGNORECASE)

    # Remove parenthetical section refs like (5.1), (2.2), (4, 5.1)
    text = re.sub(r"\(\s*\d+(?:\.\d+)?(?:\s*,\s*\d+(?:\.\d+)?)*\s*\)", "", text)

    # Remove NDC codes
    text = re.sub(r"\b\d{5}-\d{4}-\d+\b", "", text)
    text = re.sub(r"Product:\s*\d+\s*", "", text)

    # Remove "X of Y" page markers
    text = re.sub(r"\b\d+\s+of\s+\d+\b", "", text)

    # Remove orphaned brackets left behind by prior substitutions
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\[\s*\]", "", text)

    # Collapse whitespace
    text = re.sub(r"\s{2,}", " ", text)

    return text.strip()


def _scrub_section_header(text: str) -> str:
    """
    Remove the leading 'N SECTION TITLE' that OpenFDA sometimes prepends.
    e.g. '2 DOSAGE & ADMINISTRATION Adult Dosage...' -> 'Adult Dosage...'
    """
    # Pattern: one or two digits, optional decimal, then ALL-CAPS words, then real content
    text = re.sub(
        r"^\s*\d{1,2}(?:\.\d{1,2})?\s+[A-Z][A-Z /&,\-]+\s+",
        "",
        text.strip()
    )
    return text.strip()


def _first(label: dict, *keys: str, fallback: str = "Not available") -> str:
    """Return the first non-empty value found among label keys, fully cleaned."""
    for key in keys:
        val = label.get(key)
        if val and isinstance(val, list) and val[0]:
            raw = _clean(val[0])
            return _scrub_section_header(raw)
    return fallback


def _list_field(label: dict, *keys: str) -> list[str]:
    """Return a list of cleaned strings from the first matching key."""
    for key in keys:
        val = label.get(key)
        if val and isinstance(val, list):
            return [_scrub_section_header(_clean(v)) for v in val if v]
    return []


def _smart_truncate(text: str, max_chars: int) -> str:
    """Truncate at a sentence boundary where possible."""
    if len(text) <= max_chars:
        return text
    # Try to cut at last sentence end before limit
    chunk = text[:max_chars]
    last_period = max(chunk.rfind(". "), chunk.rfind(".\n"))
    if last_period > max_chars * 0.6:
        return chunk[:last_period + 1]
    # Fall back to last word boundary
    last_space = chunk.rfind(" ")
    return chunk[:last_space] if last_space > 0 else chunk


# ── RxNorm helpers ─────────────────────────────────────────────────────────────

def _get_rxcui(drug_name: str) -> str | None:
    """Resolve a drug name to its RxCUI identifier."""
    try:
        r = requests.get(
            f"{RXNORM_URL}/rxcui.json",
            params={"name": drug_name, "search": 1},
            timeout=8,
        )
        r.raise_for_status()
        ids = r.json().get("idGroup", {}).get("rxnormId", [])
        return ids[0] if ids else None
    except Exception:
        return None


def _get_drug_class(rxcui: str) -> str:
    """Fetch the pharmacological drug class from RxNorm."""
    try:
        r = requests.get(
            f"{RXNORM_URL}/rxclass/class/byRxcui.json",
            params={"rxcui": rxcui, "relaSource": "ATC"},
            timeout=8,
        )
        r.raise_for_status()
        groups = r.json().get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", [])
        if groups:
            return groups[0].get("rxclassMinConceptItem", {}).get("className", "")
    except Exception:
        pass
    return ""


def _get_brand_generics(rxcui: str) -> dict:
    """Return brand name list from RxNorm."""
    result = {"brand_names": []}
    try:
        r = requests.get(
            f"{RXNORM_URL}/rxcui/{rxcui}/related.json",
            params={"tty": "BN+SBD"},
            timeout=8,
        )
        r.raise_for_status()
        concepts = (
            r.json()
            .get("relatedGroup", {})
            .get("conceptGroup", [])
        )
        for group in concepts:
            for prop in group.get("conceptProperties", []):
                name = prop.get("name", "")
                tty  = prop.get("tty", "")
                if tty == "BN" and name:
                    result["brand_names"].append(name)
    except Exception:
        pass
    return result


# ── OpenFDA fetch ──────────────────────────────────────────────────────────────

def _fetch_openfda(drug_name: str) -> dict | None:
    """
    Query OpenFDA drug label endpoint.
    Tries multiple query strategies; returns the raw label dict or None.
    """
    name_encoded = drug_name.lower().replace(" ", "+")
    queries = [
        f'openfda.brand_name:{name_encoded}',
        f'openfda.generic_name:{name_encoded}',
        f'openfda.substance_name:{name_encoded}',
        name_encoded,                                # full-text fallback
    ]
    for query in queries:
        try:
            r = requests.get(
                OPENFDA_URL,
                params={"search": query, "limit": 1},
                timeout=10,
            )
            if r.status_code == 200:
                results = r.json().get("results", [])
                if results:
                    return results[0]
        except Exception:
            continue
    return None


# ── Public API ─────────────────────────────────────────────────────────────────

def fetch_drug_data(drug_name: str) -> dict:
    """
    Main entry point. Returns a structured dict ready for brochure generation.

    Keys:
        drug_name, generic_name, brand_names, drug_class, manufacturer,
        description, indications, dosage, contraindications,
        warnings, adverse_reactions, how_supplied, storage
    """
    drug_name = drug_name.strip()
    label     = _fetch_openfda(drug_name)

    if label is None:
        return {"error": f"No FDA label data found for '{drug_name}'."}

    openfda = label.get("openfda", {})

    # ── Basic identifiers ──────────────────────────────────────────────────────
    generic_name = _clean(", ".join(openfda.get("generic_name", [])))
    brand_names  = list(dict.fromkeys(           # deduplicate, preserve order
        _clean(b) for b in openfda.get("brand_name", [])
    ))
    manufacturer = _clean(", ".join(openfda.get("manufacturer_name", [])))

    # ── RxNorm enrichment ──────────────────────────────────────────────────────
    drug_class = ""
    rxcui = _get_rxcui(drug_name)
    if rxcui:
        drug_class = _get_drug_class(rxcui)
        if not brand_names:
            brand_names = _get_brand_generics(rxcui)["brand_names"]

    # ── Label sections ─────────────────────────────────────────────────────────
    description = _smart_truncate(
        _first(label, "description", "clinical_pharmacology",
               fallback="No description available."), 550)

    indications = _smart_truncate(
        _first(label, "indications_and_usage",
               fallback="Indications not listed."), 500)

    dosage = _smart_truncate(
        _first(label, "dosage_and_administration",
               fallback="Dosage information not available."), 500)

    contraindications = _smart_truncate(
        _first(label, "contraindications",
               fallback="No contraindications listed."), 400)

    warnings_raw = _list_field(
        label, "warnings_and_cautions", "warnings", "boxed_warning")
    warnings = _smart_truncate(
        " ".join(warnings_raw) if warnings_raw else "No specific warnings listed.", 450)

    adverse_reactions = _smart_truncate(
        _first(label, "adverse_reactions",
               fallback="Adverse reactions not listed."), 400)

    how_supplied = _smart_truncate(
        _first(label, "how_supplied",
               fallback="Supply information not available."), 300)

    storage = _smart_truncate(
        _first(label, "storage_and_handling",
               fallback="Store as per manufacturer guidelines."), 250)

    return {
        "drug_name"         : drug_name.title(),
        "generic_name"      : generic_name or drug_name.title(),
        "brand_names"       : brand_names[:6] or [drug_name.title()],
        "drug_class"        : drug_class or "Pharmaceutical Agent",
        "manufacturer"      : manufacturer or "See package insert",
        "description"       : description,
        "indications"       : indications,
        "dosage"            : dosage,
        "contraindications" : contraindications,
        "warnings"          : warnings,
        "adverse_reactions" : adverse_reactions,
        "how_supplied"      : how_supplied,
        "storage"           : storage,
    }


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    data = fetch_drug_data("metformin")
    print(json.dumps(data, indent=2))
