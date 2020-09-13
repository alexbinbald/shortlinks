
from typing import Dict, Any
from src.cache import CacheLRU, CacheWriteback
from src.db import DBShortlinks, NoFreeShortlinks
from src.shortlink_generator import shortlink_hash
from config import config


class DataManager:
    """
    Инструментарий работы с данными сервиса (Адаптер).

    Слой нужен как абстракция, чтобы Postgres можно было поменять
    на любую другую БД, ORM, файл, HTTP или какой-нибудь брокер, не затрагивая клиентский код.

    Кэш данных работает по упрощенной модели в виде поля класса, что сохраняет кэш
    при повторном создании датаменеджера (по сути Синглтон). В данном кейсе это просто и безопасно,
    но в более сложных архитектурах, потребуется другая модель.
    """
    _db: DBShortlinks
    _cache_lru = CacheLRU(maxsize=config.CACHE_READ_MAXSIZE)
    _cache_writeback = CacheWriteback(maxsize=config.CACHE_WRITE_MAXSIZE)

    def __init__(self, db: DBShortlinks):
        self._db = db

    def shortlink_get(self, short: str, update_access_date: bool = True) -> str:
        """
        Берет ссылку из базы и обновляет время доступа, если это указано в аргументах
        """
        origin = self._cache_lru.get(short, self._db.link_select, short)
        if update_access_date:
            self._cache_writeback.put(short, self._db.link_actualize, short)
        return origin

    def shortlinks_get(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        Получает группу ссылок из базы с дополнительной инфой (время доступа не обновляет)
        """
        rows = self._db.links_select(limit, offset)
        shortlinks = {short: (origin, status, date_access) for short, origin, status, date_access in rows}
        return shortlinks

    def shortlink_deactivate_all_expired(self):
        """
        Деактивация неиспользуемых ссылок
        """
        self._db.link_set_inactive_shortlinks(config.SHORTLINK_TTL_SOFT)

    def shortlink_delete_all_expired(self):
        """
        Освобождение давно неиспользуемых ссылок
        """
        self._db.link_set_expired_shortlinks(config.SHORTLINK_TTL_HARD)

    def shortlink_create(self, origin: str) -> str:
        """
        Активирует ранее освобожденную ссылку, либо создает новую.
        """
        try:
            short = self._db.link_select_free()
        except NoFreeShortlinks:
            link_id = self._db.link_insert()
            short = shortlink_hash(link_id)
            self._db.link_fill(link_id, short, origin)
            return short
        else:
            self._db.link_reuse(short, origin)
            self._cache_lru.delete(short)
            return short

    def shortlink_delete(self, short: str):
        """
        Освобождает любую ссылку безусловно
        """
        self._db.link_delete(short)
        self._cache_lru.delete(short)
        self._cache_writeback.delete(short)

    def flush_writeback_cache(cls):
        """
        Сбрасывает кэш обновления доступа к ссылкам в БД
        """
        cls._cache_writeback.flush()






