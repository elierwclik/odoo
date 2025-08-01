import { makeContext } from "@web/core/context";
import { _t } from "@web/core/l10n/translation";
import { Pager } from "@web/core/pager/pager";
import { evaluateBooleanExpr } from "@web/core/py_js/py";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { getFieldDomain } from "@web/model/relational_model/utils";
import {
    useActiveActions,
    useAddInlineRecord,
    useOpenX2ManyRecord,
    useSelectCreate,
    useX2ManyCrud,
} from "@web/views/fields/relational_utils";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { KanbanCompiler } from "@web/views/kanban/kanban_compiler";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { ListRenderer } from "@web/views/list/list_renderer";
import { computeViewClassName } from "@web/views/utils";
import { ViewButton } from "@web/views/view_button/view_button";
import { symmetricalDifference } from "@web/core/utils/arrays";
import { x2ManyCommands } from "@web/core/orm_service";

import { Component } from "@odoo/owl";

export class X2ManyField extends Component {
    static template = "web.X2ManyField";
    static components = { Pager, KanbanRenderer, ListRenderer, ViewButton };
    static props = {
        ...standardFieldProps,
        addLabel: { type: String, optional: true },
        editable: { type: String, optional: true },
        viewMode: { type: String, optional: true },
        widget: { type: String, optional: true },
        crudOptions: { type: Object, optional: true },
        string: { type: String, optional: true },
        relatedFields: { type: Object, optional: true },
        views: { type: Object, optional: true },
        domain: { type: [Array, Function], optional: true },
        context: { type: Object },
    };

    setup() {
        this.field = this.props.record.fields[this.props.name];
        const { saveRecord, updateRecord, removeRecord } = useX2ManyCrud(
            () => this.list,
            this.isMany2Many
        );

        this.archInfo = this.props.views?.[this.props.viewMode] || {};
        const classes = this.props.viewMode
            ? ["o_field_x2many", `o_field_x2many_${this.props.viewMode}`]
            : ["o_field_x2many"];
        this.className = computeViewClassName(this.props.viewMode, this.archInfo.xmlDoc, classes);

        const { activeActions, controls } = this.archInfo;
        if (this.props.viewMode === "kanban") {
            this.controls = controls || [];
        }
        const subViewActiveActions = activeActions;
        this.activeActions = useActiveActions({
            crudOptions: Object.assign({}, this.props.crudOptions, {
                onDelete: removeRecord,
                edit: this.props.record.isInEdition,
            }),
            fieldType: this.isMany2Many ? "many2many" : "one2many",
            subViewActiveActions,
            getEvalParams: (props) => ({
                evalContext: props.record.evalContext,
                readonly: props.readonly,
            }),
        });

        this.addInLine = useAddInlineRecord({
            addNew: (...args) => this.list.addNewRecord(...args),
        });

        const openRecord = useOpenX2ManyRecord({
            resModel: this.list.resModel,
            activeField: this.activeField,
            activeActions: this.activeActions,
            getList: () => this.list,
            saveRecord,
            updateRecord,
            isMany2Many: this.isMany2Many,
        });
        this._openRecord = (params) => {
            const activeElement = document.activeElement;
            openRecord({
                ...params,
                controls: this.controls,
                onClose: () => {
                    if (activeElement) {
                        activeElement.focus();
                    }
                },
            });
        };
        this.canOpenRecord =
            this.props.viewMode === "list"
                ? !(this.archInfo.editable || this.props.editable)
                : true;

        const selectCreate = useSelectCreate({
            resModel: this.props.record.data[this.props.name].resModel,
            activeActions: this.activeActions,
            onSelected: (resIds) => saveRecord(resIds),
            onCreateEdit: ({ context }) => this._openRecord({ context }),
            onUnselect: this.isMany2Many ? undefined : () => saveRecord(),
        });

        this.selectCreate = (params) => {
            const p = Object.assign({}, params);
            const currentIds = this.props.record.data[this.props.name].currentIds.filter(
                (id) => typeof id === "number"
            );
            p.domain = [...(p.domain || []), "!", ["id", "in", currentIds]];
            return selectCreate(p);
        };
        this.action = useService("action");
        this.notificationService = useService("notification");
    }

    get activeField() {
        return {
            fields: this.props.relatedFields,
            views: this.props.views,
            viewMode: this.props.viewMode,
            string: this.props.string,
        };
    }

    get displayControlPanelButtons() {
        return this.props.viewMode === "kanban" && this.canCreate && this.controls.length > 0;
    }

    get canCreate() {
        return (
            ("link" in this.activeActions ? this.activeActions.link : this.activeActions.create) &&
            !this.props.readonly
        );
    }

    get isMany2Many() {
        return this.field.type === "many2many" || this.props.widget === "many2many";
    }

    get list() {
        return this.props.record.data[this.props.name];
    }

    get nestedKeyOptionalFieldsData() {
        return {
            field: this.props.name,
            model: this.props.record.resModel,
            viewMode: "form",
        };
    }

    get pagerProps() {
        const list = this.list;
        return {
            offset: list.offset,
            limit: list.limit,
            total: list.count,
            onUpdate: async ({ offset, limit }) => {
                const initialLimit = this.list.limit;
                const leaved = await list.leaveEditMode();
                if (leaved) {
                    if (initialLimit === limit && initialLimit === this.list.limit + 1) {
                        // Unselecting the edited record might have abandonned it. If the page
                        // size was reached before that record was created, the limit was temporarily
                        // increased to keep that new record in the current page, and abandonning it
                        // decreased this limit back to it's initial value, so we keep this into
                        // account in the offset/limit update we're about to do.
                        offset -= 1;
                        limit -= 1;
                    }
                    await list.load({ limit, offset });
                    this.render();
                }
            },
            withAccessKey: false,
        };
    }

    get rendererProps() {
        const { archInfo } = this;
        const props = {
            archInfo,
            list: this.list,
            openRecord: this.openRecord.bind(this),
            readonly: this.props.readonly,
        };

        if (this.props.viewMode === "kanban") {
            const recordsDraggable = !this.props.readonly && archInfo.recordsDraggable;
            props.archInfo = { ...archInfo, recordsDraggable };
            props.Compiler = KanbanCompiler;
            // TODO: apply same logic in the list case
            props.deleteRecord = (record) => {
                if (this.isMany2Many) {
                    return this.list.forget(record);
                }
                return this.list.delete(record);
            };
            if (this.canCreate && this.controls.length === 0) {
                props.addLabel = this.props.addLabel || _t("Add %s", this.field.string);
                props.onAdd = this.onAdd.bind(this);
            }
            return props;
        }

        const editable =
            (this.archInfo.activeActions.edit && archInfo.editable) || this.props.editable;
        props.activeActions = this.activeActions;
        props.cycleOnTab = false;
        props.editable = !this.props.readonly && editable;
        props.nestedKeyOptionalFieldsData = this.nestedKeyOptionalFieldsData;
        props.onAdd = (params) => {
            params.editable =
                !this.props.readonly && ("editable" in params ? params.editable : editable);
            this.onAdd(params);
        };
        props.onOpenFormView = this.switchToForm.bind(this);
        props.hasOpenFormViewButton = archInfo.editable ? archInfo.openFormView : false;
        return props;
    }

    evalInvisible(invisible) {
        return evaluateBooleanExpr(invisible, this.list.evalContext);
    }

    async switchToForm(record, options) {
        let resId = null;
        if (record.isNew) {
            // In the case of a new record, you don't have access to the id from the start, to get it we need to:
            // - Finds the record's index using its _virtualId.
            // - Saves the record and compares resIds before and after to detect new records.
            // - If the record was created, it determines its final resId by matching the index.
            // - Opens the form view for the correct record.
            const createCommands = this.list._commands.filter(
                ([command]) => command === x2ManyCommands.CREATE
            );
            const newRecordIndex = createCommands.findIndex(
                ([_command, virtualId]) => virtualId === record._virtualId
            );
            const previousResIds = this.list.resIds;
            const saved = await this.props.record.save();
            if (!saved) {
                return;
            }
            const newResIds = symmetricalDifference(this.list.resIds, previousResIds);
            if (newResIds.length !== createCommands.length) {
                return this.notificationService.add(_t("Please save your changes first"), {
                    type: "danger",
                });
            }
            newResIds.sort((x, y) => x - y);
            resId = newResIds[newRecordIndex];
        } else {
            const saved = await this.props.record.save();
            if (!saved) {
                return;
            }
            resId = record.resId;
        }

        this.action.doAction(
            {
                type: "ir.actions.act_window",
                views: [[false, "form"]],
                res_id: resId,
                res_model: this.list.resModel,
                context: this.getFormActionContext(),
            },
            {
                props: { resIds: this.list.resIds },
                newWindow: options.newWindow,
            }
        );
    }

    getFormActionContext() {
        return this.props.context;
    }

    async onAdd({ context, editable } = {}) {
        context = makeContext([this.props.context, context]);
        if (this.isMany2Many) {
            const domain = getFieldDomain(this.props.record, this.props.name, this.props.domain);
            const { string } = this.props;
            const title = _t("Add: %s", string);
            return this.selectCreate({ domain, context, title });
        }
        if (editable) {
            const editedRecord = this.list.editedRecord;
            if (editedRecord) {
                const proms = [];
                this.list.model.bus.trigger("NEED_LOCAL_CHANGES", { proms });
                await Promise.all([...proms, editedRecord._updatePromise]);
                await this.list.leaveEditMode({ canAbandon: false });
            }
            if (!this.list.editedRecord) {
                return this.addInLine({ context, editable });
            }
            return;
        }
        return this._openRecord({ context });
    }

    async openRecord(record) {
        if (this.canOpenRecord) {
            return this._openRecord({
                record,
                context: this.props.context,
                readonly: this.props.readonly,
            });
        }
    }
}

export const x2ManyField = {
    component: X2ManyField,
    displayName: _t("Relational table"),
    supportedTypes: ["one2many", "many2many"],
    useSubView: true,
    extractProps: (
        { attrs, relatedFields, viewMode, views, widget, options, string },
        dynamicInfo
    ) => {
        const props = {
            addLabel: attrs["add-label"],
            context: dynamicInfo.context,
            domain: dynamicInfo.domain,
            crudOptions: options,
            string,
        };
        if (viewMode) {
            props.views = views;
            props.viewMode = viewMode;
            props.relatedFields = relatedFields;
        }
        if (widget) {
            props.widget = widget;
        }
        return props;
    },
};

registry.category("fields").add("one2many", x2ManyField);
registry.category("fields").add("many2many", x2ManyField);
