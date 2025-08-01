import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add('test_generate_serial_1', {  steps: () => [
    {
        trigger: '.o_field_x2many_list_row_add > a',
        run: "click",
    },
    {
        trigger: ".o_field_widget[name=product_id] input",
        run: "edit Serial",
    },
    {
        trigger: ".ui-menu-item > a:contains('Product Serial')",
        run: "click",
    },
    {
        trigger: ".btn-primary[name=action_confirm]",
        run: "click",
    },
    {
        trigger: "button:contains('Details')",
        run: "click",
    },
    {
        trigger: "h4:contains('Detailed Operations')",
        run: "click",
    },
    {
        trigger: '.o_widget_generate_serials > button',
        run: "click",
    },
    {
        trigger: ".modal h4:contains('Generate Serial numbers')",
        run: "click",
    },
    {
        trigger: ".modal div[name=next_serial] input",
        run: "edit serial_n_1",
    },
    {
        trigger: ".modal div[name=next_serial_count] input",
        run: "edit 5 && click body",
    },
    {
        trigger: ".modal .btn-primary:contains('Generate')",
        run: "click",
    },
    {
        trigger: "span[data-tooltip=Quantity]:contains('5')",
        run: () => {
            const nbLines = document.querySelectorAll(".o_field_cell[name=lot_name]").length;
            if (nbLines !== 5){
                console.error("wrong number of move lines generated. " + nbLines + " instead of 5");
            }
        },
    },
    {
        trigger: ".modal button:contains(save)",
        run: "click",
    },
    {
        trigger: "body:not(:has(.modal))",
    },
    {
        trigger: ".o_optional_columns_dropdown_toggle",
        run: "click",
    },
    {
        trigger: 'input[name="picked"]',
        content: 'Check the picked field to display the column on the list view.',
        run: function (actions) {
            if (!this.anchor.checked) {
                actions.click();
            }
        },
    },
    {
        trigger: ".o_data_cell[name=picked]",
        run: "click",
    },
    {
        trigger: ".o_field_widget[name=picked] input",
        run: function (actions) {
            if (!this.anchor.checked) {
                actions.click();
            }
        }
    },
    {
        trigger: ".btn-primary[name=button_validate]",
        run: "click",
    },
    {
        trigger: ".o_control_panel_actions button:contains('Traceability')",
    },
]});

registry.category("web_tour.tours").add('test_generate_serial_2', {  steps: () => [
    {
        trigger: '.o_field_x2many_list_row_add > a',
        run: "click",
    },
    {
        trigger: ".o_field_widget[name=product_id] input",
        run: "edit Lot",
    },
    {
        trigger: ".ui-menu-item > a:contains('Product Lot 1')",
        run: "click",
    },
    {
        trigger: ".o_field_widget[name=product_uom_qty] input",
        run: "edit 100",
    },
    {
        trigger: ".btn-primary[name=action_confirm]",
        run: "click",
    },
    {
        trigger: "button:contains('Details')",
        run: "click",
    },
    {
        trigger: ".modal h4:contains('Detailed Operations')",
        run: "click",
    },
    // We generate lots for a first batch of 50 products
    {
        trigger: ".modal .o_widget_generate_serials > button",
        run: "click",
    },
    {
        trigger: ".modal h4:contains('Generate Lot numbers')",
        run: "click",
    },
    {
        trigger: ".modal div[name=next_serial] input",
        run: "edit lot_n_1_1",
    },
    {
        trigger: ".modal div[name=next_serial_count] input",
        run: "edit 7.5",
    },
    {
        trigger: ".modal div[name=total_received] input",
        run: "edit 50",
    },
    {
        trigger: ".modal .modal-footer button.btn-primary:contains(Generate)",
        run: "click",
    },
    {
        trigger: ".modal span[data-tooltip=Quantity]:contains(50)",
        run: () => {
            const nbLines = document.querySelectorAll(".o_field_cell[name=lot_name]").length;
            if (nbLines !== 7){
                console.error("wrong number of move lines generated. " + nbLines + " instead of 7");
            }
        },
    },
    // We generate lots for the last 50 products
    {
        trigger: ".modal .o_widget_generate_serials > button",
        run: "click",
    },
    {
        trigger: ".modal h4:contains('Generate Lot numbers')",
    },
    {
        trigger: ".modal div[name=next_serial] input",
        run: "edit lot_n_2_1",
    },
    {
        trigger: ".modal div[name=next_serial_count] input",
        run: "edit 13",
    },
    {
        trigger: ".modal div[name=total_received] input",
        run: "edit 50",
    },
    {
        trigger: ".modal div[name=keep_lines] input",
        run: "check",
    },
    {
        trigger: ".modal .modal-footer button.btn-primary:contains(Generate)",
        run: "click",
    },
    {
        trigger: ".modal span[data-tooltip=Quantity]:contains(100)",
        run: () => {
            const nbLines = document.querySelectorAll(".o_field_cell[name=lot_name]").length;
            if (nbLines !== 11){
                console.error("wrong number of move lines generated. " + nbLines + " instead of 11");
            }
        },
    },
    {
        trigger: ".modal .o_form_button_save",
        run: "click",
    },
    {
        trigger: "body:not(:has(.modal))",
    },
    {
        trigger: ".o_optional_columns_dropdown_toggle",
        run: "click",
    },
    {
        trigger: "input[name='picked']",
        content: "Check the picked field to display the column on the list view.",
        run: function (actions) {
            if (!this.anchor.checked) {
                actions.click();
            }
        },
    },
    {
        trigger: ".o_data_cell[name=picked]",
        run: "click",
    },
    {
        trigger: ".o_field_widget[name=picked] input",
        run: function (actions) {
            if (!this.anchor.checked) {
                actions.click();
            }
        }
    },
    {
        trigger: ".btn-primary[name=button_validate]",
        run: "click",
    },
    {
        trigger: ".o_control_panel_actions button:contains('Traceability')",
    },
]});

registry.category('web_tour.tours').add('test_inventory_adjustment_apply_all', {  steps: () => [
    {
        trigger: '.o_list_button_add',
        run: "click",
    },
    {
        trigger: 'div[name=product_id] input',
        run: "edit Product 1",
    },
    {
        trigger: '.ui-menu-item > a:contains("Product 1")',
        run: "click",
    },
    {
        trigger: 'div[name=inventory_quantity] input',
        run: "edit 123",
    },
    // Unfocus to show the "New" button again
    {
        trigger: '.o_searchview_input_container',
        run: "click",
    },
    {
        trigger: '.o_list_button_add',
        run: "click",
    },
    {
        trigger: 'div[name=product_id] input',
        run: "edit Product 2",
    },
    {
        trigger: '.ui-menu-item > a:contains("Product 2")',
        run: "click",
    },
    {
        trigger: 'div[name=inventory_quantity] input',
        run: "edit 456",
    },
    {
        trigger: 'button[name=action_apply_all]',
        run: "click",
    },
    {
        trigger: '.modal-content button[name=action_apply]',
        run: "click",
    },
    {
        trigger: "body:not(:has(.modal))",
    },
    {
        content: "Check that all quants were applied.",
        trigger: "body:not(:has(button[name=action_apply_inventory]))",
    },
    ],
});

registry.category("web_tour.tours").add("test_add_new_line_in_detailled_op", {
    steps: () => [
        {
            trigger: ".o_list_view.o_field_x2many .o_data_row button[name='action_show_details']",
            run: "click",
        },
        {
            trigger: ".modal-content",
        },
        {
            trigger: ".modal-content .o_field_x2many_list_row_add > a",
            run: "click",
        },
        {
            content: "Pick LOT001 to create a move line with a quantity of 0.00",
            trigger: ".o_data_row .o_data_cell[name=lot_id]:contains(LOT001)",
            run: "click",
        },
        {
            content: "check that the move contains three lines",
            trigger:
                ".modal-content:has(.modal-header .modal-title:contains(Detailed Operations)) .o_data_row:nth-child(3)",
        },
        {
            content: "Check that the first line is associated with LOT001 for a quantity of 0.00",
            trigger:
                ".modal-content .o_data_row:has(.o_field_pick_from input:value(WH/Stock - LOT001)):has(.o_field_float[name=quantity] input:value(0.00))",
        },
        {
            trigger: ".modal-content .o_field_x2many_list_row_add > a",
            run: "click",
        },
        {
            content: "LOT001 should not appear as it is not available",
            trigger: ".modal-header .modal-title:contains(Add line: Product Lot)",
            run: () => {
                const lines = document.querySelectorAll(".o_data_row .o_data_cell[name=lot_id]");
                if (lines.length !== 2) {
                    console.error(
                        "Wrong number of available quants: " + lines.length + " instead of 2."
                    );
                }
                const lineLOT001 = Array.from(lines).filter((line) =>
                    line.textContent.includes("LOT001")
                );
                if (lineLOT001.length) {
                    console.error("LOT001 shoudld not be displayed as unavailable.");
                }
            },
        },
        {
            content: "Cancel the move line creation",
            trigger: ".modal-header:has(.modal-title:contains(Add line: Product Lot)) .btn-close",
            run: "click",
        },
        {
            content: "Remove the newly created line",
            trigger:
                ".modal-content .o_data_row:has(.o_field_pick_from input:value(WH/Stock - LOT001)):has(.o_field_float[name=quantity] input:value(0.00)) .o_list_record_remove",
            run: "click",
        },
        {
            content: "check that the move contains two lines",
            trigger:
                ".modal-content:has(.modal-header .modal-title:contains(Detailed Operations)):not(:has(.o_data_row:nth-child(3)))",
        },
        {
            content: "Check that the first line is associated with LOT001",
            trigger:
                ".modal-content .o_data_row:nth-child(1):has(.o_field_pick_from:contains(WH/Stock - LOT001))",
        },
        {
            content: "Check that the second line is associated with LOT002",
            trigger:
                ".modal-content .o_data_row:nth-child(2):has(.o_field_pick_from:contains(WH/Stock - LOT002))",
        },
        {
            content: "Modify the quant associated to the second line to fully use LOT003",
            trigger: ".modal-content .o_data_row:nth-child(2) .o_field_pick_from",
            run: "click",
        },
        {
            trigger: ".modal-content .o_data_row:nth-child(2) .o_field_pick_from input",
            run: "edit LOT003",
        },
        {
            trigger: ".dropdown-item:contains(LOT003)",
            run: "click",
        },
        {
            content: "Modify the quantity of the first line from 10 to 8",
            trigger: ".modal-content .o_data_row:nth-child(1) .o_data_cell[name=quantity]",
            run: "click",
        },
        {
            trigger: ".modal-content .o_data_row:nth-child(1) .o_field_widget[name=quantity] input",
            run: "edit 8",
        },
        {
            content: "Click on the header to update the total amount",
            trigger: ".modal-header .modal-title:contains(Detailed Operations)",
            run: "click",
        },
        {
            trigger: ".modal-content .o_list_number:contains(18.00)",
        },
        {
            trigger: ".modal-content .o_field_x2many_list_row_add > a",
            run: "click",
        },
        {
            content: "LOT003 should not appear as it is not available",
            trigger: ".modal-header .modal-title:contains(Add line: Product Lot)",
            run: () => {
                const lines = document.querySelectorAll(".o_data_row .o_data_cell[name=lot_id]");
                if (lines.length !== 2) {
                    console.error(
                        "Wrong number of available quants: " + lines.length + " instead of 2."
                    );
                }
                const lineLOT003 = Array.from(lines).filter((line) =>
                    line.textContent.includes("LOT003")
                );
                if (lineLOT003.length) {
                    console.error("LOT003 shoudld not be displayed as unavailable.");
                }
            },
        },
        {
            content: "Pick LOT001 to create a move line with a quantity of 2.00",
            trigger: ".o_data_row .o_data_cell[name=lot_id]:contains(LOT001)",
            run: "click",
        },
        {
            trigger: ".modal-content .o_list_number:contains(20.00)",
        },
        {
            content: "Check that 2 units of LOT001 were added",
            trigger:
                ".o_data_row:has(.o_field_pick_from input:value(WH/Stock - LOT001)) .o_field_widget[name=quantity] input:value(2.00)",
        },
        {
            content: "Check that the third line is associated with LOT003",
            trigger:
                ".modal-content .o_data_row:nth-child(3) .o_field_pick_from:contains(WH/Stock - LOT003)",
        },
        {
            content: "Modify the quant associated to the third line to use LOT002",
            trigger: ".modal-content .o_data_row:nth-child(3) .o_field_pick_from",
            run: "click",
        },
        {
            trigger: ".modal-content .o_data_row:nth-child(3) .o_field_pick_from input",
            run: "edit LOT002",
        },
        {
            trigger: ".dropdown-item:contains(LOT002)",
            run: "click",
        },
        {
            trigger: ".modal-header .modal-title:contains(Detailed Operations)",
            run: "click",
        },
        {
            trigger: ".modal-content .o_data_row:nth-child(3) .o_field_pick_from:contains(LOT002)",
        },
        {
            content: "Modify the quantity of the first line from 10 to 15 to change the demand",
            trigger: ".modal-content .o_data_row:nth-child(3) .o_data_cell[name=quantity]",
            run: "click",
        },
        {
            trigger: ".modal-content .o_data_row:nth-child(3) .o_field_widget[name=quantity] input",
            run: "edit 15",
        },
        {
            content: "Remove the LOT001 line with a quantity of 8.00",
            trigger:
                ".o_data_row:has(.o_data_cell[name=quantity]:contains(8.00)) .o_list_record_remove",
            run: "click",
        },
        {
            trigger: ".modal-content .o_list_number:contains(17.00)",
        },
        {
            trigger: ".modal-content .o_field_x2many_list_row_add > a",
            run: "click",
        },
        {
            content: "LOT002 should not appear as it is not available",
            trigger: ".modal-header .modal-title:contains(Add line: Product Lot)",
            run: () => {
                const lines = document.querySelectorAll(".o_data_row .o_data_cell[name=lot_id]");
                if (lines.length !== 2) {
                    console.error(
                        "Wrong number of available quants: " + lines.length + " instead of 2."
                    );
                }
                const lineLOT002 = Array.from(lines).filter((line) =>
                    line.textContent.includes("LOT002")
                );
                if (lineLOT002.length) {
                    console.error("LOT002 shoudld not be displayed as unavailable.");
                }
            },
        },
        {
            content: "Pick LOT001 to create move line to fullfill the demand of 3",
            trigger: ".o_data_row .o_data_cell[name=lot_id]:contains(LOT001)",
            run: "click",
        },
        {
            trigger: ".modal-content .o_list_number:contains(20.00)",
        },
        {
            content: "Check that 3 units of LOT001 were added",
            trigger:
                ".modal-content .o_data_row:has(.o_field_pick_from input:value(WH/Stock - LOT001)):has(.o_field_float[name=quantity] input:value(3.00))",
        },
        {
            trigger: ".modal-content .o_form_button_save",
            run: "click",
        },
        {
            trigger: ".o_list_view.o_field_x2many .o_data_row button[name='action_show_details']",
            run: "click",
        },
    ],
});
