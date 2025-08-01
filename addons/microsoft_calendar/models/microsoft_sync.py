# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from contextlib import contextmanager
from functools import wraps
import pytz
from dateutil.parser import parse
from datetime import timedelta

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.modules.registry import Registry
from odoo.sql_db import BaseCursor

from odoo.addons.microsoft_calendar.utils.microsoft_event import MicrosoftEvent
from odoo.addons.microsoft_calendar.utils.microsoft_calendar import MicrosoftCalendarService
from odoo.addons.microsoft_account.models.microsoft_service import TIMEOUT

_logger = logging.getLogger(__name__)

MAX_RECURRENT_EVENT = 720

# API requests are sent to Microsoft Calendar after the current transaction ends.
# This ensures changes are sent to Microsoft only if they really happened in the Odoo database.
# It is particularly important for event creation , otherwise the event might be created
# twice in Microsoft if the first creation crashed in Odoo.
def after_commit(func):
    @wraps(func)
    def wrapped(self, *args, **kwargs):
        assert isinstance(self.env.cr, BaseCursor)
        dbname = self.env.cr.dbname
        context = self.env.context
        uid = self.env.uid

        if self.env.context.get('no_calendar_sync'):
            return

        @self.env.cr.postcommit.add
        def called_after():
            db_registry = Registry(dbname)
            with db_registry.cursor() as cr:
                env = api.Environment(cr, uid, context)
                try:
                    func(self.with_env(env), *args, **kwargs)
                except Exception as e:
                    _logger.warning("Could not sync record now: %s" % self)
                    _logger.exception(e)

    return wrapped

@contextmanager
def microsoft_calendar_token(user):
    yield user._get_microsoft_calendar_token()


class MicrosoftCalendarSync(models.AbstractModel):
    _name = 'microsoft.calendar.sync'
    _description = "Synchronize a record with Microsoft Calendar"

    microsoft_id = fields.Char('Organizer event Id', copy=False, index=True)
    ms_universal_event_id = fields.Char('Universal event Id', copy=False, index=True)

    # This field helps to know when a microsoft event need to be resynced
    need_sync_m = fields.Boolean(default=True, copy=False)
    active = fields.Boolean(default=True)

    def write(self, vals):
        fields_to_sync = [x for x in vals if x in self._get_microsoft_synced_fields()]
        if fields_to_sync and 'need_sync_m' not in vals and self.env.user._get_microsoft_sync_status() == "sync_active":
            vals['need_sync_m'] = True

        result = super().write(vals)

        if self.env.user._get_microsoft_sync_status() != "sync_paused":
            for record in self:
                if record.need_sync_m and record.microsoft_id:
                    if not vals.get('active', True):
                        # We need to delete the event. Cancel is not sufficient. Errors may occur.
                        record._microsoft_delete(record._get_organizer(), record.microsoft_id, timeout=3)
                    elif fields_to_sync:
                        values = record._microsoft_values(fields_to_sync)
                        if not values:
                            continue
                        record._microsoft_patch(record._get_organizer(), record.microsoft_id, values, timeout=3)

        return result

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.user.microsoft_synchronization_stopped:
            for vals in vals_list:
                vals.update({'need_sync_m': False})
        records = super().create(vals_list)

        if self.env.user._get_microsoft_sync_status() != "sync_paused":
            for record in records:
                if record.need_sync_m and record.active:
                    record._microsoft_insert(record._microsoft_values(self._get_microsoft_synced_fields()), timeout=3)
        return records

    @api.model
    def _get_microsoft_service(self):
        return MicrosoftCalendarService(self.env['microsoft.service'])

    def _get_synced_events(self):
        """
        Get events already synced with Microsoft Outlook.
        """
        return self.filtered(lambda e: e.ms_universal_event_id)

    def unlink(self):
        synced = self._get_synced_events()
        if self.env.user._get_microsoft_sync_status() != "sync_paused":
            for ev in synced:
                ev._microsoft_delete(ev._get_organizer(), ev.microsoft_id)
        return super().unlink()

    def _write_from_microsoft(self, microsoft_event, vals):
        self.with_context(dont_notify=True).write(vals)

    @api.model
    def _create_from_microsoft(self, microsoft_event, vals_list):
        return self.with_context(dont_notify=True).create(vals_list)

    def _sync_odoo2microsoft(self):
        if not self:
            return
        if self._active_name:
            records_to_sync = self.filtered(self._active_name)
        else:
            records_to_sync = self
        cancelled_records = self - records_to_sync

        records_to_sync._ensure_attendees_have_email()
        updated_records = records_to_sync._get_synced_events()
        new_records = records_to_sync - updated_records

        for record in cancelled_records._get_synced_events():
            record._microsoft_delete(record._get_organizer(), record.microsoft_id)
        for record in new_records:
            values = record._microsoft_values(self._get_microsoft_synced_fields())
            sender_user = record._get_event_user_m()
            if record._is_microsoft_insertion_blocked(sender_user):
                continue
            if isinstance(values, dict):
                record._microsoft_insert(values)
            else:
                for value in values:
                    record._microsoft_insert(value)
        for record in updated_records.filtered('need_sync_m'):
            values = record._microsoft_values(self._get_microsoft_synced_fields())
            if not values:
                continue
            record._microsoft_patch(record._get_organizer(), record.microsoft_id, values)

    def _cancel_microsoft(self):
        self.microsoft_id = False
        self.ms_universal_event_id = False
        self.unlink()

    def _sync_recurrence_microsoft2odoo(self, microsoft_events, new_events=None):
        recurrent_masters = new_events.filter(lambda e: e.is_recurrence()) if new_events else []
        recurrents = new_events.filter(lambda e: e.is_recurrent_not_master()) if new_events else []
        default_values = {'need_sync_m': False}

        new_recurrence = self.env['calendar.recurrence']
        updated_events = self.env['calendar.event']

        # --- create new recurrences and associated events ---
        for recurrent_master in recurrent_masters:
            new_calendar_recurrence = dict(
                self.env['calendar.recurrence']._microsoft_to_odoo_values(recurrent_master, default_values, with_ids=True),
                need_sync_m=False
            )
            to_create = recurrents.filter(
                lambda e: e.seriesMasterId == new_calendar_recurrence['microsoft_id']
            )
            recurrents -= to_create
            base_values = dict(
                self.env['calendar.event']._microsoft_to_odoo_values(recurrent_master, default_values, with_ids=True),
                need_sync_m=False
            )
            to_create_values = []
            if new_calendar_recurrence.get('end_type', False) in ['count', 'forever']:
                to_create = list(to_create)[:MAX_RECURRENT_EVENT]
            for recurrent_event in to_create:
                if recurrent_event.type == 'occurrence':
                    value = self.env['calendar.event']._microsoft_to_odoo_recurrence_values(recurrent_event, base_values)
                else:
                    value = self.env['calendar.event']._microsoft_to_odoo_values(recurrent_event, default_values)

                to_create_values += [dict(value, need_sync_m=False)]

            new_calendar_recurrence['calendar_event_ids'] = [(0, 0, to_create_value) for to_create_value in to_create_values]
            new_recurrence_odoo = self.env['calendar.recurrence'].with_context(dont_notify=True).create(new_calendar_recurrence)
            new_recurrence_odoo.base_event_id = new_recurrence_odoo.calendar_event_ids[0] if new_recurrence_odoo.calendar_event_ids else False
            new_recurrence |= new_recurrence_odoo

        # --- update events in existing recurrences ---
        # Important note:
        # To map existing recurrences with events to update, we must use the universal id
        # (also known as ICalUId in the Microsoft API), as 'seriesMasterId' attribute of events
        # is specific to the Microsoft user calendar.
        ms_recurrence_ids = list({x.seriesMasterId for x in recurrents})
        ms_recurrence_uids = {r.id: r.iCalUId for r in microsoft_events if r.id in ms_recurrence_ids}
        recurrences = self.env['calendar.recurrence'].search([('ms_universal_event_id', 'in', microsoft_events.uids)])
        for recurrent_master_id in ms_recurrence_ids:
            recurrence_id = recurrences.filtered(
                lambda ev: ev.ms_universal_event_id == ms_recurrence_uids[recurrent_master_id]
            )
            to_update = recurrents.filter(lambda e: e.seriesMasterId == recurrent_master_id)
            for recurrent_event in to_update:
                if recurrent_event.type == 'occurrence':
                    value = self.env['calendar.event']._microsoft_to_odoo_recurrence_values(
                        recurrent_event, {'need_sync_m': False}
                    )
                else:
                    value = self.env['calendar.event']._microsoft_to_odoo_values(recurrent_event, default_values)
                existing_event = recurrence_id.calendar_event_ids.filtered(
                    lambda e: e._is_matching_timeslot(value['start'], value['stop'], recurrent_event.isAllDay)
                )
                if not existing_event:
                    continue
                value.pop('start')
                value.pop('stop')
                existing_event._write_from_microsoft(recurrent_event, value)
                updated_events |= existing_event
            new_recurrence |= recurrence_id
        return new_recurrence, updated_events

    def _update_microsoft_recurrence(self, recurrence, events):
        """
        Update Odoo events from Outlook recurrence and events.
        """
        # get the list of events to update ...
        events_to_update = events.filter(lambda e: e.seriesMasterId == self.microsoft_id)
        if self.end_type in ['count', 'forever']:
            events_to_update = list(events_to_update)[:MAX_RECURRENT_EVENT]

        # ... and update them
        rec_values = {}
        update_events = self.env['calendar.event']
        for e in events_to_update:
            if e.type == "exception":
                event_values = self.env['calendar.event']._microsoft_to_odoo_values(e)
            elif e.type == "occurrence":
                event_values = self.env['calendar.event']._microsoft_to_odoo_recurrence_values(e)
            else:
                event_values = None

            if event_values:
                # keep event values to update the recurrence later
                if any(f for f in ('start', 'stop') if f in event_values):
                    rec_values[(self.id, event_values.get('start'), event_values.get('stop'))] = dict(
                        event_values, need_sync_m=False
                    )

                odoo_event = self.env['calendar.event'].browse(e.odoo_id(self.env)).exists().with_context(
                    no_mail_to_attendees=True, mail_create_nolog=True
                )
                odoo_event.with_context(dont_notify=True).write(dict(event_values, need_sync_m=False))
                update_events |= odoo_event

        # update the recurrence
        detached_events = self.with_context(dont_notify=True)._apply_recurrence(rec_values)
        detached_events._cancel_microsoft()

        return update_events

    @api.model
    def _sync_microsoft2odoo(self, microsoft_events: MicrosoftEvent):
        """
        Synchronize Microsoft recurrences in Odoo.
        Creates new recurrences, updates existing ones.
        :return: synchronized odoo
        """
        existing = microsoft_events.match_with_odoo_events(self.env)
        cancelled = microsoft_events.cancelled()
        new = microsoft_events - existing - cancelled
        new_recurrence = new.filter(lambda e: e.is_recurrent())

        # create new events and reccurrences
        odoo_values = [
            dict(self._microsoft_to_odoo_values(e, with_ids=True), need_sync_m=False)
            for e in (new - new_recurrence)
        ]
        synced_events = self.with_context(dont_notify=True)._create_from_microsoft(new, odoo_values)
        synced_recurrences, updated_events = self._sync_recurrence_microsoft2odoo(existing, new_recurrence)
        synced_events |= updated_events

        # remove cancelled events and recurrences
        cancelled_recurrences = self.env['calendar.recurrence'].search([
            '|',
            ('ms_universal_event_id', 'in', cancelled.uids),
            ('microsoft_id', 'in', cancelled.ids),
        ])
        cancelled_events = self.browse([
            e.odoo_id(self.env)
            for e in cancelled
            if e.id not in [r.microsoft_id for r in cancelled_recurrences]
        ])
        cancelled_recurrences._cancel_microsoft()
        cancelled_events = cancelled_events.exists()
        cancelled_events._cancel_microsoft()

        synced_recurrences |= cancelled_recurrences
        synced_events |= cancelled_events | cancelled_recurrences.calendar_event_ids

        # Get sync lower bound days range for checking if old events must be updated in Odoo.
        ICP = self.env['ir.config_parameter'].sudo()
        lower_bound_day_range = ICP.get_param('microsoft_calendar.sync.lower_bound_range')

        # update other events
        for mevent in (existing - cancelled).filter(lambda e: e.lastModifiedDateTime):
            # Last updated wins.
            # This could be dangerous if microsoft server time and odoo server time are different
            if mevent.is_recurrence():
                odoo_event = self.env['calendar.recurrence'].browse(mevent.odoo_id(self.env)).exists()
            else:
                odoo_event = self.browse(mevent.odoo_id(self.env)).exists()

            if odoo_event:
                odoo_event_updated_time = pytz.utc.localize(odoo_event.write_date)
                ms_event_updated_time = parse(mevent.lastModifiedDateTime)

                # If the update comes from an old event/recurrence, check if time diff between updates is reasonable.
                old_event_update_condition = True
                if lower_bound_day_range:
                    update_time_diff = ms_event_updated_time - odoo_event_updated_time
                    old_event_update_condition = odoo_event._check_old_event_update_required(int(lower_bound_day_range), update_time_diff)

                if ms_event_updated_time >= odoo_event_updated_time and old_event_update_condition:
                    vals = dict(odoo_event._microsoft_to_odoo_values(mevent), need_sync_m=False)
                    odoo_event.with_context(dont_notify=True)._write_from_microsoft(mevent, vals)

                    if odoo_event._name == 'calendar.recurrence':
                        update_events = odoo_event._update_microsoft_recurrence(mevent, microsoft_events)
                        synced_recurrences |= odoo_event
                        synced_events |= update_events
                    else:
                        synced_events |= odoo_event

        return synced_events, synced_recurrences

    def _check_old_event_update_required(self, lower_bound_day_range, update_time_diff):
        """
        Checks if an old event in Odoo should be updated locally. This verification is necessary because
        sometimes events in Odoo have the same state in Microsoft and even so they trigger updates locally
        due to a second or less of update time difference, thus spamming unwanted emails on Microsoft side.
        """
        # Event can be updated locally if its stop date is bigger than lower bound and the update time difference is reasonable (1 hour).
        # For recurrences, if any of the occurrences surpass the lower bound range, we update the recurrence.
        lower_bound = fields.Datetime.subtract(fields.Datetime.now(), days=lower_bound_day_range)
        stop_date_condition = True
        if self._name == 'calendar.event':
            stop_date_condition = self.stop >= lower_bound
        elif self._name == 'calendar.recurrence':
            stop_date_condition = any(event.stop >= lower_bound for event in self.calendar_event_ids)
        return stop_date_condition or update_time_diff >= timedelta(hours=1)

    @after_commit
    def _microsoft_delete(self, user_id, event_id, timeout=TIMEOUT):
        """
        Once the event has been really removed from the Odoo database, remove it from the Outlook calendar.

        Note that all self attributes to use in this method must be provided as method parameters because
        'self' won't exist when this method will be really called due to @after_commit decorator.
        """
        microsoft_service = self._get_microsoft_service()
        sender_user = self._get_event_user_m(user_id).sudo()
        with microsoft_calendar_token(sender_user) as token:
            if token and not sender_user.microsoft_synchronization_stopped:
                microsoft_service.delete(event_id, token=token, timeout=timeout)

    @after_commit
    def _microsoft_patch(self, user_id, event_id, values, timeout=TIMEOUT):
        """
        Once the event has been really modified in the Odoo database, modify it in the Outlook calendar.

        Note that all self attributes to use in this method must be provided as method parameters because
        'self' may have been modified between the call of '_microsoft_patch' and its execution,
        due to @after_commit decorator.
        """
        microsoft_service = self._get_microsoft_service()
        sender_user = self._get_event_user_m(user_id)
        with microsoft_calendar_token(sender_user.sudo()) as token:
            if token:
                self._ensure_attendees_have_email()
                res = microsoft_service.patch(event_id, values, token=token, timeout=timeout)
                self.with_context(dont_notify=True).write({
                    'need_sync_m': not res,
                })

    @after_commit
    def _microsoft_insert(self, values, timeout=TIMEOUT):
        """
        Once the event has been really added in the Odoo database, add it in the Outlook calendar.

        Note that all self attributes to use in this method must be provided as method parameters because
        'self' may have been modified between the call of '_microsoft_insert' and its execution,
        due to @after_commit decorator.
        """
        if not values:
            return
        microsoft_service = self._get_microsoft_service()
        sender_user = self._get_event_user_m()
        with microsoft_calendar_token(sender_user.sudo()) as token:
            if token:
                self._ensure_attendees_have_email()
                event_id, uid = microsoft_service.insert(values, token=token, timeout=timeout)
                self.with_context(dont_notify=True).write({
                    'microsoft_id': event_id,
                    'ms_universal_event_id': uid,
                    'need_sync_m': False,
                })

    def _microsoft_attendee_answer(self, answer, params, timeout=TIMEOUT):
        if not answer:
            return
        microsoft_service = self._get_microsoft_service()
        with microsoft_calendar_token(self.env.user.sudo()) as token:
            if token:
                self._ensure_attendees_have_email()
                # Fetch the event's id (ms_organizer_event_id) using its iCalUId (ms_universal_event_id) since the
                # former differs for each attendee. This info is required for sending the event answer and Odoo currently
                # saves the event's id of the last user who synced the event (who might be or not the current user).
                status, event = microsoft_service._get_single_event(self.ms_universal_event_id, token=token)
                if status and event and event.get('value') and len(event.get('value')) == 1:
                    # Send the attendee answer with its own ms_organizer_event_id.
                    res = microsoft_service.answer(
                        event.get('value')[0].get('id'),
                        answer, params, token=token, timeout=timeout
                    )
                    self.need_sync_m = not res

    def _get_microsoft_records_to_sync(self, full_sync=False):
        """
        Return records that should be synced from Odoo to Microsoft
        :param full_sync: If True, all events attended by the user are returned
        :return: events
        """
        domain = self.with_context(full_sync_m=full_sync)._get_microsoft_sync_domain()
        return self.with_context(active_test=False).search(domain)

    @api.model
    def _microsoft_to_odoo_values(
        self, microsoft_event: MicrosoftEvent, default_reminders=(), default_values=None, with_ids=False
    ):
        """
        Implements this method to return a dict of Odoo values corresponding
        to the Microsoft event given as parameter
        :return: dict of Odoo formatted values
        """
        raise NotImplementedError()

    def _microsoft_values(self, fields_to_sync, initial_values=()):
        """
        Implements this method to return a dict with values formatted
        according to the Microsoft Calendar API
        :return: dict of Microsoft formatted values
        """
        raise NotImplementedError()

    def _ensure_attendees_have_email(self):
        raise NotImplementedError()

    def _get_microsoft_sync_domain(self):
        """
        Return a domain used to search records to synchronize.
        e.g. return a domain to synchronize records owned by the current user.
        """
        raise NotImplementedError()

    def _get_microsoft_synced_fields(self):
        """
        Return a set of field names. Changing one of these fields
        marks the record to be re-synchronized.
        """
        raise NotImplementedError()

    @api.model
    def _restart_microsoft_sync(self):
        """ Turns on the microsoft synchronization for all the events of
        a given user.
        """
        raise NotImplementedError()

    def _extend_microsoft_domain(self, domain: Domain):
        """ Extends the sync domain based on the full_sync_m context parameter.
        In case of full sync it shouldn't include already synced events.
        """
        if self.env.context.get('full_sync_m', True):
            domain &= Domain('ms_universal_event_id', '=', False)
        else:
            is_active_clause = Domain(self._active_name, '=', True) if self._active_name else Domain.TRUE
            domain &= (Domain('ms_universal_event_id', '=', False) & is_active_clause) | Domain('need_sync_m', '=', True)
        # Sync only events created/updated after last sync date (with 5 min of time acceptance).
        if self.env.user.microsoft_last_sync_date:
            time_offset = timedelta(minutes=5)
            domain &= Domain('write_date', '>=', self.env.user.microsoft_last_sync_date - time_offset)
        return domain

    def _get_event_user_m(self, user_id=None):
        """ Return the correct user to send the request to Microsoft.
        It's possible that a user creates an event and sets another user as the organizer. Using self.env.user will
        cause some issues, and it might not be possible to use this user for sending the request, so this method gets
        the appropriate user accordingly.
        """
        raise NotImplementedError()

    def _need_video_call(self):
        """
        Implement this method to return True if the event needs a video call
        :return: bool
        """
        self.ensure_one()
        return True

    def _is_microsoft_insertion_blocked(self, sender_user):
        """
        Returns True if the record insertion to Microsoft should be blocked.
        This is a necessary step for ensuring data match between Odoo and Microsoft,
        as it prevents attendees to synchronize new records on behalf of the owners,
        otherwise the event ownership would be lost in Outlook and it would block the
        future record synchronization for the original owner.
        """
        raise NotImplementedError()
