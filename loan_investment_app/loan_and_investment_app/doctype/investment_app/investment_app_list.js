frappe.listview_settings['Investment App'] = {
    add_fields: [
        "end_date",
        "start_date",
        "transaction_type",
        "investment_status",
        "docstatus",
        "investment_progression",
        "amount"
    ],
    get_indicator(doc) {
        if (doc.docstatus === 0) {
            return [__("Draft"), "grey", "docstatus,=,0"];
        }
        if (doc.docstatus === 2) {
            return [__("Cancelled"), "red", "docstatus,=,2"];
        }

        // Investment contracts
        if (doc.transaction_type === "Invest" || doc.transaction_type === "Re-invest") {
            if (doc.investment_progression === "Withdrawn") {
                return [__("Withdrawn"), "darkgrey", "investment_progression,=,Withdrawn"];
            }
            if (doc.investment_progression === "Rolled Over") {
                return [__("Rolled Over"), "purple", "investment_progression,=,Rolled Over"];
            }
            if (doc.investment_progression === "Matured" || (doc.end_date && frappe.datetime.get_diff(doc.end_date, frappe.datetime.get_today()) < 0)) {
                return [__("Matured"), "orange", "investment_progression,=,Matured"];
            }
            return [__("Active"), "green", "investment_progression,=,Active"];
        }

        // Payout and withdrawal requests
        if (doc.transaction_type === "Withdraw" || doc.transaction_type === "Request for Payments") {
            if (doc.docstatus === 1) {
                return [__(doc.transaction_type), "blue", "transaction_type,=," + doc.transaction_type];
            }
            return [__("Pending Payout"), "orange", "docstatus,=,0|transaction_type,in,Withdraw,Request for Payments"];
        }

        if (doc.transaction_type === "Deposit") {
            return [__("Deposit"), "blue", "transaction_type,=,Deposit"];
        }

        return [__("Submitted"), "blue", "docstatus,=,1"];
    },
    onload(listview) {
        // Quick filter buttons in list page
        listview.page.add_inner_button(__("Active Contracts"), () => {
            listview.filter_area.clear();
            listview.filter_area.add([
                ["Investment App", "docstatus", "=", 1],
                ["Investment App", "transaction_type", "in", ["Invest", "Re-invest"]],
                ["Investment App", "investment_progression", "=", "Active"]
            ]);
        }, __("Filter Preset"));

        listview.page.add_inner_button(__("Matured Contracts"), () => {
            listview.filter_area.clear();
            listview.filter_area.add([
                ["Investment App", "docstatus", "=", 1],
                ["Investment App", "transaction_type", "in", ["Invest", "Re-invest"]],
                ["Investment App", "investment_progression", "=", "Matured"]
            ]);
        }, __("Filter Preset"));

        listview.page.add_inner_button(__("Sync Contract Maturities"), () => {
            frappe.call({
                method: "loan_investment_app.custom_api.desk.sync_contract_lifecycle",
                freeze: true,
                freeze_message: __("Evaluating contract maturities..."),
                callback: function(r) {
                    if (r.message && r.message.status === "success") {
                        frappe.msgprint({
                            title: __("Maturities Synchronized"),
                            indicator: "green",
                            message: __("Portfolio evaluated: {0} Active, {1} Matured out of {2} total contracts.", [
                                r.message.updated_active,
                                r.message.updated_matured,
                                r.message.total_evaluated
                            ])
                        });
                        listview.refresh();
                    }
                }
            });
        }, __("Actions"));
    }
};
