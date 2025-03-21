import { onWebsocketEvent } from "@bus/../tests/mock_websocket";
import {
    click,
    contains,
    defineMailModels,
    insertText,
    openDiscuss,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { describe, test } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";
import { asyncStep, getService, waitForSteps } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
defineMailModels();

test("Member list and Pinned Messages Panel menu are exclusive", async () => {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({ name: "General" });
    await start();
    await openDiscuss(channelId);
    await contains(".o-discuss-ChannelMemberList"); // member list open by default
    await click("[title='Pinned Messages']");
    await contains(".o-discuss-PinnedMessagesPanel");
    await contains(".o-discuss-ChannelMemberList", { count: 0 });
});

test("bus subscription is refreshed when channel is joined", async () => {
    const pyEnv = await startServer();
    pyEnv["discuss.channel"].create([{ name: "General" }, { name: "Sales" }]);
    onWebsocketEvent("subscribe", (data) => {
        asyncStep(`subscribe - ${JSON.stringify(data.channels)}`);
    });
    const later = luxon.DateTime.now().plus({ seconds: 2 });
    mockDate(
        `${later.year}-${later.month}-${later.day} ${later.hour}:${later.minute}:${later.second}`
    );
    await start();
    const expectedSubscribes = [];
    for (const { type, id } of getService("mail.store").imStatusTrackedPersonas) {
        const model = type === "partner" ? "res.partner" : "mail.guest";
        expectedSubscribes.unshift(`"odoo-presence-${model}_${id}"`);
    }
    await waitForSteps([`subscribe - [${expectedSubscribes.join(",")}]`]);
    await openDiscuss();
    await waitForSteps([]);
    await click("input[placeholder='Find or start a conversation']");
    await insertText("input[placeholder='Search a conversation']", "new channel");
    await click("a", { text: "Create Channel" });
    await contains(".o-mail-DiscussSidebar-item", { text: "new channel" });
    const [newChannel] = pyEnv["discuss.channel"].search([["name", "=", "new channel"]]);
    expectedSubscribes.unshift(`"discuss.channel_${newChannel}"`);
    await waitForSteps([
        `subscribe - [${expectedSubscribes.join(",")}]`,
        `subscribe - [${expectedSubscribes.join(",")}]`, // 1 is enough. The 2 comes from technical details (1: from channel_join, 2: from channel open), 2nd covers shadowing
    ]);
});

test("bus subscription is refreshed when channel is left", async () => {
    const pyEnv = await startServer();
    pyEnv["discuss.channel"].create({ name: "General" });
    onWebsocketEvent("subscribe", (data) => {
        asyncStep(`subscribe - ${JSON.stringify(data.channels)}`);
    });
    const later = luxon.DateTime.now().plus({ seconds: 2 });
    mockDate(
        `${later.year}-${later.month}-${later.day} ${later.hour}:${later.minute}:${later.second}`
    );
    const env = await start();
    const imStatusChannels = [];
    for (const { type, id } of env.services["mail.store"].imStatusTrackedPersonas) {
        const model = type === "partner" ? "res.partner" : "mail.guest";
        imStatusChannels.unshift(`"odoo-presence-${model}_${id}"`);
    }
    await waitForSteps([`subscribe - [${imStatusChannels.join(",")}]`]);
    await openDiscuss();
    await waitForSteps([]);
    await click("[title='Leave Channel']");
    await waitForSteps([`subscribe - [${imStatusChannels.join(",")}]`]);
});
