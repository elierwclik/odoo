# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import logging
import uuid

from collections import defaultdict
from dateutil.relativedelta import relativedelta
from markupsafe import Markup

from odoo import api, fields, models, tools, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.fields import Domain
from odoo.tools import is_html_empty

_logger = logging.getLogger(__name__)


class SlideChannel(models.Model):
    """ A channel is a container of slides. """
    _name = 'slide.channel'
    _description = 'Course'
    _inherit = [
        'rating.mixin',
        'mail.activity.mixin',
        'image.mixin',
        'website.cover_properties.mixin',
        'website.seo.metadata',
        'website.published.multi.mixin',
        'website.searchable.mixin',
    ]
    _order = 'sequence, id'
    _partner_unfollow_enabled = True

    _CUSTOMER_HEADERS_LIMIT_COUNT = 0  # never use X-Msg-To headers

    def _default_cover_properties(self):
        """ Cover properties defaults are overridden to keep a consistent look for the slides
        channels headers across Odoo versions (pre-customization, with purple gradient fitting the
        homepage images, etc). Furthermore, as adding padding to the cover would not look great,
        its height is set to fit to content (snippet option to change this also disabled on the view)."""
        res = super()._default_cover_properties()
        res.update({
            "background_color_class": "o_cc3",
            'background_color_style': (
                'background-color: rgba(0, 0, 0, 0); '
                'background-image: linear-gradient(120deg, #875A7B, #78516F);'
            ),
            'opacity': '0',
            'resize_class': 'cover_auto'
        })
        return res

    def _default_access_token(self):
        return str(uuid.uuid4())

    def _get_default_enroll_msg(self):
        return _('Contact Responsible')

    # description
    name = fields.Char('Name', translate=True, required=True)
    active = fields.Boolean(default=True, tracking=100)
    description = fields.Html('Description', translate=True, sanitize_attributes=False, sanitize_form=False, help="The description that is displayed on top of the course page, just below the title")
    description_short = fields.Html('Short Description', translate=True, sanitize_attributes=False, sanitize_form=False, help="The description that is displayed on the course card")
    description_html = fields.Html('Detailed Description', translate=tools.html_translate, sanitize_attributes=False, sanitize_form=False)
    channel_type = fields.Selection([
        ('training', 'Training'), ('documentation', 'Documentation')],
        string="Course type", default="training", required=True)
    sequence = fields.Integer(default=10)
    user_id = fields.Many2one('res.users', string='Responsible', default=lambda self: self.env.uid)
    color = fields.Integer('Color Index', default=0, help='Used to decorate kanban view')
    tag_ids = fields.Many2many(
        'slide.channel.tag', 'slide_channel_tag_rel', 'channel_id', 'tag_id',
        string='Tags', help='Used to categorize and filter displayed channels/courses')
    # slides: promote, statistics
    slide_ids = fields.One2many('slide.slide', 'channel_id', string="Slides and categories", copy=True)
    slide_content_ids = fields.One2many('slide.slide', string='Content', compute="_compute_category_and_slide_ids")
    slide_category_ids = fields.One2many('slide.slide', string='Categories', compute="_compute_category_and_slide_ids")
    slide_last_update = fields.Date('Last Update', compute='_compute_slide_last_update', store=True)
    slide_partner_ids = fields.One2many(
        'slide.slide.partner', 'channel_id', string="Slide User Data",
        copy=False, groups='website_slides.group_website_slides_officer')
    promote_strategy = fields.Selection([
        ('latest', 'Latest Created'),
        ('most_voted', 'Most Voted'),
        ('most_viewed', 'Most Viewed'),
        ('specific', 'Select Manually'),
        ('none', 'None')],
        string="Featured Content", default='latest', required=False,
        help='Defines the content that will be promoted on the course home page',
        copy=False,
    )
    promoted_slide_id = fields.Many2one('slide.slide', string='Promoted Slide', copy=False)
    access_token = fields.Char("Security Token", copy=False, default=_default_access_token)
    nbr_document = fields.Integer('Documents', compute='_compute_slides_statistics', store=True)
    nbr_video = fields.Integer('Videos', compute='_compute_slides_statistics', store=True)
    nbr_infographic = fields.Integer('Infographics', compute='_compute_slides_statistics', store=True)
    nbr_article = fields.Integer("Articles", compute='_compute_slides_statistics', store=True)
    nbr_quiz = fields.Integer("Number of Quizs", compute='_compute_slides_statistics', store=True)
    total_slides = fields.Integer('Number of Contents', compute='_compute_slides_statistics', store=True)
    total_views = fields.Integer('Visits', compute='_compute_slides_statistics', store=True)
    total_votes = fields.Integer('Votes', compute='_compute_slides_statistics', store=True)
    total_time = fields.Float('Duration', compute='_compute_slides_statistics', digits=(10, 2), store=True)
    rating_avg_stars = fields.Float("Rating Average (Stars)", compute='_compute_rating_stats', digits=(16, 1), compute_sudo=True)
    # configuration
    allow_comment = fields.Boolean(
        "Allow rating on Course", default=True,
        help="Allow Attendees to like and comment your content and to submit reviews on your course.")
    publish_template_id = fields.Many2one(
        'mail.template', string='New Content Notification',
        help="Defines the email your Attendees will receive each time you upload new content.",
        default=lambda self: self.env['ir.model.data']._xmlid_to_res_id('website_slides.slide_template_published'),
        domain=[('model', '=', 'slide.slide')])
    share_channel_template_id = fields.Many2one(
        'mail.template', string='Channel Share Template',
        help='Email template used when sharing a channel',
        default=lambda self: self.env['ir.model.data']._xmlid_to_res_id('website_slides.mail_template_channel_shared'))
    share_slide_template_id = fields.Many2one(
        'mail.template', string='Share Template',
        help="Email template used when sharing a slide",
        default=lambda self: self.env['ir.model.data']._xmlid_to_res_id('website_slides.slide_template_shared'))
    completed_template_id = fields.Many2one(
        'mail.template', string='Completion Notification', help="Defines the email your Attendees will receive once they reach the end of your course.",
        default=lambda self: self.env['ir.model.data']._xmlid_to_res_id('website_slides.mail_template_channel_completed'),
        domain=[('model', '=', 'slide.channel.partner')])
    enroll = fields.Selection([
        ('public', 'Open'), ('invite', 'On Invitation')],
        compute='_compute_enroll', store=True, readonly=False,
        default='public', string='Enroll Policy', required=True,
        help='Defines how people can enroll to your Course.', copy=False)
    enroll_msg = fields.Html(
        'Enroll Message', help="Message explaining the enroll process",
        default=_get_default_enroll_msg, translate=tools.html_translate, sanitize_attributes=False)
    enroll_group_ids = fields.Many2many('res.groups', string='Auto Enroll Groups', help="Members of those groups are automatically added as members of the channel.")
    visibility = fields.Selection([
        ('public', 'Everyone'),
        ('connected', 'Signed In'),
        ('members', 'Course Attendees'),
        ('link', 'Anyone with the link'),
    ], default='public', string='Show Course To', required=True,
        help='Defines who can access your courses and their content.')
    upload_group_ids = fields.Many2many(
        'res.groups', 'rel_upload_groups', 'channel_id', 'group_id', string='Upload Groups',
        help="Group of users allowed to publish contents on a documentation course.")
    website_default_background_image_url = fields.Char('Background image URL', compute='_compute_website_default_background_image_url')
    # membership
    channel_partner_ids = fields.One2many(
        'slide.channel.partner', 'channel_id', string='Enrolled Attendees Information',
        groups='website_slides.group_website_slides_officer', domain=[('member_status', '!=', 'invited')])
    channel_partner_all_ids = fields.One2many(
        'slide.channel.partner', 'channel_id', string='All Attendees Information',
        groups='website_slides.group_website_slides_officer')
    members_count = fields.Integer('# Enrolled Attendees', compute='_compute_members_counts')
    members_all_count = fields.Integer('# Enrolled or Invited Attendees', compute='_compute_members_counts')
    members_engaged_count = fields.Integer(
        '# Active Attendees', help="Active attendees include both 'joined' and 'ongoing' attendees.",
        compute='_compute_members_counts')
    members_completed_count = fields.Integer('# Completed Attendees', compute='_compute_members_counts')
    members_invited_count = fields.Integer('# Invited Attendees', compute='_compute_members_counts')
    # partner_ids is implemented as compute/search instead of specifying the relation table
    # directly because we want to exclude active=False records on the joining table
    partner_ids = fields.Many2many(
        'res.partner', string='Attendees', help="Enrolled partners in the course",
        compute="_compute_partners", search="_search_partner_ids")
    # not stored access fields, depending on each user
    completed = fields.Boolean('Done', compute='_compute_user_statistics', compute_sudo=False)
    completion = fields.Integer('Completion', compute='_compute_user_statistics', compute_sudo=False)
    can_upload = fields.Boolean('Can Upload', compute='_compute_can_upload', compute_sudo=False)
    has_requested_access = fields.Boolean(string='Access Requested', compute='_compute_has_requested_access', compute_sudo=False)
    is_member = fields.Boolean(
        string='Is Enrolled Attendee', help='Is the attendee actively enrolled.',
        compute='_compute_membership_values', search="_search_is_member")
    is_member_invited = fields.Boolean(
        string='Is Invited Attendee', help='Is the invitation for this attendee pending.',
        compute='_compute_membership_values', search="_search_is_member_invited")
    is_visible = fields.Boolean(
        string='Is Visible On Website', compute='_compute_is_visible',
        search='_search_is_visible')
    partner_has_new_content = fields.Boolean(compute='_compute_partner_has_new_content', compute_sudo=False)
    # karma generation
    karma_gen_channel_rank = fields.Integer(string='Course ranked', default=5)
    karma_gen_channel_finish = fields.Integer(string='Course finished', default=10)
    # Karma based actions
    karma_review = fields.Integer('Add Review', default=10, help="Karma needed to add a review on the course")
    karma_slide_comment = fields.Integer('Add Comment', default=3, help="Karma needed to add a comment on a slide of this course")
    karma_slide_vote = fields.Integer('Vote', default=3, help="Karma needed to like/dislike a slide of this course.")
    can_review = fields.Boolean('Can Review', compute='_compute_action_rights', compute_sudo=False)
    can_comment = fields.Boolean('Can Comment', compute='_compute_action_rights', compute_sudo=False)
    can_vote = fields.Boolean('Can Vote', compute='_compute_action_rights', compute_sudo=False)
    # prerequisite settings
    prerequisite_channel_ids = fields.Many2many(
        'slide.channel', 'slide_channel_prerequisite_slide_channel_rel', 'channel_id', 'prerequisite_channel_id',
        string='Prerequisites', help='Prerequisite courses to complete before accessing this one.',
        domain="[('id', '!=', id), ('visibility', '=', visibility), ('website_published', '=', website_published)]")
    prerequisite_of_channel_ids = fields.Many2many(
        'slide.channel', 'slide_channel_prerequisite_slide_channel_rel', 'prerequisite_channel_id', 'channel_id',
        string='Prerequisite Of', help='Courses that have this course as prerequisite.')
    prerequisite_user_has_completed = fields.Boolean(
        'Has Completed Prerequisite', compute='_compute_prerequisite_user_has_completed')

    _check_enroll = models.Constraint(
        "CHECK(visibility != 'members' OR enroll = 'invite')",
        "The Enroll Policy should be set to 'On Invitation' when visibility is set to 'Course Attendees'",
    )

    @api.depends('visibility')
    def _compute_enroll(self):
        self.filtered(lambda channel: channel.visibility == 'members').enroll = 'invite'

    @api.depends('visibility', 'is_member')
    @api.depends_context('uid')
    def _compute_is_visible(self):
        for channel in self:
            channel.is_visible = (
                channel.visibility == 'public'
                or channel.is_member
                or (not self.env.user._is_public() and channel.visibility == 'connected')
            )

    @api.model
    def _search_is_visible(self, operator, value):
        if operator != 'in':
            return NotImplemented
        return [
            '|', ('is_member', '=', True),
            ('visibility', 'in', ['public'] if self.env.user._is_public() else ['public', 'connected']),
        ]

    @api.depends('channel_partner_all_ids', 'channel_partner_all_ids.member_status', 'channel_partner_all_ids.active')
    def _compute_partners(self):
        data = {
            slide_channel: partner_ids
            for slide_channel, partner_ids in self.env['slide.channel.partner'].sudo()._read_group(
                [('channel_id', 'in', self.ids), ('member_status', '!=', 'invited')],
                ['channel_id'],
                aggregates=['partner_id:array_agg']
            )
        }
        for slide_channel in self:
            slide_channel.partner_ids = data.get(slide_channel, [])

    def _search_partner_ids(self, operator, value):
        return [(
            'channel_partner_ids', 'in', self.env['slide.channel.partner'].sudo()._search(
                [('partner_id', operator, value),
                 ('active', '=', True),
                 ('member_status', '!=', 'invited')],
            )
        )]

    @api.depends('slide_ids.is_published')
    def _compute_slide_last_update(self):
        for record in self:
            record.slide_last_update = fields.Date.today()

    @api.depends('channel_partner_all_ids.channel_id', 'channel_partner_all_ids.member_status')
    def _compute_members_counts(self):
        read_group_res = self.env['slide.channel.partner'].sudo()._read_group(
            domain=[('channel_id', 'in', self.ids)],
            groupby=['channel_id', 'member_status'],
            aggregates=['__count']
        )
        data = {(channel.id, member_status): count for channel, member_status, count in read_group_res}
        for channel in self:
            channel.members_invited_count = data.get((channel.id, 'invited'), 0)
            channel.members_engaged_count = data.get((channel.id, 'joined'), 0) + data.get((channel.id, 'ongoing'), 0)
            channel.members_completed_count = data.get((channel.id, 'completed'), 0)
            channel.members_all_count = channel.members_invited_count + channel.members_engaged_count + channel.members_completed_count
            channel.members_count = channel.members_engaged_count + channel.members_completed_count

    @api.depends('activity_ids.request_partner_id')
    @api.depends_context('uid')
    @api.model
    def _compute_has_requested_access(self):
        requested_cids = self.sudo().activity_search(
            ['mail.mail_activity_data_todo'],
            additional_domain=[('request_partner_id', '=', self.env.user.partner_id.id)],
            only_automated=False,
        ).mapped('res_id')
        for channel in self:
            channel.has_requested_access = channel.id in requested_cids

    @api.depends('channel_partner_all_ids.partner_id', 'channel_partner_all_ids.member_status', 'channel_partner_all_ids.active')
    @api.depends_context('uid')
    def _compute_membership_values(self):
        if self.env.user._is_public():
            self.is_member = False
            self.is_member_invited = False
            return
        data = {
            member_status: channel_ids
            for member_status, channel_ids in self.env['slide.channel.partner'].sudo()._read_group(
                [('partner_id', '=', self.env.user.partner_id.id), ('channel_id', 'in', self.ids), ('active', '=', True)],
                ['member_status'], ['channel_id:array_agg']
            )
        }
        active_channels_ids = data.get('joined', []) + data.get('ongoing', []) + data.get('completed', [])
        invitation_pending_channels_ids = data.get('invited', [])
        for channel in self:
            channel.is_member = channel.id in active_channels_ids
            channel.is_member_invited = channel.id in invitation_pending_channels_ids

    def _search_is_member(self, operator, value):
        if operator != 'in':
            return NotImplemented
        return [('id', 'in', self._search_is_member_channel_ids())]

    def _search_is_member_invited(self, operator, value):
        if operator != 'in':
            return NotImplemented
        return [('id', 'in', self._search_is_member_channel_ids(invited=True))]

    def _search_is_member_channel_ids(self, invited=False):
        return self.env['slide.channel.partner'].sudo()._read_group(
            [('partner_id', '=', self.env.user.partner_id.id), ('member_status', '=' if invited else '!=', 'invited'), ('active', '=', True)],
            aggregates=['channel_id:array_agg']
        )[0][0]

    @api.depends('slide_ids.is_category')
    def _compute_category_and_slide_ids(self):
        for channel in self:
            channel.slide_category_ids = channel.slide_ids.filtered(lambda slide: slide.is_category)
            channel.slide_content_ids = channel.slide_ids - channel.slide_category_ids

    @api.depends('slide_ids.slide_category', 'slide_ids.is_published', 'slide_ids.completion_time',
                 'slide_ids.likes', 'slide_ids.dislikes', 'slide_ids.total_views', 'slide_ids.is_category', 'slide_ids.active')
    def _compute_slides_statistics(self):
        default_vals = dict(total_views=0, total_votes=0, total_time=0, total_slides=0)
        keys = ['nbr_%s' % slide_category for slide_category in self.env['slide.slide']._fields['slide_category'].get_values(self.env)]
        default_vals.update(dict((key, 0) for key in keys))

        result = dict((cid, dict(default_vals)) for cid in self.ids)
        read_group_res = self.env['slide.slide']._read_group(
            [('active', '=', True), ('is_published', '=', True), ('channel_id', 'in', self.ids), ('is_category', '=', False)],
            ['channel_id', 'slide_category'],
            aggregates=['__count', 'likes:sum', 'dislikes:sum', 'total_views:sum', 'completion_time:sum'])
        for channel, slide_category, count, likes_sum, dislikes_sum, total_views_sum, completion_time_sum in read_group_res:
            channel_dict = result[channel.id]
            channel_dict['total_votes'] += likes_sum
            channel_dict['total_votes'] -= dislikes_sum
            channel_dict['total_views'] += total_views_sum
            channel_dict['total_time'] += completion_time_sum
            if slide_category:
                channel_dict[f'nbr_{slide_category}'] = count
                channel_dict['total_slides'] += count

        for record in self:
            record.update(result.get(record.id, default_vals))

    def _compute_rating_stats(self):
        super()._compute_rating_stats()
        for record in self:
            record.rating_avg_stars = record.rating_avg

    @api.depends('slide_partner_ids', 'slide_partner_ids.completed', 'total_slides')
    @api.depends_context('uid')
    def _compute_user_statistics(self):
        current_user_info = self.env['slide.channel.partner'].sudo().search(
            [('channel_id', 'in', self.ids), ('partner_id', '=', self.env.user.partner_id.id)]
        )
        mapped_data = dict((info.channel_id.id, (info.member_status == 'completed', info.completed_slides_count)) for info in current_user_info)
        for record in self:
            completed, completed_slides_count = mapped_data.get(record.id, (False, 0))
            record.completed = completed
            record.completion = 100.0 if completed else round(100.0 * completed_slides_count / (record.total_slides or 1))

    @api.depends('upload_group_ids', 'user_id')
    @api.depends_context('uid')
    def _compute_can_upload(self):
        for record in self:
            if record.user_id == self.env.user:
                record.can_upload = True
            elif record.upload_group_ids:
                record.can_upload = bool(record.upload_group_ids & self.env.user.group_ids)
            else:
                record.can_upload = self.env.user.has_group('website_slides.group_website_slides_manager')

    @api.depends('channel_type', 'user_id', 'can_upload')
    @api.depends_context('uid')
    def _compute_can_publish(self):
        """ For channels of type 'training', only the responsible (see user_id field) can publish slides.
        The 'sudo' user needs to be handled because they are the one used for uploads done on the front-end when the
        logged in user is not publisher but fulfills the upload_group_ids condition. Invited attendees can
        preview the course as public and sudo. Prevent them from uploading."""
        for record in self:
            if not record.can_upload:
                record.can_publish = False
            elif record.user_id == self.env.user:
                record.can_publish = True
            else:
                record.can_publish = self.env.user.has_group('website_slides.group_website_slides_manager')

    @api.model
    def _get_can_publish_error_message(self):
        return _("Publishing is restricted to the responsible of training courses or members of the publisher group for documentation courses")

    @api.depends('slide_partner_ids')
    @api.depends_context('uid')
    def _compute_partner_has_new_content(self):
        new_published_slides = self.env['slide.slide'].sudo().search([
            ('is_published', '=', True),
            ('date_published', '>', fields.Datetime.now() - relativedelta(days=7)),
            ('channel_id', 'in', self.ids),
            ('is_category', '=', False)
        ])
        slide_partner_completed = self.env['slide.slide.partner'].sudo().search([
            ('channel_id', 'in', self.ids),
            ('partner_id', '=', self.env.user.partner_id.id),
            ('slide_id', 'in', new_published_slides.ids),
            ('completed', '=', True)
        ]).mapped('slide_id')
        for channel in self:
            new_slides = new_published_slides.filtered(lambda slide: slide.channel_id == channel)
            channel.partner_has_new_content = any(slide not in slide_partner_completed for slide in new_slides)

    @api.depends('channel_type')
    def _compute_website_default_background_image_url(self):
        for channel in self:
            channel.website_default_background_image_url = f'website_slides/static/src/img/channel-{channel.channel_type}-default.jpg'

    @api.depends('name')
    def _compute_website_url(self):
        super()._compute_website_url()
        for channel in self:
            if channel.id:  # avoid to perform a slug on a not yet saved record in case of an onchange.
                channel.website_url = f"/slides/{self.env['ir.http']._slug(channel)}"

    @api.depends('website_id.domain')
    def _compute_website_absolute_url(self):
        super()._compute_website_absolute_url()

    @api.depends('can_publish', 'is_member', 'karma_review', 'karma_slide_comment', 'karma_slide_vote')
    @api.depends_context('uid')
    def _compute_action_rights(self):
        user_karma = self.env.user.karma
        for channel in self:
            if channel.can_publish:
                channel.can_vote = channel.can_comment = channel.can_review = True
            elif not channel.is_member:
                channel.can_vote = channel.can_comment = channel.can_review = False
            else:
                channel.can_review = user_karma >= channel.karma_review
                channel.can_comment = user_karma >= channel.karma_slide_comment
                channel.can_vote = user_karma >= channel.karma_slide_vote

    ######################
    # Prerequisite Compute
    ######################

    @api.depends('prerequisite_channel_ids', 'channel_partner_ids.member_status')
    @api.depends_context('uid')
    def _compute_prerequisite_user_has_completed(self):
        completed_prerequisite_channels = self.env['slide.channel.partner'].sudo().search([
            ('partner_id', '=', self.env.user.partner_id.id),
            ('channel_id', 'in', self.prerequisite_channel_ids.ids),
            ('member_status', '=', 'completed'),
        ]).mapped('channel_id')
        for channel in self:
            channel.prerequisite_user_has_completed = all(
                channel in completed_prerequisite_channels for channel in channel.prerequisite_channel_ids)

    # ---------------------------------------------------------
    # ORM Overrides
    # ---------------------------------------------------------

    def _init_column(self, column_name):
        """ Initialize the value of the given column for existing rows.
            Overridden here because we need to generate different access tokens
            and by default _init_column calls the default method once and applies
            it for every record.
        """
        if column_name != 'access_token':
            super()._init_column(column_name)
        else:
            query = """
                UPDATE %(table_name)s
                SET access_token = md5(md5(random()::varchar || id::varchar) || clock_timestamp()::varchar)::uuid::varchar
                WHERE access_token IS NULL
            """ % {'table_name': self._table}
            self.env.cr.execute(query)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Ensure creator is member of its channel it is easier for them to manage it (unless it is odoobot)
            if not vals.get('channel_partner_ids') and not self.env.is_superuser():
                vals['channel_partner_ids'] = [(0, 0, {
                    'partner_id': self.env.user.partner_id.id
                })]
            if not is_html_empty(vals.get('description')) and is_html_empty(vals.get('description_short')):
                vals['description_short'] = vals['description']

        channels = super(SlideChannel, self.with_context(mail_create_nosubscribe=True)).create(vals_list)

        for channel in channels:
            if channel.user_id:
                channel._action_add_members(channel.user_id.partner_id)
            if channel.enroll_group_ids:
                channel._add_groups_members()

        return channels

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        for channel, vals in zip(self, vals_list):
            if 'name' not in default:
                vals['name'] = f"{channel.name} ({_('copy')})"
            if 'enroll' not in default and channel.visibility == "members":
                vals['enroll'] = 'invite'
        return vals_list

    def write(self, vals):
        # If description_short wasn't manually modified, there is an implicit link between this field and description.
        if not is_html_empty(vals.get('description')) and is_html_empty(vals.get('description_short')) and self.description == self.description_short:
            vals['description_short'] = vals.get('description')

        res = super().write(vals)

        if vals.get('user_id'):
            self._action_add_members(self.env['res.users'].sudo().browse(vals['user_id']).partner_id)
            self.activity_reschedule(
                ['mail_activity_data_todo'],
                new_user_id=vals.get('user_id'),
            )
        if 'enroll_group_ids' in vals:
            self._add_groups_members()

        return res

    def unlink(self):
        """" Necessary override to avoid cache issues in the ORM.
        This signals the ORM to remove slides first to avoid having the SQL cascade the deletion,
        which attempts to recompute slide statistics of removed slides and creates a cache failure.

        Indeed, slides statistics are computed using a read_group which will try to flush the records
        first and fail with a "Could not find all values of slide.slide.category_id to flush them".
        (Fix suggested by the ORM team).

        (See '_compute_slides_statistics' and '_compute_category_completion_time'). """

        self.slide_ids.unlink()
        return super().unlink()

    def action_archive(self):
        """ Archiving a channel does it on its slides, too.

        We want to be archiving the channel FIRST.
        So that when slides are archived and the recompute is triggered,
        it does not try to mark the channel as "completed".
        That happens because it counts slide_done / slide_total, but slide_total
        will be 0 since all the slides for the course have been archived as well.
        """
        archived = self.filtered(self._active_name)
        res = super().action_archive()
        archived.is_published = False
        archived.slide_ids.action_archive()
        return res

    def action_unarchive(self):
        """ Unarchiving a channel does it on its slides, too.

        We want to archive the channel LAST.
        So that when it recomputes stats for the channel and completion, it correctly
        counts the slides_total by counting slides that are already un-archived.
        """
        to_activate = self.filtered(lambda channel: not channel.active)
        to_activate.with_context(active_test=False).slide_ids.action_unarchive()
        return super(SlideChannel, to_activate).action_unarchive()

    # ---------------------------------------------------------
    # Mail Thread
    # ---------------------------------------------------------

    def message_post(self, *, parent_id=False, subtype_id=False, **kwargs):
        """ Temporary workaround to avoid spam. If someone replies on a channel
        through the 'Presentation Published' email, it should be considered as a
        note as we don't want all channel followers to be notified of this answer.
        Also make sure that only one review can be posted per course."""
        self.ensure_one()
        if kwargs.get('message_type') == 'comment' and not self.can_review:
            raise AccessError(_('Not enough karma to review'))
        if parent_id:
            parent_message = self.env['mail.message'].sudo().browse(parent_id)
            if parent_message.subtype_id and parent_message.subtype_id == self.env.ref('website_slides.mt_channel_slide_published'):
                subtype_id = self.env.ref('mail.mt_note').id
        message = super().message_post(parent_id=parent_id, subtype_id=subtype_id, **kwargs)
        if self.env.user._is_internal() and not message.rating_value:
            return message
        if message.subtype_id == self.env.ref("mail.mt_comment"):
            domain = [
                ("res_id", "=", self.id),
                ("author_id", "=", message.author_id.id),
                ("model", "=", "slide.channel"),
                ("subtype_id", "=", self.env.ref("mail.mt_comment").id),
            ]
            if self.env["mail.message"].search_count(domain, limit=2) > 1:
                raise ValidationError(_("Only a single review can be posted per course."))
        if message.rating_value and message.is_current_user_or_guest_author:
            self.env.user._add_karma(self.karma_gen_channel_rank, self, _("Course Ranked"))
        return message

    def _mail_get_partner_fields(self, introspect_fields=False):
        return []

    # ---------------------------------------------------------
    # Business / Actions
    # ---------------------------------------------------------

    def action_redirect_to_members(self, status_filter=''):
        """ Redirects to attendees of the course. If status_filter is set to 'invited' /
        'engaged' ('joined' + 'ongoing') / 'completed', attendees are filtered accordingly."""
        action_ctx = {}
        action = self.env["ir.actions.actions"]._for_xml_id("website_slides.slide_channel_partner_action")
        if status_filter == 'engaged':
            action_ctx['search_default_filter_joined'] = 1
            action_ctx['search_default_filter_ongoing'] = 1
        elif status_filter:
            action_ctx[f'search_default_filter_{status_filter}'] = 1
        action['domain'] = [('channel_id', 'in', self.ids)]
        action['sample'] = 1
        if status_filter == 'completed':
            help_message = {
                'header_message': _("No Attendee has completed this course yet!"),
                'body_message': ""
            }
        else:
            help_message = {
                'header_message': _("No Attendees Yet!"),
                'body_message': _("From here you'll be able to monitor attendees and to track their progress.")
            }
        action['help'] = Markup("""<p class="o_view_nocontent_smiling_face">%(header_message)s</p><p>%(body_message)s</p>""") % help_message
        if len(self) == 1:
            action['display_name'] = _('Attendees of %s', self.name)
            action_ctx['default_channel_id'] = self.id
        action['context'] = action_ctx
        return action

    def action_redirect_to_engaged_members(self):
        return self.action_redirect_to_members('engaged')

    def action_redirect_to_completed_members(self):
        return self.action_redirect_to_members('completed')

    def action_redirect_to_invited_members(self):
        return self.action_redirect_to_members('invited')

    def action_channel_enroll(self):
        template = self.env.ref('website_slides.mail_template_slide_channel_enroll', raise_if_not_found=False)
        return self._action_channel_open_invite_wizard(template, enroll_mode=True)

    def action_channel_invite(self):
        template = self.env.ref('website_slides.mail_template_slide_channel_invite', raise_if_not_found=False)
        return self._action_channel_open_invite_wizard(template)

    def _action_channel_open_invite_wizard(self, mail_template, enroll_mode=False):
        """ Open the invitation wizard to invite and add attendees to the course(s) in self.

        :param mail_template: mail.template used in the invite wizard.
        :param enroll_mode: true if we want to enroll the attendees invited through the wizard.
            False otherwise, adding them as 'invited', e.g. when using "Invite" action."""
        course_name = self.name if len(self) == 1 else ''
        local_context = dict(
            self.env.context,
            default_channel_id=self.id if len(self) == 1 else False,
            default_email_layout_xmlid='website_slides.mail_notification_channel_invite',
            default_enroll_mode=enroll_mode,
            default_template_id=mail_template and mail_template.id or False,
            default_use_template=bool(mail_template),
        )
        if enroll_mode:
            name = _('Enroll Attendees to %(course_name)s', course_name=course_name or _('a course'))
        else:
            name = _('Invite Attendees to %(course_name)s', course_name=course_name or _('a course'))

        return {
            'type': 'ir.actions.act_window',
            'views': [[False, 'form']],
            'res_model': 'slide.channel.invite',
            'target': 'new',
            'context': local_context,
            'name': name,
        }

    def _action_add_members(self, target_partners, member_status='joined', raise_on_access=False):
        """ Adds the target_partners as attendees of the channel(s).
            Partners are added as follows, depending on the value of member_status:
            1) (Default) 'joined'. The partners will be added as enrolled attendees. This will make the content
                (slides) of the channel available to that partner. This can also happen when an invited attendee
                enrolls themself. The attendees are also subscribed to the chatter of the channel.
                :return: the union of previous partners re-enrolling, new attendees and invited ones enrolling.
            2) 'invited' : This is used when inviting partners. The partners are added as invited attendees
                This will make the channel accessible but not the slides until they enroll themselves.
                :return: returns the union of new records and the ones unarchived.
        """
        SlideChannelPartnerSudo = self.env['slide.channel.partner'].sudo()
        allowed_channels = self._filter_add_members(raise_on_access=raise_on_access)
        if not allowed_channels or not target_partners:
            return SlideChannelPartnerSudo

        existing_channel_partners = self.env['slide.channel.partner'].with_context(active_test=False).sudo().search([
            ('channel_id', 'in', allowed_channels.ids),
            ('partner_id', 'in', target_partners.ids)
        ])

        # Unarchive existing channel partners, recomputing their completion and updating member_status
        archived_channel_partners = existing_channel_partners.filtered(lambda channel_partner: not channel_partner.active)
        to_unarchived = SlideChannelPartnerSudo
        if archived_channel_partners:
            archived_channel_partners.action_unarchive()
            to_unarchived = archived_channel_partners
            # Update member_status (and completion if enrolling)
            to_unarchived.member_status = member_status
            if member_status == 'joined':
                to_unarchived._recompute_completion()

        existing_channel_partners_map = defaultdict(lambda: self.env['slide.channel.partner'])
        for channel_partner in existing_channel_partners:
            existing_channel_partners_map[channel_partner.channel_id] += channel_partner

        # Invited partners confirming their invitation by enrolling, or upgraded to 'joined'.
        to_update_as_joined = SlideChannelPartnerSudo
        to_create_channel_partners_values = []

        for channel in allowed_channels:
            channel_partners = existing_channel_partners_map[channel]
            if member_status == 'joined':
                to_update_as_joined += channel_partners.filtered(lambda cp: cp.member_status == 'invited')
            for partner in target_partners - channel_partners.partner_id:
                to_create_channel_partners_values.append(dict(channel_id=channel.id, partner_id=partner.id, member_status=member_status))

        new_slide_channel_partners = SlideChannelPartnerSudo.create(to_create_channel_partners_values)
        to_update_as_joined.member_status = 'joined'
        to_update_as_joined._recompute_completion()

        # All fragments are in sudo.
        result_channel_partners = to_unarchived + to_update_as_joined + new_slide_channel_partners

        # Subscribe partners joining the course to the chatter.
        if member_status == 'joined':
            result_channel_partners_map = defaultdict(list)
            for channel_partner in result_channel_partners:
                result_channel_partners_map[channel_partner.channel_id].append(channel_partner.partner_id.id)
            for channel, partner_ids in result_channel_partners_map.items():
                channel.message_subscribe(
                    partner_ids=partner_ids,
                    subtype_ids=[self.env.ref('website_slides.mt_channel_slide_published').id]
                )
        return result_channel_partners

    def _filter_add_members(self, raise_on_access=False):
        allowed = self.filtered(lambda channel: channel.enroll == 'public')
        if controlled_access := (self - allowed):
            allowed += controlled_access._filtered_access('write')
            if raise_on_access and allowed != self:
                raise AccessError(_('You are not allowed to add members to this course. '
                                    'Please contact the course responsible or an administrator.'))
        return allowed

    def _add_groups_members(self):
        for channel in self:
            channel._action_add_members(channel.mapped('enroll_group_ids.all_user_ids.partner_id'))

    def _get_earned_karma(self, partner_ids):
        """ Compute the number of karma earned by partners on a channel
        Warning: this count will not be accurate if the configuration has been
        modified after the completion of a course!
        """
        total_karma = defaultdict(list)

        slide_completed = self.env['slide.slide.partner'].sudo().search([
            ('partner_id', 'in', partner_ids),
            ('channel_id', 'in', self.ids),
            ('completed', '=', True),
            ('quiz_attempts_count', '>', 0)
        ])
        for partner_slide in slide_completed:
            slide = partner_slide.slide_id
            if not slide.question_ids:
                continue
            gains = [
                slide.quiz_first_attempt_reward,
                slide.quiz_second_attempt_reward,
                slide.quiz_third_attempt_reward,
                slide.quiz_fourth_attempt_reward,
            ]
            attempts = min(partner_slide.quiz_attempts_count, len(gains))
            total_karma[partner_slide.partner_id.id].append({
                'karma': gains[attempts - 1],
                'channel_id': slide.channel_id,
            })

        channel_completed = self.env['slide.channel.partner'].sudo().search([
            ('partner_id', 'in', partner_ids),
            ('channel_id', 'in', self.ids),
            ('member_status', '=', 'completed')
        ])
        for partner_channel in channel_completed:
            channel = partner_channel.channel_id
            total_karma[partner_channel.partner_id.id].append({
                'karma': channel.karma_gen_channel_finish,
                'channel_id': channel,
            })

        return total_karma

    def _remove_membership(self, partner_ids):
        """ Karma earned during course progress is kept upon membership removal.
        This is done because re-joining the course will not allow you to gain the karma again,
        as we keep your progress """
        if not partner_ids:
            raise ValueError("Do not use this method with an empty partner_id recordset")

        removed_channel_partner_domain = Domain.OR(
            Domain('partner_id', 'in', partner_ids)
            & Domain('channel_id', '=', channel.id)
            for channel in self
        )

        self.message_unsubscribe(partner_ids=partner_ids)
        if self:
            removed_channel_partner = self.env['slide.channel.partner'].sudo().search(removed_channel_partner_domain)
            if removed_channel_partner:
                removed_channel_partner.action_archive()

    def _send_share_email(self, emails):
        """ Share channel through emails."""
        courses_without_templates = self.filtered(lambda channel: not channel.share_channel_template_id)
        if courses_without_templates:
            raise UserError(_('Impossible to send emails. Select a "Channel Share Template" for courses %(course_names)s first',
                                 course_names=', '.join(courses_without_templates.mapped('name'))))
        mail_ids = []
        for record in self:
            template = record.share_channel_template_id.with_context(
                user=self.env.user,
                email=emails,
                base_url=record.get_base_url(),
            )
            email_values = {'email_to': emails}
            if self.env.user._is_portal():
                template = template.sudo()
                email_values['email_from'] = self.env.company.catchall_formatted or self.env.company.email_formatted

            mail_ids.append(template.send_mail(record.id, email_layout_xmlid='mail.mail_notification_light', email_values=email_values))
        return mail_ids

    def action_view_slides(self):
        action = self.env["ir.actions.actions"]._for_xml_id("website_slides.slide_slide_action")
        action['context'] = {
            'search_default_published': 1,
            'default_channel_id': self.id
        }
        action['domain'] = [('channel_id', "=", self.id), ('is_category', '=', False)]
        return action

    def action_view_ratings(self):
        action = self.env["ir.actions.actions"]._for_xml_id("website_slides.rating_rating_action_slide_channel")
        action['name'] = _('Rating of %s', self.name)
        action['domain'] = Domain.AND([ast.literal_eval(action.get('domain', '[]')), Domain('res_id', 'in', self.ids)])
        return action

    def action_request_access(self):
        """ Request access to the channel. Returns a dict with keys being either 'error'
        (specific error raised) or 'done' (request done or not). """
        if self.env.user._is_public():
            return {'error': _('You have to sign in before')}
        if not self.is_published:
            return {'error': _('Course not published yet')}
        if self.is_member:
            return {'error': _('Already member')}
        if self.enroll == 'invite':
            activities = self.sudo()._action_request_access(self.env.user.partner_id)
            if activities:
                return {'done': True}
            return {'error': _('Already Requested')}
        return {'done': False}

    def action_grant_access(self, partner_id):
        partner = self.env['res.partner'].browse(partner_id).exists()
        if partner:
            if self._action_add_members(partner):
                self.activity_search(
                    ['mail.mail_activity_data_todo'],
                    user_id=self.user_id.id, additional_domain=[('request_partner_id', '=', partner.id)],
                    only_automated=False,
                ).action_feedback(feedback=_('Access Granted'))

    def action_refuse_access(self, partner_id):
        partner = self.env['res.partner'].browse(partner_id).exists()
        if partner:
            self.activity_search(
                ['mail.mail_activity_data_todo'],
                user_id=self.user_id.id, additional_domain=[('request_partner_id', '=', partner.id)],
                only_automated=False,
            ).action_feedback(feedback=_('Access Refused'))

    # ---------------------------------------------------------
    # Mailing Mixin API
    # ---------------------------------------------------------

    def _rating_domain(self):
        """ Only take the published rating into account to compute avg and count """
        return super()._rating_domain() & Domain('is_internal', '=', False)

    def _action_request_access(self, partner):
        activities = self.env['mail.activity']
        requested_cids = self.sudo().activity_search(
            ['mail.mail_activity_data_todo'],
            additional_domain=[('request_partner_id', '=', partner.id)],
        ).mapped('res_id')
        for channel in self:
            if channel.id not in requested_cids and channel.user_id:
                activities += channel.activity_schedule(
                    'mail.mail_activity_data_todo',
                    note=_('<b>%s</b> is requesting access to this course.', partner.name),
                    summary=_('Access Request'),
                    user_id=channel.user_id.id,
                    request_partner_id=partner.id
                )
        return activities

    # ---------------------------------------------------------
    # Data / Misc
    # ---------------------------------------------------------

    def _get_categorized_slides(self, base_domain, order, force_void=True, limit=False, offset=False):
        """ Return an ordered structure of slides by categories within a given
        base_domain that must fulfill slides. As a course structure is based on
        its slides sequences, uncategorized slides must have the lowest sequences.

        Example
          * category 1 (sequence 1), category 2 (sequence 3)
          * slide 1 (sequence 0), slide 2 (sequence 2)
          * course structure is: slide 1, category 1, slide 2, category 2
            * slide 1 is uncategorized,
            * category 1 has one slide : Slide 2
            * category 2 is empty.

        Backend and frontend ordering is the same, uncategorized first. It
        eases resequencing based on DOM / displayed order, notably when
        drag n drop is involved. """
        self.ensure_one()
        all_categories = self.env['slide.slide'].sudo().search([('channel_id', '=', self.id), ('is_category', '=', True)])
        all_slides = self.env['slide.slide'].sudo().search(base_domain, order=order)
        category_data = []

        # Prepare all categories by natural order
        for category in all_categories:
            category_slides = all_slides.filtered(lambda slide: slide.category_id == category)
            if not category_slides and not force_void:
                continue
            category_data.append({
                'category': category, 'id': category.id,
                'name': category.name, 'slug_name': self.env['ir.http']._slug(category),
                'total_slides': len(category_slides),
                'slides': category_slides[(offset or 0):(limit + offset or len(category_slides))],
            })

        # Add uncategorized slides in first position
        uncategorized_slides = all_slides.filtered(lambda slide: not slide.category_id)
        if uncategorized_slides or force_void:
            category_data.insert(0, {
                'category': False, 'id': False,
                'name': _('Uncategorized'), 'slug_name': _('Uncategorized'),
                'total_slides': len(uncategorized_slides),
                'slides': uncategorized_slides[(offset or 0):(offset + limit or len(uncategorized_slides))],
            })

        return category_data

    def _move_category_slides(self, category, new_category):
        if not category.slide_ids:
            return
        truncated_slide_ids = [slide_id for slide_id in self.slide_ids.ids if slide_id not in category.slide_ids.ids]
        if new_category:
            place_idx = truncated_slide_ids.index(new_category.id)
            ordered_slide_ids = truncated_slide_ids[:place_idx] + category.slide_ids.ids + truncated_slide_ids[place_idx]
        else:
            ordered_slide_ids = category.slide_ids.ids + truncated_slide_ids
        for index, slide_id in enumerate(ordered_slide_ids):
            self.env['slide.slide'].browse([slide_id]).sequence = index + 1

    def _resequence_slides(self, slide, force_category=False):
        ids_to_resequence = self.slide_ids.ids
        index_of_added_slide = ids_to_resequence.index(slide.id)
        next_category_id = None
        if self.slide_category_ids:
            force_category_id = force_category.id if force_category else slide.category_id.id
            index_of_category = self.slide_category_ids.ids.index(force_category_id) if force_category_id else None
            if index_of_category is None:
                next_category_id = self.slide_category_ids.ids[0]
            elif index_of_category < len(self.slide_category_ids.ids) - 1:
                next_category_id = self.slide_category_ids.ids[index_of_category + 1]

        if next_category_id:
            added_slide_id = ids_to_resequence.pop(index_of_added_slide)
            index_of_next_category = ids_to_resequence.index(next_category_id)
            ids_to_resequence.insert(index_of_next_category, added_slide_id)
            for i, record in enumerate(self.env['slide.slide'].browse(ids_to_resequence)):
                record.write({'sequence': i + 1})  # start at 1 to make people scream
        else:
            slide.write({
                'sequence': self.env['slide.slide'].browse(ids_to_resequence[-1]).sequence + 1
            })

    def get_backend_menu_id(self):
        return self.env.ref('website_slides.website_slides_menu_root').id

    @api.model
    def _search_get_detail(self, website, order, options):
        with_description = options['displayDescription']
        with_date = options['displayDetail']
        my = options.get('my')
        search_tags = options.get('tag')
        slide_category = options.get('slide_category')
        domain = [website.website_domain(), [('is_visible', '=', True)]]
        if my:
            domain.append([('is_member', '=', True)])
        if search_tags:
            ChannelTag = self.env['slide.channel.tag']
            try:
                tag_ids = list(filter(None, [self.env['ir.http']._unslug(tag)[1] for tag in search_tags.split(',')]))
                tags = ChannelTag.search([('id', 'in', tag_ids)]) if tag_ids else ChannelTag
            except Exception:
                tags = ChannelTag
            # Group by group_id
            # OR inside a group, AND between groups.
            for tags_ in tags.grouped('group_id').values():
                domain.append([('tag_ids', 'in', tags_.ids)])
        if slide_category and 'nbr_%s' % slide_category in self:
            domain.append([('nbr_%s' % slide_category, '>', 0)])
        search_fields = ['name']
        fetch_fields = ['name', 'website_url']
        mapping = {
            'name': {'name': 'name', 'type': 'text', 'match': True},
            'website_url': {'name': 'website_url', 'type': 'text', 'truncate': False},
        }
        if with_description:
            search_fields.append('description_short')
            fetch_fields.append('description_short')
            mapping['description'] = {'name': 'description_short', 'type': 'text', 'html': True, 'match': True}
        if with_date:
            fetch_fields.append('slide_last_update')
            mapping['detail'] = {'name': 'slide_last_update', 'type': 'date'}
        return {
            'model': 'slide.channel',
            'base_domain': domain,
            'search_fields': search_fields,
            'fetch_fields': fetch_fields,
            'mapping': mapping,
            'icon': 'fa-graduation-cap',
        }

    def _get_placeholder_filename(self, field):
        image_fields = ['image_%s' % size for size in [1920, 1024, 512, 256, 128]]
        if field in image_fields:
            return self.website_default_background_image_url
        return super()._get_placeholder_filename(field)
