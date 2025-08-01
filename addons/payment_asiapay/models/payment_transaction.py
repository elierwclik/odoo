# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.tools import urls

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.logging import get_payment_logger
from odoo.addons.payment_asiapay import const
from odoo.addons.payment_asiapay.controllers.main import AsiaPayController


_logger = get_payment_logger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    @api.model
    def _compute_reference(self, provider_code, prefix=None, separator='-', **kwargs):
        """ Override of `payment` to ensure that AsiaPay requirements for references are satisfied.

        AsiaPay requirements for references are as follows:
        - References must be unique at provider level for a given merchant account.
          This is satisfied by singularizing the prefix with the current datetime. If two
          transactions are created simultaneously, `_compute_reference` ensures the uniqueness of
          references by suffixing a sequence number.
        - References must be at most 35 characters long.

        :param str provider_code: The code of the provider handling the transaction.
        :param str prefix: The custom prefix used to compute the full reference.
        :param str separator: The custom separator used to separate the prefix from the suffix.
        :return: The unique reference for the transaction.
        :rtype: str
        """
        if provider_code != 'asiapay':
            return super()._compute_reference(provider_code, prefix=prefix, **kwargs)

        if not prefix:
            # If no prefix is provided, it could mean that a module has passed a kwarg intended for
            # the `_compute_reference_prefix` method, as it is only called if the prefix is empty.
            # We call it manually here because singularizing the prefix would generate a default
            # value if it was empty, hence preventing the method from ever being called and the
            # transaction from received a reference named after the related document.
            prefix = self.sudo()._compute_reference_prefix(separator, **kwargs) or None
        prefix = payment_utils.singularize_reference_prefix(prefix=prefix, max_length=35)
        return super()._compute_reference(provider_code, prefix=prefix, **kwargs)

    def _get_specific_rendering_values(self, processing_values):
        """ Override of `payment` to return AsiaPay-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`.

        :param dict processing_values: The generic and specific processing values of the
                                       transaction.
        :return: The dict of provider-specific processing values.
        :rtype: dict
        """
        def get_language_code(lang_):
            """ Return the language code corresponding to the provided lang.

            If the lang is not mapped to any language code, the country code is used instead. In
            case the country code has no match either, we fall back to English.

            :param str lang_: The lang, in IETF language tag format.
            :return: The corresponding language code.
            :rtype: str
            """
            language_code_ = const.LANGUAGE_CODES_MAPPING.get(lang_)
            if not language_code_:
                country_code_ = lang_.split('_')[0]
                language_code_ = const.LANGUAGE_CODES_MAPPING.get(country_code_)
            if not language_code_:
                language_code_ = const.LANGUAGE_CODES_MAPPING['en']
            return language_code_

        if self.provider_code != 'asiapay':
            return super()._get_specific_rendering_values(processing_values)

        base_url = self.provider_id.get_base_url()
        # The lang is taken from the context rather than from the partner because it is not required
        # to be logged in to make a payment, and because the lang is not always set on the partner.
        lang = self.env.context.get('lang') or 'en_US'
        rendering_values = {
            'merchant_id': self.provider_id.asiapay_merchant_id,
            'amount': self.amount,
            'reference': self.reference,
            'currency_code': const.CURRENCY_MAPPING[self.provider_id.available_currency_ids[0].name],
            'mps_mode': 'SCP',
            'return_url': urls.urljoin(base_url, AsiaPayController._return_url),
            'payment_type': 'N',
            'language': get_language_code(lang),
            'payment_method': const.PAYMENT_METHODS_MAPPING.get(self.payment_method_id.code, 'ALL'),
        }
        rendering_values.update({
            'secure_hash': self.provider_id._asiapay_calculate_signature(
                rendering_values, incoming=False
            ),
            'api_url': self.provider_id._asiapay_get_api_url()
        })
        return rendering_values

    @api.model
    def _extract_reference(self, provider_code, payment_data):
        """Override of `payment` to extract the reference from the payment data."""
        if provider_code != 'asiapay':
            return super()._extract_reference(provider_code, payment_data)
        return payment_data.get('Ref')

    def _extract_amount_data(self, payment_data):
        """Override of `payment` to extract the amount and currency from the payment data."""
        if self.provider_code != 'asiapay':
            return super()._extract_amount_data(payment_data)

        amount = payment_data.get('Amt')
        # AsiaPay supports only one currency per account.
        currency_code = self.provider_id.available_currency_ids[0].name
        return {
            'amount': float(amount),
            'currency_code': currency_code,
        }

    def _apply_updates(self, payment_data):
        """Override of `payment' to update the transaction based on the payment data."""
        if self.provider_code != 'asiapay':
            return super()._apply_updates(payment_data)

        # Update the provider reference.
        self.provider_reference = payment_data.get('PayRef')

        # Update the payment method.
        payment_method_code = payment_data.get('payMethod')
        payment_method = self.env['payment.method']._get_from_code(
            payment_method_code, mapping=const.PAYMENT_METHODS_MAPPING
        )
        self.payment_method_id = payment_method or self.payment_method_id

        # Update the payment state.
        success_code = payment_data.get('successcode')
        primary_response_code = payment_data.get('prc')
        if not success_code:
            raise ValidationError(_("Received data with missing success code."))
        if success_code in const.SUCCESS_CODE_MAPPING['done']:
            self._set_done()
        elif success_code in const.SUCCESS_CODE_MAPPING['error']:
            self._set_error(_(
                "An error occurred during the processing of your payment (success code %(success_code)s; primary "
                "response code %(response_code)s). Please try again.", success_code=success_code, response_code=primary_response_code,
            ))
        else:
            _logger.warning(
                "Received data with invalid success code (%s) for transaction with primary response"
                " code %s and reference %s.", success_code, primary_response_code, self.reference
            )
            self._set_error(_("Unknown success code: %s", success_code))
