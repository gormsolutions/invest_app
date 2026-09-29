// Copyright (c) 2024, paul and contributors
// For license information, please see license.txt
frappe.ui.form.on('Investment App', {
    // Triggered when the form is loaded
    onload: function (frm) {
        // Set initial state without triggering form dirty
        frm.doc.__notrigger = true;
        handle_transaction_type(frm);
        delete frm.doc.__notrigger;
    },
    refresh: function (frm) {
        // UI-only code here – no set_value, no add_child, no dirty changes
    },

    validate: function (frm) {
        // 1. Guard for new docs without transaction type
        if (frm.is_new() && !frm.doc.transaction_type) {
            frappe.msgprint(__('Please choose a Transaction Type first.'));
            return false;          // stop the save
        }

        // 2. Guard: already have schedule or missing required fields
        const needsSchedule =
            ['Invest', 'Re-invest'].includes(frm.doc.transaction_type) &&
            (!frm.doc.investment_schedule || frm.doc.investment_schedule.length === 0) &&
            frm.doc.amount &&
            frm.doc.interest_rate &&
            frm.doc.start_date;

        if (!needsSchedule) return;   // nothing to do

        // 3. Build the schedule synchronously (no Promise required)
        const percent_amount = flt(frm.doc.interest_rate) / 100 * flt(frm.doc.amount);
        const withdraw_amount = flt(frm.doc.amount) + percent_amount;

        frm.set_value('percent_amount', flt(percent_amount, 2));
        frm.set_value('withdral_amount', flt(withdraw_amount, 2));

        populate_investment_schedule(frm);   // your existing function
    },

    before_submit: function (frm) {
        // optional: fetch balances once, right before submit
        if (frm.doc.party) {
            frm.trigger('fetch_balances');
        }
    },
    // Triggered when transaction_type field is changed
    // Triggered when transaction_type field is changed
    transaction_type: function (frm) {
        let old_type = frm.doc.transaction_type;

        // ----------  Withdraw defaults & recalc  ----------
        // if (frm.doc.transaction_type === 'Withdraw') {
        //     // set to 0 if empty
        //     if (!frm.doc.amount_withrowned) frm.set_value('amount_withrowned', 0);
        //     if (!frm.doc.total_interest_earned) frm.set_value('total_interest_earned', 0);
        //     calculate_total_amount(frm);         // update totals
        // }

        // ----------  existing logic  ----------
        if (frm.doc.transaction_type === "Request for Payments") {
            frappe.run_serially([
                () => handle_transaction_type(frm),
                () => {
                    if (old_type !== "Request for Payments") {
                        frm.set_value('investment_schedule', []);
                        frm.set_value('interest_rate', '');
                        frm.set_value('start_date', '');
                        frm.set_value('end_date', '');
                        frm.set_value('investment_period', '');
                    }
                },
                () => {
                    if (frm.doc.party) frm.trigger('fetch_balances');
                }
            ]);
        } else {
            handle_transaction_type(frm);
            if (frm.doc.transaction_type) {
                frm.set_value('investment_schedule', []);
                frm.set_value('interest_rate', '');
                frm.set_value('start_date', '');
                frm.set_value('end_date', '');
                frm.set_value('investment_period', '');
                if (frm.doc.party) frm.trigger('fetch_balances');
            }
        }
    },


    party: function (frm) {
        // For Request for Payments, handle updates differently
        if (frm.doc.transaction_type === "Request for Payments") {
            frappe.run_serially([
                () => update_party_name(frm),
                () => {
                    if (frm.doc.party) {
                        frm.trigger('fetch_balances');
                    }
                }
            ]);
        } else {
            update_party_name(frm);
            if (frm.doc.party) {
                frm.trigger('fetch_balances');
            }
        }
    },

    interest_rate: function (frm) {
        calculate_and_populate_schedule(frm);
    },
    amount: function (frm) {
        let tasks = [];

        // Convert amount to words
        if (frm.doc.amount) {
            tasks.push(new Promise((resolve) => {
                frappe.call({
                    method: 'loan_investment_app.custom_api.api.get_amount_in_words', // <-- NEW line
                    args: {
                        amount: frm.doc.amount,
                        currency: frappe.defaults.get_default('currency')
                    },
                    callback: function (r) {
                        if (r.message) {
                            frm.set_value('amount_in_words', r.message);
                        }
                        resolve();
                    }
                });
            }));
        } else {
            frm.set_value('amount_in_words', '');
        }

        // Calculate schedule after all tasks are complete
        Promise.all(tasks).then(() => {
            calculate_and_populate_schedule(frm);
            frm.refresh_fields();
        }).catch(e => {
            console.error("Error in amount handler:", e);
            calculate_and_populate_schedule(frm);
            frm.refresh_fields();
        });
    },

    start_date: function (frm) {
        if (frm.doc.start_date && frm.doc.investment_period) {
            calculate_end_date(frm, false);  // Pass false to indicate it's from date change
        }
    },
    end_date: function (frm) {
        if (frm.doc.investment_period && frm.doc.start_date) {
            calculate_and_populate_schedule(frm);
        }
    },

    investment_period: function (frm) {
        if (frm.doc.start_date && frm.doc.investment_period) {
            calculate_end_date(frm, true);  // Pass true to indicate it's from period change
        }
    },



    fetch_balances: function (frm) {
        if (frm.doc.transaction_type === "Deposit") {
            return;
        }

        frappe.call({
            method: 'loan_investment_app.loan_and_investment_app.doctype.investment_app.investment_app.get_cached_balances',
            args: {
                party: frm.doc.party
            },
            callback: function (r) {
                if (r.message && !r.message.error) {
                    // Always positive wallet balance
                    const walletBalance = Math.abs(r.message.balance_walet || 0);

                    if (frm.doc.docstatus === 0) {
                        frappe.run_serially([
                            () => frm.set_value('portifolia_account', r.message.portifolia_account),
                            () => frm.set_value('balance_walet', walletBalance),
                            () => frm.refresh_fields(['portifolia_account', 'balance_walet'])
                        ]);
                    }

                    if (frm.doc.transaction_type === "Request for Payments") {
                        frappe.show_alert({
                            message: __('Wallet Balance: {0}', [format_currency(walletBalance)]),
                            indicator: walletBalance > 0 ? 'green' : 'yellow'
                        }, 5);
                    }
                }
            }
        });
    },

    posting_date: function (frm) {
        let investment_end_date = frm.doc.posting_date;
        let party = frm.doc.party;

        frappe.call({
            method: 'loan_investment_app.custom_api.my_investments.fetch_investments_party_amount',
            args: {
                end_date: investment_end_date,
                party: party,
            },
            callback: function (response) {
                console.log(response);
                if (response.message) {
                    // Set total investment amount
                    frm.set_value('total_amount_invested', response.message.withdral_amount);
                    frm.set_value('total_interest_earned', response.message.total_percent_amount);

                    let tranct_type = frm.doc.transaction_type;

                    // If it's a Withdraw transaction, fill in the relevant fields
                    if (tranct_type === 'Withdraw') {
                        frm.set_value('amount', response.message.withdral_amount);
                        frm.set_value('amount_withrowned', response.message.total_amount);
                        frm.set_value('interets_withrowned', response.message.total_percent_amount);

                        // Show fields
                        frm.set_df_property('amount_withrowned', 'hidden', 0);
                        frm.set_df_property('total_interest_earned', 'hidden', 0);
                        frm.set_df_property('interets_withrowned', 'hidden', 0);
                    }
                }
            }
        });

        // Always show total_amount_invested field
        frm.set_df_property('total_amount_invested', 'hidden', 0);
    }


});




// Handle real-time balance updates
frappe.realtime.on('investment_balance_updated', function (data) {
    // Find all open forms of Investment App
    $.each(frappe.pages, function (i, page) {
        if (page.page.label === 'Investment App') {
            let frm = page.frm;
            if (frm && frm.doc.party === data.party) {
                // Update the form if it's for the same party
                if (frm.doc.docstatus === 0) {
                    frm.set_value('portifolia_account', data.balances.portifolia_account);
                    frm.set_value('balance_walet', data.balances.balance_walet);
                    frm.refresh_fields(['portifolia_account', 'balance_walet']);
                }

                // Show balance update notification
                frappe.show_alert({
                    message: __('Balances updated'),
                    indicator: 'green'
                });
            }
        }
    });
});

function calculate_and_populate_schedule(frm) {
    return new Promise((resolve, reject) => {
        try {
            // Skip if not an investment type transaction
            if (!['Invest', 'Re-invest'].includes(frm.doc.transaction_type)) {
                resolve();
                return;
            }

            // Skip if required fields are missing
            if (!frm.doc.start_date || !frm.doc.end_date ||
                !frm.doc.interest_rate || !frm.doc.amount ||
                !frm.doc.investment_period) {
                resolve();
                return;
            }

            // Calculate percentage amount and withdrawal amount
            let percent_amount = flt((flt(frm.doc.interest_rate) / 100) * flt(frm.doc.amount));
            let withdraw_amount = flt(flt(frm.doc.amount) + percent_amount);

            // Batch set values to prevent multiple triggers
            frappe.run_serially([
                () => frm.set_value('percent_amount', flt(percent_amount, 2)),
                () => frm.set_value('withdral_amount', flt(withdraw_amount, 2)),
                () => populate_investment_schedule(frm)
            ]).then(resolve).catch(reject);
        } catch (e) {
            console.error("Error in calculate_and_populate_schedule:", e);
            reject(e);
        }
    });
}

// Helper function to format date as 'YYYY-MM-DD'
function formatDate(date) {
    if (!(date instanceof Date)) {
        throw new Error("Invalid date object");
    }
    let day = String(date.getDate()).padStart(2, '0'); // Pad day with zero if needed
    let month = String(date.getMonth() + 1).padStart(2, '0'); // Pad month with zero (months are 0-indexed)
    let year = date.getFullYear(); // Get the full year
    return `${year}-${month}-${day}`; // Return formatted date as 'YYYY-MM-DD'
}

// Function to handle the visibility of fields based on transaction_type
function handle_transaction_type(frm) {
    // Hide all fields initially
    frm.toggle_display(['interest_rate', 'start_date', 'end_date', 'investment_period',
        'schedule', 'investment_schedule', 'withhold_tax', 'total_interest_earned',
        'total_amount_after_tax', 'amount_withrowned', 'interets_withrowned', 'portifolia_account',
        'withdral_amount', 'balance_walet', 'pay_to'], 0);

    if (!frm.doc.transaction_type) return;

    switch (frm.doc.transaction_type) {
        case 'Deposit':
            // Show only basic fields for deposit
            frm.toggle_display(['amount', 'mode_of_payment'], 1);
            if (!frm.doc.__notrigger) {
                frm.set_df_property('amount', 'label', 'Deposit Amount');
            }
            break;

        case 'Invest':
            frm.toggle_display([
                'interest_rate', 'deposits', 'start_date', 'end_date',
                'investment_period', 'schedule', 'investment_schedule'
            ], true);

            if (!frm.doc.__notrigger) {
                frm.set_df_property('amount', 'label', 'Amount to Invest');
                frm.set_df_property('deposits', 'label', 'Deposits');
                frm.set_df_property('interest_rate', 'reqd', 1);
                frm.set_df_property('investment_period', 'reqd', 1);
                frm.set_df_property('deposits', 'reqd', 1);
                frm.set_df_property('start_date', 'reqd', 1);
                frm.set_df_property('portifolia_account', 'read_only', 0);

                // Fetch and set deposit balance
                frappe.call({
                    method: "loan_investment_app.custom_api.user.get_member_info",
                    args: { party: frm.doc.party },
                    callback: function (r) {
                        if (r.message && r.message.balance_deposit != null) {
                            frm.set_value('deposits', r.message.balance_deposit).then(() => {
                                frm.refresh_field('deposits');
                            });
                        }
                    }
                });
            }
            break;

        case 'Re-invest':
            // Show reinvestment fields and balance
            frm.toggle_display(['interest_rate', 'start_date', 'end_date',
                'investment_period', 'schedule', 'investment_schedule', 'balance_walet'], 1);
            if (!frm.doc.__notrigger) {
                frm.set_df_property('amount', 'label', 'Re-investment Amount');
                frm.set_df_property('interest_rate', 'reqd', 1);
                frm.set_df_property('investment_period', 'reqd', 1);
                frm.set_df_property('start_date', 'reqd', 1);
            }
            break;

        case 'Withdraw':
            // Hide multiple fields
            frm.toggle_display([
                'deposits',
                'portifolia_account',
                'percent_amount',
            ], 0);
            // Show withdrawal-related fields
            frm.toggle_display([
                'interets_withrowned',
                'total_interest_earned',
                'total_amount_after_tax',
                'withdrawal_amount',
                'amount_withrowned',
                'amount'
            ], 1);

            if (!frm.doc.__notrigger) {
                // Update field properties
                frm.set_df_property('total_interest_earned', 'label', 'Total Interest Amount Till Date');
                frm.set_df_property('posting_date', 'reqd', 1);
                frm.set_df_property('amount_withrowned', 'reqd', 1);
                frm.set_df_property('total_interest_earned', 'reqd', 1);
                frm.set_df_property('balance_walet', 'reqd', 1);

                // Add live recalculation logic
                frm.fields_dict['amount_withrowned'].df.onchange = () => {
                    calculate_total_amount(frm);
                };
                frm.fields_dict['total_interest_earned'].df.onchange = () => {
                    calculate_total_amount(frm);
                };
            }
            break;

        case 'Request for Payments':
            // Show payment request fields
            frm.toggle_display(['balance_walet', 'pay_to'], 1);

            if (!frm.doc.__notrigger) {
                frm.set_df_property('balance_walet', 'label', 'Amount in the Wallet');
                frm.set_df_property('pay_to', 'reqd', 1);
            }
            break;
    }

    // Only refresh fields if not in notrigger mode
    if (!frm.doc.__notrigger) {
        frm.refresh_fields();
    }
}

function update_party_name(frm) {
    frappe.call({
        method: 'loan_investment_app.custom_api.user.get_party_name',
        args: {
            party: frm.doc.party
        },
        callback: function (response) {
            console.log(response);
            if (response.message) {
                // Set the fetched user information to the appropriate fields
                frm.set_value('party_name', response.message.member_name);

            }
        }
    });

}

//updated 20/9/2029
function populate_investment_schedule(frm) {
    return new Promise((resolve, reject) => {
        try {
            // Skip if not an investment type transaction
            if (!['Invest', 'Re-invest'].includes(frm.doc.transaction_type)) {
                resolve();
                return;
            }

            // Skip if required fields are missing
            if (!frm.doc.start_date || !frm.doc.end_date ||
                !frm.doc.interest_rate || !frm.doc.amount ||
                !frm.doc.investment_period) {
                resolve();
                return;
            }

            // Parse values safely
            let start_date = frappe.datetime.str_to_obj(frm.doc.start_date);
            let interest_rate = flt(frm.doc.interest_rate);
            let amount = flt(frm.doc.amount);
            let months_diff = get_months_diff(frm.doc.investment_period);

            if (!months_diff) {
                frappe.throw(__('Please select a valid investment period.'));
                return;
            }

            // Clear existing schedule
            frm.clear_table('investment_schedule');

            // Calculate monthly interest amount
            let monthly_interest = flt((interest_rate / 100) * amount / months_diff, 2);
            let running_total = amount;

            // Create schedule rows
            for (let i = 0; i < months_diff; i++) {
                let period_start = frappe.datetime.add_months(start_date, i);

                // Get the last day of the month for period end
                let temp_next_month = frappe.datetime.add_months(period_start, 1);
                let period_end = frappe.datetime.add_days(temp_next_month, -1);

                running_total = flt(running_total + monthly_interest, 2);

                let row = frm.add_child('investment_schedule');
                row.start_date = frappe.datetime.obj_to_str(period_start);
                row.end_date = frappe.datetime.obj_to_str(period_end);
                row.principal_amount = i === 0 ? flt(amount, 2) : 0;
                row.amount = flt(monthly_interest, 2);
                row.available_amount = flt(running_total, 2);
                row.posted_status = 'Pending';
            }

            frm.refresh_field('investment_schedule');
            resolve();
        } catch (e) {
            console.error("Error in populate_investment_schedule:", e);
            frappe.show_alert({
                message: __('Error populating investment schedule. Please check your inputs.'),
                indicator: 'red'
            });
            reject(e);
        }
    });
}

// Helper function to get months difference based on investment period
function get_months_diff(investment_period) {
    const periods = {
        '6 Months': 6,
        '1 Year': 12,
        '2 Years': 24,
        '3 Years': 36,
        '4 Years': 48,
        '5 Years': 60,
        '6 Years': 72
    };
    return periods[investment_period];
}

// Helper function to get the last day of a month
function getLastDayOfMonth(dateInput) {
    try {
        // Convert string to Date if needed
        let date = dateInput;
        if (typeof dateInput === 'string') {
            date = frappe.datetime.str_to_obj(dateInput);
        }

        // Ensure we have a valid Date object
        if (!(date instanceof Date) || isNaN(date)) {
            console.error('Invalid date input:', dateInput);
            return new Date(); // Return current date as fallback
        }

        // Get the last day of the month
        return new Date(date.getFullYear(), date.getMonth() + 1, 0);
    } catch (e) {
        console.error('Error in getLastDayOfMonth:', e);
        return new Date(); // Return current date as fallback
    }
}

// Helper function to populate schedule rows
function populate_schedule_rows(frm, start_date, months_diff, interest_rate, amount, principal_amount) {
    let monthly_amount = (interest_rate / 100) * amount / months_diff;
    let available_amount = principal_amount;

    for (let i = 0; i < months_diff; i++) {
        let scheduled_start_date = frappe.datetime.add_months(start_date, i);
        if (!(scheduled_start_date instanceof Date)) {
            scheduled_start_date = new Date(scheduled_start_date);
        }

        available_amount += monthly_amount;

        let calculated_end_date = getLastDayOfMonth(scheduled_start_date);

        let new_row = frm.add_child('investment_schedule');
        new_row.start_date = formatDate(scheduled_start_date);
        new_row.end_date = formatDate(calculated_end_date);
        new_row.principal_amount = i === 0 ? principal_amount : 0;
        new_row.available_amount = frappe.format_number(available_amount, null, 2);
        new_row.amount = frappe.format_number(monthly_amount, null, 2);
        new_row.posted_status = 'Pending';
    }
}

function calculate_end_date(frm, from_period_change) {
    if (!frm.doc.start_date || !frm.doc.investment_period) return;

    // Get months based on investment period
    let months = get_months_diff(frm.doc.investment_period);
    if (!months) {
        frappe.throw(__('Please select a valid investment period'));
        return;
    }

    try {
        // Convert start date string to Date object
        let start_date = frappe.datetime.str_to_obj(frm.doc.start_date);
        if (!start_date) {
            frappe.throw(__('Invalid start date'));
            return;
        }

        // Add months to the start date
        let end_date = frappe.datetime.add_months(start_date, months);
        if (!end_date) {
            frappe.throw(__('Error calculating end date'));
            return;
        }

        // Convert to Date object if it's a string
        if (typeof end_date === 'string') {
            end_date = frappe.datetime.str_to_obj(end_date);
        }

        // Subtract one day to get the last day of the previous month
        end_date.setDate(end_date.getDate() - 1);

        // Format and set the end date
        frm.set_value('end_date', frappe.datetime.obj_to_str(end_date));

        // Only calculate schedule if triggered from period change and we have the required fields
        if (from_period_change && frm.doc.amount && frm.doc.interest_rate) {
            calculate_and_populate_schedule(frm);
        }
    } catch (e) {
        console.error('Error in calculate_end_date:', e);
        frappe.throw(__('Error calculating end date'));
    }
}

function calculate_total_amount(frm) {
    let principal = flt(frm.doc.amount_withrowned);
    let interest = flt(frm.doc.total_interest_earned);

    // Set the interest withdrawn to match total interest earned
    frm.set_value('interets_withrowned', interest);

    // Calculate total after tax
    frm.set_value('total_amount_after_tax', principal + interest);
}
