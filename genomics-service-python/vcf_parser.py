"""
VCF Parser module using cyvcf2.
Extracts pharmacogenomic variants from VCF v4.2 files.
Parses GENE, STAR, RS INFO tags as required by spec.
"""
import io
import tempfile
import os
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# cyvcf2 must be installed; fallback manual parser for environments without it
try:
    from cyvcf2 import VCF
    CYVCF2_AVAILABLE = True
except ImportError:
    CYVCF2_AVAILABLE = False

SUPPORTED_GENES = {"CYP2D6", "CYP2C19", "CYP2C9", "SLCO1B1", "TPMT", "DPYD"}


@dataclass
class ParsedVariant:
    chromosome: str
    position: int
    ref: str
    alt: str
    genotype: str         # e.g. "0/1", "1/1", "0/0"
    gene: str
    star_allele: str
    rsid: str
    qual: Optional[float] = None


@dataclass
class VCFParseResult:
    patient_id: str
    variants: List[ParsedVariant] = field(default_factory=list)
    gene_variants: Dict[str, List[ParsedVariant]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    success: bool = True


def validate_vcf_header(content: str) -> Tuple[bool, str]:
    """Validate that the file has a proper VCF header."""
    lines = content.strip().split('\n')
    if not lines:
        return False, "Empty file"
    
    first_line = lines[0].strip()
    if not first_line.startswith("##fileformat=VCF"):
        return False, f"Invalid VCF header. First line must start with '##fileformat=VCF', got: {first_line[:50]}"
    
    has_chrom_header = any(line.startswith("#CHROM") for line in lines)
    if not has_chrom_header:
        return False, "Missing #CHROM header line in VCF file"
    
    return True, "Valid VCF"


def _parse_with_cyvcf2(vcf_content: str, patient_id: str) -> VCFParseResult:
    """Parse VCF using cyvcf2 library."""
    result = VCFParseResult(patient_id=patient_id)
    
    # Write to temp file (cyvcf2 needs file path)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.vcf', delete=False, encoding='utf-8') as tmp:
        tmp.write(vcf_content)
        tmp_path = tmp.name
    
    try:
        vcf_reader = VCF(tmp_path)
        
        for variant in vcf_reader:
            # Extract INFO tags
            gene = variant.INFO.get("GENE", "")
            star = variant.INFO.get("STAR", "")
            rs = variant.INFO.get("RS", "")
            
            if not gene or gene not in SUPPORTED_GENES:
                if gene:
                    result.warnings.append(f"Skipping unsupported gene: {gene}")
                continue
            
            # Extract genotype from first sample
            gt_str = "unknown"
            if variant.genotypes and len(variant.genotypes) > 0:
                gt = variant.genotypes[0]
                if gt[0] is None or gt[1] is None:
                    gt_str = "./."
                else:
                    gt_str = f"{gt[0]}/{gt[1]}"
            
            # Determine ALT allele string
            alt_str = ",".join(variant.ALT) if variant.ALT else "."
            
            parsed = ParsedVariant(
                chromosome=str(variant.CHROM),
                position=int(variant.POS),
                ref=str(variant.REF),
                alt=alt_str,
                genotype=gt_str,
                gene=gene,
                star_allele=star or "*1",
                rsid=rs or f"chr{variant.CHROM}:{variant.POS}",
                qual=float(variant.QUAL) if variant.QUAL else None
            )
            
            result.variants.append(parsed)
            if gene not in result.gene_variants:
                result.gene_variants[gene] = []
            result.gene_variants[gene].append(parsed)
    
    finally:
        os.unlink(tmp_path)
    
    return result


def _parse_manual(vcf_content: str, patient_id: str) -> VCFParseResult:
    """Fallback manual VCF parser (no cyvcf2 dependency)."""
    result = VCFParseResult(patient_id=patient_id)
    lines = vcf_content.strip().split('\n')
    
    chrom_header = None
    for line in lines:
        if line.startswith('#CHROM'):
            chrom_header = line.split('\t')
            break
    
    for line in lines:
        if line.startswith('#'):
            continue
        
        parts = line.strip().split('\t')
        if len(parts) < 8:
            continue
        
        chrom, pos, vid, ref, alt, qual, filt, info_str = parts[:8]
        
        # Parse INFO field
        info = {}
        for item in info_str.split(';'):
            if '=' in item:
                k, v = item.split('=', 1)
                info[k] = v
            else:
                info[item] = True
        
        gene = info.get('GENE', '')
        star = info.get('STAR', '')
        rs = info.get('RS', '')
        
        if not gene or gene not in SUPPORTED_GENES:
            if gene:
                result.warnings.append(f"Skipping unsupported gene: {gene}")
            continue
        
        # Parse genotype from FORMAT/SAMPLE columns
        gt_str = "0/0"
        if len(parts) >= 10:
            fmt_fields = parts[8].split(':')
            sample_fields = parts[9].split(':')
            if 'GT' in fmt_fields:
                gt_idx = fmt_fields.index('GT')
                if gt_idx < len(sample_fields):
                    raw_gt = sample_fields[gt_idx]
                    # Normalize | to /
                    gt_str = raw_gt.replace('|', '/')
        
        try:
            pos_int = int(pos)
        except ValueError:
            pos_int = 0
        
        parsed = ParsedVariant(
            chromosome=chrom,
            position=pos_int,
            ref=ref,
            alt=alt,
            genotype=gt_str,
            gene=gene,
            star_allele=star or "*1",
            rsid=rs or f"{chrom}:{pos}",
            qual=float(qual) if qual and qual != '.' else None
        )
        
        result.variants.append(parsed)
        if gene not in result.gene_variants:
            result.gene_variants[gene] = []
        result.gene_variants[gene].append(parsed)
    
    return result


def parse_vcf(vcf_content: str, patient_id: str = "PATIENT_UNKNOWN") -> VCFParseResult:
    """
    Main VCF parsing entry point.
    Uses cyvcf2 if available, falls back to manual parser.
    """
    # Validate header first
    valid, msg = validate_vcf_header(vcf_content)
    if not valid:
        result = VCFParseResult(patient_id=patient_id, success=False)
        result.warnings.append(f"VCF validation failed: {msg}")
        return result
    
    if CYVCF2_AVAILABLE:
        return _parse_with_cyvcf2(vcf_content, patient_id)
    else:
        return _parse_manual(vcf_content, patient_id)


def extract_diplotype_for_gene(gene_variants: List[ParsedVariant]) -> Tuple[str, List[str]]:
    """
    Infer diplotype and collected alleles from variant list for a gene.
    Returns (diplotype_string, [star_alleles])
    """
    if not gene_variants:
        return "unknown", []
    
    alleles = []
    for v in gene_variants:
        gt = v.genotype
        star = v.star_allele
        
        if gt in ("1/1", "1|1"):
            # Homozygous ALT - both alleles are the variant
            alleles.extend([star, star])
        elif gt in ("0/1", "1/0", "0|1", "1|0"):
            # Heterozygous - one reference (*1) and one variant
            alleles.extend(["*1", star])
        elif gt in ("0/0", "0|0"):
            # Homozygous REF - both are wildtype
            alleles.extend(["*1", "*1"])
    
    if not alleles:
        return "unknown", []
    
    # Remove wildcards and deduplicate intelligently
    # Find highest-priority variant allele
    non_ref = [a for a in alleles if a != "*1"]
    
    if not non_ref:
        return "*1/*1", ["*1", "*1"]
    
    # Build diplotype from most frequent variant allele
    # Use unique stars for diplotype
    unique_stars = list(dict.fromkeys(alleles))  # preserve order, deduplicated
    
    if len(unique_stars) >= 2:
        diplotype = f"{unique_stars[0]}/{unique_stars[1]}"
    else:
        diplotype = f"{unique_stars[0]}/{unique_stars[0]}"
    
    return diplotype, alleles
