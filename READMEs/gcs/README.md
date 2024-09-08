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