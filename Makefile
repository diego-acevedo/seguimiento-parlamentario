build:
	docker-compose build

run:
	docker-compose up --build

gcloud-deploy:
	gcloud builds submit --config=cloudbuild.yaml .
	gcloud run deploy session-processing --image gcr.io/seguimiento-parlamentario-cl/session-processing --set-env-vars "PROJECT_ID=seguimiento-parlamentario-cl" --region=us-central1 --platform=managed --allow-unauthenticated