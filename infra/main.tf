terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_project" "this" {}

# ---------------------------------------------------------------------------
# APIs. Deploys run from GitHub Actions over Workload Identity Federation, so
# there is no Cloud Build dependency here -- the pipeline builds the image
# itself and pushes it to Artifact Registry.
# ---------------------------------------------------------------------------
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "iamcredentials.googleapis.com",
    "iam.googleapis.com",
  ])
  service            = each.key
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# Artifact Registry repository that the deploy workflow pushes images to.
# ---------------------------------------------------------------------------
resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = var.repo_name
  format        = "DOCKER"
  description   = "Container images for ${var.service_name}"

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Workload Identity Federation: lets the GitHub Actions workflow mint short-
# lived GCP credentials with no service-account JSON key in repo secrets.
# ---------------------------------------------------------------------------
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = var.wif_pool_id
  display_name              = "GitHub Actions"

  depends_on = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = var.wif_provider_id
  display_name                       = "GitHub OIDC"

  # Scope the provider to this one repository. Without an attribute condition
  # any GitHub repo in the world could present a token for this provider.
  #
  # Compared case-insensitively: GitHub's `repository` claim carries the repo's
  # stored casing, which can differ from the all-lowercase spelling shown in
  # URLs and clone commands. An exact match against the wrong casing fails at
  # deploy time as an opaque permission error rather than an obvious config
  # mistake. GitHub does not allow two repos under one owner differing only by
  # case, so folding case costs nothing here.
  attribute_condition = "assertion.repository.lowerAscii() == \"${lower(var.github_repo)}\""

  # The mapped attribute is lowercased too, so the principalSet binding below
  # can be lowercased as well and the whole chain stops caring about casing.
  # Mapping the raw claim here instead would reintroduce the problem: a
  # principalSet is a literal string with no room to normalise, so it would have
  # to reproduce the repo's stored casing exactly.
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository.lowerAscii()"
  }

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "deployer" {
  account_id   = var.deployer_account_id
  display_name = "Cloud Run deployer (GitHub Actions)"
}

resource "google_project_iam_member" "deployer_roles" {
  for_each = toset([
    "roles/run.admin",
    "roles/artifactregistry.writer",
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Lets the deployer act as the runtime service account when it deploys a
# revision. Scoped to that one account rather than granted project-wide.
resource "google_service_account_iam_member" "deployer_acts_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_service_account_iam_member" "github_impersonates_deployer" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${lower(var.github_repo)}"
}

# ---------------------------------------------------------------------------
# Runtime identity. The app reads only files baked into its own image, so this
# account holds no project roles at all -- it exists so the service does not
# run as the broadly-privileged compute default service account.
# ---------------------------------------------------------------------------
resource "google_service_account" "runtime" {
  account_id   = var.runtime_account_id
  display_name = "Cloud Run runtime for ${var.service_name}"
}

# ---------------------------------------------------------------------------
# The Cloud Run service
# ---------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "app" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.runtime.email
    timeout         = "${var.request_timeout_seconds}s"

    # Set above the vCPU count on purpose. A sweep pins one core for its whole
    # duration, and this headroom is what keeps the cheap requests -- static
    # assets, /api/scenarios, /api/health -- answering while one is running.
    # The app's own semaphore (MAX_CONCURRENT_SIMULATIONS) is what stops the
    # headroom from turning into several sweeps thrashing one instance.
    max_instance_request_concurrency = var.container_concurrency

    # No session_affinity: the service is stateless. Every request carries its
    # full configuration in the body and gets its whole result back inline, so
    # there is no per-instance session pinning a visitor to one instance. That
    # is exactly what lets Cloud Run scale out under concurrent load.
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          memory = var.memory
          cpu    = var.cpu
        }
        # Request-based billing: CPU is allocated (and charged) only while
        # serving a request, so an idle service at min_instances = 0 is free.
        cpu_idle = true
        # Cold starts load numpy/scipy/pandas; the boost cuts several seconds
        # off the first request and is not billed extra.
        startup_cpu_boost = true
      }

      env {
        name  = "LOG_LEVEL"
        value = var.log_level
      }

      # Compute envelope. Defaults are sized so the worst request a client can
      # ask for still finishes well inside request_timeout_seconds -- see
      # variables.tf for the measurements behind the numbers.
      env {
        name  = "MAX_N_SIMULATIONS"
        value = tostring(var.max_n_simulations)
      }
      env {
        name  = "MAX_HORIZON_DAYS"
        value = tostring(var.max_horizon_days)
      }
      env {
        name  = "MAX_CONCURRENT_SIMULATIONS"
        value = tostring(var.max_concurrent_simulations)
      }

      startup_probe {
        http_get {
          path = "/api/health"
          port = 8080
        }
        initial_delay_seconds = 5
        period_seconds        = 5
        timeout_seconds       = 5
        failure_threshold     = 12
      }

      liveness_probe {
        http_get {
          path = "/api/health"
          port = 8080
        }
        period_seconds    = 60
        timeout_seconds   = 10
        failure_threshold = 3
      }
    }
  }

  lifecycle {
    # The GitHub Actions workflow deploys new images outside Terraform;
    # don't fight it on plan/apply.
    ignore_changes = [
      template[0].containers[0].image,
      client,
      client_version,
    ]
  }

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Custom domain.
#
# Terraform owns this for the same reason it owns the service config: a mapping
# created by hand is invisible here, and the failure mode is silent. DNS
# pointing at ghs.googlehosted.com with no mapping registered returns a bare
# 404 from Google's frontend -- the hostname resolves, so it looks like an app
# problem rather than a missing resource.
#
# Prerequisites Terraform cannot do for you:
#   - the domain must be verified for the account (gcloud domains
#     list-user-verified), and
#   - the CNAME must exist in Cloudflare as DNS-only (grey cloud), or Google
#     cannot complete the challenge to issue the managed certificate.
# ---------------------------------------------------------------------------
resource "google_cloud_run_domain_mapping" "app" {
  count    = var.custom_domain == "" ? 0 : 1
  name     = var.custom_domain
  location = google_cloud_run_v2_service.app.location

  metadata {
    namespace = var.project_id
  }

  spec {
    route_name = google_cloud_run_v2_service.app.name
  }
}

# Public access (skipped if var.public = false)
resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.public ? 1 : 0
  name     = google_cloud_run_v2_service.app.name
  location = google_cloud_run_v2_service.app.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
