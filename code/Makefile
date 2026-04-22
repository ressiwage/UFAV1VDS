kill-everybody:
	./FUCKING-KILL-EVERYBODY.sh

up:
	docker compose up
down:
	docker compose down
up-nc:
	docker compose down; docker compose build --no-cache --pull && docker compose up --force-recreate

up-nc-a:
	docker compose up  --force-recreate --build api

up-nc-f:
	docker compose up  --force-recreate --build frontend

up-nc-g:
	docker compose up  --force-recreate --build gateway