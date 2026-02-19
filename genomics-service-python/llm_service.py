"""
LLM Explanation Service.
Uses OpenAI API to generate clinical explanations only.
Risk is pre-determined by the rule engine; LLM ONLY explains.
"""
import os
import json
from typing import Dict, List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

CLINICAL_SYSTEM_PROMPT = """You are a senior clinical pharmacogenomics expert with deep knowledge of CPIC guidelines, pharmacokinetics, and precision medicine. Your role is to EXPLAIN a pre-determined drug risk assessment to clinicians and patients. You must:
1. NOT modify or invent genotype, phenotype, or risk level — these are given to you
2. Explain the biological mechanism behind the risk accurately
3. Cite rsIDs when describing variant effects
4. Reference relevant CPIC guideline sections
5. Write a patient-friendly summary (simple language, no jargon in summary)
6. Write a detailed mechanism explanation for clinician audience

Always respond in valid JSON only."""


def build_explanation_prompt(gene: str, diplotype: str, phenotype: str, drug: str,
                              risk_label: str, severity: str, detected_variants: List[Dict],
                              cpic_recommendation: str) -> str:
    """Build the structured prompt for LLM explanation."""
    variant_str = "\n".join(
        f"  - {v.get('rsid', 'unknown')} at {v.get('chromosome', '')}:{v.get('position', '')}"
        for v in detected_variants
    ) or "  - No specific variants detected (inferred from phenotype)"
    
    rsids = [v.get('rsid', '') for v in detected_variants if v.get('rsid')]
    rsids_str = ", ".join(rsids) if rsids else "none"
    
    return f"""A pharmacogenomics risk assessment has already been completed using deterministic CPIC rules. Your task is to explain this assessment.

PATIENT GENOMIC PROFILE:
- Primary Gene: {gene}
- Diplotype (Star Allele): {diplotype}
- Metabolizer Phenotype: {phenotype}
- Drug Prescribed: {drug}
- Pre-determined Risk Level: {risk_label} (Severity: {severity})
- CPIC Clinical Recommendation: {cpic_recommendation}
- Detected Variants:
{variant_str}

INSTRUCTIONS:
1. Explain WHY this gene/diplotype causes the {risk_label} risk for {drug}
2. Describe the enzyme/transporter mechanism affected by the variant(s)
3. Explain what {phenotype} phenotype means clinically for this drug
4. Cite these rsIDs explicitly in your explanation: {rsids_str}
5. Align your explanation with CPIC guidelines

Return ONLY a JSON object with exactly these three fields:
{{
  "summary": "Patient-friendly explanation in 2-3 sentences. No medical jargon.",
  "mechanism": "Detailed clinical/biochemical mechanism for healthcare providers. 3-4 sentences. Include enzyme kinetics, pathway, and clinical implications.",
  "variant_citations": ["{rsids_str.replace(', ', '", "') if rsids else ""}"]
}}

Do NOT include any text outside this JSON object."""


def generate_explanation(
    gene: str,
    diplotype: str,
    phenotype: str,
    drug: str,
    risk_label: str,
    severity: str,
    detected_variants: List[Dict],
    cpic_recommendation: str
) -> Dict[str, object]:
    """
    Generate LLM explanation for a pre-determined pharmacogenomic risk.
    Returns dict with summary, mechanism, variant_citations.
    """
    if not OPENAI_API_KEY or OPENAI_API_KEY.startswith("sk-your"):
        return _mock_explanation(gene, diplotype, phenotype, drug, risk_label, detected_variants)
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        prompt = build_explanation_prompt(
            gene, diplotype, phenotype, drug, risk_label,
            severity, detected_variants, cpic_recommendation
        )
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": CLINICAL_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,  # Low temperature for factual clinical content
            max_tokens=600,
            response_format={"type": "json_object"}
        )
        
        raw = response.choices[0].message.content
        parsed = json.loads(raw)
        
        # Validate required fields
        summary = str(parsed.get("summary", ""))
        mechanism = str(parsed.get("mechanism", ""))
        citations_raw = parsed.get("variant_citations", [])
        
        if isinstance(citations_raw, str):
            citations = [s.strip() for s in citations_raw.split(',') if s.strip()]
        elif isinstance(citations_raw, list):
            citations = [str(c) for c in citations_raw]
        else:
            citations = []
        
        return {
            "summary": summary,
            "mechanism": mechanism,
            "variant_citations": citations,
            "llm_confidence": 0.85 if summary and mechanism else 0.40
        }
    
    except Exception as e:
        print(f"[LLMService] OpenAI call failed: {e}")
        return _mock_explanation(gene, diplotype, phenotype, drug, risk_label, detected_variants)


def _mock_explanation(gene: str, diplotype: str, phenotype: str, drug: str,
                       risk_label: str, detected_variants: List[Dict]) -> Dict:
    """
    Fallback explanation used when OpenAI API key is not configured.
    Provides deterministic, medically accurate template-based explanations.
    """
    rsids = [v.get('rsid', '') for v in detected_variants if v.get('rsid')]
    rsids_str = ", ".join(rsids) if rsids else "no specific variants"
    
    phenotype_descriptions = {
        "PM": "poor metabolizer",
        "IM": "intermediate metabolizer",
        "NM": "normal metabolizer",
        "RM": "rapid metabolizer",
        "URM": "ultrarapid metabolizer",
        "Unknown": "metabolizer status unknown"
    }
    ph_desc = phenotype_descriptions.get(phenotype, phenotype.lower())
    
    # Gene-specific mechanism database
    mechanisms = {
        "CYP2D6": {
            "CODEINE": f"CYP2D6 encodes a hepatic cytochrome P450 enzyme responsible for converting codeine to morphine (O-demethylation). The {diplotype} diplotype results in a {ph_desc} phenotype. In poor metabolizers, this conversion is virtually absent, making codeine ineffective. In ultrarapid metabolizers, excess morphine accumulates rapidly, causing respiratory depression and opioid toxicity. Variants {rsids_str} disrupt CYP2D6 enzyme function, altering codeine bioactivation. CPIC recommends avoiding codeine in PM and URM genotypes.",
        },
        "CYP2C19": {
            "CLOPIDOGREL": f"CYP2C19 is the primary enzyme responsible for converting clopidogrel (a prodrug) to its active thiol metabolite that inhibits platelet P2Y12 receptors. The {diplotype} diplotype confers {ph_desc} status. In poor metabolizers, insufficient active metabolite is generated, leading to inadequate platelet inhibition and increased cardiovascular event risk. Variants {rsids_str} reduce CYP2C19 enzyme activity. CPIC strongly recommends alternative antiplatelet agents (prasugrel or ticagrelor) for PM/IM phenotypes.",
        },
        "CYP2C9": {
            "WARFARIN": f"CYP2C9 metabolizes S-warfarin, the more potent enantiomer of warfarin. The {diplotype} genotype produces a {ph_desc} phenotype with reduced enzyme activity, causing warfarin accumulation and elevated bleeding risk. Reduced clearance of S-warfarin by variants {rsids_str} means standard doses result in supratherapeutic anticoagulation. CPIC recommends dose reduction proportional to CYP2C9 activity loss and more frequent INR monitoring during dose initiation.",
        },
        "SLCO1B1": {
            "SIMVASTATIN": f"SLCO1B1 encodes OATP1B1, a hepatic uptake transporter essential for moving simvastatin acid into hepatocytes. The {diplotype} genotype impairs OATP1B1 function, reducing hepatic uptake and increasing systemic simvastatin plasma concentrations. Elevated muscle exposure leads to statin-associated myopathy (SAM) and rhabdomyolysis risk. Variants {rsids_str} reduce transporter activity. CPIC recommends lower simvastatin doses (≤20mg) or switching to alternative statins with lower OATP1B1 dependence.",
        },
        "TPMT": {
            "AZATHIOPRINE": f"TPMT (thiopurine methyltransferase) inactivates thiopurine drugs by methylation. Azathioprine is converted to 6-mercaptopurine (6-MP) and then to toxic thioguanine nucleotides (TGN). In {ph_desc} patients with {diplotype}, reduced TPMT activity causes TGN accumulation in blood cells, leading to severe hematopoietic toxicity (myelosuppression). Variants {rsids_str} reduce or abolish TPMT enzyme activity. CPIC mandates 10-fold dose reduction or alternative immunosuppressant therapy for PM patients.",
        },
        "DPYD": {
            "FLUOROURACIL": f"DPYD (dihydropyrimidine dehydrogenase) is the rate-limiting enzyme in fluorouracil (5-FU) catabolism, responsible for >80% of 5-FU clearance. The {diplotype} diplotype causes {ph_desc} status with markedly reduced DPD enzyme activity. Impaired 5-FU catabolism leads to drug accumulation and severe, potentially fatal toxicities including mucositis, neutropenia, and neurotoxicity. Variants {rsids_str} disrupt DPYD enzyme function. CPIC requires 50% dose reduction for heterozygous carriers and contraindication for homozygous DPD-deficient patients.",
        }
    }
    
    summaries = {
        ("CYP2D6", "CODEINE"): f"Your genetic profile shows a {ph_desc} status for the CYP2D6 gene, which affects how your body processes codeine. This means the medication {'may not work for you' if risk_label == 'Ineffective' else 'could cause serious side effects' if risk_label == 'Toxic' else 'should be used with dose adjustment'}. Your doctor should be informed of this genetic finding before prescribing codeine.",
        ("CYP2C19", "CLOPIDOGREL"): f"Your genetics show you are a {ph_desc} for CYP2C19, the gene that activates clopidogrel in your body. {'This blood thinner may not work properly for you, increasing your risk of heart attack or stroke.' if risk_label in ('Ineffective', 'Adjust Dosage') else 'Standard clopidogrel dosing is appropriate for your genetic profile.'} Please discuss alternative medications with your cardiologist.",
        ("CYP2C9", "WARFARIN"): f"Your CYP2C9 genetic status as a {ph_desc} means your body processes warfarin more slowly than average. {'This significantly increases your bleeding risk at standard doses, requiring a dose reduction and closer monitoring.' if risk_label in ('Toxic', 'Adjust Dosage') else 'Standard warfarin dosing is appropriate based on your CYP2C9 genetics alone.'}",
        ("SLCO1B1", "SIMVASTATIN"): f"Your SLCO1B1 gene affects how your liver absorbs simvastatin. As a {ph_desc}, {'you have an elevated risk of muscle damage (myopathy) with standard simvastatin doses. A lower dose or different statin is recommended.' if risk_label in ('Toxic', 'Adjust Dosage') else 'simvastatin at standard doses is appropriate for your SLCO1B1 genetic profile.'}",
        ("TPMT", "AZATHIOPRINE"): f"Your TPMT genetic profile indicates you are a {ph_desc}, meaning your body cannot properly process azathioprine. {'This creates a high risk of serious blood toxicity. Significantly reduced doses or a different medication is essential.' if risk_label in ('Toxic', 'Adjust Dosage') else 'Standard azathioprine dosing is appropriate based on your TPMT genetics.'}",
        ("DPYD", "FLUOROURACIL"): f"Your DPYD gene status as a {ph_desc} means you cannot break down fluorouracil (5-FU) as quickly as most people. {'This puts you at serious risk of life-threatening side effects and requires dose reduction or use of an alternative chemotherapy.' if risk_label in ('Toxic', 'Adjust Dosage') else 'Standard fluorouracil dosing appears appropriate based on your DPYD genetics.'}"
    }
    
    gene_drug_key = (gene.upper().replace("CYP2D6", "CYP2D6"), drug.upper())
    
    mechanism_text = ""
    for g, drug_map in mechanisms.items():
        if g == gene.upper():
            mechanism_text = drug_map.get(drug.upper(), 
                f"The {gene} gene encodes an enzyme involved in {drug} metabolism. The {diplotype} diplotype ({ph_desc}) affects drug processing. Variants {rsids_str} alter enzyme activity. Please consult CPIC guidelines for detailed recommendations.")
            break
    
    if not mechanism_text:
        mechanism_text = f"The {gene} gene ({diplotype}, {ph_desc}) affects {drug} pharmacokinetics. Variants {rsids_str} alter drug metabolism or transport, leading to {risk_label.lower()} risk. Consult CPIC guidelines for complete clinical recommendations."
    
    summary_text = ""
    for (g, d), text in summaries.items():
        if g == gene.upper() and d == drug.upper():
            summary_text = text
            break
    
    if not summary_text:
        summary_text = f"Your {gene} genetic profile ({ph_desc}) affects how your body processes {drug}, resulting in {risk_label.lower()} risk. Please consult your healthcare provider about appropriate medication management."
    
    return {
        "summary": summary_text,
        "mechanism": mechanism_text,
        "variant_citations": rsids,
        "llm_confidence": 0.75
    }
