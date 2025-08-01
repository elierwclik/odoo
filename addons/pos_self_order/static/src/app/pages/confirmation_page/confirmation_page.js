import { Component, onMounted, onWillUnmount, useState, useEffect } from "@odoo/owl";
import { useSelfOrder } from "@pos_self_order/app/services/self_order_service";
import { cookie } from "@web/core/browser/cookie";
import { useService } from "@web/core/utils/hooks";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { rpc } from "@web/core/network/rpc";
import { PrintingFailurePopup } from "@pos_self_order/app/components/printing_failure_popup/printing_failure_popup";

export class ConfirmationPage extends Component {
    static template = "pos_self_order.ConfirmationPage";
    static props = ["orderAccessToken", "screenMode"];

    setup() {
        this.selfOrder = useSelfOrder();
        this.router = useService("router");
        this.printer = useService("printer");
        this.dialog = useService("dialog");
        this.changeToDisplay = [];
        this.state = useState({
            onReload: true,
            payment: this.props.screenMode === "pay",
        });

        onMounted(() => {
            if (this.selfOrder.config.self_ordering_mode === "kiosk") {
                this.defaultTimeout = setTimeout(() => {
                    this.router.navigate("default");
                }, 30000);
            }
        });
        useEffect(
            () => {
                if (!this.confirmedOrder) {
                    return;
                }

                this.printOrder();
            },
            () => [this.confirmedOrder?.uiState?.receiptReady]
        );
        onWillUnmount(() => {
            clearTimeout(this.defaultTimeout);
        });

        onMounted(async () => {
            await this.initOrder();
        });
    }

    get confirmedOrder() {
        return this.selfOrder.currentOrder;
    }

    async initOrder(retry = true) {
        const order = this.selfOrder.models["pos.order"].find(
            (o) => o.access_token === this.props.orderAccessToken
        );

        if (!order && retry) {
            await this.selfOrder.getUserDataFromServer([this.props.orderAccessToken]);
            return this.initOrder(false);
        }

        this.selfOrder.selectedOrderUuid = order.uuid;

        if (
            !order ||
            (this.selfOrder.hasPaymentMethod() &&
                this.selfOrder.config.self_ordering_mode === "mobile" &&
                this.selfOrder.config.self_ordering_pay_after === "each" &&
                order.state !== "paid")
        ) {
            this.router.navigate("default");
            return;
        }

        this.selfOrder.selectedOrderUuid = order.uuid;
        this.confirmedOrder.uiState.receiptReady = this.beforePrintOrder();
        this.state.onReload = false;
    }

    canPrintReceipt() {
        return (
            !this.isPrinting &&
            this.confirmedOrder.uiState.receiptReady &&
            (!this.confirmedOrder.nb_print || this.confirmedOrder.nb_print < 1)
        );
    }

    beforePrintOrder() {
        // meant to be overriden.
        return true;
    }

    async printOrder() {
        if (this.selfOrder.config.self_ordering_mode === "kiosk" && this.canPrintReceipt()) {
            try {
                this.isPrinting = true;
                const order = this.confirmedOrder;
                const result = await this.printer.print(
                    OrderReceipt,
                    {
                        order: order,
                    },
                    this.printOptions
                );
                if (!this.selfOrder.has_paper) {
                    this.updateHasPaper(true);
                }
                order.nb_print = 1;
                if (typeof order.id === "number" && result) {
                    await rpc("/pos_self_order/kiosk/increment_nb_print/", {
                        access_token: this.selfOrder.access_token,
                        order_id: order.id,
                        order_access_token: order.access_token,
                    });
                }
            } catch (e) {
                if (["EPTR_REC_EMPTY", "EPTR_COVER_OPEN"].includes(e.errorCode)) {
                    this.dialog.add(PrintingFailurePopup, {
                        trackingNumber: this.confirmedOrder.tracking_number,
                        message: e.body,
                        close: () => {
                            this.router.navigate("default");
                        },
                    });
                    this.updateHasPaper(false);
                } else {
                    console.error(e);
                }
            } finally {
                this.isPrinting = false;
            }
        }
    }

    get printOptions() {
        return {};
    }

    backToHome() {
        if (this.confirmedOrder.uiState.receiptReady && !this.setDefautLanguage()) {
            this.router.navigate("default");
        }
    }

    async updateHasPaper(state) {
        await rpc("/pos-self-order/change-printer-status", {
            access_token: this.selfOrder.access_token,
            has_paper: state,
        });
        this.selfOrder.has_paper = state;
    }

    setDefautLanguage() {
        const defaultLanguage = this.selfOrder.config.self_ordering_default_language_id;

        if (
            defaultLanguage &&
            this.selfOrder.currentLanguage.code !== defaultLanguage.code &&
            !this.state.onReload &&
            this.selfOrder.config.self_ordering_mode === "kiosk"
        ) {
            cookie.set("frontend_lang", defaultLanguage.code);
            window.location.reload();
            this.state.onReload = true;
            return true;
        }

        return this.state.onReload;
    }
}
