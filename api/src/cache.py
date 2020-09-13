from typing import Dict, Any, Callable


class Cache:
    """
    Базовый класс для двух видов кэша (LRU и Writeback)

    Оба кэша работают как Proxy, то бишь запрос на чтение и запись данных
    осуществляется всегда через кэш-движок, а он уже решает, что и как кэшировать,
    когда чистить свои буфферы, когда читать/писать данные из реального источника.

    Адресация данных в кэше происходит по произвольному (уникальному) ключу,
    который указывает потребитель при обращении к кэшу. Это дает больше гибкости
    на стороне потребителя.

    Помимо ключа указывается функция прямого чтения/записи с параметрами, которую кэш-движку
    необходимо выполнить при прямом доступе к данным.

    Для отладки доступа к данным, минуя кэш, создан холостой кэш CacheDisabled.
    """
    _container: Dict[int, Any]

    def key_exists(self, key):
        if _CacheEntry.hash(key) in self._container:
            return True
        return False

    @property
    def container(self):
        return self._container

    def delete(self, key: Any):
        self._container.pop(_CacheEntry.hash(key), None)


class CacheLRU(Cache):
    """
    LRU-кэш, работает по принципу вытеснения самых старых данных.

    Гистерезис добавлен для оптимизации механизма чистки.
    Чтобы при максимальном размере очереди = 100, чистка запускалась на 120, и чистила сразу 20 записей.
    Без гистерезиса, полная чистка кэша запускалась бы на каждый запрос.
    """
    _DEFAULT_MAXSIZE_HYSTERESIS = 1.2

    def __init__(self, maxsize: int, hysteresis: float = None):
        self._hysteresis = hysteresis or self._DEFAULT_MAXSIZE_HYSTERESIS
        self._container: Dict[int, _CacheLRU_Entry] = {}
        self._epoch = 0
        self._maxsize_soft = maxsize
        self._maxsize_hard = int(self._maxsize_soft * self._hysteresis)

    def get(self, key: Any, func: Callable[..., Any], *args, **kwargs) -> Any:
        def functor():
            return func(*args, **kwargs)
        cached = _CacheLRU_Entry(key, functor)
        try:
            cached = self._container[hash(cached)]
        except KeyError:
            cached.load_data()
            self._container[hash(cached)] = cached
            if len(self._container) >= self._maxsize_hard:
                self.clean()
        self._epoch += 1
        cached.epoch = self._epoch
        return cached.value


    def clean(self):
        truncated = sorted(self._container.values(), key=lambda cached: cached.epoch)[-self._maxsize_soft:]
        actual_entries = {hash(cached): cached for cached in truncated}
        self._container = actual_entries


class CacheWriteback(Cache):
    """
    Writeback-кэш буфферизует данные, а потом сбрасывает их кучкой.
    """
    def __init__(self, maxsize: int):
        self._container: Dict[int, _CacheWriteback_Entry] = {}
        self._maxsize = maxsize

    def put(self, key: Any, func: Callable[..., Any], *args, **kwargs):
        def functor():
            return func(*args, **kwargs)
        deferred_task = _CacheWriteback_Entry(key, functor)
        self._container[hash(deferred_task)] = deferred_task
        if len(self._container) >= self._maxsize:
            self.flush()

    def flush(self):
        for deferred_task in self._container.values():
            deferred_task.execute()
        self._container.clear()


class CacheDisabled(Cache):
    def get(self, key: Any, func: Callable[..., Any], *args, **kwargs) -> Any:
        result = func(*args, **kwargs)
        return result

    def put(self, key: Any, func: Callable[..., Any], *args, **kwargs):
        func(*args, **kwargs)




class _CacheEntry:
    @staticmethod
    def hash(key):
        return hash(key)

    def __init__(self, key: Any, func: Callable[..., Any]):
        self._key: Any = key
        self._func: Callable[..., Any] = func

    def __hash__(self):
        return self.hash(self._key)


class _CacheLRU_Entry(_CacheEntry):
    def __init__(self, key: Any, func: Callable[..., Any]):
        super().__init__(key, func)
        self._value: Any = None
        self._epoch: int = 0

    def load_data(self):
        self._value = self._func()

    @property
    def value(self) -> Any:
        return self._value

    @property
    def epoch(self) -> int:
        return self._epoch

    @epoch.setter
    def epoch(self, epoch):
        self._epoch = epoch


class _CacheWriteback_Entry(_CacheEntry):
    def execute(self):
        result = self._func()
        return result