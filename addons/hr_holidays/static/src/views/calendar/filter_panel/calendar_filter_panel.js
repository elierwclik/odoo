import { CalendarFilterPanel } from "@web/views/calendar/filter_panel/calendar_filter_panel";
import { TimeOffCardMobile } from "../../../dashboard/time_off_card";
import { getFormattedDateSpan } from "@web/views/calendar/utils";

import { serializeDate, serializeDateTime } from "@web/core/l10n/dates";
import { Cache } from "@web/core/utils/cache";
import { useService } from "@web/core/utils/hooks";
import { useState, onWillStart, onWillUpdateProps } from "@odoo/owl";

export class TimeOffCalendarFilterPanel extends CalendarFilterPanel {
    static template = "hr_holidays.CalendarFilterPanel";
    static components = {
        ...TimeOffCalendarFilterPanel.components,
        TimeOffCardMobile,
    };
    static props = {
        ...CalendarFilterPanel.props,
        // FIXME: null????
        employee_id: [Number, { value: null }],
    };
    static subTemplates = {
        filter: "hr_holidays.CalendarFilterPanel.filter",
    };

    setup() {
        super.setup();

        this.orm = useService("orm");
        this.getFormattedDateSpan = getFormattedDateSpan;
        this.leaveState = useState({
            holidays: [],
            mandatoryDays: [],
            bankHolidays: [],
        });

        this._specialDaysCache = new Cache(
            (start, end) => this.fetchSpecialDays(start, end),
            (start, end) => `${serializeDateTime(start)},${serializeDateTime(end)}`
        );

        onWillStart(() => Promise.all([this.loadFilterData(), this.updateSpecialDays()]));
        onWillUpdateProps(this.updateSpecialDays);
    }

    fetchSpecialDays(start, end) {
        const context = {
            employee_id: this.props.employee_id,
        };
        return this.orm.call(
            "hr.employee",
            "get_special_days_data",
            [serializeDate(start, "datetime"), serializeDate(end, "datetime")],
            {
                context: context,
            }
        );
    }

    async updateSpecialDays() {
        const { rangeStart, rangeEnd } = this.props.model;
        const specialDays = await this._specialDaysCache.read(rangeStart, rangeEnd);
        specialDays["bankHolidays"].forEach((bankHoliday) => {
            bankHoliday.start = luxon.DateTime.fromISO(bankHoliday.start);
            bankHoliday.end = luxon.DateTime.fromISO(bankHoliday.end);
        });
        specialDays["mandatoryDays"].forEach((mandatoryDay) => {
            mandatoryDay.start = luxon.DateTime.fromISO(mandatoryDay.start);
            mandatoryDay.end = luxon.DateTime.fromISO(mandatoryDay.end);
        });
        this.leaveState.bankHolidays = specialDays["bankHolidays"];
        this.leaveState.mandatoryDays = specialDays["mandatoryDays"];
    }

    async loadFilterData() {
        if (!this.env.isSmall) {
            return;
        }

        const filterData = {};
        const data = await this.orm.call("hr.leave.type", "get_allocation_data_request", []);

        data.forEach((leave) => {
            filterData[leave[3]] = leave;
        });
        this.leaveState.holidays = filterData;
    }
}
