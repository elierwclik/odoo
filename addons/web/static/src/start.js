import { mountComponent } from "./env";
import { localization } from "@web/core/l10n/localization";
import { session } from "@web/session";
import { hasTouch } from "@web/core/browser/feature_detection";
import { user } from "@web/core/user";
import { Component, whenReady } from "@odoo/owl";
import { rpc } from "./core/network/rpc";
import { RPCCache } from "./core/network/rpc_cache";

/**
 * Function to start a webclient.
 * It is used both in community and enterprise in main.js.
 * It's meant to be webclient flexible so we can have a subclass of
 * webclient in enterprise with added features.
 *
 * @param {Component} Webclient
 */
export async function startWebClient(Webclient) {
    odoo.info = {
        db: session.db,
        server_version: session.server_version,
        server_version_info: session.server_version_info,
        isEnterprise: session.server_version_info.slice(-1)[0] === "e",
    };
    odoo.isReady = false;

    if (window.isSecureContext && session.browser_cache_secret) {
        rpc.setCache(new RPCCache("rpc", session.registry_hash, session.browser_cache_secret));
    }

    await whenReady();
    const app = await mountComponent(Webclient, document.body, { name: "Odoo Web Client" });
    const { env } = app;
    Component.env = env;

    const classList = document.body.classList;
    if (localization.direction === "rtl") {
        classList.add("o_rtl");
    }
    if (user.userId === 1) {
        classList.add("o_is_superuser");
    }
    if (env.debug) {
        classList.add("o_debug");
    }
    if (hasTouch()) {
        classList.add("o_touch_device");
    }
    // delete odoo.debug; // FIXME: some legacy code rely on this
    odoo.isReady = true;
}
