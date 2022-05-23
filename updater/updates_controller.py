#!/usr/bin/env python3
"""
  updates_controller.py

  This file is a part of the AppMetrica.

  Copyright 2017 YANDEX

  You may not use this file except in compliance with the License.
  You may obtain a copy of the License at:
        https://yandex.com/legal/metrica_termsofuse/
"""
import datetime
import logging
import time
from turtle import update
from typing import Optional

from fields import SourcesCollection, ProcessingDefinition, LoadingDefinition
from .scheduler import Scheduler, UpdateRequest
from .db_controller import DbController
from .updater import Updater
from .db_controllers_collection import DbControllersCollection

logger = logging.getLogger(__name__)


class UpdatesController(object):
    def __init__(self, scheduler: Scheduler, updater: Updater,
                 sources_collection: SourcesCollection,
                 db_controllers_collection: DbControllersCollection):
        self._scheduler = scheduler
        self._updater = updater
        self._sources_collection = sources_collection
        self._db_controllers_collection = db_controllers_collection
        
    def _load_into_table_single_date(self, app_id: str, date: Optional[datetime.date], event_name: str,
                                     table_suffix: str,
                                     processing_definition: ProcessingDefinition,
                                     loading_definition: LoadingDefinition,
                                     db_controller: DbController,
                                     parts_count: int):
        logger.info('Loading "{date}" "{event_name}" into "{suffix}" of "{source}" '
                    'for "{app_id}"'.format(
            date=date or 'latest',
            event_name=event_name,
            source=loading_definition.source_name,
            app_id=app_id,
            suffix=table_suffix
        ))
        self._updater.update(app_id, date, event_name, table_suffix, db_controller,
                             processing_definition, loading_definition, parts_count)

    def _load_into_table_date_range(self, app_id: str,
                                    date_since: datetime.date, date_until: Optional[datetime.date],
                                    event_name: str,
                                    table_suffix: str,
                                    processing_definition: ProcessingDefinition,
                                    loading_definition: LoadingDefinition,
                                    db_controller: DbController,
                                    parts_count: int):
        logger.info('Loading from "{date_since}" to {date_until} "{event_name}" into "{suffix}" of "{source}" '
                    'for "{app_id}"'.format(
                        date_since=date_since,
                        date_until=date_until or 'latest',
                        event_name=event_name,
                        source=loading_definition.source_name,
                        app_id=app_id,
                        suffix=table_suffix
                    ))
        self._updater.update_range(app_id, date_since, date_until, event_name, table_suffix, db_controller,
                                   processing_definition, loading_definition, parts_count)

    def _archive(self, source: str, app_id: str, date: datetime.date,
                 table_suffix: str, db_controller: DbController):
        logger.info('Archiving "{date}" of "{source}" for "{app_id}"'.format(
            date=date,
            source=source,
            app_id=app_id
        ))
        db_controller.archive_table(table_suffix)

    def _prepare_temporary_table(self, table_suffix, db_controller):
        db_controller.recreate_table(table_suffix)

    def _update(self, update_request: UpdateRequest):
        source = update_request.source
        app_id = update_request.app_id
        event_name = update_request.event_name
        date_since = update_request.date_since
        date = update_request.date
        update_type = update_request.update_type
        parts_count = update_request.parts_counts
        if date is not None:
            table_suffix = '{}_{}'.format(app_id, date.strftime('%Y%m%d'))
        else:
            table_suffix = '{}_{}'.format(app_id, DbController.LATEST_SUFFIX)

        loading_definition = \
            self._sources_collection.loading_definition(source)
        processing_definition = \
            self._sources_collection.processing_definition(source)
        db_controller = \
            self._db_controllers_collection.db_controller(source)

        if update_type == UpdateRequest.LOAD_ONE_DATE:
            self._load_into_table_single_date(app_id, date, event_name, table_suffix,
                                              processing_definition, loading_definition,
                                              db_controller, parts_count)
        elif update_type == UpdateRequest.LOAD_RANGE_DATES:
            self._load_into_table_date_range(app_id, date_since, date, event_name, table_suffix,
                                            processing_definition, loading_definition,
                                            db_controller, parts_count)
        elif update_type == UpdateRequest.ARCHIVE:
            self._archive(source, app_id, date, table_suffix, db_controller)
        elif update_type == UpdateRequest.LOAD_DATE_IGNORED:
            self._load_into_table_single_date(app_id, None, None, table_suffix,
                                              processing_definition, loading_definition,
                                              db_controller)
        elif update_type == UpdateRequest.PREPARE_DAILY_TABLE:
            self._prepare_temporary_table(table_suffix, db_controller)

    def _step(self):
        update_requests = self._scheduler.update_requests()
        for update_request in update_requests:
            self._update(update_request)

    def run(self):
        logger.info("Starting updating loop")
        # Just one step for range of dates loading
        try:
            self._step()
        except Exception as e:
            logger.warning(e)
