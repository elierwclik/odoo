# Part of Odoo. See LICENSE file for full copyright and licensing details.

from werkzeug.urls import url_encode, url_parse

from odoo import _
from odoo.exceptions import UserError
from odoo.http import request, route

from odoo.addons.website_sale.controllers import main


class WebsiteSale(main.WebsiteSale):

    @route()
    def pricelist(self, promo, reward_id=None, **post):
        if not (order_sudo := request.cart):
            return request.redirect('/shop')
        coupon_status = order_sudo._try_apply_code(promo)
        if coupon_status.get('not_found'):
            return super().pricelist(promo, **post)
        elif coupon_status.get('error'):
            request.session['error_promo_code'] = coupon_status['error']
        elif 'error' not in coupon_status:
            reward_successfully_applied = True
            if len(coupon_status) == 1:
                coupon, rewards = next(iter(coupon_status.items()))
                if len(rewards) == 1:
                    reward = rewards
                else:
                    reward = reward_id in rewards.ids and rewards.browse(reward_id)
                if reward and (not reward.multi_product or request.env.get('product_id')):
                    reward_successfully_applied = self._apply_reward(order_sudo, reward, coupon)

            if reward_successfully_applied:
                request.session['successful_code'] = promo
        return request.redirect(post.get('r', '/shop/cart'))

    @route(['/coupon/<string:code>'], type='http', auth='public', website=True, sitemap=False)
    def activate_coupon(self, code, r='/shop', **kw):
        url_parts = url_parse(r)
        url_query = url_parts.decode_query()
        url_query.pop('coupon_error', False)  # trust only Odoo error message
        url_query.pop('coupon_error_type', False)
        code = code.strip()

        request.session['pending_coupon_code'] = code
        if order_sudo := request.cart:
            result = order_sudo._try_pending_coupon()
            if isinstance(result, dict) and 'error' in result:
                url_query['coupon_error'] = result['error']
            else:
                url_query['notify_coupon'] = code
        else:
            url_query['coupon_error'] = _("The coupon will be automatically applied when you add something in your cart.")
            url_query['coupon_error_type'] = 'warning'
        redirect = url_parts.replace(query=url_encode(url_query))
        return request.redirect(redirect.to_url())

    @route('/shop/claimreward', type='http', auth='public', website=True, sitemap=False)
    def claim_reward(self, reward_id, code=None, **post):
        redirect = post.get('r', '/shop/cart')
        if not (order_sudo := request.cart):
            return request.redirect(redirect)

        try:
            reward_id = int(reward_id)
        except ValueError:
            reward_id = None

        reward_sudo = request.env['loyalty.reward'].sudo().browse(reward_id).exists()
        if not reward_sudo:
            return request.redirect(redirect)

        if reward_sudo.multi_product and 'product_id' in post:
            request.update_context(product_id=int(post['product_id']))
        else:
            request.redirect(redirect)

        program_sudo = reward_sudo.program_id
        claimable_rewards = order_sudo._get_claimable_and_showable_rewards()
        coupon = request.env['loyalty.card']
        for coupon_, rewards in claimable_rewards.items():
            if reward_sudo in rewards:
                coupon = coupon_
                if code == coupon.code and (
                    (program_sudo.trigger == 'with_code' and program_sudo.program_type != 'promo_code')
                    or (program_sudo.trigger == 'auto'
                        and program_sudo.applies_on == 'future'
                        and program_sudo.program_type not in ('ewallet', 'loyalty'))
                ):
                    return self.pricelist(code, reward_id=reward_id)
        if coupon:
            self._apply_reward(order_sudo, reward_sudo, coupon)
        return request.redirect(redirect)

    def _apply_reward(self, order, reward, coupon):
        """Try to apply the given program reward

        :returns: whether the reward was successfully applied
        :rtype: bool
        """
        product_id = request.env.context.get('product_id')
        product = product_id and request.env['product.product'].sudo().browse(product_id)
        try:
            reward_status = order._apply_program_reward(reward, coupon, product=product)
        except UserError as e:
            request.session['error_promo_code'] = str(e)
            return False
        if 'error' in reward_status:
            request.session['error_promo_code'] = reward_status['error']
            return False
        order._update_programs_and_rewards()
        if order.carrier_id.free_over and not reward.program_id.is_payment_program:
            # update shiping cost if it's `free_over` and reward isn't eWallet or gift card
            # will call `_update_programs_and_rewards` again, updating applied eWallet/gift cards
            res = order.carrier_id.rate_shipment(order)
            if res.get('success'):
                order.set_delivery_line(order.carrier_id, res['price'])
            else:
                order._remove_delivery_line()
        return True
