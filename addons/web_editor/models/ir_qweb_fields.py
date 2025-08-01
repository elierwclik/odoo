# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""
Web_editor-context rendering needs to add some metadata to rendered and allow to edit fields,
as well as render a few fields differently.

Also, adds methods to convert values back to Odoo models.
"""

import base64
import io
import json
import logging
import os
import re
from datetime import datetime

import babel
import pytz
import requests
from lxml import etree, html
from markupsafe import Markup, escape_silent
from PIL import Image as I
from werkzeug import urls

from odoo import _, api, models, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tools import posix_to_ldml
from odoo.tools.misc import file_open, get_lang, babel_locale_parse

REMOTE_CONNECTION_TIMEOUT = 2.5

logger = logging.getLogger(__name__)


class IrQweb(models.AbstractModel):
    """ IrQweb object for rendering editor stuff
    """
    _inherit = 'ir.qweb'

    def _compile_node(self, el, compile_context, level):
        snippet_key = compile_context.get('snippet-key')
        template = compile_context['template']
        sub_call_key = compile_context.get('snippet-sub-call-key')
        # We only add the 'data-snippet' & 'data-name' attrib once when
        # compiling the root node of the template.
        if template not in {snippet_key, sub_call_key} or el.getparent() is not None:
            return super()._compile_node(el, compile_context, level)

        snippet_base_node = el
        if el.tag == 't':
            el_children = [child for child in list(el) if isinstance(child.tag, str) and child.tag != 't']
            if len(el_children) == 1:
                snippet_base_node = el_children[0]
            elif not el_children:
                # If there's not a valid base node we check if the base node is
                # a t-call to another template. If so the called template's base
                # node must take the current snippet key.
                el_children = [child for child in list(el) if isinstance(child.tag, str)]
                if len(el_children) == 1:
                    sub_call = el_children[0].get('t-call')
                    if sub_call:
                        el_children[0].set('t-options', f"{{'snippet-key': '{snippet_key}', 'snippet-sub-call-key': '{sub_call}'}}")
        # If it already has a data-snippet it is a saved or an
        # inherited snippet. Do not override it.
        if 'data-snippet' not in snippet_base_node.attrib:
            snippet_base_node.attrib['data-snippet'] = \
                snippet_key.split('.', 1)[-1]
        # If it already has a data-name it is a saved or an
        # inherited snippet. Do not override it.
        snippet_name = compile_context.get('snippet-name')
        if snippet_name and 'data-name' not in snippet_base_node.attrib:
            snippet_base_node.attrib['data-name'] = snippet_name
        return super()._compile_node(el, compile_context, level)

    def _get_preload_attribute_xmlids(self):
        return super()._get_preload_attribute_xmlids() + ['t-snippet', 't-snippet-call']

    # compile directives

    def _compile_directive_snippet(self, el, compile_context, indent):
        key = el.attrib.pop('t-snippet')
        el.set('t-call', key)
        snippet_lang = self.env.context.get('snippet_lang')
        if snippet_lang:
            el.set('t-lang', f"'{snippet_lang}'")

        el.set('t-options', f"{{'snippet-key': {key!r}}}")
        view = self.env['ir.ui.view']._get_template_view(key)
        name = el.attrib.pop('string', view.name)
        thumbnail = el.attrib.pop('t-thumbnail', "oe-thumbnail")
        image_preview = el.attrib.pop('t-image-preview', None)
        # Forbid sanitize contains the specific reason:
        # - "true": always forbid
        # - "form": forbid if forms are sanitized
        forbid_sanitize = el.attrib.pop('t-forbid-sanitize', None)
        snippet_group = el.attrib.pop('snippet-group', None)
        group = el.attrib.pop('group', None)
        label = el.attrib.pop('label', None)
        div = Markup('<div name="%s" data-oe-type="snippet" data-o-image-preview="%s" data-oe-thumbnail="%s" data-oe-snippet-id="%s" data-oe-snippet-key="%s" data-oe-keywords="%s" %s %s %s %s>') % (
            name,
            escape_silent(image_preview),
            thumbnail,
            view.id,
            key.split('.')[-1],
            escape_silent(el.findtext('keywords')),
            Markup('data-oe-forbid-sanitize="%s"') % forbid_sanitize if forbid_sanitize else '',
            Markup('data-o-snippet-group="%s"') % snippet_group if snippet_group else '',
            Markup('data-o-group="%s"') % group if group else '',
            Markup('data-o-label="%s"') % label if label else '',
        )
        self._append_text(div, compile_context)
        code = self._compile_node(el, compile_context, indent)
        self._append_text('</div>', compile_context)
        return code

    def _compile_directive_snippet_call(self, el, compile_context, indent):
        key = el.attrib.pop('t-snippet-call')
        snippet_name = el.attrib.pop('string', None)
        el.set('t-call', key)
        el.set('t-options', f"{{'snippet-key': {key!r}, 'snippet-name': {snippet_name!r}}}")
        return self._compile_node(el, compile_context, indent)

    def _compile_directive_install(self, el, compile_context, indent):
        key = el.attrib.pop('t-install')
        thumbnail = el.attrib.pop('t-thumbnail', 'oe-thumbnail')
        image_preview = el.attrib.pop('t-image-preview', None)
        group = el.attrib.pop('group', None)
        label = el.attrib.pop('label', None)
        if self.env.user.has_group('base.group_system'):
            module = self.env['ir.module.module'].search([('name', '=', key)])
            if not module or module.state == 'installed':
                return []
            name = el.attrib.get('string') or 'Snippet'
            div = Markup('<div name="%s" data-oe-type="snippet" data-module-id="%s" data-module-display-name="%s" data-o-image-preview="%s" data-oe-thumbnail="%s" %s %s><section/></div>') % (
                name,
                module.id,
                module.display_name,
                escape_silent(image_preview),
                thumbnail,
                Markup('data-o-group="%s"') % group if group else '',
                Markup('data-o-label="%s"') % label if label else '',
            )
            self._append_text(div, compile_context)
        return []

    def _compile_directive_placeholder(self, el, compile_context, indent):
        el.set('t-att-placeholder', el.attrib.pop('t-placeholder'))
        return []

    # order and ignore

    def _directives_eval_order(self):
        directives = super()._directives_eval_order()
        # Insert before "att" as those may rely on static attributes like
        # "string" and "att" clears all of those
        index = directives.index('att') - 1
        directives.insert(index, 'placeholder')
        directives.insert(index, 'snippet')
        directives.insert(index, 'snippet-call')
        directives.insert(index, 'install')
        return directives

    def _get_template_cache_keys(self):
        return super()._get_template_cache_keys() + ['snippet_lang']


#------------------------------------------------------
# QWeb fields
#------------------------------------------------------


class IrQwebField(models.AbstractModel):
    _name = 'ir.qweb.field'
    _description = 'Qweb Field'
    _inherit = ['ir.qweb.field']

    @api.model
    def attributes(self, record, field_name, options, values=None):
        attrs = super().attributes(record, field_name, options, values)
        field = record._fields[field_name]

        placeholder = options.get('placeholder') or getattr(field, 'placeholder', None)
        if placeholder:
            attrs['placeholder'] = placeholder

        if options['translate'] and field.type in ('char', 'text'):
            lang = record.env.lang or 'en_US'
            base_lang = record._get_base_lang()
            if lang == base_lang:
                attrs['data-oe-translation-state'] = 'translated'
            else:
                base_value = record.with_context(lang=base_lang)[field_name]
                value = record[field_name]
                attrs['data-oe-translation-state'] = 'translated' if base_value != value else 'to_translate'

        return attrs

    def value_from_string(self, value):
        return value

    @api.model
    def from_html(self, model, field, element):
        return self.value_from_string(element.text_content().strip()) or False


class IrQwebFieldInteger(models.AbstractModel):
    _name = 'ir.qweb.field.integer'
    _description = 'Qweb Field Integer'
    _inherit = ['ir.qweb.field.integer']

    @api.model
    def from_html(self, model, field, element):
        lang = self.user_lang()
        value = element.text_content().strip()
        return int(value.replace(lang.thousands_sep or '', ''))


class IrQwebFieldFloat(models.AbstractModel):
    _name = 'ir.qweb.field.float'
    _description = 'Qweb Field Float'
    _inherit = ['ir.qweb.field.float']

    @api.model
    def from_html(self, model, field, element):
        lang = self.user_lang()
        value = element.text_content().strip()
        return float(value.replace(lang.thousands_sep or '', '')
                          .replace(lang.decimal_point, '.'))


class IrQwebFieldMany2one(models.AbstractModel):
    _name = 'ir.qweb.field.many2one'
    _description = 'Qweb Field Many to One'
    _inherit = ['ir.qweb.field.many2one']

    @api.model
    def attributes(self, record, field_name, options, values=None):
        attrs = super().attributes(record, field_name, options, values)
        if options.get('inherit_branding'):
            many2one = record[field_name]
            if many2one:
                attrs['data-oe-many2one-id'] = many2one.id
                attrs['data-oe-many2one-model'] = many2one._name
            if options.get('null_text'):
                attrs['data-oe-many2one-allowreset'] = 1
                if not many2one:
                    attrs['data-oe-many2one-model'] = record._fields[field_name].comodel_name
        return attrs

    @api.model
    def from_html(self, model, field, element):
        Model = self.env[element.get('data-oe-model')]
        id = int(element.get('data-oe-id'))
        M2O = self.env[field.comodel_name]
        field_name = element.get('data-oe-field')
        many2one_id = int(element.get('data-oe-many2one-id'))

        allow_reset = element.get('data-oe-many2one-allowreset')
        if allow_reset and not many2one_id:
            # Reset the id of the many2one
            Model.browse(id).write({field_name: False})
            return None

        record = many2one_id and M2O.browse(many2one_id)
        if record and record.exists():
            # save the new id of the many2one
            Model.browse(id).write({field_name: many2one_id})

        return None


class IrQwebFieldContact(models.AbstractModel):
    _name = 'ir.qweb.field.contact'
    _description = 'Qweb Field Contact'
    _inherit = ['ir.qweb.field.contact']

    @api.model
    def attributes(self, record, field_name, options, values=None):
        attrs = super().attributes(record, field_name, options, values)
        if options.get('inherit_branding'):
            attrs['data-oe-contact-options'] = json.dumps(options)
        return attrs

    @api.model
    def get_record_to_html(self, contact_ids, options=None):
        """ Helper to call the rendering of contact field. """
        return self.value_to_html(self.env['res.partner'].search([('id', '=', contact_ids[0])]), options=options)


class IrQwebFieldDate(models.AbstractModel):
    _name = 'ir.qweb.field.date'
    _description = 'Qweb Field Date'
    _inherit = ['ir.qweb.field.date']

    @api.model
    def attributes(self, record, field_name, options, values=None):
        attrs = super().attributes(record, field_name, options, values)
        if options.get('inherit_branding'):
            attrs['data-oe-original'] = record[field_name]

            if record._fields[field_name].type == 'datetime':
                attrs = self.env['ir.qweb.field.datetime'].attributes(record, field_name, options, values)
                attrs['data-oe-type'] = 'datetime'
                return attrs

            lg = get_lang(self.env, self.env.user.lang)
            locale = babel_locale_parse(lg.code)
            babel_format = value_format = posix_to_ldml(lg.date_format, locale=locale)

            if record[field_name]:
                date = fields.Date.from_string(record[field_name])
                value_format = babel.dates.format_date(date, format=babel_format, locale=locale)

            attrs['data-oe-original-with-format'] = value_format
        return attrs

    @api.model
    def from_html(self, model, field, element):
        value = element.text_content().strip()
        if not value:
            return False

        lg = get_lang(self.env, self.env.user.lang)
        date = datetime.strptime(value, lg.date_format)
        return fields.Date.to_string(date)


class IrQwebFieldDatetime(models.AbstractModel):
    _name = 'ir.qweb.field.datetime'
    _description = 'Qweb Field Datetime'
    _inherit = ['ir.qweb.field.datetime']

    @api.model
    def attributes(self, record, field_name, options, values=None):
        attrs = super().attributes(record, field_name, options, values)

        if options.get('inherit_branding'):
            value = record[field_name]

            lg = get_lang(self.env, self.env.user.lang)
            locale = babel_locale_parse(lg.code)
            babel_format = value_format = posix_to_ldml('%s %s' % (lg.date_format, lg.time_format), locale=locale)
            tz = record.env.context.get('tz') or self.env.user.tz

            if isinstance(value, str):
                value = fields.Datetime.from_string(value)

            if value:
                # convert from UTC (server timezone) to user timezone
                value = fields.Datetime.context_timestamp(self.with_context(tz=tz), timestamp=value)
                value_format = babel.dates.format_datetime(value, format=babel_format, locale=locale)
                value = fields.Datetime.to_string(value)

            attrs['data-oe-original'] = value
            attrs['data-oe-original-with-format'] = value_format
            attrs['data-oe-original-tz'] = tz
        return attrs

    @api.model
    def from_html(self, model, field, element):
        value = element.text_content().strip()
        if not value:
            return False

        # parse from string to datetime
        lg = get_lang(self.env, self.env.user.lang)
        try:
            datetime_format = f'{lg.date_format} {lg.time_format}'
            dt = datetime.strptime(value, datetime_format)
        except ValueError:
            raise ValidationError(_("The datetime %(value)s does not match the format %(format)s", value=value, format=datetime_format))

        # convert back from user's timezone to UTC
        tz_name = element.attrib.get('data-oe-original-tz') or self.env.context.get('tz') or self.env.user.tz
        if tz_name:
            try:
                user_tz = pytz.timezone(tz_name)
                utc = pytz.utc

                dt = user_tz.localize(dt).astimezone(utc)
            except Exception:
                logger.warning(
                    "Failed to convert the value for a field of the model"
                    " %s back from the user's timezone (%s) to UTC",
                    model, tz_name,
                    exc_info=True)

        # format back to string
        return fields.Datetime.to_string(dt)


class IrQwebFieldText(models.AbstractModel):
    _name = 'ir.qweb.field.text'
    _description = 'Qweb Field Text'
    _inherit = ['ir.qweb.field.text']

    @api.model
    def from_html(self, model, field, element):
        return html_to_text(element)


class IrQwebFieldSelection(models.AbstractModel):
    _name = 'ir.qweb.field.selection'
    _description = 'Qweb Field Selection'
    _inherit = ['ir.qweb.field.selection']

    @api.model
    def from_html(self, model, field, element):
        value = element.text_content().strip()
        selection = field.get_description(self.env)['selection']
        for k, v in selection:
            if value == v:
                return k

        raise ValueError(u"No value found for label %s in selection %s" % (
                         value, selection))


class IrQwebFieldHtml(models.AbstractModel):
    _name = 'ir.qweb.field.html'
    _description = 'Qweb Field HTML'
    _inherit = ['ir.qweb.field.html']

    @api.model
    def attributes(self, record, field_name, options, values=None):
        attrs = super().attributes(record, field_name, options, values)
        if options.get('inherit_branding'):
            field = record._fields[field_name]
            if field.sanitize:
                if field.sanitize_overridable:
                    if record.env.user.has_group('base.group_sanitize_override'):
                        # Don't mark the field as 'sanitize' if the sanitize
                        # is defined as overridable and the user has the right
                        # to do so
                        return attrs
                    else:
                        try:
                            field.convert_to_column_insert(record[field_name], record)
                        except UserError:
                            # The field contains element(s) that would be
                            # removed if sanitized. It means that someone who
                            # was part of a group allowing to bypass the
                            # sanitation saved that field previously. Mark the
                            # field as not editable.
                            attrs['data-oe-sanitize-prevent-edition'] = 1
                            return attrs
                # The field edition is not fully prevented and the sanitation cannot be bypassed
                attrs['data-oe-sanitize'] = 'no_block' if field.sanitize_attributes else 1 if field.sanitize_form else 'allow_form'

        return attrs

    @api.model
    def from_html(self, model, field, element):
        content = []
        if element.text:
            content.append(element.text)
        content.extend(html.tostring(child, encoding='unicode')
                       for child in element.iterchildren(tag=etree.Element))
        return '\n'.join(content)


class IrQwebFieldImage(models.AbstractModel):
    """
    Widget options:

    ``class``
        set as attribute on the generated <img> tag
    """
    _name = 'ir.qweb.field.image'
    _description = 'Qweb Field Image'
    _inherit = ['ir.qweb.field.image']

    local_url_re = re.compile(r'^/(?P<module>[^]]+)/static/(?P<rest>.+)$')
    redirect_url_re = re.compile(r'\/web\/image\/\d+-redirect\/')

    @api.model
    def from_html(self, model, field, element):
        if element.find('img') is None:
            return False
        url = element.find('img').get('src')

        url_object = urls.url_parse(url)
        if url_object.path.startswith('/web/image'):
            fragments = url_object.path.split('/')
            query = url_object.decode_query()
            url_id = fragments[3].split('-')[0]
            # ir.attachment image urls: /web/image/<id>[-<checksum>][/...]
            if url_id.isdigit():
                model = 'ir.attachment'
                oid = url_id
                field = 'datas'
            # url of binary field on model: /web/image/<model>/<id>/<field>[/...]
            else:
                model = query.get('model', fragments[3])
                oid = query.get('id', fragments[4])
                field = query.get('field', fragments[5])
            item = self.env[model].browse(int(oid))
            if self.redirect_url_re.match(url_object.path):
                return self.load_remote_url(item.url)
            return item[field]

        if self.local_url_re.match(url_object.path):
            return self.load_local_url(url)

        return self.load_remote_url(url)

    def load_local_url(self, url):
        match = self.local_url_re.match(urls.url_parse(url).path)
        rest = match.group('rest')

        path = os.path.join(
            match.group('module'), 'static', rest)

        try:
            with file_open(path, 'rb') as f:
                # force complete image load to ensure it's valid image data
                image = I.open(f)
                image.load()
                f.seek(0)
                return base64.b64encode(f.read())
        except Exception:
            logger.exception("Failed to load local image %r", url)
            return None

    def load_remote_url(self, url):
        try:
            # should probably remove remote URLs entirely:
            # * in fields, downloading them without blowing up the server is a
            #   challenge
            # * in views, may trigger mixed content warnings if HTTPS CMS
            #   linking to HTTP images
            # implement drag & drop image upload to mitigate?

            req = requests.get(url, timeout=REMOTE_CONNECTION_TIMEOUT)
            # PIL needs a seekable file-like image so wrap result in IO buffer
            image = I.open(io.BytesIO(req.content))
            # force a complete load of the image data to validate it
            image.load()
        except Exception:
            logger.warning("Failed to load remote image %r", url, exc_info=True)
            return None

        # don't use original data in case weird stuff was smuggled in, with
        # luck PIL will remove some of it?
        out = io.BytesIO()
        image.save(out, image.format)
        return base64.b64encode(out.getvalue())


class IrQwebFieldMonetary(models.AbstractModel):
    _inherit = 'ir.qweb.field.monetary'

    @api.model
    def from_html(self, model, field, element):
        lang = self.user_lang()

        value = element.find('span').text_content().strip()

        return float(value.replace(lang.thousands_sep or '', '')
                          .replace(lang.decimal_point, '.'))


class IrQwebFieldDuration(models.AbstractModel):
    _name = 'ir.qweb.field.duration'
    _description = 'Qweb Field Duration'
    _inherit = ['ir.qweb.field.duration']

    @api.model
    def attributes(self, record, field_name, options, values=None):
        attrs = super().attributes(record, field_name, options, values)
        if options.get('inherit_branding'):
            attrs['data-oe-original'] = record[field_name]
        return attrs

    @api.model
    def from_html(self, model, field, element):
        value = element.text_content().strip()

        # non-localized value
        return float(value)


class IrQwebFieldRelative(models.AbstractModel):
    _name = 'ir.qweb.field.relative'
    _description = 'Qweb Field Relative'
    _inherit = ['ir.qweb.field.relative']

    # get formatting from ir.qweb.field.relative but edition/save from datetime


class IrQwebFieldQweb(models.AbstractModel):
    _name = 'ir.qweb.field.qweb'
    _description = 'Qweb Field qweb'
    _inherit = ['ir.qweb.field.qweb']


def html_to_text(element):
    """ Converts HTML content with HTML-specified line breaks (br, p, div, ...)
    in roughly equivalent textual content.

    Used to replace and fixup the roundtripping of text and m2o: when using
    libxml 2.8.0 (but not 2.9.1) and parsing IrQwebFieldHtml with lxml.html.fromstring
    whitespace text nodes (text nodes composed *solely* of whitespace) are
    stripped out with no recourse, and fundamentally relying on newlines
    being in the text (e.g. inserted during user edition) is probably poor form
    anyway.

    -> this utility function collapses whitespace sequences and replaces
       nodes by roughly corresponding linebreaks
       * p are pre-and post-fixed by 2 newlines
       * br are replaced by a single newline
       * block-level elements not already mentioned are pre- and post-fixed by
         a single newline

    ought be somewhat similar (but much less high-tech) to aaronsw's html2text.
    the latter produces full-blown markdown, our text -> html converter only
    replaces newlines by <br> elements at this point so we're reverting that,
    and a few more newline-ish elements in case the user tried to add
    newlines/paragraphs into the text field

    :param element: lxml.html content
    :returns: corresponding pure-text output
    """

    # output is a list of str | int. Integers are padding requests (in minimum
    # number of newlines). When multiple padding requests, fold them into the
    # biggest one
    output = []
    _wrap(element, output)

    # remove any leading or tailing whitespace, replace sequences of
    # (whitespace)\n(whitespace) by a single newline, where (whitespace) is a
    # non-newline whitespace in this case
    return re.sub(
        r'[ \t\r\f]*\n[ \t\r\f]*',
        '\n',
        ''.join(_realize_padding(output)).strip())

_PADDED_BLOCK = set('p h1 h2 h3 h4 h5 h6'.split())
# https://developer.mozilla.org/en-US/docs/HTML/Block-level_elements minus p
_MISC_BLOCK = set((
    'address article aside audio blockquote canvas dd dl div figcaption figure'
    ' footer form header hgroup hr ol output pre section tfoot ul video'
).split())


def _collapse_whitespace(text):
    """ Collapses sequences of whitespace characters in ``text`` to a single
    space
    """
    return re.sub(r'\s+', ' ', text)


def _realize_padding(it):
    """ Fold and convert padding requests: integers in the output sequence are
    requests for at least n newlines of padding. Runs thereof can be collapsed
    into the largest requests and converted to newlines.
    """
    padding = 0
    for item in it:
        if isinstance(item, int):
            padding = max(padding, item)
            continue

        if padding:
            yield '\n' * padding
            padding = 0

        yield item
    # leftover padding irrelevant as the output will be stripped


def _wrap(element, output, wrapper=''):
    """ Recursively extracts text from ``element`` (via _element_to_text), and
    wraps it all in ``wrapper``. Extracted text is added to ``output``

    :type wrapper: basestring | int
    """
    output.append(wrapper)
    if element.text:
        output.append(_collapse_whitespace(element.text))
    for child in element:
        _element_to_text(child, output)
    output.append(wrapper)


def _element_to_text(e, output):
    if e.tag == 'br':
        output.append('\n')
    elif e.tag in _PADDED_BLOCK:
        _wrap(e, output, 2)
    elif e.tag in _MISC_BLOCK:
        _wrap(e, output, 1)
    else:
        # inline
        _wrap(e, output)

    if e.tail:
        output.append(_collapse_whitespace(e.tail))
