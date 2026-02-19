"""
Groq Full Analysis Module.
Uses Groq API with pharmacogenomic_rules.csv as knowledge context
to perform complete pharmacogenomic risk analysis of VCF variants.
Groq both determines risk AND generates the explanation in one call.
"""
import os
import json
import pandas as pd
from typing import List, Dict
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL    = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# ── Load CSV knowledge base once at import time ───────────────────────────────
_CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'pharmacogenomic_rules.csv')

def _load_csv_rules(drug: str) -> str:
    """Return CSV rows for this drug as a compact text block for the prompt."""
    try:
        df = pd.read_csv(_CSV_PATH)
        drug_rows = df[df['drug'].str.upper() == drug.upper()]
        if drug_rows.empty:
            return f"No rules found for {drug} in the knowledge base."
        lines = ["gene,diplotype,phenotype,risk_label,severity,cpic_recommendation,alternative_drugs,evidence_level"]
        for _, row in drug_rows.iterrows():
            lines.append(",".join(str(row[c]) for c in
                ['gene','diplotype','phenotype','risk_label','severity',
                 'cpic_recommendation','alternative_drugs','evidence_level']))
        return "\n".join(lines)
    except Exception as e:
        return f"CSV load error: {e}"


# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """You are a senior clinical pharmacogenomics expert and AI system.
You will receive:
1. A patient's VCF variants (gene, star allele, rsID, genotype)
2. CPIC pharmacogenomic rules from our knowledge base CSV

Your task is to perform a COMPLETE pharmacogenomic risk analysis and return ONLY a valid JSON object.

Rules for your analysis:
- Match the patient's variants (gene + star allele + genotype) against the CSV rules
- Genotype 0/0 = reference/reference (likely *1/*1 = normal metabolizer)
- Genotype 0/1 = heterozygous (one risk allele)
- Genotype 1/1 = homozygous (two risk alleles, strongest effect)
- Determine the most appropriate risk_label: Safe | Adjust Dosage | Toxic | Ineffective | Unknown
- Use the CSV cpic_recommendation as the basis for dose_adjustment
- Confidence score: 0.95 for exact CSV match, 0.75 for inferred, 0.50 for no match

Return ONLY this JSON structure, no other text:
{
  "risk_assessment": {
    "risk_label": "Safe|Adjust Dosage|Toxic|Ineffective|Unknown",
    "confidence_score": 0.0,
    "severity": "none|low|moderate|high|critical"
  },
  "pharmacogenomic_profile": {
    "primary_gene": "GENE_SYMBOL",
    "diplotype": "*X/*Y",
    "phenotype": "PM|IM|NM|RM|URM|Unknown",
    "detected_variants": [{"rsid": "rsXXXX", "chromosome": "chrX", "position": 0}]
  },
  "clinical_recommendation": {
    "cpic_guideline": "CPIC Guideline for DRUG and GENE",
    "dose_adjustment": "specific recommendation text",
    "alternative_drugs": ["drug1", "drug2"]
  },
  "llm_generated_explanation": {
    "summary": "Patient-friendly 2-3 sentence explanation without medical jargon.",
    "mechanism": "Detailed 3-4 sentence clinical/biochemical mechanism for healthcare providers.",
    "variant_citations": ["rsXXXX"]
  },
  "quality_metrics": {
    "vcf_parsing_success": true,
    "guideline_version": "CPIC v2.0",
    "llm_confidence": 0.0
  }
}"""


def groq_full_analysis(
    drug: str,
    variants: List[Dict],
    patient_id: str,
    timestamp: str
) -> Dict:
    """
    Use Groq to perform complete pharmacogenomic analysis.
    CSV rules are injected as knowledge context in the prompt.
    Falls back to rule-engine if Groq is unavailable.
    """
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("gsk_your"):
        print(f"[GroqAnalyzer] No API key — falling back to rule engine for {drug}")
        return _fallback_to_rule_engine(drug, variants, patient_id, timestamp)

    # Build the user prompt with CSV context + patient variants
    csv_context = _load_csv_rules(drug)

    # Filter variants relevant to this drug's gene
    gene_map = {
        "CODEINE": "CYP2D6", "WARFARIN": "CYP2C9", "CLOPIDOGREL": "CYP2C19",
        "SIMVASTATIN": "SLCO1B1", "AZATHIOPRINE": "TPMT", "FLUOROURACIL": "DPYD"
    }
    primary_gene = gene_map.get(drug.upper(), "")
    relevant_variants = [v for v in variants if v.get("gene", "").upper() == primary_gene.upper()]
    all_variants_str = json.dumps(variants, indent=2)
    relevant_str = json.dumps(relevant_variants, indent=2) if relevant_variants else "No variants detected for this gene."

    user_prompt = f"""DRUG TO ANALYZE: {drug}
PATIENT ID: {patient_id}

=== CPIC KNOWLEDGE BASE RULES FOR {drug} ===
{csv_context}

=== ALL PATIENT VCF VARIANTS ===
{all_variants_str}

=== RELEVANT VARIANTS FOR {drug} ({primary_gene}) ===
{relevant_str}

Analyze these variants against the CPIC rules above and return the complete JSON assessment for {drug}."""

    try:
        client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt}
            ],
            temperature=0.1,  # Very low — we want deterministic, accurate results
            max_tokens=1200
        )

        raw = (response.choices[0].message.content or "").strip()

        # Strip markdown code fences Groq sometimes wraps output in
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        parsed = json.loads(raw)
        print(f"[GroqAnalyzer] ✅ Groq analysis complete for {drug} via {GROQ_MODEL}")
        return parsed

    except json.JSONDecodeError as e:
        print(f"[GroqAnalyzer] JSON parse error for {drug}: {e}\nRaw: {raw[:300]}")
        return _fallback_to_rule_engine(drug, variants, patient_id, timestamp)
    except Exception as e:
        print(f"[GroqAnalyzer] Groq call failed for {drug}: {e}")
        return _fallback_to_rule_engine(drug, variants, patient_id, timestamp)


def _fallback_to_rule_engine(drug: str, variants: List[Dict], patient_id: str, timestamp: str) -> Dict:
    """Fallback: use the deterministic CSV rule engine when Groq is unavailable."""
    try:
        from vcf_parser import ParsedVariant, VCFParseResult
        from risk_engine import RiskEngine
        from llm_service import generate_explanation

        engine = RiskEngine()
        parsed_variants = []
        for v in variants:
            pv = ParsedVariant(
                chromosome=v.get("chromosome", "chr1"),
                position=int(v.get("position", 0)),
                ref="N", alt="A",
                genotype=v.get("genotype", "0/0"),
                gene=v.get("gene", ""),
                star_allele=v.get("star_allele", ""),
                rsid=v.get("rsid", "")
            )
            parsed_variants.append(pv)

        result = VCFParseResult(patient_id=patient_id)
        result.variants = parsed_variants
        result.gene_variants = {}
        for pv in parsed_variants:
            if pv.gene:
                result.gene_variants.setdefault(pv.gene.upper(), []).append(pv)
        result.success = True

        assessment = engine.assess(result, drug.upper())
        explanation = generate_explanation(
            gene=assessment.get("primary_gene", ""),
            diplotype=assessment.get("diplotype", "unknown"),
            phenotype=assessment.get("phenotype", "Unknown"),
            drug=drug,
            risk_label=assessment.get("risk_label", "Unknown"),
            severity=assessment.get("severity", "moderate"),
            detected_variants=assessment.get("detected_variants", []),
            cpic_recommendation=assessment.get("cpic_recommendation", "")
        )

        return {
            "risk_assessment": {
                "risk_label": assessment.get("risk_label", "Unknown"),
                "confidence_score": assessment.get("confidence_score", 0.5),
                "severity": assessment.get("severity", "moderate")
            },
            "pharmacogenomic_profile": {
                "primary_gene": assessment.get("primary_gene", ""),
                "diplotype": assessment.get("diplotype", "unknown"),
                "phenotype": assessment.get("phenotype", "Unknown"),
                "detected_variants": assessment.get("detected_variants", [])
            },
            "clinical_recommendation": {
                "cpic_guideline": f"CPIC Guideline for {drug} and {assessment.get('primary_gene','')}",
                "dose_adjustment": assessment.get("cpic_recommendation", ""),
                "alternative_drugs": assessment.get("alternative_drugs", [])
            },
            "llm_generated_explanation": {
                "summary": explanation.get("summary", ""),
                "mechanism": explanation.get("mechanism", ""),
                "variant_citations": explanation.get("variant_citations", [])
            },
            "quality_metrics": {
                "vcf_parsing_success": True,
                "guideline_version": "CPIC v2.0",
                "llm_confidence": explanation.get("llm_confidence", 0.75)
            }
        }
    except Exception as e:
        print(f"[GroqAnalyzer] Fallback rule engine also failed: {e}")
        return {"error": "analysis_failed", "detail": str(e)}
