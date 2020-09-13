"""
Покрыл тестами модули, под капотом которых есть какие-то механизмы,
которые при рефакторинге легко сломать, и использование которых без тестов неочевидно.
"""

from unittest import TestCase
from src.shortlink_generator import build_base_x_encoder, shortlink_hash, number_to_base64
from src.cache import CacheLRU, CacheWriteback

class TestShortlinkGenerator(TestCase):
    def test_number_to_base64(self):
        with self.assertRaises(ValueError):
            number_to_base64(-1)
        self.assertEqual(number_to_base64(0), '0')
        self.assertEqual(number_to_base64(1), '1')
        self.assertEqual(number_to_base64(2), '2')
        self.assertEqual(number_to_base64(63), '_')
        self.assertEqual(number_to_base64(64), '10')
        self.assertEqual(number_to_base64(65), '11')


    def test_build_base_x_encoder(self):
        base2_encoder = build_base_x_encoder('01')
        self.assertEqual(base2_encoder(0), '0')
        self.assertEqual(base2_encoder(1), '1')
        self.assertEqual(base2_encoder(2), '10')

        base8_encoder = build_base_x_encoder('01234567')
        self.assertEqual(base8_encoder(1), '1')
        self.assertEqual(base8_encoder(7), '7')
        self.assertEqual(base8_encoder(8), '10')

        base16_encoder = build_base_x_encoder('0123456789abcdef')
        self.assertEqual(base16_encoder(1), '1')
        self.assertEqual(base16_encoder(10), 'a')
        self.assertEqual(base16_encoder(16), '10')


    def test_shortlink_hash(self):
        self.assertEqual(shortlink_hash(1), 'aGjZea')
        self.assertEqual(shortlink_hash(2), 'czlG8M')
        self.assertEqual(shortlink_hash(64), 'aHF8ac')
        self.assertEqual(shortlink_hash(65), '9QGV8q')
        self.assertEqual(shortlink_hash(9_999_999), 'a9YlJB')
        with self.assertRaises(ValueError):
            shortlink_hash(-1)
        with self.assertRaises(ValueError):
            shortlink_hash(0)
        with self.assertRaises(ValueError):
            shortlink_hash(10_000_000)


class TestCacheLRU(TestCase):
    def setUp(self):
        self.cache = CacheLRU(maxsize=10, hysteresis=1.5)

    def test_caching(self):
        """
        Методика тестирования: вызываем несколько раз функцию через кэш,
        контролируя количество прямых вызовов и наличие данных в кэше.
        """
        direct_call_counter = 0
        def func(x):
            nonlocal direct_call_counter
            direct_call_counter += 1
            return x * 2
        arg = 1
        self.assertFalse(self.cache.key_exists(arg))
        self.assertEqual(direct_call_counter, 0)
        result = self.cache.get(arg, func, arg)
        self.assertEqual(direct_call_counter, 1)
        self.assertEqual(result, 2)
        self.assertTrue(self.cache.key_exists(arg))
        result = self.cache.get(arg, func, arg)
        self.assertEqual(direct_call_counter, 1)
        self.assertEqual(result, 2)


    def test_flushing(self):
        """
        Методика тестирования: заполняем кэш до предела,
        контролируя его объем и механизм вытеснения старых данных.
        """
        def func(x):
            return x * 2
        self.assertEqual(len(self.cache.container), 0)
        for i in range(1, 15):
            self.cache.get(i, func, i)
        self.assertEqual(len(self.cache.container), 14)
        self.cache.get(15, func, 15)
        self.assertEqual(len(self.cache.container), 10)
        self.assertNotIn(1, self.cache.container)


class TestCacheWriteback(TestCase):
    def setUp(self):
        self.cache = CacheWriteback(maxsize=10)

    def test_caching(self):
        """
        Методика тестирования: пишем данные в некий реальный контейнер через кэш,
        контролируя буфферизацию и корректность данных на выходе.
        """
        real_data_container = []
        def func(x):
            real_data_container.append(x * 2)
        arg = 1
        self.assertFalse(self.cache.key_exists(arg))
        self.cache.put(arg, func, arg)
        self.assertNotIn(arg * 2, real_data_container)
        self.assertTrue(self.cache.key_exists(arg))
        self.cache.flush()
        self.assertIn(arg * 2, real_data_container)
        self.assertFalse(self.cache.key_exists(arg))

    def test_flushing(self):
        """
        Методика тестирования: набиваем кэш данными, контролируя срабатывание
        флуш-триггера и перенос данных в реальный контейнер.
        """
        real_data_container = []
        def func(x):
            real_data_container.append(x * 2)
        self.assertEqual(len(self.cache.container), 0)
        for i in range(1, 10):
            self.cache.put(i, func, i)
        self.assertEqual(len(self.cache.container), 9)
        self.assertEqual(len(real_data_container), 0)
        self.cache.put(10, func, 10)
        self.assertEqual(len(self.cache.container), 0)
        self.assertEqual(len(real_data_container), 10)


