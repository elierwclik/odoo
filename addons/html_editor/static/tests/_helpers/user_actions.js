import { findInSelection } from "@html_editor/utils/selection";
import { click, manuallyDispatchProgrammaticEvent, press, tick, waitFor } from "@odoo/hoot-dom";
import { setSelection } from "./selection";
import { execCommand } from "./userCommands";
import { isMobileOS } from "@web/core/browser/feature_detection";
import { isTextNode } from "@html_editor/utils/dom_info";

/** @typedef {import("@html_editor/plugin").Editor} Editor */

/**
 * @param {Editor} editor
 * @param {string} text
 */
export async function insertText(editor, text) {
    const insertChar = (char) => {
        // Create and dispatch events to mock text insertion. Unfortunatly, the
        // events will be flagged `isTrusted: false` by the browser, requiring
        // the editor to detect them since they would not trigger the default
        // browser behavior otherwise.
        const range = editor.document.getSelection().getRangeAt(0);
        let offset = range.startOffset;
        let node = range.startContainer;

        if (node.nodeType !== Node.TEXT_NODE) {
            node = document.createTextNode(char);
            offset = 1;
            range.startContainer.appendChild(node);
            range.insertNode(node);
            setSelection({ anchorNode: node, anchorOffset: offset });
        } else {
            node.textContent =
                node.textContent.slice(0, offset) + char + node.textContent.slice(offset);
            offset++;
            setSelection({
                anchorNode: node,
                anchorOffset: offset,
            });
        }
    };
    for (const char of text) {
        // KeyDownEvent is required to trigger deleteRange.
        const [keydownEvent] = await manuallyDispatchProgrammaticEvent.silent(
            editor.editable,
            "keydown",
            { key: char }
        );
        if (keydownEvent.defaultPrevented) {
            continue;
        }
        // InputEvent is required to simulate the insert text.
        const [beforeinputEvent] = await manuallyDispatchProgrammaticEvent.silent(
            editor.editable,
            "beforeinput",
            { inputType: "insertText", data: char }
        );
        if (beforeinputEvent.defaultPrevented) {
            continue;
        }
        insertChar(char);
        const [inputEvent] = await manuallyDispatchProgrammaticEvent.silent(
            editor.editable,
            "input",
            { inputType: "insertText", data: char }
        );
        if (inputEvent.defaultPrevented) {
            continue;
        }
        // KeyUpEvent is not required but is triggered like the browser would.
        await manuallyDispatchProgrammaticEvent.as("insertChar")(editor.editable, "keyup", {
            key: char,
        });
    }
}

/** @param {Editor} editor */
export function deleteForward(editor) {
    execCommand(editor, "deleteForward");
}

/**
 * @param {Editor} editor
 * @param {boolean} [isMobileTest=false]
 */
export function deleteBackward(editor, isMobileTest = false) {
    // TODO phoenix: find a strategy for test mobile and desktop. (check legacy code)

    execCommand(editor, "deleteBackward");
}

// history
/** @param {Editor} editor */
export function addStep(editor) {
    editor.shared.history.addStep();
}
/** @param {Editor} editor */
export function undo(editor) {
    execCommand(editor, "historyUndo");
}
/** @param {Editor} editor */
export function redo(editor) {
    execCommand(editor, "historyRedo");
}

// list
export function toggleOrderedList(editor) {
    execCommand(editor, "toggleListOL");
}
/** @param {Editor} editor */
export function toggleUnorderedList(editor) {
    execCommand(editor, "toggleListUL");
}
/** @param {Editor} editor */
export function toggleCheckList(editor) {
    execCommand(editor, "toggleListCL");
}

/**
 * Clicks on the checkbox of a checklist item.
 *
 * @param {HTMLLIElement} li
 * @throws {Error} If the provided element is not a LI element within a checklist.
 */
export async function clickCheckbox(li) {
    if (li.tagName !== "LI" || !li.parentNode.classList.contains("o_checklist")) {
        throw new Error("Expected a LI element in a checklist");
    }
    await click(li, {
        position: { x: -10, y: 10 },
        relative: true,
    });
}

/** @param {Editor} editor */
export function insertLineBreak(editor) {
    editor.shared.lineBreak.insertLineBreak();
}

// Format commands

/** @param {Editor} editor */
export function bold(editor) {
    execCommand(editor, "formatBold");
}
/** @param {Editor} editor */
export function italic(editor) {
    execCommand(editor, "formatItalic");
}
/** @param {Editor} editor */
export function underline(editor) {
    execCommand(editor, "formatUnderline");
}
/** @param {Editor} editor */
export function strikeThrough(editor) {
    execCommand(editor, "formatStrikethrough");
}
export function setFontSize(size) {
    return (editor) => execCommand(editor, "formatFontSize", { size });
}
export function setFontSizeClassName(className) {
    return (editor) => execCommand(editor, "formatFontSizeClassName", { className });
}
export function setFontFamily(fontFamily) {
    return (editor) => {
        editor.shared.format.formatSelection("fontFamily", {
            applyStyle: fontFamily !== false,
            formatProps: {
                name: fontFamily + "_name",
                nameShort: fontFamily + "_nameShort",
                fontFamily: fontFamily,
            },
        });
    };
}
/** @param {Editor} editor */
export function switchDirection(editor) {
    return execCommand(editor, "switchDirection");
}
/** @param {Editor} editor */
export function splitBlock(editor) {
    editor.shared.split.splitBlock();
    editor.shared.history.addStep();
}

export async function simulateArrowKeyPress(editor, keys) {
    await press(keys);
    const keysArray = Array.isArray(keys) ? keys : [keys];
    const alter = keysArray.includes("Shift") ? "extend" : "move";
    const direction =
        keysArray.includes("ArrowLeft") || keysArray.includes("ArrowUp") ? "left" : "right";
    const granularity =
        keysArray.includes("ArrowUp") || keysArray.includes("ArrowDown") ? "line" : "character";
    const selection = editor.document.getSelection();
    selection.modify(alter, direction, granularity);
}

export function unlinkByCommand(editor) {
    execCommand(editor, "removeLinkFromSelection");
}

export async function unlinkFromToolbar() {
    await waitFor(".o-we-toolbar");
    await click(".btn[name='unlink']");
}

export async function unlinkFromPopover() {
    await waitFor(".o-we-linkpopover");
    await click(".o_we_remove_link");
}

/** @param {Editor} editor */
export async function keydownTab(editor) {
    await manuallyDispatchProgrammaticEvent.as("keydownTab")(editor.editable, "keydown", {
        key: "Tab",
    });
}
/** @param {Editor} editor */
export async function keydownShiftTab(editor) {
    await manuallyDispatchProgrammaticEvent.as("keydownShiftTab")(editor.editable, "keydown", {
        key: "Tab",
        shiftKey: true,
    });
}
/** @param {Editor} editor */
export function resetSize(editor) {
    const selection = editor.shared.selection.getEditableSelection();
    editor.shared.table.resetTableSize(findInSelection(selection, "table"));
}
/** @param {Editor} editor */
export function alignLeft(editor) {
    execCommand(editor, "alignLeft");
}
/** @param {Editor} editor */
export function alignCenter(editor) {
    execCommand(editor, "alignCenter");
}
/** @param {Editor} editor */
export function alignRight(editor) {
    execCommand(editor, "alignRight");
}
/** @param {Editor} editor */
export function justify(editor) {
    execCommand(editor, "justify");
}
/** @param {Editor} editor */
export function alignTop(editor) {
    execCommand(editor, "alignTop");
}
/** @param {Editor} editor */
export function alignMiddle(editor) {
    execCommand(editor, "alignMiddle");
}
/** @param {Editor} editor */
export function alignBottom(editor) {
    execCommand(editor, "alignBottom");
}

/**
 * @param {string} color
 * @param {string} mode
 */
export function setColor(color, mode) {
    /** @param {Editor} editor */
    return (editor) => {
        execCommand(editor, "applyColor", { color, mode });
    };
}

// Mock an paste event and send it to the editor.

/**
 * @param {Editor} editor
 * @param {string} text
 * @param {string} type
 */
function pasteData(editor, text, type) {
    const clipboardData = new DataTransfer();
    clipboardData.setData(type, text);
    const pasteEvent = new ClipboardEvent("paste", { clipboardData, bubbles: true });
    editor.editable.dispatchEvent(pasteEvent);
}
/**
 * @param {Editor} editor
 * @param {string} text
 */
export function pasteText(editor, text) {
    return pasteData(editor, text, "text/plain");
}
/**
 * @param {Editor} editor
 * @param {string} html
 */
export function pasteHtml(editor, html) {
    return pasteData(editor, html, "text/html");
}
/**
 * @param {Editor} editor
 * @param {string} html
 */
export function pasteOdooEditorHtml(editor, html) {
    return pasteData(editor, html, "application/vnd.odoo.odoo-editor");
}
/**
 * For desktop use only.
 *
 * @param {Node} node
 */
export async function tripleClick(node) {
    if (isMobileOS()) {
        throw new Error("This function can only be used for desktop tests.");
    }
    const element = isTextNode(node) ? node.parentElement : node;
    const selection = element.ownerDocument.getSelection();
    // First click
    await click(element);
    setSelection({ anchorNode: element, anchorOffset: 0 });
    await tick();

    // Second click of a double click
    await click(element);
    selection.modify("extend", "forward", "word");
    await tick();

    // Third click of a triple click
    const eventList = await click(element);
    const mouseDownEvent = eventList.find((event) => event.type === "mousedown");
    if (!mouseDownEvent) {
        throw new Error("Triple click requires a mousedown event.");
    }
    if (mouseDownEvent.defaultPrevented) {
        // Default prevented, no effects on selection to simulate.
        return;
    }
    await tick();
}
