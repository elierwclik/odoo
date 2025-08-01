import { debounce, Deferred, Logger } from "@bus/workers/bus_worker_utils";

/**
 * Type of events that can be sent from the worker to its clients.
 *
 * @typedef { 'BUS:CONNECT' | 'BUS:RECONNECT' | 'BUS:DISCONNECT' | 'BUS:RECONNECTING' | 'BUS:NOTIFICATION' | 'BUS:INITIALIZED' | 'BUS:OUTDATED'| 'BUS:WORKER_STATE_UPDATED' | 'BUS:PROVIDE_LOGS' } WorkerEvent
 */

/**
 * Type of action that can be sent from the client to the worker.
 *
 * @typedef {'BUS:ADD_CHANNEL' | 'BUS:DELETE_CHANNEL' | 'BUS:FORCE_UPDATE_CHANNELS' | 'BUS:INITIALIZE_CONNECTION' | 'BUS:REQUEST_LOGS' | 'BUS:SEND' | 'BUS:SET_LOGGING_ENABLED' | 'BUS:LEAVE' | 'BUS:STOP' | 'BUS:START'} WorkerAction
 */

export const WEBSOCKET_CLOSE_CODES = Object.freeze({
    CLEAN: 1000,
    GOING_AWAY: 1001,
    PROTOCOL_ERROR: 1002,
    INCORRECT_DATA: 1003,
    ABNORMAL_CLOSURE: 1006,
    INCONSISTENT_DATA: 1007,
    MESSAGE_VIOLATING_POLICY: 1008,
    MESSAGE_TOO_BIG: 1009,
    EXTENSION_NEGOTIATION_FAILED: 1010,
    SERVER_ERROR: 1011,
    RESTART: 1012,
    TRY_LATER: 1013,
    BAD_GATEWAY: 1014,
    SESSION_EXPIRED: 4001,
    KEEP_ALIVE_TIMEOUT: 4002,
    RECONNECTING: 4003,
});
export const WORKER_STATE = Object.freeze({
    CONNECTED: "CONNECTED",
    DISCONNECTED: "DISCONNECTED",
    IDLE: "IDLE",
    CONNECTING: "CONNECTING",
});
const MAXIMUM_RECONNECT_DELAY = 60000;
const UUID = Date.now().toString(36) + Math.random().toString(36).substring(2);
const logger = new Logger("bus_websocket_worker");

/**
 * This class regroups the logic necessary in order for the
 * SharedWorker/Worker to work. Indeed, Safari and some minor browsers
 * do not support SharedWorker. In order to solve this issue, a Worker
 * is used in this case. The logic is almost the same than the one used
 * for SharedWorker and this class implements it.
 */
export class WebsocketWorker {
    INITIAL_RECONNECT_DELAY = 1000;
    RECONNECT_JITTER = 1000;

    constructor(name) {
        this.name = name;
        // Timestamp of start of most recent bus service sender
        this.newestStartTs = undefined;
        this.websocketURL = "";
        this.currentUID = null;
        this.currentDB = null;
        this.isWaitingForNewUID = true;
        this.channelsByClient = new Map();
        this.connectRetryDelay = this.INITIAL_RECONNECT_DELAY;
        this.connectTimeout = null;
        this.debugModeByClient = new Map();
        this.isDebug = false;
        this.active = true;
        this.state = WORKER_STATE.IDLE;
        this.isReconnecting = false;
        this.lastChannelSubscription = null;
        this.loggingEnabled = null;
        this.firstSubscribeDeferred = new Deferred();
        this.lastNotificationId = 0;
        this.messageWaitQueue = [];
        this._forceUpdateChannels = debounce(this._forceUpdateChannels, 300);
        this._debouncedUpdateChannels = debounce(this._updateChannels, 300);
        this._debouncedSendToServer = debounce(this._sendToServer, 300);

        this._onWebsocketClose = this._onWebsocketClose.bind(this);
        this._onWebsocketError = this._onWebsocketError.bind(this);
        this._onWebsocketMessage = this._onWebsocketMessage.bind(this);
        this._onWebsocketOpen = this._onWebsocketOpen.bind(this);

        globalThis.addEventListener("error", ({ error }) => {
            const params = error instanceof Error ? [error.constructor.name, error.stack] : [error];
            this._logDebug("Unhandled error", ...params);
        });
        globalThis.addEventListener("unhandledrejection", ({ reason }) => {
            const params =
                reason instanceof Error ? [reason.constructor.name, reason.stack] : [reason];
            this._logDebug("Unhandled rejection", params);
        });
    }

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Send the message to all the clients that are connected to the
     * worker.
     *
     * @param {WorkerEvent} type Event to broadcast to connected
     * clients.
     * @param {Object} data
     */
    broadcast(type, data) {
        this._logDebug("broadcast", type, data);
        for (const client of this.channelsByClient.keys()) {
            client.postMessage({ type, data: data ? JSON.parse(JSON.stringify(data)) : undefined });
        }
    }

    /**
     * Register a client handled by this worker.
     *
     * @param {MessagePort} messagePort
     */
    registerClient(messagePort) {
        messagePort.addEventListener("message", (ev) => {
            this._onClientMessage(messagePort, ev.data);
        });
        this.channelsByClient.set(messagePort, []);
    }

    /**
     * Send message to the given client.
     *
     * @param {number} client
     * @param {WorkerEvent} type
     * @param {Object} data
     */
    sendToClient(client, type, data) {
        if (type !== "BUS:PROVIDE_LOGS") {
            this._logDebug("sendToClient", type, data);
        }
        client.postMessage({ type, data: data ? JSON.parse(JSON.stringify(data)) : undefined });
    }

    //--------------------------------------------------------------------------
    // PRIVATE
    //--------------------------------------------------------------------------

    /**
     * Called when a message is posted to the worker by a client (i.e. a
     * MessagePort connected to this worker).
     *
     * @param {MessagePort} client
     * @param {Object} message
     * @param {WorkerAction} [message.action]
     * Action to execute.
     * @param {Object|undefined} [message.data] Data required by the
     * action.
     */
    _onClientMessage(client, { action, data }) {
        this._logDebug("_onClientMessage", action, data);
        switch (action) {
            case "BUS:SEND": {
                if (data["event_name"] === "update_presence") {
                    this._debouncedSendToServer(data);
                } else {
                    this._sendToServer(data);
                }
                return;
            }
            case "BUS:START":
                return this._start();
            case "BUS:STOP":
                return this._stop();
            case "BUS:LEAVE":
                return this._unregisterClient(client);
            case "BUS:ADD_CHANNEL":
                return this._addChannel(client, data);
            case "BUS:DELETE_CHANNEL":
                return this._deleteChannel(client, data);
            case "BUS:FORCE_UPDATE_CHANNELS":
                return this._forceUpdateChannels();
            case "BUS:SET_LOGGING_ENABLED":
                this.loggingEnabled = data;
                break;
            case "BUS:REQUEST_LOGS":
                logger.getLogs().then((logs) => {
                    const workerInfo = {
                        UUID,
                        active: this.active,
                        channels: [
                            ...new Set([].concat.apply([], [...this.channelsByClient.values()])),
                        ].sort(),
                        db: this.currentDB,
                        is_reconnecting: this.isReconnecting,
                        last_subscription: this.lastChannelSubscription,
                        name: this.name,
                        number_of_clients: this.channelsByClient.size,
                        reconnect_delay: this.connectRetryDelay,
                        uid: this.currentUID,
                        websocket_url: this.websocketURL,
                    };
                    this.sendToClient(client, "BUS:PROVIDE_LOGS", { workerInfo, logs });
                });
                break;
            case "BUS:INITIALIZE_CONNECTION":
                return this._initializeConnection(client, data);
        }
    }

    /**
     * Add a channel for the given client. If this channel is not yet
     * known, update the subscription on the server.
     *
     * @param {MessagePort} client
     * @param {string} channel
     */
    _addChannel(client, channel) {
        const clientChannels = this.channelsByClient.get(client);
        if (!clientChannels.includes(channel)) {
            clientChannels.push(channel);
            this.channelsByClient.set(client, clientChannels);
            this._debouncedUpdateChannels();
        }
    }

    /**
     * Remove a channel for the given client. If this channel is not
     * used anymore, update the subscription on the server.
     *
     * @param {MessagePort} client
     * @param {string} channel
     */
    _deleteChannel(client, channel) {
        const clientChannels = this.channelsByClient.get(client);
        if (!clientChannels) {
            return;
        }
        const channelIndex = clientChannels.indexOf(channel);
        if (channelIndex !== -1) {
            clientChannels.splice(channelIndex, 1);
            this._debouncedUpdateChannels();
        }
    }

    /**
     * Update the channels on the server side even if the channels on
     * the client side are the same than the last time we subscribed.
     */
    _forceUpdateChannels() {
        this._updateChannels({ force: true });
    }

    /**
     * Remove the given client from this worker client list as well as
     * its channels. If some of its channels are not used anymore,
     * update the subscription on the server.
     *
     * @param {MessagePort} client
     */
    _unregisterClient(client) {
        this.channelsByClient.delete(client);
        this.debugModeByClient.delete(client);
        this.isDebug = [...this.debugModeByClient.values()].some(Boolean);
        this._debouncedUpdateChannels();
    }

    /**
     * Initialize a client connection to this worker.
     *
     * @param {Object} param0
     * @param {string} [param0.db] Database name.
     * @param {String} [param0.debug] Current debugging mode for the
     * given client.
     * @param {Number} [param0.lastNotificationId] Last notification id
     * known by the client.
     * @param {String} [param0.websocketURL] URL of the websocket endpoint.
     * @param {Number|false|undefined} [param0.uid] Current user id
     *     - Number: user is logged whether on the frontend/backend.
     *     - false: user is not logged.
     *     - undefined: not available (e.g. livechat support page)
     * @param {Number} param0.startTs Timestamp of start of bus service sender.
     */
    _initializeConnection(client, { db, debug, lastNotificationId, uid, websocketURL, startTs }) {
        if (this.newestStartTs && this.newestStartTs > startTs) {
            this.debugModeByClient.set(client, debug);
            this.isDebug = [...this.debugModeByClient.values()].some(Boolean);
            this.sendToClient(client, "BUS:WORKER_STATE_UPDATED", this.state);
            this.sendToClient(client, "BUS:INITIALIZED");
            return;
        }
        this.newestStartTs = startTs;
        this.websocketURL = websocketURL;
        this.lastNotificationId = lastNotificationId;
        this.debugModeByClient.set(client, debug);
        this.isDebug = [...this.debugModeByClient.values()].some(Boolean);
        const isCurrentUserKnown = uid !== undefined;
        if (this.isWaitingForNewUID && isCurrentUserKnown) {
            this.isWaitingForNewUID = false;
            this.currentUID = uid;
        }
        if ((this.currentUID !== uid && isCurrentUserKnown) || this.currentDB !== db) {
            this.currentUID = uid;
            this.currentDB = db;
            if (this.websocket) {
                this.websocket.close(WEBSOCKET_CLOSE_CODES.CLEAN);
            }
            this.channelsByClient.forEach((_, key) => this.channelsByClient.set(key, []));
        }
        this.sendToClient(client, "BUS:WORKER_STATE_UPDATED", this.state);
        this.sendToClient(client, "BUS:INITIALIZED");
        if (!this.active) {
            this.sendToClient(client, "BUS:OUTDATED");
        }
    }

    /**
     * Determine whether or not the websocket associated to this worker
     * is connected.
     *
     * @returns {boolean}
     */
    _isWebsocketConnected() {
        return this.websocket && this.websocket.readyState === 1;
    }

    /**
     * Determine whether or not the websocket associated to this worker
     * is connecting.
     *
     * @returns {boolean}
     */
    _isWebsocketConnecting() {
        return this.websocket && this.websocket.readyState === 0;
    }

    /**
     * Determine whether or not the websocket associated to this worker
     * is in the closing state.
     *
     * @returns {boolean}
     */
    _isWebsocketClosing() {
        return this.websocket && this.websocket.readyState === 2;
    }

    /**
     * Triggered when a connection is closed. If closure was not clean ,
     * try to reconnect after indicating to the clients that the
     * connection was closed.
     *
     * @param {CloseEvent} ev
     * @param {number} code  close code indicating why the connection
     * was closed.
     * @param {string} reason reason indicating why the connection was
     * closed.
     */
    _onWebsocketClose({ code, reason }) {
        this._logDebug("_onWebsocketClose", code, reason);
        this._updateState(WORKER_STATE.DISCONNECTED);
        this.lastChannelSubscription = null;
        this.firstSubscribeDeferred = new Deferred();
        if (this.isReconnecting) {
            // Connection was not established but the close event was
            // triggered anyway. Let the onWebsocketError method handle
            // this case.
            return;
        }
        this.broadcast("BUS:DISCONNECT", { code, reason });
        if (code === WEBSOCKET_CLOSE_CODES.CLEAN) {
            if (reason === "OUTDATED_VERSION") {
                console.warn("Worker deactivated due to an outdated version.");
                this.active = false;
                this.broadcast("BUS:OUTDATED");
            }
            // WebSocket was closed on purpose, do not try to reconnect.
            return;
        }
        // WebSocket was not closed cleanly, let's try to reconnect.
        this.broadcast("BUS:RECONNECTING", { closeCode: code });
        this.isReconnecting = true;
        if (code === WEBSOCKET_CLOSE_CODES.KEEP_ALIVE_TIMEOUT) {
            // Don't wait to reconnect on keep alive timeout.
            this.connectRetryDelay = 0;
        }
        if (code === WEBSOCKET_CLOSE_CODES.SESSION_EXPIRED) {
            this.isWaitingForNewUID = true;
        }
        this._retryConnectionWithDelay();
    }

    /**
     * Triggered when a connection failed or failed to established.
     */
    _onWebsocketError() {
        this._logDebug("_onWebsocketError");
        this._retryConnectionWithDelay();
    }

    /**
     * Handle data received from the bus.
     *
     * @param {MessageEvent} messageEv
     */
    _onWebsocketMessage(messageEv) {
        const notifications = JSON.parse(messageEv.data);
        this._logDebug("_onWebsocketMessage", notifications);
        this.lastNotificationId = notifications[notifications.length - 1].id;
        this.broadcast("BUS:NOTIFICATION", notifications);
    }

    async _logDebug(title, ...args) {
        if (this.loggingEnabled) {
            try {
                await logger.log({
                    dt: new Date().toISOString(),
                    event: title,
                    args,
                    worker: UUID,
                });
            } catch (e) {
                console.error(e);
            }
        }
    }

    /**
     * Triggered on websocket open. Send message that were waiting for
     * the connection to open.
     */
    _onWebsocketOpen() {
        this._logDebug("_onWebsocketOpen");
        this._updateState(WORKER_STATE.CONNECTED);
        this.broadcast(this.isReconnecting ? "BUS:RECONNECT" : "BUS:CONNECT");
        this._debouncedUpdateChannels();
        this.connectRetryDelay = this.INITIAL_RECONNECT_DELAY;
        this.connectTimeout = null;
        this.isReconnecting = false;
        this.firstSubscribeDeferred.then(() => {
            if (!this.websocket) {
                return;
            }
            this.messageWaitQueue.forEach((msg) => this.websocket.send(msg));
            this.messageWaitQueue = [];
        });
    }

    /**
     * Try to reconnect to the server, an exponential back off is
     * applied to the reconnect attempts.
     */
    _retryConnectionWithDelay() {
        this.connectRetryDelay =
            Math.min(this.connectRetryDelay * 1.5, MAXIMUM_RECONNECT_DELAY) +
            this.RECONNECT_JITTER * Math.random();
        this._logDebug("_retryConnectionWithDelay", this.connectRetryDelay);
        this.connectTimeout = setTimeout(this._start.bind(this), this.connectRetryDelay);
    }

    /**
     * Send a message to the server through the websocket connection.
     * If the websocket is not open, enqueue the message and send it
     * upon the next reconnection.
     *
     * @param {{event_name: string, data: any }} message Message to send to the server.
     */
    _sendToServer(message) {
        this._logDebug("_sendToServer", message);
        const payload = JSON.stringify(message);
        if (!this._isWebsocketConnected()) {
            if (message["event_name"] === "subscribe") {
                this.messageWaitQueue = this.messageWaitQueue.filter(
                    (msg) => JSON.parse(msg).event_name !== "subscribe"
                );
                this.messageWaitQueue.unshift(payload);
            } else {
                this.messageWaitQueue.push(payload);
            }
        } else {
            if (message["event_name"] === "subscribe") {
                this.websocket.send(payload);
            } else {
                this.firstSubscribeDeferred.then(() => this.websocket.send(payload));
            }
        }
    }

    _removeWebsocketListeners() {
        this.websocket?.removeEventListener("open", this._onWebsocketOpen);
        this.websocket?.removeEventListener("message", this._onWebsocketMessage);
        this.websocket?.removeEventListener("error", this._onWebsocketError);
        this.websocket?.removeEventListener("close", this._onWebsocketClose);
    }

    /**
     * Start the worker by opening a websocket connection.
     */
    _start() {
        this._logDebug("_start");
        if (!this.active || this._isWebsocketConnected() || this._isWebsocketConnecting()) {
            return;
        }
        this._removeWebsocketListeners();
        if (this._isWebsocketClosing()) {
            // close event was not triggered and will never be, broadcast the
            // disconnect event for consistency sake.
            this.lastChannelSubscription = null;
            this.broadcast("BUS:DISCONNECT", { code: WEBSOCKET_CLOSE_CODES.ABNORMAL_CLOSURE });
        }
        this._updateState(WORKER_STATE.CONNECTING);
        this.websocket = new WebSocket(this.websocketURL);
        this.websocket.addEventListener("open", this._onWebsocketOpen);
        this.websocket.addEventListener("error", this._onWebsocketError);
        this.websocket.addEventListener("message", this._onWebsocketMessage);
        this.websocket.addEventListener("close", this._onWebsocketClose);
    }

    /**
     * Stop the worker.
     */
    _stop() {
        this._logDebug("_stop");
        clearTimeout(this.connectTimeout);
        this.connectRetryDelay = this.INITIAL_RECONNECT_DELAY;
        this.isReconnecting = false;
        this.lastChannelSubscription = null;
        const shouldBroadcastClose =
            this.websocket && this.websocket.readyState !== WebSocket.CLOSED;
        this.websocket?.close();
        this._removeWebsocketListeners();
        this.websocket = null;
        if (shouldBroadcastClose) {
            this.broadcast("BUS:DISCONNECT", { code: WEBSOCKET_CLOSE_CODES.CLEAN });
        }
    }

    /**
     * Update the channel subscription on the server. Ignore if the channels
     * did not change since the last subscription.
     *
     * @param {boolean} force Whether or not we should update the subscription
     * event if the channels haven't change since last subscription.
     */
    _updateChannels({ force = false } = {}) {
        const allTabsChannels = [
            ...new Set([].concat.apply([], [...this.channelsByClient.values()])),
        ].sort();
        const allTabsChannelsString = JSON.stringify(allTabsChannels);
        const shouldUpdateChannelSubscription =
            allTabsChannelsString !== this.lastChannelSubscription;
        if (force || shouldUpdateChannelSubscription) {
            this.lastChannelSubscription = allTabsChannelsString;
            this._sendToServer({
                event_name: "subscribe",
                data: { channels: allTabsChannels, last: this.lastNotificationId },
            });
            this.firstSubscribeDeferred.resolve();
        }
    }
    /**
     * Update the worker state and broadcast the new state to its clients.
     *
     * @param {WORKER_STATE[keyof WORKER_STATE]} newState
     */
    _updateState(newState) {
        this.state = newState;
        this.broadcast("BUS:WORKER_STATE_UPDATED", newState);
    }
}
