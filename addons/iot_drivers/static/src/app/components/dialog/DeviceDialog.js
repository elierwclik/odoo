/* global owl */

import useStore from "../../hooks/useStore.js";
import { BootstrapDialog } from "./BootstrapDialog.js";

const { Component, xml } = owl;

export const DEVICE_ICONS = {
    camera: "fa-camera",
    device: "fa-plug",
    display: "fa-desktop",
    fiscal_data_module: "fa-dollar",
    keyboard: "fa-keyboard-o",
    payment: "fa-credit-card",
    printer: "fa-print",
    scale: "fa-balance-scale",
    scanner: "fa-barcode",
    unsupported: "fa-question",
};

export const CONNECTION_ICONS = {
    hdmi: "fa-desktop",
    direct: "fa-usb",
    serial: "fa-usb",
    network: "fa-sitemap",
    bluetooth: "fa-bluetooth",
};

export class DeviceDialog extends Component {
    static props = {};
    static components = { BootstrapDialog };

    setup() {
        this.store = useStore();
        this.icons = DEVICE_ICONS;
        this.connectionIcons = CONNECTION_ICONS;
    }

    formatDeviceType(deviceType, numDevices) {
        const formattedDeviceType =
            deviceType[0].toUpperCase() + deviceType.replaceAll("_", " ").slice(1);
        return numDevices === 1 || deviceType === "unsupported"
            ? formattedDeviceType
            : `${formattedDeviceType}s`;
    }

    get devices() {
        return this.store.base.devices;
    }

    static template = xml`
    <t t-translation="off">
        <BootstrapDialog identifier="'device-list'" btnName="'Show'" isLarge="true">
            <t t-set-slot="header">
                Devices list
            </t>
            <t t-set-slot="body">
                <div t-if="Object.keys(devices).length === 0" class="alert alert-warning fs-6" role="alert">
                    No devices found.
                </div>
                <div class="accordion">
                    <div t-foreach="Object.keys(devices)" t-as="deviceType" t-key="deviceType" class="accordion-item">
                        <h2 class="accordion-header" t-att-id="'heading-' + deviceType">
                            <button class="accordion-button px-3 d-flex gap-3 collapsed" type="button" data-bs-toggle="collapse" t-att-data-bs-target="'#collapse-' + deviceType" t-att-aria-controls="'collapse-' + deviceType">
                                <span t-att-class="'color-primary fa fa-fw fa-2x ' + icons[deviceType]"/>
                                <span class="fs-5 fw-bold" t-out="devices[deviceType].length"/>
                                <span class="fs-5" t-out="formatDeviceType(deviceType, devices[deviceType].length)"/>
                            </button>
                        </h2>
                        <div t-att-id="'collapse-' + deviceType" class="accordion-collapse collapse" t-att-aria-labelledby="'heading-' + deviceType">
                            <div class="d-flex flex-column p-1 gap-2">
                                <div t-foreach="devices[deviceType]" t-as="device" t-key="device.identifier" class="d-flex flex-column bg-light rounded p-2 gap-1">
                                    <span t-out="device.name" class="one-line"/>
                                    <span class="text-secondary one-line">
                                        <span t-att-class="'me-2 fa fa-fw ' + connectionIcons[device.connection]"/>
                                        <t t-out="device.identifier"/>
                                    </span>
                                    <div t-if="device.value" class="text-secondary one-line">
                                        <i>Last sent value was <t t-out="device.value"/></i>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </t>
            <t t-set-slot="footer">
                <button type="button" class="btn btn-primary btn-sm" data-bs-dismiss="modal">Close</button>
            </t>
        </BootstrapDialog>
    </t>
    `;
}
