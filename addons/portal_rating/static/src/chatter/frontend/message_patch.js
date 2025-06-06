import { Message } from "@mail/core/common/message";
import { convertBrToLineBreak } from "@mail/utils/common/format";

import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";

patch(Message.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.editRating = false;
    },

    get isEditing() {
        return !this.state.editRating && super.isEditing;
    },

    get ratingValue() {
        return this.message.rating_id?.rating || this.message.rating_value;
    },

    onClikEditComment() {
        this.state.editRating = !this.state.editRating;
        if (this.state.editRating) {
            const messageContent = convertBrToLineBreak(
                this.props.message.rating_id.publisher_comment
            );
            this.props.message.composer = {
                message: this.props.message,
                text: messageContent,
                portalComment: true,
                selection: {
                    start: messageContent.length,
                    end: messageContent.length,
                    direction: "none",
                },
            };
        } else {
            this.message.composer = null;
        }
    },

    exitEditCommentMode() {
        this.props.message.composer.clear();
        this.message.composer = null;
        this.state.editRating = false;
    },

    async deleteComment() {
        const data = await rpc("/website/rating/comment", {
            rating_id: this.message.rating_id.id,
            publisher_comment: "",
        });
        this.message.rating_id = data;
    },
});
