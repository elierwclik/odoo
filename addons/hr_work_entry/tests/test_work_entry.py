# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil.relativedelta import relativedelta
from psycopg2 import IntegrityError
import pytz

from odoo.tests.common import tagged
from odoo.tools import mute_logger
from odoo.addons.hr_work_entry.tests.common import TestWorkEntryBase


@tagged('work_entry')
class TestWorkEntry(TestWorkEntryBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tz = pytz.timezone(cls.richard_emp.tz)
        cls.start = datetime(2015, 11, 1, 1, 0, 0)
        cls.end = datetime(2015, 11, 30, 23, 59, 59)
        cls.resource_calendar_id = cls.env['resource.calendar'].create({'name': 'My Calendar'})
        cls.richard_emp.create_version({
            'date_version': cls.start.date() - relativedelta(days=5),
            'contract_date_start': cls.start.date() - relativedelta(days=5),
            'contract_date_end': cls.end.date() + relativedelta(days=5),
            'name': 'dodo',
            'resource_calendar_id': cls.resource_calendar_id.id,
            'wage': 1000,
            'date_generated_from': cls.end.date() + relativedelta(days=5),
        })

    def test_no_duplicate(self):
        self.richard_emp.generate_work_entries(self.start, self.end)
        pou1 = self.env['hr.work.entry'].search_count([])
        self.richard_emp.generate_work_entries(self.start, self.end)
        pou2 = self.env['hr.work.entry'].search_count([])
        self.assertEqual(pou1, pou2, "Work entries should not be duplicated")

    def test_work_entry(self):
        self.richard_emp.generate_work_entries(self.start, self.end)
        attendance_nb = len(self.resource_calendar_id._attendance_intervals_batch(self.start.replace(tzinfo=pytz.utc), self.end.replace(tzinfo=pytz.utc))[False])
        work_entry_nb = self.env['hr.work.entry'].search_count([
            ('employee_id', '=', self.richard_emp.id),
            ('date_start', '>=', self.start),
            ('date_stop', '<=', self.end)])
        self.assertEqual(attendance_nb, work_entry_nb, "One work_entry should be generated for each calendar attendance")

    def test_approve_multiple_day_work_entry(self):
        start = datetime(2015, 11, 1, 9, 0, 0)
        end = datetime(2015, 11, 3, 18, 0, 0)

        work_entry = self.env['hr.work.entry'].create({
            'name': '1',
            'employee_id': self.richard_emp.id,
            'version_id': self.richard_emp.version_id.id,
            'date_start': start,
            'date_stop': end,
            'work_entry_type_id': self.work_entry_type.id,
        })
        work_entry.action_validate()
        work_entries = self.env['hr.work.entry'].search([('employee_id', '=', self.richard_emp.id)])
        self.assertTrue(all(b.state == 'validated' for b in work_entries), "Work entries should be approved")

    def test_validate_conflict_work_entry(self):
        start = datetime(2015, 11, 1, 9, 0, 0)
        end = datetime(2015, 11, 1, 13, 0, 0)
        work_entry1 = self.env['hr.work.entry'].create({
            'name': '1',
            'employee_id': self.richard_emp.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.work_entry_type_attendance').id,
            'version_id': self.richard_emp.version_id.id,
            'date_start': start,
            'date_stop': end + relativedelta(hours=5),
        })
        self.env['hr.work.entry'].create({
            'name': '2',
            'employee_id': self.richard_emp.id,
            'work_entry_type_id': self.env.ref('hr_work_entry.work_entry_type_attendance').id,
            'version_id': self.richard_emp.version_id.id,
            'date_start': start + relativedelta(hours=3),
            'date_stop': end,
        })
        self.assertFalse(work_entry1.action_validate(), "It should not validate work_entries conflicting with others")
        self.assertEqual(work_entry1.state, 'conflict')
        self.assertNotEqual(work_entry1.state, 'validated')

    def test_validate_undefined_work_entry(self):
        work_entry1 = self.env['hr.work.entry'].create({
            'name': '1',
            'employee_id': self.richard_emp.id,
            'version_id': self.richard_emp.version_id.id,
            'date_start': self.start,
            'date_stop': self.end,
        })
        work_entry1.work_entry_type_id = False
        self.assertFalse(work_entry1.action_validate(), "It should not validate work_entries without a type")
        self.assertEqual(work_entry1.state, 'conflict', "It should change to conflict state")
        work_entry1.work_entry_type_id = self.work_entry_type
        self.assertTrue(work_entry1.action_validate(), "It should validate work_entries")

    def test_outside_calendar(self):
        """ Test leave work entries outside schedule are conflicting """
        # Outside but not a leave
        # work_entry_1 = self.create_work_entry(datetime(2018, 10, 10, 3, 0), datetime(2018, 10, 10, 4, 0))
        # # Outside and a leave
        # work_entry_2 = self.create_work_entry(datetime(2018, 10, 10, 1, 0), datetime(2018, 10, 10, 2, 0), work_entry_type=self.work_entry_type_leave)
        # # Overlapping and a leave
        # work_entry_3 = self.create_work_entry(datetime(2018, 10, 10, 7, 0), datetime(2018, 10, 10, 10, 0), work_entry_type=self.work_entry_type_leave)
        # # Overlapping and not a leave
        # work_entry_4 = self.create_work_entry(datetime(2018, 10, 10, 11, 0), datetime(2018, 10, 10, 13, 0))
        work_entry_1, work_entry_2, work_entry_3, work_entry_4 = self.create_work_entries([
            # Outside but not a leave
            (datetime(2018, 10, 10, 3, 0), datetime(2018, 10, 10, 4, 0)),
            # Outside and a leave
            (datetime(2018, 10, 10, 1, 0), datetime(2018, 10, 10, 2, 0), self.work_entry_type_leave),
            # Overlapping and a leave
            (datetime(2018, 10, 10, 7, 0), datetime(2018, 10, 10, 10, 0), self.work_entry_type_leave),
            # Overlapping and not a leave
            (datetime(2018, 10, 10, 11, 0), datetime(2018, 10, 10, 13, 0)),
        ])
        (work_entry_1 | work_entry_2 | work_entry_3 | work_entry_4)._mark_leaves_outside_schedule()
        self.assertEqual(work_entry_2.state, 'conflict', "It should conflict")
        self.assertNotEqual(work_entry_1.state, 'conflict', "It should not conflict")
        self.assertNotEqual(work_entry_3.state, 'conflict', "It should not conflict")
        self.assertNotEqual(work_entry_4.state, 'conflict', "It should not conflict")

    def test_write_conflict(self):
        """ Test updating work entries dates recomputes conflicts """
        # work_entry_1 = self.create_work_entry(datetime(2018, 10, 10, 9, 0), datetime(2018, 10, 10, 12, 0))
        # work_entry_2 = self.create_work_entry(datetime(2018, 10, 10, 12, 0), datetime(2018, 10, 10, 18, 0))
        work_entry_1, work_entry_2 = self.create_work_entries([
            (datetime(2018, 10, 10, 9, 0), datetime(2018, 10, 10, 12, 0)),
            (datetime(2018, 10, 10, 12, 0), datetime(2018, 10, 10, 18, 0)),
        ])
        self.assertNotEqual(work_entry_1.state, 'conflict', "It should not conflict")
        self.assertNotEqual(work_entry_2.state, 'conflict', "It should not conflict")
        work_entry_1.date_stop = datetime(2018, 10, 10, 14, 0)
        self.assertEqual(work_entry_1.state, 'conflict', "It should conflict")
        self.assertEqual(work_entry_2.state, 'conflict', "It should conflict")

        work_entry_1.date_stop = datetime(2018, 10, 10, 12, 0)  # cancel conflict
        self.assertNotEqual(work_entry_1.state, 'conflict', "It should no longer conflict")
        self.assertNotEqual(work_entry_2.state, 'conflict', "It should no longer conflict")

    def test_write_move(self):
        """ Test completely moving a work entry recomputes conflicts """
        # work_entry_1 = self.create_work_entry(datetime(2018, 10, 10, 9, 0), datetime(2018, 10, 10, 12, 0))
        # work_entry_2 = self.create_work_entry(datetime(2018, 10, 18, 9, 0), datetime(2018, 10, 18, 12, 0))
        # work_entry_3 = self.create_work_entry(datetime(2018, 10, 18, 10, 0), datetime(2018, 10, 18, 12, 0))
        work_entry_1, work_entry_2, work_entry_3 = self.create_work_entries([
            (datetime(2018, 10, 10, 9, 0), datetime(2018, 10, 10, 12, 0)),
            (datetime(2018, 10, 18, 9, 0), datetime(2018, 10, 18, 12, 0)),
            (datetime(2018, 10, 18, 10, 0), datetime(2018, 10, 18, 12, 0)),
        ])
        work_entry_2.write({
            'date_start': datetime(2018, 10, 10, 9, 0),
            'date_stop': datetime(2018, 10, 10, 10, 0),
        })
        self.assertEqual(work_entry_1.state, 'conflict')
        self.assertEqual(work_entry_2.state, 'conflict')
        self.assertNotEqual(work_entry_3.state, 'conflict')

    def test_create_conflict(self):
        """ Test creating a work entry recomputes conflicts """
        work_entry_1 = self.create_work_entry(datetime(2018, 10, 10, 9, 0), datetime(2018, 10, 10, 12, 0))
        self.assertNotEqual(work_entry_1.state, 'conflict', "It should not conflict")
        work_entry_2 = self.create_work_entry(datetime(2018, 10, 10, 10, 0), datetime(2018, 10, 10, 18, 0))
        self.assertEqual(work_entry_1.state, 'conflict', "It should conflict")
        self.assertEqual(work_entry_2.state, 'conflict', "It should conflict")

    def test_unarchive_conflict(self):
        """ Test archive/unarchive a work entry recomputes conflicts """
        # work_entry_1 = self.create_work_entry(datetime(2018, 10, 10, 9, 0), datetime(2018, 10, 10, 12, 0))
        # work_entry_2 = self.create_work_entry(datetime(2018, 10, 10, 10, 0), datetime(2018, 10, 10, 18, 0))
        work_entry_1, work_entry_2 = self.create_work_entries([
            (datetime(2018, 10, 10, 9, 0), datetime(2018, 10, 10, 12, 0)),
            (datetime(2018, 10, 10, 10, 0), datetime(2018, 10, 10, 18, 0)),
        ])
        work_entry_2.active = False
        self.assertNotEqual(work_entry_1.state, 'conflict', "It should not conflict")
        self.assertEqual(work_entry_2.state, 'cancelled', "It should be cancelled")
        work_entry_2.active = True
        self.assertEqual(work_entry_1.state, 'conflict', "It should conflict")
        self.assertEqual(work_entry_2.state, 'conflict', "It should conflict")

    def test_validated_no_conflict(self):
        """ Test validating a work entry removes the conflict """
        work_entry_1 = self.create_work_entry(datetime(2018, 10, 10, 9, 0), datetime(2018, 10, 10, 12, 0))
        work_entry_1.state = 'validated'
        work_entry_2 = self.create_work_entry(datetime(2018, 10, 10, 10, 0), datetime(2018, 10, 10, 18, 0))
        self.assertEqual(work_entry_1.state, 'conflict', "It should not conflict")
        self.assertEqual(work_entry_2.state, 'conflict', "It should conflict")

    def test_no_overlap_sql_constraint(self):
        """ Test _work_entries_no_validated_conflict sql constrains """
        work_entry_1 = self.create_work_entry(datetime(2018, 10, 10, 9, 0), datetime(2018, 10, 10, 12, 0))
        work_entry_1.state = 'validated'
        work_entry_2 = self.create_work_entry(datetime(2018, 10, 10, 8, 0), datetime(2018, 10, 10, 10, 0))
        self.assertEqual(work_entry_1.state, 'conflict')

        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            (work_entry_1 + work_entry_2).write({'state': 'validated'})

    def test_work_entry_timezone(self):
        """ Test work entries with different timezone """
        hk_resource_calendar_id = self.env['resource.calendar'].create({
            'name': 'HK Calendar',
            'tz': 'Asia/Hong_Kong',
            'hours_per_day': 8,
            'attendance_ids': [(5, 0, 0),
                (0, 0, {'name': 'Monday Morning', 'dayofweek': '0', 'hour_from': 7, 'hour_to': 11, 'day_period': 'morning'}),
                (0, 0, {'name': 'Monday Afternoon', 'dayofweek': '0', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Tuesday Morning', 'dayofweek': '1', 'hour_from': 7, 'hour_to': 11, 'day_period': 'morning'}),
                (0, 0, {'name': 'Tuesday Afternoon', 'dayofweek': '1', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Wednesday Morning', 'dayofweek': '2', 'hour_from': 7, 'hour_to': 11, 'day_period': 'morning'}),
                (0, 0, {'name': 'Wednesday Afternoon', 'dayofweek': '2', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Thursday Morning', 'dayofweek': '3', 'hour_from': 7, 'hour_to': 11, 'day_period': 'morning'}),
                (0, 0, {'name': 'Thursday Afternoon', 'dayofweek': '3', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}),
                (0, 0, {'name': 'Friday Morning', 'dayofweek': '4', 'hour_from': 7, 'hour_to': 11, 'day_period': 'morning'}),
                (0, 0, {'name': 'Friday Afternoon', 'dayofweek': '4', 'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'})
            ]
        })
        hk_employee = self.env['hr.employee'].create({
            'name': 'HK Employee',
            'resource_calendar_id': hk_resource_calendar_id.id,
            'date_version': datetime(2023, 8, 1),
            'contract_date_start': datetime(2023, 8, 1),
            'contract_date_end': False,
            'wage': 1000,
        })
        self.env.company.resource_calendar_id = hk_resource_calendar_id
        hk_employee.generate_work_entries(datetime(2023, 8, 1), datetime(2023, 8, 1))
        work_entries = self.env['hr.work.entry'].search([('employee_id', '=', hk_employee.id)])
        self.assertEqual(work_entries[0].date_start, datetime(2023, 7, 31, 23, 0))

    def test_separate_overlapping_work_entries_by_type(self):
        calendar = self.env['resource.calendar'].create({'name': 'Calendar', 'tz': 'Europe/Brussels'})
        employee = self.env['hr.employee'].create({
            'name': 'Test',
            'resource_calendar_id': calendar.id,
            'date_version': datetime(2024, 9, 1),
            'contract_date_start': datetime(2024, 9, 1),
            'contract_date_end': datetime(2024, 9, 30),
            'wage': 5000.0,
        })
        calendar.attendance_ids -= calendar.attendance_ids.filtered(lambda attendance: attendance.dayofweek == '0')

        entry_type_1, entry_type_2 = self.env['hr.work.entry.type'].create([
            {'name': 'Work type 1', 'is_leave': False, 'code': 'ENTRY_TYPE1'},
            {'name': 'Work type 2', 'is_leave': False, 'code': 'ENTRY_TYPE2'},
        ])

        self.env['resource.calendar.attendance'].create([
            {
                'calendar_id': calendar.id,
                'dayofweek': '0',
                'name': 'Same type 1',
                'hour_from': 8,
                'hour_to': 11,
                'day_period': 'morning',
                'work_entry_type_id': entry_type_1.id,
            },
            {
                'calendar_id': calendar.id,
                'dayofweek': '0',
                'name': 'Same type 2',
                'hour_from': 11,
                'hour_to': 12,
                'day_period': 'morning',
                'work_entry_type_id': entry_type_1.id,
            },
            {
                'calendar_id': calendar.id,
                'dayofweek': '0',
                'name': 'Different types 1',
                'hour_from': 13,
                'hour_to': 16,
                'day_period': 'afternoon',
                'work_entry_type_id': entry_type_1.id,
            },
            {
                'calendar_id': calendar.id,
                'dayofweek': '0',
                'name': 'Different types 2',
                'hour_from': 16,
                'hour_to': 17,
                'day_period': 'afternoon',
                'work_entry_type_id': entry_type_2.id,
            },
        ])

        employee.generate_work_entries(datetime(2024, 9, 2), datetime(2024, 9, 2))
        result_entries = self.env['hr.work.entry'].search([('employee_id', '=', employee.id)])
        work_entry_types = [entry.work_entry_type_id for entry in result_entries]
        self.assertEqual(len(result_entries), 4, 'A shift should be created for each attendance')
        self.assertEqual(work_entry_types, [entry_type_1, entry_type_1, entry_type_1, entry_type_2])

    def test_work_entry_duration(self):
        """ Test the duration of a work entry is rounded to the nearest minute and correctly calculated """
        work_entry, one_day_entry, multi_day_entry = self.env['hr.work.entry'].create([
            {
                'name': 'Test Work Entry',
                'employee_id': self.richard_emp.id,
                'version_id': self.richard_emp.version_id.id,
                'date_start': datetime(2023, 10, 1, 9, 0, 0),
                'date_stop': datetime(2023, 10, 1, 9, 59, 59, 999999),
                'work_entry_type_id': self.work_entry_type.id,
            },
            {
                'name': 'Test One Day Entry',
                'employee_id': self.richard_emp.id,
                'version_id': self.richard_emp.version_id.id,
                'date_start': datetime(2023, 10, 1, 9, 0, 0),
                'date_stop': datetime(2023, 10, 2, 9, 30, 0),
                'work_entry_type_id': self.work_entry_type.id,
            },
            {
                'name': 'Multi-Day Entry',
                'employee_id': self.richard_emp.id,
                'version_id': self.richard_emp.version_id.id,
                'date_start': datetime(2023, 10, 1, 0, 0, 0),
                'date_stop': datetime(2023, 10, 8, 1, 0, 0),
                'work_entry_type_id': self.work_entry_type.id,
            }
        ])
        self.assertEqual(work_entry.duration, 1, "The duration should be 1 hour")
        self.assertEqual(one_day_entry.duration, 24.5, "Duration should be 24 hours and half an hour")
        self.assertEqual(multi_day_entry.duration, 169, "Duration should be 169 hours (7 days and one hour)")
