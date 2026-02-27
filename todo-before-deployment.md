# Pre-Deployment Checklist

Step-by-step instructions to acquire every environment variable needed to run this platform in production. Work through each section in order.

---

## 1. JWT Secret

Used to sign authentication tokens. Must be a long, random string.

**Generate it:**
```bash
openssl rand -hex 32
```
Copy the output (64 hex chars).

**Set:**
```
JWT_SECRET=<output from above>
```

---

## 2. AWS Account & IAM Setup

All AWS services (S3, Batch, ECR) live under one AWS account. If you don't have one, create it at https://aws.amazon.com/.

### 2a. Create a Programmatic IAM User

This user's credentials go into the app. It is **not** your root account.

1. Open the [AWS IAM console](https://console.aws.amazon.com/iam/) → **Users** → **Create user**
2. Username: `bioplatform-app` (or any name)
3. **Permissions** — attach these managed policies directly:
   - `AmazonS3FullAccess` *(or a custom policy — see note below)*
   - `AWSBatchFullAccess`
   - `AmazonEC2ContainerRegistryReadOnly` *(only needed if pulling from ECR)*
4. After creation → **Security credentials** tab → **Create access key** → choose **Application running outside AWS**
5. Copy the **Access key ID** and **Secret access key** (shown only once).

**Set:**
```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1     # or whatever region you'll use — must match S3 bucket + Batch
```

> **Least-privilege note:** Instead of `AmazonS3FullAccess`, you can attach a custom policy that limits access to your specific bucket:
> ```json
> {
>   "Effect": "Allow",
>   "Action": ["s3:PutObject","s3:GetObject","s3:DeleteObject","s3:ListBucket"],
>   "Resource": ["arn:aws:s3:::YOUR_BUCKET","arn:aws:s3:::YOUR_BUCKET/*"]
> }
> ```

---

## 3. S3 Bucket

Stores uploaded genomic files and pipeline outputs.

1. Open the [S3 console](https://console.aws.amazon.com/s3/) → **Create bucket**
2. **Bucket name:** choose something globally unique, e.g. `bioplatform-prod-uploads`
3. **Region:** same as `AWS_REGION`
4. **Block all public access:** leave ON (default) — the app uses presigned URLs
5. **Versioning:** optional, recommended for data safety
6. Create the bucket.

**Optional — Lifecycle rule to auto-delete old uploads:**
S3 → your bucket → **Management** → **Create lifecycle rule**
- Rule name: `expire-old-uploads`
- Apply to: all objects (or filter by prefix `uploads/`)
- Action: **Expire current versions** after 90 days

**Set:**
```
STORAGE_BACKEND=s3
S3_BUCKET=bioplatform-prod-uploads
```

---

## 4. AWS Batch — Compute Environment

AWS Batch runs the actual Nextflow / Snakemake / BioScript jobs.

### 4a. Create a Compute Environment

1. Open the [AWS Batch console](https://console.aws.amazon.com/batch/) → **Compute environments** → **Create**
2. **Type:** Managed
3. **Name:** `bioplatform-compute`
4. **Provisioning model:** On-Demand (or Spot for ~70% cost savings, but jobs can be interrupted)
5. **Instance types:** `optimal` (lets Batch choose), or specify `m5`, `c5`, `r5` families
6. **Min / Max vCPUs:** 0 / 256 (starts at 0 when idle, scales up on demand)
7. **VPC & subnets:** choose your default VPC and at least two subnets
8. **Security groups:** default is fine for a start
9. Create it.

### 4b. Create a Job Queue

1. **Job queues** → **Create**
2. **Name:** `bioplatform-default`
3. **Priority:** 1
4. **Connected compute environments:** select `bioplatform-compute`
5. Create it.

**Set:**
```
BATCH_JOB_QUEUE=bioplatform-default
```

If you want a separate queue for Snakemake jobs (optional):
```
SNAKEMAKE_BATCH_QUEUE=bioplatform-snakemake
```
Leave blank to reuse `BATCH_JOB_QUEUE`.

### 4c. Create the Batch Job Execution IAM Role

Batch job containers need permission to read/write S3 and call Batch APIs.

1. [IAM console](https://console.aws.amazon.com/iam/) → **Roles** → **Create role**
2. **Trusted entity type:** AWS service → **Elastic Container Service** → **Elastic Container Service Task**
3. **Permissions:** attach
   - `AmazonS3FullAccess` (or the scoped custom policy from §2a)
   - `AWSBatchFullAccess`
4. **Role name:** `bioplatform-batch-job-role`
5. After creation, copy the **ARN** from the role summary page. It looks like:
   `arn:aws:iam::123456789012:role/bioplatform-batch-job-role`

**Set:**
```
BATCH_JOB_ROLE_ARN=arn:aws:iam::123456789012:role/bioplatform-batch-job-role
```

---

## 5. BioScript Docker Image (if using BioScript node)

The BioScript node runs user bash scripts inside a custom Docker image with samtools, bwa, STAR, etc.

### 5a. Create an ECR repository

1. [ECR console](https://console.aws.amazon.com/ecr/) → **Repositories** → **Create repository**
2. **Visibility:** Private
3. **Name:** `bioplatform/tools`
4. Create it. Copy the repository URI, e.g.:
   `123456789012.dkr.ecr.us-east-1.amazonaws.com/bioplatform/tools`

### 5b. Build and push the image

Run these commands from the project root (requires Docker and AWS CLI installed locally):

```bash
# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS \
    --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

# Build the tools image
docker build -f backend/Dockerfile.tools \
  -t 123456789012.dkr.ecr.us-east-1.amazonaws.com/bioplatform/tools:latest \
  backend/

# Push
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/bioplatform/tools:latest
```

**Set:**
```
BIOSCRIPT_DOCKER_IMAGE=123456789012.dkr.ecr.us-east-1.amazonaws.com/bioplatform/tools:latest
BIOSCRIPT_BACKEND=awsbatch
```

If you're not using BioScript yet, leave `BIOSCRIPT_BACKEND=mock` and skip this section.

---

## 6. Snakemake Container Image

The Snakemake AWS Batch runner uses an official Snakemake Docker image. The default value (`snakemake/snakemake:v8.20.0`) is pulled from Docker Hub at job runtime — no action needed unless Docker Hub rate limits are a concern.

If you want to mirror it to ECR:
```bash
docker pull snakemake/snakemake:v8.20.0
docker tag snakemake/snakemake:v8.20.0 \
  123456789012.dkr.ecr.us-east-1.amazonaws.com/snakemake:v8.20.0
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/snakemake:v8.20.0
```
Then set:
```
SNAKEMAKE_CONTAINER_IMAGE=123456789012.dkr.ecr.us-east-1.amazonaws.com/snakemake:v8.20.0
SNAKEMAKE_BACKEND=awsbatch
```

Otherwise, leave both at their defaults and only flip `SNAKEMAKE_BACKEND=awsbatch`.

---

## 7. Nextflow Backend

```
NEXTFLOW_BACKEND=awsbatch
```

The Nextflow runner reuses `BATCH_JOB_QUEUE` and `BATCH_JOB_ROLE_ARN` from §4. No additional setup needed beyond what's already configured there.

---

## 8. Stripe — Payments

### 8a. Create a Stripe account

Sign up at https://stripe.com if you don't have one.

### 8b. Get your API keys

1. [Stripe Dashboard](https://dashboard.stripe.com/) → **Developers** → **API keys**
2. Copy the **Secret key** (starts with `sk_live_...` for production, `sk_test_...` for testing)

**Set:**
```
STRIPE_SECRET_KEY=sk_live_...
```

### 8c. Create a webhook endpoint

Stripe calls your server when a payment completes, so the job can be created automatically.

1. Stripe Dashboard → **Developers** → **Webhooks** → **Add endpoint**
2. **Endpoint URL:** `https://your-domain.com/api/v1/payments/webhook`
   *(Use your real production domain — Stripe cannot reach `localhost`)*
3. **Events to listen for:** select `checkout.session.completed`
4. Click **Add endpoint**
5. On the endpoint detail page, reveal and copy the **Signing secret** (starts with `whsec_...`)

**Set:**
```
STRIPE_WEBHOOK_SECRET=whsec_...
```

> **Testing locally:** Use the Stripe CLI to forward webhooks to localhost:
> ```bash
> stripe listen --forward-to localhost:8000/api/v1/payments/webhook
> ```
> This gives you a temporary `whsec_...` secret for local testing.

---

## 9. App Base URL

Used as the return URL after Stripe checkout (success/cancel redirects).

**Set to your production frontend URL:**
```
APP_BASE_URL=https://your-domain.com
```

For local development this defaults to `http://localhost:5173` automatically.

---

## 10. CORS Origins

If your frontend is served from a different origin than the API, list it here.

```
ALLOWED_ORIGINS=https://your-domain.com
```

Comma-separate multiple origins if needed:
```
ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

---

## 11. HLA Backend (optional)

If you have a real HLA-HD installation:
```
HLA_BACKEND=hlahd
```
Leave as `HLA_BACKEND=mock` to use the mock runner.

---

## 12. Complete `.env` File

Create a `.env` file at the project root with all values filled in:

```bash
# ── Database ─────────────────────────────────────────────────
POSTGRES_USER=bioplatform
POSTGRES_PASSWORD=<strong random password>
POSTGRES_DB=bioplatform

# ── Auth ─────────────────────────────────────────────────────
JWT_SECRET=<64 hex chars from: openssl rand -hex 32>

# ── App ──────────────────────────────────────────────────────
APP_BASE_URL=https://your-domain.com
ALLOWED_ORIGINS=https://your-domain.com

# ── Storage ──────────────────────────────────────────────────
STORAGE_BACKEND=s3
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
S3_BUCKET=bioplatform-prod-uploads

# ── AWS Batch ─────────────────────────────────────────────────
BATCH_JOB_QUEUE=bioplatform-default
BATCH_JOB_ROLE_ARN=arn:aws:iam::123456789012:role/bioplatform-batch-job-role
SNAKEMAKE_BATCH_QUEUE=           # leave blank to reuse BATCH_JOB_QUEUE

# ── Runners ───────────────────────────────────────────────────
HLA_BACKEND=mock                 # or hlahd
NEXTFLOW_BACKEND=awsbatch
SNAKEMAKE_BACKEND=awsbatch
BIOSCRIPT_BACKEND=awsbatch

# ── Container images ──────────────────────────────────────────
SNAKEMAKE_CONTAINER_IMAGE=snakemake/snakemake:v8.20.0
BIOSCRIPT_DOCKER_IMAGE=123456789012.dkr.ecr.us-east-1.amazonaws.com/bioplatform/tools:latest

# ── Stripe ────────────────────────────────────────────────────
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

---

## 13. Deploy

Once the `.env` file is complete:

```bash
docker compose up -d
docker compose logs -f backend   # watch for "Application startup complete."
```

Migrations run automatically at startup (`alembic upgrade head`). The nf-core and Snakemake catalogs are scraped in the background on first boot — allow ~2 minutes before the palette is fully populated.

**Verify:**
```bash
# Health check
curl https://your-domain.com/api/v1/snakemake/status
# → {"wrappers": 454, "workflows": 4708, "ready": true}

# Stripe webhook (after registering the endpoint)
stripe trigger checkout.session.completed
```

---

## Quick Reference — What Each Variable Gates

| Variable | Without it |
|----------|------------|
| `JWT_SECRET` | Auth broken (all endpoints return 401) |
| `AWS_*` + `S3_BUCKET` | File uploads fail |
| `BATCH_JOB_QUEUE` + `BATCH_JOB_ROLE_ARN` | Real job execution fails; mock runner still works |
| `STRIPE_SECRET_KEY` | Payment checkout fails |
| `STRIPE_WEBHOOK_SECRET` | Webhook signature check fails; jobs never created after payment |
| `APP_BASE_URL` | Stripe redirects back to localhost (wrong in production) |
| `BIOSCRIPT_DOCKER_IMAGE` | BioScript Batch jobs fail to pull image |
