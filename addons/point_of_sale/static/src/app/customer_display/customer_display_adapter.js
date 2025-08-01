import { formatCurrency } from "@point_of_sale/app/models/utils/currency";
import { toRaw } from "@odoo/owl";

/**
 * This module provides functions to format order and order line data for customer display.
 * The goal is to format data in a way that avoids loading all models in the customer display.
 */

export class CustomerDisplayPosAdapter {
    constructor() {
        this.setup();
    }

    setup() {
        this.data = {};
        this.channel = new BroadcastChannel("UPDATE_CUSTOMER_DISPLAY");
    }

    dispatch(pos) {
        this.channel.postMessage(JSON.parse(JSON.stringify(this.data)));
        pos.data
            .call("pos.config", "update_customer_display", [
                [pos.config.id],
                this.data,
                localStorage.getItem("device_uuid"),
            ])
            .catch((error) => {
                console.info("Failed to update customer display:", error);
            });
    }

    formatOrderData(order) {
        this.data = {
            finalized: order.finalized,
            general_customer_note: order.general_customer_note,
            amount: formatCurrency(order.getTotalWithTax() || 0, order.currency),
            change: order.getChange() && formatCurrency(order.getChange(), order.currency),
            paymentLines: order.payment_ids.map((pl) => this.getPaymentData(pl)),
            lines: order.lines.map((l) => this.getOrderlineData(l)),
            qrPaymentData: toRaw(order.getSelectedPaymentline()?.qrPaymentData),
        };
    }

    getOrderlineData(line) {
        return {
            productId: line.product_id.id,
            taxGroupLabels: line.taxGroupLabels,
            discount: line.getDiscountStr(),
            customerNote: line.getCustomerNote() || "",
            internalNote: line.getNote() || "[]",
            productName: line.getFullProductName(),
            price: line.getPriceString(),
            qty: line.getQuantityStr().qtyStr,
            unit: line.product_id.uom_id ? line.product_id.uom_id.name : "",
            unitPrice: formatCurrency(line.unitDisplayPrice, line.currency),
            packLotLines: line.packLotLines,
            comboParent: line.combo_parent_id?.getFullProductName?.() || "",
            price_without_discount: formatCurrency(
                line.getUnitDisplayPriceBeforeDiscount(),
                line.currency
            ),
        };
    }

    getPaymentData(payment) {
        return {
            name: payment.payment_method_id.name,
            amount: formatCurrency(payment.amount, payment.pos_order_id.currency),
        };
    }
}
