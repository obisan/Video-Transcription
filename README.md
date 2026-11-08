[![Version](https://img.shields.io/github/v/release/marc-shade/VIdeo-Transcription?style=flat-square)](https://github.com/marc-shade/VIdeo-Transcription/releases)
[![License](https://img.shields.io/github/license/marc-shade/VIdeo-Transcription?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Ollama](https://img.shields.io/badge/Ollama-000000?style=flat-square&logo=ollama&logoColor=white)](https://ollama.ai)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)

## Уже настроено — просто запустить

Docker Desktop запущен, образ собран, модель `qwen3.8:latest` скачана.

1. PowerShell, окно не закрывать:

```powershell
$env:OLLAMA_HOST="0.0.0.0:11434"
ollama serve
```

2. Второе окно, каталог проекта:

```powershell
cd D:\Projects\VIdeo-Transcription
docker compose up -d
```

3. Браузер: [http://localhost:8501](http://localhost:8501)

В сайдбаре модель `qwen3.8:latest`. Дальше **Upload & Transcribe**.

Выключить:

```powershell
cd D:\Projects\VIdeo-Transcription
docker compose down
```

В окне с `ollama serve` нажмите `Ctrl+C`. База в `data\` остаётся.

---

# AI Video Transcription

Форк [marc-shade/VIdeo-Transcription](https://github.com/marc-shade/VIdeo-Transcription).

Streamlit-приложение транскрибирует видео через Whisper и строит AI-персоны по расшифровке. В этом форке контейнер приложения подключается к **уже запущенному Ollama на Windows**, модель по умолчанию — `qwen3.8:latest`. Отдельный контейнер Ollama не поднимается.

```
Видео → аудио (FFmpeg) → текст (Whisper) → персона и чат (Ollama / Qwen)
                                              ↓
                                    экспорт SRT / VTT / MD / JSON / TXT
```

## Проверенная конфигурация

- Windows, Docker Desktop
- Ollama слушает порт `11434`
- Модель `qwen3.8:latest` (около 17 ГБ)
- Каталог моделей: `D:\LLM\ollama\models`
- Приложение: `http://localhost:8501`

## Что изменено относительно upstream

Правки уже в репозитории. Повторно править файлы перед запуском не нужно.

| Место | Зачем |
| --- | --- |
| `docker-compose.yml` | Только сервис `app`. `OLLAMA_API_BASE=http://host.docker.internal:11434`, `DEFAULT_MODEL=qwen3.8:latest`, база в `/app/data/transcription.db` |
| `main.py` | Проверка Ollama и настройки по умолчанию смотрят на `host.docker.internal:11434` и `qwen3.8:latest`. Внутри контейнера `localhost:11434` — это сам контейнер, не хост |
| `database.py`, `batch_processor.py` | Путь к SQLite берётся из `DATABASE_PATH`. Файл лежит в смонтированном `./data`, куда у процесса есть право записи |

`host.docker.internal` резолвится Docker Desktop в адрес хоста. Так контейнер достучится до Ollama на Windows.

## Запуск

### 1. Ollama на всех интерфейсах

Контейнер ходит на хост по сети. Ollama должен слушать `0.0.0.0:11434`, а не только `127.0.0.1`.

Остановите текущий процесс Ollama, если он уже запущен. В отдельном окне PowerShell:

```powershell
$env:OLLAMA_HOST="0.0.0.0:11434"
ollama serve
```

Если Windows Firewall спросит доступ, разрешите его для частных сетей. Это окно оставьте открытым.

Проверка:

```powershell
netstat -ano | Select-String ":11434"
```

В выводе должны быть `0.0.0.0:11434` и `[::]:11434` в состоянии `LISTENING`.

Модель, если её ещё нет:

```powershell
ollama pull qwen3.8:latest
```

### 2. Сборка и запуск контейнера

Docker Desktop должен быть запущен. В каталоге проекта:

```powershell
docker compose up -d --build
```

Первая сборка скачивает образ Python и модель Whisper `base` внутрь образа. Это занимает заметно больше времени, чем повторный старт.

Статус:

```powershell
docker compose ps
```

Ожидаемый статус: `Up (healthy)`.

### 3. Связь контейнера с Ollama

```powershell
docker exec video-transcription curl -s http://host.docker.internal:11434/api/tags
```

В JSON должен быть тег `qwen3.8:latest`. Пустой ответ или ошибка соединения значит, что Ollama не слушает `0.0.0.0:11434` или файрвол режет доступ с Docker-сети.

### 4. Первый прогон в браузере

1. Откройте `http://localhost:8501`.
2. В блоке **Add New Client** создайте клиента: имя, email, **Add Client**.
3. Раскройте **AI Settings** и проверьте модель `qwen3.8:latest`. Если выбрана другая — выберите эту и нажмите **Save Settings**.
4. На вкладке **Upload & Transcribe** загрузите короткое видео (до 2 минут), включите таймкоды и нажмите **Transcribe to Text**.

Whisper `base` уже в образе. Первый анализ через Qwen дольше следующих: Ollama загружает модель в видеопамять. На проверенной машине это RX 7900 XT, первый проход занимает несколько минут.

## Команды

```powershell
docker compose up -d          # старт
docker compose logs -f app    # логи приложения
docker compose ps             # статус и healthcheck
docker compose up -d --build  # пересборка после правок кода
docker compose down           # остановка
```

`docker compose down` не удаляет `./data`. База `data/transcription.db` остаётся на диске.

## Почта клиенту

После расшифровки текст уходит на email выбранного клиента. На вкладке **Upload & Transcribe** за это отвечает галочка **Email the transcript to this client** (включена по умолчанию). Пакетная очередь шлёт письмо сама.

Сервер исходящей почты задаётся в сайдбаре, блок **Email**:

1. SMTP host, порт и тип защиты.
2. Username, пароль и адрес From (обычно тот же, что Username).
3. **Save email**, затем **Send test**. Тестовое письмо приходит на From.

Пароль пишется в `data/smtp.json` и в git не попадает. Ошибка отправки не стирает расшифровку: текст остаётся в базе, в интерфейсе будет предупреждение.

| Почта | Host | Порт | Защита |
| --- | --- | --- | --- |
| Яндекс | `smtp.yandex.ru` | 465 | SSL |
| Gmail | `smtp.gmail.com` | 587 | STARTTLS |

Нужен пароль приложения, обычный пароль от ящика почтовый сервер не примет. Письмо клиенту: тема «Расшифровка: имя файла», текст расшифровки во вложении `.txt`. Если выбран перевод, он уходит вторым вложением.

Те же поля можно задать переменными `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_SECURITY` (`STARTTLS` или `SSL`). Сохранённый `smtp.json` их перекрывает.

## Переменные окружения

Заданы в `docker-compose.yml`:

```env
OLLAMA_API_BASE=http://host.docker.internal:11434
DEFAULT_MODEL=qwen3.8:latest
STREAMLIT_SERVER_PORT=8501
DATABASE_PATH=/app/data/transcription.db
```

Смена модели в интерфейсе пишется в `settings.json` внутри контейнера и переживает перезапуск сессии, пока контейнер не пересоздан без этого файла. Значения в сайдбаре имеют приоритет над дефолтом из кода.

Чтобы взять другую уже скачанную модель, поменяйте `DEFAULT_MODEL` и дефолт `model` в `main.py` (`initialize_session_state` и сброс настроек в сайдбаре), затем пересоберите образ.

## Возможности

- Транскрибация видео через Whisper
- Плеер с переходом по таймкоду
- Поиск по тексту расшифровки
- Перевод расшифровки
- Генерация AI-персоны и чат с ней через локальный Ollama
- Выбор модели из списка, который отдаёт Ollama
- Клиенты и история расшифровок в SQLite
- Экспорт в SRT, VTT, Markdown, JSON, TXT

## Структура

```
VIdeo-Transcription/
├── main.py              # Streamlit-интерфейс
├── database.py          # SQLite
├── batch_processor.py   # пакетная очередь
├── utils.py             # аудио и Whisper
├── ai_persona.py        # персона и запросы к Ollama
├── docker-compose.yml   # сервис app → Ollama на хосте
├── Dockerfile
├── requirements.txt
└── data/                # transcription.db (том контейнера)
```

Таблицы SQLite: `clients`, `transcriptions`, `persona_prompts`.

## Если что-то не стартует

**Контейнер не видит Ollama.** Повторите шаг 1 и проверку `curl` из шага 3. Адрес в логах и в сайдбаре должен быть `http://host.docker.internal:11434`. `http://localhost:11434` из контейнера до хоста не доходит.

**`permission denied` на базу.** Путь должен быть `/app/data/transcription.db`, каталог `./data` смонтирован в `/app/data`. Так задано в `docker-compose.yml` и в `database.py`.

**Healthcheck долго в `starting`.** После `--build` приложение поднимается не сразу. Подождите `start_period` и посмотрите `docker compose logs -f app`.

**Модель не в списке.** `ollama list` на хосте должен показать `qwen3.8:latest`. Имя в UI совпадает с тегом Ollama, включая `:latest`.
