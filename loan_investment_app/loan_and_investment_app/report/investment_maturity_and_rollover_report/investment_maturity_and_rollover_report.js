frappe.query_reports["Investment Maturity and Rollover Report"] = {
    filters: [
        {
            fieldname: "status",
            label: __("Maturity Status"),
            fieldtype: "Select",
            options: "\nAll\nActive\nDue in 30 Days\nDue in 60 Days\nDue in 90 Days\nMatured - Unsettled\nWithdrawn\nRolled Over",
            default: "All"
        },
        {
            fieldname: "party",
            label: __("Investor (Member)"),
            fieldtype: "Link",
            options: "Member"
        },
        {
            fieldname: "from_date",
            label: __("Maturity From"),
            fieldtype: "Date"
        },
        {
            fieldname: "to_date",
            label: __("Maturity To"),
            fieldtype: "Date"
        }
    ],
    formatter: function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname == "maturity_status") {
            if (data.maturity_status == "Active") {
                value = `<span class="indicator-pill green">${value}</span>`;
            } else if (data.maturity_status == "Due in 30 Days") {
                value = `<span class="indicator-pill orange">${value}</span>`;
            } else if (data.maturity_status == "Matured - Unsettled") {
                value = `<span class="indicator-pill red">${value}</span>`;
            } else if (data.maturity_status == "Withdrawn") {
                value = `<span class="indicator-pill grey">${value}</span>`;
            } else if (data.maturity_status == "Rolled Over") {
                value = `<span class="indicator-pill purple">${value}</span>`;
            }
        }
        return value;
    }
};
