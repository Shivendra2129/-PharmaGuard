/**
 * PharmaGuard - Node.js Express Backend
 * Acts as orchestration layer, proxy, and rate limiter for the Python genomics service.
 */
require('dotenv').config({ path: require('path').join(__dirname, '..', '.env') });

const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const rateLimit = require('express-rate-limit');
const fileUpload = require('express-fileupload');
const axios = require('axios');
const FormData = require('form-data');
const { v4: uuidv4 } = require('uuid');

const app = express();
const PORT = process.env.PORT || 3001;
const GENOMICS_URL = process.env.GENOMICS_SERVICE_URL || 'http://localhost:8000';

// Security middleware
app.use(helmet({
    crossOriginResourcePolicy: { policy: "cross-origin" }
}));

// CORS
const corsOrigins = (process.env.CORS_ORIGINS || 'http://localhost:3000').split(',');
app.use(cors({
    origin: (origin, callback) => {
        if (!origin || corsOrigins.includes(origin) || process.env.NODE_ENV === 'development') {
            callback(null, true);
        } else {
            callback(new Error('Not allowed by CORS'));
        }
    },
    credentials: true
}));

// Request logging
app.use(morgan(process.env.NODE_ENV === 'production' ? 'combined' : 'dev'));

// Rate limiting
const limiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 100,
    message: { error: 'rate_limit_exceeded', detail: 'Too many requests, please try again later.' }
});
app.use('/api/', limiter);

// Body parsing
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// File upload middleware
app.use(fileUpload({
    limits: { fileSize: 50 * 1024 * 1024 }, // 50MB limit
    abortOnLimit: true,
    responseOnLimit: 'VCF file too large (max 50MB)',
    useTempFiles: false,
    debug: false
}));

// ─── Health Check ───────────────────────────────────────────────────────────

app.get('/health', async (req, res) => {
    let genomicsStatus = 'unknown';
    try {
        const r = await axios.get(`${GENOMICS_URL}/health`, { timeout: 3000 });
        genomicsStatus = r.data.status || 'healthy';
    } catch {
        genomicsStatus = 'unavailable';
    }

    res.json({
        status: 'healthy',
        service: 'PharmaGuard Node Backend',
        version: '1.0.0',
        timestamp: new Date().toISOString(),
        dependencies: {
            genomics_service: genomicsStatus
        }
    });
});

// ─── Analysis Endpoint ──────────────────────────────────────────────────────

app.post('/api/analyze', async (req, res) => {
    const requestId = uuidv4();

    // Validate file upload
    if (!req.files || !req.files.vcf_file) {
        return res.status(400).json({
            error: 'missing_file',
            detail: 'No VCF file provided. Please upload a .vcf file.',
            request_id: requestId,
            timestamp: new Date().toISOString()
        });
    }

    const vcfFile = req.files.vcf_file;
    const drugs = req.body.drugs || req.body.drug || '';
    const patientId = req.body.patient_id || `PATIENT_${requestId.slice(0, 6).toUpperCase()}`;

    // Validate drugs field
    if (!drugs || drugs.trim() === '') {
        return res.status(400).json({
            error: 'missing_drugs',
            detail: 'No drugs specified. Please provide comma-separated drug names.',
            patient_id: patientId,
            request_id: requestId,
            timestamp: new Date().toISOString()
        });
    }

    // Validate VCF content has proper header (quick check)
    const vcfContent = vcfFile.data.toString('utf8');
    if (!vcfContent.startsWith('##fileformat=VCF')) {
        return res.status(422).json({
            error: 'invalid_vcf_format',
            detail: 'File does not appear to be a valid VCF file. First line must start with ##fileformat=VCF',
            patient_id: patientId,
            request_id: requestId,
            timestamp: new Date().toISOString()
        });
    }

    try {
        // Forward to Python genomics service
        const formData = new FormData();
        formData.append('vcf_file', vcfFile.data, {
            filename: vcfFile.name || 'upload.vcf',
            contentType: 'text/plain'
        });
        formData.append('drugs', drugs);
        formData.append('patient_id', patientId);

        const response = await axios.post(`${GENOMICS_URL}/analyze`, formData, {
            headers: {
                ...formData.getHeaders()
            },
            timeout: 60000, // 60s timeout for LLM calls
            maxContentLength: Infinity,
            maxBodyLength: Infinity
        });

        // Add metadata to response
        const results = Array.isArray(response.data) ? response.data : [response.data];

        res.json({
            success: true,
            request_id: requestId,
            results: results,
            total_drugs_analyzed: results.length,
            timestamp: new Date().toISOString()
        });

    } catch (err) {
        // Handle Python service errors
        if (err.response) {
            const status = err.response.status;
            const data = err.response.data;
            return res.status(status).json({
                error: data.error || 'genomics_service_error',
                detail: data.detail || 'Genomics service returned an error',
                patient_id: patientId,
                request_id: requestId,
                timestamp: new Date().toISOString()
            });
        }

        if (err.code === 'ECONNREFUSED' || err.code === 'ENOTFOUND') {
            return res.status(503).json({
                error: 'genomics_service_unavailable',
                detail: `Cannot connect to genomics service at ${GENOMICS_URL}. Ensure the Python service is running.`,
                request_id: requestId,
                timestamp: new Date().toISOString()
            });
        }

        return res.status(500).json({
            error: 'internal_error',
            detail: `Unexpected error: ${err.message}`,
            request_id: requestId,
            timestamp: new Date().toISOString()
        });
    }
});

// ─── Supported Drugs & Genes ─────────────────────────────────────────────────

app.get('/api/supported-drugs', async (req, res) => {
    try {
        const r = await axios.get(`${GENOMICS_URL}/supported-drugs`, { timeout: 5000 });
        res.json(r.data);
    } catch {
        res.json({
            supported_drugs: ['CODEINE', 'WARFARIN', 'CLOPIDOGREL', 'SIMVASTATIN', 'AZATHIOPRINE', 'FLUOROURACIL'],
            drug_gene_map: {
                CODEINE: 'CYP2D6', WARFARIN: 'CYP2C9', CLOPIDOGREL: 'CYP2C19',
                SIMVASTATIN: 'SLCO1B1', AZATHIOPRINE: 'TPMT', FLUOROURACIL: 'DPYD'
            }
        });
    }
});

app.get('/api/supported-genes', async (req, res) => {
    try {
        const r = await axios.get(`${GENOMICS_URL}/supported-genes`, { timeout: 5000 });
        res.json(r.data);
    } catch {
        res.json({ supported_genes: ['CYP2D6', 'CYP2C19', 'CYP2C9', 'SLCO1B1', 'TPMT', 'DPYD'] });
    }
});

// ─── Error Handler ───────────────────────────────────────────────────────────

app.use((err, req, res, next) => {
    console.error('[Error]', err.message);
    res.status(500).json({
        error: 'server_error',
        detail: err.message,
        timestamp: new Date().toISOString()
    });
});

app.use((req, res) => {
    res.status(404).json({ error: 'not_found', detail: `Route ${req.method} ${req.path} not found` });
});

// ─── Start Server ────────────────────────────────────────────────────────────

app.listen(PORT, () => {
    console.log(`✅ PharmaGuard Node Backend running at http://localhost:${PORT}`);
    console.log(`📡 Genomics Service URL: ${GENOMICS_URL}`);
    console.log(`🔒 Environment: ${process.env.NODE_ENV || 'development'}`);
});

module.exports = app;
