# -*- coding: utf-8 -*-
import base64
import binascii
from datetime import time
import logging
import re
from io import BytesIO

import babel
import babel.dates
from markupsafe import Markup, escape, escape_silent
from PIL import Image
from lxml import etree, html

from odoo import api, fields, models, tools
from odoo.tools import posix_to_ldml, float_utils, format_date, format_duration
from odoo.tools.mail import safe_attrs
from odoo.tools.misc import get_lang, babel_locale_parse
from odoo.tools.mimetypes import guess_mimetype
from odoo.tools.translate import _, LazyTranslate

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)


def nl2br(string: str) -> Markup:
    """ Converts newlines to HTML linebreaks in ``string`` after HTML-escaping
    it.
    """
    return escape_silent(string).replace('\n', Markup('<br>\n'))


def nl2br_enclose(string: str, enclosure_tag: str = 'div') -> Markup:
    """ Like nl2br, but returns enclosed Markup allowing to better manipulate
    trusted and untrusted content. New lines added by use are trusted, other
    content is escaped. """
    return Markup('<{enclosure_tag}>{converted}</{enclosure_tag}>').format(
        enclosure_tag=enclosure_tag,
        converted=nl2br(string),
    )

#--------------------------------------------------------------------
# QWeb Fields converters
#--------------------------------------------------------------------


class IrQwebField(models.AbstractModel):
    """ Used to convert a t-field specification into an output HTML field.

    :meth:`~.to_html` is the entry point of this conversion from QWeb, it:

    * converts the record value to html using :meth:`~.record_to_html`
    * generates the metadata attributes (``data-oe-``) to set on the root
      result node
    * generates the root result node itself through :meth:`~.render_element`
    """
    _name = 'ir.qweb.field'
    _description = 'Qweb Field'

    @api.model
    def get_available_options(self):
        """ Get the available option informations.

        :rtype: dict[str, dict[str, Any]]
        :return: A dictionnary that maps option names' to their settings.

            The settings are dict themselves and have the following keys:

            type

                Guaranteed, one of ``'string'``, ``'integer'``, ``'float'``,
                ``'model'``, ``'array'``, or ``'selection'``.

            string

                Guaranteed

            description

                Optional

            required

                Optional, is assumed ``False`` when absent, otherwise
                is either ``True`` or a string.

            params

                Optional

            default_value

                Optional, the default value, as a json-friendly type.

            Example::

                {
                    <option>: {
                        # guaranteed
                        'type': ...,
                        'string': ...,
                        # optional
                        'default_value': ...,
                        'description': ...,
                        'params': ...,
                        'required': ...,
                    }
                }
        """
        return {}

    @api.model
    def attributes(self, record, field_name, options, values=None):
        """ attributes(record, field_name, field, options, values)

        Generates the metadata attributes (prefixed by ``data-oe-``) for the
        root node of the field conversion.

        The default attributes are:

        * ``model``, the name of the record's model
        * ``id`` the id of the record to which the field belongs
        * ``type`` the logical field type (widget, may not match the field's
          ``type``, may not be any Field subclass name)
        * ``translate``, a boolean flag (``0`` or ``1``) denoting whether the
          field is translatable
        * ``readonly``, has this attribute if the field is readonly
        * ``expression``, the original expression

        :returns: dict (attribute name, attribute value).
        """
        data = {}
        field = record._fields[field_name]

        if not options['inherit_branding'] and not options['translate']:
            return data

        data['data-oe-model'] = record._name
        data['data-oe-id'] = record.id
        data['data-oe-field'] = field.name
        data['data-oe-type'] = options.get('type')
        data['data-oe-expression'] = options.get('expression')
        if field.readonly:
            data['data-oe-readonly'] = 1
        return data

    @api.model
    def value_to_html(self, value, options):
        """ value_to_html(value, field, options=None)

        Converts a single value to its HTML version/output
        :rtype: unicode
        """
        if value is None or value is False:
            return ''

        return escape(value.decode() if isinstance(value, bytes) else value)

    @api.model
    def record_to_html(self, record, field_name, options):
        """ record_to_html(record, field_name, options)

        Converts the specified field of the ``record`` to HTML

        :rtype: unicode
        """
        if not record:
            return False
        value = record.with_context(**self.env.context)[field_name]
        return False if value is False else self.value_to_html(value, options=options)

    @api.model
    def user_lang(self):
        """ user_lang()

        Fetches the res.lang record corresponding to the language code stored
        in the user's context.

        :returns: Model[res.lang]
        """
        return self.env['res.lang'].browse(get_lang(self.env).id)


class IrQwebFieldInteger(models.AbstractModel):
    _name = 'ir.qweb.field.integer'
    _description = 'Qweb Field Integer'
    _inherit = ['ir.qweb.field']

    @api.model
    def get_available_options(self):
        options = super().get_available_options()
        options.update(
            format_decimalized_number=dict(type='boolean', string=_('Decimalized number')),
            precision_digits=dict(type='integer', string=_('Precision Digits')),
        )
        return options

    @api.model
    def value_to_html(self, value, options):
        if options.get('format_decimalized_number'):
            return tools.misc.format_decimalized_number(value, options.get('precision_digits', 1))
        return self.user_lang().format('%d', value, grouping=True).replace(r'-', '-\N{ZERO WIDTH NO-BREAK SPACE}')


class IrQwebFieldFloat(models.AbstractModel):
    _name = 'ir.qweb.field.float'
    _description = 'Qweb Field Float'
    _inherit = ['ir.qweb.field']

    @api.model
    def get_available_options(self):
        options = super().get_available_options()
        options.update(
            precision=dict(type='integer', string=_('Rounding precision')),
        )
        return options

    @api.model
    def value_to_html(self, value, options):
        if 'decimal_precision' in options:
            precision = self.env['decimal.precision'].precision_get(options['decimal_precision'])
        else:
            precision = options['precision']

        if precision is None:
            fmt = '%f'
        else:
            value = float_utils.float_round(value, precision_digits=precision)
            fmt = '%.{precision}f'.format(precision=precision)

        formatted = self.user_lang().format(fmt, value, grouping=True).replace(r'-', '-\N{ZERO WIDTH NO-BREAK SPACE}')

        # %f does not strip trailing zeroes. %g does but its precision causes
        # it to switch to scientific notation starting at a million *and* to
        # strip decimals. So use %f and if no precision was specified manually
        # strip trailing 0.
        if precision is None:
            formatted = re.sub(r'(?:(0|\d+?)0+)$', r'\1', formatted)

        return formatted

    @api.model
    def record_to_html(self, record, field_name, options):
        if 'precision' not in options and 'decimal_precision' not in options:
            _, precision = record._fields[field_name].get_digits(record.env) or (None, None)
            options = dict(options, precision=precision)
        return super().record_to_html(record, field_name, options)


class IrQwebFieldDate(models.AbstractModel):
    _name = 'ir.qweb.field.date'
    _description = 'Qweb Field Date'
    _inherit = ['ir.qweb.field']

    @api.model
    def get_available_options(self):
        options = super().get_available_options()
        options.update(
            format=dict(type='string', string=_('Date format'))
        )
        return options

    @api.model
    def value_to_html(self, value, options):
        return format_date(self.env, value, date_format=options.get('format'))


class IrQwebFieldDatetime(models.AbstractModel):
    _name = 'ir.qweb.field.datetime'
    _description = 'Qweb Field Datetime'
    _inherit = ['ir.qweb.field']

    @api.model
    def get_available_options(self):
        options = super().get_available_options()
        options.update(
            format=dict(type='string', string=_('Pattern to format')),
            tz_name=dict(type='char', string=_('Optional timezone name')),
            time_only=dict(type='boolean', string=_('Display only the time')),
            hide_seconds=dict(type='boolean', string=_('Hide seconds')),
            date_only=dict(type='boolean', string=_('Display only the date')),
        )
        return options

    @api.model
    def value_to_html(self, value, options):
        if not value:
            return ''

        lang = self.user_lang()
        locale = babel_locale_parse(lang.code)
        if isinstance(value, str):
            value = fields.Datetime.from_string(value)

        if options.get('tz_name'):
            self = self.with_context(tz=options['tz_name'])
            tzinfo = babel.dates.get_timezone(options['tz_name'])
        else:
            tzinfo = None

        value = fields.Datetime.context_timestamp(self, value)

        if 'format' in options:
            pattern = options['format']
        else:
            if options.get('time_only'):
                strftime_pattern = lang.time_format
            elif options.get('date_only'):
                strftime_pattern = lang.date_format
            else:
                strftime_pattern = "%s %s" % (lang.date_format, lang.time_format)

            pattern = posix_to_ldml(strftime_pattern, locale=locale)

        if options.get('hide_seconds'):
            pattern = pattern.replace(":ss", "").replace(":s", "")

        if options.get('time_only'):
            return babel.dates.format_time(value, format=pattern, tzinfo=tzinfo, locale=locale)
        elif options.get('date_only'):
            return babel.dates.format_date(value, format=pattern, locale=locale)
        else:
            return babel.dates.format_datetime(value, format=pattern, tzinfo=tzinfo, locale=locale)


class IrQwebFieldText(models.AbstractModel):
    _name = 'ir.qweb.field.text'
    _description = 'Qweb Field Text'
    _inherit = ['ir.qweb.field']

    @api.model
    def value_to_html(self, value, options):
        """
        Escapes the value and converts newlines to br. This is bullshit.
        """
        return nl2br(value) if value else ''


class IrQwebFieldSelection(models.AbstractModel):
    _name = 'ir.qweb.field.selection'
    _description = 'Qweb Field Selection'
    _inherit = ['ir.qweb.field']

    @api.model
    def get_available_options(self):
        options = super().get_available_options()
        options.update(
            selection=dict(type='selection', string=_('Selection'), description=_('By default the widget uses the field information'), required=True)
        )
        options.update(
            selection=dict(type='json', string=_('Json'), description=_('By default the widget uses the field information'), required=True)
        )
        return options

    @api.model
    def value_to_html(self, value, options):
        if not value:
            return ''
        return escape(options['selection'][value] or '')

    @api.model
    def record_to_html(self, record, field_name, options):
        if 'selection' not in options:
            options = dict(options, selection=dict(record._fields[field_name].get_description(self.env)['selection']))
        return super().record_to_html(record, field_name, options)


class IrQwebFieldMany2one(models.AbstractModel):
    _name = 'ir.qweb.field.many2one'
    _description = 'Qweb Field Many to One'
    _inherit = ['ir.qweb.field']

    @api.model
    def value_to_html(self, value, options):
        if not value:
            return False
        value = value.sudo().display_name
        if not value:
            return False
        return nl2br(value)


class IrQwebFieldMany2many(models.AbstractModel):
    _name = 'ir.qweb.field.many2many'
    _description = 'Qweb field many2many'
    _inherit = ['ir.qweb.field']

    @api.model
    def value_to_html(self, value, options):
        if not value:
            return False
        text = ', '.join(value.sudo().mapped('display_name'))
        return nl2br(text)


class IrQwebFieldHtml(models.AbstractModel):
    _name = 'ir.qweb.field.html'
    _description = 'Qweb Field HTML'
    _inherit = ['ir.qweb.field']

    @api.model
    def value_to_html(self, value, options):
        irQweb = self.env['ir.qweb']
        # wrap value inside a body and parse it as HTML
        body = etree.fromstring("<body>%s</body>" % value, etree.HTMLParser(encoding='utf-8'))[0]
        # use pos processing for all nodes with attributes
        for element in body.iter():
            if element.attrib:
                attrib = dict(element.attrib)
                attrib = irQweb._post_processing_att(element.tag, attrib)
                element.attrib.clear()
                element.attrib.update(attrib)
        return Markup(etree.tostring(body, encoding='unicode', method='html')[6:-7])


class IrQwebFieldImage(models.AbstractModel):
    """ ``image`` widget rendering, inserts a data:uri-using image tag in the
    document. May be overridden by e.g. the website module to generate links
    instead.

    .. todo:: what happens if different output need different converters? e.g.
              reports may need embedded images or FS links whereas website
              needs website-aware
    """
    _name = 'ir.qweb.field.image'
    _description = 'Qweb Field Image'
    _inherit = ['ir.qweb.field']

    @api.model
    def _get_src_data_b64(self, value, options):
        try:
            img_b64 = base64.b64decode(value)
        except binascii.Error:
            raise ValueError("Invalid image content") from None

        if img_b64 and guess_mimetype(img_b64, '') == 'image/webp':
            return self.env["ir.qweb"]._get_converted_image_data_uri(value)

        try:
            image = Image.open(BytesIO(img_b64))
            image.verify()
        except IOError:
            raise ValueError("Non-image binary fields can not be converted to HTML") from None
        except: # image.verify() throws "suitable exceptions", I have no idea what they are
            raise ValueError("Invalid image content") from None

        return "data:%s;base64,%s" % (Image.MIME[image.format], value.decode('ascii'))

    @api.model
    def value_to_html(self, value, options):
        return Markup('<img src="%s">') % self._get_src_data_b64(value, options)


class IrQwebFieldImage_Url(models.AbstractModel):
    """ ``image_url`` widget rendering, inserts an image tag in the
    document.
    """
    _name = 'ir.qweb.field.image_url'
    _description = 'Qweb Field Image'
    _inherit = ['ir.qweb.field.image']

    @api.model
    def value_to_html(self, value, options):
        return Markup('<img src="%s">' % (value))


class IrQwebFieldMonetary(models.AbstractModel):
    """ ``monetary`` converter, has a mandatory option
    ``display_currency`` only if field is not of type Monetary.
    Otherwise, if we are in presence of a monetary field, the field definition must
    have a currency_field attribute set.

    The currency is used for formatting *and rounding* of the float value. It
    is assumed that the linked res_currency has a non-empty rounding value and
    res.currency's ``round`` method is used to perform rounding.

    .. note:: the monetary converter internally adds the qweb context to its
              options mapping, so that the context is available to callees.
              It's set under the ``_values`` key.
    """
    _name = 'ir.qweb.field.monetary'
    _description = 'Qweb Field Monetary'
    _inherit = ['ir.qweb.field']

    @api.model
    def get_available_options(self):
        options = super().get_available_options()
        options.update(
            from_currency=dict(type='model', params='res.currency', string=_('Original currency')),
            display_currency=dict(type='model', params='res.currency', string=_('Display currency'), required="value_to_html"),
            date=dict(type='date', string=_('Date'), description=_('Date used for the original currency (only used for t-esc). by default use the current date.')),
            company_id=dict(type='model', params='res.company', string=_('Company'), description=_('Company used for the original currency (only used for t-esc). By default use the user company')),
        )
        return options

    @api.model
    def value_to_html(self, value, options):
        display_currency = options['display_currency']

        if not isinstance(value, (int, float)):
            raise ValueError(_("The value send to monetary field is not a number."))

        # lang.format mandates a sprintf-style format. These formats are non-
        # minimal (they have a default fixed precision instead), and
        # lang.format will not set one by default. currency.round will not
        # provide one either. So we need to generate a precision value
        # (integer > 0) from the currency's rounding (a float generally < 1.0).
        fmt = "%.{0}f".format(options.get('decimal_places', display_currency.decimal_places))

        if options.get('from_currency'):
            date = options.get('date') or fields.Date.today()
            company_id = options.get('company_id')
            if company_id:
                company = self.env['res.company'].browse(company_id)
            else:
                company = self.env.company
            value = options['from_currency']._convert(value, display_currency, company, date)

        lang = self.user_lang()
        formatted_amount = lang.format(fmt, display_currency.round(value), grouping=True)\
            .replace(r' ', '\N{NO-BREAK SPACE}').replace(r'-', '-\N{ZERO WIDTH NO-BREAK SPACE}')

        pre = post = ''
        if display_currency.position == 'before':
            pre = '{symbol}\N{NO-BREAK SPACE}'.format(symbol=display_currency.symbol or '')
        else:
            post = '\N{NO-BREAK SPACE}{symbol}'.format(symbol=display_currency.symbol or '')

        if options.get('label_price') and lang.decimal_point in formatted_amount:
            sep = lang.decimal_point
            integer_part, decimal_part = formatted_amount.split(sep)
            integer_part += sep
            return Markup('{pre}<span class="oe_currency_value">{0}</span><span class="oe_currency_value" style="font-size:0.5em">{1}</span>{post}').format(integer_part, decimal_part, pre=pre, post=post)

        return Markup('{pre}<span class="oe_currency_value">{0}</span>{post}').format(formatted_amount, pre=pre, post=post)

    @api.model
    def record_to_html(self, record, field_name, options):
        options = dict(options)
        #currency should be specified by monetary field
        field = record._fields[field_name]

        if not options.get('display_currency') and field.type == 'monetary' and field.get_currency_field(record):
            options['display_currency'] = record[field.get_currency_field(record)]
        if not options.get('display_currency'):
            # search on the model if they are a res.currency field to set as default
            fields = record._fields.items()
            currency_fields = [k for k, v in fields if v.type == 'many2one' and v.comodel_name == 'res.currency']
            if currency_fields:
                options['display_currency'] = record[currency_fields[0]]
        if 'date' not in options:
            options['date'] = record.env.context.get('date')
        if 'company_id' not in options:
            options['company_id'] = record.env.context.get('company_id')

        return super().record_to_html(record, field_name, options)


TIMEDELTA_UNITS = (
    ('year',   _lt('year'),   3600 * 24 * 365),
    ('month',  _lt('month'),  3600 * 24 * 30),
    ('week',   _lt('week'),   3600 * 24 * 7),
    ('day',    _lt('day'),    3600 * 24),
    ('hour',   _lt('hour'),   3600),
    ('minute', _lt('minute'), 60),
    ('second', _lt('second'), 1)
)


class IrQwebFieldFloat_Time(models.AbstractModel):
    """ ``float_time`` converter, to display integral or fractional values as
    human-readable time spans (e.g. 1.5 as "01:30").

    Can be used on any numerical field.
    """
    _name = 'ir.qweb.field.float_time'
    _description = 'Qweb Field Float Time'
    _inherit = ['ir.qweb.field']

    @api.model
    def value_to_html(self, value, options):
        return format_duration(value)


class IrQwebFieldTime(models.AbstractModel):
    """ ``time`` converter, to display integer or fractional value as
    human-readable time (e.g. 1.5 as "1:30 AM"). The unit of this value
    is in hours.

    Can be used on any numerical field between: 0 <= value < 24
    """
    _name = 'ir.qweb.field.time'
    _description = 'QWeb Field Time'
    _inherit = ['ir.qweb.field']

    @api.model
    def value_to_html(self, value, options):
        if value < 0:
            raise ValueError(_("The value (%s) passed should be positive", value))
        hours, minutes = divmod(int(abs(value) * 60), 60)
        if hours > 23:
            raise ValueError(_("The hour must be between 0 and 23"))
        t = time(hour=hours, minute=minutes)

        locale = babel_locale_parse(self.user_lang().code)
        pattern = options.get('format', 'short')

        return babel.dates.format_time(t, format=pattern, tzinfo=None, locale=locale)


class IrQwebFieldDuration(models.AbstractModel):
    """ ``duration`` converter, to display integral or fractional values as
    human-readable time spans (e.g. 1.5 as "1 hour 30 minutes").

    Can be used on any numerical field.

    Has an option ``unit`` which can be one of ``second``, ``minute``,
    ``hour``, ``day``, ``week`` or ``year``, used to interpret the numerical
    field value before converting it. By default use ``second``.

    Has an option ``round``. By default use ``second``.

    Has an option ``digital`` to display 01:00 instead of 1 hour

    Sub-second values will be ignored.
    """
    _name = 'ir.qweb.field.duration'
    _description = 'Qweb Field Duration'
    _inherit = ['ir.qweb.field']

    @api.model
    def get_available_options(self):
        options = super().get_available_options()
        unit = [(value, str(label)) for value, label, ratio in TIMEDELTA_UNITS]
        options.update(
            digital=dict(type="boolean", string=_('Digital formatting')),
            unit=dict(type="selection", params=unit, string=_('Date unit'), description=_('Date unit used for comparison and formatting'), default_value='second', required=True),
            round=dict(type="selection", params=unit, string=_('Rounding unit'), description=_("Date unit used for the rounding. The value must be smaller than 'hour' if you use the digital formatting."), default_value='second'),
            format=dict(
                type="selection",
                params=[
                    ('long', _('Long')),
                    ('short', _('Short')),
                    ('narrow', _('Narrow'))],
                string=_('Format'),
                description=_("Formatting: long, short, narrow (not used for digital)"),
                default_value='long'
            ),
            add_direction=dict(
                type="boolean",
                string=_("Add direction"),
                description=_("Add directional information (not used for digital)")
            ),
        )
        return options

    @api.model
    def value_to_html(self, value, options):
        units = {unit: duration for unit, label, duration in TIMEDELTA_UNITS}

        locale = babel_locale_parse(self.user_lang().code)
        factor = units[options.get('unit', 'second')]
        round_to = units[options.get('round', 'second')]

        if options.get('digital') and round_to > 3600:
            round_to = 3600

        r = round((value * factor) / round_to) * round_to

        sections = []
        sign = ''
        if value < 0:
            r = -r
            sign = '-'

        if options.get('digital'):
            for _unit, _label, secs_per_unit in TIMEDELTA_UNITS:
                if secs_per_unit > 3600:
                    continue
                v, r = divmod(r, secs_per_unit)
                if not v and (secs_per_unit > factor or secs_per_unit < round_to):
                    continue
                sections.append(u"%02.0f" % int(round(v)))
            return sign + u':'.join(sections)

        for _unit, _label, secs_per_unit in TIMEDELTA_UNITS:
            v, r = divmod(r, secs_per_unit)
            if not v:
                continue
            try:
                section = babel.dates.format_timedelta(
                    v*secs_per_unit,
                    granularity=round_to,
                    add_direction=options.get('add_direction'),
                    format=options.get('format', 'long'),
                    threshold=1,
                    locale=locale)
            except KeyError:
                # in case of wrong implementation of babel, try to fallback on en_US locale.
                # https://github.com/python-babel/babel/pull/827/files
                # Some bugs already fixed in 2.10 but ubuntu22 is 2.8
                localeUS = babel_locale_parse('en_US')
                section = babel.dates.format_timedelta(
                    v*secs_per_unit,
                    granularity=round_to,
                    add_direction=options.get('add_direction'),
                    format=options.get('format', 'long'),
                    threshold=1,
                    locale=localeUS)
            if section:
                sections.append(section)

        if sign:
            sections.insert(0, sign)
        return u' '.join(sections)


class IrQwebFieldRelative(models.AbstractModel):
    _name = 'ir.qweb.field.relative'
    _description = 'Qweb Field Relative'
    _inherit = ['ir.qweb.field']

    @api.model
    def get_available_options(self):
        options = super().get_available_options()
        options.update(
            now=dict(type='datetime', string=_('Reference date'), description=_('Date to compare with the field value, by default use the current date.'))
        )
        return options

    @api.model
    def value_to_html(self, value, options):
        locale = babel_locale_parse(self.user_lang().code)

        if isinstance(value, str):
            value = fields.Datetime.from_string(value)

        # value should be a naive datetime in UTC. So is fields.Datetime.now()
        reference = fields.Datetime.from_string(options['now'])

        return babel.dates.format_timedelta(value - reference, add_direction=True, locale=locale)

    @api.model
    def record_to_html(self, record, field_name, options):
        if 'now' not in options:
            options = dict(options, now=record._fields[field_name].now())
        return super().record_to_html(record, field_name, options)


class IrQwebFieldBarcode(models.AbstractModel):
    """ ``barcode`` widget rendering, inserts a data:uri-using image tag in the
    document. May be overridden by e.g. the website module to generate links
    instead.
    """
    _name = 'ir.qweb.field.barcode'
    _description = 'Qweb Field Barcode'
    _inherit = ['ir.qweb.field']

    @api.model
    def get_available_options(self):
        options = super().get_available_options()
        options.update(
            symbology=dict(type='string', string=_('Barcode symbology'), description=_('Barcode type, eg: UPCA, EAN13, Code128'), default_value='Code128'),
            width=dict(type='integer', string=_('Width'), default_value=600),
            height=dict(type='integer', string=_('Height'), default_value=100),
            humanreadable=dict(type='integer', string=_('Human Readable'), default_value=0),
            quiet=dict(type='integer', string='Quiet', default_value=1),
            mask=dict(type='string', string='Mask', default_value='')
        )
        return options

    @api.model
    def value_to_html(self, value, options=None):
        if not value:
            return ''
        if not bool(re.match(r'^[\x00-\x7F]+$', value)):
            return nl2br(value)
        barcode_symbology = options.get('symbology', 'Code128')
        barcode = self.env['ir.actions.report'].barcode(
            barcode_symbology,
            value,
            **{key: value for key, value in options.items() if key in ['width', 'height', 'humanreadable', 'quiet', 'mask']})

        img_element = html.Element('img')
        for k, v in options.items():
            if k.startswith('img_') and k[4:] in safe_attrs:
                img_element.set(k[4:], v)
        if not img_element.get('alt'):
            img_element.set('alt', _('Barcode %s', value))
        img_element.set('src', 'data:image/png;base64,%s' % base64.b64encode(barcode).decode())
        return Markup(html.tostring(img_element, encoding='unicode'))


class IrQwebFieldContact(models.AbstractModel):
    _name = 'ir.qweb.field.contact'
    _description = 'Qweb Field Contact'
    _inherit = ['ir.qweb.field.many2one']

    @api.model
    def get_available_options(self):
        options = super().get_available_options()
        contact_fields = [
            {'field_name': 'name', 'label': _('Name'), 'default': True},
            {'field_name': 'address', 'label': _('Address'), 'default': True},
            {'field_name': 'phone', 'label': _('Phone'), 'default': True},
            {'field_name': 'email', 'label': _('Email'), 'default': True},
            {'field_name': 'vat', 'label': _('VAT')},
        ]
        separator_params = dict(
            type='selection',
            selection=[[" ", _("Space")], [",", _("Comma")], ["-", _("Dash")], ["|", _("Vertical bar")], ["/", _("Slash")]],
            placeholder=_('Linebreak'),
        )
        options.update(
            fields=dict(type='array', params=dict(type='selection', params=contact_fields), string=_('Displayed fields'), description=_('List of contact fields to display in the widget'), default_value=[param.get('field_name') for param in contact_fields if param.get('default')]),
            separator=dict(type='selection', params=separator_params, string=_('Address separator'), description=_('Separator use to split the address from the display_name.'), default_value=False),
            no_marker=dict(type='boolean', string=_('Hide badges'), description=_("Don't display the font awesome marker")),
            no_tag_br=dict(type='boolean', string=_('Use comma'), description=_("Use comma instead of the <br> tag to display the address")),
            phone_icons=dict(type='boolean', string=_('Display phone icons'), description=_("Display the phone icons even if no_marker is True")),
            country_image=dict(type='boolean', string=_('Display country image'), description=_("Display the country image if the field is present on the record")),
        )
        return options

    @api.model
    def value_to_html(self, value, options):
        if not value:
            if options.get('null_text'):
                val = {
                    'options': options,
                }
                template_options = options.get('template_options', {})
                return self.env['ir.qweb']._render('base.no_contact', val, **template_options)
            return ''

        opf = options.get('fields') or ["name", "address", "phone", "email"]
        sep = options.get('separator')
        if sep:
            opsep = escape(sep)
        elif options.get('no_tag_br'):
            # escaped joiners will auto-escape joined params
            opsep = escape(', ')
        else:
            opsep = Markup('<br/>')

        value = value.sudo().with_context(show_address=True)
        display_name = value.display_name or ''
        # Avoid having something like:
        # display_name = 'Foo\n  \n' -> This is a res.partner with a name and no address
        # That would return markup('<br/>') as address. But there is no address set.
        if any(elem.strip() for elem in display_name.split("\n")[1:]):
            address = opsep.join(display_name.split("\n")[1:]).strip()
        else:
            address = ''
        val = {
            'name': display_name.split("\n")[0],
            'address': address,
            'phone': value.phone,
            'city': value.city,
            'country_id': value.country_id.display_name,
            'website': value.website,
            'email': value.email,
            'vat': value.vat,
            'vat_label': value.country_id.vat_label or _('VAT'),
            'fields': opf,
            'object': value,
            'options': options
        }
        return self.env['ir.qweb']._render('base.contact', val, minimal_qcontext=True)


class IrQwebFieldQweb(models.AbstractModel):
    _name = 'ir.qweb.field.qweb'
    _description = 'Qweb Field qweb'
    _inherit = ['ir.qweb.field.many2one']

    @api.model
    def record_to_html(self, record, field_name, options):
        view = record[field_name]
        if not view:
            return ''

        if view._name != "ir.ui.view":
            _logger.warning("%s.%s must be a 'ir.ui.view', got %r.", record, field_name, view._name)
            return ''

        return self.env['ir.qweb']._render(view.id, options.get('values', {}))
