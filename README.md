# Bioinformatics Platform

A full-stack, visual bioinformatics pipeline execution platform. Drag-and-drop a pipeline on a canvas, upload your genomic data, pay per run, and get results — all in the browser.

---

## What It Does

- **Visual pipeline builder** — drag nodes onto a canvas, connect them, and run
- **HLA typing** — primary MVP workflow (HLA-HD)
- **nf-core pipelines** — rnaseq, sarek, atacseq, methylseq, ampliseq, chipseq, fetchngs
- **Snakemake workflows** — 4700+ community workflows + 454 wrappers
- **BioScript** — write a custom bash script that runs inside a Docker image pre-loaded with samtools, bwa, fastp, bcftools, STAR, featureCounts, and MultiQC
- **Paired-end FASTQ** — upload R1 + R2 and they both get passed to the runner
- **Pay-per-run billing** — Stripe checkout, cost estimated before every job
- **Live results** — volcano plots, VCF tables, MultiQC HTML, file lists — auto-detected

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Vite, @xyflow/react v12 |
| Backend | FastAPI + Uvicorn (async) |
| Job queue | Celery 5 + Redis 7 |
| Database | PostgreSQL 16 + SQLAlchemy 2 + Alembic |
| Auth | JWT (python-jose + passlib + bcrypt) |
| Payments | Stripe Checkout + Webhooks |
| Cloud runners | AWS Batch (Nextflow 24.10.2, Snakemake 8.20, custom Docker) |
| Storage | Local filesystem (dev) or AWS S3 (prod) |
| Containers | Docker + Docker Compose |

---

## Running Locally

### Prerequisites

- Docker Desktop (or Docker Engine + Docker Compose plugin)
- 4 GB RAM available for Docker

### Start

```bash
git clone <your-repo-url>
cd bioinformatics_platform
docker compose up
```

Wait for both of these lines:

```
backend-1  | INFO:     Application startup complete.
frontend-1 | ➜  Local:   http://localhost:5173/
```

| Service | URL |
|---------|-----|
| App | http://localhost:5173 |
| API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |

Register an account on first visit. All runners default to **mock mode** — no AWS credentials needed for local development.

### Stop

```bash
docker compose down          # keep database volumes
docker compose down -v       # full reset (wipes all data)
```

### Useful commands

```bash
# View logs
docker compose logs -f backend
docker compose logs -f worker

# TypeScript type-check (runs inside container)
docker compose exec frontend sh -c "cd /app && npx tsc --noEmit"

# Open a backend shell
docker compose exec backend bash
```

---

## Project Structure

```
bioinformatics_platform/
├── backend/
│   ├── alembic/versions/          # DB migrations (0001 – 0009)
│   ├── app/
│   │   ├── api/v1/                # REST routers: auth, uploads, jobs,
│   │   │   │                      #   pipelines, nfcore, snakemake, payments
│   │   ├── models/                # SQLAlchemy ORM: User, Job, Pipeline,
│   │   │   │                      #   NfCorePipeline, NfCoreModule,
│   │   │   │                      #   SnakemakeWrapper, SnakemakeWorkflow
│   │   ├── schemas/               # Pydantic request / response models
│   │   ├── services/
│   │   │   ├── storage/           # local.py + s3.py
│   │   │   ├── hla/               # mock.py (+ real hlahd stub)
│   │   │   ├── nextflow/          # mock.py + batch.py (AWS Batch)
│   │   │   ├── snakemake/         # mock.py + batch.py (AWS Batch)
│   │   │   ├── bioscript/         # mock.py + batch.py (AWS Batch)
│   │   │   ├── cost_estimator.py
│   │   │   ├── nfcore_scraper.py
│   │   │   └── snakemake_scraper.py
│   │   ├── tasks/                 # Celery tasks: pipeline, scrape_*
│   │   ├── config.py              # All env vars (Pydantic Settings)
│   │   ├── celery_app.py
│   │   └── main.py
│   ├── Dockerfile                 # FastAPI image
│   ├── Dockerfile.worker          # Celery worker (+ Java 17 + Nextflow + Snakemake)
│   ├── Dockerfile.tools           # BioScript tools image (samtools, bwa, STAR, etc.)
│   ├── bioplatform_helpers.sh     # Shell library sourced in BioScript jobs
│   ├── nextflow_aws.config        # Nextflow AWS Batch config
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── api/                   # Axios clients: client, authClient,
│   │   │   │                      #   pipelineClient, nfcoreClient, snakemakeClient
│   │   ├── builder/
│   │   │   ├── nodes/             # InputFileNode, HLATypingNode, BioScriptNode,
│   │   │   │   │                  #   NfCoreModuleNode, NfCorePipelineNode,
│   │   │   │   │                  #   SnakemakeWrapperNode, SnakemakeWorkflowNode, …
│   │   │   ├── PipelineBuilder.tsx
│   │   │   ├── PipelineToolbar.tsx
│   │   │   ├── NodePalette.tsx
│   │   │   ├── Spotlight.tsx      # Cmd+K command palette
│   │   │   ├── TemplateGallery.tsx
│   │   │   ├── templates.ts       # 8 built-in templates
│   │   │   ├── validation.ts
│   │   │   └── useUndoRedo.ts
│   │   ├── components/            # AuthGate, TierConfirm, JobProgress,
│   │   │   │                      #   JobHistory, ResultsPanel, ResultViewer, …
│   │   ├── types/                 # job.ts, auth.ts, snakemake.ts, …
│   │   └── App.tsx                # Top-level state machine
│   └── package.json
│
└── docker-compose.yml
```

---

## Node Types

| Node | Color | Purpose | Handles |
|------|-------|---------|---------|
| Input File | Blue | Upload FASTQ/BAM (supports paired-end R1+R2) | `file-out`, `file-out-r2` |
| HLA-HD Typing | Dark blue | HLA allele calling | `file-in` → `result-out` |
| FASTQ → BAM | Gray | Format converter | `fastq-in` → `bam-out` |
| Results | Green | Output viewer | `result-in` |
| nf-core Module | Amber | Individual nf-core module | dynamic `nfc-in-*` / `nfc-out-*` |
| nf-core Pipeline | Teal | Full nf-core pipeline block | `nfc-in-data` → `nfc-out-results` |
| Snakemake Wrapper | Amber-600 | Bio tool wrapper | dynamic `smk-in-*` / `smk-out-*` |
| Snakemake Workflow | Amber-900 | Community workflow | `smk-in-data` → `smk-out-results` |
| BioScript | Violet | Custom bash script | `bioscript-in` → `bioscript-out` |

---

## Pipeline Runners

| `pipeline_id` | Runner | Backend env var | Notes |
|---------------|--------|----------------|-------|
| `null` | HLA-HD | `HLA_BACKEND=mock\|hlahd` | Default when no pipeline chosen |
| `"rnaseq"`, `"sarek"`, … | Nextflow | `NEXTFLOW_BACKEND=mock\|awsbatch` | nf-core pipelines; auto-generates samplesheet |
| `"snakemake"` | Snakemake | `SNAKEMAKE_BACKEND=mock\|awsbatch` | Generates Snakefile from canvas wrappers |
| `"bioscript"` | BioScript | `BIOSCRIPT_BACKEND=mock\|awsbatch` | Runs user's bash script in tools Docker image |
| `"mixed"` | Nextflow → Snakemake | both | Canvas has both nf-core and Snakemake nodes |

---

## Environment Variables

All variables can be set in a `.env` file at the project root.

### Core (always needed)

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `bioplatform` | Database username |
| `POSTGRES_PASSWORD` | `bioplatform` | Database password |
| `POSTGRES_DB` | `bioplatform` | Database name |
| `JWT_SECRET` | `changeme-…` | **Change in production.** Min 32 random chars. |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated CORS origins |

### Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `STORAGE_BACKEND` | `local` | `local` or `s3` |
| `AWS_ACCESS_KEY_ID` | `` | Required when `STORAGE_BACKEND=s3` |
| `AWS_SECRET_ACCESS_KEY` | `` | Required when `STORAGE_BACKEND=s3` |
| `AWS_REGION` | `us-east-1` | AWS region |
| `S3_BUCKET` | `` | S3 bucket name |

### Runners

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXTFLOW_BACKEND` | `mock` | `mock` or `awsbatch` |
| `SNAKEMAKE_BACKEND` | `mock` | `mock` or `awsbatch` |
| `BIOSCRIPT_BACKEND` | `mock` | `mock` or `awsbatch` |

### AWS Batch

| Variable | Default | Description |
|----------|---------|-------------|
| `BATCH_JOB_QUEUE` | `bioplatform-default` | Batch job queue name |
| `BATCH_JOB_ROLE_ARN` | `` | IAM role ARN for Batch job containers |
| `SNAKEMAKE_BATCH_QUEUE` | `` | Snakemake queue (falls back to `BATCH_JOB_QUEUE`) |
| `SNAKEMAKE_CONTAINER_IMAGE` | `snakemake/snakemake:v8.20.0` | Snakemake Docker image |
| `BIOSCRIPT_DOCKER_IMAGE` | `bioplatform/tools:latest` | BioScript tools image |

### Stripe

| Variable | Default | Description |
|----------|---------|-------------|
| `STRIPE_SECRET_KEY` | `` | Stripe secret key (`sk_test_…` or `sk_live_…`) |
| `STRIPE_WEBHOOK_SECRET` | `` | Stripe webhook signing secret (`whsec_…`) |
| `APP_BASE_URL` | `http://localhost:5173` | Frontend URL (Stripe redirect target) |

---

## API Overview

All endpoints are under `/api/v1`. JWT required in `Authorization: Bearer <token>` header except for auth and webhook routes.

```
POST   /auth/register                        Register a new user
POST   /auth/login                           Login, get JWT token
GET    /auth/me                              Current user info

POST   /uploads/presign                      Get presigned upload URL + cost estimate
GET    /uploads/estimate                     Cost estimate by pipeline + samples

GET    /jobs                                 List your jobs (last 50)
POST   /jobs                                 Create job + dispatch Celery task
GET    /jobs/{job_id}                        Job details + result

GET    /pipelines                            List saved pipelines
POST   /pipelines                            Save pipeline graph
GET    /pipelines/{id}                       Get pipeline
PUT    /pipelines/{id}                       Update pipeline
DELETE /pipelines/{id}                       Delete pipeline

GET    /nfcore/pipelines                     nf-core pipeline catalog
GET    /nfcore/modules                       nf-core module catalog
GET    /nfcore/categories                    Module categories
GET    /nfcore/status                        Catalog status (count + ready flag)
POST   /nfcore/refresh                       Re-scrape catalog (background)

GET    /snakemake/wrappers                   Snakemake wrappers catalog
GET    /snakemake/wrapper-categories         Wrapper categories
GET    /snakemake/workflows                  Snakemake workflows catalog
GET    /snakemake/status                     Catalog status
POST   /snakemake/refresh                    Re-scrape catalog

POST   /payments/checkout                    Create Stripe checkout session
POST   /payments/webhook                     Stripe webhook (no auth — signature verified)
GET    /payments/session/{session_id}        Poll for job_id after Stripe redirect
```

---

## BioScript Shell Helpers

When using the BioScript node, the following functions are pre-loaded inside the container:

```bash
bioplatform_qc          <input.fastq.gz> <outdir> [r2.fastq.gz]
bioplatform_align       <reads.fastq.gz> <genome.fa> <outdir> [r2]
bioplatform_star_align  <reads.fastq.gz> <star_index_dir> <outdir> [r2]
bioplatform_call        <input.bam> <genome.fa> <outdir>
bioplatform_featurecount <bam> <gtf> <outdir>
bioplatform_multiqc     <results_dir> <outdir>
bioplatform_s3_sync_out <local_dir> <s3_prefix>
```

Environment variables available to every BioScript job:

```bash
$INPUT_FILE    # S3 URI of the uploaded input file
$OUTPUT_DIR    # S3 prefix where outputs should be written
$JOB_ID        # Unique job identifier
```

---

## Database Migrations

Migrations run automatically at startup (`alembic upgrade head`).

| Version | Description |
|---------|-------------|
| 0001 | Create jobs table |
| 0002 | Create pipelines table |
| 0003 | Create nf-core catalog tables |
| 0004 | Add pipeline input formats |
| 0005 | Add pipeline_id to jobs |
| 0006 | Create Snakemake catalog tables |
| 0007 | Create users table; add user_id to jobs + pipelines |
| 0008 | Add stripe_session_id to jobs |
| 0009 | Add storage_key_r2 + workflow_config to jobs |

---

## License

MIT
