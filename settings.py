#!/usr/bin/env python3
"""
  settings.py

  This file is a part of the AppMetrica.

  Copyright 2017 YANDEX

  You may not use this file except in compliance with the License.
  You may obtain a copy of the License at:
        https://yandex.com/legal/metrica_termsofuse/
"""
from datetime import timedelta
import json
from os import environ
from os.path import join, dirname
from dotenv import load_dotenv

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

DEFAULT_STATE_FILE_PATH = join(dirname(__file__), 'data', 'state.json')
DEFAULT_LOGS_API_HOST = 'https://api.appmetrica.yandex.ru'

DEBUG = environ.get('DEBUG', '0') == '1'

TOKEN = environ['TOKEN']
APP_IDS = json.loads(environ['APP_IDS'])
SOURCES = json.loads(environ.get('SOURCES', '[]'))  # empty == all
EVENT_NAMES = json.loads(environ.get('EVENT_NAMES', '[]')) # empty = no events

UPDATE_LIMIT = timedelta(days=int(environ.get('UPDATE_LIMIT', '30')))
UPDATE_LIMIT_UNTIL = timedelta(days=int(environ.get('UPDATE_LIMIT_UNTIL', '7')))
UPDATE_INTERVAL = timedelta(hours=int(environ.get('UPDATE_INTERVAL', '12')))
REQUEST_CHUNK_ROWS = int(environ.get('REQUEST_CHUNK_ROWS', '25000'))

STATE_FILE_PATH = environ.get('STATE_FILE_PATH', DEFAULT_STATE_FILE_PATH)

LOGS_API_HOST = environ.get('LOGS_API_HOST', DEFAULT_LOGS_API_HOST)
ALLOW_CACHED = environ.get('ALLOW_CACHED', '0') == '1'

CH_HOST = environ.get('CH_HOST', 'http://localhost:8123')
CH_USER = environ.get('CH_USER')
CH_PASSWORD = environ.get('CH_PASSWORD')
CH_DATABASE = environ.get('CH_DATABASE', 'mobile')
