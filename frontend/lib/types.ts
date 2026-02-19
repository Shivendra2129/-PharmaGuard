/**
 * TypeScript types for PharmaGuard API responses.
 * Matches the strict JSON schema exactly.
 */

export interface DetectedVariant {
    rsid: string;
    chromosome: string;
    position: number;
}

export interface RiskAssessment {
    risk_label: 'Safe' | 'Adjust Dosage' | 'Toxic' | 'Ineffective' | 'Unknown';
    confidence_score: number;
    severity: 'none' | 'low' | 'moderate' | 'high' | 'critical';
}

export interface PharmacogenomicProfile {
    primary_gene: string;
    diplotype: string;
    phenotype: 'PM' | 'IM' | 'NM' | 'RM' | 'URM' | 'Unknown';
    detected_variants: DetectedVariant[];
}

export interface ClinicalRecommendation {
    cpic_guideline: string;
    dose_adjustment: string;
    alternative_drugs: string[];
}

export interface LLMGeneratedExplanation {
    summary: string;
    mechanism: string;
    variant_citations: string[];
}

export interface QualityMetrics {
    vcf_parsing_success: boolean;
    guideline_version: string;
    llm_confidence: number;
}

export interface PharmaGuardResult {
    patient_id: string;
    drug: string;
    timestamp: string;
    risk_assessment: RiskAssessment;
    pharmacogenomic_profile: PharmacogenomicProfile;
    clinical_recommendation: ClinicalRecommendation;
    llm_generated_explanation: LLMGeneratedExplanation;
    quality_metrics: QualityMetrics;
    // Error fields
    error?: string;
    detail?: string;
}

export interface AnalysisResponse {
    success: boolean;
    request_id: string;
    results: PharmaGuardResult[];
    total_drugs_analyzed: number;
    timestamp: string;
}

export interface AnalysisError {
    error: string;
    detail: string;
    patient_id?: string;
    request_id?: string;
    timestamp: string;
}

export type RiskLabel = 'Safe' | 'Adjust Dosage' | 'Toxic' | 'Ineffective' | 'Unknown';
export type Severity = 'none' | 'low' | 'moderate' | 'high' | 'critical';
export type Phenotype = 'PM' | 'IM' | 'NM' | 'RM' | 'URM' | 'Unknown';
