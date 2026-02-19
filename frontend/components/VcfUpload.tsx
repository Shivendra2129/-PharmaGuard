'use client';

import React, { useCallback, useRef, useState } from 'react';

interface VcfUploadProps {
    onFileAccepted: (file: File) => void;
    disabled?: boolean;
}

const VcfUpload: React.FC<VcfUploadProps> = ({ onFileAccepted, disabled = false }) => {
    const [fileInfo, setFileInfo] = useState<{ name: string; size: string } | null>(null);
    const [validationError, setValidationError] = useState<string | null>(null);
    const [isDragActive, setIsDragActive] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    const processFile = useCallback(
        (file: File) => {
            setValidationError(null);

            // Size check
            if (file.size > 50 * 1024 * 1024) {
                setValidationError('File too large. Maximum size is 50MB.');
                return;
            }

            const sizeKB = (file.size / 1024).toFixed(1);

            const reader = new FileReader();
            reader.onload = (e) => {
                const content = e.target?.result as string;

                if (!content || content.trim() === '') {
                    setValidationError('File is empty.');
                    setFileInfo(null);
                    return;
                }

                // VCF header validation
                if (!content.trimStart().startsWith('##fileformat=VCF')) {
                    setValidationError('Invalid VCF format. File must start with ##fileformat=VCF header.');
                    setFileInfo(null);
                    return;
                }

                if (!content.includes('#CHROM')) {
                    setValidationError('Invalid VCF format. Missing #CHROM header line.');
                    setFileInfo(null);
                    return;
                }

                setFileInfo({ name: file.name, size: `${sizeKB} KB` });
                setValidationError(null);
                onFileAccepted(file);
            };
            reader.onerror = () => {
                setValidationError('Could not read file. Please try again.');
                setFileInfo(null);
            };
            reader.readAsText(file);
        },
        [onFileAccepted]
    );

    // ── Drag & Drop handlers ──────────────────────────────────────────────────

    const handleDragEnter = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (!disabled) setIsDragActive(true);
    };

    const handleDragLeave = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        // Only leave if we actually left the drop zone (not just moved over a child)
        if (e.currentTarget.contains(e.relatedTarget as Node)) return;
        setIsDragActive(false);
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (!disabled) setIsDragActive(true);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragActive(false);
        if (disabled) return;

        const files = Array.from(e.dataTransfer.files);
        if (files.length === 0) return;
        processFile(files[0]);
    };

    // ── Click-to-browse handler ───────────────────────────────────────────────

    const handleClick = () => {
        if (!disabled && inputRef.current) {
            inputRef.current.value = ''; // reset so same file can be re-selected
            inputRef.current.click();
        }
    };

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (files && files.length > 0) {
            processFile(files[0]);
        }
    };

    // ── State-based styles ────────────────────────────────────────────────────

    const borderClass = validationError
        ? 'border-red-500/60 bg-red-500/5'
        : fileInfo
            ? 'border-emerald-500/60 bg-emerald-500/5'
            : isDragActive
                ? 'border-indigo-400 bg-indigo-500/10 shadow-[0_0_30px_rgba(99,102,241,0.2)]'
                : 'border-indigo-500/30 hover:border-indigo-500/60 hover:bg-indigo-500/5';

    return (
        <div>
            {/* Hidden native file input — accepts everything, validation done in JS */}
            <input
                ref={inputRef}
                id="vcf-file-input"
                type="file"
                className="hidden"
                onChange={handleInputChange}
                accept=".vcf,.txt,.tsv,text/plain,application/octet-stream"
            />

            {/* Drop zone */}
            <div
                id="vcf-dropzone"
                role="button"
                tabIndex={disabled ? -1 : 0}
                aria-label="Upload VCF file"
                onClick={handleClick}
                onKeyDown={(e) => e.key === 'Enter' && handleClick()}
                onDragEnter={handleDragEnter}
                onDragLeave={handleDragLeave}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                className={`relative rounded-2xl p-10 text-center cursor-pointer
          border-2 transition-all duration-300 select-none
          ${borderClass}
          ${disabled ? 'opacity-50 cursor-not-allowed pointer-events-none' : ''}
        `}
            >
                {/* Icon */}
                <div className="flex justify-center mb-4">
                    {fileInfo && !validationError ? (
                        <div className="w-16 h-16 rounded-2xl bg-emerald-500/20 flex items-center justify-center">
                            <svg className="w-8 h-8 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                    ) : validationError ? (
                        <div className="w-16 h-16 rounded-2xl bg-red-500/20 flex items-center justify-center">
                            <svg className="w-8 h-8 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                    d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                        </div>
                    ) : (
                        <div className={`w-16 h-16 rounded-2xl bg-indigo-500/20 flex items-center justify-center
              transition-transform duration-300 ${isDragActive ? 'scale-110' : ''}`}>
                            <svg className="w-8 h-8 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                            </svg>
                        </div>
                    )}
                </div>

                {/* Text */}
                {fileInfo && !validationError ? (
                    <div>
                        <p className="text-emerald-400 font-semibold text-lg mb-1">✓ VCF File Ready</p>
                        <p className="text-gray-300 font-medium">{fileInfo.name}</p>
                        <p className="text-gray-500 text-sm mt-1">{fileInfo.size} · Click or drag to replace</p>
                    </div>
                ) : validationError ? (
                    <div>
                        <p className="text-red-400 font-semibold text-lg mb-2">Invalid File</p>
                        <p className="text-red-300 text-sm mb-3">{validationError}</p>
                        <p className="text-gray-500 text-sm">Click or drag to try again</p>
                    </div>
                ) : (
                    <div>
                        <p className="text-gray-200 font-semibold text-lg mb-2">
                            {isDragActive ? '📂 Drop your VCF file here!' : 'Drag & drop your VCF file'}
                        </p>
                        <p className="text-gray-500 text-sm mb-4">or click to browse files</p>
                        <div className="flex flex-wrap gap-2 justify-center">
                            {['VCF v4.2', 'CYP2D6', 'CYP2C19', 'CYP2C9', 'SLCO1B1', 'TPMT', 'DPYD'].map((tag) => (
                                <span key={tag}
                                    className="px-2 py-1 text-xs font-mono bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 rounded-md">
                                    {tag}
                                </span>
                            ))}
                        </div>
                        <p className="text-gray-600 text-xs mt-4">Max 50 MB · .vcf or .txt</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default VcfUpload;
