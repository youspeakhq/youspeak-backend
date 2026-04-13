// Multi-target build: core (runtime) + migration in parallel from the same Dockerfile.
// Used by CI to replace two sequential build-push-action steps with one bake call.
//
// Variables are set by the CI workflow via environment or --set flags.

variable "REGISTRY" {
  default = ""
}

variable "IMAGE_TAG" {
  default = "latest"
}

variable "CACHE_REPO" {
  default = ""
}

target "core" {
  dockerfile = "Dockerfile"
  target     = "runtime"
  tags = [
    "${REGISTRY}:${IMAGE_TAG}",
    "${REGISTRY}:latest",
  ]
  cache-from = CACHE_REPO != "" ? ["type=registry,ref=${CACHE_REPO}:cache"] : []
  cache-to   = CACHE_REPO != "" ? ["type=registry,mode=max,image-manifest=true,oci-mediatypes=true,ref=${CACHE_REPO}:cache"] : []
}

target "migration" {
  dockerfile = "Dockerfile"
  target     = "migration"
  tags = [
    "${REGISTRY}:migration",
    "${REGISTRY}:migration-${IMAGE_TAG}",
  ]
}

group "default" {
  targets = ["core", "migration"]
}
