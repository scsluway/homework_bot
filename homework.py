import os
import time
from http import HTTPStatus

import logging
import requests
from telebot import TeleBot
from dotenv import load_dotenv

import exception

load_dotenv()

FORMATTER = '%(asctime)s, %(levelname)s, %(message)s'

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    format=FORMATTER
)
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler('main.log'))

formatter = logging.Formatter(FORMATTER)

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


def check_tokens():
    """Проверка наличия переменных окружения."""
    for environment_variable in (
        PRACTICUM_TOKEN,
        TELEGRAM_CHAT_ID,
        TELEGRAM_TOKEN
    ):
        if not environment_variable:
            logging.critical(
                'Отсутствует обязательная переменная окружения: '
                f'{environment_variable}'
            )
            raise exception.ThereIsNoToken


def send_message(bot, message):
    """Отправка сообщения ботом пользователю в Телеграм."""
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    logging.debug('message')


def get_api_answer(timestamp):
    """Проверка успешного ответа API."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    finally:
        if response.status_code == HTTPStatus.OK:
            return response.json()
        message = (
            f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен. '
            f'Код ответа API: {HTTPStatus.NOT_FOUND}'
        )
        logging.error(message)
        raise exception.WrongApiAnswer


def check_response(response):
    """Проверяет ответ API на соответствие ожидаемых ключей."""
    if (
        not isinstance(response, dict)
        or not isinstance(response.get('homeworks'), list)
    ):
        raise exception.KeyNotFoundError


def parse_status(homework):
    """Проверка изменеия статуса работы."""
    status = homework.get('status')
    if status in HOMEWORK_VERDICTS and homework.get('homework_name'):
        homework_name = homework.get('homework_name')
        verdict = HOMEWORK_VERDICTS.get(status)
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        raise exception.StatusCodeError


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    response = get_api_answer(timestamp)

    while True:
        try:
            check_response(response)
            message = parse_status(response.get('homeworks')[0])
            send_message(bot, message)
        except exception.KeyNotFoundError:
            if response.get('code') == 'UnknownError':
                message = (
                    f'Сбой в работе программы: Передано неожиданное значение. '
                    f'Код ответа API: {HTTPStatus.BAD_REQUEST}'
                )
                logging.error(message)
                send_message(bot, message)
            elif response.get('code') == 'not_authenticated':
                message = (
                    f'Сбой в работе программы: {response.get("message")}. '
                    f'Код ответа API: {HTTPStatus.UNAUTHORIZED}'
                )
                logging.error(message)
                send_message(bot, message)
            else:
                message = 'Отсутствие ожидаемых ключей.'
                logging.error(message)
                send_message(bot, message)
        except IndexError:
            logging.debug('Получен пустой список домашних работ.')
        except exception.StatusCodeError as status:
            message = f'Неожиданный статус домашней работы {status}'
            logging.error(message)
            send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
