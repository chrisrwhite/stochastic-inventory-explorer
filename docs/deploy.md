# Deploying to Google Cloud Run with a Cloudflare subdomain

Runs the whole app -- FastAPI plus the built React SPA -- as one scale-to-zero
container on a custom subdomain. Deploys go out on every push to `main` from
GitHub Actions, authenticated with Workload Identity Federation, so no
service-account JSON key ever lands in a repo secret.

This is a generic walkthrough. Substitute your own values throughout:

| Placeholder | Meaning |
|---|---|
| `PROJECT_ID` | GCP project, created in step 1 |
| `REGION` | Cloud Run region — `us-east1` below |
| `SERVICE` | Cloud Run service — `stochastic-inventory-reorder` below, matching `infra/variables.tf` |
| `GITHUB_REPO` | `owner/name` of the repo that deploys |
| `inventory.example.com` | the subdomain you are mapping |

Two things own the deployment, and the split matters:

| | Owns | Change it by |
|---|---|---|
| `infra/` (Terraform) | APIs, Artifact Registry, WIF, service accounts, and every setting on the Cloud Run service — CPU, memory, concurrency, scaling, timeout, probes, `MAX_*` env vars | editing `infra/variables.tf`, then `terraform apply` |
| `.github/workflows/deploy.yml` | the container image, and nothing else | pushing to `main` |

The workflow calls `gcloud run deploy --image` with no sizing flags, which
leaves every other setting untouched; Terraform ignores image changes. **Do not
add sizing flags back to the workflow** — they would override Terraform on
every push and the drift would never show up in `terraform plan`.

---

# First deployment, step by step

Prerequisites: `gcloud`, `terraform`, `gh`, and a Google account with billing
enabled. Roughly 30 minutes, most of it waiting for a TLS certificate.

## 0. Authenticate, and mind the active project

If you already use `gcloud` for something else, it has a default project set,
and an unqualified command will happily deploy into it. Check with
`gcloud config get-value project`. Every command below passes `--project`
explicitly so nothing lands in the wrong place. Log in first:

```bash
gcloud auth login
gcloud auth application-default login    # separate credential, used by Terraform
```

## 1. Create the project and enable billing

Project IDs are globally unique, so append digits if the plain name is taken:

```bash
export PROJECT_ID="inventory-explorer-$RANDOM"
export REGION="us-east1"

gcloud projects create "$PROJECT_ID" --name="Inventory Explorer"

# Attach billing -- nothing else works until this is done. Capture the account
# ID rather than retyping it; pasting the literal placeholder is an easy slip
# and gcloud rejects it with a bare "INVALID_ARGUMENT".
BILLING_ACCOUNT=$(gcloud billing accounts list --filter='open=true' \
  --format='value(name)' --limit=1)
echo "$BILLING_ACCOUNT"          # sanity-check if you have more than one

gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"
gcloud billing projects describe "$PROJECT_ID"     # billingEnabled: true
```

Note the value of `$PROJECT_ID`; you need it in the next step and it is worth
recording in the ops table in the README.

## 2. Provision the infrastructure

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`: set `project_id` to the ID from step 1 and
`github_repo` to your `owner/name`. Casing does not matter — the WIF provider
folds case on both sides.

```bash
terraform init
terraform plan      # read it: ~15 resources, all creates
terraform apply
```

This creates the APIs, the Artifact Registry repository, the Workload Identity
pool and provider (scoped to this one repo), the deployer and runtime service
accounts, and the Cloud Run service itself — initially serving Google's `hello`
placeholder image, because there is no real image yet.

The first apply takes a few minutes; enabling APIs is the slow part. If it fails
with `SERVICE_DISABLED`, wait a minute and re-run — API enablement is eventually
consistent and a second apply picks up where it stopped.

## 3. Publish the GitHub Actions secrets

```bash
# still in infra/
gh secret set GCP_PROJECT_ID --body "$(terraform output -raw gcp_project_id)"
gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER --body "$(terraform output -raw gcp_workload_identity_provider)"
gh secret set GCP_DEPLOY_SERVICE_ACCOUNT --body "$(terraform output -raw gcp_deploy_service_account)"

gh secret list      # confirm all three
```

## 4. Ship the first real image

```bash
git push origin main
gh run watch        # follow the deploy
```

The workflow builds the image, pushes it to Artifact Registry, rolls out a
revision, and smoke-tests `/api/health` before going green. That health check
reports the loaded scenario count, so a green run means the bundled scenario
data made it into the image — not merely that the process is listening.

Confirm by hand:

```bash
SERVICE_URL=$(gcloud run services describe stochastic-inventory-reorder \
  --region "$REGION" --project "$PROJECT_ID" --format='value(status.url)')
curl "$SERVICE_URL/api/health"
open "$SERVICE_URL"
```

Expect `{"status":"ok","version":"0.1.0","n_scenarios":3,...}`. The first
request after an idle period pays a cold start of a few seconds while
numpy/scipy/pandas load.

## 5. Map the custom domain

1. **Verify domain ownership** in
   [Google Search Console](https://search.google.com/search-console) as the same
   Google identity that owns the project. Verification is per-identity, not
   per-project, so if you have mapped a domain from this account before, this
   is already done. Check first:

   ```bash
   gcloud domains list-user-verified
   ```

2. **Add the CNAME in Cloudflare** (`example.com` zone → DNS):

   - Type `CNAME`, Name `inventory`, Target `ghs.googlehosted.com`
   - Proxy status: **DNS only (grey cloud)**

   Grey cloud, not orange. Google cannot complete the challenge to issue the
   managed certificate while Cloudflare is proxying the hostname. You can switch to proxied *after* the certificate is live if
   you want Cloudflare's caching and WAF, but leave it grey until then or the
   cert will sit in `CertificatePending` indefinitely.

3. **Create the mapping** — Terraform owns this, not `gcloud`. Set the domain
   in `infra/terraform.tfvars`:

   ```hcl
   custom_domain = "inventory.example.com"
   ```

   ```bash
   cd infra && terraform apply
   ```

   Leaving `custom_domain` empty skips the mapping entirely and the service
   stays on its `*.run.app` URL.

4. **Wait for the certificate.** Two quirks worth knowing, both hit on the
   first run of this:

   **The apply can fail with a 409 while still having created the mapping.**
   The provider creates the resource, then blocks waiting for it to go Ready.
   Certificate issuance outlasts that wait, the provider retries the *create*,
   and the second attempt returns
   `Error 409: Resource '<domain>' already exists`. The mapping is real at that
   point but absent from state. Import it rather than deleting and retrying:

   ```bash
   terraform import "google_cloud_run_domain_mapping.app[0]" \
     "locations/us-east1/namespaces/PROJECT_ID/domainmappings/inventory.example.com"
   terraform plan   # expect "No changes"
   ```

   **`CertificateProvisioned: True` does not mean TLS works yet.** The status
   flips before Google's edge actually serves the certificate; until it does,
   HTTPS fails the handshake outright (`no peer certificate available`) on both
   IPv4 and IPv6 while HTTP already 302s correctly. Usually minutes, but Google
   documents up to 24 hours. There is nothing to fix during that window —
   re-running apply will not speed it up.

   Check status and liveness:

   ```bash
   TOKEN=$(gcloud auth print-access-token)
   curl -s -H "Authorization: Bearer $TOKEN" \
     "https://us-east1-run.googleapis.com/apis/domains.cloudrun.com/v1/namespaces/PROJECT_ID/domainmappings" \
     | python3 -m json.tool | grep -A2 '"type"'

   curl -sI https://inventory.example.com/api/health
   ```

   The API call above is the `gcloud beta run domain-mappings describe`
   equivalent, without needing the `beta` component installed.

   Healthy end state: `Ready`, `CertificateProvisioned` and `DomainRoutable`
   all `True`, HTTP 302s to HTTPS, and HTTPS returns the health JSON.

## 6. Record the facts — but not in the README

The **Operations & dev access** table in [README.md](../README.md) is
intentionally free of the GCP project ID and Cloudflare account ID. This repo
is on a documented path to going public
([.github/PUBLISH_CHECKLIST.md](../.github/PUBLISH_CHECKLIST.md)), and those
identifiers are awkward to retract once published. They stay recoverable from
gitignored sources instead:

```bash
cd infra && terraform output -raw gcp_project_id
```

What *is* worth doing now:

- Replace "Live demo coming soon" in the README with the live URL
  (checklist item 4).
- Set the repo's **Website** field to the same URL.
- If you want a local scratchpad of console deep links with IDs baked in, put
  it somewhere gitignored — not in `docs/`.

---

# Reference

## Manual deploy (optional)

To test a build without pushing:

```bash
make docker-build
docker push "$(cd infra && terraform output -raw image_repository)/app:$(git rev-parse --short HEAD)"
make deploy PROJECT="$PROJECT_ID"
```

`make deploy` also passes `--image` only, for the same reason the workflow does.

To check the container locally first:

```bash
make docker-build
make docker-run          # http://localhost:8080
curl localhost:8080/api/health
```

## Sizing, and why it is what it is

The service is sized from measured endpoint runtimes rather than guesses. On a
fast laptop:

| Request | Wall time | Peak RSS |
|---|---|---|
| **1000 sims x 180 days (what the UI sends)** | **5.7 s** | |
| 2000 x 180 | 11.1 s | 165 MB |
| 4000 x 180 (the deployed ceiling) | 22.7 s | |
| 2000 x 365 | 44.6 s | |
| 10000 x 365 (the schema's ceiling) | 251.4 s | 727 MB |

Cost is roughly linear in simulation count and *superlinear* in horizon.

**Cloud Run is ~3.6x slower than a laptop core here.** Measured against the
deployed service, a 2000 x 180 request took 51-53 s warm in production versus
14.3 s in a 2-vCPU container locally. That is not cold start — health responds
in 0.14 s on the same warm instance. Multiply the table above by ~3.6 to
predict production latency.

That factor is why the UI default is 1000 trajectories, not 2000: it puts the
common request near ~20 s instead of ~52 s. The cost is Monte Carlo standard
error widening by sqrt(2), visible as a slightly noisier cost-vs-reliability
scatter. More vCPUs would not have helped — the sweep is single-threaded, so
the only levers are fewer trajectories or a faster solver.

The per-day-step cost suggests real headroom in `simulate` rather than a hard
floor: 240 policies x 180 days is ~43,000 steps, and 51 s implies ~1.2 ms per
step for a 2,000-element vector operation that numpy should do in single-digit
microseconds. Profiling that is the durable fix.

Three consequences shape the config:

- **The sweep is single-threaded numpy** (integer elementwise ops and RNG
  draws, no BLAS). Extra vCPUs never make one request faster — they only buy
  concurrency. So the service runs 2 vCPU, not 8.
- **Container concurrency (8) sits above the core count on purpose**, so page
  loads, `/api/health` and `/api/scenarios` stay fast while a sweep runs. That
  was verified: during a 14 s sweep, health answered in 1.6 ms.
- **The app-level semaphore is what bounds the expensive work.**
  `MAX_CONCURRENT_SIMULATIONS` slots gate `/api/optimize`, `/api/simulate` and
  `/api/compare`; a request arriving with no free slot gets an immediate JSON
  429 (`Retry-After: 5`) rather than queueing behind a sweep and timing out.
  The frontend already surfaces `detail` from an error body, so this reads as a
  plain "the simulator is busy" message in the UI.

`MAX_N_SIMULATIONS` / `MAX_HORIZON_DAYS` cap the worst request a *public*
caller can make. The UI never asks for more than 1000 x 180, but the request
schema alone permits 10000 x 365 — a 251-second, 727 MB request on an endpoint
with no authentication. Capping at 4000 x 180 brings that worst case down to
~23 s (measured: an oversized request came back clamped in 29.7 s).

Every value lives in `infra/variables.tf` with this reasoning attached. Raise
`cpu` and `max_concurrent_simulations` together — one without the other either
buys nothing or reintroduces thrashing.

## Session state

There is none on the server, by design. Every request carries its full
configuration in the body and gets its whole result back inline: no session
cache, no cookie, no sticky routing. That is what lets `max_instances` be 10
without a second thought — any instance can serve any request, so concurrent
visitors get their own instances instead of contending for one.

The client side of that bargain is that **the URL is the session**. The whole
config round-trips through the query string (`frontend/src/state/urlState.ts`),
so a reload or a shared link reproduces exactly the run the sender saw. Values
matching the defaults are omitted, keeping the everyday URL short. If you add a
config field, add it to `urlState.ts` too — otherwise it silently resets on
reload and quietly diverges for anyone opening a shared link.

## Observability

- Logs: `gcloud run services logs read stochastic-inventory-reorder --region us-east1`
- Metrics: Cloud Run console, or Cloudflare Analytics.
- Alerting: a Cloud Monitoring uptime check on `https://$DOMAIN/api/health`.
  `/api/health` reports the loaded scenario count, so it fails loudly if an
  image ships without its bundled data rather than just reporting "listening".
- A free UptimeRobot monitor on the same path every 10 minutes keeps the
  instance warm and hides the cold start from visitors. With CPU allocated only
  during requests this costs essentially nothing.

## Rollback

```bash
gcloud run revisions list --service stochastic-inventory-reorder --region us-east1
gcloud run services update-traffic stochastic-inventory-reorder \
  --region us-east1 --to-revisions REVISION_NAME=100
```

## Cost expectations

With `min_instances = 0` and light demo traffic, well under $5/month — the
Cloud Run free tier covers 2M requests and 360k GiB-seconds. Cold starts for
the numpy/scipy/pandas runtime are the main UX cost; `startup_cpu_boost` is on
to shorten them. Set `min_instances = 1` (~$5-10/month) if that becomes the
main complaint.
