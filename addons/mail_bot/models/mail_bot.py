# Part of Odoo. See LICENSE file for full copyright and licensing details.

import itertools
import random

from markupsafe import Markup
from odoo import models, _


class MailBot(models.AbstractModel):
    _name = 'mail.bot'
    _description = 'Mail Bot'

    def _apply_logic(self, channel, values, command=None):
        """ Apply bot logic to generate an answer (or not) for the user
        The logic will only be applied if odoobot is in a chat with a user or
        if someone pinged odoobot.

         :param channel: the discuss channel where the user message was posted/odoobot will answer.
         :param values: msg_values of the message_post or other values needed by logic
         :param command: the name of the called command if the logic is not triggered by a message_post
        """
        channel.ensure_one()
        odoobot_id = self.env['ir.model.data']._xmlid_to_res_id("base.partner_root")
        if values.get("author_id") == odoobot_id or values.get("message_type") != "comment" and not command:
            return
        body = values.get("body", "").replace("\xa0", " ").strip().lower().strip(".!")
        if answer := self._get_answer(channel, body, values, command):
            answers = answer if isinstance(answer, list) else [answer]
            for ans in answers:
                channel.sudo().message_post(
                    author_id=odoobot_id,
                    body=ans,
                    message_type="comment",
                    silent=True,
                    subtype_xmlid="mail.mt_comment",
                )

    @staticmethod
    def _get_style_dict():
        return {
            "new_line": Markup("<br>"),
            "bold_start": Markup("<b>"),
            "bold_end": Markup("</b>"),
            "command_start": Markup("<span class='o_odoobot_command'>"),
            "command_end": Markup("</span>"),
            "document_link_start": Markup("<a href='https://www.odoo.com/documentation' target='_blank'>"),
            "document_link_end": Markup("</a>"),
            "slides_link_start": Markup("<a href='https://www.odoo.com/slides' target='_blank'>"),
            "slides_link_end": Markup("</a>"),
            "paperclip_icon": Markup("<i class='fa fa-paperclip' aria-hidden='true'/>"),
        }

    def _get_answer(self, channel, body, values, command=False):
        odoobot = self.env.ref("base.partner_root")
        # onboarding
        odoobot_state = self.env.user.odoobot_state

        if channel.channel_type == "chat" and odoobot in channel.channel_member_ids.partner_id:
            # main flow
            source = _("Thanks")
            description = _("This is a temporary canned response to see how canned responses work.")
            if odoobot_state == 'onboarding_emoji' and self._body_contains_emoji(body):
                self.env.user.odoobot_state = "onboarding_command"
                self.env.user.odoobot_failed = False
                return self.env._(
                    "Great! 👍%(new_line)sTo access special commands, %(bold_start)sstart your "
                    "sentence with%(bold_end)s %(command_start)s/%(command_end)s. Try getting "
                    "help.",
                    **self._get_style_dict()
                )
            elif odoobot_state == 'onboarding_command' and command == 'help':
                self.env.user.odoobot_state = "onboarding_ping"
                self.env.user.odoobot_failed = False
                return self.env._(
                    "Wow you are a natural!%(new_line)sPing someone with @username to grab their "
                    "attention. %(bold_start)sTry to ping me using%(bold_end)s "
                    "%(command_start)s@OdooBot%(command_end)s in a sentence.",
                    **self._get_style_dict()
                )
            elif odoobot_state == "onboarding_ping" and odoobot.id in values.get("partner_ids", []):
                self.env.user.odoobot_state = "onboarding_attachement"
                self.env.user.odoobot_failed = False
                return self.env._(
                    "Yep, I am here! 🎉 %(new_line)sNow, try %(bold_start)ssending an "
                    "attachment%(bold_end)s, like a picture of your cute dog...",
                    **self._get_style_dict()
                )
            elif odoobot_state == "onboarding_attachement" and values.get("attachment_ids"):
                self.env["mail.canned.response"].create({
                    "source": source,
                    "substitution": _("Thanks for your feedback. Goodbye!"),
                    "description": description,
                })
                self.env.user.odoobot_failed = False
                self.env.user.odoobot_state = "onboarding_canned"
                return self.env._(
                    "Wonderful! 😇%(new_line)sTry typing %(command_start)s::%(command_end)s to use "
                    "canned responses. I've created a temporary one for you.",
                    **self._get_style_dict()
                )
            elif odoobot_state == "onboarding_canned" and self.env.context.get("canned_response_ids"):
                self.env["mail.canned.response"].search([
                    ("create_uid", "=", self.env.user.id),
                    ("source", "=", source),
                    ("description", "=", description),
                ]).unlink()
                self.env.user.odoobot_failed = False
                self.env.user.odoobot_state = "idle"
                return [
                    self.env._(
                        "Great! You can customize %(bold_start)scanned responses%(bold_end)s in the Discuss app.",
                        **self._get_style_dict(),
                    ),
                    self.env._(
                        "That’s the end of this overview. You can %(bold_start)sclose this conversation%(bold_end)s or type "
                        "%(command_start)sstart the tour%(command_end)s to see it again. Enjoy exploring Odoo!",
                        **self._get_style_dict(),
                    ),
                ]
            # repeat question if needed
            elif odoobot_state == 'onboarding_canned' and not self._is_help_requested(body):
                self.env.user.odoobot_failed = True
                return self.env._(
                    "Not sure what you are doing. Please, type %(command_start)s:%(command_end)s "
                    "and wait for the propositions. Select one of them and press enter.",
                    **self._get_style_dict()
                )
            elif odoobot_state in (False, "idle", "not_initialized") and (_('start the tour') in body.lower()):
                self.env.user.odoobot_state = "onboarding_emoji"
                return _("To start, try to send me an emoji :)")
            # easter eggs
            elif odoobot_state == "idle" and body in ['❤️', _('i love you'), _('love')]:
                return _("Aaaaaw that's really cute but, you know, bots don't work that way. You're too human for me! Let's keep it professional ❤️")
            elif _('fuck') in body or "fuck" in body:
                return _("That's not nice! I'm a bot but I have feelings... 💔")
            # help message
            elif self._is_help_requested(body) or odoobot_state == 'idle':
                return self.env._(
                    "Unfortunately, I'm just a bot 😞 I don't understand! If you need help "
                    "discovering our product, please check %(document_link_start)sour "
                    "documentation%(document_link_end)s or %(slides_link_start)sour "
                    "videos%(slides_link_end)s.",
                    **self._get_style_dict()
                )
            else:
                # repeat question
                if odoobot_state == 'onboarding_emoji':
                    self.env.user.odoobot_failed = True
                    return self.env._(
                        "Not exactly. To continue the tour, send an emoji:"
                        " %(bold_start)stype%(bold_end)s%(command_start)s :)%(command_end)s and "
                        "press enter.",
                        **self._get_style_dict()
                    )
                elif odoobot_state == 'onboarding_attachement':
                    self.env.user.odoobot_failed = True
                    return self.env._(
                        "To %(bold_start)ssend an attachment%(bold_end)s, click on the "
                        "%(paperclip_icon)s icon and select a file.",
                        **self._get_style_dict()
                    )
                elif odoobot_state == 'onboarding_command':
                    self.env.user.odoobot_failed = True
                    return self.env._(
                        "Not sure what you are doing. Please, type "
                        "%(command_start)s/%(command_end)s and wait for the propositions."
                        " Select %(command_start)shelp%(command_end)s and press enter.",
                        **self._get_style_dict()
                    )
                elif odoobot_state == 'onboarding_ping':
                    self.env.user.odoobot_failed = True
                    return self.env._(
                        "Sorry, I am not listening. To get someone's attention, %(bold_start)sping "
                        "him%(bold_end)s. Write %(command_start)s@OdooBot%(command_end)s and select"
                        " me.",
                        **self._get_style_dict()
                    )
                return random.choice(
                    [
                        self.env._(
                            "I'm not smart enough to answer your question.%(new_line)sTo follow my "
                            "guide, ask: %(command_start)sstart the tour%(command_end)s.",
                            **self._get_style_dict()
                        ),
                        self.env._("Hmmm..."),
                        self.env._("I'm afraid I don't understand. Sorry!"),
                        self.env._(
                            "Sorry I'm sleepy. Or not! Maybe I'm just trying to hide my unawareness"
                            " of human language...%(new_line)sI can show you features if you write:"
                            " %(command_start)sstart the tour%(command_end)s.",
                            **self._get_style_dict()
                        ),
                    ]
                )
        return False

    def _body_contains_emoji(self, body):
        # coming from https://unicode.org/emoji/charts/full-emoji-list.html
        emoji_list = itertools.chain(
            range(0x231A, 0x231c),
            range(0x23E9, 0x23f4),
            range(0x23F8, 0x23fb),
            range(0x25AA, 0x25ac),
            range(0x25FB, 0x25ff),
            range(0x2600, 0x2605),
            range(0x2614, 0x2616),
            range(0x2622, 0x2624),
            range(0x262E, 0x2630),
            range(0x2638, 0x263b),
            range(0x2648, 0x2654),
            range(0x265F, 0x2661),
            range(0x2665, 0x2667),
            range(0x267E, 0x2680),
            range(0x2692, 0x2698),
            range(0x269B, 0x269d),
            range(0x26A0, 0x26a2),
            range(0x26AA, 0x26ac),
            range(0x26B0, 0x26b2),
            range(0x26BD, 0x26bf),
            range(0x26C4, 0x26c6),
            range(0x26D3, 0x26d5),
            range(0x26E9, 0x26eb),
            range(0x26F0, 0x26f6),
            range(0x26F7, 0x26fb),
            range(0x2708, 0x270a),
            range(0x270A, 0x270c),
            range(0x270C, 0x270e),
            range(0x2733, 0x2735),
            range(0x2753, 0x2756),
            range(0x2763, 0x2765),
            range(0x2795, 0x2798),
            range(0x2934, 0x2936),
            range(0x2B05, 0x2b08),
            range(0x2B1B, 0x2b1d),
            range(0x1F170, 0x1f172),
            range(0x1F191, 0x1f19b),
            range(0x1F1E6, 0x1f200),
            range(0x1F201, 0x1f203),
            range(0x1F232, 0x1f23b),
            range(0x1F250, 0x1f252),
            range(0x1F300, 0x1f321),
            range(0x1F324, 0x1f32d),
            range(0x1F32D, 0x1f330),
            range(0x1F330, 0x1f336),
            range(0x1F337, 0x1f37d),
            range(0x1F37E, 0x1f380),
            range(0x1F380, 0x1f394),
            range(0x1F396, 0x1f398),
            range(0x1F399, 0x1f39c),
            range(0x1F39E, 0x1f3a0),
            range(0x1F3A0, 0x1f3c5),
            range(0x1F3C6, 0x1f3cb),
            range(0x1F3CB, 0x1f3cf),
            range(0x1F3CF, 0x1f3d4),
            range(0x1F3D4, 0x1f3e0),
            range(0x1F3E0, 0x1f3f1),
            range(0x1F3F3, 0x1f3f6),
            range(0x1F3F8, 0x1f400),
            range(0x1F400, 0x1f43f),
            range(0x1F442, 0x1f4f8),
            range(0x1F4F9, 0x1f4fd),
            range(0x1F500, 0x1f53e),
            range(0x1F549, 0x1f54b),
            range(0x1F54B, 0x1f54f),
            range(0x1F550, 0x1f568),
            range(0x1F56F, 0x1f571),
            range(0x1F573, 0x1f57a),
            range(0x1F58A, 0x1f58e),
            range(0x1F595, 0x1f597),
            range(0x1F5B1, 0x1f5b3),
            range(0x1F5C2, 0x1f5c5),
            range(0x1F5D1, 0x1f5d4),
            range(0x1F5DC, 0x1f5df),
            range(0x1F5FB, 0x1f600),
            range(0x1F601, 0x1f611),
            range(0x1F612, 0x1f615),
            range(0x1F61C, 0x1f61f),
            range(0x1F620, 0x1f626),
            range(0x1F626, 0x1f628),
            range(0x1F628, 0x1f62c),
            range(0x1F62E, 0x1f630),
            range(0x1F630, 0x1f634),
            range(0x1F635, 0x1f641),
            range(0x1F641, 0x1f643),
            range(0x1F643, 0x1f645),
            range(0x1F645, 0x1f650),
            range(0x1F680, 0x1f6c6),
            range(0x1F6CB, 0x1f6d0),
            range(0x1F6D1, 0x1f6d3),
            range(0x1F6E0, 0x1f6e6),
            range(0x1F6EB, 0x1f6ed),
            range(0x1F6F4, 0x1f6f7),
            range(0x1F6F7, 0x1f6f9),
            range(0x1F910, 0x1f919),
            range(0x1F919, 0x1f91f),
            range(0x1F920, 0x1f928),
            range(0x1F928, 0x1f930),
            range(0x1F931, 0x1f933),
            range(0x1F933, 0x1f93b),
            range(0x1F93C, 0x1f93f),
            range(0x1F940, 0x1f946),
            range(0x1F947, 0x1f94c),
            range(0x1F94D, 0x1f950),
            range(0x1F950, 0x1f95f),
            range(0x1F95F, 0x1f96c),
            range(0x1F96C, 0x1f971),
            range(0x1F973, 0x1f977),
            range(0x1F97C, 0x1f980),
            range(0x1F980, 0x1f985),
            range(0x1F985, 0x1f992),
            range(0x1F992, 0x1f998),
            range(0x1F998, 0x1f9a3),
            range(0x1F9B0, 0x1f9ba),
            range(0x1F9C1, 0x1f9c3),
            range(0x1F9D0, 0x1f9e7),
            range(0x1F9E7, 0x1fa00),
            [0x2328, 0x23cf, 0x24c2, 0x25b6, 0x25c0, 0x260e, 0x2611, 0x2618, 0x261d, 0x2620, 0x2626,
             0x262a, 0x2640, 0x2642, 0x2663, 0x2668, 0x267b, 0x2699, 0x26c8, 0x26ce, 0x26cf,
             0x26d1, 0x26fd, 0x2702, 0x2705, 0x270f, 0x2712, 0x2714, 0x2716, 0x271d, 0x2721, 0x2728, 0x2744, 0x2747, 0x274c,
             0x274e, 0x2757, 0x27a1, 0x27b0, 0x27bf, 0x2b50, 0x2b55, 0x3030, 0x303d, 0x3297, 0x3299, 0x1f004, 0x1f0cf, 0x1f17e,
             0x1f17f, 0x1f18e, 0x1f21a, 0x1f22f, 0x1f321, 0x1f336, 0x1f37d, 0x1f3c5, 0x1f3f7, 0x1f43f, 0x1f440, 0x1f441, 0x1f4f8,
             0x1f4fd, 0x1f4ff, 0x1f57a, 0x1f587, 0x1f590, 0x1f5a4, 0x1f5a5, 0x1f5a8, 0x1f5bc, 0x1f5e1, 0x1f5e3, 0x1f5e8, 0x1f5ef,
             0x1f5f3, 0x1f5fa, 0x1f600, 0x1f611, 0x1f615, 0x1f616, 0x1f617, 0x1f618, 0x1f619, 0x1f61a, 0x1f61b, 0x1f61f, 0x1f62c,
             0x1f62d, 0x1f634, 0x1f6d0, 0x1f6e9, 0x1f6f0, 0x1f6f3, 0x1f6f9, 0x1f91f, 0x1f930, 0x1f94c, 0x1f97a, 0x1f9c0]
        )
        if any(chr(emoji) in body for emoji in emoji_list):
            return True
        return False

    def _is_help_requested(self, body):
        """Returns whether a message linking to the documentation and videos
        should be sent back to the user.
        """
        return any(token in body for token in ['help', _('help'), '?']) or self.env.user.odoobot_failed
