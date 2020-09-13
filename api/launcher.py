"""
Что не стал прикручивать в тестовом задании, но что стал бы прикручивать в проде:

- Логирование
- Отладочный режим
- Систему исключений приложения
- Всяческие валидации и проверки
- Спецификацию (например OpenAPI)
- Возможно, полноценный промежуточный слой консистентного кэширования

Ну и вообще многие незнакомые мне вещи сделаны на минималках с настройками по умолчанию.
В ходе получения опыта, механизмы и стратегии будут модернизироваться.
"""


from typing import Dict, Any
import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi_utils.tasks import repeat_every
from config import config

from src.data_manager import DataManager
from src.db import DBShortlinks, LazyDBShortlinks, ShortlinkNotFound, Installer

app = FastAPI()

def _get_db_host() -> str:
    """
    Определяет хост подключения к БД. Берет из конфига, если не найден в переменных окружения.
    Не знаю, как обычно принято делать в таких проектах, пока опыта нет, сделал так.
    """
    try:
        host = os.environ['SHORTLINKS_DB_HOST']
    except KeyError:
        host = config.DB_HOST
    return host

def _db_connect(lazy: bool=False) -> DBShortlinks:
    db_factory = LazyDBShortlinks if lazy else DBShortlinks
    host = _get_db_host()
    db = db_factory(
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        host=host,
    )
    return db

def get_datamanager() -> DataManager:
    """
    Используется как зависимость FastAPI
    """
    db = _db_connect(lazy=True)
    data_manager = DataManager(db)
    return data_manager


def database_check_or_init():
    """
    Проверяет наличие БД и схемы, и создает всё нужное при необходимости
    """
    host = _get_db_host()
    installer = Installer(
        dbname='postgres', user=config.DB_USER, password=config.DB_PASSWORD, host=host)
    installer.init_database()


@app.on_event('startup')
async def init():
    """
    При старте сервиса проверяем БД
    """
    try:
        database_check_or_init()
    except Exception as e:
        raise Exception(f'Failed to connect to datamanager: {e}')


@app.on_event('startup')
@repeat_every(seconds=config.BACKGROUND_WORKER_INTERVAL, wait_first=True)
async def background_worker():
    """
    При желании можно сделать воркеры с разными периодами.
    Для флуша кэша короткий, для обслуживания - длинный.
    """
    data_manager = get_datamanager()
    data_manager.flush_writeback_cache()
    data_manager.shortlink_deactivate_all_expired()
    data_manager.shortlink_delete_all_expired()

@app.on_event('shutdown')
async def shutdown():
    data_manager = get_datamanager()
    data_manager.flush_writeback_cache()


# ----------------------------------- API методы -------------------------------------

@app.get("/link/{short}")
async def get_shortlink(short: str, data_manager: DataManager = Depends(get_datamanager)) -> Dict[str, str]:
    """
    Получить полную ссылку
    """
    try:
        link = data_manager.shortlink_get(short)
    except ShortlinkNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {short: link}

@app.get('/link/')
async def get_shortlinks(limit: int = 1000, offset: int = 0, datamanager: DataManager = Depends(get_datamanager)) -> Dict[str, Any]:
    """
    Получить список всех ссылок (метод не для прода)
    """
    shortlinks = datamanager.shortlinks_get(limit, offset)
    return shortlinks

@app.put("/link/")
async def create_shortlink(origin: str, data_manager: DataManager = Depends(get_datamanager)) -> str:
    """
    Создать короткую ссылку
    """
    short = data_manager.shortlink_create(origin)
    return short


@app.delete("/link/")
async def delete_shortlink(short: str, data_manager: DataManager = Depends(get_datamanager)):
    """
    Удалить короткую ссылку (удаляет упреждающе, без проверки на наличие)
    """
    data_manager.shortlink_delete(short)



