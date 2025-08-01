import { _t } from "@web/core/l10n/translation";
import { messageActionsRegistry } from "@mail/core/common/message_actions";

messageActionsRegistry.add("pin", {
    condition: (component) =>
        component.store.self_partner && component.props.thread?.model === "discuss.channel",
    icon: "fa fa-thumb-tack",
    title: (component) => (component.props.message.pinned_at ? _t("Unpin") : _t("Pin")),
    onClick: (component) => component.props.message.pin(),
    sequence: 65,
});
