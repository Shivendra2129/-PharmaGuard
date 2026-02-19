"""
PharmaGuard - FastAPI Genomics Microservice
Main application entry point.
Handles VCF file upload, risk assessment, and LLM explanation generation.
"""
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from dotenv import load_dotenv

# Load environment
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from models import (
    PharmaGuardResponse, ErrorResponse,
    DetectedVariant, RiskAssessment, PharmacogenomicProfile,
    ClinicalRecommendation, LLMGeneratedExplanation, QualityMetrics
)
from vcf_parser import parse_vcf
from risk_engine import RiskEngine
from llm_service import generate_explanation

app = FastAPI(
    title="PharmaGuard Genomics API",
    description="Pharmacogenomic Risk Prediction Microservice - RIFT 2026",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:3001").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize risk engine (loads CSV on startup)
risk_engine = RiskEngine()


def make_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_error_response(error: str, detail: str, patient_id: str = None,
                          drug: str = None, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error,
            "detail": detail,
            "patient_id": patient_id,
            "drug": drug,
            "timestamp": make_timestamp()
        }
    )


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "PharmaGuard Genomics API",
        "version": "1.0.0",
        "timestamp": make_timestamp()
    }


@app.post("/analyze", response_model=List[PharmaGuardResponse])
async def analyze_vcf(
    vcf_file: UploadFile = File(..., description="VCF v4.2 file"),
    drugs: str = Form(..., description="Comma-separated drug names"),
    patient_id: Optional[str] = Form(None, description="Patient identifier")
):
    """
    Analyze a VCF file for pharmacogenomic risk for one or more drugs.
    Returns list of PharmaGuardResponse objects (one per drug).
    """
    # Generate patient ID if not provided
    if not patient_id or patient_id.strip() == "":
        patient_id = f"PATIENT_{uuid.uuid4().hex[:6].upper()}"
    else:
        patient_id = patient_id.strip()
    
    # Parse drug list
    drug_list = [d.strip().upper() for d in drugs.split(',') if d.strip()]
    if not drug_list:
        return build_error_response(
            "invalid_drugs",
            "No valid drug names provided",
            patient_id=patient_id,
            status_code=400
        )
    
    # Read and validate VCF content
    try:
        content_bytes = await vcf_file.read()
        vcf_content = content_bytes.decode('utf-8')
    except UnicodeDecodeError:
        try:
            vcf_content = content_bytes.decode('latin-1')
        except Exception:
            return build_error_response(
                "invalid_file_encoding",
                "VCF file must be UTF-8 or ASCII encoded",
                patient_id=patient_id,
                status_code=422
            )
    except Exception as e:
        return build_error_response(
            "file_read_error",
            f"Could not read uploaded file: {str(e)}",
            patient_id=patient_id,
            status_code=422
        )
    
    # Validate VCF header
    from vcf_parser import validate_vcf_header
    valid, msg = validate_vcf_header(vcf_content)
    if not valid:
        return build_error_response(
            "invalid_vcf_format",
            msg,
            patient_id=patient_id,
            status_code=422
        )
    
    # Parse VCF
    parse_result = parse_vcf(vcf_content, patient_id)
    
    # Build response for each drug
    results = []
    timestamp = make_timestamp()
    
    for drug in drug_list:
        drug_upper = drug.upper()
        
        # Run deterministic risk assessment
        assessment = risk_engine.assess(parse_result, drug_upper)
        
        # Handle unsupported drug
        if "error" in assessment:
            results.append({
                "patient_id": patient_id,
                "drug": drug_upper,
                "timestamp": timestamp,
                "error": assessment["error"],
                "detail": assessment["detail"]
            })
            continue
        
        # Generate LLM explanation (explanation only, never risk decision)
        llm_result = generate_explanation(
            gene=assessment["primary_gene"],
            diplotype=assessment["diplotype"],
            phenotype=assessment["phenotype"],
            drug=drug_upper,
            risk_label=assessment["risk_label"],
            severity=assessment["severity"],
            detected_variants=assessment["detected_variants"],
            cpic_recommendation=assessment["cpic_recommendation"]
        )
        
        # Build strict schema response
        response = PharmaGuardResponse(
            patient_id=patient_id,
            drug=drug_upper,
            timestamp=timestamp,
            risk_assessment=RiskAssessment(
                risk_label=assessment["risk_label"],
                confidence_score=assessment["confidence_score"],
                severity=assessment["severity"]
            ),
            pharmacogenomic_profile=PharmacogenomicProfile(
                primary_gene=assessment["primary_gene"],
                diplotype=assessment["diplotype"],
                phenotype=assessment["phenotype"],
                detected_variants=[
                    DetectedVariant(
                        rsid=v["rsid"],
                        chromosome=v["chromosome"],
                        position=v["position"]
                    )
                    for v in assessment["detected_variants"]
                ]
            ),
            clinical_recommendation=ClinicalRecommendation(
                cpic_guideline=f"CPIC Guideline for {drug_upper} and {assessment['primary_gene']}",
                dose_adjustment=assessment["cpic_recommendation"],
                alternative_drugs=assessment["alternative_drugs"]
            ),
            llm_generated_explanation=LLMGeneratedExplanation(
                summary=llm_result.get("summary", ""),
                mechanism=llm_result.get("mechanism", ""),
                variant_citations=llm_result.get("variant_citations", [])
            ),
            quality_metrics=QualityMetrics(
                vcf_parsing_success=assessment["vcf_parsing_success"],
                guideline_version="CPIC v2.0",
                llm_confidence=llm_result.get("llm_confidence", 0.75)
            )
        )
        
        results.append(response.model_dump())
    
    return JSONResponse(content=results)


@app.get("/supported-drugs")
async def get_supported_drugs():
    """Return list of supported drugs and their associated genes."""
    from risk_engine import DRUG_GENE_MAP, SUPPORTED_DRUGS
    return {
        "supported_drugs": sorted(list(SUPPORTED_DRUGS)),
        "drug_gene_map": DRUG_GENE_MAP
    }


@app.get("/supported-genes")
async def get_supported_genes():
    """Return list of supported pharmacogenomic genes."""
    from vcf_parser import SUPPORTED_GENES
    return {
        "supported_genes": sorted(list(SUPPORTED_GENES))
    }


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("PYTHON_HOST", "0.0.0.0")
    # Render sets PORT; PYTHON_PORT is the local fallback
    port = int(os.getenv("PORT", os.getenv("PYTHON_PORT", "8000")))
    is_prod = os.getenv("PYTHON_ENV", "development") == "production"
    uvicorn.run("main:app", host=host, port=port, reload=not is_prod)
