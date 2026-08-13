# Infrastructure (Terraform)

Codifies the Cloud Run deployment so it is `terraform apply` rather than
console clicking. Manages: the required APIs, the Artifact Registry repository,
the Workload Identity Federation setup that lets GitHub Actions deploy without
a service-account key, the runtime and deployer service accounts, the Cloud Run
service itself (CPU, memory, concurrency, scaling, timeout, health probes,
compute-envelope env vars), and public access.

## Division of labour with the deploy workflow

Terraform owns **service configuration**. `.github/workflows/deploy.yml` owns
**the image**: it builds, pushes, and rolls out a new revision with
`gcloud run deploy --image`, which leaves every other setting on the service
untouched. Terraform in turn ignores image changes
(`lifecycle.ignore_changes`), so the two never fight.

The practical consequence: **do not add sizing flags back to the workflow.**
Change CPU, memory, concurrency, scaling, timeout or the `MAX_*` env vars in
`variables.tf` and `terraform apply`. A `--memory` flag in the workflow would
silently override Terraform on every push and drift would be invisible.

## First-time use on a machine

```bash
brew install terraform          # or: brew install opentofu
gcloud auth application-default login
```

## Usage

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars   # set project_id + github_repo
terraform init
terraform plan
terraform apply
```

Then publish the three GitHub Actions repository secrets from the outputs:

```bash
terraform output -raw gcp_project_id                   # -> GCP_PROJECT_ID
terraform output -raw gcp_workload_identity_provider   # -> GCP_WORKLOAD_IDENTITY_PROVIDER
terraform output -raw gcp_deploy_service_account       # -> GCP_DEPLOY_SERVICE_ACCOUNT
```

`gh secret set GCP_PROJECT_ID --body "$(terraform output -raw gcp_project_id)"`
and so on, or paste them into Settings -> Secrets and variables -> Actions.

Push to `main` and the workflow deploys the first real image over the
`cloudrun/container/hello` placeholder.

## Sizing

Every compute knob is a variable with the measured reasoning attached; read
`variables.tf` before changing one. The short version:

| Setting | Value | Why |
|---|---|---|
| CPU | 2 | A sweep is single-threaded numpy, so one core runs it and one stays free for page loads and health checks |
| Memory | 2Gi | ~300 MB per capped sweep, 2 concurrent, plus the numpy/scipy/pandas baseline |
| Container concurrency | 8 | Above the core count on purpose, so cheap requests are not stuck behind a sweep |
| `MAX_CONCURRENT_SIMULATIONS` | 2 | App-level semaphore; excess sweeps get a clean 429 instead of thrashing |
| `MAX_N_SIMULATIONS` / `MAX_HORIZON_DAYS` | 4000 / 180 | Caps the worst public request at ~23 s measured locally, vs ~251 s at the schema own bounds |
| Request timeout | 180s | Capped worst case plus cold-start headroom |
| Min / max instances | 0 / 10 | Scale to zero when idle; stateless, so it scales out freely under load |

`cpu` and `max_concurrent_simulations` move together — raising vCPUs without
raising the semaphore buys nothing, and raising the semaphore without the
vCPUs reintroduces thrashing.

## Adopting a service that already exists

If the Cloud Run service was created by hand or by an earlier `gcloud run
deploy` before Terraform existed, import it rather than letting Terraform try
to create it a second time:

```bash
terraform init
terraform import google_cloud_run_v2_service.app \
  projects/PROJECT_ID/locations/us-east1/services/stochastic-inventory-reorder
terraform import 'google_cloud_run_v2_service_iam_member.public[0]' \
  "projects/PROJECT_ID/locations/us-east1/services/stochastic-inventory-reorder roles/run.invoker allUsers"
terraform plan   # expect diffs pulling the old sizing onto the values above
```

Import the WIF pool, provider, service accounts and Artifact Registry repo the
same way if those were created by the `gcloud` commands in `docs/deploy.md`.

## Notes

- State is local (`terraform.tfstate`, gitignored). Fine for a solo project;
  move to a GCS backend if more than one person applies.
- The runtime service account intentionally holds no project IAM roles. The app
  only reads scenario files baked into its own image, so it needs nothing from
  the project — the account exists so the service stops running as the
  broadly-privileged compute default service account.
- The WIF provider carries an `attribute_condition` pinning it to
  `var.github_repo`. Without that condition any GitHub repository could present
  a token and impersonate the deployer.
