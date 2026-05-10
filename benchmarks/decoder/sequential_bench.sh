#!/bin/bash

cd code/decoder
git checkout "$COMMIT"
# Сохраняем текущую ветку/коммит
START_POINT=$(git rev-parse HEAD)

# Получаем 8 последних коммитов (хеши)
COMMITS=$(git log --format="%H" -n 4)
cd ../../
# Проверяем, что есть хотя бы 8 коммитов
COMMIT_COUNT=$(echo "$COMMITS" | wc -l)
if [ "$COMMIT_COUNT" -lt 4 ]; then
    echo "Ошибка: в репозитории меньше 8 коммитов (найдено: $COMMIT_COUNT)"
    exit 1
fi

# Перебираем коммиты
for COMMIT in $COMMITS; do
    echo "========================================="
    echo "Переключаемся на коммит: $COMMIT"

    # Чекаутим коммит
    cd code/decoder
    git checkout "$COMMIT"
    if [ $? -ne 0 ]; then
        echo "Ошибка: не удалось переключиться на коммит $COMMIT"
        git checkout "$START_POINT"
        exit 1
    fi
    cd ../../

    # Запускаем ваш скрипт (укажите путь к вашему скрипту)
    make david_rebuild
    cat code/tvav.obu > /dev/null && \
    hyperfine --warmup 1 --runs 3 --export-json "$COMMIT.json" 'code/decoder/build/tools/dav1d -i code/tvav.obu -o /dev/null --threads 1'
    # ./ваш_скрипт.sh  # Раскомментируйте и укажите правильный путь
    cd code/decoder
    # Если скрипт возвращает ошибку, можно прервать выполнение
    if [ $? -ne 0 ]; then
        echo "Ошибка: ваш скрипт завершился с ошибкой на коммите $COMMIT"
        git checkout "$START_POINT"
        exit 1
    fi
    cd ../../
done

echo "========================================="
echo "Возвращаемся в исходное состояние..."
cd code/decoder
# Возвращаемся в исходную точку
git checkout "$START_POINT"

# Хард ресет до HEAD
git reset --hard HEAD
cd ../../
echo "Готово!"