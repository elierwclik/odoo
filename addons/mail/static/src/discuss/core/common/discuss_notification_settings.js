import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class DiscussNotificationSettings extends Component {
    static props = {};
    static template = "mail.DiscussNotificationSettings";

    setup() {
        this.store = useService("mail.store");
        this.state = useState({
            selectedDuration: false,
        });
    }

    onChangeDisplayMuteDetails() {
        // set the default mute duration to forever when opens the mute details
        if (!this.store.settings.mute_until_dt) {
            const FOREVER = this.store.settings.MUTES.find((m) => m.label === "forever").value;
            this.store.settings.setMuteDuration(FOREVER);
            this.state.selectedDuration = FOREVER;
        } else {
            this.store.settings.setMuteDuration(false);
        }
    }

    onChangeMessageSound() {
        this.store.settings.messageSound = !this.store.settings.messageSound;
    }

    onChangeMuteDuration(ev) {
        if (ev.target.value === "default") {
            return;
        }
        this.store.settings.setMuteDuration(parseInt(ev.target.value));
        this.state.selectedDuration = parseInt(ev.target.value);
    }
}
