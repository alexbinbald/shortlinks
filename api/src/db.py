
import psycopg2
from psycopg2 import DatabaseError
from psycopg2.errorcodes import DUPLICATE_DATABASE

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from psycopg2.extensions import connection as psql_connection, cursor as psql_cursor

from config import config

class ShortlinkNotFound(Exception): pass
class NoFreeShortlinks(Exception): pass


class _Connector:
    """
    Слой подключения к БД и выполнения запросов.
    """
    _connection: 'psql_connection'
    _dbname: str
    _user: str
    _password: str
    _host: str

    def __init__(self, dbname: str, user: str, password: str, host: str):
        self._dbname = dbname
        self._user = user
        self._password = password
        self._host = host

    def _connect(self):
        self._connection = psycopg2.connect(
            dbname=self._dbname, user=self._user, password=self._password, host=self._host)

    def execute(self, query, vars=None) -> 'psql_cursor':
        cursor = self._get_cursor()
        cursor.execute(query, vars)
        return cursor

    def _get_cursor(self) -> 'psql_cursor':
        return self._connection.cursor()

    def commit(self):
        self._connection.commit()

    def autocommit_enable(self):
        self._connection.autocommit = True

    def autocommit_disable(self):
        self._connection.autocommit = False


class _SimpleConnector(_Connector):
    def __init__(self, dbname: str, user: str, password: str, host: str):
        super().__init__(dbname, user, password, host)
        self._connect()


class _LazyConnector(_Connector):
    """
    Это _Connector с ленивой инициализацией.
    Подключение к базе происходит в момент выполнения первого запроса.
    """
    _connected: bool

    def __init__(self, dbname: str, user: str, password: str, host: str):
        super().__init__(dbname, user, password, host)
        self._connected = False

    def _connect(self):
        super()._connect()
        self._connected = True

    def _get_cursor(self) -> 'psql_cursor':
        if not self._connected:
            self._connect()
        return super()._get_cursor()


class _DBEngine:
    _connector: _Connector
    _CONNECTOR_FACTORY = _SimpleConnector

    def __init__(self, dbname: str, user: str, password: str, host: str):
        self._dbname = dbname
        self._user = user
        self._password = password
        self._host = host
        self._connector = self._CONNECTOR_FACTORY(dbname=dbname, user=user, password=password, host=host)

    def _table_exists(self):
        query = """SELECT table_schema FROM information_schema.tables 
            WHERE table_schema='shortlinks' AND table_name='link'"""
        try:
            cursor = self._connector.execute(query)
        except DatabaseError:
            return False
        rows = cursor.fetchall()
        if rows:
            return True
        return False

    def _database_exists(self):
        query = """SELECT oid FROM pg_catalog.pg_database WHERE datname='shortlinks'"""
        cursor = self._connector.execute(query)
        rows = cursor.fetchall()
        if rows:
            return True
        return False

    def _reconnect_to_db_shortlinks(self):
        self._connector = self._CONNECTOR_FACTORY(
            dbname='shortlinks',
            user=self._user,
            password=self._password,
            host=self._host,
        )
        self._connector.autocommit_enable()



class DBShortlinks(_DBEngine):
    """
    Слой работы с БД shortlinks.

    Пока работает с одной таблицей. При росте количества таблиц
    можно распилить на категории наследованием или композицией.
    """

    def link_insert(self) -> int:
        query = """INSERT INTO shortlinks.link (date_access, status) VALUES (NOW(), 'active') RETURNING id"""
        cursor = self._connector.execute(query)
        row = cursor.fetchone()
        self._connector.commit()
        link_id = row[0]
        return link_id

    def link_select(self, short: str) -> str:
        query = """SELECT origin
            FROM shortlinks.link
            WHERE short=%s AND status IN ('active', 'inactive')"""
        cursor = self._connector.execute(query, (short,))
        row = cursor.fetchone()
        if not row:
            raise ShortlinkNotFound(f"Ссылка '{short}' не найдена")
        origin = row[0]
        return origin

    def links_select(self, limit: int, offset: int):
        if limit > config.SELECT_HARD_LIMIT:
            limit = config.SELECT_HARD_LIMIT
        query = """SELECT short, origin, date_access, status FROM shortlinks.link LIMIT %s OFFSET %s"""
        cursor = self._connector.execute(query, (limit, offset))
        rows = cursor.fetchall()
        return rows

    def link_select_free(self) -> str:
        query = """SELECT short FROM shortlinks.link WHERE status='free' LIMIT 1"""
        cursor = self._connector.execute(query)
        row = cursor.fetchone()
        if not row:
            raise NoFreeShortlinks(f'Нет свободных ссылок')
        short = row[0]
        return short

    def link_reuse(self, short: str, origin: str):
        query = """UPDATE shortlinks.link SET origin=%s, date_access=NOW(), status='active' WHERE short=%s"""
        self._connector.execute(query, (origin, short))
        self._connector.commit()

    def link_actualize(self, short: str):
        query = """UPDATE shortlinks.link SET date_access=NOW(), status='active' WHERE short=%s"""
        self._connector.execute(query, (short,))
        self._connector.commit()

    def link_delete(self, short: str):
        query = """UPDATE shortlinks.link SET status='free', origin=NULL WHERE short=%s"""
        self._connector.execute(query, (short,))
        self._connector.commit()

    def link_set_expired_shortlinks(self, age: int):
        query = """UPDATE shortlinks.link SET status='free', origin=NULL 
            WHERE date_access < NOW() - INTERVAL '%s SECONDS' AND status = 'inactive'"""
        self._connector.execute(query, (age, ))
        self._connector.commit()

    def link_set_inactive_shortlinks(self, age: int):
        query = """UPDATE shortlinks.link SET status='inactive' 
            WHERE date_access < NOW() - INTERVAL '%s SECONDS' AND status = 'active'"""
        self._connector.execute(query, (age,))
        self._connector.commit()

    def link_fill(self, link_id: int, short: str, origin: str):
        query = """UPDATE shortlinks.link SET short=%s, origin=%s, date_access=NOW(), status='active'
            WHERE id=%s"""
        self._connector.execute(query, (short, origin, link_id))
        self._connector.commit()


class LazyDBShortlinks(DBShortlinks):
    """
    То же, что и DBShortlinks, только с ленивым коннектором.
    """
    _CONNECTOR_FACTORY = _LazyConnector


class Installer(DBShortlinks):
    """
    Проверяет и подготоавливает структуру БД
    """
    def __init__(self, dbname: str, user: str, password: str, host: str):
        super().__init__(dbname=dbname, user=user, password=password, host=host)
        self._connector.autocommit_enable()

    def _schema_create(self):
        print('Создание структуры БД...')
        script_file = open('src/db_init.sql', 'r')
        script = script_file.read()
        script_file.close()
        self._connector.execute(script)

    def _database_create(self):
        print('Создание БД shortlinks...')
        query = """CREATE DATABASE shortlinks"""
        try:
            self._connector.execute(query)
        except DatabaseError as e:
            if e.pgcode != DUPLICATE_DATABASE:
                raise

    def init_database(self):
        if not self._database_exists():
            self._database_create()
        self._reconnect_to_db_shortlinks()
        if not self._table_exists():
            self._schema_create()

