# FastAPI + Docker + Google Cloud Run Deployment Blueprint

## One-Time Setup

These steps only need to be done once per project.

1. Enable Cloud Run & Cloud Build APIs
```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com
```
2. Authenticate and set your project
```
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```
3. Grant Cloud Run permissions to deploy
```
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')-compute@developer.gserviceaccount.com" \
  --role="roles/run.admin"
```

## For Every Code Update (Backend)
Deploy to Cloud Run
```
gcloud auth configure-docker
gcloud builds submit --tag gcr.io/uvpwebapp/uvpwebapp-backend:latest .
gcloud run deploy uvpwebapp-backend \
  --image gcr.io/uvpwebapp/uvpwebapp-backend:latest \
  --region europe-west1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL="postgresql+asyncpg://app_user:S4fxMzqrp3%40cTC@ep-noisy-surf-a2mfuunr-pooler.eu-central-1.aws.neon.tech/geoapp"
```

## For Every Code Update (Frontend)
Deploy to GitHub Pages
```
npm run build
npm run deploy
```