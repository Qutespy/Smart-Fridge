# Smart Fridge + DeepSeek AI Assistant

## Как запустить
### Backend
```bash
cd smart_fridge_core
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed.py
uvicorn main:app --reload --port 8000
```

### GUI
```bash
cd gui-files
pip install flask requests
python app.py
```

## Как использовать
1. Открой GUI на `http://127.0.0.1:5001`
2. Войди под demo-пользователем: `demo@smartfridge.com / demo123`
3. Перейди в `AI-assistant`
4. Опиши цель и ограничения 
    В ограничениях пропиши: 
    не выдумывай ингредиенты
    не предлагай замен, если в базе их нет
    используй только recipe DB
    не называй отсутствующим то, что есть в inventory
5. Нажми `Начать`

## Что делает ассистент
- читает inventory семьи
- берет кандидатов из базы рецептов
- отправляет их в DeepSeek
- получает персональные рецепты в JSON
- показывает лучший вариант, недостающие ингредиенты и шаги приготовления

## ИИ-рецепты (GigaChat)

Отдельная фича на странице `/recipe`: ИИ подбирает рецепт по содержимому холодильника.

1. Получить ключ на https://developers.sber.ru/portal/products/gigachat-api
   (вход через Sber ID, без банковской карты, ~1 млн токенов/мес бесплатно)
2. Скопировать `.env.example` в `.env` в корне репозитория и вписать ключ:
   ```
   GIGACHAT_CREDENTIALS=ваш_ключ_base64
   GIGACHAT_SCOPE=GIGACHAT_API_PERS
   GIGACHAT_MODEL=GigaChat
   GIGACHAT_VERIFY_SSL=false
   ```
3. Доустановить зависимость и перезапустить бэкенд:
   ```bash
   cd smart_fridge_core
   source .venv/bin/activate
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8000
   ```
4. Открыть `http://127.0.0.1:5001/recipe` под demo-пользователем — справа сверху появится кнопка «🤖 Подобрать рецепт ИИ».

В холодильнике должно быть минимум 3 продукта. Ингредиенты в карточке помечаются 🟢 (есть в холодильнике) или 🟡 (надо докупить, с предложением замен). Если ключ не задан — фронт покажет «⚠️ Сервис ИИ временно недоступен».
