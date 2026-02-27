# Bioinformatics Platform — To-Do List

> Status legend: ✅ Done · 🔲 Not Started · 💡 Idea / Future

---

## 1. Backend — Pipeline Execution Infrastructure

### 1.1 Storage
- ✅ **Local storage backend** — presigned local upload URLs, stored in `/uploads`
- ✅ **S3 storage backend** (`services/storage/s3.py`) — real presigned S3 upload URLs via boto3; `STORAGE_BACKEND=s3`

### 1.2 Compute / Runners
- ✅ **Mock EC2 backend** — fake spawn/terminate for local dev
- ✅ **AWS Batch — Nextflow runner** (`services/nextflow/batch.py`) — generates samplesheet CSV, submits `nextflow run nf-core/<pipeline>` job to Batch, polls until done, collects S3 results; `NEXTFLOW_BACKEND=awsbatch`
- ✅ **Mock Nextflow runner** (`services/nextflow/mock.py`) — per-pipeline deterministic mock results (table/vcf/files)
- ✅ **AWS Batch — Snakemake runner** (`services/snakemake/batch.py`) — generates Snakefile from workflow_config, runs `snakemake --executor aws-batch`, collects results; `SNAKEMAKE_BACKEND=awsbatch`
- ✅ **Mock Snakemake runner** (`services/snakemake/mock.py`) — 5–12s delay, BAM/VCF/MultiQC file outputs
- ✅ **AWS Batch — BioScript runner** (`services/bioscript/batch.py`) — uploads user script to S3, submits single Batch job using `BIOSCRIPT_DOCKER_IMAGE`, polls, collects results; `BIOSCRIPT_BACKEND=awsbatch`
- ✅ **Mock BioScript runner** (`services/bioscript/mock.py`) — script-keyword-aware fake outputs
- ✅ **Custom Linux pipelines** (`services/custom/`) — 5 standalone tools not on nf-core/Snakemake: SPAdes (de novo assembly), Kraken2+Bracken (metagenomics), Prokka (annotation), MAFFT+IQ-TREE 2 (phylogenomics), Flye+NanoStat (long-read assembly); `CUSTOM_BACKEND=mock|awsbatch`
- 🔲 **Real HLA-HD runner** (`services/hla/hlahd.py`) — wrap HLA-HD binary/Docker image; parse result files; `HLA_BACKEND=hlahd`
- 🔲 **Container pre-warming** — pull Singularity/Docker images before first run to reduce latency

### 1.3 Samplesheet / Input Generation
- ✅ **Samplesheet generator** — nf-core CSV for rnaseq, sarek, atacseq, methylseq, ampliseq, chipseq, fetchngs
- ✅ **Paired-end FASTQ** — R1 + R2 presign + upload, `storage_key_r2` on Job, fills `fastq_2` column in samplesheet
- 🔲 **SRA / URL input mode** — accept SRA accession (`SRR…`) or HTTPS URL; stream-download on worker via `prefetch` + `fasterq-dump`

### 1.4 Result Parsers
- ✅ **MultiQC HTML parser** — wraps HTML as `type: "html_report"`
- ✅ **Count matrix parser** — parses `*.tsv`/`*.csv` into `type: "table"`, auto-sniffs delimiter
- ✅ **VCF parser** — parses VCF lines into `type: "vcf"` (first 500 rows)
- ✅ **Generic file-list result** — `parse_file_list()` returns `type: "files"` with name/path/size/mime
- 🔲 **Result size limits** — large VCFs / count tables streamed/paginated from S3 rather than embedded in job JSON

### 1.5 Job Lifecycle
- ✅ **Job routing** — `pipeline_id=None` → HLA; `"snakemake"` → Snakemake; `"bioscript"` → BioScript; `"custom-{tool}"` → CustomRunner; `"mixed"` → Nextflow then Snakemake; other → Nextflow
- ✅ **Job cancellation** — `DELETE /api/v1/jobs/{id}`; revokes Celery task (SIGTERM); marks status `"cancelled"`
- ✅ **Job retry** — `POST /api/v1/jobs/{id}/retry`; copies failed/cancelled job fields; creates new pending job; ↺ Retry button in JobHistory
- ✅ **AWS Batch job cancellation** — `services/batch_tracker.py` stores Batch job ID in Redis; cancel endpoint calls `batch.terminate_job()` for BioScript and Custom runners
- 🔲 **Fine-grained stage tracking** — surface Nextflow process names as live steps instead of two-stage model
- ✅ **Log streaming** — `GET /api/v1/jobs/{id}/logs?offset=N` polling endpoint backed by Redis; pipeline task emits stage log lines; `JobProgress` live log pane (dark terminal, auto-scroll, Show/Hide toggle)
- 🔲 **Notifications** — email or Slack webhook when a long-running job finishes or fails

---

## 2. Frontend — Pipeline Builder

### 2.1 Canvas & Nodes
- ✅ **Drag-drop canvas** (React Flow v12) with palette sidebar
- ✅ **Node types**: InputFile, HLA-HD Typing, FASTQ→BAM, Results, nf-core Module, nf-core Pipeline, Snakemake Wrapper, Snakemake Workflow, BioScript, Custom Pipeline (teal, 5 tools)
- ✅ **Connection validation** (`isValidConnection`) — port-type aware, cross-framework rules
- ✅ **Auto-wiring** — greedy bipartite matching + topological DAG layout
- ✅ **Undo / redo** — 50-step snapshot stack (Ctrl+Z / Ctrl+Shift+Z)
- ✅ **Keyboard shortcuts** — Ctrl+S save, Ctrl+Z/Y undo/redo, Ctrl+K spotlight
- ✅ **Pipeline type badge** — HLA / nf-core / Snakemake / BioScript / Custom / Mixed
- ✅ **Pipeline templates** — 8 one-click starter templates + gallery modal
- ✅ **Cmd+K spotlight** — command palette with template search + nf-core/Snakemake catalog search
- 🔲 **Module parameter panel** — click a module → side panel showing `nextflow.config` params with inline editing
- 🔲 **Module version pinning** — select a specific nf-core module tag/version
- 🔲 **Subworkflow nodes** — nf-core subworkflows as collapsible composite nodes
- 🔲 **Dark mode** — respect `prefers-color-scheme`

### 2.2 Input File Node
- ✅ **File upload widget** with upload-progress indicator
- ✅ **Dataset ID / storage-key input mode** — type a storage key directly
- ✅ **Paired-end toggle** — R1 + R2 upload slots with `file-out-r2` handle
- 🔲 **SRA / URL input mode** — accept SRA accession or download URL
- 🔲 **Dataset library** — dropdown of past uploads so users can re-select without re-uploading

### 2.3 Results Node & Results Panel
- ✅ **Sliding results panel** — side drawer ↔ centre modal with Summary / Data / Downloads / Raw tabs
- ✅ **HLA alleles** — locus-colour-coded cards, Class I / II grouping, bar chart
- ✅ **VCF** — stat cards, donut chart, sortable/filterable table
- ✅ **Generic table** — sortable, searchable, paginated
- ✅ **File list** — file name / size / mime type renderer
- ✅ **Volcano plot** — SVG scatter for DE tables (up/down/ns colouring)
- ✅ **HTML report** — summary with View Report button (MultiQC, Snakemake report, etc.)
- ✅ **Download** — JSON / TSV / clipboard; per-file presigned S3 ⬇ button on file list (calls `GET /jobs/{id}/download?path=s3://…`)
- 🔲 **MultiQC inline iframe** — render MultiQC HTML in the Data tab instead of new tab
- 🔲 **IGV.js integration** — embed IGV.js for BAM / VCF result navigation
- 🔲 **Log viewer tab** — stream `nextflow.log` in a dark terminal pane
- 🔲 **Result sharing** — shareable read-only link to a result

### 2.4 BioScript Node
- ✅ **BioScript node** — violet, expandable textarea code editor, pre-loaded with `bioplatform_*` helper signatures
- ✅ **Custom Pipeline node** — teal (#0d9488), 5-tool dropdown (spades/kraken2/prokka/iqtree/flye), `custom-in`/`custom-out` handles
- ✅ **Shell helper library** (`bioplatform_helpers.sh`) — QC, align, STAR, variant call, featureCount, MultiQC, S3 sync; custom: spades, kraken2, prokka, iqtree, flye
- ✅ **Custom Docker image** (`Dockerfile.tools`) — samtools, bwa, fastp, bcftools, STAR, featureCounts, MultiQC, SPAdes, Kraken2, Bracken, Prokka, MAFFT, IQ-TREE 2, Flye, NanoStat

---

## 3. Catalogs

- ✅ **nf-core pipelines** — scraped from GitHub; `input_formats` from `schema_input.json`
- ✅ **nf-core modules** — scraped from GitHub with meta.yml parsing
- ✅ **Snakemake wrappers** — 454 wrappers scraped from `snakemake/snakemake-wrappers`
- ✅ **Snakemake workflows** — 4700+ community workflows from `snakemake-workflow-catalog`
- 🔲 **Incremental refresh** — re-scrape only pipelines/modules updated since `last_scraped`
- 🔲 **WorkflowHub catalog** — index CWL / Snakemake / Nextflow workflows from workflowhub.eu
- 🔲 **Module search ranking** — rank by star count + usage frequency
- 🔲 **Changelog / version info** — show latest release tag + changelog link per pipeline

---

## 4. User Accounts & History

- ✅ **Authentication** — JWT register/login, all API endpoints protected; `AuthGate` component
- ✅ **Per-user job scoping** — uploads and job list filtered by `user_id`
- ✅ **Job history page** — table of past 50 jobs with status, pipeline, tier, cost, timestamp
- ✅ **Job cancellation from history** — Cancel button on pending/running rows
- ✅ **Job retry from history** — ↺ Retry button on failed/cancelled rows; creates new job with same inputs
- 🔲 **Pipeline sharing** — mark a saved pipeline as public or share with specific users
- 🔲 **Organisation / team workspaces**
- 🔲 **Cost tracking** — accumulate real AWS costs per job; monthly spend dashboard
- 🔲 **Result sharing** — shareable read-only links

---

## 5. Payments

- ✅ **Stripe Checkout** — cost estimate before every run, redirects to Stripe hosted page
- ✅ **Stripe webhook** — `checkout.session.completed` creates job and dispatches Celery task
- ✅ **Redis metadata store** — `workflow_config` stored in Redis (1h TTL) to work around Stripe's 500-char metadata limit
- ✅ **Session polling** — `/payments/session/{id}` polls for `job_id` after Stripe redirect

---

## 6. Infrastructure & DevOps

- ✅ **Docker Compose** — postgres, redis, backend, worker, frontend
- ✅ **Alembic migrations** — 0001–0009, run automatically at startup
- ✅ **Health check endpoint** — `GET /health`
- ✅ **CORS** — configurable via `ALLOWED_ORIGINS`
- ✅ **Terraform** — `terraform/` with main.tf, variables.tf, s3.tf, iam.tf, batch.tf (SPOT compute env + 2 queues), ecr.tf, outputs.tf; `terraform apply` provisions full AWS infra
- ✅ **CI/CD pipeline** — `.github/workflows/ci.yml` (ruff + mypy + pytest + tsc + eslint + build on PR); `.github/workflows/deploy.yml` (ECR push + Alembic migration + S3+CloudFront deploy on main)
- ✅ **Rate limiting** — slowapi (`app/limiter.py`); global 200 req/min; auth register 5/min, login 10/min, job create 20/min
- 🔲 **Secrets management** — move credentials to AWS Secrets Manager / Vault
- 🔲 **Horizontal scaling** — multiple Celery workers behind Redis
- 🔲 **Staging environment** — mock-backend mirror of production for safe testing

---

## 7. Testing

- ✅ **Backend API integration tests** — `tests/` with pytest + httpx AsyncClient; SQLite in-memory DB; tests for health, auth (register/login/me), jobs (CRUD, cancel, retry), pipelines (CRUD)
- ✅ **Backend service unit tests** — `test_cost_estimator.py`, `test_result_parsers.py`, `test_mock_runners.py`, `test_storage.py`, `test_samplesheet.py`; 154 tests, all green in <2 s
- 🔲 **Frontend component tests** — Vitest + React Testing Library for nodes + validation
- 🔲 **E2E tests** — Playwright: build pipeline → upload → run → verify results panel

---

## 8. UX / Accessibility

- 🔲 **Onboarding tour** — interactive walkthrough for first-time users
- 🔲 **Mobile / tablet layout** — results panel + palette collapse to bottom sheet
- 🔲 **Accessible colour contrast** — audit inline colours for WCAG AA compliance
