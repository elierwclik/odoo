import { describe, expect } from "@odoo/hoot";
import { advanceTime } from "@odoo/hoot-mock";
import { browser } from "@web/core/browser/browser";
import { asyncStep, onRpc, mountWebClient, waitForSteps } from "@web/../tests/web_test_helpers";
import { defineMailModels, mockGetMedia, onlineTest } from "@mail/../tests/mail_test_helpers";
import { PeerToPeer, STREAM_TYPE, UPDATE_EVENT } from "@mail/discuss/call/common/peer_to_peer";

describe.current.tags("desktop");
defineMailModels();

class Network {
    _peerToPeerInstances = new Map();
    _notificationRoute;
    constructor(route) {
        this._notificationRoute = route || "/any/mock/notification";
        onRpc(this._notificationRoute, async (req) => {
            const {
                params: { peer_notifications },
            } = await req.json();
            for (const notification of peer_notifications) {
                const [sender_session_id, target_session_ids, content] = notification;
                for (const id of target_session_ids) {
                    const p2p = this._peerToPeerInstances.get(id);
                    p2p.handleNotification(sender_session_id, content);
                }
            }
        });
    }
    /**
     * @param id
     * @return {{id, p2p: PeerToPeer}}
     */
    register(id) {
        const p2p = new PeerToPeer({ notificationRoute: this._notificationRoute });
        this._peerToPeerInstances.set(id, p2p);
        return { id, p2p };
    }
    close() {
        for (const p2p of this._peerToPeerInstances.values()) {
            p2p.disconnect();
        }
    }
}

onlineTest("basic peer to peer connection", async () => {
    await mountWebClient();
    const channelId = 1;
    const network = new Network();
    const user1 = network.register(1);
    const user2 = network.register(2);
    user2.p2p.addEventListener("update", ({ detail: { name, payload } }) => {
        if (name === UPDATE_EVENT.CONNECTION_CHANGE && payload.state === "connected") {
            asyncStep(payload.state);
        }
    });

    user2.p2p.connect(user2.id, channelId);
    user1.p2p.connect(user1.id, channelId);
    await user1.p2p.addPeer(user2.id);
    await waitForSteps(["connected"]);
    network.close();
});

onlineTest("mesh peer to peer connections", async () => {
    await mountWebClient();
    const channelId = 2;
    const network = new Network();
    const userCount = 10;
    const users = Array.from({ length: userCount }, (_, i) => network.register(i));
    const promises = [];
    for (const user of users) {
        user.p2p.connect(user.id, channelId);
        for (let i = 0; i < user.id; i++) {
            promises.push(user.p2p.addPeer(i));
        }
    }
    await Promise.all(promises);

    let connectionsCount = 0;
    for (const user of users) {
        connectionsCount += user.p2p.peers.size;
    }
    expect(connectionsCount).toBe(userCount * (userCount - 1));
    connectionsCount = 0;
    network.close();
    for (const user of users) {
        connectionsCount += user.p2p.peers.size;
    }
    expect(connectionsCount).toBe(0);
});

onlineTest("connection recovery", async () => {
    await mountWebClient();
    const channelId = 1;
    const network = new Network();
    const user1 = network.register(1);
    const user2 = network.register(2);
    user2.remoteStates = new Map();
    user2.p2p.addEventListener("update", ({ detail: { name, payload } }) => {
        if (name === UPDATE_EVENT.CONNECTION_CHANGE && payload.state === "connected") {
            asyncStep(payload.state);
        }
    });

    user1.p2p.connect(user1.id, channelId);
    user1.p2p.addPeer(user2.id);
    // only connecting user2 after user1 has called addPeer so that user2 ignores notifications
    // from user1, which simulates a connection drop that should be recovered.
    user2.p2p.connect(user2.id, channelId);
    const openPromise = new Promise((resolve) => {
        user1.p2p.peers.get(2).dataChannel.onopen = resolve;
    });
    advanceTime(5_000); // recovery timeout
    await openPromise;
    await waitForSteps(["connected"]);
    network.close();
});

onlineTest("can broadcast a stream and control download", async () => {
    mockGetMedia();
    await mountWebClient();
    const channelId = 3;
    const network = new Network();
    const user1 = network.register(1);
    const user2 = network.register(2);
    user2.remoteMedia = new Map();
    const trackPromise = new Promise((resolve) => {
        user2.p2p.addEventListener("update", ({ detail: { name, payload } }) => {
            if (name === UPDATE_EVENT.TRACK) {
                user2.remoteMedia.set(payload.sessionId, {
                    [payload.type]: {
                        track: payload.track,
                        active: payload.active,
                    },
                });
                resolve();
            }
        });
    });

    user2.p2p.connect(user2.id, channelId);
    user1.p2p.connect(user1.id, channelId);
    await user1.p2p.addPeer(user2.id);
    const videoStream = await browser.navigator.mediaDevices.getUserMedia({
        video: true,
    });
    const videoTrack = videoStream.getVideoTracks()[0];
    await user1.p2p.updateUpload(STREAM_TYPE.CAMERA, videoTrack);
    await trackPromise;
    const user2RemoteMedia = user2.remoteMedia.get(user1.id);
    const user2CameraTransceiver = user2.p2p.peers.get(user1.id).getTransceiver(STREAM_TYPE.CAMERA);
    expect(user2CameraTransceiver.direction).toBe("recvonly");
    expect(user2RemoteMedia[STREAM_TYPE.CAMERA].track.kind).toBe("video");
    expect(user2RemoteMedia[STREAM_TYPE.CAMERA].active).toBe(true);
    user2.p2p.updateDownload(user1.id, { camera: false });
    expect(user2CameraTransceiver.direction).toBe("inactive");
    network.close();
});

onlineTest("can broadcast arbitrary messages (dataChannel)", async () => {
    await mountWebClient();
    const channelId = 4;
    const network = new Network();
    const user1 = network.register(1);
    const user2 = network.register(2);
    user2.p2p.connect(user2.id, channelId);
    user1.p2p.connect(user1.id, channelId);
    await user1.p2p.addPeer(user2.id);
    user1.inbox = [];
    const pongPromise = new Promise((resolve) => {
        user1.p2p.addEventListener("update", ({ detail: { name, payload } }) => {
            if (name === UPDATE_EVENT.BROADCAST) {
                user1.inbox.push(payload);
                resolve();
            }
        });
    });
    user2.inbox = [];
    user2.p2p.addEventListener("update", ({ detail: { name, payload } }) => {
        if (name === UPDATE_EVENT.BROADCAST && payload.message === "ping") {
            user2.inbox.push(payload);
            user2.p2p.broadcast("pong");
        }
    });
    user1.p2p.broadcast("ping");
    await pongPromise;
    expect(user2.inbox[0].senderId).toBe(user1.id);
    expect(user2.inbox[0].message).toBe("ping");
    expect(user1.inbox[0].senderId).toBe(user2.id);
    expect(user1.inbox[0].message).toBe("pong");
    network.close();
});

onlineTest("can reject arbitrary offers", async () => {
    await mountWebClient();
    const channelId = 1;
    const network = new Network();
    const user1 = network.register(1);
    const user2 = network.register(2);
    user2.p2p.connect(user2.id, channelId);
    user1.p2p.connect(user1.id, channelId);
    user2.p2p._emitLog = (id, message) => {
        if (message === "offer rejected") {
            asyncStep("offer rejected");
        }
    };
    user2.p2p.acceptOffer = (id, sequence) => id !== user1.id || sequence > 20;
    user1.p2p.addPeer(user2.id, { sequence: 19 });
    await waitForSteps(["offer rejected"]);
    network.close();
});
