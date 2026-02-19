'use client';

import React, { useState } from 'react';
import { PharmaGuardResult, RiskLabel } from '@/lib/types';

interface RiskCardProps {
    result: PharmaGuardResult;
}

const RISK_CONFIG: Record<string, { cssClass: string; emoji: string; bgGradient: string }> = {
    'Safe': {
        cssClass: 'risk-safe',
        emoji: '✅',
        bgGradient: 'from-emerald-950/60 to-gray-900/60 border-emerald-700/30',
    },
    'Adjust Dosage': {
        cssClass: 'risk-adjust',
        emoji: '⚠️',
        bgGradient: 'from-amber-950/60 to-gray-900/60 border-amber-700/30',
    },
    'Toxic': {
        cssClass: 'risk-toxic',
        emoji: '☠️',
        bgGradient: 'from-red-950/60 to-gray-900/60 border-red-700/30',
    },
    'Ineffective': {
        cssClass: 'risk-ineffective',
        emoji: '🚫',
        bgGradient: 'from-red-950/60 to-gray-900/60 border-red-700/30',
    },
    'Unknown': {
        cssClass: 'risk-unknown',
        emoji: '❓',
        bgGradient: 'from-gray-900/60 to-gray-950/60 border-gray-700/30',
    },
};

const SEVERITY_COLORS: Record<string, string> = {
    none: 'text-gray-400',
    low: 'text-blue-400',
    moderate: 'text-amber-400',
    high: 'text-orange-400',
    critical: 'text-red-400',
};

const PHENOTYPE_LABELS: Record<string, string> = {
    PM: 'Poor Metabolizer',
    IM: 'Intermediate Metabolizer',
    NM: 'Normal Metabolizer',
    RM: 'Rapid Metabolizer',
    URM: 'Ultrarapid Metabolizer',
    Unknown: 'Unknown',
};

const ConfidenceBar = ({ score }: { score: number }) => {
    const pct = Math.round(score * 100);
    const color = pct >= 85 ? '#10b981' : pct >= 70 ? '#f59e0b' : '#ef4444';
    return (
        <div className="flex items-center gap-3">
            <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
                <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{ width: `${pct}%`, backgroundColor: color }}
                />
            </div>
            <span className="text-sm font-mono font-semibold" style={{ color }}>{pct}%</span>
        </div>
    );
};

const Section = ({
    title, icon, children, defaultOpen = false
}: {
    title: string; icon: string; children: React.ReactNode; defaultOpen?: boolean;
}) => {
    const [open, setOpen] = useState(defaultOpen);
    return (
        <div className="border border-white/5 rounded-xl overflow-hidden">
            <button
                onClick={() => setOpen(!open)}
                className="w-full flex items-center justify-between px-5 py-4 hover:bg-white/5 transition-colors duration-200"
                id={`section-toggle-${title.replace(/\s+/g, '-').toLowerCase()}`}
            >
                <div className="flex items-center gap-3">
                    <span className="text-lg">{icon}</span>
                    <span className="font-semibold text-gray-200">{title}</span>
                </div>
                <svg
                    className={`w-5 h-5 text-gray-400 transition-transform duration-300 ${open ? 'rotate-180' : ''}`}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
            </button>
            {open && (
                <div className="px-5 pb-5 pt-2 bg-gray-950/30 border-t border-white/5">
                    {children}
                </div>
            )}
        </div>
    );
};

const RiskCard: React.FC<RiskCardProps> = ({ result }) => {
    const riskLabel = result.risk_assessment?.risk_label || 'Unknown';
    const config = RISK_CONFIG[riskLabel] || RISK_CONFIG['Unknown'];
    const profile = result.pharmacogenomic_profile;
    const recommendation = result.clinical_recommendation;
    const explanation = result.llm_generated_explanation;
    const quality = result.quality_metrics;

    if (result.error) {
        return (
            <div className="glass-card rounded-2xl p-6 border border-red-700/30 bg-gradient-to-br from-red-950/60 to-gray-900/60">
                <div className="flex items-center gap-3 mb-3">
                    <span className="text-2xl">❌</span>
                    <div>
                        <h3 className="font-bold text-red-400 text-lg">{result.drug}</h3>
                        <p className="text-red-300/70 text-sm">{result.error}</p>
                    </div>
                </div>
                <p className="text-gray-400 text-sm bg-red-950/40 rounded-lg p-3">{result.detail}</p>
            </div>
        );
    }

    return (
        <div className={`glass-card rounded-2xl overflow-hidden border bg-gradient-to-br ${config.bgGradient}`}>
            {/* Header */}
            <div className="px-6 py-5 border-b border-white/5">
                <div className="flex items-start justify-between flex-wrap gap-3">
                    <div>
                        <div className="flex items-center gap-3 mb-2">
                            <span className="text-3xl">{config.emoji}</span>
                            <div>
                                <h3 className="text-xl font-bold text-white">{result.drug}</h3>
                                <p className="text-gray-400 text-sm font-mono">
                                    {profile?.primary_gene} • {profile?.diplotype}
                                </p>
                            </div>
                        </div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                        <span className={`px-4 py-1.5 rounded-full text-sm font-bold ${config.cssClass}`}>
                            {riskLabel}
                        </span>
                        <span className={`text-xs font-semibold uppercase tracking-wider ${SEVERITY_COLORS[result.risk_assessment.severity] || 'text-gray-400'}`}>
                            {result.risk_assessment.severity} severity
                        </span>
                    </div>
                </div>

                {/* Confidence */}
                <div className="mt-4">
                    <div className="flex justify-between text-xs text-gray-400 mb-2">
                        <span>Confidence Score</span>
                        <span className="font-mono">{PHENOTYPE_LABELS[profile?.phenotype] || profile?.phenotype}</span>
                    </div>
                    <ConfidenceBar score={result.risk_assessment.confidence_score} />
                </div>
            </div>

            {/* Content sections */}
            <div className="p-4 space-y-3">

                {/* Genomic Profile */}
                <Section title="Pharmacogenomic Profile" icon="🧬" defaultOpen={true}>
                    <div className="grid grid-cols-2 gap-3 mb-4">
                        {[
                            { label: 'Gene', value: profile?.primary_gene },
                            { label: 'Phenotype', value: profile?.phenotype },
                            { label: 'Diplotype', value: profile?.diplotype },
                            { label: 'Guideline', value: quality?.guideline_version || 'CPIC v2.0' },
                        ].map(({ label, value }) => (
                            <div key={label} className="bg-gray-900/50 rounded-lg p-3">
                                <p className="text-xs text-gray-500 mb-1">{label}</p>
                                <p className="font-mono font-semibold text-gray-200 text-sm">{value || '—'}</p>
                            </div>
                        ))}
                    </div>

                    {/* Detected Variants */}
                    {profile?.detected_variants && profile.detected_variants.length > 0 && (
                        <div>
                            <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Detected Variants</p>
                            <div className="space-y-2">
                                {profile.detected_variants.map((v, i) => (
                                    <div key={i} className="flex items-center gap-3 bg-gray-900/60 rounded-lg px-3 py-2 text-sm font-mono">
                                        <span className="text-indigo-400 font-semibold">{v.rsid}</span>
                                        <span className="text-gray-500">•</span>
                                        <span className="text-gray-400">{v.chromosome}</span>
                                        <span className="text-gray-500">•</span>
                                        <span className="text-gray-400">pos: {v.position.toLocaleString()}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </Section>

                {/* Clinical Recommendation */}
                <Section title="Clinical Recommendation" icon="💊" defaultOpen={true}>
                    <div className="space-y-3">
                        <div className="bg-gray-900/50 rounded-lg p-3">
                            <p className="text-xs text-gray-500 mb-1">CPIC Guideline</p>
                            <p className="text-gray-300 text-sm">{recommendation?.cpic_guideline || '—'}</p>
                        </div>
                        <div className="bg-gray-900/50 rounded-lg p-3">
                            <p className="text-xs text-gray-500 mb-1">Dose Adjustment</p>
                            <p className="text-gray-300 text-sm">{recommendation?.dose_adjustment || '—'}</p>
                        </div>
                        {recommendation?.alternative_drugs && recommendation.alternative_drugs.length > 0 && (
                            <div>
                                <p className="text-xs text-gray-500 mb-2">Alternative Drugs</p>
                                <div className="flex flex-wrap gap-2">
                                    {recommendation.alternative_drugs.map((drug) => (
                                        <span key={drug} className="px-2 py-1 text-xs font-semibold bg-indigo-900/40 border border-indigo-500/30 text-indigo-300 rounded-md">
                                            {drug}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </Section>

                {/* AI Explanation */}
                <Section title="AI-Generated Explanation" icon="🤖">
                    <div className="space-y-4">
                        <div>
                            <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Patient Summary</p>
                            <p className="text-gray-300 text-sm leading-relaxed bg-gray-900/40 rounded-lg p-3">
                                {explanation?.summary || 'No explanation available.'}
                            </p>
                        </div>
                        <div>
                            <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Clinical Mechanism</p>
                            <p className="text-gray-300 text-sm leading-relaxed bg-gray-900/40 rounded-lg p-3">
                                {explanation?.mechanism || 'No mechanism explanation available.'}
                            </p>
                        </div>
                        {explanation?.variant_citations && explanation.variant_citations.length > 0 && (
                            <div>
                                <p className="text-xs text-gray-500 mb-2 uppercase tracking-wider">Variant Citations</p>
                                <div className="flex flex-wrap gap-2">
                                    {explanation.variant_citations.map((rs) => (
                                        <span key={rs} className="px-2 py-1 text-xs font-mono bg-purple-900/30 border border-purple-500/30 text-purple-300 rounded-md">
                                            {rs}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}
                        <div className="flex items-center gap-2 mt-2">
                            <span className="text-xs text-gray-500">LLM Confidence:</span>
                            <ConfidenceBar score={quality?.llm_confidence || 0} />
                        </div>
                    </div>
                </Section>

                {/* Quality Metrics */}
                <Section title="Quality Metrics" icon="📊">
                    <div className="grid grid-cols-3 gap-2">
                        {[
                            { label: 'VCF Parsed', value: quality?.vcf_parsing_success ? '✓ Yes' : '✗ No', ok: quality?.vcf_parsing_success },
                            { label: 'Guideline', value: quality?.guideline_version || 'CPIC v2.0', ok: true },
                            { label: 'LLM Score', value: `${Math.round((quality?.llm_confidence || 0) * 100)}%`, ok: (quality?.llm_confidence || 0) > 0.5 },
                        ].map(({ label, value, ok }) => (
                            <div key={label} className="bg-gray-900/50 rounded-lg p-3 text-center">
                                <p className="text-xs text-gray-500 mb-1">{label}</p>
                                <p className={`text-sm font-semibold ${ok ? 'text-emerald-400' : 'text-red-400'}`}>{value}</p>
                            </div>
                        ))}
                    </div>
                </Section>
            </div>
        </div>
    );
};

export default RiskCard;
