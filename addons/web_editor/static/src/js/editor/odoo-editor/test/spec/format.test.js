import { isSelectionFormat } from '../../src/utils/utils.js';
import { BasicEditor, testEditor, setTestSelection, Direction, unformat, insertText, triggerEvent } from '../utils.js';

const bold = async editor => {
    await editor.execCommand('bold');
};
const italic = async editor => {
    await editor.execCommand('italic');
};
const underline = async editor => {
    await editor.execCommand('underline');
};
const strikeThrough = async editor => {
    await editor.execCommand('strikeThrough');
};
const setFontSize = size => editor => editor.execCommand('setFontSize', size);

const setFontSizeClassName = className => editor => editor.execCommand('setFontSizeClassName', className);

const switchDirection = editor => editor.execCommand('switchDirection');

describe('Format', () => {
    const getZwsTag = (tagName, {style} = {}) => {
        const styleAttr = style ? ` style="${style}"` : '';
        return (content, zws) => {
            const zwsFirstAttr = zws === 'first' ? ' data-oe-zws-empty-inline=""' : '';
            const zwsLastAttr = zws === 'last' ? ' data-oe-zws-empty-inline=""' : '';
            return `<${tagName}${zwsFirstAttr}${styleAttr}${zwsLastAttr}>${content}</${tagName}>`
        };
    }

    const span = getZwsTag('span');

    const strong = getZwsTag('strong');
    const notStrong = getZwsTag('span', {style: 'font-weight: normal;'});
    const spanBold = getZwsTag('span', {style: 'font-weight: bolder;'});
    const b = getZwsTag('b');
    const repeatWithBoldTags = async (cb) => {
        for (const fn of [spanBold, b, strong]) {
            await cb(fn);
        }
    }

    const em = getZwsTag('em');

    const u = getZwsTag('u');

    const s = getZwsTag('s');


    describe('bold', () => {
        it('should make a few characters bold', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>ab[cde]fg</p>',
                stepFunction: bold,
                contentAfter: `<p>ab${strong(`[cde]`)}fg</p>`,
            });
        });
        it('should make a few characters bold inside table', async () => {
            await testEditor(BasicEditor, {
                contentBefore: unformat(`
                    <table class="table table-bordered o_table o_selected_table">
                        <tbody>
                            <tr>
                                <td class="o_selected_td"><p>[abc</p></td>
                                <td class="o_selected_td"><p>def</p></td>
                                <td class="o_selected_td"><p>]<br></p></td>
                            </tr>
                            <tr>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                            <tr>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                        </tbody>
                    </table>`
                ),
                stepFunction: async editor => {
                    await triggerEvent(editor.editable, 'keydown', { key: 'b', ctrlKey: true });
                },
                contentAfterEdit: unformat(`
                    <table class="table table-bordered o_table o_selected_table">
                        <tbody>
                            <tr>
                                <td class="o_selected_td"><p>${strong(`[abc`)}</p></td>
                                <td class="o_selected_td"><p>${strong(`def`)}</p></td>
                                <td class="o_selected_td"><p>${strong(`]<br>`)}</p></td>
                            </tr>
                            <tr>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                            <tr>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                        </tbody>
                    </table>`
                ),
            });
        });
        it('should make a few characters not bold', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${strong(`ab[cde]fg`)}</p>`,
                stepFunction: bold,
                contentAfter: `<p>${strong(`ab`)}[cde]${strong(`fg`)}</p>`,
            });
        });
        it('should make two paragraphs bold', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>[abc</p><p>def]</p>',
                stepFunction: bold,
                contentAfter: `<p>${strong(`[abc`)}</p><p>${strong(`def]`)}</p>`,
            });
        });
        it('should make two paragraphs not bold', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${strong(`[abc`)}</p><p>${strong(`def]`)}</p>`,
                stepFunction: bold,
                contentAfter: `<p>[abc</p><p>def]</p>`,
            });
        });
        it('should make qweb tag bold', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<div><p t-esc="'Test'" contenteditable="false">[Test]</p></div>`,
                stepFunction: bold,
                contentAfter: `<div><p t-esc="'Test'" contenteditable="false" style="font-weight: bolder;">[Test]</p></div>`,
            });
            await testEditor(BasicEditor, {
                contentBefore: `<div><p t-field="record.name" contenteditable="false">[Test]</p></div>`,
                stepFunction: bold,
                contentAfter: `<div><p t-field="record.name" contenteditable="false" style="font-weight: bolder;">[Test]</p></div>`,
            });
        });
        it('should make qweb tag bold even with partial selection', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<div><p t-esc="'Test'" contenteditable="false">T[e]st</p></div>`,
                stepFunction: bold,
                contentAfter: `<div><p t-esc="'Test'" contenteditable="false" style="font-weight: bolder;">T[e]st</p></div>`,
            });
        });
        it('should make a whole heading bold after a triple click', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<h1>${notStrong(`[ab`)}</h1><p>]cd</p>`,
                stepFunction: bold,
                contentAfter: `<h1>[ab]</h1><p>cd</p>`,
            });
        });
        it('should make a whole heading not bold after a triple click (heading is considered bold)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>[ab</h1><p>]cd</p>',
                stepFunction: bold,
                contentAfter: `<h1>${notStrong(`[ab]`)}</h1><p>cd</p>`,
            });
        });
        it('should make a selection starting with bold text fully bold', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${strong(`[ab`)}</p><p>c]d</p>`,
                stepFunction: bold,
                contentAfter: `<p>${strong(`[ab`)}</p><p>${strong(`c]`)}d</p>`,
            });
        });
        it('should make a selection with bold text in the middle fully bold', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>[a${strong(`b`)}</p><p>${strong(`c`)}d]e</p>`,
                stepFunction: bold,
                contentAfter: `<p>${strong(`[ab`)}</p><p>${strong(`cd]`)}e</p>`,
            });
        });
        it('should make a selection ending with bold text fully bold', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<h1>${notStrong(`[ab`)}</h1><p>${strong(`c]d`)}</p>`,
                stepFunction: bold,
                contentAfter: `<h1>[ab</h1><p>${strong(`c]d`)}</p>`,
            });
        });
        it('should get ready to type in bold', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>ab[]cd</p>',
                stepFunction: bold,
                contentAfterEdit: `<p>ab${strong(`[]\u200B`, 'first')}cd</p>`,
                contentAfter: `<p>ab[]cd</p>`,
            });
        });
        it('should get ready to type in not bold', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${strong(`ab[]cd`)}</p>`,
                stepFunction: bold,
                contentAfterEdit: `<p>${strong(`ab`)}${span(`[]\u200B`, 'first')}${strong(`cd`)}</p>`,
                contentAfter: `<p>${strong(`ab[]cd`)}</p>`,
            });
        });


        it('should remove a bold tag that was redondant while performing the command', async () => {
            await repeatWithBoldTags(async (tag) => {
                await testEditor(BasicEditor, {
                    contentBefore: `<p>a${tag(`b${tag(`[c]`)}d`)}e</p>`,
                    stepFunction: bold,
                    contentAfter: `<p>a${tag('b')}[c]${tag('d')}e</p>`,
                });
            });
        });
        it('should remove a bold tag that was redondant with different tags while performing the command', async () => {
            await testEditor(BasicEditor, {
                contentBefore: unformat(`<p>
                    a
                    <span style="font-weight: bolder;">
                        b
                        <strong>c<b>[d]</b>e</strong>
                        f
                    </span>
                    g
                </p>`),
                stepFunction: bold,
                contentAfter: unformat(`<p>
                    a
                    <span style="font-weight: bolder;">b<strong>c</strong></span>
                    [d]
                    <span style="font-weight: bolder;"><strong>e</strong>f</span>
                    g
                </p>`),
            });
        });
        it('should not format non-editable text (bold)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>[a</p><p contenteditable="false">b</p><p>c]</p>',
                stepFunction: bold,
                contentAfter: `<p>${strong('[a')}</p><p contenteditable="false">b</p><p>${strong('c]')}</p>`,
            });
        });

        describe('inside container or inline with class already bold', () => {
            it('should force the font-weight to normal with an inline with class', async () => {
                await testEditor(BasicEditor, {
                    styleContent: `.boldClass { font-weight: bold; }`,
                    contentBefore: `<div>a<span class="boldClass">[b]</span>c</div>`,
                    stepFunction: bold,
                    contentAfter: `<div>a<span class="boldClass"><span style="font-weight: normal;">[b]</span></span>c</div>`,
                });
            });

            it('should force the font-weight to normal', async () => {
                await testEditor(BasicEditor, {
                    contentBefore: `<h1>a[b]c</h1>`,
                    stepFunction: bold,
                    contentAfter: `<h1>a<span style="font-weight: normal;">[b]</span>c</h1>`,
                });
            });

            it('should force the font-weight to normal while removing redundant tag', async () => {
                await repeatWithBoldTags(async (tag) => {
                    await testEditor(BasicEditor, {
                        contentBefore: `<h1>a${tag('[b]')}c</h1>`,
                        stepFunction: bold,
                        contentAfter: `<h1>a<span style="font-weight: normal;">[b]</span>c</h1>`,
                    });
                });
            });
        });
        describe('inside container font-weight: 500 and strong being strong-weight: 500', () => {
            it('should remove the redundant strong style and add span with a bolder font-weight', async () => {
                await testEditor(BasicEditor, {
                    styleContent: `h1, strong {font-weight: 500;}`,
                    contentBefore: `<h1>a${strong(`[b]`)}c</h1>`,
                    stepFunction: bold,
                    contentAfter: `<h1>a<span style="font-weight: bolder;">[b]</span>c</h1>`,
                });
            });
        });
    });
    describe('bold and italic inside container already bold', () => {
        it('should remove the redundant strong style and add span with a bolder font-weight', async () => {
            await testEditor(BasicEditor, {
                styleContent: `h1 {font-weight: bold;}`,
                contentBefore: `<h1>a[b]c</h1>`,
                stepFunction: (editor) => {
                    editor.execCommand('italic');
                    editor.execCommand('bold');
                    editor.execCommand('italic');
                },
                contentAfter: `<h1>a<span style="font-weight: normal;">[b]</span>c</h1>`,
            });
        });
    });

    describe('italic', () => {
        it('should make a few characters italic', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab[cde]fg</p>`,
                stepFunction: italic,
                contentAfter: `<p>ab${em(`[cde]`)}fg</p>`,
            });
        });
        it('should make a few characters italic inside table', async () => {
            await testEditor(BasicEditor, {
                contentBefore: unformat(`
                    <table class="table table-bordered o_table o_selected_table">
                        <tbody>
                            <tr>
                                <td class="o_selected_td"><p>[abc</p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                            <tr>
                                <td class="o_selected_td"><p>def</p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                            <tr>
                                <td class="o_selected_td"><p>]<br></p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                        </tbody>
                    </table>`
                ),
                stepFunction: async editor => {
                    await triggerEvent(editor.editable, 'keydown', { key: 'i', ctrlKey: true });
                },
                contentAfterEdit: unformat(`
                    <table class="table table-bordered o_table o_selected_table">
                        <tbody>
                            <tr>
                                <td class="o_selected_td"><p>${em(`[abc`)}</p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                            <tr>
                                <td class="o_selected_td"><p>${em(`def`)}</p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                            <tr>
                                <td class="o_selected_td"><p>${em(`]<br>`)}</p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                        </tbody>
                    </table>`
                ),
            });
        });
        it('should make a few characters not italic', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${em(`ab[cde]fg`)}</p>`,
                stepFunction: italic,
                contentAfter: `<p>${em(`ab`)}[cde]${em(`fg`)}</p>`,
            });
        });
        it('should make two paragraphs italic', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>[abc</p><p>def]</p>',
                stepFunction: italic,
                contentAfter: `<p>${em(`[abc`)}</p><p>${em(`def]`)}</p>`,
            });
        });
        it('should make two paragraphs not italic', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${em(`[abc`)}</p><p>${em(`def]`)}</p>`,
                stepFunction: italic,
                contentAfter: `<p>[abc</p><p>def]</p>`,
            });
        });
        it('should make qweb tag italic', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<div><p t-esc="'Test'" contenteditable="false">[Test]</p></div>`,
                stepFunction: italic,
                contentAfter: `<div><p t-esc="'Test'" contenteditable="false" style="font-style: italic;">[Test]</p></div>`,
            });
        });
        it('should make a whole heading italic after a triple click', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<h1>[ab</h1><p>]cd</p>`,
                stepFunction: italic,
                contentAfter: `<h1>${em(`[ab]`)}</h1><p>cd</p>`,
            });
        });
        it('should make a whole heading not italic after a triple click', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<h1>${em(`[ab`)}</h1><p>]cd</p>`,
                stepFunction: italic,
                contentAfter: `<h1>[ab]</h1><p>cd</p>`,
            });
        });
        it('should make a selection starting with italic text fully italic', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${em(`[ab`)}</p><p>c]d</p>`,
                stepFunction: italic,
                contentAfter: `<p>${em(`[ab`)}</p><p>${em(`c]`)}d</p>`,
            });
        });
        it('should make a selection with italic text in the middle fully italic', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>[a${em(`b`)}</p><p>${em(`c`)}d]e</p>`,
                stepFunction: italic,
                contentAfter: `<p>${em(`[ab`)}</p><p>${em(`cd]`)}e</p>`,
            });
        });
        it('should make a selection ending with italic text fully italic', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>[ab</p><p>${em(`c]d`)}</p>`,
                stepFunction: italic,
                contentAfter: `<p>${em(`[ab`)}</p><p>${em(`c]d`)}</p>`,
            });
        });
        it('should get ready to type in italic', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab[]cd</p>`,
                stepFunction: italic,
                contentAfterEdit: `<p>ab${em(`[]\u200B`, 'first')}cd</p>`,
                contentAfter: `<p>ab[]cd</p>`,
            });
        });
        it('should get ready to type in not italic', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${em(`ab[]cd`)}</p>`,
                stepFunction: italic,
                contentAfterEdit: `<p>${em(`ab`)}${span(`[]\u200B`, 'first')}${em(`cd`)}</p>`,
                contentAfter: `<p>${em(`ab[]cd`)}</p>`,
            });
        });
        it('should not format non-editable text (italic)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>[a</p><p contenteditable="false">b</p><p>c]</p>',
                stepFunction: italic,
                contentAfter: `<p>${em('[a')}</p><p contenteditable="false">b</p><p>${em('c]')}</p>`,
            });
        });
    });
    describe('underline', () => {
        it('should make a few characters underline', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab[cde]fg</p>`,
                stepFunction: underline,
                contentAfter: `<p>ab${u(`[cde]`)}fg</p>`,
            });
        });
        it('should make a few characters underline inside table', async () => {
            await testEditor(BasicEditor, {
                contentBefore: unformat(`
                    <table class="table table-bordered o_table o_selected_table">
                        <tbody>
                            <tr>
                                <td class="o_selected_td"><p>[abc</p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                            <tr>
                                <td class="o_selected_td"><p>def</p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                            <tr>
                                <td class="o_selected_td"><p>]<br></p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                        </tbody>
                    </table>`
                ),
                stepFunction: async editor => {
                    await triggerEvent(editor.editable, 'keydown', { key: 'u', ctrlKey: true });
                },
                contentAfterEdit: unformat(`
                    <table class="table table-bordered o_table o_selected_table">
                        <tbody>
                            <tr>
                                <td class="o_selected_td"><p>${u(`[abc`)}</p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                            <tr>
                                <td class="o_selected_td"><p>${u(`def`)}</p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                            <tr>
                                <td class="o_selected_td"><p>${u(`]<br>`)}</p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                        </tbody>
                    </table>`
                ),
            });
        });
        it('should make a few characters not underline', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${u(`ab[cde]fg`)}</p>`,
                stepFunction: underline,
                contentAfter: `<p>${u(`ab`)}[cde]${u(`fg`)}</p>`,
            });
        });
        it('should make two paragraphs underline', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>[abc</p><p>def]</p>',
                stepFunction: underline,
                contentAfter: `<p>${u(`[abc`)}</p><p>${u(`def]`)}</p>`,
            });
        });
        it('should make two paragraphs not underline', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${u(`[abc`)}</p><p>${u(`def]`)}</p>`,
                stepFunction: underline,
                contentAfter: '<p>[abc</p><p>def]</p>',
            });
        });
        it('should make qweb tag underline', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<div><p t-esc="'Test'" contenteditable="false">[Test]</p></div>`,
                stepFunction: underline,
                contentAfter: `<div><p t-esc="'Test'" contenteditable="false" style="text-decoration-line: underline;">[Test]</p></div>`,
            });
        });
        it('should make a whole heading underline after a triple click', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<h1>[ab</h1><p>]cd</p>`,
                stepFunction: underline,
                contentAfter: `<h1>${u(`[ab]`)}</h1><p>cd</p>`,
            });
        });
        it('should make a whole heading not underline after a triple click', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<h1>${u(`[ab`)}</h1><p>]cd</p>`,
                stepFunction: underline,
                contentAfter: `<h1>[ab]</h1><p>cd</p>`,
            });
        });
        it('should make a selection starting with underline text fully underline', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${u(`[ab`)}</p><p>c]d</p>`,
                stepFunction: underline,
                contentAfter: `<p>${u(`[ab`)}</p><p>${u(`c]`)}d</p>`,
            });
        });
        it('should make a selection with underline text in the middle fully underline', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>[a${u(`b`)}</p><p>${u(`c`)}d]e</p>`,
                stepFunction: underline,
                contentAfter: `<p>${u(`[ab`)}</p><p>${u(`cd]`)}e</p>`,
            });
        });
        it('should make a selection ending with underline text fully underline', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>[ab</h1><p>${u(`c]d`)}</p>`,
                stepFunction: underline,
                contentAfter: `<p>${u(`[ab`)}</p><p>${u(`c]d`)}</p>`,
            });
        });
        it('should get ready to type in underline', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab[]cd</p>`,
                stepFunction: underline,
                contentAfterEdit: `<p>ab${u(`[]\u200B`, 'first')}cd</p>`,
                contentAfter: `<p>ab[]cd</p>`,
            });
        });
        it('should get ready to type in not underline', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${u(`ab[]cd`)}</p>`,
                stepFunction: underline,
                contentAfterEdit: `<p>${u(`ab`)}${span(`[]\u200B`, 'first')}${u(`cd`)}</p>`,
                contentAfter: `<p>${u(`ab[]cd`)}</p>`,
            });
        });
        it('should not format non-editable text (underline)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>[a</p><p contenteditable="false">b</p><p>c]</p>',
                stepFunction: underline,
                contentAfter: `<p>${u('[a')}</p><p contenteditable="false">b</p><p>${u('c]')}</p>`,
            });
        });
    });
    describe('strikeThrough', () => {
        it('should make a few characters strikeThrough', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab[cde]fg</p>`,
                stepFunction: strikeThrough,
                contentAfter: `<p>ab${s(`[cde]`)}fg</p>`,
            });
        });
        it('should make a few characters strikeThrough inside table', async () => {
            await testEditor(BasicEditor, {
                contentBefore: unformat(`
                    <table class="table table-bordered o_table o_selected_table">
                        <tbody>
                            <tr>
                                <td class="o_selected_td"><p>[abc</p></td>
                                <td class="o_selected_td"><p>def</p></td>
                                <td class="o_selected_td"><p>]<br></p></td>
                            </tr>
                            <tr>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                            <tr>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                        </tbody>
                    </table>`
                ),
                stepFunction: async editor => {
                    await triggerEvent(editor.editable, 'keydown', { key: '5', ctrlKey: true });
                },
                contentAfterEdit: unformat(`
                    <table class="table table-bordered o_table o_selected_table">
                        <tbody>
                            <tr>
                                <td class="o_selected_td"><p>${s(`[abc`)}</p></td>
                                <td class="o_selected_td"><p>${s(`def`)}</p></td>
                                <td class="o_selected_td"><p>${s(`]<br>`)}</p></td>
                            </tr>
                            <tr>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                            <tr>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                                <td><p><br></p></td>
                            </tr>
                        </tbody>
                    </table>`
                ),
            });
        });
        it('should make a few characters not strikeThrough', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${s(`ab[cde]fg`)}</p>`,
                stepFunction: strikeThrough,
                contentAfter: `<p>${s(`ab`)}[cde]${s(`fg`)}</p>`,
            });
        });
        it('should make a few characters strikeThrough then remove style inside', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab[c d]ef</p>`,
                stepFunction: async editor => {
                    await strikeThrough(editor);
                    const styleSpan = editor.editable.querySelector('s').childNodes[0];
                    const selection = {
                        anchorNode: styleSpan,
                        anchorOffset: 1,
                        focusNode: styleSpan,
                        focusOffset: 2,
                        direction: Direction.FORWARD,
                    };
                    await setTestSelection(selection);
                    await strikeThrough(editor);
                },
                contentAfter: `<p>ab<s>c</s>[ ]<s>d</s>ef</p>`,
            });
        });
        it('should make strikeThrough then more then remove', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>abc[ ]def</p>`,
                stepFunction: async editor => {
                    await strikeThrough(editor);
                    const pElem = editor.editable.querySelector('p').childNodes;
                    const selection = {
                        anchorNode: pElem[0],
                        anchorOffset: 2,
                        focusNode: pElem[2],
                        focusOffset: 1,
                        direction: Direction.FORWARD,
                    };
                    await setTestSelection(selection);
                    await strikeThrough(editor);
                },
                contentAfter: `<p>ab${s(`[c d]`)}ef</p>`,
            });
            await testEditor(BasicEditor, {
                contentBefore: `<p>abc[ ]def</p>`,
                stepFunction: async editor => {
                    await strikeThrough(editor);
                    const pElem = editor.editable.querySelector('p').childNodes;
                    const selection = {
                        anchorNode: pElem[0],
                        anchorOffset: 2,
                        focusNode: pElem[2],
                        focusOffset: 1,
                        direction: Direction.FORWARD,
                    };
                    await setTestSelection(selection);
                    await strikeThrough(editor);
                    await strikeThrough(editor);
                },
                contentAfter: `<p>ab[c d]ef</p>`,
            });
        });
        it('should make two paragraphs strikeThrough', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>[abc</p><p>def]</p>',
                stepFunction: strikeThrough,
                contentAfter: `<p>${s(`[abc`)}</p><p>${s(`def]`)}</p>`,
            });
        });
        it('should make two paragraphs not strikeThrough', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${s(`[abc`)}</p><p>${s(`def]`)}</p>`,
                stepFunction: strikeThrough,
                contentAfter: '<p>[abc</p><p>def]</p>',
            });
        });
        it('should make qweb tag strikeThrough', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<div><p t-esc="'Test'" contenteditable="false">[Test]</p></div>`,
                stepFunction: strikeThrough,
                contentAfter: `<div><p t-esc="'Test'" contenteditable="false" style="text-decoration-line: line-through;">[Test]</p></div>`,
            });
        });
        it('should make a whole heading strikeThrough after a triple click', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<h1>[ab</h1><p>]cd</p>`,
                stepFunction: strikeThrough,
                contentAfter: `<h1>${s(`[ab]`)}</h1><p>cd</p>`,
            });
        });
        it('should make a whole heading not strikeThrough after a triple click', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<h1>${s(`[ab`)}</h1><p>]cd</p>`,
                stepFunction: strikeThrough,
                contentAfter: `<h1>[ab]</h1><p>cd</p>`,
            });
        });
        it('should make a selection starting with strikeThrough text fully strikeThrough', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${s(`[ab`)}</p><p>c]d</p>`,
                stepFunction: strikeThrough,
                contentAfter: `<p>${s(`[ab`)}</p><p>${s(`c]`)}d</p>`,
            });
        });
        it('should make a selection with strikeThrough text in the middle fully strikeThrough', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>[a${s(`b`)}</p><p>${s(`c`)}d]e</p>`,
                stepFunction: strikeThrough,
                contentAfter: `<p>${s(`[ab`)}</p><p>${s(`cd]`)}e</p>`,
            });
        });
        it('should make a selection ending with strikeThrough text fully strikeThrough', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>[ab</h1><p>${s(`c]d`)}</p>`,
                stepFunction: strikeThrough,
                contentAfter: `<p>${s(`[ab`)}</p><p>${s(`c]d`)}</p>`,
            });
        });
        it('should get ready to type in strikeThrough', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab[]cd</p>`,
                stepFunction: strikeThrough,
                contentAfterEdit: `<p>ab${s(`[]\u200B`, 'first')}cd</p>`,
                contentAfter: `<p>ab[]cd</p>`,
            });
        });
        it('should get ready to type in not underline', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${s(`ab[]cd`)}</p>`,
                stepFunction: strikeThrough,
                contentAfterEdit: `<p>${s(`ab`)}${span(`[]\u200B`, 'first')}${s(`cd`)}</p>`,
                contentAfter: `<p>${s(`ab[]cd`)}</p>`,
            });
        });
        it('should do nothing when a block already has a line-through decoration', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p style="text-decoration: line-through;">a[b]c</p>`,
                stepFunction: strikeThrough,
                contentAfter: `<p style="text-decoration: line-through;">a[b]c</p>`,
            });
        });
        it('should insert before strikethrough', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>d[a${s('bc]<br><br>')}</p>`,
                stepFunction: async editor => {
                    insertText(editor, 'A');
                },
                contentAfter: `<p>dA[]${s(`<br><br>`)}</p>`,
            });
            await testEditor(BasicEditor, {
                contentBefore: `<p>[a${s('bc]<br><br>')}</p>`,
                stepFunction: async editor => {
                    insertText(editor, 'A');
                },
                contentAfter: `<p>${s(`A[]<br><br>`)}</p>`,
            });
        });
        it('should not format non-editable text (strikeThrough)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>[a</p><p contenteditable="false">b</p><p>c]</p>',
                stepFunction: strikeThrough,
                contentAfter: `<p>${s('[a')}</p><p contenteditable="false">b</p><p>${s('c]')}</p>`,
            });
        });
    });

    describe('underline + strikeThrough', () => {
        it('should get ready to write in strikeThrough without underline (underline was first)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab${u(s(`cd[]ef`))}</p>`,
                stepFunction: underline,
                contentAfterEdit: `<p>ab${u(s(`cd`))}${s(`[]\u200b`, 'last')}${u(s(`ef`))}</p>`,
                contentAfter: `<p>ab${u(s(`cd[]ef`))}</p>`,
            });
        });
        it('should restore underline after removing it (collapsed, strikeThrough)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab${u(s(`cd`))}${s(`\u200b[]`, 'first')}${u(s(`ef`))}</p>`,
                stepFunction: underline,
                contentAfterEdit: `<p>ab${u(s(`cd`))}${s(u(`[]\u200b`, 'first'), 'first')}${u(s(`ef`))}</p>`,
                contentAfter: `<p>ab${u(s(`cd[]ef`))}</p>`,
            });
        });
        it('should remove underline after restoring it after removing it (collapsed, strikeThrough)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab${u(s(`cd`))}${s(u(`[]\u200b`, 'first'))}${u(s(`ef`))}</p>`,
                stepFunction: underline,
                contentAfterEdit: `<p>ab${u(s(`cd`))}${s(`[]\u200b`, 'last')}${u(s(`ef`))}</p>`,
                contentAfter: `<p>ab${u(s(`cd[]ef`))}</p>`,
            });
        });
        it('should remove underline after restoring it and writing after removing it (collapsed, strikeThrough)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab${u(s(`cd`))}${s(u(`ghi[]`))}${u(s(`ef`))}</p>`,
                stepFunction: underline,
                contentAfterEdit: `<p>ab${u(s(`cd`))}${s(`${u(`ghi`)}`)}${s(`[]\u200b`, 'first')}${u(s(`ef`))}</p>`,
                // The reason the cursor is after the tag <s> is because when the editor get's cleaned, the zws tag gets deleted.
                contentAfter: `<p>ab${u(s(`cd`))}${s(u(`ghi`))}[]${u(s(`ef`))}</p>`,
            });
        });
        it('should remove underline, write, restore underline, write, remove underline again, write (collapsed, strikeThrough)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab${u(s(`cd[]ef`))}</p>`,
                stepFunction: async editor => {
                    await editor.execCommand('underline');
                    await editor.execCommand('insert', 'A');
                    await editor.execCommand('underline');
                    await editor.execCommand('insert', 'B');
                    await editor.execCommand('underline');
                    await editor.execCommand('insert', 'C');
                },
                contentAfterEdit: `<p>ab${u(s(`cd`))}${s(`A${u("B")}C[]`)}${u(s(`ef`))}</p>`,
            });
        });
        it('should remove only underline decoration on a span', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p><span style="text-decoration: underline line-through;">[a]</span></p>`,
                stepFunction: underline,
                contentAfter: `<p><span style="text-decoration: line-through;">[a]</span></p>`,
            });
        });
    });
    describe('underline + italic', () => {
        it('should get ready to write in italic and underline', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab[]cd</p>`,
                stepFunction: async editor => {
                    await editor.execCommand('italic');
                    await editor.execCommand('underline');
                },
                contentAfterEdit: `<p>ab${em(u(`[]\u200B`, 'first'), 'first')}cd</p>`,
                contentAfter: `<p>ab[]cd</p>`,
            });
        });
        it('should get ready to write in italic, after changing one\'s mind about underline (two consecutive at the end)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab[]cd</p>`,
                stepFunction: async editor => {
                    await editor.execCommand('italic');
                    await editor.execCommand('underline');
                    await editor.execCommand('underline');
                },
                contentAfterEdit: `<p>ab${em(`[]\u200B`, 'first')}cd</p>`,
                contentAfter: `<p>ab[]cd</p>`,
            });
        });
        it('should get ready to write in italic, after changing one\'s mind about underline (separated by italic)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab[]cd</p>`,
                stepFunction: async editor => {
                    await editor.execCommand('underline');
                    await editor.execCommand('italic');
                    await editor.execCommand('underline');
                },
                contentAfterEdit: `<p>ab${em(`[]\u200B`, 'first')}cd</p>`,
                contentAfter: `<p>ab[]cd</p>`,
            });
        });
        it('should get ready to write in italic, after changing one\'s mind about underline (two consecutive at the beginning)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab[]cd</p>`,
                stepFunction: async editor => {
                    await editor.execCommand('underline');
                    await editor.execCommand('underline');
                    await editor.execCommand('italic');
                },
                contentAfterEdit: `<p>ab${em(`[]\u200B`, 'first')}cd</p>`,
                contentAfter: `<p>ab[]cd</p>`,
            });
        });
        it('should get ready to write in italic without underline (underline was first)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab${u(em(`cd[]ef`))}</p>`,
                stepFunction: underline,
                contentAfterEdit: `<p>ab${u(em(`cd`))}${em(`[]\u200b`, 'last')}${u(em(`ef`))}</p>`,
                contentAfter: `<p>ab${u(em(`cd[]ef`))}</p>`,
            });
        });
        it('should restore underline after removing it (collapsed, italic)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab${u(em(`cd`))}${em(`[]\u200b`)}${u(em(`ef`))}</p>`,
                stepFunction: underline,
                contentAfterEdit: `<p>ab${u(em(`cd`))}${em(u(`[]\u200b`, 'last'))}${u(em(`ef`))}</p>`,
                contentAfter: `<p>ab${u(em(`cd`))}${em(`[]`)}${u(em(`ef`))}</p>`,
            });
        });
        it('should remove underline after restoring it after removing it (collapsed, italic)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab${u(em(`cd`))}${em(u(`[]\u200b`))}${u(em(`ef`))}</p>`,
                stepFunction: underline,
                contentAfterEdit: `<p>ab${u(em(`cd`))}${em(`[]\u200b`, 'last')}${u(em(`ef`))}</p>`,
                contentAfter: `<p>ab${u(em(`cd[]ef`))}</p>`,
            });
        });
        it('should remove underline after restoring it and writing after removing it (collapsed, italic)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab${u(em(`cd`))}${em(u(`ghi[]`))}${u(em(`ef`))}</p>`,
                stepFunction: underline,
                contentAfterEdit: `<p>ab${u(em(`cd`))}${em(u(`ghi`))}<em data-oe-zws-empty-inline="">[]\u200b</em>${u(em(`ef`))}</p>`,
                // The reason the cursor is after the tag <s> is because when the editor get's cleaned, the zws tag gets deleted.
                contentAfter: `<p>ab${u(em(`cd`))}${em(u(`ghi`))}[]${u(em(`ef`))}</p>`,
            });
        });
        it('should remove underline, write, restore underline, write, remove underline again, write (collapsed, italic)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>ab${u(em(`cd[]ef`))}</p>`,
                stepFunction: async editor => {
                    await editor.execCommand('underline');
                    await editor.execCommand('insert', 'A');
                    await editor.execCommand('underline');
                    await editor.execCommand('insert', 'B');
                    await editor.execCommand('underline');
                    await editor.execCommand('insert', 'C');
                },
                contentAfter: `<p>ab${u(em(`cd`))}${em(`A${u(`B`)}C[]`)}${u(em(`ef`))}</p>`,
            });
        });
    });

    describe('setFontSize', () => {
        it('should change the font size of a few characters', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>ab[cde]fg</p>',
                stepFunction: setFontSize('10px'),
                contentAfter: '<p>ab<span style="font-size: 10px;">[cde]</span>fg</p>',
            });
        });
        it('should change the font size the qweb tag', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<div><p t-esc="'Test'" contenteditable="false">[Test]</p></div>`,
                stepFunction: setFontSize('36px'),
                contentAfter: `<div><p t-esc="'Test'" contenteditable="false" style="font-size: 36px;">[Test]</p></div>`,
            });
        });
        it('should change the font size of a whole heading after a triple click', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>[ab</h1><p>]cd</p>',
                stepFunction: setFontSize('36px'),
                contentAfter: '<h1><span style="font-size: 36px;">[ab]</span></h1><p>cd</p>',
            });
        });
        it('should get ready to type with a different font size', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>ab[]cd</p>',
                stepFunction: setFontSize('36px'),
                contentAfterEdit: `<p>ab<span data-oe-zws-empty-inline="" style="font-size: 36px;">[]\u200B</span>cd</p>`,
                contentAfter: '<p>ab[]cd</p>',
            });
        });
        it('should change the font-size for a character in an inline that has a font-size', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>a<span style="font-size: 10px;">b[c]d</span>e</p>`,
                stepFunction: setFontSize('20px'),
                contentAfter:   unformat(`<p>
                                    a
                                    <span style="font-size: 10px;">b</span>
                                    <span style="font-size: 20px;">[c]</span>
                                    <span style="font-size: 10px;">d</span>
                                    e
                                </p>`),
            });
        });
        it('should change the font-size of a character with multiples inline ancestors having a font-size', async () => {
            await testEditor(BasicEditor, {
                contentBefore:   unformat(`<p>
                                    a
                                    <span style="font-size: 10px;">
                                        b
                                        <span style="font-size: 20px;">c[d]e</span>
                                        f
                                    </span>
                                    g
                                </p>`),
                stepFunction: setFontSize('30px'),
                contentAfter:   unformat(`<p>
                                    a
                                    <span style="font-size: 10px;">
                                        b
                                        <span style="font-size: 20px;">c</span>
                                    </span>
                                    <span style="font-size: 30px;">[d]</span>
                                    <span style="font-size: 10px;">
                                        <span style="font-size: 20px;">e</span>
                                        f
                                    </span>
                                    g
                                </p>`),
            });
        });
        it('should remove a redundant font-size', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p style="font-size: 10px">b<span style="font-size: 10px;">[c]</span>d</p>',
                stepFunction: setFontSize('10px'),
                contentAfter: '<p style="font-size: 10px">b[c]d</p>',
            });
        });
        it('should change the font-size to default', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>[ab]</p>',
                stepFunction: setFontSize(),
                contentAfter: '<p>[ab]</p>',
            });
        });
        it('should change the font-size to default removing the existing style with no empty span at the end', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p><span style="font-size: 36px;">[abc]</span></p>',
                stepFunction: setFontSize(),
                contentAfter: '<p>[abc]</p>',
            });
        });
        it('should not format non-editable text (setFontSize)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>a[b</p><p contenteditable="false">c</p><p>d]e</p>',
                stepFunction: setFontSize('10px'),
                contentAfter: unformat(`
                    <p>a<span style="font-size: 10px;">[b</span></p>
                    <p contenteditable="false">c</p>
                    <p><span style="font-size: 10px;">d]</span>e</p>
                `),
            });
        });
        it('should add font size in selected table cells', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<table><tbody><tr><td class="o_selected_td"><p>[<br></p></td><td class="o_selected_td"><p><br></p>]</td></tr><tr><td><p><br></p></td><td><p><br></p></td></tr></tbody></table>',
                stepFunction: setFontSize('48px'),
                contentAfter: '<table><tbody><tr><td><p><span style="font-size: 48px;">[]<br></span></p></td><td><p><span style="font-size: 48px;"><br></span></p></td></tr><tr><td><p><br></p></td><td><p><br></p></td></tr></tbody></table>',
            });
        });
        it('should add font size in all table cells', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<table><tbody><tr><td class="o_selected_td"><p>[<br></p></td><td class="o_selected_td"><p><br></p></td></tr><tr><td class="o_selected_td"><p><br></p></td><td class="o_selected_td"><p><br>]</p></td></tr></tbody></table>',
                stepFunction: setFontSize('36px'),
                contentAfter: '<table><tbody><tr><td><p><span style="font-size: 36px;">[]<br></span></p></td><td><p><span style="font-size: 36px;"><br></span></p></td></tr><tr><td><p><span style="font-size: 36px;"><br></span></p></td><td><p><span style="font-size: 36px;"><br></span></p></td></tr></tbody></table>',
            });
        });
        it('should add font size in selected table cells with h1 as first child', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<table><tbody><tr><td class="o_selected_td"><h1>[<br></h1></td><td class="o_selected_td"><h1><br>]</h1></td></tr><tr><td><h1><br></h1></td><td><h1><br></h1></td></tr></tbody></table>',
                stepFunction: setFontSize('18px'),
                contentAfter: '<table><tbody><tr><td><h1><span style="font-size: 18px;">[]<br></span></h1></td><td><h1><span style="font-size: 18px;"><br></span></h1></td></tr><tr><td><h1><br></h1></td><td><h1><br></h1></td></tr></tbody></table>',
            });
        });
        it('should apply font size in unbreakable span with class', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<h1><span class="oe_unbreakable">some [text]</span></h1>`,
                stepFunction: setFontSize('18px'),
                contentAfter: `<h1><span class="oe_unbreakable">some <span style="font-size: 18px;">[text]</span></span></h1>`,
            });
        });
        it('should apply font size in unbreakable span without class', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<h1><span t="unbreakable">some [text]</span></h1>`,
                stepFunction: setFontSize('18px'),
                contentAfter: `<h1><span t="unbreakable">some <span style="font-size: 18px;">[text]</span></span></h1>`,
            });
        });
        it('should apply font size on top of `u` and `s` tags', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>a<u>[b]</u>c</p>`,
                stepFunction: setFontSize('18px'),
                contentAfter: `<p>a<span style="font-size: 18px;"><u>[b]</u></span>c</p>`,
            });
        });
        it('should apply font size on topmost `u` or `s` tags if multiple applied', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>a<s><u>[b]</u></s>c</p>`,
                stepFunction: setFontSize('18px'),
                contentAfter: `<p>a<span style="font-size: 18px;"><s><u>[b]</u></s></span>c</p>`,
            });
        });
        it("should apply font size on top of `font` tag", async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p><font class="text-gradient" style="background-image: linear-gradient(135deg, rgb(214, 255, 127) 0%, rgb(0, 179, 204) 100%);">[abcdefg]</font></p>`,
                stepFunction: setFontSize("80px"),
                contentAfter: `<p><span style="font-size: 80px;"><font class="text-gradient" style="background-image: linear-gradient(135deg, rgb(214, 255, 127) 0%, rgb(0, 179, 204) 100%);">[abcdefg]</font></span></p>`,
            });
            await testEditor(BasicEditor, {
                contentBefore: `<p><font class="bg-o-color-1 text-black">[abcdefg]</font></p>`,
                stepFunction: setFontSize("72px"),
                contentAfter: `<p><span style="font-size: 72px;"><font class="bg-o-color-1 text-black">[abcdefg]</font></span></p>`,
            });
        });
    });

    describe('setFontSizeClassName', () => {
        it('should be able to change font-size class', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>a<span class="h1-fs">[bcd]</span>e</p>`,
                stepFunction: setFontSizeClassName("h2-fs"),
                contentAfter: `<p>a<span class="h2-fs">[bcd]</span>e</p>`,
            });
        });
    });

    it('should add style to a span parent of an inline', async () => {
        await testEditor(BasicEditor, {
            contentBefore: `<p>a<span style="background-color: black;">${strong(`[bc]`)}</span>d</p>`,
            stepFunction: setFontSize('10px'),
            contentAfter: `<p>a<span style="background-color: black; font-size: 10px;">${strong(`[bc]`)}</span>d</p>`,
        });
    });

    describe('isSelectionFormat', () => {
        it('return false for isSelectionFormat when partially selecting 2 text node, the anchor is formated and focus is not formated', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${strong(`a[b`)}</p><p>c]d</p>`,
                stepFunction: (editor) => {
                    window.chai.expect(isSelectionFormat(editor.editable, 'bold')).to.be.equal(false);
                },
            });
        });
        it('return false for isSelectionFormat when partially selecting 2 text node, the anchor is not formated and focus is formated', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>${strong(`a]b`)}</p><p>c[d</p>`,
                stepFunction: (editor) => {
                    window.chai.expect(isSelectionFormat(editor.editable, 'bold')).to.be.equal(false);
                },
            });
        });
        it('return false for isSelectionFormat when selecting 3 text node, the anchor and focus not formated and the text node in between formated', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>a[b</p><p>${strong(`c`)}</p><p>d]e</p>`,
                stepFunction: (editor) => {
                    window.chai.expect(isSelectionFormat(editor.editable, 'bold')).to.be.equal(false);
                },
            });
        });
        it('return true for isSelectionFormat selecting text nodes including invisible elements', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `[<p>${strong("a")}\ufeff<p>${strong("b")}</p></p>]`,
                stepFunction: async (editor) => {
                    window.chai.expect(isSelectionFormat(editor.editable, 'bold')).to.be.equal(true);
                },
            });
        });
    });
    describe('switchDirection', () => {
        it('should switch direction on a collapsed range', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>a[]b</p>`,
                stepFunction: switchDirection,
                contentAfter: `<p dir="rtl">a[]b</p>`,
            });
        });
        it('should switch direction on an uncollapsed range', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>a[b]c</p>`,
                stepFunction: switchDirection,
                contentAfter: `<p dir="rtl">a[b]c</p>`,
            });
        });
        it('should not switch direction of non-editable elements', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>[before</p><p contenteditable="false">noneditable</p><p>after]</p>`,
                stepFunction: switchDirection,
                contentAfter: `<p dir="rtl">[before</p><p contenteditable="false">noneditable</p><p dir="rtl">after]</p>`,
            });
        });
    });
    describe('removeFormat', () => {
        it('should remove the background image when clear the format', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<div><p><font class="text-gradient" style="background-image: linear-gradient(135deg, rgb(255, 204, 51) 0%, rgb(226, 51, 255) 100%);">[ab]</font></p></div>',
                stepFunction: editor => editor.execCommand('removeFormat'),
                contentAfter: '<div><p>[ab]</p></div>',
            });
        });
        it('should remove all the colors for the text separated by Shift+Enter when using removeFormat button', async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<div><h1><font style="color: rgb(255, 0, 0);">[abc</font><br><font style="color: rgb(255, 0, 0);">abc</font><br><font style="color: rgb(255, 0, 0);">abc</font><br><font style="color: rgb(255, 0, 0);">abc]</font></h1></div>`,
                stepFunction: editor => editor.execCommand('removeFormat'),
                contentAfter: `<div><h1>[abc<br>abc<br>abc<br>abc]</h1></div>`

            });
            await testEditor(BasicEditor, {
                contentBefore: `<div><h1><font style="background-color: rgb(255, 0, 0);">[abc</font><br><font style="background-color: rgb(255, 0, 0);">abc</font><br><font style="background-color: rgb(255, 0, 0);">abc]</font></h1></div>`,
                stepFunction: editor => editor.execCommand('removeFormat'),
                contentAfter: `<div><h1>[abc<br>abc<br>abc]</h1></div>`

            });
        })
        it('should remove all the colors for the text separated by Enter when using removeFormat button' , async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<div><h1><font style="background-color: rgb(255, 0, 0);">[abc</font></h1><h1><font style="background-color: rgb(255, 0, 0);">abc</font></h1><h1><font style="background-color: rgb(255, 0, 0);">abc]</font></h1></div>`,
                stepFunction: editor => editor.execCommand('removeFormat'),
                contentAfter: `<div><h1>[abc</h1><h1>abc</h1><h1>abc]</h1></div>`

            });
            await testEditor(BasicEditor, {
                contentBefore: `<div><h1><font style="color: rgb(255, 0, 0);">[abc</font></h1><h1><font style="color: rgb(255, 0, 0);">abc</font></h1><h1><font style="color: rgb(255, 0, 0);">abc]</font></h1></div>`,
                stepFunction: editor => editor.execCommand('removeFormat'),
                contentAfter: `<div><h1>[abc</h1><h1>abc</h1><h1>abc]</h1></div>`

            });
        });
        it("should remove font size classes and gradient color styles", async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p><span class="display-1-fs"><font class="text-gradient" style="background-image: linear-gradient(135deg, rgb(214, 255, 127) 0%, rgb(0, 179, 204) 100%);">[abcdefg]</font></span></p>`,
                stepFunction: (editor) => editor.execCommand("removeFormat"),
                contentAfter: `<p>[abcdefg]</p>`,
            });
            await testEditor(BasicEditor, {
                contentBefore: `<p><span class="display-2-fs"><font style="background-image: linear-gradient(135deg, rgb(214, 255, 127) 0%, rgb(0, 179, 204) 100%);">[abcdefg]</font></span></p>`,
                stepFunction: (editor) => editor.execCommand("removeFormat"),
                contentAfter: `<p>[abcdefg]</p>`,
            });
        });
        it('should remove font-size classes when clearing the format' , async () => {
            await testEditor(BasicEditor, {
                contentBefore: `<p>123<span class="h1-fs">[abc]</span>456</p>`,
                stepFunction: editor => editor.execCommand('removeFormat'),
                contentAfter: `<p>123[abc]456</p>`
            });
            await testEditor(BasicEditor, {
                contentBefore: `<p>[a<span class="h1-fs">bc</span>d<span class="h2-fs">ef</span>g]</p>`,
                stepFunction: editor => editor.execCommand('removeFormat'),
                contentAfter: `<p>[abcdefg]</p>`
            });
            await testEditor(BasicEditor, {
                contentBefore: `<p>[a<span class="h1-fs">bc</span>d</p><p>e<span class="o_small-fs">fg</span>h]</p>`,
                stepFunction: editor => editor.execCommand('removeFormat'),
                contentAfter: `<p>[abcd</p><p>efgh]</p>`
            });
        });
    });
    describe('zws', () => {
        it('should insert a span zws when toggling a formatting command twice', () => {
            return testEditor(BasicEditor, {
                contentBefore: `<p>[]<br></p>`,
                stepFunction: async editor => {
                    await editor.execCommand('bold');
                    await editor.execCommand('bold');
                },
                // todo: It would be better to remove the zws entirely so that
                // the P could have the "/" hint but that behavior might be
                // complex with the current implementation.
                contentAfterEdit: `<p>${span(`[]\u200B`, 'first')}</p>`,
            });
        });
    });
});

describe('setTagName', () => {
    describe('to paragraph', () => {
        it('should turn a heading 1 into a paragraph', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>ab[]cd</h1>',
                stepFunction: editor => editor.execCommand('setTag', 'p'),
                contentAfter: '<p>ab[]cd</p>',
            });
        });
        it('should turn a heading 1 into a paragraph (character selected)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>a[b]c</h1>',
                stepFunction: editor => editor.execCommand('setTag', 'p'),
                contentAfter: '<p>a[b]c</p>',
            });
        });
        it('should turn a heading 1, a paragraph and a heading 2 into three paragraphs', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>a[b</h1><p>cd</p><h2>e]f</h2>',
                stepFunction: editor => editor.execCommand('setTag', 'p'),
                contentAfter: '<p>a[b</p><p>cd</p><p>e]f</p>',
            });
        });
        it.skip('should turn a heading 1 into a paragraph after a triple click', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>[ab</h1><h2>]cd</h2>',
                stepFunction: editor => editor.execCommand('setTag', 'p'),
                contentAfter: '<p>[ab</p><h2>]cd</h2>',
            });
        });
        it('should not turn a div into a paragraph', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<div>[ab]</div>',
                stepFunction: editor => editor.execCommand('setTag', 'p'),
                contentAfter: '<div><p>[ab]</p></div>',
            });
        });
        it('should not add paragraph tag when selection is changed to normal in list', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<ul><li><h1>[abcd]</h1></li></ul>',
                stepFunction: editor => editor.execCommand('setTag', "p"),
                contentAfter: `<ul><li>[abcd]</li></ul>`
            });
        });
        it('should not add paragraph tag to normal text in list', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<ul><li>[abcd]</li></ul>',
                stepFunction: editor => editor.execCommand('setTag', "p"),
                contentAfter: `<ul><li>[abcd]</li></ul>`
            });
        });
        it('should turn three table cells with heading 1 to table cells with paragraph', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<table><tbody><tr><td><h1>[a</h1></td><td><h1>b</h1></td><td><h1>c]</h1></td></tr></tbody></table>',
                stepFunction: editor => editor.execCommand('setTag', 'p'),
                // The custom table selection is removed in cleanForSave and the selection is collapsed.
                contentAfter: '<table><tbody><tr><td><p>[]a</p></td><td><p>b</p></td><td><p>c</p></td></tr></tbody></table>',
            });
        });
        it('should not set the tag of non-editable elements', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>[before</h1><h1 contenteditable="false">noneditable</h1><h1>after]</h1>',
                stepFunction: editor => editor.execCommand('setTag', 'p'),
                contentAfter: '<p>[before</p><h1 contenteditable="false">noneditable</h1><p>after]</p>',
            });
        });
    });
    describe('to heading 1', () => {
        it('should turn a paragraph into a heading 1', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>ab[]cd</p>',
                stepFunction: editor => editor.execCommand('setTag', 'h1'),
                contentAfter: '<h1>ab[]cd</h1>',
            });
        });
        it('should turn a paragraph into a heading 1 (character selected)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>a[b]c</p>',
                stepFunction: editor => editor.execCommand('setTag', 'h1'),
                contentAfter: '<h1>a[b]c</h1>',
            });
        });
        it('should turn a paragraph, a heading 1 and a heading 2 into three headings 1', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>a[b</p><h1>cd</h1><h2>e]f</h2>',
                stepFunction: editor => editor.execCommand('setTag', 'h1'),
                contentAfter: '<h1>a[b</h1><h1>cd</h1><h1>e]f</h1>',
            });
        });
        it.skip('should turn a paragraph into a heading 1 after a triple click', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>[ab</p><h2>]cd</h2>',
                stepFunction: editor => editor.execCommand('setTag', 'h1'),
                contentAfter: '<h1>[ab</h1><h2>]cd</h2>',
            });
        });
        it('should not turn a div into a heading 1', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<div>[ab]</div>',
                stepFunction: editor => editor.execCommand('setTag', 'h1'),
                contentAfter: '<div><h1>[ab]</h1></div>',
            });
        });
        it('should turn three table cells with paragraph to table cells with heading 1', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<table><tbody><tr><td><p>[a</p></td><td><p>b</p></td><td><p>c]</p></td></tr></tbody></table>',
                stepFunction: editor => editor.execCommand('setTag', 'h1'),
                // The custom table selection is removed in cleanForSave and the selection is collapsed.
                contentAfter: '<table><tbody><tr><td><h1>[]a</h1></td><td><h1>b</h1></td><td><h1>c</h1></td></tr></tbody></table>',
            });
        });
        it('should not transfer attributes of list to heading 1', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<ul><li class="nav-item">[abcd]</li></ul>',
                stepFunction: editor => editor.execCommand('setTag', 'h1'),
                contentAfter: '<ul><li class="nav-item"><h1>[abcd]</h1></li></ul>',
            });
        });
    });
    describe('to heading 2', () => {
        it('should turn a heading 1 into a heading 2', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>ab[]cd</h1>',
                stepFunction: editor => editor.execCommand('setTag', 'h2'),
                contentAfter: '<h2>ab[]cd</h2>',
            });
        });
        it('should turn a heading 1 into a heading 2 (character selected)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>a[b]c</h1>',
                stepFunction: editor => editor.execCommand('setTag', 'h2'),
                contentAfter: '<h2>a[b]c</h2>',
            });
        });
        it('should turn a heading 1, a heading 2 and a paragraph into three headings 2', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>a[b</h1><h2>cd</h2><p>e]f</p>',
                stepFunction: editor => editor.execCommand('setTag', 'h2'),
                contentAfter: '<h2>a[b</h2><h2>cd</h2><h2>e]f</h2>',
            });
        });
        it.skip('should turn a paragraph into a heading 2 after a triple click', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>[ab</p><h1>]cd</h1>',
                stepFunction: editor => editor.execCommand('setTag', 'h2'),
                contentAfter: '<h2>[ab</h2><h1>]cd</h1>',
            });
        });
        it('should not turn a div into a heading 2', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<div>[ab]</div>',
                stepFunction: editor => editor.execCommand('setTag', 'h2'),
                contentAfter: '<div><h2>[ab]</h2></div>',
            });
        });
        it('should turn three table cells with paragraph to table cells with heading 2', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<table><tbody><tr><td><p>[a</p></td><td><p>b</p></td><td><p>c]</p></td></tr></tbody></table>',
                stepFunction: editor => editor.execCommand('setTag', 'h2'),
                // The custom table selection is removed in cleanForSave and the selection is collapsed.
                contentAfter: '<table><tbody><tr><td><h2>[]a</h2></td><td><h2>b</h2></td><td><h2>c</h2></td></tr></tbody></table>',
            });
        });
        it('should not transfer attributes of list to heading 2', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<ul><li class="nav-item">[abcd]</li></ul>',
                stepFunction: editor => editor.execCommand('setTag', 'h2'),
                contentAfter: '<ul><li class="nav-item"><h2>[abcd]</h2></li></ul>',
            });
        });
    });
    describe('to heading 3', () => {
        it('should turn a heading 1 into a heading 3', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>ab[]cd</h1>',
                stepFunction: editor => editor.execCommand('setTag', 'h3'),
                contentAfter: '<h3>ab[]cd</h3>',
            });
        });
        it('should turn a heading 1 into a heading 3 (character selected)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>a[b]c</h1>',
                stepFunction: editor => editor.execCommand('setTag', 'h3'),
                contentAfter: '<h3>a[b]c</h3>',
            });
        });
        it('should turn a heading 1, a paragraph and a heading 2 into three headings 3', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>a[b</h1><p>cd</p><h2>e]f</h2>',
                stepFunction: editor => editor.execCommand('setTag', 'h3'),
                contentAfter: '<h3>a[b</h3><h3>cd</h3><h3>e]f</h3>',
            });
        });
        it.skip('should turn a paragraph into a heading 3 after a triple click', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>[ab</p><h1>]cd</h1>',
                stepFunction: editor => editor.execCommand('setTag', 'h3'),
                contentAfter: '<h3>[ab</h3><h1>]cd</h1>',
            });
        });
        it('should not turn a div into a heading 3', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<div>[ab]</div>',
                stepFunction: editor => editor.execCommand('setTag', 'h3'),
                contentAfter: '<div><h3>[ab]</h3></div>',
            });
        });
        it('should turn three table cells with paragraph to table cells with heading 3', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<table><tbody><tr><td><p>[a</p></td><td><p>b</p></td><td><p>c]</p></td></tr></tbody></table>',
                stepFunction: editor => editor.execCommand('setTag', 'h3'),
                // The custom table selection is removed in cleanForSave and the selection is collapsed.
                contentAfter: '<table><tbody><tr><td><h3>[]a</h3></td><td><h3>b</h3></td><td><h3>c</h3></td></tr></tbody></table>',
            });
        });
        it('should not transfer attributes of list to heading 3', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<ul><li class="nav-item">[abcd]</li></ul>',
                stepFunction: editor => editor.execCommand('setTag', 'h3'),
                contentAfter: '<ul><li class="nav-item"><h3>[abcd]</h3></li></ul>',
            });
        });
    });
    describe('to pre', () => {
        it('should turn a heading 1 into a pre', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>ab[]cd</h1>',
                stepFunction: editor => editor.execCommand('setTag', 'pre'),
                contentAfter: '<pre>ab[]cd</pre>',
            });
        });
        it('should turn a heading 1 into a pre (character selected)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>a[b]c</h1>',
                stepFunction: editor => editor.execCommand('setTag', 'pre'),
                contentAfter: '<pre>a[b]c</pre>',
            });
        });
        it('should turn a heading 1 a pre and a paragraph into three pres', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>a[b</h1><pre>cd</pre><p>e]f</p>',
                stepFunction: editor => editor.execCommand('setTag', 'pre'),
                contentAfter: '<pre>a[b</pre><pre>cd</pre><pre>e]f</pre>',
            });
        });
        it('should turn three table cells with paragraph to table cells with pre', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<table><tbody><tr><td><p>[a</p></td><td><p>b</p></td><td><p>c]</p></td></tr></tbody></table>',
                stepFunction: editor => editor.execCommand('setTag', 'pre'),
                // The custom table selection is removed in cleanForSave and the selection is collapsed.
                contentAfter: '<table><tbody><tr><td><pre>[]a</pre></td><td><pre>b</pre></td><td><pre>c</pre></td></tr></tbody></table>',
            });
        });
        it('should turn a paragraph into pre preserving the cursor position', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<p>abcd<br>[]<br></p>',
                stepFunction: editor => editor.execCommand('setTag', 'pre'),
                contentAfter: '<pre>abcd<br>[]<br></pre>',
            });
        });
        it('should not transfer attributes of list to pre', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<ul><li class="nav-item" id="test">[abcd]</li></ul>',
                stepFunction: editor => editor.execCommand('setTag', 'pre'),
                contentAfter: '<ul><li class="nav-item" id="test"><pre>[abcd]</pre></li></ul>',
            });
        });
    });
    describe('to blockquote', () => {
        it('should turn a blockquote into a paragraph', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>ab[]cd</h1>',
                stepFunction: editor => editor.execCommand('setTag', 'blockquote'),
                contentAfter: '<blockquote>ab[]cd</blockquote>',
            });
        });
        it('should turn a heading 1 into a blockquote (character selected)', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>a[b]c</h1>',
                stepFunction: editor => editor.execCommand('setTag', 'blockquote'),
                contentAfter: '<blockquote>a[b]c</blockquote>',
            });
        });
        it('should turn a heading 1, a paragraph and a heading 2 into three blockquote', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>a[b</h1><p>cd</p><h2>e]f</h2>',
                stepFunction: editor => editor.execCommand('setTag', 'blockquote'),
                contentAfter:
                    '<blockquote>a[b</blockquote><blockquote>cd</blockquote><blockquote>e]f</blockquote>',
            });
        });
        it.skip('should turn a heading 1 into a blockquote after a triple click', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<h1>[ab</h1><h2>]cd</h2>',
                stepFunction: editor => editor.execCommand('setTag', 'blockquote'),
                contentAfter: '<blockquote>[ab</blockquote><h2>]cd</h2>',
            });
        });
        it('should not turn a div into a blockquote', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<div>[ab]</div>',
                stepFunction: editor => editor.execCommand('setTag', 'blockquote'),
                contentAfter: '<div><blockquote>[ab]</blockquote></div>',
            });
        });
        it('should turn three table cells with paragraph to table cells with blockquote', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<table><tbody><tr><td><p>[a</p></td><td><p>b</p></td><td><p>c]</p></td></tr></tbody></table>',
                stepFunction: editor => editor.execCommand('setTag', 'blockquote'),
                // The custom table selection is removed in cleanForSave and the selection is collapsed.
                contentAfter: '<table><tbody><tr><td><blockquote>[]a</blockquote></td><td><blockquote>b</blockquote></td><td><blockquote>c</blockquote></td></tr></tbody></table>',
            });
        });
        it('should not transfer attributes of list to blockquote', async () => {
            await testEditor(BasicEditor, {
                contentBefore: '<ul><li class="nav-item" style="color: red;">[abcd]</li></ul>',
                stepFunction: editor => editor.execCommand('setTag', 'blockquote'),
                contentAfter: '<ul><li class="nav-item" style="color: red;"><blockquote>[abcd]</blockquote></li></ul>',
            });
        });
    });
});
