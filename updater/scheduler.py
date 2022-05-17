#!/usr/bin/env python3
"""
  scheduler.py

  This file is a part of the AppMetrica.

  Copyright 2017 YANDEX

  You may not use this file except in compliance with the License.
  You may obtain a copy of the License at:
        https://yandex.com/legal/metrica_termsofuse/
"""
from datetime import datetime, date, time, timedelta
import logging
from time import sleep
from typing import List, Optional, Generator

import pandas as pd

from state import StateStorage, AppIdState
from fields import SchedulingDefinition

logger = logging.getLogger(__name__)


class UpdateRequest(object):
    ARCHIVE = 'archive'
    LOAD_ONE_DATE = 'load_one_date'
    LOAD_DATE_IGNORED = 'load_date_ignored'

    def __init__(self, source: str, event_name: str, app_id: str, p_date: Optional[date],
                 update_type: str):
        self.source = source
        self.event_name = event_name
        self.app_id = app_id
        self.date = p_date
        self.update_type = update_type


class Scheduler(object):
    ARCHIVED_DATE = datetime(3000, 1, 1)

    def __init__(self, state_storage: StateStorage,
                 scheduling_definition: SchedulingDefinition,
                 app_ids: List[str], event_names: List[str], update_limit: timedelta,
                 update_interval: timedelta, fresh_limit: timedelta):
        self._state_storage = state_storage
        self._definition = scheduling_definition
        self._app_ids = app_ids
        self._event_names = event_names
        self._update_limit = update_limit
        self._update_interval = update_interval
        self._fresh_limit = fresh_limit
        self._state = None

    def _load_state(self):
        self._state = self._state_storage.load()

    def _save_state(self):
        self._state_storage.save(self._state)

    def _get_or_create_app_id_state(self, app_id: str) -> AppIdState:
        app_id_states = [s for s in self._state.app_id_states
                         if s.app_id == app_id]
        if len(app_id_states) == 0:
            app_id_state = AppIdState(app_id)
            self._state.app_id_states.append(app_id_state)
        else:
            app_id_state = app_id_states[0]
        return app_id_state

    def _mark_date_updated(self, app_id_state: AppIdState, event_name: str, p_date: date,
                           now: Optional[datetime] = None):
        logger.debug('Data for {} event {} of {} is updated'.format(
            p_date, event_name, app_id_state.app_id
        ))
        if app_id_state.date_updates.get(event_name) is None:
            app_id_state.date_updates[event_name] = dict()
        app_id_state.date_updates[event_name][p_date] = now or datetime.now()
        self._save_state()

    def _mark_date_archived(self, app_id_state: AppIdState, event_name: str, p_date: date):
        logger.debug('Data for {} of {} is archived'.format(
            p_date, app_id_state.app_id
        ))
        if app_id_state.date_updates.get(event_name) is None:
            app_id_state.date_updates[event_name] = dict()
        app_id_state.date_updates[event_name][p_date] = self.ARCHIVED_DATE
        self._save_state()

    def _is_date_archived(self, app_id_state: AppIdState, event_name: str, p_date: date):
        if app_id_state.date_updates.get(event_name):
            updated_at = app_id_state.date_updates.get(event_name).get(p_date)
        else:
            updated_at = None
        return updated_at is not None and updated_at == self.ARCHIVED_DATE

    def _finish_updates(self, now: datetime = None):
        logger.debug('Updates are finished')
        self._state.last_update_time = now or datetime.now()
        self._save_state()

    def _wait_time(self, update_interval: timedelta,
                   now: datetime = None) \
            -> Optional[timedelta]:
        if not self._state.last_update_time:
            return None
        now = now or datetime.now()
        delta = self._state.last_update_time - now + update_interval
        if delta.total_seconds() < 0:
            return None
        return delta

    def _wait_if_needed(self):
        wait_time = self._wait_time(self._update_interval)
        if wait_time:
            logger.info('Sleep for {}'.format(wait_time))
            sleep(wait_time.total_seconds())

    def _archive_old_dates(self, app_id_state: AppIdState):
        for event_name, event in app_id_state.date_updates.items():
            for p_date, updated_at in event.items():
                if self._is_date_archived(app_id_state, p_date):
                    continue
                last_event_date = datetime.combine(p_date, time.max)
                fresh = updated_at - last_event_date < self._fresh_limit
                if not fresh:
                    for source in self._definition.date_required_sources:
                        yield UpdateRequest(source, None, app_id_state.app_id, p_date,
                                            UpdateRequest.ARCHIVE)
                    self._mark_date_archived(app_id_state, event_name, p_date)

    def _update_date(self, event_name: str, app_id_state: AppIdState, p_date: date,
                     started_at: datetime) \
            -> Generator[UpdateRequest, None, None]:
        sources = self._definition.date_required_sources
        if app_id_state.date_updates.get(event_name):
            updated_at = app_id_state.date_updates.get(event_name).get(p_date)
        else:
            updated_at = None
        last_event_date = datetime.combine(p_date, time.max)
        if updated_at:
            updated = started_at - updated_at < self._update_interval
            if updated:
                return
        last_event_delta = (updated_at or started_at) - last_event_date
        for source in sources:
            yield UpdateRequest(source, event_name, app_id_state.app_id, p_date,
                                UpdateRequest.LOAD_ONE_DATE)
        self._mark_date_updated(app_id_state, event_name, p_date)
        
        fresh = last_event_delta < self._fresh_limit
        if not fresh:
            for source in sources:
                yield UpdateRequest(source, None, app_id_state.app_id, p_date,
                                    UpdateRequest.ARCHIVE)
            self._mark_date_archived(app_id_state, event_name, p_date)

    def _update_date_ignored_fields(self, app_id: str):
        for source in self._definition.date_ignored_sources:
            yield UpdateRequest(source, None, app_id, None,
                                UpdateRequest.LOAD_DATE_IGNORED)

    def update_requests(self) \
            -> Generator[UpdateRequest, None, None]:
        self._load_state()
        self._wait_if_needed()
        started_at = datetime.now()
        for app_id in self._app_ids:
            app_id_state = self._get_or_create_app_id_state(app_id)
            date_to = started_at.date()
            date_from = date_to - self._update_limit

            updates = self._archive_old_dates(app_id_state)
            for update_request in updates:
                yield update_request

            for event_name in self._event_names:
                logger.debug('Logging event: {}'.format(event_name))
                for pd_date in pd.date_range(date_from, date_to):
                    p_date = pd_date.to_pydatetime().date()  # type: date
                    updates = self._update_date(event_name, app_id_state, p_date, started_at)
                    for update_request in updates:
                        yield update_request

            updates = self._update_date_ignored_fields(app_id_state.app_id)
            for update_request in updates:
                yield update_request
        self._finish_updates()
