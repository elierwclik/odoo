import { parseDate, parseDateTime } from "@web/core/l10n/dates";
import { localization } from "@web/core/l10n/localization";
import { evaluateExpr } from "@web/core/py_js/py";
import { registry } from "@web/core/registry";
import { escapeRegExp } from "@web/core/utils/strings";
import { Operation } from "@web/model/relational_model/operation";

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

function evaluateMathematicalExpression(expr, context = {}) {
    // remove extra space
    var val = expr.replace(new RegExp(/( )/g), "");
    var safeEvalString = "";
    for (let v of val.split(new RegExp(/([-+*/()^])/g))) {
        if (!["+", "-", "*", "/", "(", ")", "^"].includes(v) && v.length) {
            // check if this is a float and take into account user delimiter preference
            v = parseFloat(v);
        }
        if (v === "^") {
            v = "**";
        }
        safeEvalString += v;
    }
    return evaluateExpr(safeEvalString, context);
}

function parseOperation(value, parseValueFn) {
    const regex = new RegExp(
        `^(?<operator>[+\\-*/])\\s*=\\s*(?<operand>-?\\d+(?:[${escapeRegExp(
            localization.decimalPoint
        )}]\\d+)?)$`
    );
    const match = value.match(regex);
    if (match?.groups) {
        const operand = parseValueFn(match.groups.operand);
        const operator = match.groups.operator;
        return new Operation(operator, operand);
    }
    return false;
}

/**
 * Parses a string into a number.
 *
 * @param {string} value
 * @param {Object} options - additional options
 * @param {string|RegExp} options.thousandsSep - the thousands separator used in the value
 * @param {string|RegExp} options.decimalPoint - the decimal point used in the value
 * @returns {number}
 */
function parseNumber(value, options = {}) {
    if (value.startsWith("=")) {
        value = evaluateMathematicalExpression(value.substring(1));
        if (options.truncate) {
            value = Math.trunc(value);
        }
    } else {
        // A whitespace thousands separator is equivalent to any whitespace character.
        // E.g. "1  000 000" should be parsed as 1000000 even if the
        // thousands separator is nbsp.
        const thousandsSepRegex = options.thousandsSep.match(/\s+/)
            ? /\s+/g
            : new RegExp(escapeRegExp(options.thousandsSep), "g") || ",";

        // a number can have the thousand separator multiple times. ex: 1,000,000.00
        value = value.replaceAll(thousandsSepRegex, "");
        // a number only have one decimal separator
        value = value.replace(new RegExp(escapeRegExp(options.decimalPoint), "g") || ".", ".");
    }

    return Number(value);
}

// -----------------------------------------------------------------------------
// Exports
// -----------------------------------------------------------------------------

export class InvalidNumberError extends Error {}

/**
 * Try to extract a float from a string. The localization is considered in the process.
 *
 * @param {string} value
 * @returns {number} a float
 */
export function parseFloat(value, { allowOperation = false } = {}) {
    const operation = allowOperation ? parseOperation(value, parseFloat) : null;
    if (operation instanceof Operation) {
        return operation;
    }
    const thousandsSepRegex = localization.thousandsSep || "";
    const decimalPointRegex = localization.decimalPoint;
    let parsed = parseNumber(value, {
        thousandsSep: thousandsSepRegex,
        decimalPoint: decimalPointRegex,
    });
    if (isNaN(parsed)) {
        parsed = parseNumber(value, {
            thousandsSep: ",",
            decimalPoint: ".",
        });
        if (isNaN(parsed)) {
            throw new InvalidNumberError(`"${value}" is not a correct number`);
        }
    }
    return parsed;
}

/**
 * Try to extract a float time from a string. The localization is considered in the process.
 * The float time can have two formats: float or integer:integer.
 *
 * @param {string} value
 * @returns {number} a float
 */
export function parseFloatTime(value) {
    let sign = 1;
    if (value[0] === "-") {
        value = value.slice(1);
        sign = -1;
    }
    const values = value.split(":");
    if (values.length > 2) {
        throw new InvalidNumberError(`"${value}" is not a correct number`);
    }
    if (values.length === 1) {
        return sign * parseFloat(value);
    }
    const hours = parseInteger(values[0]);
    const minutes = parseInteger(values[1]);
    return sign * (hours + minutes / 60);
}

/**
 * Try to extract an integer from a string. The localization is considered in the process.
 *
 * @param {string} value
 * @returns {number} an integer
 */
export function parseInteger(value, { allowOperation = false } = {}) {
    const operation = allowOperation ? parseOperation(value, parseInteger) : null;
    if (operation instanceof Operation) {
        return operation;
    }
    const thousandsSepRegex = localization.thousandsSep || "";
    const decimalPointRegex = localization.decimalPoint;
    let parsed = parseNumber(value, {
        thousandsSep: thousandsSepRegex,
        decimalPoint: decimalPointRegex,
        truncate: true,
    });
    if (!Number.isInteger(parsed)) {
        parsed = parseNumber(value, {
            thousandsSep: ",",
            decimalPoint: ".",
            truncate: true,
        });
        if (!Number.isInteger(parsed)) {
            throw new InvalidNumberError(`"${value}" is not a correct number`);
        }
    }
    if (parsed < -2147483648 || parsed > 2147483647) {
        throw new InvalidNumberError(
            `"${value}" is out of bounds (integers should be between -2,147,483,648 and 2,147,483,647)`
        );
    }
    return parsed;
}

/**
 * Try to extract a float from a string and unconvert it with a conversion factor of 100.
 * The localization is considered in the process.
 * The percentage can have two formats: float or float%.
 *
 * @param {string} value
 * @returns {number} float
 */
export function parsePercentage(value) {
    if (value[value.length - 1] === "%") {
        value = value.slice(0, value.length - 1);
    }
    return parseFloat(value) / 100;
}

/**
 * Try to extract a monetary value from a string. The localization is considered in the process.
 * This is a very lenient function such that it ignores everything before we encounter a substring consisting of either
 * - a sign (- or +)
 * - an equals sign (signaling the start of a mathematical expression)
 * - a decimal point
 * - a number
 * We then remove any non-numeric characters at the end
 *
 *
 * @param {string} value
 * @returns {number}
 */
export function parseMonetary(value, { allowOperation = false } = {}) {
    const operation = allowOperation ? parseOperation(value, parseMonetary) : null;
    if (operation instanceof Operation) {
        return operation;
    }
    value = value.trim();
    const startMatch = value.match(
        new RegExp(`[\\d\\-+=]|${escapeRegExp(localization.decimalPoint)}`)
    );
    if (startMatch) {
        value = value.substring(startMatch.index);
    }
    value = value.replace(/\D*$/, "");
    return parseFloat(value);
}

registry
    .category("parsers")
    .add("date", parseDate)
    .add("datetime", parseDateTime)
    .add("float", parseFloat)
    .add("float_time", parseFloatTime)
    .add("integer", parseInteger)
    .add("many2one_reference", parseInteger)
    .add("monetary", parseMonetary)
    .add("percentage", parsePercentage);
