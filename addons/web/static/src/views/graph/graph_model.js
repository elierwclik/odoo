import { _t } from "@web/core/l10n/translation";
import { sortBy, groupBy, unique } from "@web/core/utils/arrays";
import { KeepLast, Race } from "@web/core/utils/concurrency";
import { rankInterval } from "@web/search/utils/dates";
import { getGroupBy } from "@web/search/utils/group_by";
import { GROUPABLE_TYPES } from "@web/search/utils/misc";
import { addPropertyFieldDefs, Model } from "@web/model/model";
import { computeReportMeasures, processMeasure } from "@web/views/utils";
import { Domain } from "@web/core/domain";

export const SEP = " / ";
const DATA_LIMIT = 80;

export const SEQUENTIAL_TYPES = ["date", "datetime"];

/**
 * @typedef {import("@web/search/search_model").SearchParams} SearchParams
 */

export class GraphModel extends Model {
    /**
     * @override
     */
    setup(params) {
        // concurrency management
        this.keepLast = new KeepLast();
        this.race = new Race();
        const _fetchDataPoints = this._fetchDataPoints.bind(this);
        this._fetchDataPoints = (...args) => this.race.add(_fetchDataPoints(...args));

        this.initialGroupBy = null;

        this.metaData = params;
        this.data = null;
        this.searchParams = null;
        // This dataset will be added as a line plot on top of stacked bar chart.
        this.lineOverlayDataset = null;
    }

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * @param {SearchParams} searchParams
     */
    async load(searchParams) {
        this.searchParams = searchParams;
        if (!this.initialGroupBy) {
            this.initialGroupBy = searchParams.context.graph_groupbys || this.metaData.groupBy; // = arch groupBy --> change that
        }
        const metaData = this._buildMetaData();
        await addPropertyFieldDefs(
            this.orm,
            metaData.resModel,
            searchParams.context,
            metaData.fields,
            metaData.groupBy.map((gb) => gb.fieldName)
        );
        await this._fetchDataPoints(metaData);
    }

    async forceLoadAll() {
        const metaData = this._buildMetaData();
        await this._fetchDataPoints(metaData, true);
        this.notify();
    }

    /**
     * @override
     */
    hasData() {
        return this.dataPoints?.length > 0;
    }

    /**
     * Only supposed to be called to change one or several parameters among
     * "measure", "mode", "order", "stacked" and "cumulated".
     * @param {Object} params
     */
    async updateMetaData(params) {
        if ("measure" in params) {
            const metaData = this._buildMetaData(params);
            await this._fetchDataPoints(metaData);
            this.useSampleModel = false;
        } else {
            await this.race.getCurrentProm();
            this.metaData = Object.assign({}, this.metaData, params);
            this._prepareData();
        }
        this.notify();
    }

    //--------------------------------------------------------------------------
    // Protected
    //--------------------------------------------------------------------------

    /**
     * @protected
     * @param {Object} [params={}]
     * @returns {Object}
     */
    _buildMetaData(params) {
        const { domain, context, groupBy } = this.searchParams;

        const metaData = Object.assign({}, this.metaData, { context });
        metaData.domains = [{ arrayRepr: domain, description: null }];
        metaData.measure = context.graph_measure || metaData.measure;
        metaData.mode = context.graph_mode || metaData.mode;
        metaData.groupBy = groupBy.length ? groupBy : this.initialGroupBy;
        if (metaData.mode !== "pie") {
            metaData.order = "graph_order" in context ? context.graph_order : metaData.order;
            if ("graph_stacked" in context) {
                metaData.stacked = context.graph_stacked;
            }
            if (metaData.mode === "line") {
                metaData.cumulated =
                    "graph_cumulated" in context ? context.graph_cumulated : metaData.cumulated;
            }
        }

        this._normalize(metaData);

        metaData.measures = computeReportMeasures(metaData.fields, metaData.fieldAttrs, [
            ...(metaData.viewMeasures || []),
            metaData.measure,
        ]);

        return Object.assign(metaData, params);
    }

    /**
     * Fetch the data points determined by the metaData. This function has
     * several side effects. It can alter this.metaData and set this.dataPoints.
     * @protected
     * @param {Object} metaData
     * @param {boolean} [forceUseAllDataPoints=false]
     */
    async _fetchDataPoints(metaData, forceUseAllDataPoints = false) {
        [this.dataPoints, this.currencyState] = await this.keepLast.add(
            this._loadDataPoints(metaData)
        );
        this.metaData = metaData;
        this._prepareData(forceUseAllDataPoints);
    }

    /**
     * Separates dataPoints coming from the read_group(s) into different
     * datasets. This function returns the parameters data and labels used
     * to produce the charts.
     * @protected
     * @param {Object[]} dataPoints
     * @param {boolean} forceUseAllDataPoints
     * @returns {Object}
     */
    _getData(dataPoints, forceUseAllDataPoints) {
        const { mode } = this.metaData;

        const dataPtMapping = new WeakMap();
        const datasetsTmp = {};
        let exceeds = false;

        // dataPoints --> labels
        const labels = [];
        const labelMap = {};
        for (const dataPt of dataPoints) {
            const datasetLabel = this._getDatasetLabel(dataPt);
            if (!(datasetLabel in datasetsTmp)) {
                if (!forceUseAllDataPoints && Object.keys(datasetsTmp).length >= DATA_LIMIT) {
                    exceeds = true;
                    continue;
                }
                datasetsTmp[datasetLabel] = {
                    label: datasetLabel,
                    originIndex: dataPt.originIndex,
                }; // add the entry but don't initialize it entirely
            }
            dataPtMapping.set(dataPt, datasetsTmp[datasetLabel]);

            const x = dataPt.labels.slice(0, mode === "pie" ? undefined : 1);
            const trueLabel = x.length ? x.join(SEP) : _t("Total");
            const key = JSON.stringify(x);
            if (labelMap[key] === undefined) {
                labelMap[key] = labels.length;
                const label = x.length ? x.join(SEP) : _t("Total");
                labels.push(label);
            }
            dataPt.labelIndex = labelMap[key];
            dataPt.trueLabel = trueLabel;
        }

        // dataPoints + labels --> datasetsTmp --> datasets
        for (const dataPt of dataPoints) {
            if (!dataPtMapping.has(dataPt)) {
                continue;
            }

            const { domain, labelIndex, trueLabel, value, identifier, cumulatedStart, currencyId } =
                dataPt;
            const dataset = dataPtMapping.get(dataPt);
            if (!dataset.data) {
                const dataLength = labels.length;
                Object.assign(dataset, {
                    data: new Array(dataLength).fill(0),
                    cumulatedStart,
                    trueLabels: labels.slice(0, dataLength),
                    domains: new Array(dataLength).fill([]),
                    identifiers: new Set(),
                    currencyIds: new Array(dataLength).fill(),
                });
            }
            dataset.data[labelIndex] = value;
            dataset.domains[labelIndex] = domain;
            dataset.trueLabels[labelIndex] = trueLabel;
            dataset.identifiers.add(identifier);
            dataset.currencyIds[labelIndex] = currencyId;
        }
        // sort by origin
        const datasets = sortBy(Object.values(datasetsTmp), "originIndex");

        return {
            datasets,
            labels,
            exceeds,
        };
    }

    _getLabel(description) {
        if (!description) {
            return _t("Sum");
        } else {
            return _t("Sum (%s)", description);
        }
    }

    _getLineOverlayDataset() {
        const { domains, stacked } = this.metaData;
        const data = this.data;
        let lineOverlayDataset = null;
        if (stacked) {
            const stacks = groupBy(data.datasets, (dataset) => dataset.originIndex);
            if (Object.keys(stacks).length == 1) {
                const [[originIndex, datasets]] = Object.entries(stacks);
                if (datasets.length > 1) {
                    const data = [];
                    const currencyIds = [];
                    for (const dataset of datasets) {
                        for (let i = 0; i < dataset.data.length; i++) {
                            data[i] = (data[i] || 0) + dataset.data[i];
                            currencyIds[i] = dataset.currencyIds[i] || currencyIds[i];
                        }
                    }
                    lineOverlayDataset = {
                        label: this._getLabel(domains[originIndex].description),
                        data,
                        currencyIds,
                        trueLabels: datasets[0].trueLabels,
                    };
                }
            }
        }
        return lineOverlayDataset;
    }

    /**
     * Determines the dataset to which the data point belongs.
     * @protected
     * @param {Object} dataPoint
     * @returns {string}
     */
    _getDatasetLabel(dataPoint) {
        const { measure, measures, domains, mode } = this.metaData;
        const { labels, originIndex } = dataPoint;
        if (mode === "pie") {
            return domains[originIndex].description || "";
        }
        // ([origin] + second to last groupBys) or measure
        let datasetLabel = labels.slice(1).join(SEP);
        if (domains.length > 1) {
            datasetLabel =
                domains[originIndex].description + (datasetLabel ? SEP + datasetLabel : "");
        }
        datasetLabel = datasetLabel || measures[measure].string;
        return datasetLabel;
    }

    /**
     * @protected
     * @returns {string}
     */
    _getDefaultFilterLabel(gb) {
        return this.metaData.fields[gb?.fieldName]?.falsy_value_label || _t("None");
    }

    /**
     * Eventually filters and sort data points.
     * @protected
     * @returns {Object[]}
     */
    _getProcessedDataPoints() {
        const { domains, groupBy, mode, order } = this.metaData;
        let processedDataPoints = [];
        if (mode === "line") {
            processedDataPoints = this.dataPoints.filter(
                (dataPoint) => dataPoint.labels[0] !== this._getDefaultFilterLabel(groupBy[0])
            );
        } else if (mode === "pie") {
            processedDataPoints = this.dataPoints.filter(
                (dataPoint) => dataPoint.value > 0 && dataPoint.count !== 0
            );
        } else {
            processedDataPoints = this.dataPoints.filter((dataPoint) => dataPoint.count !== 0);
        }

        if (order !== null && mode !== "pie" && domains.length === 1 && groupBy.length > 0) {
            // group data by their x-axis value, and then sort datapoints
            // based on the sum of values by group in ascending/descending order
            const groupedDataPoints = {};
            for (const dataPt of processedDataPoints) {
                const key = dataPt.labels[0]; // = x-axis value under the current assumptions
                if (!groupedDataPoints[key]) {
                    groupedDataPoints[key] = [];
                }
                groupedDataPoints[key].push(dataPt);
            }
            const groups = Object.values(groupedDataPoints);
            const groupTotal = (group) => group.reduce((sum, dataPt) => sum + dataPt.value, 0);
            processedDataPoints = sortBy(groups, groupTotal, order.toLowerCase()).flat();
        }

        return processedDataPoints;
    }

    /**
     * Fetch and process graph data.  It is basically a(some) read_group(s)
     * with correct fields for each domain.  We have to do some light processing
     * to separate date groups in the field list, because they can be defined
     * with an aggregation function, such as my_date:week.
     * @protected
     * @param {Object} metaData
     * @returns {Array}
     */
    async _loadDataPoints(metaData) {
        const { measure, domains, fields, groupBy, resModel, cumulatedStart } = metaData;
        const fieldName = groupBy[0]?.fieldName;
        const sequential_field =
            cumulatedStart && SEQUENTIAL_TYPES.includes(fields[fieldName]?.type) ? fieldName : null;
        const sequential_spec = sequential_field && groupBy[0].spec;
        const measures = ["__count"];
        let currencyState;
        if (measure !== "__count") {
            let { aggregator, type, currency_field } = fields[measure];
            if (type === "many2one") {
                aggregator = "count_distinct";
            }
            if (aggregator === undefined) {
                throw new Error(
                    `No aggregate function has been provided for the measure '${measure}'`
                );
            }
            if (type === "monetary" && currency_field) {
                currencyState = {
                    currencyField: currency_field,
                    currencies: [],
                };
                measures.push(`${currency_field}:array_agg_distinct`);
            }
            measures.push(`${measure}:${aggregator}`);
        }

        const numbering = {}; // used to avoid ambiguity with many2one with values with same labels:
        // for instance [1, "ABC"] [3, "ABC"] should be distinguished.

        const proms = domains.map(async (domain, originIndex) => {
            const groups = await this.orm.formattedReadGroup(
                resModel,
                domain.arrayRepr,
                groupBy.map((gb) => gb.spec),
                measures,
                {
                    context: { fill_temporal: true, ...this.searchParams.context },
                }
            );
            let start_groups = false;
            if (
                cumulatedStart &&
                sequential_field &&
                groups.length &&
                domain.arrayRepr.some((leaf) => leaf.length === 3 && leaf[0] == sequential_field)
            ) {
                const first_date = groups[0][sequential_spec][0];
                const new_domain = Domain.combine(
                    [
                        new Domain([[sequential_field, "<", first_date]]),
                        Domain.removeDomainLeaves(domain.arrayRepr, [sequential_field]),
                    ],
                    "AND"
                ).toList();
                start_groups = await this.orm.formattedReadGroup(
                    resModel,
                    new_domain,
                    groupBy.filter((gb) => gb.fieldName != sequential_field).map((gb) => gb.spec),
                    measures,
                    {
                        context: { ...this.searchParams.context },
                    }
                );
            }
            const dataPoints = [];
            const cumulatedStartValue = {};
            if (start_groups) {
                for (const group of start_groups) {
                    const rawValues = [];
                    for (const gb of groupBy.filter((gb) => gb.fieldName != sequential_field)) {
                        rawValues.push({ [gb.spec]: group[gb.spec] });
                    }
                    cumulatedStartValue[JSON.stringify(rawValues)] = group[measures.slice(-1)];
                }
            }
            for (const group of groups) {
                const { __domain, __count } = group;
                const labels = [];
                const rawValues = [];
                for (const gb of groupBy) {
                    let label;
                    const val = group[gb.spec];
                    rawValues.push({ [gb.spec]: val });
                    const fieldName = gb.fieldName;
                    const { type } = fields[fieldName];
                    if (type === "boolean") {
                        label = `${val}`; // toUpperCase?
                    } else if (type === "integer") {
                        label = val === false ? "0" : `${val}`;
                    } else if (val === false) {
                        label = this._getDefaultFilterLabel(gb);
                    } else if (["many2many", "many2one"].includes(type)) {
                        const [id, name] = val;
                        const key = JSON.stringify([fieldName, name]);
                        if (!numbering[key]) {
                            numbering[key] = {};
                        }
                        const numbers = numbering[key];
                        if (!numbers[id]) {
                            numbers[id] = Object.keys(numbers).length + 1;
                        }
                        const num = numbers[id];
                        label = num === 1 ? name : `${name} (${num})`;
                    } else if (type === "selection") {
                        const selected = fields[fieldName].selection.find((s) => s[0] === val);
                        label = selected[1];
                    } else if (["date", "datetime"].includes(type)) {
                        label = val[1];
                    } else {
                        label = val;
                    }
                    labels.push(label);
                }

                const value = group[measures.at(-1)];
                if (!Number.isInteger(value)) {
                    metaData.allIntegers = false;
                }
                const group_id = JSON.stringify(rawValues.slice(1));
                const dataPoint = {
                    count: __count,
                    domain: __domain,
                    value,
                    labels,
                    originIndex,
                    identifier: JSON.stringify(rawValues),
                    cumulatedStart: cumulatedStartValue[group_id] || 0,
                };
                // There is a currency aggregate
                if (measures.length > 2) {
                    const currencies = group[measures[1]];
                    currencyState.currencies = unique(currencyState.currencies.concat(currencies));
                    dataPoint.currencyId = currencies.length > 1 ? false : currencies[0];
                }
                dataPoints.push(dataPoint);
            }
            return dataPoints;
        });
        const promResults = await Promise.all(proms);
        return [promResults.flat(), currencyState];
    }

    /**
     * Process metaData.groupBy in order to keep only the finest interval option for
     * elements based on date/datetime field (e.g. 'date:year'). This means that
     * 'week' is prefered to 'month'. The field stays at the place of its first occurence.
     * For instance,
     * ['foo', 'date:month', 'bar', 'date:week'] becomes ['foo', 'date:week', 'bar'].
     * @protected
     * @param {Object} metaData
     */
    _normalize(metaData) {
        const { fields } = metaData;
        const groupBy = [];
        for (const gb of metaData.groupBy) {
            let ngb = gb;
            if (typeof gb === "string") {
                ngb = getGroupBy(gb, fields);
            }
            groupBy.push(ngb);
        }

        const processedGroupBy = [];
        for (const gb of groupBy) {
            const { fieldName, interval } = gb;
            if (!fieldName.includes(".")) {
                const { groupable, type } = fields[fieldName];
                if (
                    // cf. _description_groupable in odoo/fields.py
                    !groupable ||
                    ["id", "__count"].includes(fieldName) ||
                    !GROUPABLE_TYPES.includes(type)
                ) {
                    continue;
                }
            }
            const index = processedGroupBy.findIndex((gb) => gb.fieldName === fieldName);
            if (index === -1) {
                processedGroupBy.push(gb);
            } else if (interval) {
                const registeredInterval = processedGroupBy[index].interval;
                if (rankInterval(registeredInterval) < rankInterval(interval)) {
                    processedGroupBy.splice(index, 1, gb);
                }
            }
        }
        metaData.groupBy = processedGroupBy;

        metaData.measure = processMeasure(metaData.measure);
    }

    /**
     * @protected
     * @param {boolean} [forceUseAllDataPoints=false]
     */
    _prepareData(forceUseAllDataPoints = false) {
        const processedDataPoints = this._getProcessedDataPoints();
        this.data = this._getData(processedDataPoints, forceUseAllDataPoints);
        this.lineOverlayDataset = null;
        if (this.metaData.mode === "bar") {
            this.lineOverlayDataset = this._getLineOverlayDataset();
        }
    }
}
