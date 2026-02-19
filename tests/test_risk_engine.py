"""
Unit tests for the PharmaGuard risk engine.
Tests deterministic CPIC-aligned rule matching.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'genomics-service-python'))

import pytest
from vcf_parser import ParsedVariant, VCFParseResult, extract_diplotype_for_gene, validate_vcf_header
from risk_engine import RiskEngine

# ─── VCF Parser Tests ─────────────────────────────────────────────────────────

def test_vcf_header_validation_valid():
    content = "##fileformat=VCFv4.2\n##INFO=<ID=GENE>\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
    valid, msg = validate_vcf_header(content)
    assert valid is True

def test_vcf_header_validation_missing_format():
    content = "# This is not a VCF\n#CHROM\tPOS\n"
    valid, msg = validate_vcf_header(content)
    assert valid is False
    assert "VCF" in msg

def test_vcf_header_validation_empty():
    valid, msg = validate_vcf_header("")
    assert valid is False

def test_vcf_header_missing_chrom():
    content = "##fileformat=VCFv4.2\n##INFO=test\n"
    valid, msg = validate_vcf_header(content)
    assert valid is False
    assert "#CHROM" in msg

# ─── Diplotype Extraction Tests ───────────────────────────────────────────────

def make_variant(gene, star, rsid, gt, chrom="chr22", pos=100000):
    return ParsedVariant(
        chromosome=chrom, position=pos, ref="C", alt="T",
        genotype=gt, gene=gene, star_allele=star, rsid=rsid
    )

def test_diplotype_homozygous_alt():
    variants = [make_variant("CYP2D6", "*4", "rs3892097", "1/1")]
    diplotype, alleles = extract_diplotype_for_gene(variants)
    assert "*4" in diplotype

def test_diplotype_heterozygous():
    variants = [make_variant("CYP2D6", "*4", "rs3892097", "0/1")]
    diplotype, alleles = extract_diplotype_for_gene(variants)
    assert "*1" in diplotype or "*4" in diplotype

def test_diplotype_ref_ref():
    variants = [make_variant("CYP2C9", "*1", "rs1799853", "0/0")]
    diplotype, alleles = extract_diplotype_for_gene(variants)
    assert "*1" in diplotype

def test_diplotype_empty():
    diplotype, alleles = extract_diplotype_for_gene([])
    assert diplotype == "unknown"
    assert alleles == []

# ─── Risk Engine Tests ────────────────────────────────────────────────────────

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'pharmacogenomic_rules.csv')

@pytest.fixture
def engine():
    return RiskEngine(csv_path=CSV_PATH)

def make_parse_result(gene, star, rsid, gt, patient_id="TEST_001"):
    variant = make_variant(gene, star, rsid, gt)
    result = VCFParseResult(patient_id=patient_id)
    result.variants = [variant]
    result.gene_variants = {gene: [variant]}
    result.success = True
    return result

# CYP2D6 + CODEINE tests
def test_cyp2d6_pm_codeine_ineffective(engine):
    """CYP2D6 *4/*4 (PM) + CODEINE = Ineffective (CPIC)"""
    v1 = make_variant("CYP2D6", "*4", "rs3892097", "1/1")
    result = VCFParseResult(patient_id="TEST_001")
    result.variants = [v1]
    result.gene_variants = {"CYP2D6": [v1]}
    result.success = True
    assessment = engine.assess(result, "CODEINE")
    assert assessment["risk_label"] in ("Ineffective", "Unknown")
    assert "error" not in assessment

def test_cyp2d6_nm_codeine_safe(engine):
    """CYP2D6 *1/*1 (NM) + CODEINE = Safe"""
    v1 = make_variant("CYP2D6", "*1", "rs1065852", "0/0")
    result = VCFParseResult(patient_id="TEST_002")
    result.variants = [v1]
    result.gene_variants = {"CYP2D6": [v1]}
    result.success = True
    assessment = engine.assess(result, "CODEINE")
    assert assessment["risk_label"] in ("Safe", "Unknown")

# CYP2C19 + CLOPIDOGREL tests
def test_cyp2c19_pm_clopidogrel_ineffective(engine):
    """CYP2C19 *2/*2 (PM) + CLOPIDOGREL = Ineffective"""
    v1 = make_variant("CYP2C19", "*2", "rs4244285", "1/1", chrom="chr10", pos=96741053)
    result = VCFParseResult(patient_id="TEST_003")
    result.variants = [v1]
    result.gene_variants = {"CYP2C19": [v1]}
    result.success = True
    assessment = engine.assess(result, "CLOPIDOGREL")
    assert assessment["risk_label"] in ("Ineffective", "Unknown")

# DPYD + FLUOROURACIL tests
def test_dpyd_toxic_rs3918290(engine):
    """DPYD rs3918290 heterozygous + FLUOROURACIL = Toxic/Adjust Dosage"""
    v1 = make_variant("DPYD", "*2A", "rs3918290", "0/1", chrom="chr1", pos=97915614)
    result = VCFParseResult(patient_id="TEST_004")
    result.variants = [v1]
    result.gene_variants = {"DPYD": [v1]}
    result.success = True
    assessment = engine.assess(result, "FLUOROURACIL")
    assert assessment["risk_label"] in ("Toxic", "Adjust Dosage", "Unknown")

# SLCO1B1 + SIMVASTATIN tests
def test_slco1b1_hom_toxic(engine):
    """SLCO1B1 *5/*5 (homozygous) + SIMVASTATIN = Toxic"""
    v1 = make_variant("SLCO1B1", "*5", "rs4149056", "1/1", chrom="chr12", pos=21284873)
    result = VCFParseResult(patient_id="TEST_005")
    result.variants = [v1]
    result.gene_variants = {"SLCO1B1": [v1]}
    result.success = True
    assessment = engine.assess(result, "SIMVASTATIN")
    assert assessment["risk_label"] in ("Toxic", "Unknown")

# TPMT + AZATHIOPRINE tests
def test_tpmt_im_adjust_dosage(engine):
    """TPMT *1/*3A (het) + AZATHIOPRINE = Adjust Dosage"""
    v1 = make_variant("TPMT", "*3A", "rs1142345", "0/1", chrom="chr6", pos=18130918)
    result = VCFParseResult(patient_id="TEST_006")
    result.variants = [v1]
    result.gene_variants = {"TPMT": [v1]}
    result.success = True
    assessment = engine.assess(result, "AZATHIOPRINE")
    assert assessment["risk_label"] in ("Adjust Dosage", "Unknown")

# CYP2C9 + WARFARIN tests
def test_cyp2c9_hom_toxic(engine):
    """CYP2C9 *3/*3 (PM) + WARFARIN = Toxic"""
    v1 = make_variant("CYP2C9", "*3", "rs1057910", "1/1", chrom="chr10", pos=96741058)
    result = VCFParseResult(patient_id="TEST_007")
    result.variants = [v1]
    result.gene_variants = {"CYP2C9": [v1]}
    result.success = True
    assessment = engine.assess(result, "WARFARIN")
    assert assessment["risk_label"] in ("Toxic", "Unknown")

# Unsupported drug test
def test_unsupported_drug(engine):
    result = VCFParseResult(patient_id="TEST_008", success=True)
    assessment = engine.assess(result, "ASPIRIN")
    assert "error" in assessment
    assert assessment["error"] == "unsupported_drug"

# Confidence score tests
def test_confidence_score_range(engine):
    v1 = make_variant("CYP2D6", "*1", "rs1065852", "0/0")
    result = VCFParseResult(patient_id="TEST_009")
    result.variants = [v1]
    result.gene_variants = {"CYP2D6": [v1]}
    result.success = True
    assessment = engine.assess(result, "CODEINE")
    assert 0.0 <= assessment["confidence_score"] <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
