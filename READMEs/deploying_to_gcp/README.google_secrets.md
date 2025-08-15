##

- `gcloud services list --enabled`
- `gcloud services enable secretmanager.googleapis.com`

- `echo -n "YOUR_SECRET_VALUE" | gcloud secrets create SECRET_NAME --data-file=-`
- ie: `echo -n "your_anthropic_api_key" | gcloud secrets create ANTHROPIC_API_KEY --data-file=-`
- ie: `echo -n "openai api key" | gcloud secrets create OPENAI_API_KEY --data-file=-`

- ie: `echo -n "key for signing JWT" | gcloud secrets create AUTH_SECRET_KEY --data-file=-`
- ie: `echo -n "hashing algorithm" | gcloud secrets create AUTH_ALGORITHM --data-file=-`

- ie: `echo -n "render.com url" | gcloud secrets create POSTGRES_URL --data-file=-`

- ie: `echo -n "langsmith endpoint" | gcloud secrets create LANGSMITH_ENDPOINT --data-file=-`
- ie: `echo -n "langsmith API keys" | gcloud secrets create LANGSMITH_API_KEY --data-file=-`

- ie: `echo -n "cookie domain" | gcloud secrets create COOKIE_DOMAIN --data-file=-`

- ie: `echo -n "embedding api url" | gcloud secrets create EMBEDDINGS_API_URL --data-file=-`
- ie: `echo -n "pinecone api key" | gcloud secrets create PINECONE_API_KEY --data-file=-`
- ie: `echo -n "REPLICATE_API_TOKEN" | gcloud secrets create REPLICATE_API_TOKEN --data-file=-`
- ie: `echo -n "all-minilm-l6-v2-384-dims" | gcloud secrets create PINECONE_ALL_MINILM_L6_V2_INDEX --data-file=-`
- ie: `echo -n "imagebind-1024-dims" | gcloud secrets create PINECONE_IMAGEBIND_1024_DIMS_INDEX --data-file=-`

- ie: `echo -n "production" | gcloud secrets create ENVIRONMENT --data-file=-`

- ie: `echo -n "S.A. as a string" | gcloud secrets GCS_SA --data-file=-`

- CHECK OUT: `https://console.cloud.google.com/security/secret-manager?project=fullstack-rag`

## Granting Cloud Run the permissions to access secrets

- gcloud secrets add-iam-policy-binding SECRET_NAME \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

## ie: this should be scripted

- gcloud secrets add-iam-policy-binding ANTHROPIC_API_KEY \
  --member="serviceAccount:370967482684-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding POSTGRES_URL \   
  --member="serviceAccount:370967482684-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding AUTH_SECRET_KEY \  
  --member="serviceAccount:370967482684-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding AUTH_ALGORITHM \   
  --member="serviceAccount:370967482684-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding LANGSMITH_ENDPOINT \   
  --member="serviceAccount:370967482684-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding LANGSMITH_API_KEY \   
  --member="serviceAccount:370967482684-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding EMBEDDINGS_API_URL \
  --member="serviceAccount:370967482684-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding PINECONE_API_KEY \
  --member="serviceAccount:370967482684-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding PINECONE_ALL_MINILM_L6_V2_INDEX \
  --member="serviceAccount:370967482684-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding PINECONE_IMAGEBIND_1024_DIMS_INDEX \
  --member="serviceAccount:370967482684-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding OPENAI_API_KEY \
  --member="serviceAccount:370967482684-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding COOKIE_DOMAIN \
  --member="serviceAccount:370967482684-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding REPLICATE_API_TOKEN \
  --member="serviceAccount:370967482684-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

- gcloud secrets add-iam-policy-binding ENVIRONMENT \
  --member="serviceAccount:370967482684-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

  ## Steps to add a secret

  1. Add it to the Google Secrets Manager
    - ie: `echo -n "YOUR_SECRET_VALUE" | gcloud secrets create SECRET_NAME --data-file=-`
  2. Give the default google engine service account permissions to pull the secret at runtime
  ```
  gcloud secrets add-iam-policy-binding SECRET_ENV_VAR_VALUE \
  --member="serviceAccount:370967482684-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
  ```
  3. Add the reference to the new secret in the service.yaml spec
    - `gcloud run services replace service.yaml --region us-east1`
  4. After redeploying things should work

  FOR VERIFYING: https://console.cloud.google.com/run/detail/us-east1/fullstack-rag-fastapi-service/revisions?organizationId=355415429731&project=fullstack-rag