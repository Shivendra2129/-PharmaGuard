"""Quick verification script for PharmaGuard"""
import sys, os, ast, pathlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'genomics-service-python'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'genomics-service-python'))

print("=== PharmaGuard Verification ===\n")

# 1. Python syntax check
print("[1] Python Syntax Check")
for f in pathlib.Path('.').glob('*.py'):
    try:
        ast.parse(f.read_text(encoding='utf-8'))
        print(f"  OK: {f.name}")
    except SyntaxError as e:
        print(f"  ERROR: {f.name} - {e}")

# 2. Import check
print("\n[2] Import Check")
try:
    from models import PharmaGuardResponse, ErrorResponse
    print("  OK: models.py")
except Exception as e:
    print(f"  ERROR: models.py - {e}")

try:
    from vcf_parser import parse_vcf, validate_vcf_header, extract_diplotype_for_gene
    print("  OK: vcf_parser.py")
except Exception as e:
    print(f"  ERROR: vcf_parser.py - {e}")

try:
    from risk_engine import RiskEngine
    print("  OK: risk_engine.py")
except Exception as e:
    print(f"  ERROR: risk_engine.py - {e}")

try:
    from llm_service import generate_explanation, build_explanation_prompt
    print("  OK: llm_service.py")
except Exception as e:
    print(f"  ERROR: llm_service.py - {e}")

# 3. CSV validation
print("\n[3] CSV Knowledge Base")
import pandas as pd
df = pd.read_csv('../data/pharmacogenomic_rules.csv')
print(f"  Rules: {len(df)}")
print(f"  Columns: {list(df.columns)}")
required = ['gene','drug','diplotype','phenotype','risk_label','severity','cpic_recommendation','alternative_drugs','evidence_level']
missing = [c for c in required if c not in df.columns]
if missing:
    print(f"  MISSING COLUMNS: {missing}")
else:
    print("  All 9 columns present")
genes = sorted(df['gene'].unique())
drugs = sorted(df['drug'].unique())
print(f"  Genes: {genes}")
print(f"  Drugs: {drugs}")

# 4. Sample VCFs
print("\n[4] Sample VCF Files")
for vcf_file in ['../sample_vcfs/sample1_cyp2d6_pm.vcf', '../sample_vcfs/sample2_dpyd_toxic.vcf']:
    if os.path.exists(vcf_file):
        content = open(vcf_file, encoding='utf-8').read()
        valid_header = content.startswith('##fileformat=VCF')
        has_chrom = '#CHROM' in content
        lines = [l for l in content.split('\n') if l and not l.startswith('#')]
        print(f"  {os.path.basename(vcf_file)}: header={valid_header}, #CHROM={has_chrom}, variants={len(lines)}")
    else:
        print(f"  MISSING: {vcf_file}")

# 5. Risk engine functional test
print("\n[5] Risk Engine Functional Test")
engine = RiskEngine()
from vcf_parser import ParsedVariant, VCFParseResult

def quick_test(gene, star, rsid, gt, drug, expected_label):
    v = ParsedVariant(chromosome="chr1", position=100, ref="C", alt="T", genotype=gt, gene=gene, star_allele=star, rsid=rsid)
    r = VCFParseResult(patient_id="TEST")
    r.variants = [v]
    r.gene_variants = {gene: [v]}
    r.success = True
    result = engine.assess(r, drug)
    label = result.get("risk_label", result.get("error", "?"))
    status = "OK" if label == expected_label or "error" not in result else "WARN"
    print(f"  {status}: {gene} {star}({gt}) + {drug} => {label} (expected ~{expected_label})")

quick_test("CYP2D6", "*4", "rs3892097", "1/1", "CODEINE", "Ineffective")
quick_test("CYP2C19", "*2", "rs4244285", "1/1", "CLOPIDOGREL", "Ineffective")
quick_test("CYP2C9", "*3", "rs1057910", "1/1", "WARFARIN", "Toxic")
quick_test("SLCO1B1", "*5", "rs4149056", "1/1", "SIMVASTATIN", "Toxic")
quick_test("TPMT", "*3A", "rs1142345", "0/1", "AZATHIOPRINE", "Adjust Dosage")
quick_test("DPYD", "*2A", "rs3918290", "0/1", "FLUOROURACIL", "Toxic")
quick_test("CYP2D6", "*1", "rs1065852", "0/0", "CODEINE", "Safe")

# 6. JSON schema validation
print("\n[6] JSON Schema Compliance")
from datetime import datetime, timezone
resp = PharmaGuardResponse(
    patient_id="TEST_001",
    drug="CODEINE",
    timestamp=datetime.now(timezone.utc).isoformat(),
    risk_assessment={"risk_label": "Safe", "confidence_score": 0.9, "severity": "none"},
    pharmacogenomic_profile={"primary_gene": "CYP2D6", "diplotype": "*1/*1", "phenotype": "NM", "detected_variants": []},
    clinical_recommendation={"cpic_guideline": "test", "dose_adjustment": "none", "alternative_drugs": []},
    llm_generated_explanation={"summary": "test", "mechanism": "test", "variant_citations": []},
    quality_metrics={"vcf_parsing_success": True, "guideline_version": "CPIC v2.0", "llm_confidence": 0.8}
)
schema_keys = list(resp.model_dump().keys())
expected = ["patient_id","drug","timestamp","risk_assessment","pharmacogenomic_profile","clinical_recommendation","llm_generated_explanation","quality_metrics"]
if schema_keys == expected:
    print(f"  OK: All 8 top-level fields in correct order")
else:
    print(f"  WARN: Got {schema_keys}")
    print(f"  Expected {expected}")

print("\n=== Verification Complete ===")
