output "service_url" {
  description = "Public URL of the deployed service"
  value       = google_cloud_run_v2_service.app.uri
}

output "service_name" {
  value = google_cloud_run_v2_service.app.name
}

# The three values below go straight into GitHub Actions repository secrets.
# See infra/README.md.

output "gcp_project_id" {
  description = "Value for the GCP_PROJECT_ID repository secret"
  value       = var.project_id
}

output "gcp_workload_identity_provider" {
  description = "Value for the GCP_WORKLOAD_IDENTITY_PROVIDER repository secret"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "gcp_deploy_service_account" {
  description = "Value for the GCP_DEPLOY_SERVICE_ACCOUNT repository secret"
  value       = google_service_account.deployer.email
}

output "image_repository" {
  description = "Artifact Registry path the deploy workflow pushes to"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${var.repo_name}"
}
