# 1. Остановить всё нахуй
docker compose down -v

# 2. Удалить все контейнеры (все, не только из этого проекта)
docker rm -f $(docker ps -aq) 2>/dev/null

# 3. Удалить все образы
docker rmi -f $(docker images -q) 2>/dev/null

# 4. Удалить все тома (volumes) с кешами
docker volume rm $(docker volume ls -q) 2>/dev/null

# 5. Очистить билд-кеш (самое важное блядь)
docker builder prune -af

# 6. Системная чистка всего подряд
docker system prune -af --volumes