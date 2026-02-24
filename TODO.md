# Bioinformatics Platform — To-Do List

> Status legend: ✅ Done · 🔄 In Progress · 🔲 Not Started · 💡 Idea / Future

---

## 1. Backend — Pipeline Execution Infrastructure

### 1.1 Real Storage Backend
- 🔲 **S3 storage backend** (`app/services/storage/s3.py`)
  - Generate real presigned upload URLs via `boto3`
  - Store files in S3 so EC2 workers can pull them
  - Return `s3://bucket/key` paths to the pipeline runner
  - Config switch: `STORAGE_BACKEND=s3`

### 1.2 Real Compute Backend
- 🔲 **AWS EC2 backend** (`app/services/ec2/aws.py`)
  - Launch spot or on-demand instances via `boto3` based on job tier
  - Wait for SSH readiness (or use AWS SSM instead of raw SSH)
  - Mount / pull input file from S3
  - Terminate instance on completion or failure
  - Config switch: `EC2_BACKEND=aws`
- 🔲 **Alternative: ECS/Fargate task runner** — simpler than raw EC2 for containerised tools
- 🔲 **Alternative: AWS Batch** — purpose-built for bioinformatics batch jobs, handles queuing and spot interruptions automatically

### 1.3 Nextflow / nf-core Pipeline Runner
- 🔲 **Nextflow runner service** (`app/services/nextflow/`)
  - Call `nextflow run nf-core/<pipeline>` with `--input samplesheet.csv`
  - Capture `stdout`/`stderr` and tail `.nextflow.log` for live progress
  - Parse Nextflow's `trace.txt` for per-process timing
  - Handle Nextflow resume (`-resume`) to restart failed runs cheaply
  - Config switch: `NEXTFLOW_BACKEND=nextflow` (mock is ready; real runner is 🔲)
- ✅ **Mock Nextflow runner** (`app/services/nextflow/mock.py`) — deterministic per-pipeline mock results (table/vcf/files) wired into Celery task routing
- ✅ **Samplesheet generator** (`app/services/samplesheet.py`) — generates nf-core CSV samplesheets for rnaseq, sarek, atacseq, methylseq, ampliseq, chipseq, fetchngs
- ✅ **Result parsers** (`app/services/result_parsers.py`) — VCF, count matrix, MultiQC HTML, file list, auto-detect dispatcher
- 🔲 **Container registry** — pull correct Singularity/Docker containers before running; pre-warm on instance startup to reduce latency

### 1.4 Snakemake Pipeline Runner *(future)*
- 🔲 **Snakemake runner service** (`app/services/snakemake/`)
  - Call `snakemake --cores N --use-conda` or `--use-singularity`
  - Support remote execution via Snakemake's built-in AWS/Slurm profiles
  - Parse `snakemake --summary` for progress tracking
- 🔲 **Snakemake catalog** — index community Snakemake workflows (Snakemake Wrappers, WorkflowHub) similar to nf-core catalog scraper

### 1.5 Real HLA-HD Runner
- 🔲 **HLA-HD runner** (`app/services/hla/hlahd.py`)
  - Wrap HLA-HD binary (or Docker image) with the real analysis
  - Parse `HLA-HD` result files into the `hla_alleles` JSON structure
  - Config switch: `HLA_BACKEND=hlahd`

### 1.6 Result Parsers
- ✅ **MultiQC HTML parser** — wraps HTML as `type: "html_report"` in `result_parsers.py`
- ✅ **Count matrix parser** — parses `*.tsv` / `*.csv` into `type: "table"` with auto-sniffed delimiter
- ✅ **VCF parser** — parses VCF lines into `type: "vcf"` variant list (first 500 rows)
- ✅ **Generic file-list result** — `parse_file_list()` returns `type: "files"` with name/path/size/mime
- 🔲 **Result size limits** — large VCFs / count tables should be stored in S3 and streamed/paginated rather than embedded in the job JSON

### 1.7 Job Stage Tracking
- 🔲 **Fine-grained stage tracking** — surface Nextflow process names as live progress steps instead of the current two-stage (ec2_starting / hla_running) model
- 🔲 **Log streaming** — WebSocket or SSE endpoint so the frontend can show live `nextflow.log` output in the Results panel
- 🔲 **Job cancellation** — `DELETE /api/v1/jobs/{id}` endpoint that kills the running Nextflow/EC2 process and terminates the instance

---

## 2. Frontend — Pipeline Builder

### 2.1 Canvas & Validation
- ✅ Validation only shows HLA errors when HLA nodes are present
- ✅ nf-core canvas: unconnected InputFileNode no longer shows HLA warnings
- 🔲 **Run button context** — when running a pure nf-core pipeline, route the job to the Nextflow runner instead of HLA runner (requires backend routing by pipeline type)
- 🔲 **Pipeline type badge** — display "HLA" / "nf-core" / "Snakemake" / "Mixed" badge in toolbar based on canvas content

### 2.2 Input File Node
- ✅ File upload widget with progress indicator
- ✅ Dataset ID / storage-key input mode
- 🔲 **Multi-file upload** — nf-core pipelines often need paired FASTQ (R1 + R2); allow uploading two files and auto-generate the samplesheet
- 🔲 **URL / SRA input mode** — accept an SRA accession (e.g. `SRR12345678`) and stream-download on the EC2 worker via `prefetch` + `fasterq-dump`
- 🔲 **Dataset library** — persist uploaded files so users can re-select them without re-uploading (dropdown of past uploads)

### 2.3 nf-core Module Nodes
- ✅ Auto-wiring with pattern-overlap and port-stem matching
- ✅ Topological DAG layout with grid fallback
- 🔲 **Module parameter panel** — click a module to open a side panel showing its `nextflow.config` params with inline editing
- 🔲 **Module version pinning** — allow selecting a specific nf-core module tag/version
- 🔲 **Subworkflow nodes** — nf-core subworkflows (e.g. `BAM_SORT_STATS_SAMTOOLS`) should be collapsible composite nodes

### 2.4 Results Node & Results Panel
- ✅ Smart output hints from connected module port patterns
- ✅ "View Results" button + download shortcut on node
- ✅ Sliding results panel (side drawer ↔ center modal) with Summary / Data / Downloads / Raw tabs
- ✅ HLA alleles: locus-color-coded cards, Class I / II grouping, bar chart
- ✅ VCF: stat cards, donut chart, sortable/filterable table
- ✅ Generic table: sortable, searchable, paginated
- ✅ Download as JSON / TSV / clipboard
- 🔲 **MultiQC iframe viewer** — render MultiQC HTML reports in the Data tab
- 🔲 **IGV.js integration** — for BAM / VCF results, embed IGV.js genome browser in the Results panel
- 🔲 **Volcano / MA plot** — for RNA-seq differential expression results, render D3 or Vega-Lite plot
- 🔲 **Log viewer tab** — stream `nextflow.log` in a dark-mode terminal pane within the Results panel
- 🔲 **Result sharing** — generate a shareable read-only link to a result (requires auth)

### 2.5 Snakemake Module Nodes *(future)*
- 🔲 **Snakemake node type** — `snakemakeRule` node rendered with a snake icon and distinct colour scheme
- 🔲 **Mixed pipeline canvas** — allow connecting nf-core output ports → Snakemake input wildcards on the same canvas, with cross-framework edge validation
- 🔲 **Snakemake palette section** — catalog panel section for Snakemake Wrappers alongside nf-core modules

### 2.6 Built-in Custom Modules *(future)*
- 🔲 **Built-in module type** (`builtinTool` node) — curated set of common tools (FastQC, MultiQC, Trimmomatic, STAR, DESeq2, …) with pre-configured parameters
- 🔲 **Built-in module catalog** — separate palette section "Built-in Tools" above nf-core Modules
- 🔲 **Script node** — drop in a Python/R/Bash code block node; backend runs it in a container on the worker instance

---

## 3. User Accounts & Multi-tenancy

- 🔲 **Authentication** — JWT or OAuth2 (GitHub / Google) login; protect all API endpoints
- 🔲 **Per-user storage namespacing** — uploads and results scoped to `user_id`
- 🔲 **Pipeline sharing** — mark a saved pipeline as public or share with specific users
- 🔲 **Organisation / team workspaces** — share pipelines and result history within a team

---

## 4. Job Management

- 🔲 **Job history page** — list all past jobs with status, cost, runtime, pipeline used
- 🔲 **Job retry** — one-click re-run a failed job with the same input and parameters
- 🔲 **Job cancellation** — cancel a running job from both the builder canvas and the history page
- 🔲 **Cost tracking** — accumulate real AWS costs per job and surface a monthly spend summary
- 🔲 **Notifications** — email or Slack webhook when a long-running job finishes or fails

---

## 5. nf-core / Snakemake Catalog

- ✅ nf-core pipeline + module catalog scraped from GitHub
- ✅ `input_formats` scraped from `assets/schema_input.json` per pipeline
- 🔲 **Incremental refresh** — re-scrape only pipelines/modules updated since `last_scraped`
- 🔲 **Snakemake Wrappers catalog** — scrape https://snakemake-wrappers.readthedocs.io
- 🔲 **WorkflowHub catalog** — index CWL / Snakemake / Nextflow workflows from workflowhub.eu
- 🔲 **Module search ranking** — rank search results by star count + usage frequency
- 🔲 **Changelog / version info** — show latest release tag and changelog link for each pipeline

---

## 6. Infrastructure & DevOps

- 🔲 **Terraform / CDK** — infrastructure-as-code for VPC, S3 buckets, IAM roles, RDS, Redis, ECS
- 🔲 **CI/CD pipeline** — GitHub Actions: lint → test → build Docker images → push to ECR → deploy
- 🔲 **Staging environment** — mirror of production with mock backends for safe testing
- 🔲 **Database migrations** — Alembic migrations run automatically on deploy (already partially done)
- 🔲 **Secrets management** — move AWS credentials / DB passwords to AWS Secrets Manager or Vault
- 🔲 **Rate limiting** — per-IP and per-user rate limits on API endpoints
- 🔲 **Health checks** — `/health` endpoint for load-balancer and monitoring
- 🔲 **Horizontal scaling** — multiple Celery workers behind SQS or Redis for job parallelism

---

## 7. Testing

- 🔲 **Backend unit tests** — pytest for services (mock runner, storage, scraper)
- 🔲 **API integration tests** — pytest + httpx for all CRUD endpoints
- 🔲 **Frontend component tests** — Vitest + React Testing Library for node components and validation logic
- 🔲 **E2E tests** — Playwright: build a pipeline → upload file → run → verify results panel opens
- 🔲 **Scraper tests** — snapshot tests for nf-core meta.yml parsing (old + new format)

---

## 8. UX / Accessibility

- ✅ **Keyboard shortcuts** — `Ctrl+S` save, `Ctrl+Z` undo, `Ctrl+Shift+Z`/`Ctrl+Y` redo, `Ctrl+K` spotlight
- ✅ **Undo / redo** — 50-step snapshot stack (`useUndoRedo.ts`) with toolbar buttons
- ✅ **Node search / spotlight** — `Cmd+K` opens command palette (commands + templates + nf-core API search)
- 🔲 **Dark mode** — respect `prefers-color-scheme`; all inline styles already use CSS-var-ready values
- 🔲 **Mobile / tablet layout** — results panel and palette collapse to bottom sheet on small screens
- 🔲 **Onboarding tour** — interactive walkthrough for first-time users (drag a node, connect, run)
- ✅ **Pipeline templates** — 8 one-click starter templates (HLA, RNA-seq, Sarek, ATAC-seq, ChIP-seq, Methylation, Amplicon, FetchNGS) with template gallery modal

---

## 9. Documentation

- 🔲 **API reference** — auto-generated OpenAPI docs (FastAPI `/docs` is already there; customise it)
- 🔲 **User guide** — how to build a pipeline, upload data, interpret results
- 🔲 **Developer guide** — how to add a new node type, new backend, new result renderer
- 🔲 **Architecture diagram** — system overview (frontend → API → Celery → EC2 → results)
