# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re
import werkzeug.urls

from odoo import api, fields, models, tools


class MailMail(models.Model):
    """Add the mass mailing campaign data to mail"""
    _inherit = 'mail.mail'

    mailing_id = fields.Many2one('mailing.mailing', string='Mass Mailing')
    mailing_trace_ids = fields.One2many('mailing.trace', 'mail_mail_id', string='Statistics')

    def _get_tracking_url(self):
        token = self._generate_mail_recipient_token(self.id)
        return tools.urls.urljoin(
            self.get_base_url(),
            f'mail/track/{self.id}/{token}/blank.gif'
        )

    @api.model
    def _generate_mail_recipient_token(self, mail_id):
        return tools.hmac(self.env(su=True), 'mass_mailing-mail_mail-open', mail_id)

    def _prepare_outgoing_body(self):
        """ Override to add the tracking URL to the body and to add trace ID in
        shortened urls """
        self.ensure_one()
        # super() already cleans pseudo-void content from editor
        body = super()._prepare_outgoing_body()

        if body and self.mailing_id and self.mailing_trace_ids:
            Wrapper = body.__class__
            for match in set(re.findall(tools.mail.URL_REGEX, body)):
                href = match[0]
                url = match[1]

                parsed = werkzeug.urls.url_parse(url, scheme='http')

                if parsed.scheme.startswith('http') and parsed.path.startswith('/r/'):
                    new_href = href.replace(url, f"{url}/m/{self.mailing_trace_ids[0].id}")
                    body = body.replace(Wrapper(href), Wrapper(new_href))

            # generate tracking URL
            tracking_url = self._get_tracking_url()
            body = tools.mail.append_content_to_html(
                body,
                f'<img src="{tracking_url}"/>',
                plaintext=False,
            )
        return body

    def _prepare_outgoing_list(self, mail_server=False, doc_to_followers=None):
        """ Update mailing specific links to replace generic unsubscribe and
        view links by email-specific links. Also add headers to allow
        unsubscribe from email managers. """
        email_list = super()._prepare_outgoing_list(mail_server=mail_server, doc_to_followers=doc_to_followers)
        if not self.res_id or not self.mailing_id:
            return email_list

        base_url = self.mailing_id.get_base_url()
        for email_values in email_list:
            if not email_values['email_to']:
                continue

            # prepare links with normalize email
            email_normalized = tools.email_normalize(email_values['email_to'][0], strict=False)
            email_to = email_normalized or email_values['email_to'][0]

            unsubscribe_url = self.mailing_id._get_unsubscribe_url(email_to, self.res_id)
            unsubscribe_oneclick_url = self.mailing_id._get_unsubscribe_oneclick_url(email_to, self.res_id)
            view_url = self.mailing_id._get_view_url(email_to, self.res_id)

            # replace links in body
            if not tools.is_html_empty(email_values['body']):
                # replace generic link by recipient-specific one, except if we know
                # by advance it won't work (i.e. testing mailing scenario)
                if f'{base_url}/unsubscribe_from_list' in email_values['body'] and not self.env.context.get('mailing_test_mail'):
                    email_values['body'] = email_values['body'].replace(
                        f'{base_url}/unsubscribe_from_list',
                        unsubscribe_url,
                    )
                if f'{base_url}/view' in email_values['body']:
                    email_values['body'] = email_values['body'].replace(
                        f'{base_url}/view',
                        view_url,
                    )

            # add headers
            email_values['headers'].update({
                'List-Unsubscribe': f'<{unsubscribe_oneclick_url}>',
                'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
                'Precedence': 'list',
                'X-Auto-Response-Suppress': 'OOF',  # avoid out-of-office replies from MS Exchange
            })
        return email_list

    def _postprocess_sent_message(self, success_pids, failure_reason=False, failure_type=None):
        if failure_type:  # we consider that a recipient error is a failure with mass mailing and show them as failed
            self.filtered('mailing_id').mailing_trace_ids.set_failed(failure_type=failure_type)
        else:
            self.filtered('mailing_id').mailing_trace_ids.set_sent()
        return super()._postprocess_sent_message(success_pids, failure_reason=failure_reason, failure_type=failure_type)
