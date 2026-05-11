.PHONY: init-storage test check-storage db-up db-down init-db check-db check-registry create-test-manifest

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
