.PHONY: migration migrate downgrade migration-current migration-history create-admin create-user auth-smoke users-smoke dictionaries-smoke airports-smoke runways-smoke declared-distances-smoke standards-smoke ols-generation-smoke manual-ols-smoke ols-data-smoke ols-revisions-smoke dtm-smoke obstacles-smoke violations-smoke remaining-workflows-smoke

migration:
	@test -n "$(message)" || (echo 'Usage: make migration message="describe change"' && exit 1)
	docker compose exec api alembic revision --autogenerate -m "$(message)"

migrate:
	docker compose exec api alembic upgrade head

downgrade:
	docker compose exec api alembic downgrade -1

migration-current:
	docker compose exec api alembic current

migration-history:
	docker compose exec api alembic history --verbose

create-admin:
	@test -n "$(username)" -a -n "$(email)" -a -n "$(first_name)" -a -n "$(last_name)" || (echo 'Usage: make create-admin username=admin email=admin@example.com first_name=Admin last_name=User' && exit 1)
	docker compose exec api python -m app.scripts.create_admin --username "$(username)" --email "$(email)" --first-name "$(first_name)" --last-name "$(last_name)"

create-user:
	@test -n "$(username)" -a -n "$(email)" -a -n "$(first_name)" -a -n "$(last_name)" -a -n "$(role)" || (echo 'Usage: make create-user username=user email=user@example.com first_name=First last_name=Last role=VIEWER' && exit 1)
	docker compose exec api python -m app.scripts.create_admin --username "$(username)" --email "$(email)" --first-name "$(first_name)" --last-name "$(last_name)" --role "$(role)"

auth-smoke:
	docker compose exec -T api python -m tests.auth_smoke

users-smoke:
	docker compose exec -T api python -m tests.users_smoke

dictionaries-smoke:
	docker compose exec -T api python -m tests.dictionaries_smoke

airports-smoke:
	docker compose exec -T api python -m tests.airports_smoke

runways-smoke:
	docker compose exec -T api python -m tests.runways_smoke

declared-distances-smoke:
	docker compose exec -T api python -m tests.runways_smoke

standards-smoke:
	docker compose exec -T api python -m tests.standards_smoke

ols-generation-smoke:
	docker compose exec -T api python -m tests.ols_generation_smoke

manual-ols-smoke:
	docker compose exec -T api python -m tests.manual_ols_smoke

ols-data-smoke:
	docker compose exec -T api python -m tests.ols_generation_smoke

ols-revisions-smoke:
	docker compose exec -T api python -m tests.ols_generation_smoke

dtm-smoke:
	docker compose exec -T api python -m tests.dtm_smoke

obstacles-smoke:
	docker compose exec -T api python -m tests.obstacles_smoke

violations-smoke:
	docker compose exec -T api python -m tests.ols_generation_smoke

remaining-workflows-smoke:
	docker compose exec -T api python -m tests.remaining_workflows_smoke
