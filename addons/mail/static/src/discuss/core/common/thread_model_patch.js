import { fields } from "@mail/core/common/record";
import { Thread } from "@mail/core/common/thread_model";
import { useSequential } from "@mail/utils/common/hooks";
import { compareDatetime, nearestGreaterThanOrEqual } from "@mail/utils/common/misc";

import { formatList } from "@web/core/l10n/utils";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { Deferred } from "@web/core/utils/concurrency";
import { patch } from "@web/core/utils/patch";
import { imageUrl } from "@web/core/utils/urls";

const commandRegistry = registry.category("discuss.channel_commands");

/** @type {typeof Thread} */
const threadStaticPatch = {
    async getOrFetch(data, fieldNames = []) {
        if (data.model !== "discuss.channel" || data.id < 1) {
            return super.getOrFetch(...arguments);
        }
        const thread = this.insert({ id: data.id, model: data.model });
        if (thread.fetchChannelInfoState === "fetched") {
            return Promise.resolve(thread);
        }
        if (thread.fetchChannelInfoState === "fetching") {
            return thread.fetchChannelInfoDeferred;
        }
        thread.fetchChannelInfoState = "fetching";
        const def = new Deferred();
        thread.fetchChannelInfoDeferred = def;
        this.store.fetchChannel(thread.id).then(
            () => {
                if (thread.exists()) {
                    thread.fetchChannelInfoState = "fetched";
                    thread.fetchChannelInfoDeferred = undefined;
                    def.resolve(thread);
                } else {
                    def.resolve();
                }
            },
            () => {
                if (thread.exists()) {
                    thread.fetchChannelInfoState = "not_fetched";
                    thread.fetchChannelInfoDeferred = undefined;
                    def.reject(thread);
                } else {
                    def.reject();
                }
            }
        );
        return def;
    },
};
patch(Thread, threadStaticPatch);

/** @type {import("models").Thread} */
const threadPatch = {
    setup() {
        super.setup();
        this.channel_member_ids = fields.Many("discuss.channel.member", {
            inverse: "channel_id",
            onDelete: (r) => r.delete(),
            sort: (m1, m2) => m1.id - m2.id,
        });
        this.correspondent = fields.One("discuss.channel.member", {
            /** @this {import("models").Thread} */
            compute() {
                return this.computeCorrespondent();
            },
        });
        this.correspondentCountry = fields.One("res.country", {
            /** @this {import("models").Thread} */
            compute() {
                return this.correspondent?.persona?.country_id ?? this.country_id;
            },
        });
        /** @type {"video_full_screen"|undefined} */
        this.default_display_mode = undefined;
        /** @type {Deferred<Thread|undefined>} */
        this.fetchChannelInfoDeferred = undefined;
        /** @type {"not_fetched"|"fetching"|"fetched"} */
        this.fetchChannelInfoState = "not_fetched";
        this.group_ids = fields.Many("res.groups");
        this.hasOtherMembersTyping = fields.Attr(false, {
            /** @this {import("models").Thread} */
            compute() {
                return this.otherTypingMembers.length > 0;
            },
        });
        this.hasSeenFeature = fields.Attr(false, {
            /** @this {import("models").Thread} */
            compute() {
                return this.store.channel_types_with_seen_infos.includes(this.channel_type);
            },
        });
        this.firstUnreadMessage = fields.One("mail.message", {
            /** @this {import("models").Thread} */
            compute() {
                if (!this.selfMember) {
                    return null;
                }
                const messages = this.messages.filter((m) => !m.isNotification);
                const separator = this.selfMember.new_message_separator_ui;
                if (separator === 0 && !this.loadOlder) {
                    return messages[0];
                }
                if (!separator || messages.length === 0 || messages.at(-1).id < separator) {
                    return null;
                }
                // try to find a perfect match according to the member's separator
                let message = this.store["mail.message"].get({ id: separator });
                if (!message || this.notEq(message.thread)) {
                    message = nearestGreaterThanOrEqual(messages, separator, (msg) => msg.id);
                }
                return message;
            },
            inverse: "threadAsFirstUnread",
        });
        this.invited_member_ids = fields.Many("discuss.channel.member");
        this.last_interest_dt = fields.Datetime();
        this.lastInterestDt = fields.Datetime({
            /** @this {import("models").Thread} */
            compute() {
                const selfMemberLastInterestDt = this.selfMember?.last_interest_dt;
                const lastInterestDt = this.last_interest_dt;
                return compareDatetime(selfMemberLastInterestDt, lastInterestDt) > 0
                    ? selfMemberLastInterestDt
                    : lastInterestDt;
            },
        });
        this.lastMessageSeenByAllId = fields.Attr(undefined, {
            /** @this {import("models").Thread} */
            compute() {
                if (!this.hasSeenFeature) {
                    return;
                }
                return this.channel_member_ids.reduce((lastMessageSeenByAllId, member) => {
                    if (member.persona.notEq(this.store.self) && member.seen_message_id) {
                        return lastMessageSeenByAllId
                            ? Math.min(lastMessageSeenByAllId, member.seen_message_id.id)
                            : member.seen_message_id.id;
                    } else {
                        return lastMessageSeenByAllId;
                    }
                }, undefined);
            },
        });
        this.lastSelfMessageSeenByEveryone = fields.One("mail.message", {
            compute() {
                if (!this.lastMessageSeenByAllId) {
                    return false;
                }
                let res;
                // starts from most recent persistent messages to find early
                for (let i = this.persistentMessages.length - 1; i >= 0; i--) {
                    const message = this.persistentMessages[i];
                    if (!message.isSelfAuthored) {
                        continue;
                    }
                    if (message.id > this.lastMessageSeenByAllId) {
                        continue;
                    }
                    res = message;
                    break;
                }
                return res;
            },
        });
        this.markReadSequential = useSequential();
        this.markedAsUnread = false;
        this.markingAsRead = false;
        /** @type {number|undefined} */
        this.member_count = undefined;
        /** @type {string} name: only for channel. For generic thread, @see display_name */
        this.name = undefined;
        this.onlineMembers = fields.Many("discuss.channel.member", {
            /** @this {import("models").Thread} */
            compute() {
                return this.channel_member_ids
                    .filter((member) => this.store.onlineMemberStatuses.includes(member.im_status))
                    .sort((m1, m2) => this.store.sortMembers(m1, m2)); // FIXME: sort are prone to infinite loop (see test "Display livechat custom name in typing status")
            },
        });
        this.offlineMembers = fields.Many("discuss.channel.member", {
            compute() {
                return this._computeOfflineMembers().sort(
                    (m1, m2) => this.store.sortMembers(m1, m2) // FIXME: sort are prone to infinite loop (see test "Display livechat custom name in typing status")
                );
            },
        });
        this.otherTypingMembers = fields.Many("discuss.channel.member", {
            /** @this {import("models").Thread} */
            compute() {
                return this.typingMembers.filter((member) => !member.persona?.eq(this.store.self));
            },
        });
        this.selfMember = fields.One("discuss.channel.member", {
            inverse: "threadAsSelf",
        });
        this.scrollUnread = true;
        this.toggleBusSubscription = fields.Attr(false, {
            /** @this {import("models").Thread} */
            compute() {
                return (
                    this.model === "discuss.channel" &&
                    this.selfMember?.memberSince >= this.store.env.services.bus_service.startedAt
                );
            },
            onUpdate() {
                this.store.updateBusSubscription();
            },
        });
        this.typingMembers = fields.Many("discuss.channel.member", { inverse: "threadAsTyping" });
    },
    /** @returns {import("models").ChannelMember[]} */
    _computeOfflineMembers() {
        return this.channel_member_ids.filter(
            (member) => !this.store.onlineMemberStatuses.includes(member.im_status)
        );
    },
    get areAllMembersLoaded() {
        return this.member_count === this.channel_member_ids.length;
    },
    get avatarUrl() {
        if (this.channel_type === "channel" || this.channel_type === "group") {
            return imageUrl("discuss.channel", this.id, "avatar_128", {
                unique: this.avatar_cache_key,
            });
        }
        if (this.channel_type === "chat" && this.correspondent) {
            return this.correspondent.avatarUrl;
        }
        return super.avatarUrl;
    },
    get showCorrespondentCountry() {
        return false;
    },
    /** @returns {import("models").ChannelMember} */
    computeCorrespondent() {
        if (this.channel_type === "channel") {
            return undefined;
        }
        const correspondents = this.correspondents;
        if (correspondents.length === 1) {
            // 2 members chat.
            return correspondents[0];
        }
        if (correspondents.length === 0 && this.channel_member_ids.length === 1) {
            // Self-chat.
            return this.channel_member_ids[0];
        }
        return undefined;
    },
    /** @returns {import("models").ChannelMember[]} */
    get correspondents() {
        return this.channel_member_ids.filter(({ persona }) => persona?.notEq(this.store.self));
    },
    get displayName() {
        if (this.supportsCustomChannelName && this.selfMember?.custom_channel_name) {
            return this.selfMember.custom_channel_name;
        }
        if (this.channel_type === "chat" && this.correspondent) {
            return this.correspondent.name;
        }
        if (this.channel_type === "group" && !this.name) {
            return formatList(this.channel_member_ids.map((channelMember) => channelMember.name));
        }
        if (this.model === "discuss.channel" && this.name) {
            return this.name;
        }
        return super.displayName;
    },
    async fetchChannelMembers() {
        if (this.fetchMembersState === "pending") {
            return;
        }
        const previousState = this.fetchMembersState;
        this.fetchMembersState = "pending";
        const known_member_ids = this.channel_member_ids.map((channelMember) => channelMember.id);
        let data;
        try {
            data = await rpc("/discuss/channel/members", {
                channel_id: this.id,
                known_member_ids: known_member_ids,
            });
        } catch (e) {
            this.fetchMembersState = previousState;
            throw e;
        }
        this.fetchMembersState = "fetched";
        this.store.insert(data);
    },
    async fetchMoreAttachments(limit = 30) {
        if (this.isLoadingAttachments || this.areAttachmentsLoaded) {
            return;
        }
        this.isLoadingAttachments = true;
        try {
            const data = await rpc("/discuss/channel/attachments", {
                before: Math.min(...this.attachments.map(({ id }) => id)),
                channel_id: this.id,
                limit,
            });
            const { "ir.attachment": attachments = [] } = this.store.insert(data);
            if (attachments.length < limit) {
                this.areAttachmentsLoaded = true;
            }
        } finally {
            this.isLoadingAttachments = false;
        }
    },
    get hasMemberList() {
        return ["channel", "group"].includes(this.channel_type);
    },
    get hasSelfAsMember() {
        return Boolean(this.selfMember);
    },
    /** @override */
    get importantCounter() {
        if (this.isChatChannel && this.selfMember?.message_unread_counter_ui) {
            return this.selfMember.message_unread_counter_ui;
        }
        return super.importantCounter;
    },
    /** @override */
    isDisplayedOnUpdate() {
        super.isDisplayedOnUpdate(...arguments);
        if (!this.selfMember) {
            return;
        }
        if (!this.isDisplayed) {
            this.selfMember.new_message_separator_ui = this.selfMember.new_message_separator;
            this.markedAsUnread = false;
        }
    },
    get isUnread() {
        return this.selfMember?.message_unread_counter > 0 || super.isUnread;
    },
    /** @override */
    markAsRead() {
        super.markAsRead(...arguments);
        if (!this.selfMember) {
            return;
        }
        const newestPersistentMessage = this.newestPersistentOfAllMessage;
        if (!newestPersistentMessage) {
            return;
        }
        const alreadyReadBySelf =
            this.selfMember.seen_message_id?.id >= newestPersistentMessage.id &&
            this.selfMember.new_message_separator > newestPersistentMessage.id;
        if (alreadyReadBySelf) {
            return;
        }
        this.markReadSequential(async () => {
            this.markingAsRead = true;
            return rpc(
                "/discuss/channel/mark_as_read",
                {
                    channel_id: this.id,
                    last_message_id: newestPersistentMessage.id,
                },
                { silent: true }
            ).catch((e) => {
                if (e.code !== 404) {
                    throw e;
                }
            });
        }).then(() => (this.markingAsRead = false));
    },
    /**
     * To be overridden.
     * The purpose is to exclude technical channel_member_ids like bots and avoid
     * "wrong" seen message indicator
     * @returns {import("models").ChannelMember[]}
     */
    get membersThatCanSeen() {
        return this.channel_member_ids;
    },
    /** @override */
    get needactionCounter() {
        return this.isChatChannel
            ? this.selfMember?.message_unread_counter ?? 0
            : super.needactionCounter;
    },
    /** @override */
    onNewSelfMessage(message) {
        if (!this.selfMember || message.id < this.selfMember.seen_message_id?.id) {
            return;
        }
        this.selfMember.seen_message_id = message;
        this.selfMember.new_message_separator = message.id + 1;
        this.selfMember.new_message_separator_ui = this.selfMember.new_message_separator;
        this.markedAsUnread = false;
    },
    /** @param {string} body */
    async post(body) {
        if (this.model === "discuss.channel" && body.startsWith("/")) {
            const [firstWord] = body.substring(1).split(/\s/);
            const command = commandRegistry.get(firstWord, false);
            if (
                command &&
                (!command.channel_types || command.channel_types.includes(this.channel_type))
            ) {
                await this.executeCommand(command, body);
                return;
            }
        }
        return super.post(...arguments);
    },
    get showUnreadBanner() {
        return this.selfMember?.message_unread_counter_ui > 0;
    },
    get unknownMembersCount() {
        return (this.member_count ?? 0) - this.channel_member_ids.length;
    },
};
patch(Thread.prototype, threadPatch);
