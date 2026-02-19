'use client';

import React from 'react';

interface ErrorPanelProps {
    error: string;
    detail?: string;
    onDismiss?: () => void;
}

const ErrorPanel: React.FC<ErrorPanelProps> = ({ error, detail, onDismiss }) => {
    const errorMessages: Record<string, string> = {
        invalid_vcf_format: 'The uploaded file does not appear to be a valid VCF file.',
        missing_file: 'No VCF file was provided for analysis.',
        missing_drugs: 'No drug names were specified.',
        unsupported_drug: 'One or more specified drugs are not supported.',
        genomics_service_unavailable: 'The genomics analysis service is unavailable.',
        network_error: 'Could not connect to the analysis service.',
        rate_limit_exceeded: 'Too many requests. Please wait before trying again.',
        internal_error: 'An unexpected server error occurred.',
    };

    const humanMessage = errorMessages[error] || detail || 'An unexpected error occurred.';

    return (
        <div
            id="error-panel"
            className="glass-card rounded-2xl border border-red-700/40 bg-gradient-to-br from-red-950/50 to-gray-900/60 p-6"
            role="alert"
        >
            <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-xl bg-red-500/20 flex items-center justify-center flex-shrink-0">
                    <svg className="w-5 h-5 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                </div>
                <div className="flex-1 min-w-0">
                    <h4 className="text-red-400 font-bold text-base mb-1">Analysis Error</h4>
                    <p className="text-gray-300 text-sm mb-2">{humanMessage}</p>
                    {detail && detail !== humanMessage && (
                        <details className="mt-2">
                            <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-400">Technical details</summary>
                            <p className="mt-2 text-xs font-mono text-red-300/70 bg-red-950/40 rounded-lg p-3 break-words">
                                [{error}]: {detail}
                            </p>
                        </details>
                    )}
                </div>
                {onDismiss && (
                    <button
                        onClick={onDismiss}
                        id="dismiss-error-btn"
                        className="flex-shrink-0 text-gray-500 hover:text-gray-300 transition-colors"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                )}
            </div>
        </div>
    );
};

export default ErrorPanel;
