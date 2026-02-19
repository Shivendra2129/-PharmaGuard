"""
Pydantic models for strict JSON schema enforcement.
All field names are case-sensitive per RIFT 2026 specification.
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class DetectedVariant(BaseModel):
    rsid: str
    chromosome: str
    position: int


class RiskAssessment(BaseModel):
    risk_label: str  # Safe | Adjust Dosage | Toxic | Ineffective | Unknown
    confidence_score: float
    severity: str    # none | low | moderate | high | critical


class PharmacogenomicProfile(BaseModel):
    primary_gene: str
    diplotype: str
    phenotype: str   # PM | IM | NM | RM | URM | Unknown
    detected_variants: List[DetectedVariant]


class ClinicalRecommendation(BaseModel):
    cpic_guideline: str
    dose_adjustment: str
    alternative_drugs: List[str]


class LLMGeneratedExplanation(BaseModel):
    summary: str
    mechanism: str
    variant_citations: List[str]


class QualityMetrics(BaseModel):
    vcf_parsing_success: bool
    guideline_version: str
    llm_confidence: float


class PharmaGuardResponse(BaseModel):
    patient_id: str
    drug: str
    timestamp: str
    risk_assessment: RiskAssessment
    pharmacogenomic_profile: PharmacogenomicProfile
    clinical_recommendation: ClinicalRecommendation
    llm_generated_explanation: LLMGeneratedExplanation
    quality_metrics: QualityMetrics


class ErrorResponse(BaseModel):
    error: str
    detail: str
    patient_id: Optional[str] = None
    drug: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class AnalysisRequest(BaseModel):
    patient_id: str
    drugs: List[str]
