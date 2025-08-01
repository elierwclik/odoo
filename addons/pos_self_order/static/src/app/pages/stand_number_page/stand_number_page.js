import { Component, useState } from "@odoo/owl";
import { useSelfOrder } from "@pos_self_order/app/services/self_order_service";
import { useService } from "@web/core/utils/hooks";
import { Numpad } from "@point_of_sale/app/components/numpad/numpad";
import { _t } from "@web/core/l10n/translation";

export class StandNumberPage extends Component {
    static template = "pos_self_order.StandNumberPage";
    static components = { Numpad };
    static props = {};

    setup() {
        this.selfOrder = useSelfOrder();
        this.selfOrder.isOrder();
        this.router = useService("router");
        this.state = useState({
            standNumber: "",
        });
    }
    numberClick(key) {
        if (key === "Backspace") {
            this.state.standNumber = this.state.standNumber.slice(0, -1);
            return;
        }
        if (this.state.standNumber.length >= 10) {
            return;
        }
        this.state.standNumber += key;
    }

    confirm() {
        this.selfOrder.currentOrder.table_stand_number = this.state.standNumber;
        this.selfOrder.confirmOrder();
    }

    get actionBtnText() {
        return this.selfOrder.hasPaymentMethod() ? _t("Pay") : _t("Order");
    }
}
