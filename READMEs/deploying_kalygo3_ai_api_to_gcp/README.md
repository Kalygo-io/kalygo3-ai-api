# TLDR

Documenting process of deploying Kalygo 3.0 A.I. API to GCP

## ToC

1. Artifact Registry
2. Cloud Build
3. Add Google Secrets 
4. Cloud Run
5. CICD with Github Actions

## 1. Artifact Registry

- TODO: setup gcloud inside of Devcontainer
- `gcloud artifacts repositories create kalygo3-fastapi --repository-format docker --project kalygo-v3 --location us-central1`
- CONFIRM REPOSITORY WAS CREATED: `https://console.cloud.google.com/artifacts?hl=en&project=kalygo-v3`
## 2. Cloud Build

- `gcloud builds submit --region=us-central1 --config cloudbuild.yaml`
  - CONFIRM IMAGE WAS STORED: `https://console.cloud.google.com/artifacts/docker/kalygo-v3/us-central1/kalygo3-fastapi?hl=en&project=kalygo-v3`

## 3. Add Application Secrets to GCP project

- `gcloud services list --enabled`
- `gcloud services enable secretmanager.googleapis.com`
- Add secrets
  - `echo -n "YOUR_SECRET_VALUE" | gcloud secrets create SECRET_NAME --data-file=-`
  - ie: `echo -n "your_anthropic_api_key" | gcloud secrets create ANTHROPIC_API_KEY --data-file=-`
  - ie: `echo -n "your_openai api key" | gcloud secrets create OPENAI_API_KEY --data-file=-`
  <!-- -->
  - ie: `echo -n "key for signing JWT" | gcloud secrets create AUTH_SECRET_KEY --data-file=-`
  - ie: `echo -n "hashing algorithm" | gcloud secrets create AUTH_ALGORITHM --data-file=-`
  <!-- -->
  - ie: `echo -n "render.com url" | gcloud secrets create POSTGRES_URL --data-file=-`
  <!-- -->
  - ie: `echo -n "langsmith endpoint" | gcloud secrets create LANGCHAIN_ENDPOINT --data-file=-`
  - ie: `echo -n "langsmith API keys" | gcloud secrets create LANGCHAIN_API_KEY --data-file=-`
  <!-- -->
  - ie: `echo -n "cookie domain" | gcloud secrets create COOKIE_DOMAIN --data-file=-`
  <!-- -->
  - ie: `echo -n "pinecone api key" | gcloud secrets create PINECONE_API_KEY --data-file=-`
  <!-- -->
  - ie: `echo -n "swarms_workspace" | gcloud secrets create WORKSPACE_DIR --data-file=-`

  - ie: `echo -n "production" | gcloud secrets create ENVIRONMENT --data-file=-`

  - ie: `echo -n "https://demo.swarms.world" | gcloud secrets create API_HOSTNAME --data-file=-`

  <!-- -->
  - ie: `echo -n "us-east-1" | gcloud secrets create AWS_REGION --data-file=-`
  - ie: `echo -n "" | gcloud secrets create AWS_ACCESS_KEY_ID --data-file=-`
  - ie: `echo -n "" | gcloud secrets create AWS_SECRET_KEY --data-file=-`
  <!-- -->

  <!-- v NOT NEEDED? v --->
  - ie: `echo -n "embedding api url" | gcloud secrets create EMBEDDINGS_API_URL --data-file=-`
  - ie: `echo -n "REPLICATE_API_TOKEN" | gcloud secrets create REPLICATE_API_TOKEN --data-file=-`
  - ie: `echo -n "all-minilm-l6-v2-384-dims" | gcloud secrets create PINECONE_ALL_MINILM_L6_V2_INDEX --data-file=-`
  - ie: `echo -n "imagebind-1024-dims" | gcloud secrets create PINECONE_IMAGEBIND_1024_DIMS_INDEX --data-file=-`
  <!-- ^ NOT NEEDED? ^ --->
  

- Verify secrets created in console
  - ie: `https://console.cloud.google.com/security/secret-manager?referrer=search&hl=en&project=kalygo-v3`

- Grant the Cloud Run service permission to access the secrets at runtime

- EXAMPLE: gcloud secrets add-iam-policy-binding SECRET_NAME \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding ANTHROPIC_API_KEY \
  --member="serviceAccount:830723611668-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding OPENAI_API_KEY \
  --member="serviceAccount:137963986378-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

<!-- -->

- gcloud secrets add-iam-policy-binding AWS_REGION \
  --member="serviceAccount:830723611668-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding AWS_ACCESS_KEY_ID \
  --member="serviceAccount:830723611668-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding AWS_SECRET_KEY \
  --member="serviceAccount:830723611668-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

<!-- -->

- gcloud secrets add-iam-policy-binding AUTH_SECRET_KEY \
  --member="serviceAccount:830723611668-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding AUTH_ALGORITHM \
  --member="serviceAccount:830723611668-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding POSTGRES_URL \
  --member="serviceAccount:137963986378-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding LANGCHAIN_ENDPOINT \
  --member="serviceAccount:830723611668-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding LANGCHAIN_API_KEY \
  --member="serviceAccount:137963986378-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding COOKIE_DOMAIN \
  --member="serviceAccount:830723611668-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding PINECONE_API_KEY \
  --member="serviceAccount:137963986378-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding WORKSPACE_DIR \
  --member="serviceAccount:137963986378-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding API_HOSTNAME \
  --member="serviceAccount:137963986378-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- MORE SECRETS WILL BE NEEDED

## 4. Cloud Run

- `gcloud run services replace service.yaml --region us-east1`
- `gcloud run services set-iam-policy kalygo3-nextjs-service gcr-service-policy.yaml --region us-east1`
