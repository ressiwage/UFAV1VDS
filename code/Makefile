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

bench_ram:
	cmdbench -v -a -j ../benchmarks/dav1d.json -p ../benchmarks/dav1d.png -i 1 "sh ../benchmarks/decoder/dav1d_mem.sh"

ghcr_login:
	bash ./ghcr_login.sh

ghcr_publish:
	bash ./ghcr_publish.sh

install_servers:
	bash ./install_servers.sh

up-swarm:
	docker pull ghcr.io/ressiwage/decoder-api:latest

delete-unused:
	docker images -q | xargs docker rmi -f 2>/dev/null; docker system prune -af --volumes

deploy: 
	docker stack deploy -c docker-stack.yml myapp
force-redeploy:
	bash ./ghcr_hard_refresh.sh
force_redeploy-react:
	docker service update --force --image ghcr.io/ressiwage/frontend:latest myapp_frontend

gigapull:
	bash ./gigapull.sh