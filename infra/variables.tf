variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Region for Cloud Run and Artifact Registry"
  type        = string
  default     = "us-east1"
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "stochastic-inventory-reorder"
}

variable "repo_name" {
  description = "Artifact Registry repository name (must match REPO in .github/workflows/deploy.yml)"
  type        = string
  default     = "stochastic-inventory-reorder"
}

variable "github_repo" {
  description = <<-EOT
    GitHub repository allowed to deploy, as owner/name. Casing does not matter:
    the WIF provider lowercases both the incoming claim and this value, so
    "Owner/My-Repo" and its all-lowercase
    spelling both work.
  EOT
  type        = string

  validation {
    condition     = can(regex("^[^/]+/[^/]+$", var.github_repo))
    error_message = "github_repo must be owner/name, with no https:// prefix and no trailing .git"
  }
}

# ---------------------------------------------------------------------------
# Compute sizing
#
# The numbers below come from timing the real endpoint on Apple silicon:
#
#   1000 sims x 180 days ->    5.7 s   <- what the UI actually sends
#   2000 sims x 180 days ->   11.1 s
#   4000 sims x 180 days ->   22.7 s
#   2000 sims x 365 days ->   44.6 s
#  10000 sims x 365 days ->  251.4 s, 727 MB peak RSS
#
# Cost is roughly linear in simulation count and superlinear in horizon.
#
# A Cloud Run vCPU is much slower than a laptop core for this workload -- about
# 3.6x, measured against the deployed service (2000 x 180 took 51-53 s warm in
# production versus 14.3 s in a 2-vCPU container locally). Multiply the table
# above by ~3.6 to predict production latency; that factor is why the UI default
# was dropped from 2000 trajectories to 1000.
# ---------------------------------------------------------------------------

variable "cpu" {
  description = <<-EOT
    vCPUs per instance. The sweep is single-threaded numpy (integer elementwise
    ops and RNG draws, no BLAS), so extra vCPUs never make one request faster --
    they buy concurrency. 2 gives one core to a sweep and leaves one for static
    assets, /api/health and /api/scenarios, so the page stays responsive while
    someone else's scenario is running. Raise this together with
    max_concurrent_simulations, never on its own.
  EOT
  type        = string
  default     = "2"
}

variable "memory" {
  description = <<-EOT
    Memory per instance. A 2000x180 run peaks around 165 MB of simulation
    arrays; the capped worst case (max_n_simulations x max_horizon_days) is
    roughly 300 MB, and max_concurrent_simulations of those can be in flight at
    once on top of the ~150 MB numpy/scipy/pandas baseline. 2Gi leaves
    comfortable headroom for that.
  EOT
  type        = string
  default     = "2Gi"
}

variable "container_concurrency" {
  description = <<-EOT
    Requests Cloud Run will send to one instance at a time. Deliberately above
    the vCPU count so cheap requests are not stuck behind a sweep; the app's
    MAX_CONCURRENT_SIMULATIONS semaphore is what bounds the expensive ones.
    The previous value of 40 on 1 vCPU was the failure mode this replaces.
  EOT
  type        = number
  default     = 8
}

variable "max_concurrent_simulations" {
  description = <<-EOT
    Simulation slots per instance (app-level semaphore). Requests arriving with
    no slot free get an immediate JSON 429 instead of queueing behind a sweep
    and timing out. Keep this at or below var.cpu -- sweeps beyond the core
    count thrash rather than overlap.
  EOT
  type        = number
  default     = 2
}

variable "max_n_simulations" {
  description = <<-EOT
    Hard ceiling on Monte-Carlo trajectories per request, applied server-side by
    _clamp_request. The UI asks for 1000, so 4000 is 4x headroom while keeping
    the worst case a public caller can request down to ~23 s measured locally
    (~85 s in production) rather than the ~251 s the schema's 10000 bound allows.
    Keep this comfortably under request_timeout_seconds after applying the ~3.6x
    production slowdown noted above.
  EOT
  type        = number
  default     = 4000
}

variable "max_horizon_days" {
  description = <<-EOT
    Hard ceiling on simulation horizon, applied server-side by _clamp_request.
    Matches what the UI sends. Cost is superlinear in horizon -- doubling 180 to
    365 quadrupled the runtime (11 s -> 45 s) -- so this is the more important
    of the two caps.
  EOT
  type        = number
  default     = 180
}

variable "request_timeout_seconds" {
  description = <<-EOT
    Max request duration. The capped worst case is ~23 s measured locally, call
    it a minute on a Cloud Run vCPU; 180 s leaves room for that plus a cold
    start without letting a wedged request hold a simulation slot for long.
  EOT
  type        = number
  default     = 180
}

variable "min_instances" {
  description = <<-EOT
    Idle instances. 0 means the service scales to zero and costs nothing while
    unused, at the price of a cold start (numpy/scipy/pandas import) on the
    first request. Set to 1 if cold starts become the main UX complaint.
  EOT
  type        = number
  default     = 0
}

variable "max_instances" {
  description = <<-EOT
    Max instances. The service is stateless, so this scales out freely: each
    concurrent visitor can land on their own instance instead of contending for
    one instance's cores. 10 caps cost and blast radius; instances are billed
    only while serving requests.
  EOT
  type        = number
  default     = 10
}

variable "log_level" {
  description = "Python log level for the app and uvicorn"
  type        = string
  default     = "INFO"
}

variable "public" {
  description = "Allow unauthenticated access"
  type        = bool
  default     = true
}

variable "custom_domain" {
  description = <<-EOT
    Hostname to map to the service, e.g. inventory.example.com. Empty disables
    the mapping and the service is reachable only on its *.run.app URL.

    The domain must already be verified for the account and the CNAME must
    already point at ghs.googlehosted.com as DNS-only (not proxied). Terraform
    creates the mapping; it cannot do the verification or the DNS.
  EOT
  type        = string
  default     = ""
}

variable "image" {
  description = <<-EOT
    Container image deployed on first create. The GitHub Actions workflow owns
    every later image; Terraform ignores image changes on the service so the
    two do not fight.
  EOT
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

# ---------------------------------------------------------------------------
# Identity naming (rarely need changing)
# ---------------------------------------------------------------------------

variable "wif_pool_id" {
  description = "Workload Identity Pool ID"
  type        = string
  default     = "github"
}

variable "wif_provider_id" {
  description = "Workload Identity Pool Provider ID"
  type        = string
  default     = "github-provider"
}

variable "deployer_account_id" {
  description = "Service account ID that GitHub Actions impersonates"
  type        = string
  default     = "deployer"
}

variable "runtime_account_id" {
  description = "Service account ID the Cloud Run service runs as"
  type        = string
  default     = "inventory-runtime"
}
