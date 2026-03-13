# Bioinformatics Platform

A full-stack, visual bioinformatics pipeline execution platform. Drag-and-drop a pipeline on a canvas, upload your genomic data, pay per run, and get results — all in the browser.

---

## What It Does

- **Visual pipeline builder** — drag nodes onto a canvas, connect them, and run
- **nf-core/sarek** — variant calling (GATK HaplotypeCaller, DeepVariant, Strelka2, FreeBayes) — primary MVP workflow
- **nf-core pipelines** — rnaseq, atacseq, methylseq, ampliseq, chipseq, fetchngs
- **Snakemake workflows** — 4700+ community workflows + 454 wrappers
- **BioScript** — custom bash script runs inside a Docker image pre-loaded with bio tools
- **Mutation Assessment** — post-sarek pipeline: annotates VCF variants against 17 public databases and generates a PDF report
- **Paired-end FASTQ** — upload R1 + R2 and both get passed to the runner
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
- 8 GB RAM available for Docker (4 GB minimum)

### Start (demo / debug mode — no AWS, no Stripe needed)

```bash
git clone <your-repo-url>
cd bioinformatics_platform
docker compose up
```

Wait for:

```
backend-1  | INFO:     Application startup complete.
frontend-1 | ➜  Local:   http://localhost:5173/
```

| Service | URL |
|---------|-----|
| App | http://localhost:5173 |
| API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |

Register an account on first visit. Everything works out of the box:

- **Storage** → files saved to a local Docker volume (`/uploads`)
- **sarek / nf-core** → mock runner returns realistic fake results in ~10 s
- **Snakemake / BioScript / Custom** → mock runners, no tools installed
- **Assessment pipeline** → fully real (queries ClinVar, gnomAD, CADD, etc. live over the internet)
- **Payments** → Stripe is optional; you can create jobs directly via the API without a Stripe key

### Running modes

There are three modes for the sarek/Nextflow runner, controlled by `NEXTFLOW_BACKEND`:

| Mode | `NEXTFLOW_BACKEND` | What happens | When to use |
|------|-------------------|-------------|-------------|
| **Mock** (default) | `mock` | Returns realistic fake VCF/MultiQC data in ~10 s | Demos, UI development, debugging |
| **Local** | `local` | Runs real `nf-core/sarek` via Docker on your machine | Testing the real pipeline locally |
| **AWS** | `aws` | Submits to AWS Batch | Production |

To switch modes without editing files, set the variable before `docker compose up`:

```bash
# Demo mode (default — no setup needed)
docker compose up

# Real local sarek (needs ~100 GB GATK reference files — see below)
NEXTFLOW_BACKEND=local docker compose up
```

### Running real sarek locally

`NEXTFLOW_BACKEND=local` runs the actual nf-core/sarek pipeline on your laptop/server via Docker. Requirements:

1. **Docker** with at least 16 GB RAM allocated and 200 GB free disk.
2. **GATK reference bundle** — download GRCh38 resources (~100 GB):
   ```bash
   # The pipeline will auto-download on first run via nf-core's iGenomes config.
   # Or pre-download to a local path and override --genome with a custom genomes.conf.
   ```
3. Set in `.env`:
   ```
   NEXTFLOW_BACKEND=local
   NEXTFLOW_PROFILE=docker   # or singularity
   ```
4. The first run pulls all the nf-core/sarek Docker images (~20 GB). Subsequent runs are fast.

> **Tip:** For MVP demos, always use mock mode. It's instant and shows the full UI/results flow without any data files.

### Stop

```bash
docker compose down          # keep database volumes
docker compose down -v       # full reset (wipes all data)
```

### Useful commands

```bash
# View all logs
docker compose logs -f

# View only worker (where pipeline jobs run)
docker compose logs -f worker

# TypeScript type-check (runs inside container)
docker compose exec frontend sh -c "cd /app && npx tsc --noEmit"

# Open a backend Python shell
docker compose exec backend bash

# Run backend tests
docker compose exec backend pytest tests/ -v

# Restart just the worker (after code changes)
docker compose restart worker
```

### Troubleshooting

| Problem | Fix |
|---------|-----|
| Port 5432 already in use | Stop local Postgres, or change `5432:5432` to `5433:5432` in docker-compose.yml |
| Port 6380 already in use | Change `6380:6379` to another port |
| Assessment job fails with network errors | The assessment runner calls live public APIs — check your internet connection |
| `nextflow: not found` in worker logs | Only relevant when `NEXTFLOW_BACKEND=local`; Nextflow is pre-installed in `Dockerfile.worker` |
| Jobs stuck in `pending` | Worker container crashed — run `docker compose logs worker` to see why |

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
│   │   │   ├── nextflow/          # mock.py + batch.py (AWS Batch)
│   │   │   ├── snakemake/         # mock.py + batch.py (AWS Batch)
│   │   │   ├── bioscript/         # mock.py + batch.py (AWS Batch)
│   │   │   ├── assessment/        # real.py + databases.py + report.py
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
│   │   │   ├── nodes/             # InputFileNode, AssessmentNode, BioScriptNode,
│   │   │   │   │                  #   NfCoreModuleNode, NfCorePipelineNode,
│   │   │   │   │                  #   SnakemakeWrapperNode, SnakemakeWorkflowNode, …
│   │   │   ├── PipelineBuilder.tsx
│   │   │   ├── PipelineToolbar.tsx
│   │   │   ├── NodePalette.tsx
│   │   │   ├── Spotlight.tsx      # Cmd+K command palette
│   │   │   ├── TemplateGallery.tsx
│   │   │   ├── templates.ts       # pipeline templates incl. sarek + assessment
│   │   │   ├── validation.ts
│   │   │   └── useUndoRedo.ts
│   │   ├── components/            # AuthGate, TierConfirm, JobProgress,
│   │   │   │                      #   JobHistory, ResultsPanel, ResultViewer, …
│   │   ├── types/                 # job.ts, auth.ts, snakemake.ts, …
│   │   └── App.tsx                # Top-level state machine
│   └── package.json
│
├── .env.example                   # Copy to .env — all configurable variables
└── docker-compose.yml
```

---

## Pipeline Runners

| `pipeline_id` | Runner | Backend env var | Notes |
|---------------|--------|----------------|-------|
| `"sarek"` | Nextflow | `NEXTFLOW_BACKEND=mock\|local\|aws` | nf-core variant calling; auto-generates samplesheet |
| other nf-core | Nextflow | `NEXTFLOW_BACKEND=mock\|local\|aws` | rnaseq, atacseq, etc. |
| `"snakemake"` | Snakemake | `SNAKEMAKE_BACKEND=mock\|aws` | Generates Snakefile from canvas wrappers |
| `"bioscript"` | BioScript | `BIOSCRIPT_BACKEND=mock\|aws` | Runs user's bash script in tools Docker image |
| `"assessment"` | Assessment | always real | Annotates sarek VCF against 17 databases; generates PDF |

---

## Mutation Assessment Pipeline

The Assessment pipeline takes a completed sarek job's VCF output and annotates every variant against 17 public databases. No API key is required for 15 of them; OMIM and Orphanet are optional enhancements.

### How to use

1. Run a sarek job first (or select a completed one).
2. Drop an **Assessment** node on the canvas and connect it to the sarek Results node.
3. In the Assessment node, pick the source sarek job from the dropdown.
4. Submit — no file upload needed. The runner reads variants directly from the sarek job's stored result.
5. Results: interactive variant table in the UI + downloadable PDF report.

### PDF report contents

- **Summary stats** — total variants, pathogenic/LP count, cancer hotspot count
- **Classification chart** — bar chart by ACMG bucket
- **Table A — Clinical Summary** — ClinVar significance, InterVar/ACMG classification + criteria met, gnomAD AF, popmax AF, hotspot flag, rsID
- **Table B — Computational Scores** — SIFT, PolyPhen-2, CADD phred, REVEL, MetaLR, MetaSVM, MutationTaster, SpliceAI Δmax, GERP++, PhyloP
- **Table C — Gene Annotations** — protein name + function (UniProt), OMIM disease, ClinGen validity, GenCC, Orphanet diseases, HPO phenotype terms, LOVD variant count
- **Data sources** and **research-use disclaimer**

### Database sources — full reference

#### Variant-level (queried per variant, all free, no key)

| # | Database | What it provides | API endpoint |
|---|----------|-----------------|--------------|
| 1 | **ClinVar** (NCBI) | Pathogenicity classification, gene symbol, HGVS notation | `eutils.ncbi.nlm.nih.gov/entrez/eutils` |
| 2 | **gnomAD v4.1** | Population allele frequency, popmax AF across continental groups, AC/AN | `gnomad.broadinstitute.org/api` (GraphQL) |
| 3 | **Ensembl VEP** | SIFT score + prediction, PolyPhen-2 score + prediction, consequence terms, canonical transcript, HGVS | `rest.ensembl.org/vep/human/region` |
| 4 | **CADD v1.7** | Phred-scaled combined annotation-dependent depletion score (≥20 = top 1% deleterious) | `cadd.gs.washington.edu/api/v1.0` |
| 5 | **MyVariant.info** | REVEL, MetaLR, MetaSVM, MutationTaster (pred + score), GERP++ rs score, PhyloP — all from dbNSFP | `myvariant.info/v1/variant` |
| 6 | **SpliceAI** (Broad) | Splice site disruption Δ scores: acceptor gain/loss, donor gain/loss; max Δ ≥ 0.2 is significant | `spliceailookup-api.broadinstitute.org/spliceai` |
| 7 | **InterVar** (WinterVar) | ACMG/AMP 2015 auto-classification (Pathogenic/LP/VUS/LB/Benign) + list of met criteria (PVS1, PS1-4, PM1-6…) | `wintervar.wglab.org/api2.php` |
| 8 | **CancerHotspots.org** | Recurrent cancer driver mutation hotspot flag + type | `cancerhotspots.org/api/hotspots/single` |
| 9 | **dbSNP** (NCBI) | rsID — used as fallback if ClinVar and gnomAD don't return one | `eutils.ncbi.nlm.nih.gov/entrez/eutils` |

#### Gene-level (queried once per unique gene, cached, all free, no key)

| # | Database | What it provides | API endpoint |
|---|----------|-----------------|--------------|
| 10 | **UniProt** | Protein full name, function description (first sentence) | `rest.uniprot.org/uniprotkb/search` |
| 11 | **HGNC** | Authoritative gene symbol, locus group/type, Entrez ID, Ensembl gene ID, gene family | `rest.genenames.org/fetch/symbol` |
| 12 | **ClinGen** | Gene-disease validity: Definitive / Strong / Moderate / Limited / No Known Disease, mode of inheritance | `erepo.clinicalgenome.org/evrepo/api/v1/classifications` |
| 13 | **GenCC** | Aggregated gene-disease classifications from ClinGen, OMIM, Orphanet, PanelApp, and others | `thegencc.org/api/v1/classifications-search` |
| 14 | **HPO / Ensembl** | Human Phenotype Ontology terms and disease phenotypes associated with the gene | `rest.ensembl.org/phenotype/gene/homo_sapiens` |
| 15 | **LOVD** | Locus-specific variant database — total variant count for the gene | `api.lovd.nl/v1.0/variants` |

#### Optional gene-level (require free registration)

| # | Database | What it provides | How to enable |
|---|----------|-----------------|---------------|
| 16 | **OMIM** | Gene-disease relationship, preferred disease title, inheritance pattern | Register at [omim.org/api](https://www.omim.org/api), set `OMIM_API_KEY=` in `.env` |
| 17 | **Orphanet** | Rare disease associations for the gene (up to 5 diseases with ORPHAcode) | Register at [orphacode.org](https://api.orphacode.org), set `ORPHANET_API_KEY=` in `.env` |

### Databases that can be added via bulk download (not yet integrated)

These are not queried live but can be incorporated as local flat-file lookups in a future version:

| Database | What it adds | How to download | Notes |
|----------|-------------|-----------------|-------|
| **dbNSFP** | Full dbNSFP scores offline (REVEL, MetaLR, MetaSVM, PROVEAN, SIFT, PolyPhen, MutationTaster, etc.) for every possible SNV | [sites.google.com/site/jpopgen/dbNSFP](https://sites.google.com/site/jpopgen/dbNSFP) | ~100 GB; academic free; useful for offline / air-gapped deployments |
| **DGV** (Database of Genomic Variants) | Structural variant population database | [dgv.tcag.ca/dgv/app/downloads](http://dgv.tcag.ca/dgv/app/downloads) | BED/VCF for GRCh38; free |
| **MONDO** | Disease ontology — maps disease names across OMIM, Orphanet, DOID, MeSH | [github.com/monarch-initiative/mondo](https://github.com/monarch-initiative/mondo) | OBO + JSON format; free |
| **DECIPHER** | Rare disease genomic variants + patient phenotypes | Apply at [decipher.sanger.ac.uk/data](https://decipher.sanger.ac.uk/data) | Data Access Agreement required; free for research |
| **HGMD** (Human Gene Mutation Database) | Comprehensive curated disease-causing mutations | [portal.biobase-international.com](https://portal.biobase-international.com) | Commercial licence; academic pricing available |
| **MaxEntScan** | Splice site strength scoring algorithm | [genes.mit.edu/burgelab/maxent/Xmaxentscan_scoreseq.html](http://genes.mit.edu/burgelab/maxent/Xmaxentscan_scoreseq.html) | Perl script; run locally |

> **Note on superseded databases:** 1000 Genomes, ExAC, ESP, TOPMed, and UK10K are all population frequency databases whose data is fully incorporated into gnomAD v4.1, which we already query. No separate integration is needed.

---

## Environment Variables

All variables can be set in a `.env` file at the project root (copy from `.env.example`).

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
| `NEXTFLOW_BACKEND` | `mock` | `mock`, `local`, or `awsbatch` |
| `NEXTFLOW_PROFILE` | `docker` | `docker` or `singularity` (local mode only) |
| `SNAKEMAKE_BACKEND` | `mock` | `mock` or `awsbatch` |
| `BIOSCRIPT_BACKEND` | `mock` | `mock` or `awsbatch` |

### Mutation Assessment

| Variable | Default | Description |
|----------|---------|-------------|
| `ASSESSMENT_GENOME` | `hg38` | Genome build for gnomAD / VEP / CADD / InterVar (`hg19` or `hg38`) |
| `OMIM_API_KEY` | `` | Optional. Free academic key from [omim.org/api](https://www.omim.org/api). Enables OMIM gene-disease data in reports. |
| `ORPHANET_API_KEY` | `` | Optional. Free key from [orphacode.org](https://api.orphacode.org). Enables rare disease annotations. |

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
GET    /uploads/local/{filename}             Serve locally stored file (e.g. PDF reports)

GET    /jobs                                 List your jobs (last 50)
POST   /jobs                                 Create job + dispatch Celery task
GET    /jobs/{job_id}                        Job details + result
DELETE /jobs/{job_id}                        Cancel job
POST   /jobs/{job_id}/retry                  Retry failed/cancelled job
GET    /jobs/{job_id}/logs                   Stream log lines (?offset=N)
GET    /jobs/{job_id}/download               Presign S3 download URL (?path=s3://…)

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
