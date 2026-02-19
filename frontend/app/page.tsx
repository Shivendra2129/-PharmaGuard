'use client';

import React, { useState, useCallback } from 'react';
import axios from 'axios';
import VcfUpload from '@/components/VcfUpload';
import RiskCard from '@/components/RiskCard';
import JsonViewer from '@/components/JsonViewer';
import ErrorPanel from '@/components/ErrorPanel';
import { AnalysisResponse, AnalysisError, PharmaGuardResult } from '@/lib/types';

const SUPPORTED_DRUGS = ['CODEINE', 'WARFARIN', 'CLOPIDOGREL', 'SIMVASTATIN', 'AZATHIOPRINE', 'FLUOROURACIL'];
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';

export default function Home() {
  const [vcfFile, setVcfFile] = useState<File | null>(null);
  const [drugsInput, setDrugsInput] = useState<string>('CODEINE,WARFARIN');
  const [patientId, setPatientId] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [results, setResults] = useState<PharmaGuardResult[] | null>(null);
  const [rawResponse, setRawResponse] = useState<object | null>(null);
  const [copyDone, setCopyDone] = useState(false);
  const [error, setError] = useState<{ error: string; detail: string } | null>(null);
  const [showJson, setShowJson] = useState<boolean>(false);

  const handleFileAccepted = useCallback((file: File) => {
    setVcfFile(file);
    setResults(null);
    setError(null);
  }, []);

  const toggleDrug = (drug: string) => {
    const current = drugsInput.split(',').map(d => d.trim().toUpperCase()).filter(Boolean);
    if (current.includes(drug)) {
      setDrugsInput(current.filter(d => d !== drug).join(','));
    } else {
      setDrugsInput([...current, drug].join(','));
    }
  };

  const isDrugSelected = (drug: string) =>
    drugsInput.split(',').map(d => d.trim().toUpperCase()).includes(drug);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vcfFile) { setError({ error: 'missing_file', detail: 'Please upload a VCF file.' }); return; }
    if (!drugsInput.trim()) { setError({ error: 'missing_drugs', detail: 'Please specify at least one drug.' }); return; }

    setIsLoading(true);
    setError(null);
    setResults(null);
    setRawResponse(null);

    const formData = new FormData();
    formData.append('vcf_file', vcfFile);
    formData.append('drugs', drugsInput);
    if (patientId.trim()) formData.append('patient_id', patientId.trim());

    try {
      const response = await axios.post<AnalysisResponse>(
        `${API_URL}/api/analyze`, formData,
        { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 90000 }
      );
      const data = response.data;
      setResults(data.results);
      // Store only the schema-compliant results array for JSON export
      setRawResponse(data.results);
    } catch (err: any) {
      if (err.response?.data) {
        setError(err.response.data);
      } else if (err.code === 'ECONNREFUSED' || err.message?.includes('Network Error')) {
        setError({
          error: 'network_error',
          detail: `Cannot reach API at ${API_URL}. Ensure the backend services are running.`
        });
      } else {
        setError({ error: 'unexpected_error', detail: err.message || 'Unknown error occurred.' });
      }
    } finally {
      setIsLoading(false);
    }
  };

  const hasResults = results && results.length > 0;
  const riskCounts = results ? {
    safe: results.filter(r => r.risk_assessment?.risk_label === 'Safe').length,
    adjust: results.filter(r => r.risk_assessment?.risk_label === 'Adjust Dosage').length,
    danger: results.filter(r => ['Toxic', 'Ineffective'].includes(r.risk_assessment?.risk_label)).length,
  } : null;

  return (
    <main className="min-h-screen">
      {/* Navigation */}
      <nav className="sticky top-0 z-50 glass-card border-b border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
              <span className="text-lg">🧬</span>
            </div>
            <div>
              <h1 className="text-lg font-bold text-white leading-none">PharmaGuard</h1>
              <p className="text-xs text-indigo-400 font-mono">Pharmacogenomic Risk Prediction</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-indigo-950/60 border border-indigo-500/20 text-xs text-indigo-300 font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse"></span>
              RIFT 2026
            </span>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 lg:py-12">
        {/* Hero section */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-indigo-950/60 border border-indigo-500/20 text-sm text-indigo-300 mb-6">
            <span>🏆</span>
            <span>RIFT 2026 Hackathon | Pharmacogenomics / Explainable AI Track</span>
          </div>
          <h2 className="text-4xl sm:text-5xl font-extrabold text-white mb-4 leading-tight">
            AI-Powered{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-emerald-400">
              Pharmacogenomic
            </span>
            {' '}Risk Analysis
          </h2>
          <p className="text-gray-400 text-lg max-w-2xl mx-auto">
            Upload your VCF file and receive CPIC-aligned drug safety predictions powered by{' '}
            <span className="text-indigo-300">deterministic genomic rules</span> and{' '}
            <span className="text-emerald-300">explainable AI</span>.
          </p>

          {/* Feature pills */}
          <div className="flex flex-wrap justify-center gap-2 mt-6">
            {['6 Pharmacogenes', 'CPIC Guidelines', 'GPT-4 Explanations', 'VCF v4.2', 'Strict JSON Schema', 'No Data Storage'].map(f => (
              <span key={f} className="px-3 py-1 rounded-full text-xs font-semibold bg-gray-800/60 border border-white/10 text-gray-300">
                {f}
              </span>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left: Analysis Form */}
          <div className="lg:col-span-1">
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="glass-card rounded-2xl p-6 space-y-5">
                <h3 className="font-bold text-white text-lg flex items-center gap-2">
                  <span className="w-7 h-7 rounded-lg bg-indigo-500/20 flex items-center justify-center text-sm">1</span>
                  Patient & File
                </h3>

                {/* Patient ID */}
                <div>
                  <label htmlFor="patient-id" className="block text-sm text-gray-400 mb-2 font-medium">
                    Patient ID <span className="text-gray-600">(optional)</span>
                  </label>
                  <input
                    id="patient-id"
                    type="text"
                    value={patientId}
                    onChange={(e) => setPatientId(e.target.value)}
                    placeholder="PATIENT_001"
                    className="w-full px-4 py-2.5 rounded-xl bg-gray-900/70 border border-white/10 text-gray-200 placeholder-gray-600 font-mono text-sm focus:outline-none focus:border-indigo-500/50 transition-colors"
                  />
                </div>

                {/* VCF Upload */}
                <div>
                  <label className="block text-sm text-gray-400 mb-2 font-medium">VCF File</label>
                  <VcfUpload onFileAccepted={handleFileAccepted} disabled={isLoading} />
                </div>
              </div>

              {/* Drug Selection */}
              <div className="glass-card rounded-2xl p-6 space-y-4">
                <h3 className="font-bold text-white text-lg flex items-center gap-2">
                  <span className="w-7 h-7 rounded-lg bg-indigo-500/20 flex items-center justify-center text-sm">2</span>
                  Select Drugs
                </h3>

                {/* Quick-select pills */}
                <div className="flex flex-wrap gap-2">
                  {SUPPORTED_DRUGS.map(drug => (
                    <button
                      key={drug}
                      type="button"
                      id={`drug-btn-${drug.toLowerCase()}`}
                      onClick={() => toggleDrug(drug)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-all duration-200
                        ${isDrugSelected(drug)
                          ? 'bg-indigo-500/30 border-indigo-400 text-indigo-200'
                          : 'bg-gray-800/50 border-gray-700/50 text-gray-400 hover:border-gray-600'}`}
                    >
                      {drug}
                    </button>
                  ))}
                </div>

                {/* Manual input */}
                <div>
                  <label htmlFor="drugs-input" className="block text-xs text-gray-500 mb-1">
                    Or type comma-separated drugs:
                  </label>
                  <input
                    id="drugs-input"
                    type="text"
                    value={drugsInput}
                    onChange={(e) => setDrugsInput(e.target.value)}
                    placeholder="CODEINE,WARFARIN,CLOPIDOGREL"
                    className="w-full px-4 py-2.5 rounded-xl bg-gray-900/70 border border-white/10 text-gray-200 placeholder-gray-600 font-mono text-sm focus:outline-none focus:border-indigo-500/50 transition-colors"
                  />
                </div>
              </div>

              {/* Submit */}
              <button
                id="analyze-btn"
                type="submit"
                disabled={isLoading || !vcfFile}
                className={`w-full py-4 rounded-2xl font-bold text-base transition-all duration-300 flex items-center justify-center gap-3
                  ${isLoading || !vcfFile
                    ? 'bg-gray-800/50 text-gray-600 cursor-not-allowed border border-gray-700/30'
                    : 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white shadow-lg hover:shadow-indigo-500/25 pulse-glow'}`}
              >
                {isLoading ? (
                  <>
                    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Analyzing Genome...
                  </>
                ) : (
                  <>
                    <span>🔬</span>
                    Analyze Pharmacogenomics
                  </>
                )}
              </button>

              {/* Network status hint */}
              <p className="text-xs text-center text-gray-600">
                Requires local services on port 3001 (Node) + 8000 (Python)
              </p>
            </form>

            {/* How it works */}
            <div className="mt-6 glass-card rounded-2xl p-5 space-y-3">
              <h4 className="text-sm font-semibold text-gray-300">How it works</h4>
              {[
                { step: '1', text: 'VCF parsed for GENE, STAR, RS tags' },
                { step: '2', text: 'CPIC rule engine determines risk' },
                { step: '3', text: 'GPT-4 explains — never decides — risk' },
                { step: '4', text: 'Strict JSON schema output returned' },
              ].map(({ step, text }) => (
                <div key={step} className="flex items-center gap-3 text-sm">
                  <span className="w-5 h-5 rounded-full bg-indigo-500/20 text-indigo-400 text-xs font-bold flex items-center justify-center flex-shrink-0">{step}</span>
                  <span className="text-gray-400">{text}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Right: Results */}
          <div className="lg:col-span-2 space-y-6">
            {/* Loading state */}
            {isLoading && (
              <div className="glass-card rounded-2xl p-8 text-center">
                <div className="flex justify-center mb-6">
                  <div className="relative">
                    <div className="w-20 h-20 rounded-full border-4 border-indigo-500/20 border-t-indigo-500 animate-spin"></div>
                    <div className="absolute inset-0 flex items-center justify-center text-2xl">🧬</div>
                  </div>
                </div>
                <h3 className="text-xl font-bold text-white mb-2">Analyzing your genome...</h3>
                <p className="text-gray-400 text-sm mb-6">Parsing VCF → Running CPIC rules → Generating AI explanation</p>
                <div className="space-y-3 max-w-sm mx-auto">
                  {['Parsing VCF file', 'Applying CPIC rules', 'Computing risk scores', 'Generating explanation'].map((step, i) => (
                    <div key={step} className="flex items-center gap-3">
                      <div className="loading-shimmer w-full h-2 rounded-full"></div>
                      <span className="text-xs text-gray-500 whitespace-nowrap">{step}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Error Display */}
            {error && !isLoading && (
              <ErrorPanel error={error.error} detail={error.detail} onDismiss={() => setError(null)} />
            )}

            {/* Summary banner */}
            {hasResults && !isLoading && riskCounts && (
              <div className="glass-card rounded-2xl p-5">
                <div className="flex items-center justify-between flex-wrap gap-4">
                  <div>
                    <h3 className="text-lg font-bold text-white mb-1">Analysis Complete</h3>
                    <p className="text-sm text-gray-400">
                      {results!.length} drug{results!.length !== 1 ? 's' : ''} analyzed •{' '}
                      {results![0]?.patient_id}
                    </p>
                  </div>
                  <div className="flex gap-3">
                    {riskCounts.safe > 0 && (
                      <div className="text-center px-4 py-2 rounded-xl risk-safe">
                        <p className="text-xl font-bold">{riskCounts.safe}</p>
                        <p className="text-xs font-semibold">Safe</p>
                      </div>
                    )}
                    {riskCounts.adjust > 0 && (
                      <div className="text-center px-4 py-2 rounded-xl risk-adjust">
                        <p className="text-xl font-bold">{riskCounts.adjust}</p>
                        <p className="text-xs font-semibold">Adjust</p>
                      </div>
                    )}
                    {riskCounts.danger > 0 && (
                      <div className="text-center px-4 py-2 rounded-xl risk-toxic">
                        <p className="text-xl font-bold">{riskCounts.danger}</p>
                        <p className="text-xs font-semibold">Danger</p>
                      </div>
                    )}
                  </div>
                </div>

                {/* JSON toggle + quick action buttons */}
                <div className="mt-4 pt-4 border-t border-white/5 flex flex-wrap gap-3">
                  <button
                    id="toggle-json-btn"
                    onClick={() => setShowJson(!showJson)}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all
                      bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-indigo-300"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                    </svg>
                    {showJson ? 'Hide' : 'View'} JSON
                  </button>

                  {/* Download report.json */}
                  <button
                    id="download-report-btn"
                    onClick={() => {
                      const blob = new Blob([JSON.stringify(rawResponse, null, 2)], { type: 'application/json' });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement('a');
                      a.href = url; a.download = 'report.json'; a.click();
                      URL.revokeObjectURL(url);
                    }}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all
                      bg-emerald-600/20 hover:bg-emerald-600/40 border border-emerald-500/30 text-emerald-300"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Download report.json
                  </button>

                  {/* Copy JSON to clipboard */}
                  <button
                    id="copy-report-btn"
                    onClick={async () => {
                      const text = JSON.stringify(rawResponse, null, 2);
                      try { await navigator.clipboard.writeText(text); }
                      catch { const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); }
                      setCopyDone(true);
                      setTimeout(() => setCopyDone(false), 2000);
                    }}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all
                      bg-sky-600/20 hover:bg-sky-600/40 border border-sky-500/30 text-sky-300"
                  >
                    {copyDone ? (
                      <><svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg> Copied!</>
                    ) : (
                      <><svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg> Copy JSON</>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* JSON Viewer — shows schema-compliant results array */}
            {showJson && rawResponse && !isLoading && (
              <JsonViewer data={rawResponse} title="report.json — RIFT 2026 Schema" />
            )}

            {/* Risk Cards */}
            {hasResults && !isLoading && (
              <div className="space-y-6">
                {results!.map((result, i) => (
                  <RiskCard key={`${result.drug}-${i}`} result={result} />
                ))}
              </div>
            )}

            {/* Empty state */}
            {!isLoading && !results && !error && (
              <div className="glass-card rounded-2xl p-12 text-center">
                <div className="text-6xl mb-6">🧬</div>
                <h3 className="text-xl font-bold text-gray-200 mb-3">Ready for Analysis</h3>
                <p className="text-gray-500 text-sm max-w-md mx-auto">
                  Upload a VCF v4.2 file and select the drugs you want to analyze.
                  The system will identify pharmacogenomic variants and predict drug-specific risks.
                </p>
                <div className="grid grid-cols-3 gap-3 mt-8 max-w-sm mx-auto text-center">
                  {[
                    { icon: '📄', label: 'VCF v4.2', sub: 'File format' },
                    { icon: '🔬', label: 'CPIC Rules', sub: 'Risk engine' },
                    { icon: '🤖', label: 'GPT-4', sub: 'Explanation' },
                  ].map(({ icon, label, sub }) => (
                    <div key={label} className="p-3 rounded-xl bg-gray-900/40 border border-white/5">
                      <div className="text-2xl mb-1">{icon}</div>
                      <p className="text-xs font-semibold text-gray-300">{label}</p>
                      <p className="text-xs text-gray-600">{sub}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="mt-20 border-t border-white/5 py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-4 text-sm text-gray-600">
            <p>
              <span className="text-gray-400 font-semibold">PharmaGuard</span> – RIFT 2026 Hackathon Entry |
              Pharmacogenomics / Explainable AI Track
            </p>
            <div className="flex gap-4 font-mono text-xs">
              {['CPIC v2.0', 'VCF v4.2', 'GPT-4', 'Next.js 15', 'FastAPI'].map(t => (
                <span key={t} className="px-2 py-1 rounded bg-gray-900/60 border border-white/5">{t}</span>
              ))}
            </div>
          </div>
        </div>
      </footer>
    </main>
  );
}
