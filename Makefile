.PHONY: init-storage test check-storage db-up db-down init-db check-db check-registry create-test-manifest ingest-fixture ingest-wri load-postgis build-map-data build-map-data-legacy build-pmtiles-inputs build-atlas-core build-pmtiles check-atlas-core check-pmtiles check-frontend-data frontend-install frontend-dev frontend-build frontend-preview deploy-vercel validate-all

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
	python scripts/build_web_map_data.py --cable-geometry-csv data/raw/submarine_cable_geometries/kmcd_manual_20260511/world_submarine_cable_geometries_kmcd.csv --allow-license-review --max-public-mb 5

build-map-data-legacy:
	python scripts/build_web_map_data.py --max-public-mb 5

build-pmtiles-inputs:
	python scripts/build_pmtiles_inputs.py

build-atlas-core:
	python scripts/build_atlas_core.py

build-pmtiles:
	python scripts/build_pmtiles.py --all --max-public-mb 25

check-atlas-core:
	python scripts/check_atlas_core.py

check-pmtiles:
	python scripts/check_pmtiles_outputs.py --max-public-mb 25

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

check-frontend-data:
	python scripts/check_frontend_data.py

frontend-preview:
	cd frontend && npm run preview

deploy-vercel:
	cd frontend && vercel --prod

validate-all: init-storage check-registry build-map-data check-frontend-data build-atlas-core test check-storage frontend-build
