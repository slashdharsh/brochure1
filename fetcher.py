"""
Phase 1: Drug Data Fetcher
Uses OpenFDA and RxNorm APIs (both free, no API key required)
"""

import requests
import re

OPENFDA_URL = "https://api.fda.gov/drug/label.json"
RXNORM_URL  = "https://rxnav.nlm.nih.gov/REST"

# All-caps FDA section title words to strip
_SECTION_TITLES = re.compile(
    r"^\s*(?:\d{1,2}(?:\.\d{1,2})?\s+)?"   # optional leading number
    r"(?:"
    r"INDICATIONS?\s+AND\s+USAGE|"
    r"DOSAGE\s+AND\s+ADMINISTRATION|"
    r"CONTRAINDICATIONS?|"
    r"WARNINGS?\s+AND\s+PRECAUTIONS?|"
    r"WARNINGS?|"
    r"PRECAUTIONS?|"
    r"ADVERSE\s+REACTIONS?|"
    r"CLINICAL\s+PHARMACOLOGY|"
    r"DESCRIPTION|"
    r"HOW\s+SUPPLIED(?:/STORAGE\s+AND\s+HANDLING)?|"
    r"STORAGE\s+AND\s+HANDLING|"
    r"DRUG\s+INTERACTIONS?|"
    r"USE\s+IN\s+SPECIFIC\s+POPULATIONS?|"
    r"OVERDOSAGE|"
    r"MECHANISM\s+OF\s+ACTION"
    r")\s*",
    re.IGNORECASE
)


def _clean(text: str) -> str:
    if not text:
        return ""
    # Control chars
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    # Cross-references: [ see Warnings (5.1) ]
    text = re.sub(r"\[\s*see[^\]]{0,120}\]", "", text, flags=re.IGNORECASE)
    # Parenthetical section refs (5.1), (2.2), (4, 5.1)
    text = re.sub(r"\(\s*\d+(?:\.\d+)?(?:\s*,\s*\d+(?:\.\d+)?)*\s*\)", "", text)
    # NDC codes  60760-586-90
    text = re.sub(r"\b\d{5}-\d{3,4}-\d+\b", "", text)
    text = re.sub(r"NDC\s*[\d\-]+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Product:\s*\d+\s*", "", text)
    # Page markers
    text = re.sub(r"\b\d+\s+of\s+\d+\b", "", text)
    # Chemical formulas like "C 21 H 31 N 3 O 5" or "C21H31N3O5"
    text = re.sub(r"\b[A-Z]\s*\d*\s*(?:[A-Z]\s*\d*\s*){2,}\b", "", text)
    # Empirical formula lines
    text = re.sub(r"(?:empirical|molecular|structural)\s+formula[^.]*\.", "", text, flags=re.IGNORECASE)
    # "Its empirical formula is ..."
    text = re.sub(r"Its\s+empirical\s+formula\s+is[^.]*\.", "", text, flags=re.IGNORECASE)
    # Molecular weight lines
    text = re.sub(r"molecular\s+weight\s+of\s+[\d.]+", "", text, flags=re.IGNORECASE)
    # Orphaned brackets
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\[\s*\]", "", text)
    # "BOTTLES OF N  Storage ..." — strip storage line from how_supplied
    text = re.sub(r"BOTTLES?\s+OF\s+\d+\s+Storage.*", "", text, flags=re.IGNORECASE)
    # Collapse whitespace
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def _strip_header(text: str) -> str:
    """Remove leading ALL-CAPS FDA section title from text body."""
    # Strip known titles
    text = _SECTION_TITLES.sub("", text.strip())
    # Also strip any remaining leading ALL-CAPS word run (≥2 consecutive caps words)
    text = re.sub(r"^(?:[A-Z]{2,}(?:\s+(?:AND|OR|OF|IN|FOR|TO|WITH|THE|A|AN)?\s*)?){2,}\s+", "", text.strip())
    return text.strip()


def _first(label, *keys, fallback="Not available"):
    for key in keys:
        val = label.get(key)
        if val and isinstance(val, list) and val[0]:
            return _strip_header(_clean(val[0]))
    return fallback


def _list_field(label, *keys):
    for key in keys:
        val = label.get(key)
        if val and isinstance(val, list):
            return [_strip_header(_clean(v)) for v in val if v]
    return []


def _smart_truncate(text, max_chars):
    if len(text) <= max_chars:
        return text
    chunk = text[:max_chars]
    last_period = max(chunk.rfind(". "), chunk.rfind(".\n"))
    if last_period > max_chars * 0.6:
        return chunk[:last_period + 1]
    last_space = chunk.rfind(" ")
    return chunk[:last_space] if last_space > 0 else chunk


# ── RxNorm ─────────────────────────────────────────────────────────────────────

def _get_rxcui(drug_name):
    try:
        r = requests.get(f"{RXNORM_URL}/rxcui.json",
                         params={"name": drug_name, "search": 1}, timeout=8)
        r.raise_for_status()
        ids = r.json().get("idGroup", {}).get("rxnormId", [])
        return ids[0] if ids else None
    except Exception:
        return None


def _get_drug_class(rxcui):
    try:
        r = requests.get(f"{RXNORM_URL}/rxclass/class/byRxcui.json",
                         params={"rxcui": rxcui, "relaSource": "ATC"}, timeout=8)
        r.raise_for_status()
        groups = r.json().get("rxclassDrugInfoList", {}).get("rxclassDrugInfo", [])
        if groups:
            return groups[0].get("rxclassMinConceptItem", {}).get("className", "")
    except Exception:
        pass
    return ""


def _get_brand_names(rxcui):
    try:
        r = requests.get(f"{RXNORM_URL}/rxcui/{rxcui}/related.json",
                         params={"tty": "BN+SBD"}, timeout=8)
        r.raise_for_status()
        concepts = r.json().get("relatedGroup", {}).get("conceptGroup", [])
        names = []
        for group in concepts:
            for prop in group.get("conceptProperties", []):
                if prop.get("tty") == "BN" and prop.get("name"):
                    names.append(prop["name"])
        return names
    except Exception:
        return []


# ── OpenFDA ────────────────────────────────────────────────────────────────────

def _fetch_openfda(drug_name):
    name_enc = drug_name.lower().replace(" ", "+")
    for query in [
        f'openfda.brand_name:{name_enc}',
        f'openfda.generic_name:{name_enc}',
        f'openfda.substance_name:{name_enc}',
        name_enc,
    ]:
        try:
            r = requests.get(OPENFDA_URL, params={"search": query, "limit": 1}, timeout=10)
            if r.status_code == 200:
                results = r.json().get("results", [])
                if results:
                    return results[0]
        except Exception:
            continue
    return None


# ── Drug-specific filler content ───────────────────────────────────────────────

def _derive_monitoring(drug_class: str, indications: str, warnings: str) -> list[str]:
    """Return monitoring parameters relevant to the drug's class/use."""
    text = (drug_class + " " + indications + " " + warnings).lower()
    params = []
    if any(w in text for w in ["renal", "kidney", "ace inhibitor", "diuretic", "egfr"]):
        params.append("Renal function (eGFR) — before & periodically during therapy")
    if any(w in text for w in ["liver", "hepatic", "transaminase"]):
        params.append("Liver function tests — baseline and periodically")
    if any(w in text for w in ["potassium", "electrolyte", "hypokalemia"]):
        params.append("Serum electrolytes (K⁺, Na⁺) — regularly")
    if any(w in text for w in ["blood pressure", "hypertension", "cardiac"]):
        params.append("Blood pressure — at each clinical visit")
    if any(w in text for w in ["glucose", "diabetes", "glycemic", "hba1c"]):
        params.append("Blood glucose & HbA1c — every 3–6 months")
    if any(w in text for w in ["thyroid", "tsh"]):
        params.append("Thyroid function (TSH) — periodically")
    if any(w in text for w in ["lipid", "cholesterol", "statin"]):
        params.append("Lipid panel — at baseline and after dose changes")
    if any(w in text for w in ["vitamin b12", "metformin", "biguanide"]):
        params.append("Vitamin B12 levels — every 2–3 years")
    if any(w in text for w in ["cbc", "blood count", "anemia", "hematolog"]):
        params.append("Complete blood count (CBC) — periodically")
    # Always include signs of serious reaction
    params.append("Signs of hypersensitivity or serious adverse reactions — ongoing")
    return params[:5]  # cap at 5


def _derive_interactions(drug_class: str, warnings: str) -> list[tuple]:
    """Return notable drug interactions relevant to the drug class."""
    text = (drug_class + " " + warnings).lower()
    interactions = []
    if any(w in text for w in ["ace inhibitor", "lisinopril", "ramipril"]):
        interactions += [
            ("NSAIDs:", "May reduce antihypertensive effect"),
            ("Potassium-sparing diuretics:", "Risk of hyperkalemia"),
            ("Lithium:", "Increased lithium toxicity risk"),
        ]
    if any(w in text for w in ["diuretic", "hydrochlorothiazide", "furosemide"]):
        interactions += [
            ("Digoxin:", "Electrolyte imbalance may increase toxicity"),
            ("Alcohol:", "Enhanced hypotensive effect"),
        ]
    if any(w in text for w in ["statin", "atorvastatin", "simvastatin"]):
        interactions += [
            ("CYP3A4 inhibitors:", "Increased statin plasma levels"),
            ("Fibrates:", "Increased myopathy risk"),
        ]
    if any(w in text for w in ["biguanide", "metformin", "antidiabetic"]):
        interactions += [
            ("Iodinated contrast:", "Hold 48 hrs before/after procedure"),
            ("Alcohol:", "Increased lactic acidosis risk"),
        ]
    if any(w in text for w in ["anticoagulant", "warfarin", "blood thinner"]):
        interactions += [
            ("NSAIDs:", "Increased bleeding risk"),
            ("CYP2C9 inhibitors:", "Increased anticoagulant effect"),
        ]
    # Generic fallbacks
    if not interactions:
        interactions = [
            ("CYP enzyme substrates:", "Check for metabolic interactions"),
            ("Protein-bound drugs:", "Potential displacement interactions"),
            ("Renal-cleared drugs:", "Monitor if renal function changes"),
        ]
    return list(dict.fromkeys(interactions))[:4]


def _derive_clinical_notes(drug_class: str, indications: str) -> list[str]:
    """Return clinical use notes relevant to the drug."""
    text = (drug_class + " " + indications).lower()
    notes = []
    if any(w in text for w in ["ace inhibitor", "lisinopril", "hypertension", "cardiac"]):
        notes += [
            "Monitor blood pressure at each visit and after dose changes.",
            "Counsel patients on signs of angioedema (swelling of face/throat).",
            "Avoid use in pregnancy — teratogenic risk.",
        ]
    if any(w in text for w in ["diuretic", "hydrochlorothiazide"]):
        notes += ["Monitor serum electrolytes and renal function regularly."]
    if any(w in text for w in ["statin", "cholesterol", "lipid"]):
        notes += [
            "Advise patients to report unexplained muscle pain or weakness.",
            "Obtain lipid panel before and during therapy.",
        ]
    if any(w in text for w in ["diabetes", "glucose", "metformin", "biguanide"]):
        notes += [
            "Monitor renal function before and during therapy.",
            "Hold therapy before iodinated contrast procedures.",
        ]
    if any(w in text for w in ["antibiotic", "infection", "antimicrobial"]):
        notes += [
            "Complete full course of therapy even if symptoms improve.",
            "Monitor for signs of superinfection or resistance.",
        ]
    # Generic always-applicable notes
    notes += ["Counsel patients to report any new or worsening symptoms promptly."]
    return list(dict.fromkeys(notes))[:5]


def _derive_patient_population(indications: str, contraindications: str) -> list[tuple]:
    """Return patient population notes."""
    text = (indications + " " + contraindications).lower()
    rows = []
    if "pediatric" in text or "children" in text:
        rows.append(("Pediatric:", "See prescribing information"))
    else:
        rows.append(("Pediatric:", "Safety not established — consult PI"))
    rows.append(("Adults:", "18 years and older"))
    rows.append(("Geriatric:", "Use with caution; monitor closely"))
    if "pregnancy" in text or "pregnant" in text:
        rows.append(("Pregnancy:", "Contraindicated — see PI"))
    else:
        rows.append(("Pregnancy:", "Consult physician before use"))
    return rows


def _derive_dosage_summary(dosage: str, drug_name: str) -> list[tuple]:
    """Extract key dosage facts or return drug-appropriate placeholders."""
    text = dosage.lower()
    rows = []
    # Try to extract mg amounts mentioned
    amounts = re.findall(r"(\d+(?:\.\d+)?\s*mg(?:\s*/\s*\d+\s*mg)?)", dosage)
    if amounts:
        rows.append(("Starting dose:", amounts[0]))
    if len(amounts) > 1:
        rows.append(("Max dose:", amounts[-1] + " per day"))
    # Frequency
    if "once daily" in text or "once a day" in text:
        rows.append(("Frequency:", "Once daily"))
    elif "twice daily" in text or "twice a day" in text or "bid" in text:
        rows.append(("Frequency:", "Twice daily"))
    elif "three times" in text or "tid" in text:
        rows.append(("Frequency:", "Three times daily"))
    # Administration
    if "with meal" in text or "with food" in text:
        rows.append(("Administration:", "Take with meals"))
    elif "without food" in text or "empty stomach" in text:
        rows.append(("Administration:", "Take on empty stomach"))
    else:
        rows.append(("Administration:", "As directed by physician"))
    # Titration
    if "titrat" in text or "increase" in text:
        rows.append(("Titration:", "Gradual dose escalation recommended"))
    if not rows:
        rows = [
            ("Dosing:", "Per prescribing information"),
            ("Route:", "Oral"),
            ("Administration:", "As directed by physician"),
        ]
    return rows[:5]


def _derive_moa(drug_class: str, description: str) -> list[str]:
    """Return mechanism of action bullets relevant to the drug class."""
    text = (drug_class + " " + description).lower()
    moa = []
    if any(w in text for w in ["ace inhibitor", "angiotensin converting"]):
        moa = [
            "Inhibits angiotensin-converting enzyme (ACE), reducing angiotensin II formation.",
            "Decreases vasoconstriction and aldosterone secretion.",
            "Lowers peripheral vascular resistance and blood pressure.",
            "Reduces cardiac preload and afterload.",
        ]
    elif any(w in text for w in ["statin", "hmg-coa", "reductase inhibitor"]):
        moa = [
            "Inhibits HMG-CoA reductase, blocking hepatic cholesterol synthesis.",
            "Upregulates LDL receptors, increasing LDL clearance from blood.",
            "Reduces circulating LDL-C, total cholesterol, and triglycerides.",
            "May stabilise atherosclerotic plaques.",
        ]
    elif any(w in text for w in ["biguanide", "metformin"]):
        moa = [
            "Decreases hepatic glucose production (gluconeogenesis).",
            "Reduces intestinal glucose absorption.",
            "Improves peripheral insulin sensitivity.",
            "Does not stimulate insulin secretion — low hypoglycemia risk.",
        ]
    elif any(w in text for w in ["calcium channel", "amlodipine", "dihydropyridine"]):
        moa = [
            "Blocks L-type voltage-gated calcium channels in vascular smooth muscle.",
            "Reduces intracellular calcium, causing vasodilation.",
            "Lowers peripheral vascular resistance and blood pressure.",
            "Minimal negative inotropic effect at therapeutic doses.",
        ]
    elif any(w in text for w in ["beta block", "atenolol", "metoprolol"]):
        moa = [
            "Selectively blocks beta-1 adrenergic receptors in the heart.",
            "Reduces heart rate, myocardial contractility, and cardiac output.",
            "Lowers blood pressure and myocardial oxygen demand.",
            "Suppresses renin release from the kidney.",
        ]
    elif any(w in text for w in ["diuretic", "hydrochlorothiazide", "thiazide"]):
        moa = [
            "Inhibits sodium-chloride co-transporter in the distal convoluted tubule.",
            "Increases urinary excretion of sodium, chloride, and water.",
            "Reduces plasma volume and cardiac output.",
            "Long-term: decreases peripheral vascular resistance.",
        ]
    elif any(w in text for w in ["ssri", "serotonin reuptake", "sertraline", "fluoxetine"]):
        moa = [
            "Selectively inhibits presynaptic serotonin (5-HT) reuptake.",
            "Increases synaptic serotonin concentration.",
            "Minimal effect on norepinephrine or dopamine reuptake.",
            "Does not bind significantly to histaminergic or muscarinic receptors.",
        ]
    elif any(w in text for w in ["proton pump", "omeprazole", "ppi"]):
        moa = [
            "Irreversibly inhibits H⁺/K⁺-ATPase (proton pump) in gastric parietal cells.",
            "Suppresses both basal and stimulated gastric acid secretion.",
            "Provides prolonged acid suppression beyond plasma half-life.",
            "Effective regardless of the stimulus for acid secretion.",
        ]
    else:
        # Generic fallback using description keywords
        moa = [
            f"Acts on specific receptors/enzymes relevant to {drug_class.lower() or 'its therapeutic target'}.",
            "Modulates physiological pathways to achieve therapeutic effect.",
            "Refer to full prescribing information for detailed pharmacology.",
        ]
    return moa


# ── Public API ─────────────────────────────────────────────────────────────────

def fetch_drug_data(drug_name: str) -> dict:
    drug_name = drug_name.strip()
    label     = _fetch_openfda(drug_name)

    if label is None:
        return {"error": f"No FDA label data found for '{drug_name}'."}

    openfda = label.get("openfda", {})

    generic_name = _clean(", ".join(openfda.get("generic_name", [])))
    brand_names  = list(dict.fromkeys(_clean(b) for b in openfda.get("brand_name", [])))
    manufacturer = _clean(", ".join(openfda.get("manufacturer_name", [])))

    drug_class = ""
    rxcui = _get_rxcui(drug_name)
    if rxcui:
        drug_class = _get_drug_class(rxcui)
        if not brand_names:
            brand_names = _get_brand_names(rxcui)

    description       = _smart_truncate(_first(label, "description", "clinical_pharmacology", fallback="No description available."), 550)
    indications       = _smart_truncate(_first(label, "indications_and_usage", fallback="Indications not listed."), 500)
    dosage            = _smart_truncate(_first(label, "dosage_and_administration", fallback="Dosage information not available."), 500)
    contraindications = _smart_truncate(_first(label, "contraindications", fallback="No contraindications listed."), 400)
    warnings_raw      = _list_field(label, "warnings_and_cautions", "warnings", "boxed_warning")
    warnings          = _smart_truncate(" ".join(warnings_raw) if warnings_raw else "No specific warnings listed.", 450)
    adverse_reactions = _smart_truncate(_first(label, "adverse_reactions", fallback="Adverse reactions not listed."), 400)
    how_supplied      = _smart_truncate(_first(label, "how_supplied", fallback="Supply information not available."), 300)
    storage           = _smart_truncate(_first(label, "storage_and_handling", fallback="Store as per manufacturer guidelines."), 250)

    # ── Derived / drug-specific filler content ─────────────────────────────────
    monitoring       = _derive_monitoring(drug_class, indications, warnings)
    interactions     = _derive_interactions(drug_class, warnings)
    clinical_notes   = _derive_clinical_notes(drug_class, indications)
    patient_pop      = _derive_patient_population(indications, contraindications)
    dosage_summary   = _derive_dosage_summary(dosage, drug_name)
    moa              = _derive_moa(drug_class, description)

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
        # derived
        "monitoring"        : monitoring,
        "interactions"      : interactions,
        "clinical_notes"    : clinical_notes,
        "patient_pop"       : patient_pop,
        "dosage_summary"    : dosage_summary,
        "moa"               : moa,
    }


if __name__ == "__main__":
    import json
    data = fetch_drug_data("lisinopril")
    print(json.dumps(data, indent=2))
