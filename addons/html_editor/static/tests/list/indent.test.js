import { describe, expect, test } from "@odoo/hoot";
import { setupEditor, testEditor } from "../_helpers/editor";
import { unformat } from "../_helpers/format";
import { splitBlock, keydownTab, undo, tripleClick } from "../_helpers/user_actions";
import { getContent } from "../_helpers/selection";

describe("Checklist", () => {
    test("should indent a checklist", async () => {
        await testEditor({
            contentBefore: unformat(`
                    <ul class="o_checklist">
                        <li class="o_checked">a[b]c</li>
                    </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                    <ul class="o_checklist">
                        <li class="oe-nested">
                            <ul class="o_checklist">
                                <li class="o_checked">a[b]c</li>
                            </ul>
                        </li>
                    </ul>`),
        });
        await testEditor({
            contentBefore: unformat(`
                    <ul class="o_checklist">
                        <li>a[b]c</li>
                    </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                    <ul class="o_checklist">
                        <li class="oe-nested">
                            <ul class="o_checklist">
                                <li>a[b]c</li>
                            </ul>
                        </li>
                    </ul>`),
        });
    });

    test('should indent a checklist and previous line become the "title"', async () => {
        await testEditor({
            contentBefore: unformat(`
                    <ul class="o_checklist">
                        <li class="o_checked">abc</li>
                        <li class="o_checked">d[e]f</li>
                    </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                    <ul class="o_checklist">
                        <li class="o_checked">
                            <p>abc</p>
                            <ul class="o_checklist">
                                <li class="o_checked">d[e]f</li>
                            </ul>
                        </li>
                    </ul>`),
        });
        await testEditor({
            contentBefore: unformat(`
                    <ul class="o_checklist">
                        <li class="o_checked">abc</li>
                        <li>d[e]f</li>
                    </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                    <ul class="o_checklist">
                        <li class="o_checked">
                            <p>abc</p>
                            <ul class="o_checklist">
                                <li>d[e]f</li>
                            </ul>
                        </li>
                    </ul>`),
        });
        await testEditor({
            contentBefore: unformat(`
                    <ul class="o_checklist">
                        <li>abc</li>
                        <li>d[e]f</li>
                    </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                    <ul class="o_checklist">
                        <li>
                            <p>abc</p>
                            <ul class="o_checklist">
                                <li>d[e]f</li>
                            </ul>
                        </li>
                    </ul>`),
        });
        await testEditor({
            contentBefore: unformat(`
                    <ul class="o_checklist">
                        <li>abc</li>
                        <li class="o_checked">d[e]f</li>
                    </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                    <ul class="o_checklist">
                        <li>
                            <p>abc</p>
                            <ul class="o_checklist">
                                <li class="o_checked">d[e]f</li>
                            </ul>
                        </li>
                    </ul>`),
        });
    });

    test("should indent a checklist and merge it with previous siblings", async () => {
        await testEditor({
            contentBefore: unformat(`
                    <ul class="o_checklist">
                        <li class="oe-nested">
                            <ul class="o_checklist">
                                <li class="o_checked">def</li>
                            </ul>
                        </li>
                        <li class="o_checked">g[h]i</li>
                    </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                    <ul class="o_checklist">
                        <li class="oe-nested">
                            <ul class="o_checklist">
                                <li class="o_checked">def</li>
                                <li class="o_checked">g[h]i</li>
                            </ul>
                        </li>
                    </ul>`),
        });

        await testEditor({
            contentBefore: unformat(`
                    <ul class="o_checklist">
                        <li><p>abc</p>
                            <ul class="o_checklist">
                                <li>def</li>
                            </ul>
                        </li>
                        <li class="o_checked">g[h]i</li>
                    </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                    <ul class="o_checklist">
                        <li><p>abc</p>
                            <ul class="o_checklist">
                                <li>def</li>
                                <li class="o_checked">g[h]i</li>
                            </ul>
                        </li>
                    </ul>`),
        });
        await testEditor({
            contentBefore: unformat(`
                    <ul class="o_checklist">
                        <li><p>abc</p>
                            <ul class="o_checklist">
                                <li class="o_checked">def</li>
                            </ul>
                        </li>
                        <li>g[h]i</li>
                    </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                    <ul class="o_checklist">
                        <li><p>abc</p>
                            <ul class="o_checklist">
                                <li class="o_checked">def</li>
                                <li>g[h]i</li>
                            </ul>
                        </li>
                    </ul>`),
        });
    });

    test("should indent a checklist and merge it with next siblings", async () => {
        await testEditor({
            contentBefore: unformat(`
                    <ul class="o_checklist">
                        <li class="o_checked">abc</li>
                        <li class="o_checked">d[e]f
                            <ul class="o_checklist">
                                <li class="o_checked">ghi</li>
                            </ul>
                        </li>
                    </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                    <ul class="o_checklist">
                        <li class="o_checked"><p>abc</p>
                            <ul class="o_checklist">
                                <li class="o_checked"><p>d[e]f</p></li>
                                <li class="o_checked">ghi</li>
                            </ul>
                        </li>
                    </ul>`),
        });
        await testEditor({
            contentBefore: unformat(`
                    <ul class="o_checklist">
                        <li>abc</li>
                        <li><p>d[e]f</p>
                            <ul class="o_checklist">
                                <li class="o_checked">ghi</li>
                            </ul>
                        </li>
                    </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                    <ul class="o_checklist">
                        <li><p>abc</p>
                            <ul class="o_checklist">
                                <li><p>d[e]f</p></li>
                                <li class="o_checked">ghi</li>
                            </ul>
                        </li>
                    </ul>`),
        });
        await testEditor({
            contentBefore: unformat(`
                    <ul class="o_checklist">
                        <li class="o_checked">abc</li>
                        <li><p>d[e]f</p>
                            <ul class="o_checklist">
                                <li>ghi</li>
                            </ul>
                        </li>
                    </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                    <ul class="o_checklist">
                        <li class="o_checked"><p>abc</p>
                            <ul class="o_checklist">
                                <li><p>d[e]f</p></li>
                                <li>ghi</li>
                            </ul>
                        </li>
                    </ul>`),
        });
    });
});

describe("Regular list", () => {
    test("should indent a regular list empty item", async () => {
        await testEditor({
            contentBefore: unformat(`
                    <ul>
                        <li>abc</li>
                        <li>[]</li>
                    </ul>
                    <p>def</p>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                    <ul>
                        <li><p>abc</p>
                            <ul>
                                <li>[]</li>
                            </ul>
                        </li>
                    </ul>
                    <p>def</p>`),
        });
    });

    test("should indent a regular list empty item after an splitBlock", async () => {
        await testEditor({
            contentBefore: unformat(`
                    <ul>
                        <li>abc[]</li>
                    </ul>
                    <p>def</p>`),
            stepFunction: async (editor) => {
                splitBlock(editor);
                await keydownTab(editor);
            },
            contentAfter: unformat(`
                    <ul>
                        <li><p>abc</p>
                            <ul>
                                <li>[]<br></li>
                            </ul>
                        </li>
                    </ul>
                    <p>def</p>`),
        });
    });
    test("indent regular list item when selection is not within unspittable block element", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li><br></li>
                    <li>
                        <br>[]
                        <table>
                            <tbody>
                                <tr>
                                    <td>ab</td>
                                    <td>cd</td>
                                    <td>ef</td>
                                </tr>
                            </tbody>
                        </table>
                        <br>
                    </li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li><p><br></p>
                        <ul>
                            <li>
                                []<br>
                                <table>
                                    <tbody>
                                        <tr>
                                            <td>ab</td>
                                            <td>cd</td>
                                            <td>ef</td>
                                        </tr>
                                    </tbody>
                                </table>
                                <br>
                            </li>
                        </ul>
                    </li>
                </ul>`),
        });
    });
});

describe("with selection collapsed", () => {
    test("should indent the first element of a list", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>a[]</li>
                    <li>b</li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li class="oe-nested">
                        <ul>
                            <li>a[]</li>
                        </ul>
                    </li>
                    <li>b</li>
                </ul>`),
        });
    });

    test("should indent the last element of a list", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>a</li>
                    <li>[]b</li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li><p>
                        a
                    </p>
                        <ul>
                            <li>[]b</li>
                        </ul>
                    </li>
                </ul>`),
        });
    });

    test("should indent multi-level", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>
                        a
                        <ul>
                            <li>[]b</li>
                        </ul>
                    </li>
                </ul>`),
            contentBeforeEdit: unformat(`
                <ul>
                    <li>
                        <p>a</p>
                        <ul>
                            <li>[]b</li>
                        </ul>
                    </li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li>
                        <p>a</p>
                        <ul>
                            <li class="oe-nested">
                                <ul>
                                    <li>[]b</li>
                                </ul>
                            </li>
                        </ul>
                    </li>
                </ul>`),
        });
    });

    test("should indent the last element of a list with proper with unordered list", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ol>
                    <li>a</li>
                    <li>[]b</li>
                </ol>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ol>
                    <li><p>
                        a
                    </p>
                        <ol>
                            <li>[]b</li>
                        </ol>
                    </li>
                </ol>`),
        });
    });

    test("should indent the middle element of a list", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>a</li>
                    <li>[]b</li>
                    <li>c</li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li><p>
                        a
                    </p>
                        <ul>
                            <li>[]b</li>
                        </ul>
                    </li>
                    <li>
                        c
                    </li>
                </ul>`),
        });
    });

    test("should indent even if the first element of a list is selected", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>[]a</li>
                    <li>b</li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li class="oe-nested">
                        <ul>
                            <li>[]a</li>
                        </ul>
                    </li>
                    <li>b</li>
                </ul>`),
        });
    });

    test("should indent only one element of a list with sublist", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>a</li>
                    <li><p>[]b</p>
                        <ul>
                            <li>c</li>
                        </ul>
                    </li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li><p>a</p>
                        <ul>
                            <li><p>[]b</p></li>
                            <li>c</li>
                        </ul>
                    </li>
                </ul>`),
        });
    });

    test("should convert mixed lists", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>a</li>
                    <li><p>
                        []b
                    </p>
                        <ol>
                            <li>c</li>
                        </ol>
                    </li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li><p>
                        a
                    </p>
                        <ol>
                            <li><p>[]b</p></li>
                            <li>c</li>
                        </ol>
                    </li>
                </ul>`),
        });
    });

    test("should rejoin after indent", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ol>
                    <li class="oe-nested">
                        <ol>
                            <li>a</li>
                        </ol>
                    </li>
                    <li><p>
                        []b
                    </p>
                        <ol>
                            <li>c</li>
                        </ol>
                    </li>
                </ol>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ol>
                    <li class="oe-nested">
                        <ol>
                            <li>a</li>
                            <li><p>[]b</p></li>
                            <li>c</li>
                        </ol>
                    </li>
                </ol>`),
        });
    });

    test("should indent unordered list inside a table cell", async () => {
        await testEditor({
            contentBefore: unformat(`
                        <table>
                            <tbody>
                                <tr>
                                    <td>
                                        <ul>
                                            <li>abc</li>
                                            <li>def[]</li>
                                        </ul>
                                    </td>
                                    <td>
                                        ghi
                                    </td>
                                    <td>
                                        jkl
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    `),
            stepFunction: async (editor) => await keydownTab(editor),
            contentAfter: unformat(`
                        <table>
                            <tbody>
                                <tr>
                                    <td>
                                        <ul>
                                            <li><p>abc</p>
                                                <ul>
                                                    <li>def[]</li>
                                                </ul>
                                            </li>
                                        </ul>
                                    </td>
                                    <td>
                                        ghi
                                    </td>
                                    <td>
                                        jkl
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    `),
        });
    });

    test("should indent checklist inside a table cell", async () => {
        await testEditor({
            contentBefore: unformat(`
                        <table>
                            <tbody>
                                <tr>
                                    <td>
                                        <ul class="o_checklist">
                                            <li>abc</li>
                                            <li>def[]</li>
                                        </ul>
                                    </td>
                                    <td>
                                        ghi
                                    </td>
                                    <td>
                                        jkl
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    `),
            stepFunction: async (editor) => await keydownTab(editor),
            contentAfter: unformat(`
                        <table>
                            <tbody>
                                <tr>
                                    <td>
                                        <ul class="o_checklist">
                                            <li><p>abc</p>
                                                <ul class="o_checklist">
                                                    <li>def[]</li>
                                                </ul>
                                            </li>
                                        </ul>
                                    </td>
                                    <td>
                                        ghi
                                    </td>
                                    <td>
                                        jkl
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    `),
        });
    });

    test("should not indent a nav-item list", async () => {
        await testEditor({
            contentBefore: '<ul><li class="nav-item">a[]</li></ul>',
            stepFunction: keydownTab,
            contentAfter: '<ul><li class="nav-item">a[]</li></ul>',
        });
    });
    test("should adjust list padding on tab", async () => {
        await testEditor({
            styleContent: ":root { font: 14px Roboto }",
            contentBefore: unformat(`
                <ol style="padding-inline-start: 58px;">
                    <li style="font-size: 56px;">abc</li>
                    <li style="font-size: 56px;">def[]</li>
                </ol>
            `),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ol style="padding-inline-start: 58px;">
                    <li style="font-size: 56px;"><p>abc</p>
                        <ol style="padding-inline-start: 59px;">
                            <li style="font-size: 56px;">def[]</li>
                        </ol>
                    </li>
                </ol>
            `),
        });
    });
});

describe("with selection", () => {
    test("should indent the first element of a list", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>[a]</li>
                    <li>b</li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li class="oe-nested">
                        <ul>
                            <li>[a]</li>
                        </ul>
                    </li>
                    <li>b</li>
                </ul>`),
        });
    });

    test("should indent the middle element of a list", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>a</li>
                    <li>[b]</li>
                    <li>c</li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li><p>
                        a
                    </p>
                        <ul>
                            <li>[b]</li>
                        </ul>
                    </li>
                    <li>
                        c
                    </li>
                </ul>`),
        });
    });

    test("should indent list item containing a block", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>
                        <h1>[abc]</h1>
                    </li>
                </ul>
            `),
            stepFunction: async (editor) => await keydownTab(editor),
            contentAfter: unformat(`
                <ul>
                    <li class="oe-nested">
                        <ul>
                            <li>
                                <h1>[abc]</h1>
                            </li>
                        </ul>
                    </li>
                </ul>
            `),
        });
    });

    test("should indent list item containing a block (2)", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    [<li><h1>abc</h1></li>]
                </ul>
            `),
            stepFunction: async (editor) => await keydownTab(editor),
            contentAfter: unformat(`
                <ul>
                    <li class="oe-nested">
                        <ul>
                            [<li><h1>abc</h1></li>]
                        </ul>
                    </li>
                </ul>
            `),
        });
    });

    test("should indent three list items, one of them containing a block", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>[a</li>
                    <li><h1>b</h1></li>
                    <li>c]</li>
                </ul>
            `),
            stepFunction: async (editor) => await keydownTab(editor),
            contentAfter: unformat(`
                <ul>
                    <li class="oe-nested">
                        <ul>
                            <li>[a</li>
                            <li>
                                <h1>b</h1>
                            </li>
                            <li>c]</li>
                        </ul>
                    </li>
                </ul>
            `),
        });
    });

    test("should indent multi-level", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li><p>
                        a
                    </p>
                        <ul>
                            <li>[b]</li>
                        </ul>
                    </li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li><p>
                        a
                    </p>
                        <ul>
                            <li class="oe-nested">
                                <ul>
                                    <li>[b]</li>
                                </ul>
                            </li>
                        </ul>
                    </li>
                </ul>`),
        });
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li><p>
                        a
                    </p>
                        <ul>
                            <li class="oe-nested">
                                <ul>
                                    <li>[b]</li>
                                </ul>
                            </li>
                        </ul>
                    </li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li><p>
                        a
                    </p>
                        <ul>
                            <li class="oe-nested">
                                <ul>
                                    <li class="oe-nested">
                                        <ul>
                                            <li>[b]</li>
                                        </ul>
                                    </li>
                                </ul>
                            </li>
                        </ul>
                    </li>
                </ul>`),
        });
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li><p>[a</p>
                        <ul>
                            <li><p>b</p>
                                <ul>
                                    <li><p>c</p>
                                        <ul>
                                            <li>d</li>
                                        </ul>
                                    </li>
                                    <li>e</li>
                                </ul>
                            </li>
                            <li>f</li>
                        </ul>
                    </li>
                    <li>g]</li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li class="oe-nested">
                        <ul>
                            <li><p>[a</p>
                                <ul>
                                    <li><p>b</p>
                                        <ul>
                                            <li><p>c</p>
                                                <ul>
                                                    <li>d</li>
                                                </ul>
                                            </li>
                                            <li>e</li>
                                        </ul>
                                    </li>
                                    <li>f</li>
                                </ul>
                            </li>
                            <li>g]</li>
                        </ul>
                    </li>
                </ul>`),
        });
    });

    test("should indent two multi-levels", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li><p>
                        a
                    </p>
                        <ul>
                            <li><p>[b</p>
                                <ul>
                                    <li>c]</li>
                                </ul>
                            </li>
                        </ul>
                    </li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li><p>
                        a
                    </p>
                        <ul>
                            <li class="oe-nested">
                                <ul>
                                    <li><p>[b</p>
                                        <ul>
                                            <li>c]</li>
                                        </ul>
                                    </li>
                                </ul>
                            </li>
                        </ul>
                    </li>
                </ul>`),
        });
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li><p>
                        a
                    </p>
                        <ul>
                            <li class="oe-nested">
                                <ul>
                                    <li><p>[b
                                    </p>
                                        <ul>
                                            <li>c]</li>
                                        </ul>
                                    </li>
                                </ul>
                            </li>
                        </ul>
                    </li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li><p>
                        a
                    </p>
                        <ul>
                            <li class="oe-nested">
                                <ul>
                                    <li class="oe-nested">
                                        <ul>
                                            <li><p>[b</p>
                                                <ul>
                                                    <li>c]</li>
                                                </ul>
                                            </li>
                                        </ul>
                                    </li>
                                </ul>
                            </li>
                        </ul>
                    </li>
                </ul>`),
        });
    });

    test("should indent multiples list item in the middle element of a list", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>a</li>
                    <li>[b</li>
                    <li>c]</li>
                    <li>d</li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li><p>
                        a
                    </p>
                        <ul>
                            <li>[b</li>
                            <li>c]</li>
                        </ul>
                    </li>
                    <li>
                        d
                    </li>
                </ul>`),
        });
    });

    test("should indent multiples list item with reversed range", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>a</li>
                    <li>]b</li>
                    <li>c[</li>
                    <li>d</li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li><p>
                        a
                    </p>
                        <ul>
                            <li>]b</li>
                            <li>c[</li>
                        </ul>
                    </li>
                    <li>
                        d
                    </li>
                </ul>`),
        });
    });

    test("should indent multiples list item in the middle element of a list with sublist", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>a</li>
                    <li><p>
                        [b
                    </p>
                        <ul>
                            <li>c</li>
                        </ul>
                    </li>
                    <li>d]</li>
                    <li>e</li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li><p>
                        a
                    </p>
                        <ul>
                            <li><p>
                                [b
                            </p>
                                <ul>
                                    <li>c</li>
                                </ul>
                            </li>
                            <li>d]</li>
                        </ul>
                    </li>
                    <li>e</li>
                </ul>`),
        });
    });

    test("should indent with mixed lists", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>a</li>
                    <li><p>
                        [b
                    </p>
                        <ol>
                            <li>c]</li>
                        </ol>
                    </li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li><p>
                        a
                    </p>
                        <ol>
                            <li><p>
                                [b
                            </p>
                                <ol>
                                    <li>c]</li>
                                </ol>
                            </li>
                        </ol>
                    </li>
                </ul>`),
        });
    });

    test("should only indent elements with selected content (mix lists)", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>a</li>
                    <li><p>
                        [b
                    </p>
                        <ol>
                            <li>]c</li>
                        </ol>
                    </li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li><p>a</p>
                        <ol>
                            <li><p>
                                [b
                            </p>
                                <ol>
                                    <li>]c</li>
                                </ol>
                            </li>
                        </ol>
                    </li>
                </ul>`),
        });
    });

    test.tags("desktop");
    test("should only indent elements with selected content (mix lists - triple click)", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>a</li>
                    <li>
                        <p>b</p>
                        <ol>
                            <li>c</li>
                        </ol>
                    </li>
                </ul>`),
            stepFunction: async (editor) => {
                await tripleClick(editor.editable.querySelectorAll("li")[1]);
                await keydownTab(editor);
            },
            contentAfter: unformat(`
                <ul>
                    <li><p>a</p>
                        <ol>
                            <li><p>[b]</p></li>
                            <li>c</li>
                        </ol>
                    </li>
                </ul>`),
        });
    });

    test("should indent nested list and list with elements in a upper level than the rangestart", async () => {
        await testEditor({
            contentBefore: unformat(`
                <ul>
                    <li>a</li>
                    <li><p>
                        b
                    </p>
                        <ul>
                            <li>c</li>
                            <li>[d</li>
                        </ul>
                    </li>
                    <li><p>
                        e
                    </p>
                        <ul>
                            <li>f</li>
                            <li>g</li>
                        </ul>
                    </li>
                    <li>h]</li>
                    <li>i</li>
                </ul>`),
            stepFunction: keydownTab,
            contentAfter: unformat(`
                <ul>
                    <li>a</li>
                    <li><p>
                        b
                    </p>
                        <ul>
                            <li><p>
                                c
                            </p>
                                <ul>
                                    <li>[d</li>
                                </ul>
                            </li>
                            <li><p>
                            e
                            </p>
                            <ul>
                                <li>f</li>
                                <li>g</li>
                            </ul>
                        </li>
                        <li>h]</li>
                        </ul>
                    </li>
                    <li>i</li>
                </ul>`),
        });
    });

    test("should not indent a non-editable list", async () => {
        const tab = '<span class="oe-tabs" style="width: 40px;">\u0009</span>\u200B';
        await testEditor({
            contentBefore: unformat(`
                <p>[before</p>
                <ul>
                    <li>a</li>
                </ul>
                <ul contenteditable="false">
                    <li>a</li>
                </ul>
                <p>after]</p>`),
            stepFunction: keydownTab,
            contentAfter:
                `<p>${tab}[before</p>` +
                unformat(`
                    <ul>
                        <li class="oe-nested">
                            <ul>
                                <li>a</li>
                            </ul>
                        </li>
                    </ul>
                    <ul contenteditable="false">
                        <li>a</li>
                    </ul>`) +
                `<p>${tab}after]</p>`,
        });
    });

    test("should indent ordered list inside a table cell", async () => {
        await testEditor({
            contentBefore: unformat(`
                        <table>
                            <tbody>
                                <tr>
                                    <td>
                                        <ol>
                                            <li>abc</li>
                                            <li>[def]</li>
                                        </ol>
                                    </td>
                                    <td>
                                        ghi
                                    </td>
                                    <td>
                                        jkl
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    `),
            stepFunction: async (editor) => await keydownTab(editor),
            contentAfter: unformat(`
                        <table>
                            <tbody>
                                <tr>
                                    <td>
                                        <ol>
                                            <li><p>abc</p>
                                                <ol>
                                                    <li>[def]</li>
                                                </ol>
                                            </li>
                                        </ol>
                                    </td>
                                    <td>
                                        ghi
                                    </td>
                                    <td>
                                        jkl
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    `),
        });
    });
});

describe("Mixed: list + paragraph", () => {
    test("should indent a list and paragraph", async () => {
        const contentBefore = unformat(`
            <ul>
                <li>[abc</li>
            </ul>
            <p>def]</p>`);
        const { el, editor } = await setupEditor(contentBefore);

        await keydownTab(editor);

        /* eslint-disable */
        const expectedContent =
            unformat(`
            <ul>
                <li class="oe-nested">
                    <ul>
                        <li>[abc</li>
                    </ul>
                </li>
            </ul>`) +
            '<p><span class="oe-tabs" contenteditable="false" style="width: 40px;">\t</span>\u200bdef]</p>';
        /* eslint-enable */
        expect(getContent(el)).toBe(expectedContent);

        // Check that it was done as single history step.
        undo(editor);
        expect(getContent(el)).toBe(contentBefore);
    });
});
