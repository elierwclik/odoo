# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from freezegun import freeze_time

from odoo import tests
from odoo.tests import Form, new_test_user, TransactionCase
from odoo.exceptions import ValidationError


@tests.tagged('access_rights', 'post_install', '-at_install')
class TestHrLeaveMandatoryDays(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.default_calendar = cls.env['resource.calendar'].create({
            'name': 'moon calendar',
        })

        cls.company = cls.env['res.company'].create({
            'name': 'super company',
            'resource_calendar_id': cls.default_calendar.id,
        })

        cls.employee_user = new_test_user(cls.env, login='user', groups='base.group_user', company_ids=[(6, 0, cls.company.ids)], company_id=cls.company.id)
        cls.manager_user = new_test_user(cls.env, login='manager', groups='base.group_user,hr_holidays.group_hr_holidays_manager', company_ids=[(6, 0, cls.company.ids)], company_id=cls.company.id)

        cls.employee_emp = cls.env['hr.employee'].create({
            'name': 'Toto Employee',
            'company_id': cls.company.id,
            'user_id': cls.employee_user.id,
            'resource_calendar_id': cls.default_calendar.id,
        })
        cls.manager_emp = cls.env['hr.employee'].create({
            'name': 'Toto Mananger',
            'company_id': cls.company.id,
            'user_id': cls.manager_user.id,
        })

        cls.leave_type = cls.env['hr.leave.type'].create({
            'name': 'Unlimited',
            'leave_validation_type': 'hr',
            'requires_allocation': False,
            'company_id': cls.company.id,
        })

        cls.mandatory_day = cls.env['hr.leave.mandatory.day'].create({
            'name': 'Super Event',
            'company_id': cls.company.id,
            'start_date': datetime(2021, 11, 2),
            'end_date': datetime(2021, 11, 2),
            'color': 1,
            'resource_calendar_id': cls.default_calendar.id,
        })
        cls.mandatory_week = cls.env['hr.leave.mandatory.day'].create({
            'name': 'Super Event End Of Week',
            'company_id': cls.company.id,
            'start_date': datetime(2021, 11, 8),
            'end_date': datetime(2021, 11, 12),
            'color': 2,
            'resource_calendar_id': cls.default_calendar.id,
        })

    @freeze_time('2021-10-15')
    def test_request_mandatory_days(self):
        # An employee can request time off outside mandatory days
        self.env['hr.leave'].with_user(self.employee_user.id).create({
            'name': 'coucou',
            'holiday_status_id': self.leave_type.id,
            'employee_id': self.employee_emp.id,
            'request_date_from': datetime(2021, 11, 3),
            'request_date_to': datetime(2021, 11, 3),
        })

        # Taking a time off during a Mandatory Day is not allowed for a simple employee...
        with self.assertRaises(ValidationError):
            self.env['hr.leave'].with_user(self.employee_user.id).create({
                'name': 'coucou',
                'holiday_status_id': self.leave_type.id,
                'employee_id': self.employee_emp.id,
                'request_date_from': datetime(2021, 11, 3),
                'request_date_to': datetime(2021, 11, 17),
            })

        with self.assertRaises(ValidationError):
            self.env['hr.leave'].with_user(self.employee_user.id).create({
                'name': 'coucou',
                'holiday_status_id': self.leave_type.id,
                'employee_id': self.employee_emp.id,
                'request_date_from': datetime(2021, 11, 9),
                'request_date_to': datetime(2021, 11, 9),
            })

        # ... but is allowed for a Time Off Officer
        self.env['hr.leave'].with_user(self.manager_user.id).create({
            'name': 'coucou',
            'holiday_status_id': self.leave_type.id,
            'employee_id': self.employee_emp.id,
            'request_date_from': datetime(2021, 11, 2),
            'request_date_to': datetime(2021, 11, 2),
        })

    @freeze_time('2021-10-15')
    def test_get_mandatory_days(self):
        mandatory_days = self.employee_emp.get_mandatory_days('2021-11-01', '2021-11-30')

        # Mandatory Days spanning multiple days should be split in single days
        expected_data = {'2021-11-02': 1, '2021-11-08': 2, '2021-11-09': 2, '2021-11-10': 2, '2021-11-11': 2, '2021-11-12': 2}

        self.assertEqual(len(mandatory_days), len(expected_data))
        for day, color in expected_data.items():
            self.assertTrue(day in mandatory_days)
            self.assertEqual(color, mandatory_days[day])

        with Form(self.env['hr.leave'].with_user(self.employee_user.id).with_context(default_employee_id=self.employee_emp.id)) as leave_form:
            leave_form.holiday_status_id = self.leave_type
            leave_form.request_date_from = datetime(2021, 11, 1)
            leave_form.request_date_to = datetime(2021, 11, 1)

            leave_form.save()  # need to be saved to have access to record
            self.assertFalse(leave_form.record.has_mandatory_day)

            leave_form.request_date_to = datetime(2021, 11, 5)

            leave_form.save()  # need to be saved to have access to record
            self.assertTrue(leave_form.record.has_mandatory_day)

    @freeze_time('2021-10-15')
    def test_department_mandatory_days(self):
        production_department = self.env['hr.department'].create({
            'name': 'Production Department',
            'company_id': self.company.id,
        })
        post_production_department = self.env['hr.department'].create({
            'name': 'Post-Production Department',
            'company_id': self.company.id,
            'parent_id': production_department.id,
        })
        deployment_department = self.env['hr.department'].create({
            'name': 'Deployment Department',
            'company_id': self.company.id,
            'parent_id': production_department.id,
        })

        self.employee_emp.write({
            'department_id': post_production_department.id
        })

        # Create one mandatory day for each department
        self.env['hr.leave.mandatory.day'].create({
            'name': 'Last Rush Before Launch (production)',
            'company_id': self.company.id,
            'start_date': datetime(2021, 11, 3),
            'end_date': datetime(2021, 11, 3),
            'color': 1,
            'resource_calendar_id': self.default_calendar.id,
            'department_ids': [production_department.id],
        })
        self.env['hr.leave.mandatory.day'].create({
            'name': 'Last Rush Before Launch (post-production)',
            'company_id': self.company.id,
            'start_date': datetime(2021, 11, 4),
            'end_date': datetime(2021, 11, 4),
            'color': 1,
            'resource_calendar_id': self.default_calendar.id,
            'department_ids': [post_production_department.id],
        })
        self.env['hr.leave.mandatory.day'].create({
            'name': 'Last Rush Before Launch (deployment)',
            'company_id': self.company.id,
            'start_date': datetime(2021, 11, 5),
            'end_date': datetime(2021, 11, 5),
            'color': 1,
            'resource_calendar_id': self.default_calendar.id,
            'department_ids': [deployment_department.id],
        })

        # The employee should only be able to create a time off on mandatory days
        # that do not include his department
        with self.assertRaises(ValidationError):
            self.env['hr.leave'].with_user(self.employee_user.id).create({
                'name': 'have been given the black spot',
                'holiday_status_id': self.leave_type.id,
                'employee_id': self.employee_emp.id,
                'request_date_from': datetime(2021, 11, 3),
                'request_date_to': datetime(2021, 11, 3),
            })
        with self.assertRaises(ValidationError):
            self.env['hr.leave'].with_user(self.employee_user.id).create({
                'name': 'have been given the black spot',
                'holiday_status_id': self.leave_type.id,
                'employee_id': self.employee_emp.id,
                'request_date_from': datetime(2021, 11, 4),
                'request_date_to': datetime(2021, 11, 4),
            })
        self.env['hr.leave'].with_user(self.employee_user.id).create({
            'name': 'have been given the black spot',
            'holiday_status_id': self.leave_type.id,
            'employee_id': self.employee_emp.id,
            'request_date_from': datetime(2021, 11, 5),
            'request_date_to': datetime(2021, 11, 5),
        })

    @freeze_time('2021-10-15')
    def test_job_position_mandatory_days(self):
        """
            Test mandatory leave restrictions based on job positions and departments.

            This test ensures that employees cannot request time off on mandatory leave days
            that are assigned to their specific job position or department. The logic includes:

            - Creating a production department and job positions.
            - Assigning an employee to a department and job position.
            - Defining mandatory leave days for specific jobs and departments.
            - Validating that the employee cannot take leave on restricted days.
            - Allowing leave requests on days without conflicts.

            Expected behavior:
            - Raises a ValidationError if the employee's department or job position is linked to a mandatory leave day.
            - Allows leave requests on days that do not conflict with their assigned job or department.
        """
        production_department = self.env['hr.department'].create({
            'name': 'Production Department',
            'company_id': self.company.id,
        })

        # Create job positions
        production_manager, post_production_manager = self.env['hr.job'].create([{
            'name': 'Production Manager',
            'company_id': self.company.id,
        },{
            'name': 'Post-Production Manager',
            'company_id': self.company.id,
        }])

        self.employee_emp.write({
            'department_id': production_department.id,
            'job_id': production_manager.id,
        })

        # Create mandatory leave days for job positions and departments
        self.env['hr.leave.mandatory.day'].create([{
            'name': 'Production Deadline',
            'company_id': self.company.id,
            'start_date': datetime(2021, 11, 3),
            'end_date': datetime(2021, 11, 3),
            'color': 1,
            'resource_calendar_id': self.default_calendar.id,
            'department_ids': [production_department.id],
            'job_ids': [production_manager.id],
        },{
            'name': 'Post-Production Deadline',
            'company_id': self.company.id,
            'start_date': datetime(2021, 11, 4),
            'end_date': datetime(2021, 11, 4),
            'color': 2,
            'resource_calendar_id': self.default_calendar.id,
            'department_ids': [production_department.id],
        }, {
            'name': 'Team General Meeting',
            'company_id': self.company.id,
            'start_date': datetime(2021, 11, 6),
            'end_date': datetime(2021, 11, 6),
            'color': 3,
            'resource_calendar_id': self.default_calendar.id,
            'job_ids': [production_manager.id]
        }, {
            'name': 'Department General Meeting',
            'company_id': self.company.id,
            'start_date': datetime(2021, 11, 5),
            'end_date': datetime(2021, 11, 5),
            'color': 3,
            'resource_calendar_id': self.default_calendar.id,
            'department_ids': [production_department.id],
            'job_ids': [post_production_manager.id]
        }])

        # The employee should only be able to create a time off on mandatory days
        # that do not conflict with their job or department restrictions
        with self.assertRaises(ValidationError):
            self.env['hr.leave'].with_user(self.employee_user.id).create({
                'name': 'Vacation during Production Deadline',
                'holiday_status_id': self.leave_type.id,
                'employee_id': self.employee_emp.id,
                'request_date_from': datetime(2021, 11, 3),
                'request_date_to': datetime(2021, 11, 3),
            })
        with self.assertRaises(ValidationError):
            self.env['hr.leave'].with_user(self.employee_user.id).create({
                'name': 'Vacation during Post-Production Deadline',
                'holiday_status_id': self.leave_type.id,
                'employee_id': self.employee_emp.id,
                'request_date_from': datetime(2021, 11, 4),
                'request_date_to': datetime(2021, 11, 4),
            })
        with self.assertRaises(ValidationError):
            self.env['hr.leave'].with_user(self.employee_user.id).create({
                'name': 'Holiday During Team General Meating',
                'holiday_status_id': self.leave_type.id,
                'employee_id': self.employee_emp.id,
                'request_date_from': datetime(2021, 11, 6),
                'request_date_to': datetime(2021, 11, 6),
            })
        self.env['hr.leave'].with_user(self.employee_user.id).create({
            'name': 'Vacation during General Meeting',
            'holiday_status_id': self.leave_type.id,
            'employee_id': self.employee_emp.id,
            'request_date_from': datetime(2021, 11, 5),
            'request_date_to': datetime(2021, 11, 5),
        })
