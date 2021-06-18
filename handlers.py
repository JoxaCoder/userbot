import config
from .database import database
from . import lang
from . import croco
from . import gallows
from .game import role_titles, stop_game
from .stages import stages, go_to_next_stage, format_roles, get_votes
from .bot import bot

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import re
import random
from time import time
from uuid import uuid4
from datetime import datetime
from pymongo.collection import ReturnDocument


def get_name(user):
    return '@' + user.username if user.username else user.first_name


def get_full_name(user):
    result = user.first_name
    if user.last_name:
        result += ' ' + user.last_name
    return result


def user_object(user):
    return {'id': user.id, 'name': get_name(user), 'full_name': get_full_name(user)}


def command_regexp(command):
    return f'^/{command}(@{bot.get_me().username})?$'


@bot.message_handler(regexp=command_regexp('help'))
@bot.message_handler(func=lambda message: message.chat.type == 'private', commands=['start'])
def start_command(message, *args, **kwargs):
    answer = (
        f'Привет, я {bot.get_me().first_name}!\n'
        'Я умею создавать игры в мафию в группах и супергруппах.\n'
        'Инструкция и исходный код: https://gitlab.com/r4rdsn/mafia_host_bot\n'
        'По всем вопросам пишите на https://t.me/r4rdsn'
    )
    bot.send_message(message.chat.id, answer)


def get_mafia_score(stats):
    return 2 * stats.get('win', 0) - stats['total']


def get_croco_score(stats):
    result = 3 * stats['croco'].get('win', 0)
    result += stats['croco'].get('guesses', 0)
    result -= stats['croco'].get('cheat', 0)
    return result / 25


@bot.message_handler(regexp=command_regexp('stats'))
def stats_command(message, *args, **kwargs):
    stats = database.stats.find_one({'id': message.from_user.id, 'chat': message.chat.id})

    if not stats:
        bot.send_message(message.chat.id, f'Статистика {get_name(message.from_user)} пуста.')
        return

    paragraphs = []

    if 'total' in stats:
        win = stats.get('win', 0)
        answer = (
            f'Счёт {get_name(message.from_user)} в мафии: {get_mafia_score(stats)}\n'
            f'Побед: {win}/{stats["total"]} ({100 * win // stats["total"]}%)'
        )
        roles = []
        for role, title in role_titles.items():
            if role in stats:
                role_win = stats[role].get('win', 0)
                roles.append({
                    'title': title,
                    'total': stats[role]['total'],
                    'win': role_win,
                    'rate': 100 * role_win // stats[role]['total']
                })
        for role in sorted(roles, key=lambda s: s['rate'], reverse=True):
            answer += (
                f'\n{role["title"].capitalize()}: '
                f'побед - {role.get("win", 0)}/{role["total"]} ({role["rate"]}%)'
            )
        paragraphs.append(answer)

    if 'croco' in stats:
        answer = f'Счёт {get_name(message.from_user)} в крокодиле: {get_croco_score(stats)}'
        total = stats['croco'].get('total')
        if total:
            win = stats['croco'].get('win', 0)
            answer += f'\nПобед: {win}/{total} ({100 * win // total}%)'
        guesses = stats['croco'].get('guesses')
        if guesses:
            answer += f'\nУгадано: {guesses}'
        paragraphs.append(answer)

    if 'gallows' in stats:
        right = stats['gallows'].get('right', 0)
        wrong = stats['gallows'].get('wrong', 0)
        win = stats['gallows'].get('win', 0)
        total = stats['gallows']['total']
        answer = f'Угадано букв в виселице: {right}/{right + wrong} ({100 * right // (right + wrong)}%)'
        answer += f'\nПобед: {win}/{total} ({100 * win // total}%)'
        paragraphs.append(answer)

    bot.send_message(message.chat.id, '\n\n'.join(paragraphs))


def update_rating(rating, name, score, maxlen):
    place = None
    for i, (_, rating_score) in enumerate(rating):
        if score > rating_score:
            place = i
            break
    if place is not None:
        rating.insert(place, (name, score))
        if len(rating) > maxlen:
            rating.pop(-1)
    elif len(rating) < maxlen:
        rating.append((name, score))


def get_rating_list(rating):
    return '\n'.join(f'{i + 1}. {n}: {s}' for i, (n, s) in enumerate(rating))
