import logging
import logging.handlers
import os
import sys
import time
from contextlib import suppress
from http import HTTPStatus

import requests
from telebot import TeleBot, apihelper
from dotenv import load_dotenv

load_dotenv()

FORMATTER = '%(asctime)s, %(funcName)s, %(levelname)s, %(message)s'

logger = logging.getLogger(__name__)
logger.setLevel(level=logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
handler.setFormatter(logging.Formatter(FORMATTER))


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

variable_token_names = (
    'PRACTICUM_TOKEN',
    'TELEGRAM_TOKEN',
    'TELEGRAM_CHAT_ID'
)


def check_message(message, previous_message, bot):
    """Не допускает отрпавку повторных сообщений."""
    if message != previous_message:
        send_message(bot, message)
        return message
    return previous_message


def check_tokens():
    """Проверка наличия переменных окружения."""
    missing_tokens = [
        name for name in variable_token_names
        if globals()[name] is None or len(globals()[name]) == 0
    ]
    if len(missing_tokens):
        message = (
            'Отсутствуют обязательные переменные окружения: '
            f'{missing_tokens}'
        )
        logger.critical(message)
        raise ValueError(message)


def send_message(bot, message):
    """Отправка сообщения ботом пользователю в Телеграм."""
    logger.debug('Сообщение готовится к отправке.')
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logger.debug(message)


def get_api_answer(timestamp):
    """Возвращает ответ API, если получен ожидаемый результат."""
    try:
        logger.debug('Готовится запрос к отрпавке.')
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.RequestException as error:
        raise ValueError(
            f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен. '
            f'Код ответа API: {error}'
        )
    else:
        status = response.status_code
        if status == HTTPStatus.OK:
            logger.debug('Ответ на запрос успешно получен.')
            return response.json()
        else:
            raise ValueError(
                f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен. '
                f'Код ответа API: {status}'
            )


def check_response(response):
    """Проверяет ответ API на соответствие ожидаемых ключей."""
    logger.debug('Начало проверки ответа API.')
    if not isinstance(response, dict):
        raise TypeError(f'Объект {response} не является словарем.')
    elif response.get('homeworks') is None:
        raise KeyError(
            f'Отсутствие ключа homeworks в объекте {response}.'
        )
    elif not isinstance(response.get('homeworks'), list):
        raise TypeError('Ключ homeworks не является списком.')
    elif len(response.get('homeworks')) == 0:
        raise IndexError('Получен пустой список домашних работ.')
    logger.debug('Проверка ответа успешно завершена.')


def parse_status(homework):
    """Проверка изменеия статуса работы."""
    logger.debug('Проверка изменения статуса работы.')
    if homework.get('status') is not None:
        status = homework.get('status')
        if homework.get('homework_name') is None:
            raise KeyError(
                f'Отсутствие ключа homework_name в списке {homework}.'
            )
        elif HOMEWORK_VERDICTS.get(status) is None:
            raise KeyError(f'Неожиданный статус домашней работы {status}')
        else:
            homework_name = homework.get('homework_name')
            verdict = HOMEWORK_VERDICTS.get(status)
            logger.debug('Проверка изменения статуса работы завершена.')
            return (f'Изменился статус проверки работы "{homework_name}". '
                    f'{verdict}')
    else:
        raise KeyError(f'Отсутствие ключа status в списке {homework}.')


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            message = parse_status(response.get('homeworks')[0])
            previous_message = check_message(message, previous_message, bot)
            timestamp = int(time.time())
        except TypeError as error:
            logger.error(error)
            previous_message = check_message(error, previous_message, bot)
        except KeyError as error:
            logger.error(error)
            previous_message = check_message(error, previous_message, bot)
        except IndexError as error:
            logger.debug(error)
            previous_message = check_message(error, previous_message, bot)
        except ValueError as error:
            logger.error(error)
            previous_message = check_message(error, previous_message, bot)
        except apihelper.ApiTelegramException as error:
            logger.error(error)
            previous_message = check_message(error, previous_message, bot)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message, exc_info=True)
            with suppress(apihelper.ApiTelegramException):
                previous_message = check_message(error, previous_message, bot)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
