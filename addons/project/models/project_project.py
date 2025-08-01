# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import json

from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models
from odoo.addons.mail.tools.discuss import Store
from odoo.addons.rating.models import rating_data
from odoo.exceptions import UserError
from odoo.fields import Command, Domain
from odoo.tools import get_lang, float_utils, formatLang, SQL, LazyTranslate
from odoo.tools.misc import unquote
from odoo.tools.translate import _
from .project_update import STATUS_COLOR
from .project_task import CLOSED_STATES

_lt = LazyTranslate(__name__)


class ProjectProject(models.Model):
    _name = 'project.project'
    _description = "Project"
    _inherit = [
        'portal.mixin',
        'mail.alias.mixin',
        'rating.parent.mixin',
        'mail.thread',
        'mail.activity.mixin',
        'mail.tracking.duration.mixin',
        'analytic.plan.fields.mixin',
    ]
    _order = "sequence, name, id"
    _rating_satisfaction_days = 30  # takes 30 days by default
    _track_duration_field = 'stage_id'

    def __compute_task_count(self, count_field='task_count', additional_domain=None):
        count_fields = {fname for fname in self._fields if 'count' in fname}
        if count_field not in count_fields:
            raise ValueError(f"Parameter 'count_field' can only be one of {count_fields}, got {count_field} instead.")
        domain = Domain('project_id', 'in', self.ids)
        if additional_domain:
            domain &= Domain(additional_domain)
        ProjectTask = self.env['project.task'].with_context(active_test=any(project.active for project in self))
        tasks_count_by_project = dict(ProjectTask._read_group(domain, ['project_id'], ['__count']))
        templates_count_by_project = dict(ProjectTask._read_group(domain & Domain('is_template', '=', True), ['project_id'], ['__count']))
        for project in self:
            if project.is_template:
                count = templates_count_by_project.get(project, 0)
            else:
                count = tasks_count_by_project.get(project, 0) - templates_count_by_project.get(project, 0)
            project.update({count_field: count})

    def _compute_task_count(self):
        self.__compute_task_count()

    def _compute_open_task_count(self):
        self.__compute_task_count(
            count_field='open_task_count',
            additional_domain=[('state', 'in', self.env['project.task'].OPEN_STATES)],
        )

    def _compute_closed_task_count(self):
        self.__compute_task_count(
            count_field='closed_task_count',
            additional_domain=[('state', 'in', [*CLOSED_STATES])],
        )

    def _default_stage_id(self):
        # Since project stages are order by sequence first, this should fetch the one with the lowest sequence number.
        return self.env['project.project.stage'].search([], limit=1)

    @api.model
    def _search_is_favorite(self, operator, value):
        if operator != 'in':
            return NotImplemented
        return [('favorite_user_ids', 'in', [self.env.uid])]

    def _compute_is_favorite(self):
        favorite_project_ids = self.env.user.favorite_project_ids
        for project in self:
            project.is_favorite = project in favorite_project_ids

    def _set_favorite_user_ids(self, is_favorite):
        self_sudo = self.sudo() # To allow project users to set projects as favorite
        if is_favorite:
            self_sudo.favorite_user_ids = [Command.link(self.env.uid)]
        else:
            self_sudo.favorite_user_ids = [Command.unlink(self.env.uid)]

    name = fields.Char("Name", index='trigram', required=True, tracking=True, translate=True, default_export_compatible=True)
    description = fields.Html(help="Description to provide more information and context about this project")
    active = fields.Boolean(default=True, copy=False, export_string_translation=False)
    sequence = fields.Integer(default=10, export_string_translation=False)
    partner_id = fields.Many2one('res.partner', string='Customer', bypass_search_access=True, tracking=True, domain="['|', ('company_id', '=?', company_id), ('company_id', '=', False)]", index='btree_not_null')
    company_id = fields.Many2one('res.company', string='Company', compute="_compute_company_id", inverse="_inverse_company_id", store=True, readonly=False)
    currency_id = fields.Many2one('res.currency', compute="_compute_currency_id", string="Currency", readonly=True, export_string_translation=False)
    analytic_account_balance = fields.Monetary(related="account_id.balance")
    account_id = fields.Many2one('account.analytic.account', copy=False, domain="['|', ('company_id', '=', False), ('company_id', '=?', company_id)]", ondelete='set null')

    favorite_user_ids = fields.Many2many(
        'res.users', 'project_favorite_user_rel', 'project_id', 'user_id',
        string='Members', export_string_translation=False, copy=False)
    is_favorite = fields.Boolean(compute='_compute_is_favorite', readonly=False, search='_search_is_favorite',
        compute_sudo=True, string='Show Project on Dashboard', export_string_translation=False)
    label_tasks = fields.Char(string='Use Tasks as', default=lambda s: s.env._('Tasks'), translate=True,
        help="Name used to refer to the tasks of your project e.g. tasks, tickets, sprints, etc...")
    tasks = fields.One2many('project.task', 'project_id', string="Task Activities")
    resource_calendar_id = fields.Many2one(
        'resource.calendar', string='Working Time', compute='_compute_resource_calendar_id', export_string_translation=False)
    type_ids = fields.Many2many('project.task.type', 'project_task_type_rel', 'project_id', 'type_id', string='Tasks Stages', export_string_translation=False)
    task_count = fields.Integer(compute='_compute_task_count', string="Task Count", export_string_translation=False)
    open_task_count = fields.Integer(compute='_compute_open_task_count', string="Open Task Count", export_string_translation=False)
    task_ids = fields.One2many('project.task', 'project_id', string='Tasks', export_string_translation=False,
                               domain="[('is_closed', '=', False), ('is_template', 'in', [is_template, True])]")
    color = fields.Integer(string='Color Index', export_string_translation=False)
    user_id = fields.Many2one('res.users', string='Project Manager', default=lambda self: self.env.user, tracking=True, falsy_value_label=_lt("👤 Unassigned"))
    alias_id = fields.Many2one(help="Internal email associated with this project. Incoming emails are automatically synchronized "
                                    "with Tasks (or optionally Issues if the Issue Tracker module is installed).")
    privacy_visibility = fields.Selection([
            ('followers', 'Invited internal users (private)'),
            ('employees', 'All internal users'),
            ('portal', 'Invited portal users and all internal users (public)'),
        ],
        string='Visibility', required=True,
        default='portal',
        tracking=True,
        help="People to whom this project and its tasks will be visible.\n\n"
            "- Invited internal users: when following a project, internal users will get access to all of its tasks without distinction. "
            "Otherwise, they will only get access to the specific tasks they are following.\n "
            "A user with the project > administrator access right level can still access this project and its tasks, even if they are not explicitly part of the followers.\n\n"
            "- All internal users: all internal users can access the project and all of its tasks without distinction.\n\n"
            "- Invited portal users and all internal users: all internal users can access the project and all of its tasks without distinction.\n"
            "When following a project, portal users will only get access to the specific tasks they are following.\n\n"
            "When a project is shared in read-only, the portal user is redirected to their portal. They can view the tasks they are following, but not edit them.\n"
            "When a project is shared in edit, the portal user is redirected to the kanban and list views of the tasks. They can modify a selected number of fields on the tasks.\n\n"
            "In any case, an internal user with no project access rights can still access a task, "
            "provided that they are given the corresponding URL (and that they are part of the followers if the project is private).")
    privacy_visibility_warning = fields.Char('Privacy Visibility Warning', compute='_compute_privacy_visibility_warning', export_string_translation=False)
    access_instruction_message = fields.Char('Access Instruction Message', compute='_compute_access_instruction_message', export_string_translation=False)
    date_start = fields.Date(string='Start Date', copy=False)
    date = fields.Date(string='Expiration Date', copy=False, index=True, tracking=True,
        help="Date on which this project ends. The timeframe defined on the project is taken into account when viewing its planning.")
    allow_task_dependencies = fields.Boolean('Task Dependencies', default=lambda self: self.env.user.has_group('project.group_project_task_dependencies'), inverse='_inverse_allow_task_dependencies')
    allow_milestones = fields.Boolean('Milestones', default=lambda self: self.env.user.has_group('project.group_project_milestone'))
    tag_ids = fields.Many2many('project.tags', relation='project_project_project_tags_rel', string='Tags')
    task_properties_definition = fields.PropertiesDefinition('Task Properties')
    closed_task_count = fields.Integer(compute="_compute_closed_task_count", export_string_translation=False)
    task_completion_percentage = fields.Float(compute="_compute_task_completion_percentage", export_string_translation=False)

    # Project Sharing fields
    collaborator_ids = fields.One2many('project.collaborator', 'project_id', string='Collaborators', copy=False, export_string_translation=False)
    collaborator_count = fields.Integer('# Collaborators', compute='_compute_collaborator_count', compute_sudo=True, export_string_translation=False)

    # rating fields
    rating_request_deadline = fields.Datetime(compute='_compute_rating_request_deadline', store=True, export_string_translation=False)
    rating_active = fields.Boolean('Customer Ratings', default=lambda self: self.env.user.has_group('project.group_project_rating'))
    rating_status = fields.Selection(
        [('stage', 'when reaching a given stage'),
         ('periodic', 'on a periodic basis')
        ], 'Customer Ratings Status', default="stage", required=True,
        help="Collect feedback from your customers by sending them a rating request when a task enters a certain stage. To do so, define a rating email template on the corresponding stages.\n"
             "Rating when changing stage: an email will be automatically sent when the task reaches the stage on which the rating email template is set.\n"
             "Periodic rating: an email will be automatically sent at regular intervals as long as the task remains in the stage in which the rating email template is set.")
    rating_status_period = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('bimonthly', 'Twice a Month'),
        ('monthly', 'Once a Month'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly')], 'Rating Frequency', required=True, default='monthly')

    # Not `required` since this is an option to enable in project settings.
    stage_id = fields.Many2one('project.project.stage', string='Stage', ondelete='restrict', groups="project.group_project_stages",
        tracking=True, index=True, copy=False, default=_default_stage_id, group_expand='_read_group_expand_full')
    stage_id_color = fields.Integer(string='Stage Color', related="stage_id.color", export_string_translation=False)
    duration_tracking = fields.Json(groups="project.group_project_stages")

    update_ids = fields.One2many('project.update', 'project_id', export_string_translation=False)
    update_count = fields.Integer(compute='_compute_total_update_ids', export_string_translation=False)
    last_update_id = fields.Many2one('project.update', string='Last Update', copy=False, export_string_translation=False)
    last_update_status = fields.Selection(selection=[
        ('on_track', 'On Track'),
        ('at_risk', 'At Risk'),
        ('off_track', 'Off Track'),
        ('on_hold', 'On Hold'),
        ('to_define', 'Set Status'),
        ('done', 'Complete'),
    ], default='to_define', compute='_compute_last_update_status', store=True, readonly=False, required=True, export_string_translation=False)
    last_update_color = fields.Integer(compute='_compute_last_update_color', export_string_translation=False)
    milestone_ids = fields.One2many('project.milestone', 'project_id', copy=True, export_string_translation=False)
    milestone_count = fields.Integer(compute='_compute_milestone_count', groups='project.group_project_milestone', export_string_translation=False)
    milestone_count_reached = fields.Integer(compute='_compute_milestone_reached_count', groups='project.group_project_milestone', export_string_translation=False)
    is_milestone_exceeded = fields.Boolean(compute="_compute_is_milestone_exceeded", search='_search_is_milestone_exceeded', export_string_translation=False)
    milestone_progress = fields.Integer("Milestones Reached", compute='_compute_milestone_reached_count', groups="project.group_project_milestone", export_string_translation=False)
    next_milestone_id = fields.Many2one('project.milestone', compute='_compute_next_milestone_id', groups="project.group_project_milestone", export_string_translation=False)
    can_mark_milestone_as_done = fields.Boolean(compute='_compute_next_milestone_id', groups="project.group_project_milestone", export_string_translation=False)
    is_milestone_deadline_exceeded = fields.Boolean(compute='_compute_next_milestone_id', groups="project.group_project_milestone", export_string_translation=False)
    is_template = fields.Boolean(copy=False, export_string_translation=False)

    _project_date_greater = models.Constraint(
        'check(date >= date_start)',
        "The project's start date must be before its end date.",
    )

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if (self.env.user.has_group('project.group_project_stages') and self.stage_id.company_id
                and self.stage_id.company_id != self.company_id):
            self.stage_id = self.env['project.project.stage'].search(
                [('company_id', 'in', [self.company_id.id, False])],
                order=f"sequence asc, {self.env['project.project.stage']._order}",
                limit=1,
            ).id

    @api.depends('milestone_ids', 'milestone_ids.is_reached', 'milestone_ids.deadline')
    def _compute_next_milestone_id(self):
        milestones_per_project_id = {
            project.id: milestones
            for project, milestones in self.env['project.milestone']._read_group(
                [('project_id', 'in', self.ids), ('is_reached', '=', False)],
                ['project_id'],
                ['id:recordset'],
            )
        }
        milestones = self.env['project.milestone'].concat(*milestones_per_project_id.values())
        task_read_group = self.env['project.task']._read_group(
            [('milestone_id', 'in', milestones.ids)],
            ['milestone_id', 'state'],
            ['__count'],
        )
        task_count_per_milestones = defaultdict(lambda: (0, 0))
        for milestone, state, count in task_read_group:
            opened_task_count, closed_task_count = task_count_per_milestones[milestone.id]
            if state in CLOSED_STATES:
                closed_task_count += count
            else:
                opened_task_count += count
            task_count_per_milestones[milestone.id] = opened_task_count, closed_task_count
        for project in self:
            milestones = milestones_per_project_id.get(project.id, self.env['project.milestone'])
            project.next_milestone_id = milestones[:1]
            milestone_deadline_exceeded = False
            milestone_marked_as_done = False
            for m in milestones:
                opened_task_count, closed_task_count = task_count_per_milestones[m.id]
                if (
                    not milestone_deadline_exceeded
                    and m.is_deadline_exceeded
                    and (opened_task_count > 0 or closed_task_count == 0)
                ):
                    milestone_deadline_exceeded = True
                    break
                if not milestone_marked_as_done and opened_task_count == 0 and closed_task_count > 0:
                    milestone_marked_as_done = True
            project.is_milestone_deadline_exceeded = milestone_deadline_exceeded
            project.can_mark_milestone_as_done = milestone_marked_as_done

    def _compute_access_url(self):
        super()._compute_access_url()
        for project in self:
            project.access_url = f'/my/projects/{project.id}'

    def _compute_access_warning(self):
        super()._compute_access_warning()
        for project in self.filtered(lambda x: x.privacy_visibility != 'portal'):
            project.access_warning = _(
                "This project is currently restricted to \"Invited internal users\". The project's visibility will be changed to \"invited portal users and all internal users (public)\" in order to make it accessible to the recipients.")

    @api.depends('account_id.company_id', 'partner_id.company_id')
    def _compute_company_id(self):
        for project in self:
            # if a new restriction is put on the account or the customer, the restriction on the project is updated.
            if project.account_id.company_id:
                project.company_id = project.account_id.company_id
            if not project.company_id and project.partner_id.company_id:
                project.company_id = project.partner_id.company_id

    @api.depends_context('company')
    @api.depends('company_id', 'company_id.resource_calendar_id')
    def _compute_resource_calendar_id(self):
        for project in self:
            project.resource_calendar_id = project.company_id.resource_calendar_id or self.env.company.resource_calendar_id

    def _inverse_company_id(self):
        """
        Ensures that the new company of the project is valid for the account. If not set back the previous company, and raise a user Error.
        Ensures that the new company of the project is valid for the partner
        """
        for project in self:
            account = project.account_id
            if project.partner_id and project.partner_id.company_id and project.company_id != project.partner_id.company_id:
                raise UserError(_('The project and the associated partner must be linked to the same company.'))
            if not account or not account.company_id:
                continue
            # if the account of the project has more than one company linked to it, or if it has aal, do not update the account, and set back the old company on the project.
            if (account.project_count > 1 or account.line_ids) and project.company_id != account.company_id:
                raise UserError(
                    _("The project's company cannot be changed if its analytic account has analytic lines or if more than one project is linked to it."))
            account.company_id = project.company_id

    @api.depends('rating_status', 'rating_status_period')
    def _compute_rating_request_deadline(self):
        periods = {'daily': 1, 'weekly': 7, 'bimonthly': 15, 'monthly': 30, 'quarterly': 90, 'yearly': 365}
        for project in self:
            project.rating_request_deadline = fields.Datetime.now() + timedelta(days=periods.get(project.rating_status_period, 0))

    @api.depends('last_update_id.status')
    def _compute_last_update_status(self):
        for project in self:
            project.last_update_status = project.last_update_id.status or 'to_define'

    @api.depends('last_update_status')
    def _compute_last_update_color(self):
        for project in self:
            project.last_update_color = STATUS_COLOR[project.last_update_status]

    @api.depends('milestone_ids')
    def _compute_milestone_count(self):
        read_group = self.env['project.milestone']._read_group([('project_id', 'in', self.ids)], ['project_id'], ['__count'])
        mapped_count = {project.id: count for project, count in read_group}
        for project in self:
            project.milestone_count = mapped_count.get(project.id, 0)

    @api.depends('milestone_ids.is_reached', 'milestone_count')
    def _compute_milestone_reached_count(self):
        read_group = self.env['project.milestone']._read_group(
            [('project_id', 'in', self.ids), ('is_reached', '=', True)],
            ['project_id'],
            ['__count'],
        )
        mapped_count = {project.id: count for project, count in read_group}
        for project in self:
            project.milestone_count_reached = mapped_count.get(project.id, 0)
            project.milestone_progress = project.milestone_count and project.milestone_count_reached * 100 // project.milestone_count

    @api.depends('milestone_ids', 'milestone_ids.is_reached', 'milestone_ids.deadline', 'allow_milestones')
    def _compute_is_milestone_exceeded(self):
        today = fields.Date.context_today(self)
        read_group = self.env['project.milestone']._read_group([
            ('project_id', 'in', self.filtered('allow_milestones').ids),
            ('is_reached', '=', False),
            ('deadline', '<=', today)], ['project_id'], ['__count'])
        mapped_count = {project.id: count for project, count in read_group}
        for project in self:
            project.is_milestone_exceeded = bool(mapped_count.get(project.id, 0))

    @api.depends_context('company')
    @api.depends('company_id')
    def _compute_currency_id(self):
        default_currency_id = self.env.company.currency_id
        for project in self:
            project.currency_id = project.company_id.currency_id or default_currency_id

    @api.model
    def _search_is_milestone_exceeded(self, operator, value):
        if operator != 'in':
            return NotImplemented

        sql = SQL("""(
            SELECT P.id
              FROM project_project P
         LEFT JOIN project_milestone M ON P.id = M.project_id
             WHERE M.is_reached IS false
               AND P.allow_milestones IS true
               AND M.deadline <= CAST(now() AS date)
        )""")
        return [('id', 'any', sql)]

    @api.depends('collaborator_ids', 'privacy_visibility')
    def _compute_collaborator_count(self):
        project_sharings = self.filtered(lambda project: project.privacy_visibility == 'portal')
        collaborator_read_group = self.env['project.collaborator']._read_group(
            [('project_id', 'in', project_sharings.ids)],
            ['project_id'],
            ['__count'],
        )
        collaborator_count_by_project = {project.id: count for project, count in collaborator_read_group}
        for project in self:
            project.collaborator_count = collaborator_count_by_project.get(project.id, 0)

    @api.depends('privacy_visibility')
    def _compute_privacy_visibility_warning(self):
        for project in self:
            if not project.ids:
                project.privacy_visibility_warning = ''
            elif project.privacy_visibility == 'portal' and project._origin.privacy_visibility != 'portal':
                project.privacy_visibility_warning = _('Customers will be added to the followers of their project and tasks.')
            elif project.privacy_visibility != 'portal' and project._origin.privacy_visibility == 'portal':
                project.privacy_visibility_warning = _('Portal users will be removed from the followers of the project and its tasks.')
            else:
                project.privacy_visibility_warning = ''

    @api.depends('privacy_visibility')
    def _compute_access_instruction_message(self):
        for project in self:
            if project.privacy_visibility == 'portal':
                project.access_instruction_message = _('To give portal users access to your project, add them as followers. For task access, add them as followers for each task.')
            elif project.privacy_visibility == 'followers':
                project.access_instruction_message = _('Grant employees access to your project or tasks by adding them as followers. Employees automatically get access to the tasks they are assigned to.')
            else:
                project.access_instruction_message = ''

    @api.depends('update_ids')
    def _compute_total_update_ids(self):
        update_count_per_project = dict(
            self.env['project.update']._read_group(
                [('project_id', 'in', self.ids)],
                ['project_id'],
                ['id:count'],
            )
        )
        for project in self:
            project.update_count = update_count_per_project.get(project, 0)

    def _inverse_allow_task_dependencies(self):
        """ Reset state for waiting tasks in the project if the feature is disabled
            or recompute the tasks with dependencies if the project has the feature enabled again
        """
        project_with_task_dependencies_feature = self.filtered('allow_task_dependencies')
        projects_without_task_dependencies_feature = self - project_with_task_dependencies_feature
        ProjectTask = self.env['project.task']
        if (
            project_with_task_dependencies_feature
            and (
                open_tasks_with_dependencies := ProjectTask.search([
                    ('project_id', 'in', project_with_task_dependencies_feature.ids),
                    ('depend_on_ids.state', 'in', ProjectTask.OPEN_STATES),
                    ('state', 'in', ProjectTask.OPEN_STATES),
                ])
            )
        ):
            open_tasks_with_dependencies.state = '04_waiting_normal'
        if (
            projects_without_task_dependencies_feature
            and (
                waiting_tasks := ProjectTask.search([
                    ('project_id', 'in', projects_without_task_dependencies_feature.ids),
                    ('state', '=', '04_waiting_normal'),
                ])
            )
        ):
            waiting_tasks.state = '01_in_progress'

    @api.model
    def _map_tasks_default_values(self, project):
        """ get the default value for the copied task on project duplication.
        The stage_id, name field will be set for each task in the overwritten copy_data function in project.task """
        return {
            'state': '01_in_progress',
            'company_id': project.company_id.id,
            'project_id': project.id,
        }

    def map_tasks(self, new_project_id):
        """ copy and map tasks from old to new project """
        project = self.browse(new_project_id)
        new_tasks = self.env['project.task']
        # We want to copy archived task, but do not propagate an active_test context key
        tasks = self.env['project.task'].with_context(active_test=False).search([('project_id', '=', self.id), ('parent_id', '=', False)])
        if self.allow_task_dependencies and 'task_mapping' not in self.env.context:
            self = self.with_context(task_mapping=dict())
        # preserve task name and stage, normally altered during copy
        defaults = self._map_tasks_default_values(project)
        new_tasks = tasks.with_context(copy_project=True).copy(defaults)
        all_subtasks = new_tasks._get_all_subtasks()
        all_subtasks.filtered(
            lambda child: child.project_id == self
        ).write({
            'project_id': project.id
        })
        return True

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        copy_from_template = self.env.context.get('copy_from_template')
        for project, vals in zip(self, vals_list):
            if project.is_template and not copy_from_template:
                vals['is_template'] = True
            if copy_from_template:
                for field in self._get_template_field_blacklist():
                    if field in vals and field not in default:
                        del vals[field]
            if copy_from_template or (not project.is_template and vals.get('is_template')):
                vals['name'] = default.get('name', project.name)
            else:
                vals['name'] = default.get('name', self.env._('%s (copy)', project.name))
        return vals_list

    def copy(self, default=None):
        default = dict(default or {})
        # Since we dont want to copy the milestones if the original project has the feature disabled, we set the milestones to False by default.
        default['milestone_ids'] = False
        copy_context = dict(
             self.env.context,
             mail_auto_subscribe_no_notify=True,
             mail_create_nosubscribe=True,
         )
        copy_context.pop("default_stage_id", None)
        new_projects = super(ProjectProject, self.with_context(copy_context)).copy(default=default)
        if 'milestone_mapping' not in self.env.context:
            self = self.with_context(milestone_mapping={})
        actions_per_project = dict(self.env['ir.embedded.actions']._read_group(
            domain=[
                ('parent_res_id', 'in', self.ids),
                ('parent_res_model', '=', 'project.project'),
                ('user_id', '=', False),
            ],
            groupby=['parent_res_id'],
            aggregates=['id:recordset'],
        ))
        for old_project, new_project in zip(self, new_projects):
            for follower in old_project.message_follower_ids:
                new_project.message_subscribe(partner_ids=follower.partner_id.ids, subtype_ids=follower.subtype_ids.ids)
            if old_project.allow_milestones:
                new_project.milestone_ids = self.milestone_ids.copy().ids
            if 'tasks' not in default:
                old_project.map_tasks(new_project.id)
            if not old_project.active:
                new_project.with_context(active_test=False).tasks.active = True
            # Copy the shared embedded actions in the new project
            shared_embedded_actions = actions_per_project.get(old_project.id)
            if shared_embedded_actions:
                copy_shared_embedded_actions = shared_embedded_actions.copy({'parent_res_id': new_project.id})
                for original_action, copied_action in zip(shared_embedded_actions, copy_shared_embedded_actions):
                    copied_action.filter_ids = original_action.filter_ids.copy({'embedded_parent_res_id': new_project.id})
        return new_projects

    @api.model
    def name_create(self, name):
        res = super().name_create(name)
        if res:
            # We create a default stage `new` for projects created on the fly.
            self.browse(res[0]).type_ids += self.env['project.task.type'].sudo().create({'name': _('New')})
        return res

    @api.model_create_multi
    def create(self, vals_list):
        # Prevent double project creation
        self = self.with_context(mail_create_nosubscribe=True)
        if any('label_tasks' in vals and not vals['label_tasks'] for vals in vals_list):
            task_label = _("Tasks")
            for vals in vals_list:
                if 'label_tasks' in vals and not vals['label_tasks']:
                    vals['label_tasks'] = task_label
        if self.env.user.has_group('project.group_project_stages'):
            if 'default_stage_id' in self.env.context:
                stage = self.env['project.project.stage'].browse(self.env.context['default_stage_id'])
                # The project's company_id must be the same as the stage's company_id
                if stage.company_id:
                    for vals in vals_list:
                        if vals.get('stage_id'):
                            continue
                        vals['company_id'] = stage.company_id.id
            else:
                companies_ids = [vals.get('company_id', False) for vals in vals_list] + [False]
                stages = self.env['project.project.stage'].search([('company_id', 'in', companies_ids)])
                for vals in vals_list:
                    if vals.get('stage_id'):
                        continue
                    # Pick the stage with the lowest sequence with no company or project's company
                    stage_domain = [False] if 'company_id' not in vals else [False, vals.get('company_id')]
                    stage = stages.filtered(lambda s: s.company_id.id in stage_domain)[:1]
                    vals['stage_id'] = stage.id

        for vals in vals_list:
            if vals.pop('is_favorite', False):
                vals['favorite_user_ids'] = [self.env.uid]
        projects = super().create(vals_list)
        return projects

    def write(self, vals):
        if vals.get('access_token'):
            self.ensure_one()  # We are not supposed to add a single access token to multiple project
            if self.privacy_visibility != 'portal':
                vals['access_token'] = ''

        # Here we modify the project's stage according to the selected company (selecting the first
        # stage in sequence that is linked to the company).
        company_id = vals.get('company_id')
        if self.env.user.has_group('project.group_project_stages') and company_id:
            projects_already_with_company = self.filtered(lambda p: p.company_id.id == company_id)
            if projects_already_with_company:
                projects_already_with_company.write({key: value for key, value in vals.items() if key != 'company_id'})
                self -= projects_already_with_company
            if company_id not in (None, *self.company_id.ids) and self.stage_id.company_id:
                ProjectStage = self.env['project.project.stage']
                vals["stage_id"] = ProjectStage.search(
                    [('company_id', 'in', (company_id, False))],
                    order=f"sequence asc, {ProjectStage._order}",
                    limit=1,
                ).id

        # directly compute is_favorite to dodge allow write access right
        if 'is_favorite' in vals:
            self._set_favorite_user_ids(vals.pop('is_favorite'))

        if 'last_update_status' in vals and vals['last_update_status'] != 'to_define':
            for project in self:
                # This does not benefit from multi create, this is to allow the default description from being built.
                # This does seem ok since last_update_status should only be updated on one record at once.
                self.env['project.update'].with_context(default_project_id=project.id).create({
                    'name': _('Status Update - %(date)s', date=fields.Date.today().strftime(get_lang(self.env).date_format)),
                    'status': vals.get('last_update_status'),
                })
            vals.pop('last_update_status')
        if vals.get('privacy_visibility'):
            self._change_privacy_visibility(vals['privacy_visibility'])

        date_start = vals.get('date_start', True)
        date_end = vals.get('date', True)
        if not date_start or not date_end:
            vals['date_start'] = False
            vals['date'] = False
        else:
            no_current_date_begin = not all(project.date_start for project in self)
            no_current_date_end = not all(project.date for project in self)
            date_start_update = 'date_start' in vals
            date_end_update = 'date' in vals
            if (date_start_update and no_current_date_end and not date_end_update):
                del vals['date_start']
            elif (date_end_update and no_current_date_begin and not date_start_update):
                del vals['date']

        res = super().write(vals) if vals else True

        if 'allow_task_dependencies' in vals and not vals.get('allow_task_dependencies'):
            self.env['project.task'].search([('project_id', 'in', self.ids), ('state', '=', '04_waiting_normal')]).write({'state': '01_in_progress'})

        if 'active' in vals:
            # archiving/unarchiving a project does it on its tasks, too
            self.with_context(active_test=False).mapped('tasks').write({'active': vals['active']})
        if 'name' in vals and self.account_id:
            projects_read_group = self.env['project.project']._read_group(
                [('account_id', 'in', self.account_id.ids)],
                ['account_id'],
                having=[('__count', '=', 1)],
            )
            analytic_account_to_update = self.env['account.analytic.account'].browse([
                analytic_account.id for [analytic_account] in projects_read_group
            ])
            analytic_account_to_update.write({'name': self.name})
        return res

    def unlink(self):
        # Delete the empty related analytic account
        analytic_accounts_to_delete = self.env['account.analytic.account']
        for project in self:
            if project.account_id and not project.account_id.line_ids:
                analytic_accounts_to_delete |= project.account_id
        self.with_context(active_test=False).tasks.unlink()
        result = super().unlink()
        analytic_accounts_to_delete.unlink()
        return result

    def _order_field_to_sql(self, alias, field_name, direction, nulls, query):
        if field_name == 'is_favorite':
            sql_field = SQL(
                "%s IN (SELECT project_id FROM project_favorite_user_rel WHERE user_id = %s)",
                SQL.identifier(alias, 'id'), self.env.uid,
            )
            return SQL("%s %s %s", sql_field, direction, nulls)

        return super()._order_field_to_sql(alias, field_name, direction, nulls, query)

    def message_subscribe(self, partner_ids=None, subtype_ids=None):
        """
        Subscribe to newly created task but not all existing active task when subscribing to a project.
        User update notification preference of project its propagated to all the tasks that the user is
        currently following.
        """
        res = super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)
        if subtype_ids:
            project_subtypes = self.env['mail.message.subtype'].browse(subtype_ids)
            task_subtypes = (project_subtypes.mapped('parent_id') | project_subtypes.filtered(lambda sub: sub.internal or sub.default)).ids
            if task_subtypes:
                for task in self.task_ids:
                    partners = set(task.message_partner_ids.ids) & set(partner_ids)
                    if partners:
                        task.message_subscribe(partner_ids=list(partners), subtype_ids=task_subtypes)
                self.update_ids.message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)
        return res

    def message_unsubscribe(self, partner_ids=None):
        self.task_ids.message_unsubscribe(partner_ids=partner_ids)
        super().message_unsubscribe(partner_ids=partner_ids)
        if partner_ids:
            self.env['project.collaborator'].search([('partner_id', 'in', partner_ids), ('project_id', 'in', self.ids)]).unlink()

    def _alias_get_creation_values(self):
        values = super()._alias_get_creation_values()
        values['alias_model_id'] = self.env['ir.model']._get('project.task').id
        if self.id:
            values['alias_defaults'] = defaults = ast.literal_eval(self.alias_defaults or "{}")
            defaults['project_id'] = self.id
        return values

    @api.constrains('stage_id')
    def _ensure_stage_has_same_company(self):
        for project in self:
            if project.stage_id.company_id and project.stage_id.company_id != project.company_id:
                raise UserError(
                    _('This project is associated with %(project_company)s, whereas the selected stage belongs to %(stage_company)s. '
                    'There are a couple of options to consider: either remove the company designation '
                    'from the project or from the stage. Alternatively, you can update the company '
                    'information for these records to align them under the same company.', project_company=project.company_id.name, stage_company=project.stage_id.company_id.name)
                    if project.company_id else
                    _('This project is not associated with any company, while the stage is associated with %s. '
                    'There are a couple of options to consider: either change the project\'s company '
                    'to align with the stage\'s company or remove the company designation from the stage', project.stage_id.company_id.name)
                )

    def get_template_tasks(self):
        self.ensure_one()
        return self.env['project.task'].search_read(
            [('project_id', '=', self.id), ('is_template', '=', True)],
            ['id', 'name'],
        )

    # ---------------------------------------------------
    # Mail gateway
    # ---------------------------------------------------

    def _track_template(self, changes):
        res = super()._track_template(changes)
        project = self[0]
        if self.env.user.has_group('project.group_project_stages') and 'stage_id' in changes and project.stage_id.mail_template_id:
            res['stage_id'] = (project.stage_id.mail_template_id, {
                'auto_delete_keep_log': False,
                'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
                'email_layout_xmlid': 'mail.mail_notification_light',
            })
        return res

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'stage_id' in init_values:
            return self.env.ref('project.mt_project_stage_change')
        return super()._track_subtype(init_values)

    def _mail_get_message_subtypes(self):
        res = super()._mail_get_message_subtypes()
        if not self.rating_active:
            res -= self.env.ref('project.mt_project_task_rating')
        if len(self) == 1:
            waiting_subtype = self.env.ref('project.mt_project_task_waiting')
            if not self.allow_task_dependencies and waiting_subtype in res:
                res -= waiting_subtype
        return res

    def _notify_get_recipients_groups(self, message, model_description, msg_vals=False):
        """ Give access to the portal user/customer if the project visibility is portal. """
        groups = super()._notify_get_recipients_groups(message, model_description, msg_vals=msg_vals)
        if not self:
            return groups

        self.ensure_one()
        portal_privacy = self.privacy_visibility == 'portal'
        for group_name, _group_method, group_data in groups:
            if group_name in ['portal', 'portal_customer'] and not portal_privacy:
                group_data['has_button_access'] = False
        return groups

    # ---------------------------------------------------
    #  Actions
    # ---------------------------------------------------

    def action_project_task_burndown_chart_report(self):
        action = self.env['ir.actions.act_window']._for_xml_id('project.action_project_task_burndown_chart_report')
        action['display_name'] = _("%(name)s's Burndown Chart", name=self.name)
        context = action['context'].replace('active_id', str(self.id))
        context = ast.literal_eval(context)
        context.update({
            'stage_name_and_sequence_per_id': {
                stage.id: {
                    'sequence': stage.sequence,
                    'name': stage.name
                } for stage in self.type_ids
            }
        })
        action['context'] = context
        return action

    def project_update_all_action(self):
        action = self.env['ir.actions.act_window']._for_xml_id('project.project_update_all_action')
        action['display_name'] = _("%(name)s Dashboard", name=self.name)
        return action

    def action_open_share_project_wizard(self):
        template = self.env.ref('project.mail_template_project_sharing', raise_if_not_found=False)

        local_context = self.env.context | {
            'default_template_id': template.id if template else False,
            'default_email_layout_xmlid': 'mail.mail_notification_light',
            'active_id': self.id,
            'active_model': 'project.project',
        }
        action = self.env["ir.actions.actions"]._for_xml_id("project.project_share_wizard_action")
        if self.env.context.get('default_access_mode'):
            action['name'] = _("Share Project")
        action['context'] = local_context
        return action

    def toggle_favorite(self):
        favorite_projects = not_fav_projects = self.env['project.project'].sudo()
        for project in self:
            if self.env.user in project.favorite_user_ids:
                favorite_projects |= project
            else:
                not_fav_projects |= project

        # Project User has no write access for project.
        not_fav_projects.write({'favorite_user_ids': [(4, self.env.uid)]})
        favorite_projects.write({'favorite_user_ids': [(3, self.env.uid)]})

    def action_view_tasks(self):
        action = self.env['ir.actions.act_window'].with_context(active_id=self.id)._for_xml_id('project.act_project_project_2_project_task_all')
        action['display_name'] = self.name
        context = action['context'].replace('active_id', str(self.id))
        context = ast.literal_eval(context)
        context.update({
            'create': self.active,
            'active_test': self.active,
            'active_id': self.id,
            })
        action['context'] = context
        if self.is_template:
            action['context'].update({'default_is_template': True})
            domain = ast.literal_eval(action['domain'].replace('active_id', str(self.id)))
            domain.remove(('has_template_ancestor', '=', False))
            action['domain'] = domain
            action['views'] = [(view_id, view_type) for view_id, view_type in action['views'] if view_type not in ('pivot', 'graph')]
        return action

    def action_view_all_rating(self):
        """ return the action to see all the rating of the project and activate default filters"""
        action = self.env['ir.actions.act_window']._for_xml_id('project.rating_rating_action_view_project_rating')
        action['display_name'] = _("%(name)s's Rating", name=self.name)
        action_context = ast.literal_eval(action['context']) if action['context'] else {}
        action_context.update(self.env.context)
        action_context['search_default_filter_write_date'] = 'custom_write_date_last_30_days'
        action_context.pop('group_by', None)
        action['domain'] = [('consumed', '=', True), ('parent_res_model', '=', 'project.project'), ('parent_res_id', '=', self.id)]
        if self.rating_count == 1:
            action.update({
                'view_mode': 'form',
                'views': [(view_id, view_type) for view_id, view_type in action['views'] if view_type == 'form'],
                'res_id': self.rating_ids[0].id, # [0] since rating_ids might be > then rating_count
            })
        return dict(action, context=action_context)

    def action_view_tasks_analysis(self):
        """ return the action to see the tasks analysis report of the project """
        action = self.env['ir.actions.act_window']._for_xml_id('project.action_project_task_user_tree')
        action['display_name'] = _("%(name)s's Tasks Analysis", name=self.name)
        action_context = ast.literal_eval(action['context']) if action['context'] else {}
        action_context['search_default_project_id'] = self.id
        return dict(action, context=action_context)

    def action_get_list_view(self):
        action = self.env['ir.actions.act_window']._for_xml_id('project.project_milestone_action')
        action['display_name'] = _("%(name)s's Milestones", name=self.name)
        return action

    def action_view_tasks_from_project_milestone(self):
        action = self.env['ir.actions.act_window']._for_xml_id('project.project_milestone_action_view_tasks')
        action['display_name'] = _("Tasks")
        action['domain'] = [('milestone_id', 'in', self.milestone_ids.ids)]
        return action

    # ---------------------------------------------
    #  PROJECT UPDATES
    # ---------------------------------------------

    def action_profitability_items(self, section_name, domain=None, res_id=False):
        return {}

    def get_last_update_or_default(self):
        self.ensure_one()
        labels = dict(self._fields['last_update_status']._description_selection(self.env))
        return {
            'status': labels.get(self.last_update_status, _('Set Status')),
            'color': self.last_update_color,
        }

    def get_panel_data(self):
        self.ensure_one()
        if not self.env.user.has_group('project.group_project_user'):
            return {}
        show_profitability = self._show_profitability()
        panel_data = {
            'user': self._get_user_values(),
            'buttons': sorted(self._get_stat_buttons(), key=lambda k: k['sequence']),
            'currency_id': self.currency_id.id,
            'show_project_profitability_helper': show_profitability and self._show_profitability_helper(),
            'show_milestones': self.allow_milestones,
        }
        if self.allow_milestones:
            panel_data['milestones'] = self._get_milestones()
        if show_profitability:
            profitability_items = self.with_context(active_test=False)._get_profitability_items()
            if self._get_profitability_sequence_per_invoice_type() and profitability_items and 'revenues' in profitability_items and 'costs' in profitability_items:  # sort the data values
                profitability_items['revenues']['data'] = sorted(profitability_items['revenues']['data'], key=lambda k: k['sequence'])
                profitability_items['costs']['data'] = sorted(profitability_items['costs']['data'], key=lambda k: k['sequence'])
            panel_data['profitability_items'] = profitability_items
            panel_data['profitability_labels'] = self._get_profitability_labels()
        return panel_data

    def get_milestones(self):
        if self.env.user.has_group('project.group_project_user'):
            return self._get_milestones()
        return {}

    def _get_profitability_labels(self):
        return {}

    def _get_profitability_sequence_per_invoice_type(self):
        return {}

    def _get_already_included_profitability_invoice_line_ids(self):
        # To be extended to avoid account.move.line overlap between
        # profitability reports.
        return []

    def _get_user_values(self):
        return {
            'is_project_user': self.env.user.has_group('project.group_project_user'),
        }

    def _show_profitability(self):
        self.ensure_one()
        return True

    def _show_profitability_helper(self):
        return self.env.user.has_group('analytic.group_analytic_accounting')

    def _get_profitability_aal_domain(self):
        return [('account_id', 'in', self.account_id.ids)]

    def _get_profitability_items(self, with_action=True):
        return self._get_items_from_aal(with_action)

    def _get_items_from_aal(self, with_action=True):
        return {
            'revenues': {'data': [], 'total': {'invoiced': 0.0, 'to_invoice': 0.0}},
            'costs': {'data': [], 'total': {'billed': 0.0, 'to_bill': 0.0}},
        }

    def _get_milestones(self):
        self.ensure_one()
        return {
            'data': self.milestone_ids._get_data_list(),
        }

    def _get_stat_buttons(self):
        self.ensure_one()
        closed_task_count = self.task_count - self.open_task_count
        if self.task_count:
            number = self.env._(
                "%(closed_task_count)s / %(task_count)s (%(closed_rate)s%%)",
                closed_task_count=closed_task_count,
                task_count=self.task_count,
                closed_rate=round(100 * closed_task_count / self.task_count),
            )
        else:
            number = self.env._(
                "%(closed_task_count)s / %(task_count)s",
                closed_task_count=closed_task_count,
                task_count=self.task_count,
            )
        buttons = [{
            'icon': 'check',
            'text': self.label_tasks,
            'number': number,
            'action_type': 'object',
            'action': 'action_view_tasks',
            'show': True,
            'sequence': 1,
        }]
        if self.rating_count != 0 and self.env.user.has_group('project.group_project_rating'):
            if self.rating_avg >= rating_data.RATING_AVG_TOP:
                icon = 'smile-o text-success'
            elif self.rating_avg >= rating_data.RATING_AVG_OK:
                icon = 'meh-o text-warning'
            else:
                icon = 'frown-o text-danger'
            buttons.append({
                'icon': icon,
                'text': self.env._('Average Rating'),
                'number': f'{int(self.rating_avg) if self.rating_avg.is_integer() else round(self.rating_avg, 1)} / 5',
                'action_type': 'object',
                'action': 'action_view_all_rating',
                'show': self.rating_active,
                'sequence': 15,
            })
        if self.env.user.has_group('project.group_project_user'):
            buttons.append({
                'icon': 'area-chart',
                'text': self.env._('Burndown Chart'),
                'action_type': 'action',
                'action': 'project.action_project_task_burndown_chart_report',
                'additional_context': json.dumps({
                    'active_id': self.id,
                    'stage_name_and_sequence_per_id': {
                        stage.id: {
                            'sequence': stage.sequence,
                            'name': stage.name
                        } for stage in self.type_ids
                    },
                }),
                'show': True,
                'sequence': 60,
            })
        return buttons

    def _get_profitability_values(self):
        if not self.env.user.has_group('project.group_project_manager'):
            return {}, False
        profitability_items = self._get_profitability_items(False)
        if profitability_items and 'revenues' in profitability_items and 'costs' in profitability_items:  # sort the data values
            profitability_items['revenues']['data'] = sorted(profitability_items['revenues']['data'], key=lambda k: k['sequence'])
            profitability_items['costs']['data'] = sorted(profitability_items['costs']['data'], key=lambda k: k['sequence'])
        costs = sum(profitability_items['costs']['total'].values())
        revenues = sum(profitability_items['revenues']['total'].values())
        margin = revenues + costs
        to_bill_to_invoice = profitability_items['costs']['total']['to_bill'] + profitability_items['revenues']['total']['to_invoice']
        billed_invoiced = profitability_items['costs']['total']['billed'] + profitability_items['revenues']['total']['invoiced']
        expected_percentage, to_bill_to_invoice_percentage, billed_invoiced_percentage = 0, 0, 0
        if revenues:
            expected_percentage = formatLang(self.env, (margin / revenues) * 100, digits=0)
        if profitability_items['revenues']['total']['to_invoice']:
            to_bill_to_invoice_percentage = formatLang(self.env, (to_bill_to_invoice / profitability_items['revenues']['total']['to_invoice']) * 100, digits=0)
        if profitability_items['revenues']['total']['invoiced']:
            billed_invoiced_percentage = formatLang(self.env, (billed_invoiced / profitability_items['revenues']['total']['invoiced']) * 100, digits=0)
        profitability_values_dict = {
            'account_id': self.account_id,
            'costs': profitability_items['costs'],
            'revenues': profitability_items['revenues'],
            'expected_percentage': expected_percentage,
            'to_bill_to_invoice_percentage': to_bill_to_invoice_percentage,
            'billed_invoiced_percentage': billed_invoiced_percentage,
            'total': {
                'costs': costs,
                'revenues': revenues,
                'margin': margin,
                'margin_percentage': formatLang(self.env,
                                                not float_utils.float_is_zero(costs, precision_digits=2) and (margin / -costs) * 100 or 0.0,
                                                digits=0),
            },
            'labels': self._get_profitability_labels(),
        }
        show_profitability = bool(profitability_values_dict.get('account_id')
            and (profitability_values_dict.get('costs') or profitability_values_dict.get('revenues'))
        )
        return profitability_values_dict, show_profitability

    # ---------------------------------------------------
    #  Business Methods
    # ---------------------------------------------------

    def _get_hide_partner(self):
        return False

    @api.model
    def _get_values_analytic_account_batch(self, project_vals_list):
        project_plan, _other_plans = self.env['account.analytic.plan']._get_all_plans()
        return [{
            'name': project_vals.get('name', self.env._('Unknown Analytic Account')),
            'company_id': project_vals.get('company_id', False),
            'partner_id': project_vals.get('partner_id', False),
            'plan_id': project_plan.id,
        } for project_vals in project_vals_list]

    def _create_analytic_account(self):
        analytic_accounts_values = self._get_values_analytic_account_batch(self._read_format(['name', 'company_id', 'partner_id'], None))
        analytic_accounts = self.env['account.analytic.account'].create(analytic_accounts_values)
        for project, analytic_account in zip(self, analytic_accounts):
            project.account_id = analytic_account

    def _get_projects_to_make_billable_domain(self):
        return [('partner_id', '!=', False)]

    @api.constrains(lambda self: self._get_plan_fnames())
    def _check_account_id(self):
        # Overriden from 'analytic.plan.fields.mixin'
        pass

    def _get_plan_domain(self, plan):
        return Domain.AND([super()._get_plan_domain(plan), ['|', ('company_id', '=', False), ('company_id', '=?', unquote('company_id'))]])

    def _get_account_node_context(self, plan):
        return {
            **super()._get_account_node_context(plan),
            'default_company_id': unquote('company_id'),
        }

    # ---------------------------------------------------
    # Rating business
    # ---------------------------------------------------

    # This method should be called once a day by the scheduler
    @api.model
    def _send_rating_all(self):
        projects = self.search([
            ('rating_active', '=', True),
            ('rating_status', '=', 'periodic'),
            ('rating_request_deadline', '<=', fields.Datetime.now())
        ])
        for project in projects:
            project.task_ids._send_task_rating_mail()
            project._compute_rating_request_deadline()
            self.env.cr.commit()

    # ---------------------------------------------------
    # Privacy
    # ---------------------------------------------------

    def _change_privacy_visibility(self, new_visibility):
        """
        Unsubscribe non-internal users from the project and tasks if the project privacy visibility
        goes from 'portal' to a different value.
        If the privacy visibility is set to 'portal', subscribe back project and tasks partners.
        """
        for project in self:
            if project.privacy_visibility == new_visibility:
                continue
            if new_visibility == 'portal':
                project.message_subscribe(partner_ids=project.partner_id.ids)
                for task in project.task_ids.filtered('partner_id'):
                    task.message_subscribe(partner_ids=task.partner_id.ids)
            elif project.privacy_visibility == 'portal':
                portal_users = project.message_partner_ids.user_ids.filtered('share')
                project.message_unsubscribe(partner_ids=portal_users.partner_id.ids)
                project.tasks._unsubscribe_portal_users()
                # revoke access_token since the project and its tasks are no longer accessible for portal/public users
                project.tasks.access_token = ''
                project.access_token = ''

    # ---------------------------------------------------
    # Project sharing
    # ---------------------------------------------------
    def _check_project_sharing_access(self):
        self.ensure_one()
        if self.privacy_visibility != 'portal':
            return False
        if self.env.user._is_portal():
            return self.env['project.collaborator'].search([('project_id', '=', self.sudo().id), ('partner_id', '=', self.env.user.partner_id.id)])
        return self.env.user._is_internal()

    def _add_collaborators(self, partners, limited_access=False):
        self.ensure_one()
        new_collaborators = self._get_new_collaborators(partners)
        if not new_collaborators:
            # Then we have nothing to do
            return
        self.write({'collaborator_ids': [
            Command.create({
                'partner_id': collaborator.id,
                'limited_access': limited_access,
            }) for collaborator in new_collaborators],
        })

    def _get_new_collaborators(self, partners):
        self.ensure_one()
        return partners.filtered(
            lambda partner:
                partner not in self.collaborator_ids.partner_id
                and partner.partner_share
        )

    def _add_followers(self, partners):
        self.ensure_one()
        self.message_subscribe(partners.ids)

        dict_tasks_per_partner = {}
        dict_partner_ids_to_subscribe_per_partner = {}
        for task in self.task_ids:
            if task.partner_id in dict_tasks_per_partner:
                dict_tasks_per_partner[task.partner_id] |= task
            else:
                partner_ids_to_subscribe = [
                    partner.id for partner in partners
                    if partner == task.partner_id or partner in task.partner_id.child_ids
                ]
                if partner_ids_to_subscribe:
                    dict_tasks_per_partner[task.partner_id] = task
                    dict_partner_ids_to_subscribe_per_partner[task.partner_id] = partner_ids_to_subscribe
        for partner, tasks in dict_tasks_per_partner.items():
            tasks.message_subscribe(dict_partner_ids_to_subscribe_per_partner[partner])

    def _thread_to_store(self, store: Store, fields, *, request_list=None):
        super()._thread_to_store(store, fields, request_list=request_list)
        if request_list and "followers" in request_list:
            store.add(
                self,
                {"collaborator_ids": Store.Many(self.collaborator_ids.partner_id, [])},
                as_thread=True,
            )

    @api.depends('task_count', 'open_task_count')
    def _compute_task_completion_percentage(self):
        for task in self:
            task.task_completion_percentage = task.task_count and 1 - task.open_task_count / task.task_count

    # ---------------------------------------------------
    #  Project Template Methods
    # ---------------------------------------------------

    def _get_template_to_project_warnings(self):
        self.ensure_one()
        return []

    def template_to_project_confirmation_callback(self, callbacks):
        self.ensure_one()
        pass

    def _get_template_to_project_confirmation_callbacks(self):
        self.ensure_one()
        return {}

    def action_toggle_project_template_mode(self):
        self.ensure_one()
        config = {
            "params": {
                "project_id": self.id,
            },
        }
        if self.is_template:
            config["tag"] = "project_template_show_undo_confirmation_dialog"
            if callbacks := self._get_template_to_project_confirmation_callbacks():
                config["params"]["callback_data"] = {
                    "method": "template_to_project_confirmation_callback",
                    "args": [self.id, callbacks],
                }
            if warning_messages := self._get_template_to_project_warnings():
                config["params"]["message"] = self.env._(
                    "%(warning_messages)s\nAre you sure you want to continue?",
                    warning_messages="\n".join(warning_messages),
                )
            else:
                config["params"]["message"] = self.env._(
                    "This project is currently a template. Would you like to convert it back into a regular project?",
                )
        else:
            config["tag"] = "project_to_template_redirection_action"
        return {
            "type": "ir.actions.client",
            **config,
        }

    def create_template_from_project_undo_callback(self, callbacks):
        self.ensure_one()
        if callbacks.get("unarchive_project"):
            self.action_unarchive()

    def _get_template_from_project_undo_callbacks(self):
        self.ensure_one()
        callbacks = {}
        if self.active:
            self.action_archive()
            callbacks["unarchive_project"] = True
        return callbacks

    def action_create_template_from_project(self):
        self.ensure_one()
        template = self.copy(default={"is_template": True, "partner_id": False})
        template._toggle_template_mode(True)
        template.message_post(body=self.env._("Template created from %s.", self.name))
        config = {
            "tag": "project_template_show_notification",
            "params": {
                "project_id": template.id,
                "undo_method": "unlink",
            },
        }
        if callbacks := self._get_template_from_project_undo_callbacks():
            config["params"]["callback_data"] = {
                "method": "create_template_from_project_undo_callback",
                "args": [self.id, callbacks],
            }
        return {
            "type": "ir.actions.client",
            **config,
        }

    def action_undo_convert_to_template(self):
        self.ensure_one()
        self._toggle_template_mode(False)
        self.message_post(body=self.env._("Template converted back to regular project."))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": self.env._("Template converted back to regular project."),
                "next": {
                    "type": "ir.actions.client",
                    "tag": "soft_reload",
                },
            },
        }

    def _toggle_template_mode(self, is_template):
        self.ensure_one()
        self.is_template = is_template
        self.task_ids.write({"is_template": is_template})
        if not is_template:
            self.task_ids.role_ids = False

    @api.model
    def _get_template_default_context_whitelist(self):
        """
        Whitelist of fields that can be set through the `default_` context keys when creating a project from a template.
        """
        return []

    @api.model
    def _get_template_field_blacklist(self):
        """
        Blacklist of fields to not copy when creating a project from a template.
        """
        return [
            "partner_id",
        ]

    def action_create_from_template(self, values=None, role_to_users_mapping=None):
        self.ensure_one()
        values = values or {}
        default = {
            key.removeprefix('default_'): value
            for key, value in self.env.context.items()
            if key.startswith('default_') and key.removeprefix('default_') in self._get_template_default_context_whitelist()
        } | values
        project = self.with_context(copy_from_template=True).copy(default=default)
        project.message_post(body=self.env._("Project created from template %(name)s.", name=self.name))

        # Tasks dispatching using project roles
        project.task_ids.role_ids = False
        if role_to_users_mapping and (mapping := role_to_users_mapping.filtered(lambda entry: entry.user_ids)):
            for template_task, new_task in zip(self.task_ids, project.task_ids):
                for entry in mapping:
                    if entry.role_id in template_task.role_ids:
                        new_task.user_ids |= entry.user_ids
        return project
