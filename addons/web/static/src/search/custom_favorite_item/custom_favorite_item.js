import { _t } from "@web/core/l10n/translation";
import { AccordionItem } from "@web/core/dropdown/accordion_item";
import { CheckBox } from "@web/core/checkbox/checkbox";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { Component, useRef, useState } from "@odoo/owl";

const favoriteMenuRegistry = registry.category("favoriteMenu");

export class CustomFavoriteItem extends Component {
    static template = "web.CustomFavoriteItem";
    static components = { CheckBox, AccordionItem };
    static props = {};

    setup() {
        this.actionService = useService("action");
        this.notificationService = useService("notification");
        this.descriptionRef = useRef("description");
        this.state = useState({
            description: this.env.config.getDisplayName(),
            isDefault: false,
        });
    }

    /**
     * @param {Event} ev
     */
    async saveFavorite(ev, isShared = false) {
        if (!this.state.description) {
            this.notificationService.add(_t("A name for your favorite filter is required."), {
                type: "danger",
            });
            ev.stopPropagation();
            this.descriptionRef.el.focus();
            return false;
        }
        const { description, isDefault } = this.state;
        const embeddedActionId = this.env.config.currentEmbeddedActionId || false;
        const serverSideId = await this.env.searchModel.createNewFavorite({
            description,
            isDefault,
            isShared,
            embeddedActionId,
        });

        Object.assign(this.state, {
            description: this.env.config.getDisplayName(),
            isDefault: false,
        });
        return serverSideId;
    }

    /**
     * @param {Event} ev
     */
    async editFavorite(ev) {
        const serverSideId = await this.saveFavorite(ev);
        if (!serverSideId) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "ir.filters",
            views: [[false, "form"]],
            context: {
                form_view_ref: "base.ir_filters_view_edit_form",
            },
            res_id: serverSideId,
        });
    }

    /**
     * @param {KeyboardEvent} ev
     */
    onInputKeydown(ev) {
        switch (ev.key) {
            case "Enter":
                ev.preventDefault();
                this.saveFavorite(ev);
                break;
            case "Escape":
                // Gives the focus back to the component.
                ev.preventDefault();
                ev.target.blur();
                break;
        }
    }
}

favoriteMenuRegistry.add(
    "custom-favorite-item",
    { Component: CustomFavoriteItem, groupNumber: 3 },
    { sequence: 0 }
);
