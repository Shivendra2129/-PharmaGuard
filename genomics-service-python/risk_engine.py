"""
Deterministic CPIC-aligned risk engine.
Loads pharmacogenomic_rules.csv and applies rule-based logic.
LLM does NOT make risk decisions - only explains them.
"""
import os
import pandas as pd
from typing import Dict, List, Optional, Tuple
from vcf_parser import ParsedVariant, VCFParseResult, extract_diplotype_for_gene

# Path to knowledge base
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
CSV_PATH = os.path.join(DATA_DIR, 'pharmacogenomic_rules.csv')

SUPPORTED_DRUGS = {
    "CODEINE", "WARFARIN", "CLOPIDOGREL",
    "SIMVASTATIN", "AZATHIOPRINE", "FLUOROURACIL"
}

DRUG_GENE_MAP = {
    "CODEINE": "CYP2D6",
    "WARFARIN": "CYP2C9",
    "CLOPIDOGREL": "CYP2C19",
    "SIMVASTATIN": "SLCO1B1",
    "AZATHIOPRINE": "TPMT",
    "FLUOROURACIL": "DPYD"
}

PHENOTYPE_CONFIDENCE = {
    "PM":  0.95,
    "IM":  0.82,
    "NM":  0.90,
    "RM":  0.78,
    "URM": 0.92,
    "Unknown": 0.40
}

RISK_CONFIDENCE_MAP = {
    "Toxic":         0.93,
    "Ineffective":   0.88,
    "Adjust Dosage": 0.80,
    "Safe":          0.92,
    "Unknown":       0.40
}


class RiskEngine:
    """Loads CSV rules and performs deterministic pharmacogenomic risk assessment."""
    
    def __init__(self, csv_path: str = CSV_PATH):
        self.csv_path = csv_path
        self._rules_df = None
        self._load_rules()
    
    def _load_rules(self):
        """Load and validate the CSV knowledge base."""
        try:
            self._rules_df = pd.read_csv(self.csv_path)
            required_cols = [
                'gene', 'drug', 'diplotype', 'phenotype',
                'risk_label', 'severity', 'cpic_recommendation',
                'alternative_drugs', 'evidence_level'
            ]
            missing = [c for c in required_cols if c not in self._rules_df.columns]
            if missing:
                raise ValueError(f"CSV missing columns: {missing}")
            
            # Normalize for case-insensitive matching
            self._rules_df['drug_upper'] = self._rules_df['drug'].str.upper()
            self._rules_df['gene_upper'] = self._rules_df['gene'].str.upper()
            print(f"[RiskEngine] Loaded {len(self._rules_df)} rules from {self.csv_path}")
        except Exception as e:
            print(f"[RiskEngine] WARNING: Could not load CSV: {e}")
            self._rules_df = pd.DataFrame()
    
    def _infer_phenotype(self, gene: str, diplotype: str, gene_variants: List[ParsedVariant]) -> str:
        """
        Infer phenotype from diplotype and variant genotypes.
        Priority: exact diplotype match in CSV > genotype-based inference.
        """
        if self._rules_df.empty:
            return "Unknown"
        
        gene_upper = gene.upper()
        
        # Direct lookup in CSV by diplotype
        mask = (
            (self._rules_df['gene_upper'] == gene_upper) &
            (self._rules_df['diplotype'] == diplotype)
        )
        matches = self._rules_df[mask]
        if not matches.empty:
            return str(matches.iloc[0]['phenotype'])
        
        # Pattern-based phenotype inference from alleles
        return self._infer_phenotype_from_alleles(gene, gene_variants)
    
    def _infer_phenotype_from_alleles(self, gene: str, variants: List[ParsedVariant]) -> str:
        """Infer metabolizer phenotype from observed alleles and genotypes."""
        if not variants:
            return "Unknown"
        
        # Collect unique star alleles and their genotypes
        hom_alt = [v for v in variants if v.genotype in ("1/1", "1|1")]
        het = [v for v in variants if v.genotype in ("0/1", "1/0", "0|1", "1|0")]
        
        # No-function alleles (loss-of-function)
        nof_stars = {"*3", "*4", "*5", "*6", "*7", "*8", "*11", "*12", "*13", "*14",
                      "*2A", "*2", "*13", "*3A", "*3B", "*3C"}
        
        all_stars = set(v.star_allele for v in variants)
        has_nof = bool(all_stars & nof_stars)
        
        # Homozygous LOF variant → PM
        if hom_alt and has_nof:
            return "PM"
        
        # Heterozygous LOF → IM
        if het and has_nof:
            return "IM"
        
        # DPYD special case: rs3918290 het → IM
        if gene == "DPYD":
            dpyd_toxic_rs = {"rs3918290", "rs55886062", "rs67376798"}
            for v in variants:
                if v.rsid in dpyd_toxic_rs and v.genotype in ("0/1", "1/0", "0|1", "1|0"):
                    return "IM"
                if v.rsid in dpyd_toxic_rs and v.genotype in ("1/1", "1|1"):
                    return "PM"
        
        # URM detection (xN duplication - handled via star allele name containing xN)
        for v in variants:
            if "xN" in v.star_allele or "x2" in v.star_allele:
                return "URM"
        
        # All ref → NM
        all_ref = [v for v in variants if v.genotype in ("0/0", "0|0")]
        if len(all_ref) == len(variants):
            return "NM"
        
        return "NM"
    
    def _lookup_risk(self, gene: str, drug: str, diplotype: str, phenotype: str,
                     variants: List[ParsedVariant]) -> Dict:
        """
        Lookup risk using deterministic rules.
        Priority: diplotype exact > phenotype > rsID special cases.
        """
        if self._rules_df.empty:
            return self._fallback_rule(gene, drug, diplotype, phenotype)
        
        gene_upper = gene.upper()
        drug_upper = drug.upper()
        
        # 1. Try exact diplotype match
        mask = (
            (self._rules_df['gene_upper'] == gene_upper) &
            (self._rules_df['drug_upper'] == drug_upper) &
            (self._rules_df['diplotype'] == diplotype)
        )
        matches = self._rules_df[mask]
        if not matches.empty:
            row = matches.iloc[0]
            return self._row_to_risk(row, "A")
        
        # 2. Try phenotype match
        mask2 = (
            (self._rules_df['gene_upper'] == gene_upper) &
            (self._rules_df['drug_upper'] == drug_upper) &
            (self._rules_df['phenotype'] == phenotype)
        )
        matches2 = self._rules_df[mask2]
        if not matches2.empty:
            row = matches2.iloc[0]
            return self._row_to_risk(row, "B")
        
        # 3. DPYD rsID special case: check if toxic rsID present
        if gene == "DPYD" and drug_upper == "FLUOROURACIL":
            dpyd_toxic_rs = {"rs3918290", "rs55886062", "rs55939643"}
            for v in variants:
                if v.rsid in dpyd_toxic_rs and v.genotype not in ("0/0", "0|0"):
                    mask3 = (
                        (self._rules_df['gene_upper'] == "DPYD") &
                        (self._rules_df['drug_upper'] == "FLUOROURACIL") &
                        (self._rules_df['phenotype'].isin(["PM", "IM"]))
                    )
                    m3 = self._rules_df[mask3]
                    if not m3.empty:
                        pheno = "PM" if v.genotype in ("1/1", "1|1") else "IM"
                        row_filter = m3[m3['phenotype'] == pheno]
                        if not row_filter.empty:
                            return self._row_to_risk(row_filter.iloc[0], "A")
        
        # 4. Unknown fallback
        mask4 = (
            (self._rules_df['gene_upper'] == gene_upper) &
            (self._rules_df['drug_upper'] == drug_upper) &
            (self._rules_df['phenotype'] == "Unknown")
        )
        matches4 = self._rules_df[mask4]
        if not matches4.empty:
            return self._row_to_risk(matches4.iloc[0], "C")
        
        return self._fallback_rule(gene, drug, diplotype, phenotype)
    
    def _row_to_risk(self, row, evidence_override: str = None) -> Dict:
        """Convert a CSV row to risk dictionary."""
        alts_raw = str(row.get('alternative_drugs', 'none'))
        if alts_raw.lower() in ('none', 'nan', ''):
            alternatives = []
        else:
            alternatives = [a.strip() for a in alts_raw.split('|') if a.strip() and a.strip().lower() != 'none']
        
        return {
            "risk_label": str(row['risk_label']),
            "severity": str(row['severity']),
            "cpic_recommendation": str(row['cpic_recommendation']),
            "alternative_drugs": alternatives,
            "phenotype": str(row['phenotype']),
            "evidence_level": str(evidence_override or row.get('evidence_level', 'B'))
        }
    
    def _fallback_rule(self, gene: str, drug: str, diplotype: str, phenotype: str) -> Dict:
        """Default fallback when no rule is matched."""
        return {
            "risk_label": "Unknown",
            "severity": "none",
            "cpic_recommendation": f"No CPIC guideline data available for {gene}/{drug} combination.",
            "alternative_drugs": [],
            "phenotype": phenotype,
            "evidence_level": "D"
        }
    
    def assess(self, parse_result: VCFParseResult, drug: str) -> Dict:
        """
        Perform full pharmacogenomic risk assessment for one drug.
        Returns structured dict matching the PharmaGuardResponse schema.
        """
        drug_upper = drug.upper().strip()
        
        if drug_upper not in SUPPORTED_DRUGS:
            return {
                "error": "unsupported_drug",
                "detail": f"Drug '{drug}' is not supported. Supported: {', '.join(sorted(SUPPORTED_DRUGS))}",
                "drug": drug
            }
        
        primary_gene = DRUG_GENE_MAP[drug_upper]
        gene_variants = parse_result.gene_variants.get(primary_gene, [])
        
        # Extract diplotype
        diplotype, alleles = extract_diplotype_for_gene(gene_variants)
        
        # Infer phenotype
        phenotype = self._infer_phenotype(primary_gene, diplotype, gene_variants)
        
        # Lookup risk from CSV rules
        risk_data = self._lookup_risk(primary_gene, drug_upper, diplotype, phenotype, gene_variants)
        
        # Build detected variants list
        detected_variants = []
        seen_rsids = set()
        for v in gene_variants:
            if v.rsid not in seen_rsids:
                detected_variants.append({
                    "rsid": v.rsid,
                    "chromosome": v.chromosome,
                    "position": v.position
                })
                seen_rsids.add(v.rsid)
        
        # Compute confidence
        risk_label = risk_data.get("risk_label", "Unknown")
        confidence = RISK_CONFIDENCE_MAP.get(risk_label, 0.5)
        if not parse_result.success or not gene_variants:
            confidence *= 0.5
        
        return {
            "primary_gene": primary_gene,
            "diplotype": diplotype,
            "phenotype": risk_data.get("phenotype", phenotype),
            "risk_label": risk_label,
            "severity": risk_data.get("severity", "none"),
            "confidence_score": round(confidence, 2),
            "cpic_recommendation": risk_data.get("cpic_recommendation", ""),
            "alternative_drugs": risk_data.get("alternative_drugs", []),
            "detected_variants": detected_variants,
            "evidence_level": risk_data.get("evidence_level", "B"),
            "vcf_parsing_success": parse_result.success and len(parse_result.variants) > 0
        }
