from binascii import crc32
from typing import Callable

BASE_62_ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
BASE_64_ALPHABET = BASE_62_ALPHABET + '-_'

CRC32_PADDING_SIZE = 10


def build_base_x_encoder(alphabet: str) -> Callable[[int], str]:
    """
    Создает энкодер десятиричного числа в любую другую систему счисления, исходя из переданного алфавита.

    encode подсмотрено тут https://stackoverflow.com/questions/1119722/base-62-conversion
    и слегка переделано.
    """

    def encode(number: int) -> str:
        """
        Переводит число из 10-ричной системы в X-ричную. Не путать с кодированием данных в base64.
        """
        if number < 0:
            raise ValueError('number must be positive')  # иначе цикл бесконечного деления столбиком
        if number == 0:
            return alphabet[0]
        arr = []
        base = len(alphabet)
        while number:
            number, remainder = divmod(number, base)
            arr.append(alphabet[remainder])
        arr.reverse()
        return ''.join(arr)
    return encode


number_to_base64 = build_base_x_encoder(BASE_64_ALPHABET) # создаем энкодер в 64


def shortlink_hash(number: int) -> str:
    """
    Превращает число от 1 до 10 млн. в 6-значную строку символов.
    CRC32 хэш выбран, т.к. он быстрый и в этом диапазоне не даёт коллизий.
    Паддингом добивается до размера, который позволяет на выходе давать результаты одинаковой длины.

    Хэш так же нужен для нарушения визуального эффекта последовательности и предсказуемости результата,
    то бишь хэши чисел 1 и 2 отличаются полностью, а не только последним символом.

    Функция протестирована на всём диапазоне от 1 до 10 млн., не было обнаружено коллизий
    и не шестизначных последовательностей. Значения вне диапазона не тестировались,
    поэтому магические числа в конфиг и константы не выношу.
    Для других диапазонов возможно потребуется придумывать другой механизм.

    Алгоритм, прямо скажем, сомнительный, придуман на коленках и под конкретную задачу.
    Под что-то более гибкое и расширяемое нужно продумывать тщательнее.
    """
    if not 0 < number < 10_000_000:
        raise ValueError('Argument "number" out of range (0, 10_000_000)')
    padding = 10 ** CRC32_PADDING_SIZE
    return number_to_base64(crc32(number.to_bytes(4, 'big')) + padding)



