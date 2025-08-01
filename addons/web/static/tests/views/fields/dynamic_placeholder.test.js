import { expect, test } from "@odoo/hoot";
import { Deferred, press, waitFor, waitUntil } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { onWillStart } from "@odoo/owl";
import {
    contains,
    defineModels,
    fields,
    models,
    mountView,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { DynamicPlaceholderPopover } from "@web/views/fields/dynamic_placeholder_popover";

class Partner extends models.Model {
    char = fields.Char();
    placeholder = fields.Char({ default: "partner" });
    product_id = fields.Many2one({ relation: "product" });
    properties = fields.Properties({
        string: "Properties",
        definition_record: "product_id",
        definition_record_field: "properties_definitions",
    });

    _records = [
        {
            id: 1,
            char: "yop",
            product_id: 37,
            properties: { f80b6fb58d0d4c72: 3, f424643eee1f3655: 41 },
        },
        { id: 2, char: "blip", product_id: false },
        { id: 4, char: "abc", product_id: 41 },
    ];

    _views = {
        form: /* xml */ `
            <form>
                <field name="placeholder" invisible="1"/>
                <sheet>
                    <group>
                        <field
                            name="char"
                            options="{
                                'dynamic_placeholder': true,
                                'dynamic_placeholder_model_reference_field': 'placeholder'
                            }"
                        />
                    </group>
                </sheet>
            </form>
        `,
    };
}

class Product extends models.Model {
    name = fields.Char({ string: "Product Name" });
    properties_definitions = fields.PropertiesDefinition();

    _records = [
        {
            id: 37,
            name: "xphone",
            properties_definitions: [
                { name: "f80b6fb58d0d4c72", type: "integer", string: "prop 1" },
                { name: "f424643eee1f3655", type: "many2one", string: "prop 2", comodel: "product" },
            ],
        },
        { id: 41, name: "xpad" },
    ];
}

defineModels([Partner, Product]);

onRpc("has_group", () => true);
onRpc("mail_allowed_qweb_expressions", () => []);

test("dynamic placeholder close with click out", async () => {
    await mountView({ type: "form", resModel: "partner", resId: 1 });

    await contains(".o_field_char input").edit("#", { confirm: false });
    expect(".o_model_field_selector_popover").toHaveCount(1);
    await contains(".o_content").click();
    expect(".o_model_field_selector_popover").toHaveCount(0);
    await contains(".o_field_char input").edit("#", { confirm: false });
    await contains(".o_model_field_selector_popover_item_relation").click();
    await contains(".o_content").click();
    expect(".o_model_field_selector_popover").toHaveCount(0);
});

test("dynamic placeholder close with escape", async () => {
    await mountView({ type: "form", resModel: "partner", resId: 1 });

    await contains(".o_field_char input").edit("#", { confirm: false });
    expect(".o_model_field_selector_popover").toHaveCount(1);
    press("Escape");
    await animationFrame();
    expect(".o_model_field_selector_popover").toHaveCount(0);
    await contains(".o_field_char input").edit("#", { confirm: false });
    await contains(".o_model_field_selector_popover_item_relation").click();
    press("Escape");
    await animationFrame();
    expect(".o_model_field_selector_popover").toHaveCount(0);
});

test("dynamic placeholder close when clicking on the cross", async () => {
    await mountView({ type: "form", resModel: "partner", resId: 1 });

    await contains(".o_field_char input").edit("#", { confirm: false });
    expect(".o_model_field_selector_popover").toHaveCount(1);
    await contains(".o_model_field_selector_popover_close").click();
    expect(".o_model_field_selector_popover").toHaveCount(0);
    await contains(".o_field_char input").edit("#", { confirm: false });
    await contains(".o_model_field_selector_popover_item_relation").click();
    await contains(".o_model_field_selector_popover_close").click();
    expect(".o_model_field_selector_popover").toHaveCount(0);
});

test("dynamic placeholder properties", async () => {
    await mountView({ type: "form", resModel: "partner", resId: 1 });

    await contains(".o_field_char input").edit("#", { confirm: false });
    expect(".o_model_field_selector_popover").toHaveCount(1);
    expect(".o_model_field_selector_popover .o_model_field_selector_popover_item_name:contains('Properties')").toHaveCount(1);

    // select the properties
    await contains(".o_model_field_selector_popover .o_model_field_selector_popover_item_name:contains('Properties') + .o_model_field_selector_popover_item_relation").click();
    expect(".o_model_field_selector_popover .o_model_field_selector_popover_item_name:contains('prop 1 (xphone)')").toHaveCount(1);
    expect(".o_model_field_selector_popover .o_model_field_selector_popover_item_name:contains('prop 2 (xphone)')").toHaveCount(1);

    // select the many2one property
    await contains(".o_model_field_selector_popover .o_model_field_selector_popover_item_name:contains('prop 2 (xphone)') + .o_model_field_selector_popover_item_relation").click();
    expect(".o_model_field_selector_popover .o_model_field_selector_popover_item_name:contains('Created on')").toHaveCount(1);

    // select the product name
    await contains(".o_model_field_selector_popover .o_model_field_selector_popover_item_name:contains('Product Name')").click();

    // click on insert
    await contains(".o_model_field_selector_popover button:contains('Insert')").click();

    const value = document.querySelector(".o_field_placeholder").value.trim();
    expect(value).toBe("{{object.properties.get('f424643eee1f3655', env['product']).name}}");
});

test("correctly cache model qweb variables and don't prevent opening of other popovers", async () => {
    const def = new Deferred();
    let willStarts = 0;
    patchWithCleanup(DynamicPlaceholderPopover.prototype, {
        setup() {
            super.setup();
            onWillStart(() => {
                willStarts++;
            });
        },
    });

    onRpc("partner", "mail_allowed_qweb_expressions", async () => {
        expect.step("mail_allowed_qweb_expressions");
        await def;
        return [];
    });

    await mountView({ type: "form", resModel: "partner", resId: 1 });
    await contains(".o_field_char input").edit("#", { confirm: false });
    await waitUntil(() => willStarts === 1);
    await contains(".o_field_char input").edit("#", { confirm: false });
    await waitUntil(() => willStarts === 2);

    def.resolve();
    await waitFor(".o_model_field_selector_popover");
    expect(willStarts).toBe(2);
    expect.verifySteps(["mail_allowed_qweb_expressions"]);
});
