#!/usr/bin/env python
# pylint: disable=C0116
# This program is dedicated to the public domain under the CC0 license.

"""
First, a few callback functions are defined. Then, those functions are passed to
the Dispatcher and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Example of a bot-user conversation using ConversationHandler.
Send /start to initiate the conversation.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging
from typing import Dict

from telegram import ReplyKeyboardMarkup, Update, ReplyKeyboardRemove
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackContext,
)

from ptb_firebase_persistence import FirebasePersistence

from dotenv import load_dotenv
from os import getenv
import json
load_dotenv()  # take environment variables from .env.

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

CHOOSING, TYPING_REPLY_TEXT, TYPING_REPLY_TIME = range(3)
SET_TASK_TEXT = 'Set task'
SHOW_MY_TASKS_TEXT = 'Show my tasks'
reply_keyboard = [
    [SET_TASK_TEXT, SHOW_MY_TASKS_TEXT]
]
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
updater = None

def facts_to_str(user_data: Dict[str, str]) -> str:
    facts = []

    for key, value in user_data.items():
        facts.append(f'{key} - {value}')

    return "\n".join(facts).join(['\n', '\n'])


def start(update: Update, context: CallbackContext) -> int:
    reply_text = "Hi! I will help you to not forget things"
    context.chat_data['started'] = True
    if context.user_data:
        reply_text += (
            f"\nI see we met before already"
        )
    else:
        reply_text += (
            "Nice to get you know"
        )
    update.message.reply_text(reply_text, reply_markup=markup)

    return CHOOSING


def set_task_choice(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('What shall I ask you about?')
    return TYPING_REPLY_TEXT


def received_information_text(update: Update, context: CallbackContext) -> int:
    text = update.message.text
    context.user_data['text_for_upcoming_task'] = text
    update.message.reply_text(
        "Ok, I will ask you about:"
        f"{text}"
        "\nWhen should I do this?",
    )

    return TYPING_REPLY_TIME


def received_information_time(update: Update, context: CallbackContext) -> int:
    task_time = update.message.text
    task_text = context.user_data['text_for_upcoming_task']
    task = {
        "time": task_time,
        "text": task_text,
    }
    if 'tasks' not in context.user_data:
        context.user_data['tasks'] = []

    context.user_data['tasks'].append(task)

    def callback_minute(ctx):
        context.bot.send_message(update.effective_user.id, text=task_text)
        if 'answers' not in context.user_data:
            context.user_data['answers'] = []

        context.user_data['tasks'].append({
            "question": task_text,
            "answer": "" # How get text here?
        })
    #     How to switch state ofr handler


    if updater:
        print('Assign task')
        updater.job_queue.run_repeating(callback_minute, interval=int(task_time))


    del context.user_data['text_for_upcoming_task']

    update.message.reply_text(
        "Ok, I will ask you about:"
        f"{task_text} at {task_time}"
        "Can I do something else for you?",
        reply_markup=markup,
    )

    return CHOOSING


def show_data(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        f"This is what you already told me: {facts_to_str(context.user_data)}"
    )


def done(update: Update, context: CallbackContext) -> int:
    if 'choice' in context.user_data:
        del context.user_data['choice']

    update.message.reply_text(
        "I learned these facts about you:" f"{facts_to_str(context.user_data)}Until next time!",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


with open(getenv('FIREBASE_CREDENTIALS_FILE')) as json_file:
    credentials = json.load(json_file)


def main() -> None:
    global updater
    # Create the Updater and pass it your bot's token.
    persistence = FirebasePersistence(database_url=getenv('FIREBASE_URL'), credentials=credentials)
    updater = Updater(getenv('TELEGRAM_TOKEN'),  persistence=persistence)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Add conversation handler with the states CHOOSING, TYPING_CHOICE and TYPING_REPLY
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING: [
                MessageHandler(Filters.regex(f'^{SET_TASK_TEXT}$'), set_task_choice),
                # MessageHandler(Filters.regex(f'^{SHOW_MY_TASKS_TEXT}$'), show_tasks_choice),
            ],
            TYPING_REPLY_TEXT: [
                MessageHandler(
                    Filters.text & ~(Filters.command | Filters.regex('^Done$')),
                    received_information_text,
                    )
            ],
            TYPING_REPLY_TIME: [
                MessageHandler(
                    Filters.text & ~(Filters.command | Filters.regex('^Done$')),
                    received_information_time,
                    )
            ],
        },
        fallbacks=[MessageHandler(Filters.regex('^Done$'), done)],
        name="my_conversation",
        persistent=True,
    )

    dispatcher.add_handler(conv_handler)

    show_data_handler = CommandHandler('show_data', show_data)
    dispatcher.add_handler(show_data_handler)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
