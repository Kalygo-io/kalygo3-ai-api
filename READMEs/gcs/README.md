# TLDR

Info regarding how the FastAPI was integrated with GCS (Google Cloud Storage)

## log

- Go to IAM & Admin section of the GCP console
- Created a Google S.A. with the `Storage Object User` role
- Create JSON key for using the S.A.
- Created a bucket called: `swarms`
- Add more permissions to the GCS S.A. account
  - gcloud projects add-iam-policy-binding 137963986378 \
    --member="serviceAccount:kalygo3-gcs-sa@kalygo-v3.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

## Permissions to CRUD to GCS

- NOTE: a different technique for importing the S.A. creds is needed in local (dev machine) vs production (Cloud Run)

## Needed to give SA in GitHub action an additional permission for giving a non-default S.A. when deploying Cloud Run services

- gcloud iam service-accounts add-iam-policy-binding kalygo3-gcs-sa@kalygo-v3.iam.gserviceaccount.com \
  --member="serviceAccount:kalygo3-sa@kalygo-v3.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

- gcloud projects add-iam-policy-binding 137963986378 \
  --member="serviceAccount:kalygo3-gcs-sa@kalygo-v3.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

## WTF

--service-account kalygo3-gcs-sa@kalygo-v3.iam.gserviceaccount.com

##

Added `Storage Admin` to default GCP service account

##

roles/storage.objectAdmin

##

gcloud projects get-iam-policy 137963986378 \
--flatten="bindings[].members" \
--format='table(bindings.role)' \
--filter="bindings.members:137963986378-compute@developer.gserviceaccount.com"

##

gcloud projects get-iam-policy 137963986378 \
--flatten="bindings[].members" \
--format='table(bindings.role)' \
--filter="bindings.members:kalygo3-gcs-sa@kalygo-v3.iam.gserviceaccount.com"

##

gcloud projects add-iam-policy-binding 137963986378 \
  --member="serviceAccount:137963986378-compute@developer.gserviceaccount.com" \
  --role="roles/storage.objectUser"

##

gcloud projects add-iam-policy-binding 137963986378 \
    --member="serviceAccount:137963986378-compute@developer.gserviceaccount.com" \
    --role="roles/iam.serviceAccountTokenCreator"

##

gcloud projects add-iam-policy-binding 137963986378 \
    --member="serviceAccount:kalygo3-gcs-sa@kalygo-v3.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountTokenCreator"

##

gcloud projects add-iam-policy-binding 137963986378 \
    --member="serviceAccount:kalygo3-gcs-sa@kalygo-v3.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

## 

Adding S.A. as secret and loading in with google.auth.load_credentials_from_dict()

## NEW DEMARKATION

- gcloud secrets create GCS_SA --data-file="gcs-sa.json"

- gcloud secrets add-iam-policy-binding GCS_SA \
    --member="serviceAccount:137963986378-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

- Add reference to GCS_SA secret in service.yaml
  - gcloud run services replace service.yaml --region us-east1

