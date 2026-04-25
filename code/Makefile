kill-everybody:
	./FUCKING-KILL-EVERYBODY.sh

up:
	docker compose up
down:
	docker compose down
up-nc:
	docker compose down; docker compose build --no-cache --pull && docker compose up --force-recreate

up-nc-da:
	docker compose up  --force-recreate --build decoder-api

up-nc-ca:
	docker compose up  --force-recreate --build common-api

up-nc-f:
	docker compose up  --force-recreate --build frontend

up-nc-g:
	docker compose up  --force-recreate --build gateway