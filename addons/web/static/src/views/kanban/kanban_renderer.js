import { Component, onPatched, onWillDestroy, useEffect, useRef, useState } from "@odoo/owl";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { _t } from "@web/core/l10n/translation";
import { evaluateExpr } from "@web/core/py_js/py";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { useSortable } from "@web/core/utils/sortable_owl";
import { MOVABLE_RECORD_TYPES } from "@web/model/relational_model/dynamic_group_list";
import { isNull } from "@web/views/utils";
import { ColumnProgress } from "@web/views/view_components/column_progress";
import { useBounceButton } from "@web/views/view_hook";
import { KanbanColumnExamplesDialog } from "./kanban_column_examples_dialog";
import { KanbanColumnQuickCreate } from "./kanban_column_quick_create";
import { KanbanHeader } from "./kanban_header";
import { KanbanRecord } from "./kanban_record";
import { KanbanRecordQuickCreate } from "./kanban_record_quick_create";
import { Widget } from "@web/views/widgets/widget";
import { ActionHelper } from "@web/views/action_helper";

const DRAGGABLE_GROUP_TYPES = ["many2one"];

function validateColumnQuickCreateExamples(data) {
    const { allowedGroupBys = [], examples = [], foldField = "" } = data;
    if (!allowedGroupBys.length) {
        throw new Error("The example data must contain an array of allowed groupbys");
    }
    if (!examples.length) {
        throw new Error("The example data must contain an array of examples");
    }
    const someHasFoldedColumns = examples.some(({ foldedColumns = [] }) => foldedColumns.length);
    if (!foldField && someHasFoldedColumns) {
        throw new Error("The example data must contain a fold field if there are folded columns");
    }
}

export class KanbanRenderer extends Component {
    static template = "web.KanbanRenderer";
    static components = {
        Dropdown,
        DropdownItem,
        ColumnProgress,
        KanbanColumnQuickCreate,
        KanbanHeader,
        KanbanRecord,
        KanbanRecordQuickCreate,
        Widget,
        ActionHelper,
    };
    static props = [
        "archInfo",
        "Compiler",
        "list",
        "deleteRecord",
        "openRecord",
        "readonly?",
        "forceGlobalClick?",
        "noContentHelp?",
        "scrollTop?",
        "canQuickCreate?",
        "quickCreateState?",
        "progressBarState?",
        "addLabel?",
        "onAdd?",
    ];

    static defaultProps = {
        scrollTop: () => {},
        quickCreateState: { groupId: false },
        tooltipInfo: {},
    };

    setup() {
        this.dialogClose = [];
        /**
         * @type {{ processedIds: string[], columnQuickCreateIsFolded: boolean }}
         */
        this.state = useState({
            selectionAvailable: false,
            processedIds: [],
            columnQuickCreateIsFolded:
                !this.props.list.isGrouped || this.props.list.groups.length > 0,
        });
        this.dialog = useService("dialog");
        this.exampleData = registry
            .category("kanban_examples")
            .get(this.props.archInfo.examples, null);
        if (this.exampleData) {
            validateColumnQuickCreateExamples(this.exampleData);
        }
        this.lastCheckedRecord = null;

        // Sortable
        let dataRecordId;
        let dataGroupId;
        this.rootRef = useRef("root");
        if (this.canUseSortable) {
            useSortable({
                enable: () => this.canResequenceRecords,
                // Params
                ref: this.rootRef,
                elements: ".o_draggable",
                ignore: ".dropdown,select",
                groups: () => this.props.list.isGrouped && ".o_kanban_group",
                connectGroups: () => this.canMoveRecords,
                cursor: "move",
                placeholderClasses: ["visible", "opacity-50", "my-2"],
                // Hooks
                onDragStart: (params) => {
                    const { element, group } = params;
                    dataRecordId = element.dataset.id;
                    dataGroupId = group && group.dataset.id;
                    if (this.props.list.selection?.length) {
                        this.props.list.selection.forEach((record) => {
                            record.toggleSelection(false);
                        });
                    }
                    return this.sortStart(params);
                },
                onDragEnd: (params) => this.sortStop(params),
                onGroupEnter: (params) => this.sortRecordGroupEnter(params),
                onGroupLeave: (params) => this.sortRecordGroupLeave(params),
                onDrop: (params) => this.sortRecordDrop(dataRecordId, dataGroupId, params),
            });
            useSortable({
                enable: () => this.canResequenceGroups,
                // Params
                ref: this.rootRef,
                elements: ".o_group_draggable",
                handle: ".o_column_title",
                cursor: "move",
                // Hooks
                onDragStart: (params) => {
                    const { element } = params;
                    dataGroupId = element.dataset.id;
                    return this.sortStart(params);
                },
                onDragEnd: (params) => this.sortStop(params),
                onDrop: (params) => this.sortGroupDrop(dataGroupId, params),
            });
        }

        useBounceButton(this.rootRef, (clickedEl) => {
            if (
                this.props.list.isGrouped
                    ? !this.props.list.recordCount
                    : !this.props.list.count || this.props.list.model.useSampleModel
            ) {
                return clickedEl.matches(
                    [
                        ".o_kanban_renderer",
                        ".o_kanban_group",
                        ".o_kanban_header",
                        ".o_column_quick_create",
                        ".o_view_nocontent_smiling_face",
                    ].join(", ")
                );
            }
            return false;
        });
        onWillDestroy(() => {
            this.dialogClose.forEach((close) => close());
        });

        if (this.env.searchModel) {
            useBus(this.env.searchModel, "focus-view", () => {
                const { model } = this.props.list;
                if (model.useSampleModel || !model.hasData()) {
                    return;
                }
                const firstCard = this.rootRef.el.querySelector(".o_kanban_record");
                if (firstCard) {
                    // Focus first kanban card
                    firstCard.focus();
                }
            });
        }

        useHotkey(
            "Enter",
            ({ target }) => {
                if (target.closest(".o_kanban_selection_active") !== null) {
                    return;
                }

                if (!target.classList.contains("o_kanban_record")) {
                    return;
                }

                if (this.props.archInfo.canOpenRecords) {
                    target.click();
                    return;
                }

                // Open first link
                const firstLink = target.querySelector("a, button");
                if (firstLink) {
                    firstLink.click();
                }
            },
            { area: () => this.rootRef.el }
        );

        useHotkey("space", ({ target }) => this.onSpaceKeyPress(target), {
            area: () => this.rootRef.el,
        });

        useHotkey("shift+space", ({ target }) => this.onSpaceKeyPress(target, true), {
            area: () => this.rootRef.el,
        });

        const arrowsOptions = { area: () => this.rootRef.el, allowRepeat: true };
        if (this.env.searchModel) {
            useHotkey(
                "ArrowUp",
                ({ area }) => {
                    if (!this.focusNextCard(area, "up")) {
                        this.env.searchModel.trigger("focus-search");
                    }
                },
                arrowsOptions
            );
        }
        useHotkey("ArrowDown", ({ area }) => this.focusNextCard(area, "down"), arrowsOptions);
        useHotkey("ArrowLeft", ({ area }) => this.focusNextCard(area, "left"), arrowsOptions);
        useHotkey("ArrowRight", ({ area }) => this.focusNextCard(area, "right"), arrowsOptions);
        const handleAltKeyDown = (ev) => {
            if (ev.key === "Alt") {
                this.state.selectionAvailable = true;
            }
        };
        const handleAltKeyUp = () => {
            this.state.selectionAvailable = false;
        };
        useEffect(
            () => {
                window.addEventListener("keydown", handleAltKeyDown);
                window.addEventListener("keyup", handleAltKeyUp);
                window.addEventListener("blur", handleAltKeyUp);
                return () => {
                    window.removeEventListener("keydown", handleAltKeyDown);
                    window.removeEventListener("keyup", handleAltKeyUp);
                    window.removeEventListener("blur", handleAltKeyUp);
                };
            },
            () => []
        );

        // After a group is unfolded through onGroupClick, we want to scroll towards
        // the next group if it exists and is folded, and to the unfolded group
        // itself otherwise
        onPatched(() => {
            if (this.lastOpenedGroupId) {
                const groups = this.getGroupsOrRecords();
                const lastOpenedGroupIndex = groups.findIndex(
                    (g) => g.group.id === this.lastOpenedGroupId
                );
                let groupIdToFocus = this.lastOpenedGroupId;
                if (
                    lastOpenedGroupIndex < groups.length - 1 &&
                    groups[lastOpenedGroupIndex + 1].group.isFolded
                ) {
                    groupIdToFocus = groups[lastOpenedGroupIndex + 1].group.id;
                }
                const groupEl = this.rootRef.el.querySelector(
                    `.o_kanban_group[data-id="${groupIdToFocus}"]`
                );
                const rect = groupEl.getBoundingClientRect();
                // Don't scroll if the group to focus is completely inside of the viewport
                if (rect.x + rect.width > window.innerWidth) {
                    groupEl.scrollIntoView({ behavior: "smooth", inline: "end" });
                }
                delete this.lastOpenedGroupId;
            }
        });
    }

    // ------------------------------------------------------------------------
    // Getters
    // ------------------------------------------------------------------------

    get canUseSortable() {
        return !this.env.isSmall;
    }

    get canMoveRecords() {
        if (!this.canResequenceRecords) {
            return false;
        }
        const groupByField = this.props.list.groupByField;
        if (!groupByField) {
            return true;
        }
        const fieldNodes = Object.values(this.props.archInfo.fieldNodes).filter(
            (fieldNode) => fieldNode.name === groupByField.name
        );
        let isReadonly = this.props.list.fields[groupByField.name].readonly;
        if (!isReadonly && fieldNodes.length) {
            isReadonly = fieldNodes.every((fieldNode) => {
                if (!fieldNode.readonly) {
                    return false;
                }
                try {
                    return evaluateExpr(fieldNode.readonly, this.props.list.evalContext);
                } catch {
                    return false;
                }
            });
        }
        return !isReadonly && this.isMovableField(groupByField);
    }

    get canResequenceGroups() {
        if (!this.props.list.isGrouped) {
            return false;
        }
        const { type } = this.props.list.groupByField;
        const { groupsDraggable } = this.props.archInfo;
        return groupsDraggable && DRAGGABLE_GROUP_TYPES.includes(type);
    }

    get canResequenceRecords() {
        const { isGrouped, orderBy } = this.props.list;
        const { handleField, recordsDraggable } = this.props.archInfo;
        return Boolean(
            recordsDraggable &&
                (isGrouped || (handleField && (!orderBy[0] || orderBy[0].name === handleField)))
        );
    }

    get canShowExamples() {
        const { allowedGroupBys = [], examples = [] } = this.exampleData || {};
        const hasExamples = Boolean(examples.length);
        return hasExamples && allowedGroupBys.includes(this.props.list.groupByField.name);
    }

    get showNoContentHelper() {
        const { model, isGrouped, groupByField, groups } = this.props.list;
        if (model.useSampleModel) {
            return true;
        }
        if (isGrouped) {
            if (this.props.quickCreateState.groupId) {
                return false;
            }
            if (this.canCreateGroup() && !this.state.columnQuickCreateIsFolded) {
                return false;
            }
            if (groups.length === 0) {
                return groupByField.type !== "many2one";
            }
        }
        return !model.hasData();
    }

    getSelection() {
        return this.props.list.selection || [];
    }

    /**
     * When the kanban records are grouped, the 'false' or 'undefined' group
     * must appear first.
     * @returns {any[]}
     */
    getGroupsOrRecords() {
        const { list } = this.props;
        if (list.isGrouped) {
            return [...list.groups]
                .sort((a, b) => (a.value && !b.value ? 1 : !a.value && b.value ? -1 : 0))
                .map((group, i) => ({
                    group,
                    key: isNull(group.value) ? `group_key_${i}` : String(group.value),
                }));
        } else {
            return list.records.map((record) => ({ record, key: record.id }));
        }
    }

    /**
     * @param {RelationalGroup} group
     * @param {boolean} isGroupProcessing
     * @returns {string}
     */
    getGroupClasses(group, isGroupProcessing) {
        const classes = [];
        if (!isGroupProcessing && this.canResequenceGroups && group.value) {
            classes.push("o_group_draggable");
        }
        if (!group.count) {
            classes.push("o_kanban_no_records");
        }
        if (!this.env.isSmall && group.isFolded) {
            classes.push("o_column_folded", "flex-basis-0");
        }
        if (this.props.progressBarState && !group.isFolded) {
            const progressBarInfo = this.props.progressBarState.getGroupInfo(group);
            if (progressBarInfo.activeBar) {
                const progressBar = progressBarInfo.bars.find(
                    (b) => b.value === progressBarInfo.activeBar
                );
                classes.push("o_kanban_group_show", `o_kanban_group_show_${progressBar.color}`);
            }
        }
        return classes.join(" ");
    }

    getGroupUnloadedCount(group) {
        const records = group.list.records.filter((r) => !r.isInQuickCreation);
        const count = this.props.progressBarState?.getGroupCount(group) || group.count;
        return count - records.length;
    }

    /**
     * @param {string} id
     * @returns {boolean}
     */
    isProcessing(id) {
        return this.state.processedIds.includes(id);
    }

    isMovableField(field) {
        return MOVABLE_RECORD_TYPES.includes(field.type);
    }

    // ------------------------------------------------------------------------
    // Permissions
    // ------------------------------------------------------------------------

    canCreateGroup() {
        const { activeActions, defaultGroupBy } = this.props.archInfo;
        return (
            activeActions.createGroup &&
            this.props.list.groupByField.type === "many2one" &&
            this.props.list.groupByField.name === defaultGroupBy?.[0]
        );
    }

    canQuickCreate() {
        return this.props.canQuickCreate;
    }

    // ------------------------------------------------------------------------
    // Edition methods
    // ------------------------------------------------------------------------

    async archiveRecord(record, active) {
        if (active) {
            this.dialog.add(ConfirmationDialog, {
                body: _t("Are you sure that you want to archive this record?"),
                confirmLabel: _t("Archive"),
                confirm: () => record.archive(),
                cancel: () => {},
            });
        } else {
            return record.unarchive();
        }
    }

    async validateQuickCreate(recordId, mode, group) {
        const record = await group.addExistingRecord(recordId, true);
        if (mode === "edit") {
            await this.props.openRecord(record);
        } else {
            this.props.progressBarState?.updateCounts(group);
        }
        this.props.quickCreateState.groupId = mode === "add" ? group.id : false;
    }

    cancelQuickCreate() {
        this.props.quickCreateState.groupId = false;
    }

    async deleteGroup(group) {
        await this.props.list.deleteGroups([group]);
        if (this.props.list.groups.length === 0) {
            this.state.columnQuickCreateIsFolded = false;
        }
    }

    toggleGroup(group) {
        return group.toggle();
    }

    loadMore(group) {
        return group.list.load({ limit: group.list.records.length + group.model.initialLimit });
    }

    /**
     * @param {string} id
     * @param {boolean} isProcessing
     */
    toggleProcessing(id, isProcessing) {
        if (isProcessing) {
            this.state.processedIds = [...this.state.processedIds, id];
        } else {
            this.state.processedIds = this.state.processedIds.filter(
                (processedId) => processedId !== id
            );
        }
    }

    toggleSelection(record, isRange = false) {
        if (isRange) {
            this.toggleRangeSelection(record);
        } else {
            record.toggleSelection();
        }
        this.lastCheckedRecord = record;
    }

    toggleRangeSelection(record) {
        const { records } = this.props.list;
        const recordIndex = records.findIndex((e) => e.id === record.id);
        const lastCheckedRecordIndex = records.findIndex((e) => e.id === this.lastCheckedRecord.id);
        const start = Math.min(recordIndex, lastCheckedRecordIndex);
        const end = Math.max(recordIndex, lastCheckedRecordIndex);
        for (let i = start; i <= end; i++) {
            records[i].toggleSelection(!record.selected);
        }
    }

    // ------------------------------------------------------------------------
    // Handlers
    // ------------------------------------------------------------------------

    async onGroupClick(group, ev) {
        if (!this.env.isSmall && group.isFolded) {
            this.lastOpenedGroupId = group.id;
            await group.toggle();
            this.props.scrollTop();
        }
    }

    /**
     * @param {string} dataGroupId
     * @param {Object} params
     * @param {HTMLElement} params.element
     * @param {HTMLElement} [params.group]
     * @param {HTMLElement} [params.next]
     * @param {HTMLElement} [params.parent]
     * @param {HTMLElement} [params.previous]
     */
    async sortGroupDrop(dataGroupId, { previous }) {
        this.toggleProcessing(dataGroupId, true);
        const refId = previous ? previous.dataset.id : null;
        try {
            await this.props.list.resequence(dataGroupId, refId);
        } finally {
            this.toggleProcessing(dataGroupId, false);
        }
    }

    onSpaceKeyPress(target, isRange) {
        if (target.classList.contains("o_kanban_record")) {
            const record = this.props.list.records.find((e) => e.id === target.dataset.id);
            this.toggleSelection(record, isRange);
        }
    }

    showExamples() {
        this.dialog.add(KanbanColumnExamplesDialog, {
            examples: this.exampleData.examples,
            applyExamplesText: this.exampleData.applyExamplesText || _t("Use This For My Kanban"),
            applyExamples: (index) => {
                const { examples, foldField } = this.exampleData;
                const { columns, foldedColumns = [] } = examples[index];
                for (const groupName of columns) {
                    this.props.list.createGroup(groupName);
                }
                for (const groupName of foldedColumns) {
                    this.props.list.createGroup(groupName, foldField);
                }
            },
        });
    }

    /**
     * @param {string} dataRecordId
     * @param {string} dataGroupId
     * @param {Object} params
     * @param {HTMLElement} params.element
     * @param {HTMLElement} [params.group]
     * @param {HTMLElement} [params.next]
     * @param {HTMLElement} [params.parent]
     * @param {HTMLElement} [params.previous]
     */
    async sortRecordDrop(dataRecordId, dataGroupId, { element, parent, previous }) {
        if (
            !this.props.list.isGrouped ||
            parent.classList.contains("o_kanban_hover") ||
            parent.dataset.id === element.parentElement.dataset.id
        ) {
            this.toggleProcessing(dataRecordId, true);

            parent?.classList.remove("o_kanban_hover");
            while (previous && !previous.dataset.id) {
                previous = previous.previousElementSibling;
            }
            const refId = previous ? previous.dataset.id : null;
            const targetGroupId = parent?.dataset.id;
            try {
                await this.props.list.moveRecord(dataRecordId, dataGroupId, refId, targetGroupId);
            } finally {
                this.toggleProcessing(dataRecordId, false);
            }
        }
    }

    /**
     * @param {Object} params
     * @param {HTMLElement} params.group
     */
    sortRecordGroupEnter({ group }) {
        group.classList.add("o_kanban_hover");
    }

    /**
     * @param {Object} params
     * @param {HTMLElement} params.group
     */
    sortRecordGroupLeave({ group }) {
        group.classList.remove("o_kanban_hover");
    }

    /**
     * @param {Object} params
     * @param {HTMLElement} params.element
     * @param {HTMLElement} [params.group]
     */
    sortStart({ element }) {
        element.classList.add("shadow");
    }

    /**
     * @param {Object} params
     * @param {HTMLElement} params.element
     * @param {HTMLElement} [params.group]
     */
    sortStop({ element, group }) {
        element.classList.remove("shadow");
        if (group) {
            group.classList.remove("o_kanban_hover");
        }
    }

    /**
     * Focus next card in the area within the chosen direction.
     *
     * @param {HTMLElement} area
     * @param {"down"|"up"|"right"|"left"} direction
     * @returns {true?} true if the next card has been focused
     */
    focusNextCard(area, direction) {
        const { isGrouped } = this.props.list;
        const closestCard = document.activeElement.closest(".o_kanban_record");
        if (!closestCard) {
            return;
        }
        const groups = isGrouped ? [...area.querySelectorAll(".o_kanban_group")] : [area];
        const cards = [...groups]
            .map((group) => [...group.querySelectorAll(".o_kanban_record")])
            .filter((group) => group.length);

        let iGroup;
        let iCard;
        for (iGroup = 0; iGroup < cards.length; iGroup++) {
            const i = cards[iGroup].indexOf(closestCard);
            if (i !== -1) {
                iCard = i;
                break;
            }
        }
        // Find next card to focus
        let nextCard;
        switch (direction) {
            case "down":
                nextCard = iCard < cards[iGroup].length - 1 && cards[iGroup][iCard + 1];
                break;
            case "up":
                nextCard = iCard > 0 && cards[iGroup][iCard - 1];
                break;
            case "right":
                if (isGrouped) {
                    nextCard = iGroup < cards.length - 1 && cards[iGroup + 1][0];
                } else {
                    nextCard = iCard < cards[0].length - 1 && cards[0][iCard + 1];
                }
                break;
            case "left":
                if (isGrouped) {
                    nextCard = iGroup > 0 && cards[iGroup - 1][0];
                } else {
                    nextCard = iCard > 0 && cards[0][iCard - 1];
                }
                break;
        }

        if (nextCard && nextCard instanceof HTMLElement) {
            nextCard.focus();
            return true;
        }
    }
}
