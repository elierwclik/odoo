import { expect, test } from "@odoo/hoot";
import { press, queryAll, queryAllAttributes, queryAllTexts } from "@odoo/hoot-dom";
import { animationFrame, mockDate, mockTimeZone, runAllTimers } from "@odoo/hoot-mock";
import { Component, useState, xml } from "@odoo/owl";

import { getPickerCell } from "@web/../tests/core/datetime/datetime_test_helpers";
import {
    Country,
    Partner,
    Player,
    Product,
    Stage,
    Team,
    addNewRule,
    clearNotSupported,
    clickOnButtonAddBranch,
    clickOnButtonAddRule,
    clickOnButtonDeleteNode,
    clickPrev,
    editValue,
    followRelation,
    getConditionText,
    getCurrentOperator,
    getCurrentPath,
    getCurrentValue,
    getOperatorOptions,
    getValueOptions,
    isNotSupportedOperator,
    isNotSupportedPath,
    isNotSupportedValue,
    openModelFieldSelectorPopover,
    formatDomain,
    selectOperator,
    selectValue,
    toggleArchive,
    toggleConnector,
} from "@web/../tests/core/tree_editor/condition_tree_editor_test_helpers";
import {
    contains,
    defineModels,
    defineParams,
    fields,
    MockServer,
    models,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { SELECTORS } from "./domain_selector_helpers";

import { DomainSelector } from "@web/core/domain_selector/domain_selector";

function addProductIds() {
    Partner._fields.product_ids = fields.Many2many({
        string: "Products",
        relation: "product",
    });
}

async function makeDomainSelector(params = {}) {
    const props = { ...params };

    class Parent extends Component {
        static components = { DomainSelector };
        static template = xml`<DomainSelector t-props="domainSelectorProps"/>`;
        static props = ["*"];
        setup() {
            this.domainSelectorProps = {
                resModel: "partner",
                readonly: false,
                domain: "[]",
                ...props,
                update: (domain, fromDebug) => {
                    if (props.update) {
                        props.update(domain, fromDebug);
                    }
                    this.domainSelectorProps.domain = domain;
                    this.render();
                },
            };
        }
        async set(domain) {
            this.domainSelectorProps.domain = domain;
            this.render();
            await animationFrame();
        }
    }
    return mountWithCleanup(Parent, { props });
}

defineModels([Partner, Product, Country, Stage, Team, Player]);

test("creating a domain from scratch", async () => {
    await makeDomainSelector({
        isDebugMode: true,
    });

    // As we gave an empty domain, there should be a visible button to add
    // the first domain part
    expect(SELECTORS.addNewRule).toHaveCount(1);

    // Clicking on that button should add a visible field selector in the
    // component so that the user can change the field chain
    await addNewRule();
    expect(".o_model_field_selector").toHaveCount(1);

    // Focusing the field selector input should open a field selector popover
    await openModelFieldSelectorPopover();
    expect(".o_model_field_selector_popover").toHaveCount(1, {
        message: "field selector popover should be visible",
    });
    // The field selector popover should contain the list of "partner"
    // fields. "Bar" should be among them. "Bar" result li will display the
    // name of the field and some debug info.
    expect(
        ".o_model_field_selector_popover .o_model_field_selector_popover_item_name:first"
    ).toHaveText("Bar\nbar (boolean)", {
        message: "field selector popover should contain the 'Bar' field",
    });

    // Clicking the "Bar" field should change the internal domain and this
    // should be displayed in the debug textarea
    await contains(
        ".o_model_field_selector_popover .o_model_field_selector_popover_item_name"
    ).click();
    expect(SELECTORS.debugArea).toHaveValue(`[("bar", "!=", False)]`);

    // There should be a "+" button to add a domain part; clicking on it
    // should add the default "('id', '=', 1)" domain
    await addNewRule();
    expect(SELECTORS.debugArea).toHaveValue(`["&", ("bar", "!=", False), ("bar", "!=", False)]`);

    // There should be two "Add branch" buttons to add a domain "branch"; clicking on
    // the first one, should add this group with defaults "('id', '=', 1)"
    // domains and the "|" operator
    expect(SELECTORS.buttonAddBranch).toHaveCount(2);
    await clickOnButtonAddBranch();
    expect(SELECTORS.debugArea).toHaveValue(
        `["&", "&", ("bar", "!=", False), ("bar", "!=", False), ("bar", "!=", False)]`
    );

    expect(SELECTORS.buttonAddNewRule).toHaveCount(1);
    await clickOnButtonAddRule();
    expect(SELECTORS.debugArea).toHaveValue(
        `["&", "&", ("bar", "!=", False), "|", ("bar", "!=", False), ("bar", "!=", False), ("bar", "!=", False)]`
    );

    // There should be five buttons to remove domain part; clicking on
    // the two last ones, should leave a domain with only the "bar" and
    // "foo" fields, with the initial "&" operator
    expect(SELECTORS.buttonDeleteNode).toHaveCount(5);
    await clickOnButtonDeleteNode(-1);
    await clickOnButtonDeleteNode(-1);
    expect(SELECTORS.debugArea).toHaveValue(`["&", ("bar", "!=", False), ("bar", "!=", False)]`);
});

test("building a domain with a datetime", async () => {
    expect.assertions(4);

    await makeDomainSelector({
        domain: `[("datetime", "=", "2017-03-27 15:42:00")]`,
        isDebugMode: true,
        update(domain) {
            expect(domain).toBe(`[("datetime", "=", "2017-03-26 15:42:00")]`);
        },
    });

    // Check that there is a datepicker to choose the date
    expect(".o_datetime_input").toHaveCount(1, { message: "there should be a datepicker" });

    // The input field should display the date and time in the user's timezone
    expect(".o_datetime_input").toHaveValue("03/27/2017 16:42");

    // Change the date in the datepicker
    await contains(".o_datetime_input").click();
    await contains(getPickerCell("26")).click();
    await press("enter");

    // The input field should display the date and time in the user's timezone
    expect(".o_datetime_input").toHaveValue("03/26/2017 16:42");
});

test("building a domain with an invalid path", async () => {
    await makeDomainSelector({
        domain: `[("fooooooo", "=", "abc")]`,
        update(domain) {
            expect(domain).toBe(`[("bar", "!=", False)]`);
        },
    });

    expect(getCurrentPath()).toBe("fooooooo");
    expect(".o_model_field_selector_warning").toHaveCount(1);
    expect(".o_model_field_selector_warning").toHaveAttribute(
        "data-tooltip",
        "Invalid field chain"
    );
    expect(getOperatorOptions()).toHaveLength(1);
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("abc");

    await openModelFieldSelectorPopover();
    await contains(".o_model_field_selector_popover_item_name").click();
    expect(getCurrentPath()).toBe("Bar");
    expect(getCurrentOperator()).toBe("set");
});

test("building a domain with an invalid path (2)", async () => {
    await makeDomainSelector({
        domain: `[(bloup, "=", "abc")]`,
        update(domain) {
            expect(domain).toBe(`[("id", "=", 1)]`);
        },
    });

    expect(getCurrentPath()).toBe("bloup");
    expect(isNotSupportedPath()).toBe(true);
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("abc");

    await clearNotSupported();
    expect(getCurrentPath()).toBe("Id");
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("1");
});

test("building a domain with an invalid path (3)", async () => {
    Partner._fields.user_id = fields.Many2one({
        string: "User",
        relation: "users",
    });
    defineModels([class Users extends models.Model {}]);
    await makeDomainSelector({
        domain: `[(bloup, "=", "abc")]`,
        update(domain) {
            expect(domain).toBe(`[("user_id", "in", [])]`);
        },
    });

    expect(getCurrentPath()).toBe("bloup");
    expect(isNotSupportedPath()).toBe(true);
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("abc");

    await clearNotSupported();
    expect(getCurrentPath()).toBe("User");
    expect(getCurrentOperator()).toBe("is in");
    expect(getCurrentValue()).toBe("");
});

test("building a domain with an invalid operator", async () => {
    await makeDomainSelector({
        domain: `[("foo", "!!!!=!!!!", "abc")]`,
        update(domain) {
            expect(domain).toBe(`[("foo", "=", "abc")]`);
        },
    });

    expect(getCurrentPath()).toBe("Foo");
    expect(".o_model_field_selector_warning").toHaveCount(0);
    expect(getCurrentOperator()).toBe(`"!!!!=!!!!"`);
    expect(isNotSupportedOperator()).toBe(true);
    expect(getCurrentValue()).toBe("abc");

    await clearNotSupported();
    expect(getCurrentPath()).toBe("Foo");
    expect(".o_model_field_selector_warning").toHaveCount(0);
    expect(getOperatorOptions()).toHaveLength(10);
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("abc");
});

test("building a domain with an expression for value", async () => {
    mockDate("2023-04-20 17:00:00", 0);

    await makeDomainSelector({
        domain: `[("datetime", ">=", context_today())]`,
        update(domain) {
            expect(domain).toBe(`[("datetime", ">=", "2023-04-20 00:00:00")]`);
        },
    });

    expect(getCurrentValue()).toBe("context_today()");
    await clearNotSupported();
    expect(getCurrentValue()).toBe("04/20/2023 00:00");
});

test("building a domain with an expression in value", async () => {
    await makeDomainSelector({
        domain: `[("int", "=", id)]`,
        update(domain) {
            expect(domain).toBe(`[("int", "<", 1)]`);
        },
    });

    expect(getCurrentPath()).toBe("Int");
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("id");

    await selectOperator("<");

    expect(getCurrentPath()).toBe("Int");
    expect(getCurrentOperator()).toBe("lower");
    expect(getCurrentValue()).toBe("1");
});

test("building a domain with a m2o without following the relation", async () => {
    await makeDomainSelector({
        domain: `[("product_id", "ilike", 1)]`,
        isDebugMode: true,
        update: (domain) => {
            expect.step(domain);
        },
    });
    expect.verifySteps([]);
    expect(isNotSupportedValue()).toBe(true);

    await clearNotSupported();
    expect.verifySteps([`[("product_id", "ilike", "")]`]);

    await contains(`${SELECTORS.valueEditor} input`).edit("pad");
    expect.verifySteps([`[("product_id", "ilike", "pad")]`]);
});

test("editing a domain with `parent` key", async () => {
    await makeDomainSelector({
        resModel: "product",
        domain: `[("name", "=", parent.foo)]`,
        isDebugMode: true,
    });

    expect.assertions(2);

    expect(getCurrentValue()).toBe("parent.foo");
    expect(isNotSupportedValue()).toBe(true);
});

test("edit a domain with the debug textarea", async () => {
    expect.assertions(5);

    let newDomain;
    await makeDomainSelector({
        domain: `[("product_id", "ilike", 1)]`,
        isDebugMode: true,
        update(domain, fromDebug) {
            expect(domain).toBe(newDomain);
            expect(fromDebug).toBe(true);
        },
    });

    expect(SELECTORS.condition).toHaveCount(1);

    newDomain = `[['product_id', 'ilike', 1],['id', '=', 0]]`;
    await contains(SELECTORS.debugArea).edit(newDomain, {
        message: "the domain should not have been formatted",
    });
    expect(SELECTORS.debugArea).toHaveValue(newDomain);
    expect(SELECTORS.condition).toHaveCount(2);
});

test("set [(1, '=', 1)] or [(0, '=', 1)] as domain with the debug textarea", async () => {
    expect.assertions(11);

    let newDomain;
    await makeDomainSelector({
        domain: `[("product_id", "ilike", 1)]`,
        isDebugMode: true,
        update(domain, fromDebug) {
            expect(domain).toBe(newDomain);
            expect(fromDebug).toBe(true);
        },
    });

    expect(SELECTORS.condition).toHaveCount(1);

    newDomain = `[(1, "=", 1)]`;
    await contains(SELECTORS.debugArea).edit(newDomain);
    expect(SELECTORS.debugArea).toHaveValue(newDomain, {
        message: "the domain should not have been formatted",
    });

    newDomain = `[(0, "=", 1)]`;
    await contains(SELECTORS.debugArea).edit(newDomain);
    expect(SELECTORS.debugArea).toHaveValue(newDomain, {
        message: "the domain should not have been formatted",
    });
    expect(SELECTORS.condition).toHaveCount(1);
    expect(getCurrentPath()).toBe("0");
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("1");
});

test("operator fallback (mode readonly)", async () => {
    await makeDomainSelector({
        domain: `[['foo', 'like', 'kikou']]`,
        readonly: true,
    });
    expect(getConditionText()).toBe(`Foo like kikou`);
});

test("cache fields_get", async () => {
    onRpc("fields_get", ({ method }) => expect.step(method));

    await makeDomainSelector({
        domain: "['&', ['foo', '=', 'kikou'], ['bar', '=', 'true']]",
    });
    expect.verifySteps(["fields_get"]);
});

test("selection field with operator change from 'set' to '='", async () => {
    await makeDomainSelector({ domain: `[['state', '!=', False]]` });
    expect(getCurrentPath()).toBe("State");
    expect(getCurrentOperator()).toBe("set");

    await selectOperator("=");
    expect(getCurrentPath()).toBe("State");
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe(`ABC`);
});

test("show correct operator", async () => {
    await makeDomainSelector({ domain: `[['state', 'in', ['abc']]]` });
    expect(getCurrentOperator()).toBe("is in");
});

test("multi selection", async () => {
    class Parent extends Component {
        static components = { DomainSelector };
        static template = xml`
            <DomainSelector
                resModel="'partner'"
                domain="domain"
                readonly="false"
                update.bind="update"
            />
        `;
        static props = ["*"];
        setup() {
            this.domain = `[("state", "in", ["a", "b", "c"])]`;
        }
        update(domain) {
            this.domain = domain;
            this.render();
        }
    }

    // Create the domain selector and its mock environment
    const comp = await mountWithCleanup(Parent);
    expect(comp.domain).toBe(`[("state", "in", ["a", "b", "c"])]`);
    expect(queryAllTexts(SELECTORS.tag)).toEqual(["a", "b", "c"]);
    expect(`${SELECTORS.valueEditor} select`).toHaveCount(1);

    await contains(`${SELECTORS.valueEditor} .o_tag .o_delete`).click();
    expect(comp.domain).toBe(`[("state", "in", ["b", "c"])]`);

    await selectValue("abc");
    expect(comp.domain).toBe(`[("state", "in", ["b", "c", "abc"])]`);
    const tags = queryAll(SELECTORS.tag);
    expect(tags[0]).toHaveClass("o_tag_color_2");
    expect(tags[1]).toHaveClass("o_tag_color_2");
    expect(tags[2]).toHaveClass("o_tag_color_0");
});

test("json field with operator change from 'equal' to 'ilike'", async () => {
    await makeDomainSelector({ domain: `[['json_field', '=', "hey"]]` });
    expect(getCurrentPath()).toBe(`Json Field`);
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe(`hey`);

    await selectOperator("ilike");
    expect(getCurrentOperator()).toBe("contains");
});

test("parse -1", async () => {
    class Parent extends Component {
        static components = { DomainSelector };
        static template = xml`
            <DomainSelector resModel="'partner'" domain="domain" readonly="false"/>
        `;
        static props = ["*"];
        setup() {
            this.domain = `[("id", "=", -1)]`;
        }
    }
    await mountWithCleanup(Parent);
    expect(getCurrentValue()).toBe("-1");
});

test("parse 3-1", async () => {
    class Parent extends Component {
        static components = { DomainSelector };
        static template = xml`
            <DomainSelector resModel="'partner'" domain="domain" readonly="false"/>
        `;
        static props = ["*"];
        setup() {
            this.domain = `[("id", "=", 3-1)]`;
        }
    }
    await mountWithCleanup(Parent);
    expect(getCurrentValue()).toBe("3 - 1");
});

test("domain not supported (mode readonly)", async () => {
    await mountWithCleanup(DomainSelector, {
        props: {
            resModel: "partner",
            domain: `[`,
            readonly: true,
            isDebugMode: false,
        },
    });
    expect(SELECTORS.resetButton).toHaveCount(0);
    expect(SELECTORS.debugArea).toHaveCount(0);
});

test("domain not supported (mode readonly + mode debug)", async () => {
    await mountWithCleanup(DomainSelector, {
        props: {
            resModel: "partner",
            domain: `[`,
            readonly: true,
            isDebugMode: true,
        },
    });
    expect(SELECTORS.resetButton).toHaveCount(0);
    expect(SELECTORS.debugArea).toHaveCount(1);
    expect(SELECTORS.debugArea).toHaveAttribute("readonly");
});

test("domain not supported (mode edit)", async () => {
    await mountWithCleanup(DomainSelector, {
        props: {
            resModel: "partner",
            domain: `[`,
            readonly: false,
            isDebugMode: false,
        },
    });
    expect(SELECTORS.resetButton).toHaveCount(1);
    expect(SELECTORS.debugArea).toHaveCount(0);
});

test("domain not supported (mode edit + mode debug)", async () => {
    await makeDomainSelector({
        domain: `[`,
        isDebugMode: true,
    });
    expect(SELECTORS.resetButton).toHaveCount(1);
    expect(SELECTORS.debugArea).toHaveCount(1);
    expect(SELECTORS.debugArea).not.toHaveAttribute("readonly");
});

test("reset domain", async () => {
    await makeDomainSelector({
        domain: `[`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(".o_domain_selector").toHaveText("This domain is not supported.\nReset domain");
    expect(SELECTORS.resetButton).toHaveCount(1);
    expect(SELECTORS.addNewRule).toHaveCount(0);

    await contains(SELECTORS.resetButton).click();
    expect(".o_domain_selector").toHaveText("Match all records\nNew Rule");
    expect(SELECTORS.resetButton).toHaveCount(0);
    expect(SELECTORS.addNewRule).toHaveCount(1);
    expect.verifySteps(["[]"]);
});

test("default condition depends on available fields", async () => {
    Partner._fields.user_id = fields.Many2one({
        string: "User",
        relation: "users",
    });
    defineModels([class Users extends models.Model {}]);
    await makeDomainSelector({
        update(domain) {
            expect.step(domain);
        },
    });
    expect(".o_domain_selector").toHaveText("Match all records\nNew Rule");
    await addNewRule();
    expect.verifySteps(['[("user_id", "in", [])]']);
});

test("debug input in model field selector popover", async () => {
    class Parent extends Component {
        static components = { DomainSelector };
        static template = xml`
            <DomainSelector
                resModel="'partner'"
                domain="domain"
                readonly="false"
                isDebugMode="true"
                update.bind="update"
            />
        `;
        static props = ["*"];
        setup() {
            this.domain = `[("id", "=", 1)]`;
        }
        update(domain) {
            expect.step(domain);
            this.domain = domain;
            this.render();
        }
    }
    await mountWithCleanup(Parent);
    await openModelFieldSelectorPopover();
    await contains(".o_model_field_selector_debug").edit("a", { confirm: "tab" });
    await contains(".o_model_field_selector_popover_close").click();
    expect.verifySteps([`[("a", "=", 1)]`]);
    expect(getCurrentPath()).toBe("a");
    expect(".o_model_field_selector_warning").toHaveCount(1);
    expect(getOperatorOptions()).toHaveLength(1);
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("1");
    expect(SELECTORS.debugArea).toHaveValue(`[("a", "=", 1)]`);
});

test("between operator", async () => {
    mockTimeZone(0);
    await makeDomainSelector({
        domain: `["&", ("datetime", ">=", "2023-01-01 00:00:00"), ("datetime", "<=", "2023-01-10 23:59:59")]`,
        isDebugMode: true,
        update(domain) {
            expect.step(domain);
        },
    });

    expect(SELECTORS.condition).toHaveCount(1);
    expect(getCurrentOperator()).toBe("between");
    expect(".o_datetime_input").toHaveCount(2);

    await contains(".o_datetime_input:first").edit("2023-01-02 00:00:00");
    expect.verifySteps([
        `["&", ("datetime", ">=", "2023-01-02 00:00:00"), ("datetime", "<=", "2023-01-10 23:59:59")]`,
    ]);

    await contains(".o_datetime_input:eq(1)").edit("2023-01-08 00:00:00");
    expect.verifySteps([
        `["&", ("datetime", ">=", "2023-01-02 00:00:00"), ("datetime", "<=", "2023-01-08 00:00:00")]`,
    ]);
});

test("between operator (2)", async () => {
    mockTimeZone(0);
    await makeDomainSelector({
        domain: `["&", "&", ("foo", "=", "abc"), ("datetime", ">=", "2023-01-01 00:00:00"), ("datetime", "<=", "2023-01-10 23:59:59")]`,
    });
    expect(SELECTORS.condition).toHaveCount(2);
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentOperator(1)).toBe("between");
    expect(".o_datetime_input").toHaveCount(2);
});

test("between operator (3)", async () => {
    mockTimeZone(0);
    await makeDomainSelector({
        domain: `["&", "&", ("datetime", ">=", "2023-01-01 00:00:00"), ("datetime", "<=", "2023-01-10 23:59:59"), ("foo", "=", "abc")]`,
    });
    expect(SELECTORS.condition).toHaveCount(2);
    expect(getCurrentOperator()).toBe("between");
    expect(getCurrentOperator(1)).toBe("equals");
    expect(".o_datetime_input").toHaveCount(2);
});

test("between operator (4)", async () => {
    mockTimeZone(0);
    await makeDomainSelector({
        domain: `["&", ("datetime", ">=", "2023-01-01 00:00:00"), "&", ("datetime", "<=", "2023-01-10 00:00:00"), ("foo", "=", "abc")]`,
    });
    expect(SELECTORS.condition).toHaveCount(2);
    expect(getCurrentOperator()).toBe("between");
    expect(getCurrentOperator(1)).toBe("equals");
    expect(".o_datetime_input").toHaveCount(2);
});

test("between operator (5)", async () => {
    mockTimeZone(0);
    await makeDomainSelector({
        domain: `["|", "&", ("create_date", ">=", "2023-04-01 00:00:00"), ("create_date", "<=", "2023-04-30 23:59:59"), (0, "=", 1)]`,
        readonly: true,
    });
    expect(".o_domain_selector").toHaveText(
        `Match\nany\nof the following rules:\nCreated on\nbetween\n04/01/2023 00:00:00\nand\n04/30/2023 23:59:59\n0\n=\n1`
    );
});

test("expressions in between operator", async () => {
    mockDate("2023-01-01 00:00:00", 0);

    await makeDomainSelector({
        domain: `["&", ("datetime", ">=", context_today()), ("datetime", "<=", "2023-01-10 00:00:00")]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(SELECTORS.condition).toHaveCount(1);
    expect(getCurrentOperator()).toBe("between");
    expect(SELECTORS.valueEditor).toHaveCount(1);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}`).toHaveCount(2);
    expect(SELECTORS.clearNotSupported).toHaveCount(1);
    expect(`${SELECTORS.editor} .o_datetime_input`).toHaveCount(1);

    await clearNotSupported();
    expect(SELECTORS.valueEditor).toHaveCount(1);
    expect(`${SELECTORS.editor} .o_datetime_input`).toHaveCount(2);
    expect.verifySteps([
        `["&", ("datetime", ">=", "2023-01-01 00:00:00"), ("datetime", "<=", "2023-01-10 00:00:00")]`,
    ]);
});

test("support of connector '!' (mode readonly)", async () => {
    const toTest = [
        {
            domain: `["!", ("foo", "=", "abc")]`,
            result: `Match\nall\nof the following rules:\nFoo\nnot =\nabc`,
        },
        {
            domain: `["!", "!", ("foo", "=", "abc")]`,
            result: `Match\nall\nof the following rules:\nFoo\n=\nabc`,
        },
        {
            domain: `["!", "!", "!", ("foo", "=", "abc")]`,
            result: `Match\nall\nof the following rules:\nFoo\nnot =\nabc`,
        },
        {
            domain: `["!", "&", ("foo", "=", "abc"), ("foo", "=", "def")]`,
            result: `Match\nany\nof the following rules:\nFoo\nnot =\nabc\nFoo\nnot =\ndef`,
        },
        {
            domain: `["!", "|", ("foo", "=", "abc"), ("foo", "=", "def")]`,
            result: `Match\nall\nof the following rules:\nFoo\nnot =\nabc\nFoo\nnot =\ndef`,
        },
        {
            domain: `["&", "!", ("foo", "=", "abc"), ("foo", "=", "def")]`,
            result: `Match\nall\nof the following rules:\nFoo\nnot =\nabc\nFoo\n=\ndef`,
        },
        {
            domain: `["&", "!", "!", ("foo", "=", "abc"), ("foo", "=", "def")]`,
            result: `Match\nall\nof the following rules:\nFoo\n=\nabc\nFoo\n=\ndef`,
        },
        {
            domain: `["&", ("foo", "=", "abc"), "!", ("foo", "=", "def")]`,
            result: `Match\nall\nof the following rules:\nFoo\n=\nabc\nFoo\nnot =\ndef`,
        },
        {
            domain: `["&", ("foo", "=", "abc"), "!", "!", ("foo", "=", "def")]`,
            result: `Match\nall\nof the following rules:\nFoo\n=\nabc\nFoo\n=\ndef`,
        },
        {
            domain: `["|", "!", ("foo", "=", "abc"), ("foo", "=", "def")]`,
            result: `Match\nany\nof the following rules:\nFoo\nnot =\nabc\nFoo\n=\ndef`,
        },
        {
            domain: `["|", "!", "!", ("foo", "=", "abc"), ("foo", "=", "def")]`,
            result: `Match\nany\nof the following rules:\nFoo\n=\nabc\nFoo\n=\ndef`,
        },
        {
            domain: `["|", ("foo", "=", "abc"), "!", ("foo", "=", "def")]`,
            result: `Match\nany\nof the following rules:\nFoo\n=\nabc\nFoo\nnot =\ndef`,
        },
        {
            domain: `["|", ("foo", "=", "abc"), "!", "!", ("foo", "=", "def")]`,
            result: `Match\nany\nof the following rules:\nFoo\n=\nabc\nFoo\n=\ndef`,
        },
        {
            domain: `["&", "!", "&", ("foo", "=", "abc"), ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nall\nof the following rules:\nany\nof:\nFoo\nnot =\nabc\nFoo\nnot =\ndef\nFoo\n=\nghi`,
        },
        {
            domain: `["&", "!", "|", ("foo", "=", "abc"), ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nall\nof the following rules:\nFoo\nnot =\nabc\nFoo\nnot =\ndef\nFoo\n=\nghi`,
        },
        {
            domain: `["|", "!", "&", ("foo", "=", "abc"), ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nany\nof the following rules:\nFoo\nnot =\nabc\nFoo\nnot =\ndef\nFoo\n=\nghi`,
        },
        {
            domain: `["|", "!", "|", ("foo", "=", "abc"), ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nany\nof the following rules:\nall\nof:\nFoo\nnot =\nabc\nFoo\nnot =\ndef\nFoo\n=\nghi`,
        },
        {
            domain: `["!", "&", "&", ("foo", "=", "abc"), ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nany\nof the following rules:\nFoo\nnot =\nabc\nFoo\nnot =\ndef\nFoo\nnot =\nghi`,
        },
        {
            domain: `["!", "|", "|", ("foo", "=", "abc"), ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nall\nof the following rules:\nFoo\nnot =\nabc\nFoo\nnot =\ndef\nFoo\nnot =\nghi`,
        },
        {
            domain: `["!", "&", "|", ("foo", "=", "abc"), "!", ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nany\nof the following rules:\nall\nof:\nFoo\nnot =\nabc\nFoo\n=\ndef\nFoo\nnot =\nghi`,
        },
        {
            domain: `["!", "|", "&", ("foo", "=", "abc"), ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nall\nof the following rules:\nany\nof:\nFoo\nnot =\nabc\nFoo\nnot =\ndef\nFoo\nnot =\nghi`,
        },
        {
            domain: `["!", "&", ("foo", "=", "abc"), "|", ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nany\nof the following rules:\nFoo\nnot =\nabc\nall\nof:\nFoo\nnot =\ndef\nFoo\nnot =\nghi`,
        },
        {
            domain: `["!", "|", ("foo", "=", "abc"), "&", ("foo", "=", "def"), ("foo", "!=", "ghi")]`,
            result: `Match\nall\nof the following rules:\nFoo\nnot =\nabc\nany\nof:\nFoo\nnot =\ndef\nFoo\nnot not =\nghi`,
        },
        {
            domain: `["!", "|", ("foo", "=", "abc"), "&", ("foo", "!=", "def"), "!", ("foo", "=", "ghi")]`,
            result: `Match\nall\nof the following rules:\nFoo\nnot =\nabc\nany\nof:\nFoo\nnot not =\ndef\nFoo\n=\nghi`,
        },
    ];

    class Parent extends Component {
        static components = { DomainSelector };
        static template = xml`<DomainSelector resModel="'partner'" domain="state.domain"/>`;
        static props = ["*"];
        setup() {
            this.state = useState({ domain: `[]` });
        }
    }

    const parent = await mountWithCleanup(Parent);

    for (const { domain, result } of toTest) {
        parent.state.domain = domain;
        await animationFrame();
        expect(".o_domain_selector").toHaveText(result);
    }
});

test("support of connector '!' (debug mode)", async () => {
    const toTest = [
        {
            domain: `["!", ("foo", "=", "abc")]`,
            result: `Match\nall\nof the following rules:\nFoo\nnot =\nabc`,
        },
        {
            domain: `["!", "!", ("foo", "=", "abc")]`,
            result: `Match\nall\nof the following rules:\nFoo\n=\nabc`,
        },
        {
            domain: `["!", "!", "!", ("foo", "=", "abc")]`,
            result: `Match\nall\nof the following rules:\nFoo\nnot =\nabc`,
        },
        {
            domain: `["!", "&", ("foo", "=", "abc"), ("foo", "=", "def")]`,
            result: `Match\nnot all\nof the following rules:\nFoo\n=\nabc\nFoo\n=\ndef`,
        },
        {
            domain: `["!", "|", ("foo", "=", "abc"), ("foo", "=", "def")]`,
            result: `Match\nnone\nof the following rules:\nFoo\n=\nabc\nFoo\n=\ndef`,
        },
        {
            domain: `["&", "!", ("foo", "=", "abc"), ("foo", "=", "def")]`,
            result: `Match\nall\nof the following rules:\nFoo\nnot =\nabc\nFoo\n=\ndef`,
        },
        {
            domain: `["&", "!", "!", ("foo", "=", "abc"), ("foo", "=", "def")]`,
            result: `Match\nall\nof the following rules:\nFoo\n=\nabc\nFoo\n=\ndef`,
        },
        {
            domain: `["&", ("foo", "=", "abc"), "!", ("foo", "=", "def")]`,
            result: `Match\nall\nof the following rules:\nFoo\n=\nabc\nFoo\nnot =\ndef`,
        },
        {
            domain: `["&", ("foo", "=", "abc"), "!", "!", ("foo", "=", "def")]`,
            result: `Match\nall\nof the following rules:\nFoo\n=\nabc\nFoo\n=\ndef`,
        },
        {
            domain: `["|", "!", ("foo", "=", "abc"), ("foo", "=", "def")]`,
            result: `Match\nany\nof the following rules:\nFoo\nnot =\nabc\nFoo\n=\ndef`,
        },
        {
            domain: `["|", "!", "!", ("foo", "=", "abc"), ("foo", "=", "def")]`,
            result: `Match\nany\nof the following rules:\nFoo\n=\nabc\nFoo\n=\ndef`,
        },
        {
            domain: `["|", ("foo", "=", "abc"), "!", ("foo", "=", "def")]`,
            result: `Match\nany\nof the following rules:\nFoo\n=\nabc\nFoo\nnot =\ndef`,
        },
        {
            domain: `["|", ("foo", "=", "abc"), "!", "!", ("foo", "=", "def")]`,
            result: `Match\nany\nof the following rules:\nFoo\n=\nabc\nFoo\n=\ndef`,
        },
        {
            domain: `["&", "!", "&", ("foo", "=", "abc"), ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nall\nof the following rules:\nnot all\nof:\nFoo\n=\nabc\nFoo\n=\ndef\nFoo\n=\nghi`,
        },
        {
            domain: `["&", "!", "|", ("foo", "=", "abc"), ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nall\nof the following rules:\nnone\nof:\nFoo\n=\nabc\nFoo\n=\ndef\nFoo\n=\nghi`,
        },
        {
            domain: `["|", "!", "&", ("foo", "=", "abc"), ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nany\nof the following rules:\nnot all\nof:\nFoo\n=\nabc\nFoo\n=\ndef\nFoo\n=\nghi`,
        },
        {
            domain: `["|", "!", "|", ("foo", "=", "abc"), ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nany\nof the following rules:\nnone\nof:\nFoo\n=\nabc\nFoo\n=\ndef\nFoo\n=\nghi`,
        },
        {
            domain: `["!", "&", "&", ("foo", "=", "abc"), ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nnot all\nof the following rules:\nFoo\n=\nabc\nFoo\n=\ndef\nFoo\n=\nghi`,
        },
        {
            domain: `["!", "|", "|", ("foo", "=", "abc"), ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nnone\nof the following rules:\nFoo\n=\nabc\nFoo\n=\ndef\nFoo\n=\nghi`,
        },
        {
            domain: `["!", "&", "|", ("foo", "=", "abc"), "!", ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nnot all\nof the following rules:\nany\nof:\nFoo\n=\nabc\nFoo\nnot =\ndef\nFoo\n=\nghi`,
        },
        {
            domain: `["!", "|", "&", ("foo", "=", "abc"), ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nnone\nof the following rules:\nall\nof:\nFoo\n=\nabc\nFoo\n=\ndef\nFoo\n=\nghi`,
        },
        {
            domain: `["!", "&", ("foo", "=", "abc"), "|", ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nnot all\nof the following rules:\nFoo\n=\nabc\nany\nof:\nFoo\n=\ndef\nFoo\n=\nghi`,
        },
        {
            domain: `["!", "|", ("foo", "=", "abc"), "&", ("foo", "=", "def"), ("foo", "=", "ghi")]`,
            result: `Match\nnone\nof the following rules:\nFoo\n=\nabc\nall\nof:\nFoo\n=\ndef\nFoo\n=\nghi`,
        },
        {
            domain: `["!", "|", ("foo", "=", "abc"), "&", ("foo", "=", "def"), "!", ("foo", "=", "ghi")]`,
            result: `Match\nnone\nof the following rules:\nFoo\n=\nabc\nall\nof:\nFoo\n=\ndef\nFoo\nnot =\nghi`,
        },
    ];

    class Parent extends Component {
        static components = { DomainSelector };
        static template = xml`<DomainSelector resModel="'partner'" isDebugMode="true" domain="state.domain"/>`;
        static props = ["*"];
        setup() {
            this.state = useState({ domain: `[]` });
        }
    }

    const parent = await mountWithCleanup(Parent);

    for (const { domain, result } of toTest) {
        parent.state.domain = domain;
        await animationFrame();
        expect(".o_domain_selector").toHaveText(result);
    }
});

test("support properties", async () => {
    expect.assertions(25);

    mockDate("2023-10-05 15:00:00", 0);

    Partner._fields.properties = fields.Properties({
        string: "Properties",
        definition_record: "product_id",
        definition_record_field: "definitions",
    });
    Product._fields.definitions = fields.PropertiesDefinition({
        string: "Definitions",
    });
    Product._records[0].definitions = [
        { name: "xphone_prop_1", string: "Boolean", type: "boolean" },
        { name: "xphone_prop_2", string: "Selection", type: "selection", selection: [] },
        { name: "xphone_prop_3", string: "Char", type: "char" },
        { name: "xphone_prop_4", string: "Integer", type: "integer" },
        { name: "xphone_prop_5", string: "Date", type: "date" },
        { name: "xphone_prop_6", string: "Tags", type: "tags" },
        { name: "xphone_prop_7", string: "M2M", type: "many2many", comodel: "partner" },
    ];
    Product._records[1].definitions = [
        { name: "xpad_prop_1", string: "M2O", type: "many2one", comodel: "partner" },
    ];

    let expectedDomain = `[("id", "=", 1)]`;

    class Parent extends Component {
        static template = xml`
            <DomainSelector
                resModel="'partner'"
                domain="domain"
                readonly="false"
                isDebugMode="true"
                update.bind="update"
            />
        `;
        static components = { DomainSelector };
        static props = ["*"];
        setup() {
            this.domain = expectedDomain;
        }
        update(domain) {
            expect(domain).toBe(expectedDomain);
            this.domain = domain;
            this.render();
        }
    }

    await mountWithCleanup(Parent);
    await openModelFieldSelectorPopover();
    await contains(
        ".o_model_field_selector_popover_item[data-name='properties'] .o_model_field_selector_popover_relation_icon"
    ).click();
    expect(getCurrentPath()).toBe("Properties");
    expectedDomain = `[("properties.xpad_prop_1", "=", False)]`;
    await contains(".o_model_field_selector_popover_item[data-name='xpad_prop_1'] button").click();
    expect(getCurrentPath()).toBe("Properties > M2O");
    expect(getOperatorOptions()).toEqual(["equals", "not equals", "set", "not set"]);

    const toTests = [
        {
            name: "xphone_prop_1",
            domain: `[("properties.xphone_prop_1", "!=", False)]`,
            options: ["set", "not set"],
        },
        {
            name: "xphone_prop_2",
            domain: `[("properties.xphone_prop_2", "=", False)]`,
            options: ["equals", "not equals", "set", "not set"],
        },
        {
            name: "xphone_prop_3",
            domain: `[("properties.xphone_prop_3", "=", "")]`,
            options: [
                "equals",
                "not equals",
                "contains",
                "not contains",
                "is in",
                "is not in",
                "set",
                "not set",
                "starts with",
                "ends with",
            ],
        },
        {
            name: "xphone_prop_4",
            domain: `[("properties.xphone_prop_4", "=", 1)]`,
            options: [
                "equals",
                "not equals",
                "greater",
                "lower",
                "between",
                "not between",
                "contains",
                "not contains",
                "set",
                "not set",
            ],
        },
        {
            name: "xphone_prop_5",
            domain: `[("properties.xphone_prop_5", "=", context_today().strftime("%Y-%m-%d"))]`,
            options: [
                "today",
                "not today",
                "equals",
                "not equals",
                "greater",
                "lower",
                "between",
                "not between",
                "next",
                "not next",
                "last",
                "not last",
                "set",
                "not set",
            ],
        },
        {
            name: "xphone_prop_6",
            domain: `[("properties.xphone_prop_6", "in", "")]`,
            options: ["is in", "is not in", "set", "not set"],
        },
        {
            name: "xphone_prop_7",
            domain: `[("properties.xphone_prop_7", "in", [])]`,
            options: ["is in", "is not in", "set", "not set"],
        },
    ];

    for (const { name, domain, options } of toTests) {
        await openModelFieldSelectorPopover();
        expectedDomain = domain;
        await contains(`.o_model_field_selector_popover_item[data-name='${name}'] button`).click();
        const { string } = MockServer.env["product"][0].definitions.find(
            (def) => def.name === name
        );
        expect(getCurrentPath()).toBe(`Properties > ${string}`);
        expect(getOperatorOptions()).toEqual(options);
    }
});

test("support properties (mode readonly)", async () => {
    Partner._fields.properties = fields.Properties({
        string: "Properties",
        definition_record: "product_id",
        definition_record_field: "definitions",
    });
    Product._fields.definitions = fields.PropertiesDefinition({
        string: "Definitions",
    });
    Product._records[0].definitions = [
        { name: "xphone_prop_1", string: "Boolean", type: "boolean" },
        {
            name: "xphone_prop_2",
            string: "Selection",
            type: "selection",
            selection: [["abc", "ABC"]],
        },
        { name: "xphone_prop_3", string: "Char", type: "char" },
        { name: "xphone_prop_4", string: "Integer", type: "integer" },
        { name: "xphone_prop_5", string: "Date", type: "date" },
        { name: "xphone_prop_6", string: "Tags", type: "tags" },
        { name: "xphone_prop_7", string: "M2M", type: "many2many", comodel: "product" },
    ];
    Product._records[1].definitions = [
        { name: "xpad_prop_1", string: "M2O", type: "many2one", comodel: "product" },
    ];

    defineParams({
        lang_parameters: {
            date_format: "%d|%m|%Y",
        },
    });
    onRpc(() => {});
    const toTest = [
        {
            domain: `[("properties.xphone_prop_1", "=", False)]`,
            result: "Properties ➔ Boolean not set",
        },
        {
            domain: `[("properties.xphone_prop_2", "=", "abc")]`,
            result: "Properties ➔ Selection = ABC",
        },
        {
            domain: `[("properties.xphone_prop_3", "=", "def")]`,
            result: "Properties ➔ Char = def",
        },
        {
            domain: `[("properties.xphone_prop_4", "=", 1)]`,
            result: "Properties ➔ Integer = 1",
        },
        {
            domain: `[("properties.xphone_prop_5", "=", "2023-10-05")]`,
            result: "Properties ➔ Date = 05|10|2023",
        },
        {
            domain: `[("properties.xphone_prop_6", "in", "g")]`,
            result: "Properties ➔ Tags = g",
        },
        {
            domain: `[("properties.xphone_prop_7", "in", [37])]`,
            result: "Properties ➔ M2M = xphone",
        },
        {
            domain: `[("properties.xpad_prop_1", "=", 41)]`,
            result: "Properties ➔ M2O = xpad",
        },
    ];

    class Parent extends Component {
        static components = { DomainSelector };
        static template = xml`<DomainSelector resModel="'partner'" domain="state.domain"/>`;
        static props = ["*"];
        setup() {
            this.state = useState({ domain: `[]` });
        }
    }

    const parent = await mountWithCleanup(Parent);

    for (const { domain, result } of toTest) {
        parent.state.domain = domain;
        await animationFrame();
        expect(getConditionText()).toBe(result);
    }
});

test("no button 'New Rule' (mode readonly)", async () => {
    await makeDomainSelector({
        readonly: true,
        domain: `[("bar", "=", True)]`,
    });
    expect(SELECTORS.condition).toHaveCount(1);
    expect("a[role=button]").toHaveCount(0);
});

test("button 'New Rule' (edit mode)", async () => {
    await makeDomainSelector();
    expect(SELECTORS.condition).toHaveCount(0);
    expect(SELECTORS.addNewRule).toHaveCount(1);

    await addNewRule();
    expect(SELECTORS.condition).toHaveCount(1);
    expect(SELECTORS.addNewRule).toHaveCount(1);

    await addNewRule();
    expect(SELECTORS.condition).toHaveCount(2);
    expect(SELECTORS.addNewRule).toHaveCount(1);
});

test("updating path should also update operator if invalid", async () => {
    await makeDomainSelector({
        domain: `[("id", "<", 0)]`,
        update: (domain) => {
            expect(domain).toBe(`[("foo", "=", "")]`);
        },
    });

    await openModelFieldSelectorPopover();
    await contains(".o_model_field_selector_popover_item[data-name=foo] button").click();
});

test("treat false and true like False and True", async () => {
    const parent = await makeDomainSelector({
        resModel: "partner",
        domain: `[("bar","=",false)]`,
        readonly: true,
    });
    expect(getConditionText()).toBe(`Bar not set`);
    await parent.set(`[("bar","=",true)]`);
    expect(getConditionText()).toBe(`Bar set`);
});

test("Edit the value for field char and an operator in", async () => {
    const parent = await makeDomainSelector({
        resModel: "partner",
        domain: `[("foo", "in", ["a", "b", uid])]`,
        update: (domain) => {
            expect.step(domain);
        },
        isDebugMode: true,
    });
    expect(queryAllTexts(SELECTORS.tag)).toEqual([`"a"`, `"b"`, `uid`]);
    expect(queryAllAttributes(SELECTORS.tag, "data-color")).toEqual(["0", "0", "2"]);

    await editValue("c");
    expect(queryAllTexts(SELECTORS.tag)).toEqual([`"a"`, `"b"`, `uid`, `"c"`]);
    expect.verifySteps([`[("foo", "in", ["a", "b", uid, "c"])]`]);

    await contains(".o_tag .o_delete:eq(2)").click();
    expect(queryAllTexts(SELECTORS.tag)).toEqual([`a`, `b`, `c`]);
    expect.verifySteps([`[("foo", "in", ["a", "b", "c"])]`]);

    await parent.set(`[("foo", "in", ["a"])]`);
    expect(queryAllTexts(SELECTORS.tag)).toEqual([`a`]);

    await editValue("b");
    expect(queryAllTexts(SELECTORS.tag)).toEqual([`a`, `b`]);
    expect.verifySteps([`[("foo", "in", ["a", "b"])]`]);
});

test("display of an unknown operator (readonly)", async () => {
    const parent = await makeDomainSelector({
        resModel: "partner",
        domain: `[("foo", "hop", "a")]`,
        readonly: true,
    });
    expect(getConditionText()).toBe(`Foo "hop" a`);

    await parent.set(`[("foo", hop, "a")]`);
    expect(getConditionText()).toBe(`Foo hop a`);
});

test("display of an unknown operator (edit)", async () => {
    const parent = await makeDomainSelector({
        resModel: "partner",
        domain: `[("foo", "hop", "a")]`,
    });
    expect(getCurrentOperator()).toBe(`"hop"`);

    await parent.set(`[("foo", hop, "a")]`);
    expect(getCurrentOperator()).toBe(`hop`);
});

test("display of negation of an unknown operator (readonly)", async () => {
    const parent = await makeDomainSelector({
        resModel: "partner",
        domain: `["!", ("foo", "hop", "a")]`,
        readonly: true,
    });
    expect(getConditionText()).toBe(`Foo not "hop" a`);

    await parent.set(`["!", ("foo", hop, "a")]`);
    expect(getConditionText()).toBe(`Foo not hop a`);
});

test("display of an operator without negation defined (readonly)", async () => {
    await makeDomainSelector({
        resModel: "partner",
        domain: `["!", ("foo", "=?", "a")]`,
        readonly: true,
    });
    expect(getConditionText()).toBe("Foo not =? a");
});

test("display of an operator without negation defined (edit)", async () => {
    await makeDomainSelector({
        resModel: "partner",
        domain: `["!", ("foo", "=?", "a")]`,
    });
    expect(getCurrentOperator()).toBe("not =?");
});

test("display of an operator without negation defined (edit) 2", async () => {
    await makeDomainSelector({
        resModel: "partner",
        domain: `["!", ("expr", "parent_of", "a")]`,
    });
    expect(getCurrentOperator()).toBe("not parent of");
});

test("display of a contextual value (readonly)", async () => {
    await makeDomainSelector({
        domain: `[("foo", "=", uid)]`,
        readonly: true,
    });
    expect(getConditionText()).toBe("Foo = uid");
});

test("boolean field (readonly)", async () => {
    const parent = await makeDomainSelector({
        readonly: true,
    });
    const toTest = [
        { domain: `[("bar", "=", True)]`, text: "Bar set" },
        { domain: `[("bar", "=", False)]`, text: "Bar not set" },
        { domain: `[("bar", "!=", True)]`, text: "Bar not set" },
        { domain: `[("bar", "!=", False)]`, text: "Bar set" },
    ];
    for (const { domain, text } of toTest) {
        await parent.set(domain);
        expect(getConditionText()).toBe(text);
    }
});

test("integer field (readonly)", async () => {
    const parent = await makeDomainSelector({
        readonly: true,
    });
    const toTest = [
        { domain: `[("int", "=", True)]`, text: `Int = true` },
        { domain: `[("int", "=", False)]`, text: `Int not set` },
        { domain: `[("int", "!=", True)]`, text: `Int not = true` },
        { domain: `[("int", "!=", False)]`, text: `Int set` },
        { domain: `[("int", "=", 1)]`, text: `Int = 1` },
        { domain: `[("int", "!=", 1)]`, text: `Int not = 1` },
        { domain: `[("int", "<", 1)]`, text: `Int lower 1` },
        { domain: `[("int", "<=", 1)]`, text: `Int lower or equal 1` },
        { domain: `[("int", ">", 1)]`, text: `Int greater 1` },
        { domain: `[("int", ">=", 1)]`, text: `Int greater or equal 1` },
        {
            domain: `["&", ("int", ">=", 1),("int","<=", 2)]`,
            text: `Int between 1 and 2`,
        },
    ];
    for (const { domain, text } of toTest) {
        await parent.set(domain);
        expect(getConditionText()).toBe(text);
    }
});

test("date field (readonly)", async () => {
    defineParams({
        lang_parameters: {
            date_format: "%d|%m|%Y",
        },
    });
    const parent = await makeDomainSelector({
        readonly: true,
    });
    const toTest = [
        { domain: `[("date", "=", False)]`, text: `Date not set` },
        { domain: `[("date", "!=", False)]`, text: `Date set` },
        { domain: `[("date", "=", "2023-07-03")]`, text: `Date = 03|07|2023` },
        { domain: `[("date", "=", context_today())]`, text: `Date = context_today()` },
        { domain: `[("date", "!=", "2023-07-03")]`, text: `Date not = 03|07|2023` },
        { domain: `[("date", "<", "2023-07-03")]`, text: `Date lower 03|07|2023` },
        { domain: `[("date", "<=", "2023-07-03")]`, text: `Date lower or equal 03|07|2023` },
        { domain: `[("date", ">", "2023-07-03")]`, text: `Date greater 03|07|2023` },
        { domain: `[("date", ">=", "2023-07-03")]`, text: `Date greater or equal 03|07|2023` },
        {
            domain: `["&", ("date", ">=", "2023-07-03"),("date","<=", "2023-07-15")]`,
            text: `Date between 03|07|2023 and 15|07|2023`,
        },
        {
            domain: `["&", ("date", ">=", "2023-07-03"),("date","<=", context_today())]`,
            text: `Date between 03|07|2023 and context_today()`,
        },
    ];
    for (const { domain, text } of toTest) {
        await parent.set(domain);
        expect(getConditionText()).toBe(text);
    }
});

test("char field (readonly)", async () => {
    const parent = await makeDomainSelector({
        readonly: true,
    });
    const toTest = [
        { domain: `[("foo", "=", False)]`, text: `Foo not set` },
        { domain: `[("foo", "!=", False)]`, text: `Foo set` },
        { domain: `[("foo", "=", "abc")]`, text: `Foo = abc` },
        { domain: `[("foo", "=", expr)]`, text: `Foo = expr` },
        { domain: `[("foo", "!=", "abc")]`, text: `Foo not = abc` },
        { domain: `[("foo", "ilike", "abc")]`, text: `Foo contains abc` },
        { domain: `[("foo", "not ilike", "abc")]`, text: `Foo not contains abc` },
        { domain: `[("foo", "in", ["abc", "def"])]`, text: `Foo = abc or def` },
        { domain: `[("foo", "not in", ["abc", "def"])]`, text: `Foo not = abc or def` },
    ];
    for (const { domain, text } of toTest) {
        await parent.set(domain);
        expect(getConditionText()).toBe(text);
    }
});

test("selection field (readonly)", async () => {
    const parent = await makeDomainSelector({
        readonly: true,
    });
    const toTest = [
        { domain: `[("state", "=", False)]`, text: `State not set` },
        { domain: `[("state", "!=", False)]`, text: `State set` },
        { domain: `[("state", "=", "abc")]`, text: `State = ABC` },
        { domain: `[("state", "=", expr)]`, text: `State = expr` },
        { domain: `[("state", "!=", "abc")]`, text: `State not = ABC` },
        { domain: `[("state", "in", ["abc", "def"])]`, text: `State = ABC or DEF` },
        { domain: `[("state", "in", ["abc", False])]`, text: `State = "ABC" or false` },
        {
            domain: `[("state", "not in", ["abc", "def"])]`,
            text: `State not = ABC or DEF`,
        },
        {
            domain: `[("state", "not in", ["abc", expr])]`,
            text: `State not = "ABC" or expr`,
        },
    ];
    for (const { domain, text } of toTest) {
        await parent.set(domain);
        expect(getConditionText()).toBe(text);
    }
});

test("selection property (readonly)", async () => {
    Partner._fields.properties = fields.Properties({
        string: "Properties",
        definition_record: "product_id",
        definition_record_field: "definitions",
    });
    Product._fields.definitions = fields.PropertiesDefinition({
        string: "Definitions",
    });
    Product._records[0].definitions = [
        {
            name: "selection_prop",
            string: "Selection",
            type: "selection",
            selection: [
                ["abc", "ABC"],
                ["def", "DEF"],
            ],
        },
    ];
    const parent = await makeDomainSelector({
        readonly: true,
    });
    const toTest = [
        {
            domain: `[("properties.selection_prop", "=", false)]`,
            text: `Properties ➔ Selection not set`,
        },
        {
            domain: `[("properties.selection_prop", "!=", false)]`,
            text: `Properties ➔ Selection set`,
        },
        {
            domain: `[("properties.selection_prop", "=", "abc")]`,
            text: `Properties ➔ Selection = ABC`,
        },
        {
            domain: `[("properties.selection_prop", "=", expr)]`,
            text: `Properties ➔ Selection = expr`,
        },
        {
            domain: `[("properties.selection_prop", "!=", "abc")]`,
            text: `Properties ➔ Selection not = ABC`,
        },
    ];
    for (const { domain, text } of toTest) {
        await parent.set(domain);
        expect(getConditionText()).toBe(text);
    }
});

test("many2one field (readonly)", async () => {
    const toTest = [
        {
            domain: `[("product_id", "=", 37)]`,
            text: "Product = xphone",
        },
        {
            domain: `[("product_id", "=", 2)]`,
            text: "Product = Inaccessible/missing record ID: 2",
        },
        {
            domain: `[("product_id", "!=", 37)]`,
            text: "Product not = xphone",
        },
        {
            domain: `[("product_id", "=", false)]`,
            text: "Product not set",
        },
        {
            domain: `[("product_id", "!=", false)]`,
            text: "Product set",
        },
        {
            domain: `[("product_id", "in", [])]`,
            text: "Product not set",
        },
        {
            domain: `[("product_id", "in", [41, 37])]`,
            text: "Product = xpad or xphone",
        },
        {
            domain: `[("product_id", "in", [1, 37])]`,
            text: "Product = Inaccessible/missing record ID: 1 or xphone",
        },
        {
            domain: `[("product_id", "in", [1, uid, 37])]`,
            text: 'Product = Inaccessible/missing record ID: 1 or uid or "xphone"',
        },
        {
            domain: `[("product_id", "in", ["abc"])]`,
            text: "Product = abc",
        },
        {
            domain: `[("product_id", "in", 37)]`,
            text: "Product = xphone",
        },
        {
            domain: `[("product_id", "in", 2)]`,
            text: "Product = Inaccessible/missing record ID: 2",
        },
    ];
    const parent = await makeDomainSelector({ readonly: true });
    for (const { domain, text } of toTest) {
        await parent.set(domain);
        expect(getConditionText()).toBe(text);
    }
});

test("many2one field operators (edit)", async () => {
    await makeDomainSelector({
        domain: `[("product_id", "=", false)]`,
    });
    expect(getOperatorOptions()).toEqual([
        "is in",
        "is not in",
        "equals",
        "not equals",
        "contains",
        "not contains",
        "set",
        "not set",
        "starts with",
        "ends with",
    ]);
});

test("many2one field: operator switch (edit)", async () => {
    await makeDomainSelector({
        domain: `[("product_id", "=", False)]`,
        update(domain) {
            expect.step(domain);
        },
    });
    await selectOperator("in");
    expect(queryAllTexts(SELECTORS.tag)).toEqual([]);
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([`[("product_id", "in", [])]`]);

    await selectOperator("=");
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([`[("product_id", "=", False)]`]);

    await selectOperator("not in");
    expect(queryAllTexts(SELECTORS.tag)).toEqual([]);
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([`[("product_id", "not in", [])]`]);

    await selectOperator("ilike");
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([`[("product_id", "ilike", "")]`]);

    await selectOperator("!=");
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([`[("product_id", "!=", False)]`]);

    await selectOperator("not ilike");
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([`[("product_id", "not ilike", "")]`]);
});

test("many2one field and operator =/!= (edit)", async () => {
    await makeDomainSelector({
        domain: `[("product_id", "=", False)]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([]);
    expect(".dropdown-menu").toHaveCount(0);

    await editValue("xph", { confirm: false });
    await runAllTimers();
    expect(".dropdown-menu").toHaveCount(1);
    expect(queryAllTexts(".dropdown-menu li")).toEqual(["xphone"]);
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("xph");

    await contains(".dropdown-menu li").click();
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("xphone");
    expect.verifySteps([`[("product_id", "=", 37)]`]);
    expect(".dropdown-menu").toHaveCount(0);

    await editValue("", { confirm: false });
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("");
    await contains(".o_domain_selector").click();
    expect.verifySteps([`[("product_id", "=", False)]`]);

    await selectOperator("!=");
    expect(getCurrentOperator()).toBe("not equals");
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([`[("product_id", "!=", False)]`]);

    await editValue("xpa", { confirm: false });
    await runAllTimers();
    await contains(".dropdown-menu li").click();
    expect(getCurrentOperator()).toBe("not equals");
    expect(getCurrentValue()).toBe("xpad");
    expect.verifySteps([`[("product_id", "!=", 41)]`]);
});

test("many2one field on record with falsy display_name", async () => {
    Product._records[0].name = false;
    await makeDomainSelector({
        domain: `[("product_id", "=", False)]`,
    });
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("");
    expect(".dropdown-menu").toHaveCount(0);

    await contains(".o-autocomplete--input").click();

    expect("a.dropdown-item:first").toHaveText("Unnamed", {
        message: "should have a Unnamed as fallback of many2one display_name",
    });
});

test("many2one field and operator in/not in (edit)", async () => {
    await makeDomainSelector({
        domain: `[("product_id", "in", [37])]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("is in");
    expect(getCurrentValue()).toBe("xphone");
    expect.verifySteps([]);
    expect(".dropdown-menu").toHaveCount(0);
    await contains(SELECTORS.valueEditor + " input").fill("x", { confirm: false });
    await runAllTimers();
    expect(".dropdown-menu").toHaveCount(1);
    expect(queryAllTexts(".dropdown-menu li")).toEqual(["xpad"]);

    await contains(".dropdown-menu li").click();
    expect.verifySteps([`[("product_id", "in", [37, 41])]`]);
    expect(getCurrentValue()).toBe("xphone xpad");

    await selectOperator("not in");
    expect(getCurrentOperator()).toBe("is not in");
    expect(getCurrentValue()).toBe("xphone xpad");
    expect.verifySteps([`[("product_id", "not in", [37, 41])]`]);

    await contains(".o_tag .o_delete").click();
    expect(getCurrentOperator()).toBe("is not in");
    expect(getCurrentValue()).toBe("xpad");
    expect.verifySteps([`[("product_id", "not in", [41])]`]);
});

test("many2one field and operator ilike/not ilike (edit)", async () => {
    await makeDomainSelector({
        domain: `[("product_id", "ilike", "abc")]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("contains");
    expect(".o-autocomplete--input").toHaveCount(0);
    expect(`${SELECTORS.valueEditor} .o_input`).toHaveCount(1);
    expect(getCurrentValue()).toBe("abc");
    expect.verifySteps([]);

    await contains(`${SELECTORS.valueEditor} .o_input`).edit("def");
    expect(getCurrentOperator()).toBe("contains");
    expect(`${SELECTORS.valueEditor} .o_input`).toHaveCount(1);
    expect(getCurrentValue()).toBe("def");
    expect.verifySteps([`[("product_id", "ilike", "def")]`]);

    await selectOperator("not ilike");
    expect(getCurrentOperator()).toBe("not contains");
    expect(`${SELECTORS.valueEditor} .o_input`).toHaveCount(1);
    expect(getCurrentValue()).toBe("def");
    expect.verifySteps([`[("product_id", "not ilike", "def")]`]);
});

test("many2many field and operator set/not set (edit)", async () => {
    await makeDomainSelector({
        domain: `[("product_id", "=", False)]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([]);

    await selectOperator("not_set");

    expect(getCurrentOperator()).toBe("not set");
    expect(".o_ds_value_cell").toHaveCount(0);
    expect.verifySteps([`[("product_id", "=", False)]`]);

    await selectOperator("set");
    expect(getCurrentOperator()).toBe("set");
    expect(".o_ds_value_cell").toHaveCount(0);
    expect.verifySteps([`[("product_id", "!=", False)]`]);

    await selectOperator("!=");
    expect(getCurrentOperator()).toBe("not equals");
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([`[("product_id", "!=", False)]`]);
});

test("many2many field: clone a set/not set condition", async () => {
    await makeDomainSelector({
        domain: `[("product_id", "=", False)]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([]);

    await selectOperator("not_set");
    expect(getCurrentOperator()).toBe("not set");
    expect(".o_ds_value_cell").toHaveCount(0);
    expect.verifySteps([`[("product_id", "=", False)]`]);
    expect(SELECTORS.condition).toHaveCount(1);

    await addNewRule();
    expect(SELECTORS.condition).toHaveCount(2);
    expect(getCurrentOperator()).toBe("not set");
    expect(getCurrentOperator(1)).toBe("not set");
    expect.verifySteps([`["&", ("product_id", "=", False), ("product_id", "=", False)]`]);
});

test("x2many field operators (edit)", async () => {
    addProductIds();
    await makeDomainSelector({
        domain: `[("product_ids", "=", false)]`,
    });
    expect(getOperatorOptions()).toEqual([
        "is in",
        "is not in",
        "equals",
        "not equals",
        "contains",
        "not contains",
        "set",
        "not set",
        "starts with",
        "ends with",
    ]);
});

test("x2many field: operator switch (edit)", async () => {
    addProductIds();
    await makeDomainSelector({
        domain: `[("product_ids", "=", false)]`,
        update(domain) {
            expect.step(domain);
        },
    });
    await selectOperator("in");
    expect(queryAllTexts(SELECTORS.tag)).toEqual([]);
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([`[("product_ids", "in", [])]`]);

    await selectOperator("=");
    expect(queryAllTexts(SELECTORS.tag)).toEqual([]);
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([`[("product_ids", "=", [])]`]);

    await selectOperator("not in");
    expect(queryAllTexts(SELECTORS.tag)).toEqual([]);
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([`[("product_ids", "not in", [])]`]);

    await selectOperator("ilike");
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([`[("product_ids", "ilike", "")]`]);

    await selectOperator("not_set");
    expect(".o_ds_value_cell").toHaveCount(0);
    expect.verifySteps([`[("product_ids", "=", False)]`]);

    await selectOperator("!=");
    expect(queryAllTexts(SELECTORS.tag)).toEqual([]);
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([`[("product_ids", "!=", [])]`]);

    await selectOperator("not ilike");
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([`[("product_ids", "not ilike", "")]`]);

    await selectOperator("set");
    expect(".o_ds_value_cell").toHaveCount(0);
    expect.verifySteps([`[("product_ids", "!=", False)]`]);
});

test("many2many field: operator =/!=/in/not in (edit)", async () => {
    addProductIds();
    await makeDomainSelector({
        domain: `[("product_ids", "in", [37])]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("is in");
    expect(getCurrentValue()).toBe("xphone");
    expect.verifySteps([]);
    expect(".dropdown-menu").toHaveCount(0);

    await contains(SELECTORS.valueEditor + " input").fill("x", { confirm: false });
    await runAllTimers();
    expect(".dropdown-menu").toHaveCount(1);
    expect(queryAllTexts(".dropdown-menu li")).toEqual(["xpad"]);

    await contains(".dropdown-menu li").click();
    expect.verifySteps([`[("product_ids", "in", [37, 41])]`]);
    expect(getCurrentValue()).toBe("xphone xpad");

    await selectOperator("not in");
    expect(getCurrentOperator()).toBe("is not in");
    expect(getCurrentValue()).toBe("xphone xpad");
    expect.verifySteps([`[("product_ids", "not in", [37, 41])]`]);

    await contains(".o_tag .o_delete").click();
    expect(getCurrentOperator()).toBe("is not in");
    expect(getCurrentValue()).toBe("xpad");
    expect.verifySteps([`[("product_ids", "not in", [41])]`]);

    await selectOperator("=");
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("xpad");
    expect.verifySteps([`[("product_ids", "=", [41])]`]);

    await selectOperator("!=");
    expect(getCurrentOperator()).toBe("not equals");
    expect(getCurrentValue()).toBe("xpad");
    expect.verifySteps([`[("product_ids", "!=", [41])]`]);
});

test("many2many field: operator ilike/not ilike (edit)", async () => {
    addProductIds();
    await makeDomainSelector({
        domain: `[("product_ids", "ilike", "abc")]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("contains");
    expect(".o-autocomplete--input").toHaveCount(0);
    expect(`${SELECTORS.valueEditor} .o_input`).toHaveCount(1);
    expect(getCurrentValue()).toBe("abc");
    expect.verifySteps([]);

    await contains(`${SELECTORS.valueEditor} .o_input`).edit("def");
    expect(getCurrentOperator()).toBe("contains");
    expect(`${SELECTORS.valueEditor} .o_input`).toHaveCount(1);
    expect(getCurrentValue()).toBe("def");
    expect.verifySteps([`[("product_ids", "ilike", "def")]`]);

    await selectOperator("not ilike");
    expect(getCurrentOperator()).toBe("not contains");
    expect(`${SELECTORS.valueEditor} .o_input`).toHaveCount(1);
    expect(getCurrentValue()).toBe("def");
    expect.verifySteps([`[("product_ids", "not ilike", "def")]`]);
});

test("many2many field: operator set/not set (edit)", async () => {
    addProductIds();
    await makeDomainSelector({
        domain: `[("product_ids", "=", False)]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("not set");
    expect(".o_ds_value_cell").toHaveCount(0);
    expect.verifySteps([]);

    await selectOperator("set");
    expect(getCurrentOperator()).toBe("set");
    expect(".o_ds_value_cell").toHaveCount(0);
    expect.verifySteps([`[("product_ids", "!=", False)]`]);
});

test("Include archived button basic use", async () => {
    Partner._fields.active = fields.Boolean();
    await makeDomainSelector({
        isDebugMode: true,
        domain: `["&", ("foo", "=", "test"), ("bar", "=", True)]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(SELECTORS.condition).toHaveCount(2);
    expect('.form-switch label:contains("Include archived")').toHaveCount(1);

    await toggleArchive();
    expect(SELECTORS.condition).toHaveCount(2);
    expect.verifySteps([
        '["&", "&", ("foo", "=", "test"), ("bar", "=", True), ("active", "in", [True, False])]',
    ]);

    await toggleConnector();
    expect(SELECTORS.condition).toHaveCount(2);
    expect.verifySteps([
        '["&", "|", ("foo", "=", "test"), ("bar", "=", True), ("active", "in", [True, False])]',
    ]);

    await toggleArchive();
    expect(SELECTORS.condition).toHaveCount(2);
    expect.verifySteps(['["|", ("foo", "=", "test"), ("bar", "=", True)]']);
});

test("Include archived on empty tree", async () => {
    Partner._fields.active = fields.Boolean();
    await makeDomainSelector({
        isDebugMode: true,
        domain: `[("foo", "=", "test")]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(SELECTORS.condition).toHaveCount(1);
    expect('.form-switch label:contains("Include archived")').toHaveCount(1);

    await toggleArchive();
    expect(SELECTORS.condition).toHaveCount(1);
    expect.verifySteps(['["&", ("foo", "=", "test"), ("active", "in", [True, False])]']);

    await clickOnButtonDeleteNode();
    expect(SELECTORS.condition).toHaveCount(0);
    expect.verifySteps(['[("active", "in", [True, False])]']);

    await toggleArchive();
    expect.verifySteps(["[]"]);

    await toggleArchive();
    expect(SELECTORS.condition).toHaveCount(0);
    expect.verifySteps(['[("active", "in", [True, False])]']);

    await addNewRule();
    expect(SELECTORS.condition).toHaveCount(1);
    expect.verifySteps(['["&", ("id", "=", 1), ("active", "in", [True, False])]']);
});

test("Include archived not shown when model doesn't have the active field", async () => {
    await makeDomainSelector({
        isDebugMode: true,
        domain: `[("foo", "=", "test")]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(SELECTORS.condition).toHaveCount(1);
    expect('.form-switch label:contains("Include archived")').toHaveCount(0);
});

test("date/datetime edition: switch !=/set", async () => {
    mockDate("2023-04-20 17:00:00", 0);
    await makeDomainSelector({
        isDebugMode: true,
        domain: `[("date", "!=", "2023-05-20")]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("not equals");
    expect(".o_datetime_input").toHaveCount(1);
    expect(getCurrentValue()).toBe("05/20/2023");

    await selectOperator("set");
    expect(getCurrentOperator()).toBe("set");
    expect(".o_datetime_input").toHaveCount(0);
    expect.verifySteps([`[("date", "!=", False)]`]);

    await selectOperator("!=");
    expect(getCurrentOperator()).toBe("not equals");
    expect(".o_datetime_input").toHaveCount(1);
    expect(getCurrentValue()).toBe("04/20/2023");
    expect.verifySteps([`[("date", "!=", "2023-04-20")]`]);
});

test("date/datetime edition: switch is_set to other operators", async () => {
    mockDate("2023-04-20 17:00:00", 0);
    await makeDomainSelector({
        isDebugMode: true,
        domain: `[("datetime", "!=", "2023-05-20")]`,
        update(domain) {
            expect.step(domain);
        },
    });
    await selectOperator("set");
    expect(".o_datetime_input").toHaveCount(0);
    expect(getCurrentValue()).toBe(null);
    expect(getCurrentOperator()).toBe("set");
    expect.verifySteps(['[("datetime", "!=", False)]']);

    await selectOperator("between");
    expect(SELECTORS.condition).toHaveCount(1);
    expect(getCurrentOperator()).toBe("between");
    expect(SELECTORS.valueEditor).toHaveCount(1);
    expect(SELECTORS.valueEditor + " " + SELECTORS.editor).toHaveCount(2);
    expect(SELECTORS.clearNotSupported).toHaveCount(0);
    expect(`${SELECTORS.editor} .o_datetime_input`).toHaveCount(2);
    expect.verifySteps([
        '["&", ("datetime", ">=", "2023-04-20 00:00:00"), ("datetime", "<=", "2023-04-20 23:59:59")]',
    ]);

    await selectOperator("not_set");
    expect(".o_datetime_input").toHaveCount(0);
    expect(getCurrentValue()).toBe(null);
    expect(getCurrentOperator()).toBe("not set");
    expect.verifySteps(['[("datetime", "=", False)]']);

    await selectOperator(">");
    expect(".o_datetime_input").toHaveCount(1);
    expect(getCurrentValue()).toBe("04/20/2023 00:00");
    expect(getCurrentOperator()).toBe("greater");
    expect.verifySteps(['[("datetime", ">", "2023-04-20 00:00:00")]']);
});

test("render false and true leaves", async () => {
    await makeDomainSelector({ domain: `[(0, "=", 1), (1, "=", 1)]` });
    expect(getOperatorOptions()).toEqual(["equals"]);
    expect(getValueOptions()).toEqual(["1"]);
    expect(getOperatorOptions(-1)).toEqual(["equals"]);
    expect(getValueOptions(-1)).toEqual(["1"]);
});

test("datetime domain in readonly mode (check localization)", async () => {
    defineParams({
        lang_parameters: {
            date_format: "%m.%d.%Y",
        },
    });
    mockTimeZone(+2);
    await makeDomainSelector({
        domain: `["&", ("datetime", ">=", "2023-11-03 11:41:23"), ("datetime", "<=", "2023-11-13 09:45:11")]`,
        readonly: true,
    });
    expect(".o_tree_editor_condition").toHaveText(
        `Datetime\nbetween\n11.03.2023 13:41:23\nand\n11.13.2023 11:45:11`
    );
});

test("date domain in readonly mode (check localization)", async () => {
    defineParams({
        lang_parameters: {
            date_format: "%d|%m|%Y",
        },
    });
    mockTimeZone(+2);
    await makeDomainSelector({
        domain: `["&", ("date", ">=", "2023-11-03"), ("date", "<=", "2023-11-13")]`,
        readonly: true,
    });
    expect(".o_tree_editor_condition").toHaveText("Date\nbetween\n03|11|2023\nand\n13|11|2023");
});

test(`any/not any operator in editable mode`, async () => {
    await makeDomainSelector({
        readonly: false,
        isDebugMode: true,
        domain: `[("product_id", "any", ["|", ("team_id", "any", [("name", "=", "Mancester City")]), ("team_id.name", "not in", ["Leicester", "Liverpool"])])]`,
    });
    expect(".o_tree_editor").toHaveCount(3);
    expect(".o_tree_editor_row").toHaveCount(10);
    expect(getCurrentPath(1)).toBe("Product Team");
    expect(getCurrentPath(3)).toBe("Product Team > Team Name");
    expect(getCurrentValue(1)).toBe("Leicester Liverpool");
    expect(getCurrentOperator(1)).toBe("matches");
    expect(getCurrentOperator(3)).toBe("is not in");
    await selectOperator("in", 3);
    expect(getCurrentOperator(3)).toBe("is in");
    expect(SELECTORS.debugArea).toHaveValue(
        `[("product_id", "any", ["|", ("team_id", "any", [("name", "=", "Mancester City")]), ("team_id.name", "in", ["Leicester", "Liverpool"])])]`
    );
});

test(`any/not any operator in editable mode (add a rule in empty sub domain)`, async () => {
    await makeDomainSelector({
        readonly: false,
        isDebugMode: true,
        domain: `[("product_id", "any", [])]`,
    });
    await addNewRule();
    expect(getCurrentPath()).toBe("Product");
    expect(getCurrentOperator()).toBe("matches");
    expect(getCurrentPath(1)).toBe("Id");
    expect(getCurrentOperator(1)).toBe("equals");
    expect(SELECTORS.debugArea).toHaveValue(`[("product_id", "any", [("id", "=", 1)])]`);
});

test(`any/not any operator (readonly) with custom domain as value`, async () => {
    const toTest = [
        {
            domain: `[("product_id", "any", [("machin", "in", ["chose", "truc"] )] )]`,
            text: `Match\nall\nof the following rules:\nProduct\n:\nall\nof:\nmachin\n=\nchose\nor\ntruc`,
        },
    ];
    const parent = await makeDomainSelector({ readonly: true });
    for (const { domain, text } of toTest) {
        await parent.set(domain);
        expect(".o_domain_selector").toHaveText(text);
    }
});

test(`any/not any operator (readonly) with invalid domain as value`, async () => {
    const toTest = [
        {
            domain: `[("product_id", "any", A )]`,
            text: `Match\nall\nof the following rules:\nProduct\n:\n(\nA\n)`,
        },
        {
            domain: `[("product_id", "any", "bete et méchant" )]`,
            text: `Match\nall\nof the following rules:\nProduct\n:\n(\nbete et méchant\n)`,
        },
        {
            domain: `[("product_id", "any", [("team_id", "any", "bête et méchant")])]`,
            text: `Match\nall\nof the following rules:\nProduct\n:\nall\nof:\nProduct Team\n:\n(\nbête et méchant\n)`,
        },
        {
            domain: `[("product_id", "any", ["&"])]`,
            text: `Match\nall\nof the following rules:\nProduct\n:\n(\n&\n)`,
        },
    ];
    const parent = await makeDomainSelector({ readonly: true });
    for (const { domain, text } of toTest) {
        await parent.set(domain);
        expect(".o_domain_selector").toHaveText(text);
    }
});

test(`any operator (edit) with invalid domain as value`, async () => {
    await makeDomainSelector({ domain: `[("product_id", "any", ["&"])]` });
    expect(SELECTORS.valueEditor).toHaveCount(1);
    expect(SELECTORS.clearNotSupported).toHaveCount(1);
    await contains(SELECTORS.clearNotSupported).click();
    expect(`${SELECTORS.connector}:eq(1)`).toHaveText("all records");
});

test(`any operator (edit) test getDefaultPath`, async () => {
    Partner._fields.country_id = fields.Many2one({
        string: "Country",
        relation: "country",
        searchable: true,
    });
    await makeDomainSelector({
        resModel: "partner",
        domain: `[("country_id", "any", [])]`,
    });
    await addNewRule();
    expect(getCurrentPath(0)).toBe("Country");
    expect(getCurrentPath(1)).toBe("Stage");
});

test(`any operator (edit) test defaultValue => defaultCondition`, async () => {
    Product._fields.country_id = fields.Many2one({
        string: "Country",
        relation: "country",
        searchable: true,
    });
    await makeDomainSelector({
        domain: `[("product_id", "any", [(A, "=", 1)])]`,
        isDebugMode: true,
    });
    await clearNotSupported();
    expect(getCurrentPath(1)).toBe("Country");
});

test(`any operator with include archived`, async () => {
    Partner._fields.active = fields.Boolean({
        string: "Active",
        searchable: true,
    });
    await makeDomainSelector({
        readonly: false,
        isDebugMode: true,
        domain: `[("product_id", "any", [("name", "=", "Mancester City")])]`,
    });
    expect(SELECTORS.condition).toHaveCount(2);
    expect('.form-switch label:contains("Include archived")').toHaveCount(1, {
        message: "Sub TreeEditor shouldn't add another checkbox",
    });
});

test(`any/not any operator (readonly)`, async () => {
    const toTest = [
        {
            domain: `[("product_id", "any", [("name", "in", [37,41] )] )]`,
            text: `Match\nall\nof the following rules:\nProduct\n:\nall\nof:\nProduct Name\n=\n37\nor\n41`,
        },
        {
            domain: `[("product_id", "not any", [("name", "in", [37,41] )] )]`,
            text: `Match\nall\nof the following rules:\nProduct\n: not\nall\nof:\nProduct Name\n=\n37\nor\n41`,
        },
        {
            domain: `[("product_id", "not any", ["|", ("team_id", "any", [("name", "ilike", "mancity")] ), ("name", "in", [37,41] )] )]`,
            text: `Match\nall\nof the following rules:\nProduct\n: not\nany\nof:\nProduct Team\n:\nall\nof:\nTeam Name\ncontains\nmancity\nProduct Name\n=\n37\nor\n41`,
        },
        {
            domain: `[("product_id", "any", ["|", ("name", "in", [37,41] ), ("bar", "=", True)] )]`,
            text: `Match\nall\nof the following rules:\nProduct\n:\nany\nof:\nProduct Name\n=\n37\nor\n41\nProduct Bar\nset`,
        },
        {
            domain: `[("product_id", "any", ["&", ("name", "in", ["JD7", "KDB"]), ("team_id", "not any", ["&", ("id", "=", 17), ("name", "ilike", "mancity")])])]`,
            text: `Match\nall\nof the following rules:\nProduct\n:\nall\nof:\nProduct Name\n=\nJD7\nor\nKDB\nProduct Team\n: not\nall\nof:\nId\n=\n17\nTeam Name\ncontains\nmancity`,
        },
        {
            domain: `[("product_id", "any", ["|", ("name", "in", ["JD7", "KDB"]), ("team_id", "not any", ["|", ("id", "=", 17), ("name", "ilike", "mancity")])])]`,
            text: `Match\nall\nof the following rules:\nProduct\n:\nany\nof:\nProduct Name\n=\nJD7\nor\nKDB\nProduct Team\n: not\nany\nof:\nId\n=\n17\nTeam Name\ncontains\nmancity`,
        },
    ];
    const parent = await makeDomainSelector({ readonly: true });
    for (const { domain, text } of toTest) {
        await parent.set(domain);
        expect(".o_domain_selector").toHaveText(text);
    }
});

test(`any/not any operator (readonly) for one2many`, async () => {
    await makeDomainSelector({
        resModel: "team",
        domain: `[("player_ids", "any", [('name', 'in', ["Kevin De Bruyne", "Jeremy Doku"])])]`,
        readonly: true,
    });
    const text = `Match\nall\nof the following rules:\nPlayers\n:\nall\nof:\nPlayer Name\n=\nKevin De Bruyne\nor\nJeremy Doku`;
    expect(".o_domain_selector").toHaveText(text);
});

test(`next operator (readonly) for date`, async () => {
    await makeDomainSelector({
        resModel: "partner",
        domain: `["&", ("date", ">=", context_today().strftime("%Y-%m-%d")), ("date", "<=", (context_today() + relativedelta(weeks = 1)).strftime("%Y-%m-%d"))]`,
        readonly: true,
    });
    const text = `Match\nall\nof the following rules:\nDate\nnext\n1\nweeks`;
    expect(".o_domain_selector").toHaveText(text);
});

test(`next operator (readonly) for datetime`, async () => {
    await makeDomainSelector({
        resModel: "partner",
        domain: `["&", ("datetime", ">=", datetime.datetime.combine(context_today(), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S")), ("datetime", "<=", datetime.datetime.combine(context_today() + relativedelta(weeks=1), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S"))]`,
        readonly: true,
    });
    const text = `Match\nall\nof the following rules:\nDatetime\nnext\n1\nweeks`;
    expect(".o_domain_selector").toHaveText(text);
});

test(`next operator (edit) for date`, async () => {
    await makeDomainSelector({
        resModel: "partner",
        domain: `["&", ("date", ">=", context_today().strftime("%Y-%m-%d")), ("date", "<=", (context_today() + relativedelta(weeks = 1)).strftime("%Y-%m-%d"))]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("next");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}`).toHaveCount(2);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:first input`).toHaveValue("1");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(2) select`).toHaveValue(
        `"weeks"`
    );
    await contains(`${SELECTORS.valueEditor} ${SELECTORS.editor}:first input`).edit("1%");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}`).toHaveCount(2);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(1) span`).toHaveText(`"1%"`);
    expect(
        `${SELECTORS.valueEditor} ${SELECTORS.editor} ${SELECTORS.clearNotSupported}`
    ).toHaveCount(1);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor} .fa-exclamation-triangle`).toHaveAttribute(
        "data-tooltip",
        "Positive integer expected"
    );
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(2) select`).toHaveValue(
        `"weeks"`
    );
    expect.verifySteps([
        `["&", ("date", ">=", context_today().strftime("%Y-%m-%d")), ("date", "<=", (context_today() + relativedelta(weeks = "1%")).strftime("%Y-%m-%d"))]`,
    ]);

    await contains(SELECTORS.clearNotSupported).click();
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}`).toHaveCount(2);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:first input`).toHaveValue("1");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(2) select`).toHaveValue(
        `"weeks"`
    );
    expect.verifySteps([
        `["&", ("date", ">=", context_today().strftime("%Y-%m-%d")), ("date", "<=", (context_today() + relativedelta(weeks = 1)).strftime("%Y-%m-%d"))]`,
    ]);
});

test(`next operator (edit) for date with an expression for amount`, async () => {
    await makeDomainSelector({
        resModel: "partner",
        domain: `["&", ("date", ">=", context_today().strftime("%Y-%m-%d")), ("date", "<=", (context_today() + relativedelta(weeks = 1)).strftime("%Y-%m-%d"))]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("next");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}`).toHaveCount(2);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:first input`).toHaveValue("1");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(2) select`).toHaveValue(
        `"weeks"`
    );

    await contains(`${SELECTORS.valueEditor} ${SELECTORS.editor}:first input`).edit("ab");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(1) span`).toHaveText(`"ab"`);
    expect(
        `${SELECTORS.valueEditor} ${SELECTORS.editor} ${SELECTORS.clearNotSupported}`
    ).toHaveCount(1);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(2) select`).toHaveValue(
        `"weeks"`
    );
    expect.verifySteps([
        `["&", ("date", ">=", context_today().strftime("%Y-%m-%d")), ("date", "<=", (context_today() + relativedelta(weeks = "ab")).strftime("%Y-%m-%d"))]`,
    ]);
});

test(`next operator (edit) for datetime with invalid period`, async () => {
    await makeDomainSelector({
        resModel: "partner",
        domain: `["&", ("datetime", ">=", datetime.datetime.combine(context_today(), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S")), ("datetime", "<=", datetime.datetime.combine(context_today() + relativedelta(a=1), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S"))]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("next");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}`).toHaveCount(2);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:first input`).toHaveValue("1");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(2) span`).toHaveText("a");
    expect(isNotSupportedValue(2)).toBe(true);

    await clearNotSupported();
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}`).toHaveCount(2);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:first input`).toHaveValue("1");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(2) select`).toHaveValue(
        `"days"`
    );
    expect.verifySteps([
        `["&", ("datetime", ">=", datetime.datetime.combine(context_today(), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S")), ("datetime", "<=", datetime.datetime.combine(context_today() + relativedelta(days = 1), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S"))]`,
    ]);
});

test(`last operator (readonly) for date`, async () => {
    await makeDomainSelector({
        resModel: "partner",
        domain: `["&", ("date", ">=", (context_today() + relativedelta(weeks = -1)).strftime("%Y-%m-%d")), ("date", "<=", context_today().strftime("%Y-%m-%d"))]`,
        readonly: true,
    });
    const text = `Match\nall\nof the following rules:\nDate\nlast\n1\nweeks`;
    expect(".o_domain_selector").toHaveText(text);
});

test(`last operator (readonly) for datetime`, async () => {
    await makeDomainSelector({
        resModel: "partner",
        domain: `["&", ("datetime", ">=", datetime.datetime.combine(context_today() + relativedelta(weeks = -1), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S")), ("datetime", "<=", datetime.datetime.combine(context_today(), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S"))]`,
        readonly: true,
    });
    const text = `Match\nall\nof the following rules:\nDatetime\nlast\n1\nweeks`;
    expect(".o_domain_selector").toHaveText(text);
});

test(`last operator (edit) for date`, async () => {
    await makeDomainSelector({
        resModel: "partner",
        domain: `["&", ("date", ">=", (context_today() + relativedelta(weeks = -1)).strftime("%Y-%m-%d")), ("date", "<=", context_today().strftime("%Y-%m-%d"))]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("last");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}`).toHaveCount(2);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:first input`).toHaveValue("1");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(2) select`).toHaveValue(
        `"weeks"`
    );
    await contains(`${SELECTORS.valueEditor} ${SELECTORS.editor}:first input`).edit("1%");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}`).toHaveCount(2);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(1) span`).toHaveText(`"1%"`);
    expect(
        `${SELECTORS.valueEditor} ${SELECTORS.editor} ${SELECTORS.clearNotSupported}`
    ).toHaveCount(1);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor} .fa-exclamation-triangle`).toHaveAttribute(
        "data-tooltip",
        "Positive integer expected"
    );
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(2) select`).toHaveValue(
        `"weeks"`
    );
    expect.verifySteps([
        `["&", ("date", ">=", (context_today() + relativedelta(weeks = "1%")).strftime("%Y-%m-%d")), ("date", "<=", context_today().strftime("%Y-%m-%d"))]`,
    ]);

    await contains(SELECTORS.clearNotSupported).click();
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}`).toHaveCount(2);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:first input`).toHaveValue("1");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(2) select`).toHaveValue(
        `"weeks"`
    );
    expect.verifySteps([
        `["&", ("date", ">=", (context_today() + relativedelta(weeks = -1)).strftime("%Y-%m-%d")), ("date", "<=", context_today().strftime("%Y-%m-%d"))]`,
    ]);
});

test(`last operator (edit) for date with an expression for amount`, async () => {
    await makeDomainSelector({
        resModel: "partner",
        domain: `["&", ("date", ">=", (context_today() + relativedelta(weeks = -1)).strftime("%Y-%m-%d")), ("date", "<=", context_today().strftime("%Y-%m-%d"))]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("last");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}`).toHaveCount(2);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:first input`).toHaveValue("1");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(2) select`).toHaveValue(
        `"weeks"`
    );

    await contains(`${SELECTORS.valueEditor} ${SELECTORS.editor}:first input`).edit("ab");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(1) span`).toHaveText(`"ab"`);
    expect(
        `${SELECTORS.valueEditor} ${SELECTORS.editor} ${SELECTORS.clearNotSupported}`
    ).toHaveCount(1);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(2) select`).toHaveValue(
        `"weeks"`
    );
    expect.verifySteps([
        `["&", ("date", ">=", (context_today() + relativedelta(weeks = "ab")).strftime("%Y-%m-%d")), ("date", "<=", context_today().strftime("%Y-%m-%d"))]`,
    ]);
});

test(`last operator (edit) for datetime with invalid period`, async () => {
    await makeDomainSelector({
        resModel: "partner",
        domain: `["&", ("datetime", ">=", datetime.datetime.combine(context_today() + relativedelta(a = -1), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S")), ("datetime", "<=", datetime.datetime.combine(context_today(), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S"))]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("last");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}`).toHaveCount(2);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:first input`).toHaveValue("1");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(2) span`).toHaveText("a");
    expect(isNotSupportedValue(2)).toBe(true);

    await clearNotSupported();
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}`).toHaveCount(2);
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:first input`).toHaveValue("1");
    expect(`${SELECTORS.valueEditor} ${SELECTORS.editor}:nth-child(2) select`).toHaveValue(
        `"days"`
    );
    expect.verifySteps([
        `["&", ("datetime", ">=", datetime.datetime.combine(context_today() + relativedelta(days = -1), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S")), ("datetime", "<=", datetime.datetime.combine(context_today(), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S"))]`,
    ]);
});

test("shorten descriptions of long lists", async () => {
    const values = new Array(500).fill(42525245);
    await makeDomainSelector({
        domain: `[("id", "in", [${values}])]`,
        readonly: true,
    });
    expect(".o_tree_editor_condition").toHaveText(
        `Id\n=\n${values.slice(0, 4).join("\nor\n")}\nor\n...`
    );
});

test("many2one: no domain in autocompletion", async () => {
    Partner._fields.product_id.domain = `[("display_name", "ilike", "xpa")]`;
    await makeDomainSelector({
        domain: `[("product_id", "=", False)]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([]);
    expect(".dropdown-menu").toHaveCount(0);

    await editValue("x", { confirm: false });
    await runAllTimers();

    expect(".dropdown-menu").toHaveCount(1);
    expect(queryAllTexts(".dropdown-menu li")).toEqual(["xphone", "xpad"]);
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("x");

    await contains(".dropdown-menu li").click();
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("xphone");
    expect.verifySteps([`[("product_id", "=", 37)]`]);
    expect(".dropdown-menu").toHaveCount(0);
});

test("many2many: domain in autocompletion", async () => {
    addProductIds();
    Partner._fields.product_ids.domain = `[("display_name", "ilike", "xpa")]`;
    await makeDomainSelector({
        domain: `[("product_ids", "=", [])]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("");
    expect.verifySteps([]);
    expect(".dropdown-menu").toHaveCount(0);

    await editValue("x", { confirm: false });
    await runAllTimers();

    expect(".dropdown-menu").toHaveCount(1);
    expect(queryAllTexts(".dropdown-menu li")).toEqual(["xpad"]);
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("x");

    await contains(".dropdown-menu li").click();
    expect(getCurrentOperator()).toBe("equals");
    expect(getCurrentValue()).toBe("xpad");
    expect.verifySteps([`[("product_ids", "=", [41])]`]);
    expect(".dropdown-menu").toHaveCount(0);
});

test("Any operator supported even if not proposed", async () => {
    await makeDomainSelector({
        isDebugMode: true,
        update(domain) {
            expect.step(domain);
        },
        domain: `[("product_id", "any", [])]`,
    });
    expect(getOperatorOptions()).toEqual([
        "is in",
        "is not in",
        "equals",
        "not equals",
        "contains",
        "not contains",
        "set",
        "not set",
        "starts with",
        "ends with",
        "matches",
    ]);
    await addNewRule();
    expect.verifySteps([`[("product_id", "any", [("id", "=", 1)])]`]);
});

test("Hierarchical operators", async () => {
    await makeDomainSelector({
        isDebugMode: true,
        update(domain) {
            expect.step(domain);
        },
    });
    await addNewRule();
    expect.verifySteps(['[("id", "=", 1)]']);
    await openModelFieldSelectorPopover();
    await contains(
        ".o_model_field_selector_popover .o_model_field_selector_popover_item_name:contains(Product)"
    ).click();
    expect.verifySteps(['[("product_id", "in", [])]']);
    expect(getOperatorOptions()).toEqual([
        "is in",
        "is not in",
        "equals",
        "not equals",
        "contains",
        "not contains",
        "set",
        "not set",
        "starts with",
        "ends with",
    ]);
    await contains(SELECTORS.debugArea).edit(`[("product_id", "parent_of", [])]`);
    expect.verifySteps(['[("product_id", "parent_of", [])]']);
    expect(getOperatorOptions()).toEqual([
        "is in",
        "is not in",
        "equals",
        "not equals",
        "contains",
        "not contains",
        "set",
        "not set",
        "starts with",
        "ends with",
        "parent of",
    ]);
    await editValue("x", { confirm: false });
    await runAllTimers();

    expect(".dropdown-menu").toHaveCount(1);
    expect(queryAllTexts(".dropdown-menu li")).toEqual(["xphone", "xpad"]);
    await contains(".dropdown-menu li").click();
    expect.verifySteps(['[("product_id", "parent_of", [37])]']);
    await editValue("x", { confirm: false });
    await runAllTimers();

    expect(".dropdown-menu").toHaveCount(1);
    expect(queryAllTexts(".dropdown-menu li")).toEqual(["xpad"]);
    await contains(".dropdown-menu li").click();
    expect.verifySteps(['[("product_id", "parent_of", [37, 41])]']);
});

test("preserve virtual operators in sub domains", async () => {
    Team._fields.active = fields.Boolean();
    await makeDomainSelector({
        domain: `[("product_id", "any", ["&", ("team_id", "any", ["&", ("active", "=", False), ("name", "=", False)]), ("id", "=", 1)])]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentOperator()).toBe("matches");
    expect(getCurrentOperator(1)).toBe("matches");
    expect(getCurrentOperator(2)).toBe("not set");
    expect(getCurrentOperator(3)).toBe("not set");
    expect(getCurrentOperator(4)).toBe("equals");

    await addNewRule(1);
    expect(getCurrentOperator(2)).toBe("not set");
    expect(getCurrentOperator(3)).toBe("not set");
    expect(getCurrentOperator(4)).toBe("equals");
    expect(getCurrentOperator(5)).toBe("equals");
    expect.verifySteps([
        `[("product_id", "any", ["&", "&", ("team_id", "any", ["&", ("active", "=", False), ("name", "=", False)]), ("id", "=", 1), ("id", "=", 1)])]`,
    ]);

    await clickOnButtonDeleteNode(5);
    expect(getCurrentOperator()).toBe("matches");
    expect(getCurrentOperator(1)).toBe("matches");
    expect(getCurrentOperator(2)).toBe("not set");
    expect(getCurrentOperator(3)).toBe("not set");
    expect.verifySteps([
        `[("product_id", "any", ["&", ("team_id", "any", ["&", ("active", "=", False), ("name", "=", False)]), ("id", "=", 1)])]`,
    ]);
});

test("don't show avatar for expressions", async () => {
    class Users extends models.Model {
        _name = "res.users";
        name = fields.Char();

        _records = [
            { id: 1, name: "Mitchell Admin" },
            { id: 2, name: "Marc Demo" },
        ];
    }
    defineModels([Users]);
    Partner._fields.user_id = fields.Many2one({ relation: "res.users" });
    await makeDomainSelector({
        isDebugMode: true,
        domain: `[("user_id", "in", [1, uid, 2])]`,
        resModel: "partner",
    });
    expect(".o_tag").toHaveCount(3);
    expect(".o_tag.o_avatar").toHaveCount(2);
    expect(".o_tag:not(.o_avatar)").toHaveText("uid");
    expect(".o_tag:not(.o_avatar) img").toHaveCount(0);
    await contains(SELECTORS.debugArea).edit(`[("user_id", "=", uid)]`);
    expect(".o_record_selector input").toHaveValue("uid");
    expect(".o_record_selector img").toHaveCount(0);
});

test("today operator for date field (mode readonly)", async () => {
    const parent = await makeDomainSelector({
        domain: `[("date", "=", context_today().strftime("%Y-%m-%d"))]`,
        readonly: true,
    });
    expect(getConditionText()).toBe(`Date today`);
    await parent.set(`[("date", "!=", context_today().strftime("%Y-%m-%d"))]`);
    expect(getConditionText()).toBe(`Date not today`);
});

test("today operator for date field", async () => {
    await makeDomainSelector({
        domain: `[("date", "=", False)]`,
        update(domain) {
            expect.step(domain);
        },
    });
    await selectOperator("not_today");
    expect.verifySteps([`[("date", "!=", context_today().strftime("%Y-%m-%d"))]`]);
    await selectOperator("today");
    expect.verifySteps([`[("date", "=", context_today().strftime("%Y-%m-%d"))]`]);
    await selectOperator("between");
    expect.verifySteps([`["&", ("date", ">=", "2019-03-11"), ("date", "<=", "2019-03-11")]`]);
});

test("today operator for datetime field", async () => {
    await makeDomainSelector({
        domain: `[("datetime", "=", False)]`,
        update(domain) {
            expect.step(domain);
        },
    });
    await selectOperator("not_today");
    expect.verifySteps([
        `["|", ("datetime", "<", datetime.datetime.combine(context_today(), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S")), ("datetime", ">", datetime.datetime.combine(context_today(), datetime.time(23, 59, 59)).to_utc().strftime("%Y-%m-%d %H:%M:%S"))]`,
    ]);
    await selectOperator("today");
    expect.verifySteps([
        `["&", ("datetime", ">=", datetime.datetime.combine(context_today(), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S")), ("datetime", "<=", datetime.datetime.combine(context_today(), datetime.time(23, 59, 59)).to_utc().strftime("%Y-%m-%d %H:%M:%S"))]`,
    ]);
    await selectOperator("between");
    expect.verifySteps([
        `["&", ("datetime", ">=", "2019-03-10 23:00:00"), ("datetime", "<=", "2019-03-11 22:59:59")]`,
    ]);
});

test("remove all conditions in a sub connector", async () => {
    await makeDomainSelector({
        domain: `["&", ("bar", "!=", False), "|", ("id", "=", 1), ("id", "=", False)]`,
        update(domain) {
            expect.step(domain);
        },
    });
    await clickOnButtonDeleteNode(3);
    expect.verifySteps([`["&", ("bar", "!=", False), ("id", "=", 1)]`]);
    await clickOnButtonDeleteNode(2);
    expect.verifySteps([`[("bar", "!=", False)]`]);
});

test("datetime options (readonly)", async () => {
    const parent = await makeDomainSelector({
        readonly: true,
        domain: `[]`,
    });
    const toTest = [
        {
            domain: `[
                ("datetime.year_number", "=", False),
                ("datetime.month_number", "=", False),
                ("datetime.day_of_month", "=", False),
            ]`,
            text: `Datetime ➔ Date not set`,
        },
        {
            domain: `[
                "|",
                "|",
                ("datetime.year_number", "!=", False),
                ("datetime.month_number", "!=", False),
                ("datetime.day_of_month", "!=", False),
            ]`,
            text: `Datetime ➔ Date set`,
        },
        {
            domain: `[
                ("datetime.year_number", "=", 2025),
                ("datetime.month_number", "=", 3),
                ("datetime.day_of_month", "=", 20),
            ]`,
            text: `Datetime ➔ Date = 03/20/2025`,
        },
        {
            domain: `[
                "|",
                "|",
                ("datetime.year_number", "!=", 2025),
                ("datetime.month_number", "!=", 3),
                ("datetime.day_of_month", "!=", 20),
            ]`,
            text: `Datetime ➔ Date not = 03/20/2025`,
        },
        {
            domain: `[
                ("datetime.year_number", "=", a),
                ("datetime.month_number", "=", 3),
                ("datetime.day_of_month", "=", 20),
            ]`,
            text: `Datetime ➔ Date ➔ Year = a`, // first line here
        },
        {
            domain: `[
                "&",
                    "|",
                        "|", "|",
                            ("datetime.year_number", ">", 2025),
                            "&",
                                ("datetime.year_number", "=", 2025),
                                ("datetime.month_number", ">", 3),
                            "&", "&",
                                ("datetime.year_number", "=", 2025),
                                ("datetime.month_number", "=", 3),
                                ("datetime.day_of_month", ">", 20),
                        "&", "&",
                            ("datetime.year_number", "=", 2025),
                            ("datetime.month_number", "=", 3),
                            ("datetime.day_of_month", "=", 20),
                    "|",
                        "|","|",
                            ("datetime.year_number", "<", 2026),
                            "&",
                                ("datetime.year_number", "=", 2026),
                                ("datetime.month_number", "<", 7),
                            "&", "&",
                                ("datetime.year_number", "=", 2026),
                                ("datetime.month_number", "=", 7),
                                ("datetime.day_of_month", "<", 15),
                        "&", "&",
                            ("datetime.year_number", "=", 2026),
                            ("datetime.month_number", "=", 7),
                            ("datetime.day_of_month", "=", 15)
            ]`,
            text: `Datetime ➔ Date between 03/20/2025 and 07/15/2026`,
        },
        {
            domain: `[
                ("datetime.hour_number", "=", False),
                ("datetime.minute_number", "=", False),
                ("datetime.second_number", "=", False),
            ]`,
            text: `Datetime ➔ Time not set`,
        },
        {
            domain: `[
                "|",
                "|",
                ("datetime.hour_number", "!=", False),
                ("datetime.minute_number", "!=", False),
                ("datetime.second_number", "!=", False),
            ]`,
            text: `Datetime ➔ Time set`,
        },
        {
            domain: `[
                ("datetime.hour_number", "=", 15),
                ("datetime.minute_number", "=", 4),
                ("datetime.second_number", "=", 3),
            ]`,
            text: `Datetime ➔ Time = 15:04:03`,
        },
        {
            domain: `[
                "|",
                "|",
                ("datetime.hour_number", "!=", 15),
                ("datetime.minute_number", "!=", 40),
                ("datetime.second_number", "!=", 30),
            ]`,
            text: `Datetime ➔ Time not = 15:40:30`,
        },
        {
            domain: `[
                "!",
                "|",
                "|",
                ("datetime.hour_number", "!=", 15),
                ("datetime.minute_number", "!=", 40),
                ("datetime.second_number", "!=", 30),
            ]`,
            text: `Datetime ➔ Time ➔ Hour not not = 15`, // first line here
        },
        {
            domain: `[
                "&",
                    "|",
                        "|", "|",
                            ("datetime.hour_number", ">", 15),
                            "&",
                                ("datetime.hour_number", "=", 15),
                                ("datetime.minute_number", ">", 40),
                            "&", "&",
                                ("datetime.hour_number", "=", 15),
                                ("datetime.minute_number", "=", 40),
                                ("datetime.second_number", ">", 30),
                        "&", "&",
                            ("datetime.hour_number", "=", 15),
                            ("datetime.minute_number", "=", 40),
                            ("datetime.second_number", "=", 30),
                    "|",
                        "|", "|",
                            ("datetime.hour_number", "<", 17),
                            "&",
                                ("datetime.hour_number", "=", 17),
                                ("datetime.minute_number", "<", 20),
                            "&", "&",
                                ("datetime.hour_number", "=", 17),
                                ("datetime.minute_number", "=", 20),
                                ("datetime.second_number", "<", 00),
                        "&", "&",
                                ("datetime.hour_number", "=", 17),
                                ("datetime.minute_number", "=", 20),
                                ("datetime.second_number", "=", 00)
            ]`,
            text: `Datetime ➔ Time between 15:40:30 and 17:20:00`,
        },
        {
            domain: `[
                ("datetime.hour_number", "=", a),
                ("datetime.minute_number", "=", 40),
                ("datetime.second_number", "=", 20),
            ]`,
            text: `Datetime ➔ Time ➔ Hour = a`, // first line here
        },
        {
            domain: `[("datetime.year_number", "=", False)]`,
            text: `Datetime ➔ Date ➔ Year not set`,
        },
        {
            domain: `[("datetime.year_number", "=", 2026)]`,
            text: `Datetime ➔ Date ➔ Year = 2026`,
        },
        {
            domain: `[("datetime.quarter_number", "=", False)]`,
            text: `Datetime ➔ Date ➔ Quarter not set`,
        },
        {
            domain: `[("datetime.quarter_number", "=", 1)]`,
            text: `Datetime ➔ Date ➔ Quarter = Quarter 1`,
        },
        {
            domain: `[("datetime.month_number", "=", False)]`,
            text: `Datetime ➔ Date ➔ Month not set`,
        },
        {
            domain: `[("datetime.month_number", "=", 3)]`,
            text: `Datetime ➔ Date ➔ Month = March`,
        },
        {
            domain: `[("datetime.iso_week_number", "=", False)]`,
            text: `Datetime ➔ Date ➔ Week number not set`,
        },
        {
            domain: `[("datetime.iso_week_number", "=", 3)]`,
            text: `Datetime ➔ Date ➔ Week number = 3`,
        },
        {
            domain: `[("datetime.day_of_year", "=", False)]`,
            text: `Datetime ➔ Date ➔ Day of year not set`,
        },
        {
            domain: `[("datetime.day_of_year", "=", 3)]`,
            text: `Datetime ➔ Date ➔ Day of year = 3`,
        },
        {
            domain: `[("datetime.day_of_month", "=", False)]`,
            text: `Datetime ➔ Date ➔ Day of month not set`,
        },
        {
            domain: `[("datetime.day_of_month", "=", 3)]`,
            text: `Datetime ➔ Date ➔ Day of month = 3`,
        },
        {
            domain: `[("datetime.day_of_week", "=", False)]`,
            text: `Datetime ➔ Date ➔ Weekday not set`,
        },
        {
            domain: `[("datetime.day_of_week", "=", 3)]`,
            text: `Datetime ➔ Date ➔ Weekday = Wednesday`,
        },
        {
            domain: `[("datetime.hour_number", "=", False)]`,
            text: `Datetime ➔ Time ➔ Hour not set`,
        },
        {
            domain: `[("datetime.hour_number", "=", 3)]`,
            text: `Datetime ➔ Time ➔ Hour = 3`,
        },
        {
            domain: `[("datetime.minute_number", "=", False)]`,
            text: `Datetime ➔ Time ➔ Minute not set`,
        },
        {
            domain: `[("datetime.minute_number", "=", 3)]`,
            text: `Datetime ➔ Time ➔ Minute = 3`,
        },
        {
            domain: `[("datetime.second_number", "=", False)]`,
            text: `Datetime ➔ Time ➔ Second not set`,
        },
        {
            domain: `[("datetime.second_number", "=", 3)]`,
            text: `Datetime ➔ Time ➔ Second = 3`,
        },
    ];
    for (const { domain, text } of toTest) {
        await parent.set(domain);
        expect(getConditionText()).toBe(text);
    }
});

test("datetime options (edit)", async () => {
    mockDate("2025-03-24 17:00:00");
    let expectStep = true;
    await makeDomainSelector({
        domain: `[]`,
        update(domain) {
            if (expectStep) {
                expect.step(domain);
            }
        },
    });
    await addNewRule();
    expect.verifySteps([formatDomain('[("id", "=", 1)]')]);
    await openModelFieldSelectorPopover();
    await contains(".o_model_field_selector_popover_item_name:contains('Datetime')").click();
    expect.verifySteps([
        formatDomain(
            `[
                "&",
                    ("datetime", ">=", datetime.datetime.combine(context_today(), datetime.time(0, 0, 0)).to_utc().strftime("%Y-%m-%d %H:%M:%S")),
                    ("datetime", "<=", datetime.datetime.combine(context_today(), datetime.time(23, 59, 59)).to_utc().strftime("%Y-%m-%d %H:%M:%S"))
            ]`
        ),
    ]);

    await openModelFieldSelectorPopover();
    await followRelation(2);
    await contains(".o_model_field_selector_popover_item_name:contains('Date')").click();
    expect.verifySteps([
        formatDomain(
            '["&", "&", ("datetime.year_number", "=", 2025), ("datetime.month_number", "=", 3), ("datetime.day_of_month", "=", 24)]'
        ),
    ]);

    await contains(".o_datetime_input").click();
    await contains(getPickerCell("26")).click();
    expect(getCurrentValue()).toBe("03/26/2025");
    expect.verifySteps([
        formatDomain(
            '["&", "&", ("datetime.year_number", "=", 2025), ("datetime.month_number", "=", 3), ("datetime.day_of_month", "=", 26)]'
        ),
    ]);

    expect(getOperatorOptions()).toEqual([
        "equals",
        "not equals",
        "greater",
        "lower",
        "between",
        "not between",
        "set",
        "not set",
    ]);

    await selectOperator("between");
    expect(SELECTORS.condition).toHaveCount(1);
    expect(getCurrentOperator()).toBe("between");
    expect(SELECTORS.valueEditor).toHaveCount(1);
    expect(SELECTORS.valueEditor + " " + SELECTORS.editor).toHaveCount(2);
    expect(SELECTORS.clearNotSupported).toHaveCount(0);
    expect(`${SELECTORS.editor} .o_datetime_input`).toHaveCount(2);
    expect.verifySteps([
        formatDomain(
            `[
                "&",
                    "|",
                        "|", "|",
                            ("datetime.year_number", ">", 2025),
                            "&", ("datetime.year_number", "=", 2025), ("datetime.month_number", ">", 3),
                            "&", "&", ("datetime.year_number", "=", 2025), ("datetime.month_number", "=", 3), ("datetime.day_of_month", ">", 24),
                        "&", "&", ("datetime.year_number", "=", 2025), ("datetime.month_number", "=", 3), ("datetime.day_of_month", "=", 24),
                    "|",
                        "|", "|",
                            ("datetime.year_number", "<", 2025),
                            "&", ("datetime.year_number", "=", 2025), ("datetime.month_number", "<", 3),
                            "&", "&", ("datetime.year_number", "=", 2025), ("datetime.month_number", "=", 3), ("datetime.day_of_month", "<", 24),
                            "&", "&", ("datetime.year_number", "=", 2025), ("datetime.month_number", "=", 3), ("datetime.day_of_month", "=", 24)]`
        ),
    ]);

    await openModelFieldSelectorPopover();
    await followRelation();
    await contains(".o_model_field_selector_popover_item_name:contains('Weekday')").click();
    expect.verifySteps([formatDomain(`[("datetime.day_of_week", "=", 1)]`)]);
    await selectValue(5);
    expect(getCurrentValue()).toBe("Friday");
    expect.verifySteps([formatDomain(`[("datetime.day_of_week", "=", 5)]`)]);

    expect(getOperatorOptions()).toEqual([
        "equals",
        "not equals",
        "greater",
        "lower",
        "between",
        "not between",
        "set",
        "not set",
    ]);

    await openModelFieldSelectorPopover();
    await clickPrev();
    expectStep = false; // we don't want to control minutes/seconds.
    await contains(".o_model_field_selector_popover_item_name:contains('Time')").click();
    expectStep = true;

    await editValue("12:15:00");
    expect(getCurrentValue()).toBe("12:15:00");
    expect.verifySteps([
        formatDomain(
            '["&", "&", ("datetime.hour_number", "=", 12), ("datetime.minute_number", "=", 15), ("datetime.second_number", "=", 0)]'
        ),
    ]);

    await openModelFieldSelectorPopover();
    await followRelation(1);
    expectStep = false;
    await contains(".o_model_field_selector_popover_item_name:contains('Hour')").click();
    expectStep = true;
    await editValue("15");
    expect.verifySteps([formatDomain('[("datetime.hour_number", "=", 15)]')]);

    expect(getOperatorOptions()).toEqual([
        "equals",
        "not equals",
        "greater",
        "lower",
        "between",
        "not between",
        "set",
        "not set",
    ]);
});

test("date options (readonly)", async () => {
    const parent = await makeDomainSelector({
        readonly: true,
        domain: `[]`,
    });
    const toTest = [
        {
            domain: `[
                ("date.year_number", "=", False),
                ("date.month_number", "=", False),
                ("date.day_of_month", "=", False),
            ]`,
            text: `Date ➔ Year not set`, // first line here
        },
        {
            domain: `[
                ("date.hour_number", "=", False),
                ("date.minute_number", "=", False),
                ("date.second_number", "=", False),
            ]`,
            text: `Date ➔ hour_number not set`, // first line here
        },
        {
            domain: `[("date.year_number", "=", False)]`,
            text: `Date ➔ Year not set`,
        },
        {
            domain: `[("date.year_number", "=", 2026)]`,
            text: `Date ➔ Year = 2026`,
        },
        {
            domain: `[("date.quarter_number", "=", False)]`,
            text: `Date ➔ Quarter not set`,
        },
        {
            domain: `[("date.quarter_number", "=", 1)]`,
            text: `Date ➔ Quarter = Quarter 1`,
        },
        {
            domain: `[("date.month_number", "=", False)]`,
            text: `Date ➔ Month not set`,
        },
        {
            domain: `[("date.month_number", "=", 3)]`,
            text: `Date ➔ Month = March`,
        },
        {
            domain: `[("date.iso_week_number", "=", False)]`,
            text: `Date ➔ Week number not set`,
        },
        {
            domain: `[("date.iso_week_number", "=", 3)]`,
            text: `Date ➔ Week number = 3`,
        },
        {
            domain: `[("date.day_of_year", "=", False)]`,
            text: `Date ➔ Day of year not set`,
        },
        {
            domain: `[("date.day_of_year", "=", 3)]`,
            text: `Date ➔ Day of year = 3`,
        },
        {
            domain: `[("date.day_of_month", "=", False)]`,
            text: `Date ➔ Day of month not set`,
        },
        {
            domain: `[("date.day_of_month", "=", 3)]`,
            text: `Date ➔ Day of month = 3`,
        },
        {
            domain: `[("date.day_of_week", "=", False)]`,
            text: `Date ➔ Weekday not set`,
        },
        {
            domain: `[("date.day_of_week", "=", 3)]`,
            text: `Date ➔ Weekday = Wednesday`,
        },
        {
            domain: `[("date.month_number", "=", context_today().month)]`,
            text: `Date ➔ Month = This month`,
        },
        {
            domain: `[("date.day_of_month", "=", context_today().day)]`,
            text: `Date ➔ Day of month = This day`,
        },
    ];
    for (const { domain, text } of toTest) {
        await parent.set(domain);
        expect(getConditionText()).toBe(text);
    }
});

test("date options (edit)", async () => {
    mockDate("2025-03-24 17:00:00");
    await makeDomainSelector({
        domain: `[]`,
        update(domain) {
            expect.step(domain);
        },
    });
    await addNewRule();
    expect.verifySteps(['[("id", "=", 1)]']);
    await openModelFieldSelectorPopover();
    await contains(".o_model_field_selector_popover_item_name:contains('Date')").click();
    expect.verifySteps(['[("date", "=", context_today().strftime("%Y-%m-%d"))]']);

    await openModelFieldSelectorPopover();
    await followRelation(1);
    await contains(".o_model_field_selector_popover_item_name:contains(/^Month$/)").click();

    expect(getOperatorOptions()).toEqual([
        "equals",
        "not equals",
        "greater",
        "lower",
        "between",
        "not between",
        "set",
        "not set",
    ]);
    expect.verifySteps([`[("date.month_number", "=", 3)]`]);
    expect(getCurrentValue()).toBe("March");

    await selectValue(5);
    expect(getCurrentValue()).toBe("May");
    expect.verifySteps([`[("date.month_number", "=", 5)]`]);
});

test("date options (edit): This day/This month", async () => {
    mockDate("2025-03-24 17:00:00");
    await makeDomainSelector({
        domain: `[("date.month_number", "=", 5)]`,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getCurrentValue()).toBe("May");
    await selectValue("context_today().month");
    expect(getCurrentValue()).toBe("This month");
    expect.verifySteps([`[("date.month_number", "=", context_today().month)]`]);
    await openModelFieldSelectorPopover();
    await contains(`.o_model_field_selector_popover_item[data-name='day_of_month'] button`).click();
    expect.verifySteps([`[("date.day_of_month", "=", 24)]`]);
    expect(getCurrentValue()).toBe("24");
    await selectValue("context_today().day");
    expect(getCurrentValue()).toBe("This day");
    expect.verifySteps([`[("date.day_of_month", "=", context_today().day)]`]);
});

test("hide today, next, last operators when allowExpressions = False", async () => {
    Team._fields.active = fields.Boolean();
    await makeDomainSelector({
        domain: `[("datetime", "=", False)]`,
        allowExpressions: false,
        update(domain) {
            expect.step(domain);
        },
    });
    expect(getOperatorOptions()).toEqual([
        "equals",
        "not equals",
        "greater",
        "lower",
        "between",
        "not between",
        "set",
        "not set",
    ]);
});

test(`hide "This day"/"This month" when allowExpressions = False`, async () => {
    await makeDomainSelector({
        domain: `[("datetime.day_of_month", "=", 1), ("datetime.month_number", "=", 1) ]`,
        allowExpressions: false,
        update(domain) {
            expect.step(domain);
        },
    });
    const range = [];
    for (let i = 1; i <= 31; i++) {
        range.push(String(i));
    }
    expect(getValueOptions()).toEqual(range);
    expect(getValueOptions(1)).toEqual([
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ]);
});

test("many2one: placeholders for in operator", async () => {
    await makeDomainSelector({
        domain: `[("product_id", "in", [])]`,
    });
    expect(`${SELECTORS.valueEditor} input`).toHaveAttribute(
        "placeholder",
        `Select one or several criteria`
    );
});

test("datetime: placeholders for in operator", async () => {
    await makeDomainSelector({
        domain: `[("datetime", "in", [])]`,
    });
    expect(`${SELECTORS.valueEditor} input`).toHaveAttribute(
        "placeholder",
        `Select one or several criteria`
    );
});

test("date: placeholders for in operator", async () => {
    await makeDomainSelector({
        domain: `[("date", "in", [])]`,
    });
    expect(`${SELECTORS.valueEditor} input`).toHaveAttribute(
        "placeholder",
        `Select one or several criteria`
    );
});

test("char: placeholders for in operator", async () => {
    await makeDomainSelector({
        domain: `[("display_name", "in", [])]`,
    });
    expect(`${SELECTORS.valueEditor} input`).toHaveAttribute(
        "placeholder",
        `Press "Enter" to add criterion`
    );
});

test("selection: placeholders for in operator", async () => {
    await makeDomainSelector({
        domain: `[("state", "in", [])]`,
    });
    expect(`${SELECTORS.valueEditor} select`).toHaveValue(`Select one or several criteria`);
});
