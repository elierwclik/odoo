# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import res_company # has to be before hr_holidays to create needed columns on res.company
from . import account_analytic
from . import hr_leave
from . import project_task
from . import res_config_settings
from . import resource_calendar_leaves
from . import hr_employee
