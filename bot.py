# pylint: disable=C0116,C0115,C0114,C0103,R0903
import json
from datetime import datetime, timedelta, timezone
import logging
from os import environ
import random
import re

from telegram.ext import Dispatcher, Filters, MessageHandler, CommandHandler
from telegram import Update, Bot, ChatAction, ParseMode

import db
import postpone

logger = logging.getLogger()
logger.setLevel(logging.INFO)


MARKDOWN_SPECIAL_CHARACTERS = str.maketrans({
    '*': r'\*',
    '_': r'\_',
    '`': r'\`',
    '[': r'\['
})

def escape_md(string):
    return string.translate(MARKDOWN_SPECIAL_CHARACTERS)


def next_weekday(dt: datetime, weekday: int):
    days_ahead = weekday - dt.weekday()
    if days_ahead <= 0: # Target day already happened this week
        days_ahead += 7
    return dt + timedelta(days_ahead)

def next_month(dt: datetime):
    cur_month = dt.month
    cur_year = dt.year
    if cur_month == 12:
        new_month = 1
        new_year = cur_year + 1
    else:
        new_month = cur_month + 1
        new_year = cur_year
    return dt.replace(month=new_month, year=new_year, day=1)

def calc_postpone_due_for(now: datetime, postpone_for):
    if postpone_for.data == 'int':
        value = postpone_for.children[0].value

        if len(postpone_for.children) == 2:
            unit = postpone_for.children[1].value
        else:
            unit = None

        if unit == 'h':
            seconds = value * 3600
        elif unit == 'd':
            seconds = value * 3600 * 24
        elif not unit:
            seconds = value
        else:
            raise NotImplementedError(unit)

        due = now + timedelta(seconds=seconds)
    elif postpone_for.data == 'human':
        value = postpone_for.children[0].value

        if value == 'few days':
            days = random.randint(2, 5)
            due = now + timedelta(days=days)
            due = due.replace(hour=0, minute=0)
        elif value == 'few hours':
            hours = random.randint(2, 5)
            due = now + timedelta(hours=hours)
    else:
        raise NotImplementedError(postpone_for.data)

    return due

def calc_postpone_due_to(now: datetime, postpone_to):
    if postpone_to.data == "human":
        postpone_time, = postpone_to.children
        human_to = postpone_time.value.lower()
        if human_to == 'next month':
            due = next_month(now)
        elif human_to == 'next week':
            due = next_weekday(now, 0)
        elif human_to.startswith('mon'):
            due = next_weekday(now, 0)
        elif human_to.startswith('tue'):
            due = next_weekday(now, 1)
        elif human_to.startswith('wed'):
            due = next_weekday(now, 2)
        elif human_to.startswith('thu'):
            due = next_weekday(now, 3)
        elif human_to.startswith('fri'):
            due = next_weekday(now, 4)
        elif human_to == 'weekend' or human_to.startswith('sat'):
            due = next_weekday(now, 5)
        elif human_to.startswith('sun'):
            due = next_weekday(now, 6)
        elif human_to == 'tomorrow':
            due = now + timedelta(days=1)
    else:
        raise NotImplementedError(postpone_time.data)

    return due.replace(hour=0, minute=0)

def calc_postpone_due(now: datetime, command):
    if command.data == 'for':
        postpone_for, = command.children
        due = calc_postpone_due_for(now, postpone_for)
    elif command.data == "to":
        postpone_to, = command.children
        due = calc_postpone_due_to(now, postpone_to)
    return due

def request_status_update(bot, user, card):
    text = f"How's task *{escape_md(card.name)}* progressing?"
    keyboard = [
        [{'text': '/postpone for a few hours'}],
        [{'text': '/postpone to tomorrow'}],
        [{'text': '/postpone for a few days'}],
        [{'text': '/postpone to the next week'}],
        [{'text': '/postpone to the next month'}],
        [{'text': '/complete'}]
    ]

    reply_markup = {
        'keyboard': keyboard,
        'resize_keyboard': True,
        'one_time_keyboard': True
    }
    bot.send_message(
        user.telegram_user_id,
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=json.dumps(reply_markup)
    )
    user.context_card = card

def remind_user(bot, user):
    utcnow = datetime.now(timezone.utc)

    for card in user.trello_upcoming_cards:
        if card.is_due_complete or card.closed:
            continue
        if not card.due_date or card.due_date < utcnow:
            request_status_update(bot, user, card)
            break

def cron(event, context): # pylint: disable=W0613
    bot = Bot(token=environ['TELEGRAM_TOKEN'])

    for user in db.UserModel.scan():
        if not user.in_card_context or user.context_is_stale:
            remind_user(bot, user)

    return {
        'statusCode': 200
    }


DUE_PATTERNS = [
    {
        'pattern': re.compile('завтра', re.IGNORECASE),
        'due': lambda now: (now + timedelta(days=1)).replace(hour=0, minute=0),
    }
]

def message_handler(update: Update, context): # pylint: disable=W0613
    update.effective_chat.send_action(ChatAction.TYPING)

    user = db.UserModel.get(update.effective_user.id)
    #if user.in_card_context:
    #    update.effective_message.reply_text("Please report card status first", quote=True)
    #    return

    text = update.effective_message.text

    lists = user.trello_board.list_lists()
    list0 = lists[0]
    card = list0.add_card(name=text)
    request_status_update(context.bot, user, card)

def postpone_handler(update: Update, context):
    update.effective_chat.send_action(ChatAction.TYPING)

    user = db.UserModel.get(update.effective_user.id)

    if not user.in_card_context:
        update.effective_message.reply_text("Not in the card context", quote=True)
        return

    saying = ' '.join(context.args).lower()

    try:
        command = postpone.parse(saying)
    except Exception as e: # pylint: disable=W0703
        logger.exception(e)
        update.effective_message.reply_text("Sorry, I don't understand", quote=True)
        return

    card = user.context_card
    now = datetime.now(user.timezone)
    due = calc_postpone_due(now, command)
    utcdue = due.astimezone(timezone.utc)
    card.set_due(utcdue)

    text = due.strftime(f"Task *{escape_md(card.name)}* postponed to %A (%d %b) %H:%M")
    reply_markup = {'remove_keyboard': True}
    update.effective_message.reply_text(
        text,
        quote=True,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=json.dumps(reply_markup),
        disable_notification=True
    )

    user.context_card = None

def complete_handler(update: Update, context):  # pylint: disable=W0613
    update.effective_chat.send_action(ChatAction.TYPING)

    user = db.UserModel.get(update.effective_user.id)

    if not user.in_card_context:
        update.effective_message.reply_text("Not in the card context", quote=True)
        return

    utcnow = datetime.now(timezone.utc)
    card = user.context_card
    if not card.due:
        card.set_due(utcnow)
    card.set_due_complete()

    text = f"Task *{escape_md(card.name)}* marked as complete"
    reply_markup = {'remove_keyboard': True}
    update.effective_message.reply_text(
        text,
        quote=True,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=json.dumps(reply_markup),
        disable_notification=True
    )

    user.context_card = None

def agenda_handler(update: Update, context): # pylint: disable=W0613
    update.effective_chat.send_action(ChatAction.TYPING)

    user = db.UserModel.get(update.effective_user.id)
    if user.in_card_context:
        update.effective_message.reply_text("Please report card status first", quote=True)
        return

    day = datetime.now(timezone.utc) + timedelta(days=1)
    upcoming_cards = user.trello_upcoming_cards
    on_agenda = lambda c: not c.due_date or c.due_date < day
    agenda_cards = filter(on_agenda, upcoming_cards)
    text = '\n'.join([f'➤ {c.name}' for c in agenda_cards])
    update.effective_chat.send_message(text, disable_web_page_preview=True)

def update_handler(update: Update, context): # pylint: disable=W0613
    update.effective_chat.send_action(ChatAction.TYPING)

    user = db.UserModel.get(update.effective_user.id)
    if user.in_card_context:
        update.effective_message.reply_text("Please report card status first", quote=True)
        return

    pattern = ' '.join(context.args)
    if not pattern:
        update.effective_message.reply_text("Usage: /update <pattern>", quote=True)
        return

    found = False
    for card in user.trello_upcoming_cards:
        if re.search(pattern, card.name, flags=re.IGNORECASE):
            found = True
            request_status_update(context.bot, user, card)
            break

    if not found:
        update.effective_message.reply_text("No tasks found", quote=True)

def webhook(event, context): # pylint: disable=W0613
    bot = Bot(token=environ['TELEGRAM_TOKEN'])
    dispatcher = Dispatcher(bot, None, use_context=True)
    dispatcher.add_handler(MessageHandler(Filters.text, message_handler))
    dispatcher.add_handler(CommandHandler('agenda', agenda_handler))
    dispatcher.add_handler(CommandHandler('update', update_handler))
    dispatcher.add_handler(CommandHandler('postpone', postpone_handler))
    dispatcher.add_handler(CommandHandler('complete', complete_handler))
    try:
        dispatcher.process_update(
            Update.de_json(json.loads(event["body"]), bot)
        )
        status_code = 200
    except Exception as e: # pylint: disable=W0703
        logger.exception(e)
        status_code = 500
    return {
        'statusCode': status_code
    }

