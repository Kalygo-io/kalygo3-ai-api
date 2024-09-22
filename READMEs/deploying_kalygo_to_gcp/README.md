# TLDR

Documenting steps of setting up Kalygo on GCP

## FRONTEND

### Setting up project

- `gcloud config list`
- `gcloud config set project kalygo`
- `gcloud auth login`
- `gcloud auth application-default set-quota-project kalygo-436411`
- `gcloud config list`

- `gcloud config configurations list`
- `gcloud services enable compute.googleapis.com`
- `gcloud config configurations create kalygo`
  - `gcloud config set account [YOUR_EMAIL]`
  - `gcloud config set project kalygo-436411`
  - `gcloud config set compute/zone us-east1-b`
  - `gcloud config set compute/region us-east1`

### Creating Artifact Registry

- `gcloud services enable artifactregistry.googleapis.com`
- Create artifact in Artifact Registry
``` template
gcloud artifacts repositories create REPOSITORY \
  --repository-format=docker \
  --location=LOCATION \
  --description="DESCRIPTION" \
  --immutable-tags \
  --async
```
``` ie:
gcloud artifacts repositories create kalygo-nextjs \
  --repository-format=docker \
  --location=us-central1 \
  --description="Docker repository for Kalygo web app" \
  --immutable-tags \
  --async
```
- CONFIRM ARTIFACT WAS CREATED: `https://console.cloud.google.com/artifacts?hl=en&project=kalygo-v3`
  - `gcloud artifacts repositories list`

### SIDETRACKED

- Noticed `fullstack vectors` was still incurring billing which makes sense
- So restored the project and then manually deleted the resources incurring costs as deleting a project has a retention policy of 30 days while resources are still being deleted

### Cloud Build

- update `next.config.mjs` <!-- Already was done -->
  - REFERENCE: https://nextjs.org/docs/pages/api-reference/next-config-js/output#automatically-copying-traced-files
  ```
  /** @type {import('next').NextConfig} */
  const nextConfig = {
    // reactStrictMode: true,
    output: "standalone",
  };
  export default nextConfig;
  ```
- REFERENCE: https://cloud.google.com/build/docs/build-push-docker-image#build_an_image_using_a_build_config_file
- `touch cloudbuild.yaml`
- `gcloud services enable cloudbuild.googleapis.com`
- `gcloud builds submit --region=us-central1 --config cloudbuild.yaml`
  - REFERENCE: https://cloud.google.com/build/docs/locations#restricted_regions_for_some_projects
- CONFIRM IMAGE WAS STORED: `https://console.cloud.google.com/artifacts/docker/kalygo-v3/us-east1/kalygo3-nextjs?hl=en&project=kalygo-v3`

### Copied the `kalygo3` UI project

- Copied the `kalygo3` Next.js UI project to another project called `swarms-playground-ui`
- Eventually will switch over kalygo3 code to power Kalygo's site when the `swarms-playground` repo is set up
- Then will have a repo for each project

  - Created a Service Account called `swarms-playground-repos-cicd@kalygo-v3.iam.gserviceaccount.com` for the new `swarms-playground-ui` repo
  - Add `GCP_SA_KEY` as a repository secret
  - Add the following permission to the newly created Service Account
  ```
  1. gcloud projects add-iam-policy-binding kalygo-v3 \
  --member="serviceAccount:swarms-playground-repos-cicd@kalygo-v3.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"
  2. gcloud projects add-iam-policy-binding kalygo-v3 \
  --member="serviceAccount:swarms-playground-repos-cicd@kalygo-v3.iam.gserviceaccount.com" \
  --role="roles/run.admin"
  3. gcloud iam service-accounts add-iam-policy-binding 137963986378-compute@developer.gserviceaccount.com \
  --member="serviceAccount:swarms-playground-repos-cicd@kalygo-v3.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
  ```

## BACKEND

### Updating the GitHub action to use the new project `kalygo-436411`

### Create Artifact Registry for api

- Create artifact in Artifact Registry
``` template
gcloud artifacts repositories create REPOSITORY \
  --repository-format=docker \
  --location=LOCATION \
  --description="DESCRIPTION" \
  --immutable-tags \
  --async
```
``` ie:
gcloud artifacts repositories create kalygo-fastapi \
  --repository-format=docker \
  --location=us-central1 \
  --description="Docker repository for Kalygo FastAPI" \
  --immutable-tags \
  --async
```

### Testing CICD deployment

- 