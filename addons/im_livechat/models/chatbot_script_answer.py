# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields
from odoo.fields import Domain

import textwrap


class ChatbotScriptAnswer(models.Model):
    _name = 'chatbot.script.answer'
    _description = 'Chatbot Script Answer'
    _order = 'script_step_id, sequence, id'

    name = fields.Char(string='Answer', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=1)
    redirect_link = fields.Char('Redirect Link',
        help="The visitor will be redirected to this link upon clicking the option "
             "(note that the script will end if the link is external to the livechat website).")
    script_step_id = fields.Many2one(
        'chatbot.script.step', string='Script Step', required=True, index=True, ondelete='cascade')
    chatbot_script_id = fields.Many2one(related='script_step_id.chatbot_script_id')

    @api.depends('script_step_id')
    @api.depends_context('chatbot_script_answer_display_short_name')
    def _compute_display_name(self):
        if self.env.context.get('chatbot_script_answer_display_short_name'):
            return super()._compute_display_name()

        for answer in self:
            if answer.script_step_id:
                answer_message = answer.script_step_id.message.replace('\n', ' ')
                shortened_message = textwrap.shorten(answer_message, width=26, placeholder=" [...]")
                answer.display_name = f"{shortened_message}: {answer.name}"
            else:
                answer.display_name = answer.name

    @api.model
    def _search_display_name(self, operator, value):
        """
        Search the records whose name or step message are matching the ``name`` pattern.
        The chatbot_script_id is also passed to the context through the custom widget
        ('chatbot_triggering_answers_widget') This allows to only see the question_answer
        from the same chatbot you're configuring.
        """
        domain = Domain.TRUE
        if value and operator == 'ilike':
            # search on both name OR step's message (combined with passed args)
            domain = Domain('name', operator, value) | Domain('script_step_id.message', operator, value)

        force_domain_chatbot_script_id = self.env.context.get('force_domain_chatbot_script_id')
        if force_domain_chatbot_script_id:
            domain &= Domain('chatbot_script_id', '=', force_domain_chatbot_script_id)

        return domain

    def _to_store_defaults(self, target):
        return ["name", "redirect_link"]
