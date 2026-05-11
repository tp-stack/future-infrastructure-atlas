.PHONY: init-storage test check-storage db-up db-down init-db check-db check-registry create-test-manifest ingest-fixture ingest-wri load-postgis build-map-data frontend-install frontend-dev frontend-build frontend-preview deploy-vercel

init-storage:
	python scripts/init_storage.py

test:
	pytest -q

check-storage:
	python -m atlas.storage .

db-up:
	docker compose up -d postgis

db-down:
	docker compose down

init-db:
	python scripts/init_db.py

check-db:
	python scripts/check_db.py

check-registry:
	python scripts/check_registry.py

create-test-manifest:
	python scripts/create_manifest.py --dataset-key wri_global_power_plants --file-path tests/fixtures/sample_power_plants.csv --output data/cache/sample_power_plants.raw_manifest.json

ingest-fixture:
	python scripts/ingest_dataset.py --dataset-key wri_global_power_plants --file-path tests/fixtures/sample_power_plants.csv

ingest-wri:
	python scripts/ingest_dataset.py --dataset-key wri_global_power_plants --file-path data/raw/wri_global_power_plants/global_power_plant_database.csv

load-postgis:
	python scripts/load_processed_to_postgis.py --processed-path data/processed/wri_global_power_plants

build-map-data:
	python scripts/build_web_map_data.py --max-public-mb 5

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

frontend-preview:
	cd frontend && npm run preview

deploy-vercel:
	cd frontend && vercel --prod
