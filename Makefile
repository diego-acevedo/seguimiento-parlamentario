PROJECT_ID ?= seguimiento-parlamentario

make fmt:
	black .

build:
	docker-compose build

run:
	docker-compose up --build

gcloud-deploy:
	gcloud builds submit --config=cloudbuild.yaml --substitutions=_PROJECT_ID=${PROJECT_ID} .
	gcloud run deploy session-processing \
		--image gcr.io/${PROJECT_ID}/session-processing \
		--set-env-vars "PROJECT_ID=${PROJECT_ID}" \
		--region=us-central1 \
		--platform=managed \
		--allow-unauthenticated