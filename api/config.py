
"""
Для этого проекта не стал городить YAML или что-то гибкое и удобное.
Но если потребуется, прикрутим прозрачно, не затрагивая клиентский код.
"""

class config:
    SHORTLINK_TTL_SOFT = 60 * 60 * 24 * 3
    SHORTLINK_TTL_HARD = 60 * 60 * 24 * 7

    # Каленькие размеры кэшей стоят для удобства демонстрации.
    # В проде можно ставить десятки/сотни тысяч, в зависимости от оперативки.
    CACHE_READ_MAXSIZE = 5
    CACHE_WRITE_MAXSIZE = 3

    # Короткий интервал выбран тоже для отладки. На деле можно обслуживать сервис раз в несколько минут.
    BACKGROUND_WORKER_INTERVAL = 10 # seconds

    DB_NAME     = 'shortlinks'
    DB_USER     = 'postgres'
    DB_PASSWORD = '123123'
    DB_HOST     = '127.0.0.1'

    SELECT_HARD_LIMIT = 1000

