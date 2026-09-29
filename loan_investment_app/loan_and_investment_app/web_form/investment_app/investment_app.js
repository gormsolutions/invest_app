frappe.ready(function () {
    // Bind events here
    setTimeout(function () {
        // Fetch the user information
        frappe.call({
            method: 'loan_investment_app.custom_api.user.get_logged_in_user_info',
            callback: function (response) {
                console.log(response);
                if (response.message) {
                    // Set the fetched user information to the appropriate fields  
                    frappe.web_form.set_value('posting_date', response.message.current_date);
                    frappe.web_form.set_value('party_type', "Member");
                    frappe.web_form.set_value('party_id', response.message.member);
                    frappe.web_form.set_value('party_name', response.message.member_name);
                    frappe.web_form.set_value('investor_bank_name', response.message.custom_investor_bank_name);
                    frappe.web_form.set_value('investor_account_number', response.message.custom_investor_account_number);
                    frappe.web_form.set_value('investor_account_name', response.message.custom_investor_account_name);
                    frappe.web_form.set_value('balance_walet', response.message.balance_withdrawal_payable);
                    frappe.web_form.set_value('amount', response.message.balance_amount_in_wallet);
                    frappe.web_form.set_value('amount_withrowned', response.message.balance_portfolia);
                    frappe.web_form.set_value('interets_withrowned', response.message.balance_interest);
                    frappe.web_form.set_value('portifolia_account', response.message.balance_deposit);
                    frappe.web_form.set_value('adress', response.message.custom_resident);
                     frappe.web_form.set_value('total_interest_earned', response.message.balance_interest);
                    frappe.web_form.set_value('available_amount_in_wallet', response.message.balance_amount_in_wallet);
                }
            }
        });

        // Event listener for transaction_type field
        frappe.web_form.on('transaction_type', function (field, value) {
            handle_transaction_type(value);
            populate_schedule_table(value)
            frappe.web_form.set_df_property('posting_date', 'hidden', 0);
        });

        // Event listeners for posting_date and amount fields total_amount_invested
        frappe.web_form.on('posting_date', function (field, value) {
            let investment_end_date = value;  // Assign value to investment_end_date
           
            // Fetch total investment amount for the selected end date
            frappe.call({
                method: 'loan_investment_app.custom_api.my_investments.fetch_investments_for_party_amount',
                args: {
                    end_date: investment_end_date  // Pass the investment_end_date as the 'end_date' argument
                },
                callback: function (response) {
                    // console.log(response);
                    if (response.message) { 
                        // Set the fetched total amount to the 'total_amount_invested' field
                        frappe.web_form.set_value('total_amount_invested', response.message.withdral_amount);
                        frappe.web_form.set_value('total_interest_earned', response.message.total_percent_amount);
                        let tranct_type = frappe.web_form.get_value('transaction_type');

                        // Get the raw value from the total_amount_invested field
                        // let investedField = frappe.web_form.get_value('total_amount_invested'); 
                                
                   

                        // Call populate_schedule_table with both the start_date and end_date
                        if (tranct_type == 'Withdraw') {
                            frappe.web_form.set_value('amount', response.message.withdral_amount);
                            frappe.web_form.set_value('amount_withrowned', response.message.total_amount);
                            frappe.web_form.set_value('interets_withrowned', response.message.total_percent_amount);
                            

                            // frappe.web_form.set_value('interets_withrowned', response.message.total_percent_amount);
                            frappe.web_form.set_df_property('amount_withrowned', 'hidden', 0);
                            frappe.web_form.set_df_property('total_interest_earned', 'hidden', 0);
                            frappe.web_form.set_df_property('interets_withrowned', 'hidden', 0);
                            // Check if total_invested is zero after converting it to a float
                                    
                        }
                        
                    }
                }
            });

            frappe.web_form.set_df_property('total_amount_invested', 'hidden', 0);


        });
        frappe.web_form.on('amount', function (field, value) {
            calculate_percent_amount();
        });
        frappe.web_form.on('start_date', function (field, value) {
            frappe.web_form.set_df_property('investment_period', 'hidden', 0);
            calculate_percent_amount();
            set_end_date();
        });
        frappe.web_form.on('investment_period', function (field, value) {
            frappe.web_form.set_df_property('end_date', 'hidden', 0);
            set_end_date();
            // calculate_percent_amount();
        });

        // Trigger when the end_date field changes
        frappe.web_form.on('end_date', function (field, value) {
            // calculate_percent_amount();  // Call to calculate the percentage amount again when the end date changes

            // Fetch the start_date value to pass it along with the end_date
            let start_date = frappe.web_form.get_value('start_date');
            let tranct_type = frappe.web_form.get_value('transaction_type');

            if (!start_date) {
                console.error("Start date not provided. Cannot proceed.");
                return;
            }


            // Call populate_schedule_table with both the start_date and end_date
            if (tranct_type == 'Withdraw') {
                populate_schedule_table('Withdraw', start_date, value);  // Pass the transaction type 'Withdraw', start_date, and end_date

            }

            if (tranct_type == 'Invest' || tranct_type == 'Re-invest') {
                populate_investment_schedule();  // Call the function to populate the investment schedule if needed
            }

        });
        // Initial handling of transaction_type visibility
        handle_transaction_type(frappe.web_form.get_value('transaction_type'));

        // Initial percent amount calculation
        calculate_percent_amount();
    }, 1000); // Adjust the timeout value as needed

    // Function to calculate percent_amount and set it in the form
    function calculate_percent_amount() {
        let interest_rate = parseFloat(frappe.web_form.get_value('interest_rate'));
        let amount = parseFloat(frappe.web_form.get_value('amount'));
        if (interest_rate && amount) {
            // Calculate the percentage amount
            let percent_amount = (interest_rate / 100) * amount;
            let withdraw_amount = percent_amount + amount;

            // Set the calculated value in the percent_amount field
            frappe.web_form.set_value('percent_amount', percent_amount);
            frappe.web_form.set_value('withdral_amount', withdraw_amount);
        }
    }


    function populate_schedule_table(transaction_type, start_date, end_date) {
        if (transaction_type === 'Withdraw') {
            // Fetch the investment schedule for the withdrawal with the provided date range
            frappe.call({
                method: 'loan_investment_app.custom_api.user.fetch_investment_schedule',
                args: {
                    start_date: start_date,  // Pass start date as argument
                    end_date: end_date       // Pass end date as argument
                },
                callback: function (response) {
                    console.log(response.message);
                    if (response.message) {
                        // Clear existing rows in the investment_schedule child table
                        let child_table = frappe.web_form.get_field('investment_schedule');
                        // console.log(response);

                        // Set the calculated value in the percent_amount field 
                        frappe.web_form.set_value('withdraw_percen_amount', response.message.total_percent_amount);
                        let amount = parseFloat(frappe.web_form.get_value('amount'));
                        let total_amount = amount + response.message.total_percent_amount
                        frappe.web_form.set_value('withdraw_grand_totals', total_amount);


                        // Check if the child table exists before proceeding
                        if (!child_table) {
                            console.error('Child table investment_schedule not found');
                            return; // Exit if the child table is not found
                        }

                        // Clear the existing data in the child table
                        child_table.df.data = [];

                        // Sort the schedule data by the 'parent' field to maintain order
                        let sorted_schedule_data = response.message.investment_schedule_data.sort((a, b) => {
                            return a.parent.localeCompare(b.parent);
                        });

                        // Populate new rows based on the sorted response data
                        sorted_schedule_data.forEach(schedule => {
                            // Create a new row object directly from the schedule data
                            let new_row = {
                                start_date: schedule.start_date,  // Assuming schedule has a 'date' field
                                end_date: schedule.end_date,
                                principal_amount: schedule.principal_amount || 0,  // Use provided principal amount
                                available_amount: schedule.available_amount || 0,  // Use provided available amount
                                amount: schedule.amount || 0,  // Use provided amount
                                // invest_id: schedule.parent  // Ensure parent is added in order
                            };

                            // Add the new row to the child table
                            child_table.df.data.push(new_row);
                        });

                        // Set the new rows in the child table
                        child_table.refresh();
                    }
                }
            });
        }
    }
   
    // Function to handle the visibility of fields based on transaction_type 
    function handle_transaction_type(transaction_type) {
        const fields = ['interest_rate', 'investor_account_number', 'posting_date',
            'start_date', 'withdraw_percen_amount', 'withdraw_grand_totals',
            'investment_schedule', 'investor_account_name', 'pay_to', 'withdral_amount',
            'end_date','total_amount_invested', 'adress', 'total_interest_earned',
            'investment_period', 'balance_walet', 'available_amount_in_wallet',
             'amount_withrowned', 'interets_withrowned', 'investor_bank_name',
              'percent_amount', 'mode_of_payment'];

        if (transaction_type === 'Invest' || transaction_type === 'Re-invest') {
            // Make fields visible for 'Invest' and 'Re-invest'
            frappe.web_form.set_df_property('interest_rate', 'hidden', 1);
            frappe.web_form.set_df_property('start_date', 'hidden', 0);
            frappe.web_form.set_df_property('end_date', 'hidden', 1);
            frappe.web_form.set_df_property('percent_amount', 'hidden', 1);
            frappe.web_form.set_df_property('mode_of_payment', 'hidden', 1);
            frappe.web_form.set_df_property('investor_bank_name', 'hidden', 1);
            frappe.web_form.set_df_property('investor_account_number', 'hidden', 1);
            frappe.web_form.set_df_property('investment_schedule', 'hidden', 1);
            frappe.web_form.set_df_property('investor_account_name', 'hidden', 1);
            frappe.web_form.set_df_property('investment_period', 'hidden', 1);
            frappe.web_form.set_df_property('balance_walet', 'hidden', 0);
        } else if (transaction_type === 'Deposit') {
            // Make mode_of_payment visible for 'Deposit' and 'Withdraw'
            frappe.web_form.set_df_property('interest_rate', 'hidden', 1);
            frappe.web_form.set_df_property('start_date', 'hidden', 1);
            frappe.web_form.set_df_property('end_date', 'hidden', 1);
            frappe.web_form.set_df_property('percent_amount', 'hidden', 1);
            frappe.web_form.set_df_property('mode_of_payment', 'hidden', 1);
            frappe.web_form.set_df_property('investment_schedule', 'hidden', 1);
            frappe.web_form.set_df_property('withdral_amount', 'hidden', 1);
            frappe.web_form.set_df_property('investor_bank_name', 'hidden', 1);
            frappe.web_form.set_df_property('investor_account_number', 'hidden', 1);
            frappe.web_form.set_df_property('investor_account_name', 'hidden', 1);
            frappe.web_form.set_df_property('balance_walet', 'hidden', 0);
        }
        else if (transaction_type === 'Withdraw') {
            // Make mode_of_payment visible for 'Deposit' and 'Withdraw' investor_bank_name
            frappe.web_form.set_df_property('interest_rate', 'hidden', 1);
            frappe.web_form.set_df_property('start_date', 'hidden', 1);
            frappe.web_form.set_df_property('end_date', 'hidden', 1);
            frappe.web_form.set_df_property('withdraw_percen_amount', 'hidden', 1);
            frappe.web_form.set_df_property('mode_of_payment', 'hidden', 1);
            frappe.web_form.set_df_property('investment_schedule', 'hidden', 0);
            frappe.web_form.set_df_property('withdral_amount', 'hidden', 1);
            frappe.web_form.set_df_property('investor_bank_name', 'hidden', 1);
            frappe.web_form.set_df_property('investor_account_number', 'hidden', 1);
            frappe.web_form.set_df_property('investor_account_name', 'hidden', 1);
            frappe.web_form.set_df_property('balance_walet', 'hidden', 0);
            frappe.web_form.set_df_property('amount_withrowned', 'hidden', 0);
            frappe.web_form.set_df_property('total_interest_earned', 'hidden', 0);
            frappe.web_form.set_df_property('interets_withrowned', 'hidden', 0);
  
        }


        else if (transaction_type === 'Request for Payments') {
            // Make mode_of_payment visible for 'Deposit' and 'Withdraw' pay_to
            frappe.web_form.set_df_property('interest_rate', 'hidden', 1);
            frappe.web_form.set_df_property('start_date', 'hidden', 1);
            frappe.web_form.set_df_property('end_date', 'hidden', 1);
            frappe.web_form.set_df_property('percent_amount', 'hidden', 1);
            frappe.web_form.set_df_property('mode_of_payment', 'hidden', 1);
            frappe.web_form.set_df_property('investment_schedule', 'hidden', 1);
            frappe.web_form.set_df_property('withdral_amount', 'hidden', 0);
            frappe.web_form.set_df_property('investor_bank_name', 'hidden', 0);
            frappe.web_form.set_df_property('investor_account_number', 'hidden', 0);
            frappe.web_form.set_df_property('investor_account_name', 'hidden', 0);
            frappe.web_form.set_df_property('balance_walet', 'hidden', 0);
            frappe.web_form.set_df_property('pay_to', 'hidden', 1);
            frappe.web_form.set_df_property('adress', 'hidden', 0);
        }
        else if (transaction_type === 'Transfer') {
            // Hide all fields for 'Transfer'
            fields.forEach(field => {
                frappe.web_form.set_df_property(field, 'hidden', 1);
                frappe.web_form.set_df_property('balance_walet', 'hidden', 0);
            });
        } else {
            // Default case: Hide all fields
            fields.forEach(field => {
                frappe.web_form.set_df_property(field, 'hidden', 1);
            });
        }
    }

    // Function to set the investment end date with last day of the month and 28-day months
    function set_end_date() {
        // Get start date and investment period from the form
        let start_date = frappe.web_form.get_value('start_date');
        let investment_period = frappe.web_form.get_value('investment_period');
        // Trim any whitespace

        // Ensure the start date is valid before proceeding
        if (start_date) {
            // Convert start date string to a Date object
            let end_date = new Date(start_date);

            // Adjust the end date based on the selected investment period
            switch (investment_period) {
                case '6 Months':
                    end_date.setMonth(end_date.getMonth() + 6);
                    break;
                case '1 Year':
                    end_date.setFullYear(end_date.getFullYear() + 1);
                    break;
                case '2 Years':
                    end_date.setFullYear(end_date.getFullYear() + 2);
                    break;
                case '3 Years':
                    end_date.setFullYear(end_date.getFullYear() + 3);
                    break;
                case '4 Years':
                    end_date.setFullYear(end_date.getFullYear() + 4);
                    break;
                case '5 Years':
                    end_date.setFullYear(end_date.getFullYear() + 5);
                    break;
                default:
                    // Handle cases where no valid period is selected
                    // frappe.msgprint(__('Please select a valid investment period'));
                    return;
            }

            // Always set to the last day of the month, considering months as 28 days
            // Set the date to the 28th of the adjusted month
            end_date.setDate(28);

            // Format the end_date to 'YYYY-MM-DD'
            let formatted_end_date = end_date.toISOString().split('T')[0]; // Extract only the date portion

            // Set the calculated end date back into the form
            frappe.web_form.set_value('end_date', formatted_end_date);
        } else {
            frappe.msgprint(__('Please select a start date first.'));
        }
    }

    // Function to populate the investment schedule child table based on the selected period
    function populate_investment_schedule() {
        let start_date = frappe.web_form.get_value('start_date');
        let end_date = frappe.web_form.get_value('end_date');
        let interest_rate = parseFloat(frappe.web_form.get_value('interest_rate'));
        let amount = parseFloat(frappe.web_form.get_value('amount'));
        let investment_period = frappe.web_form.get_value('investment_period');

        // Define the initial principal amount
        let principal_amount = amount;

        if (start_date && end_date && interest_rate && amount && investment_period) {
            // Convert the start and end dates to JavaScript Date objects
            start_date = frappe.datetime.str_to_obj(start_date);
            end_date = frappe.datetime.str_to_obj(end_date);

            // Calculate the difference in months based on the selected investment period
            let months_diff;
            switch (investment_period) {
                case '6 Months':
                    months_diff = 6;
                    break;
                case '1 Year':
                    months_diff = 12;
                    break;
                case '2 Years':
                    months_diff = 24;
                    break;
                case '3 Years':
                    months_diff = 36;
                    break;
                case '4 Years':
                    months_diff = 48;
                    break;
                case '5 Years':
                    months_diff = 60;
                    break;
                default:
                    frappe.msgprint(__('Please select a valid investment period.'));
                    return;
            }

            // Clear existing rows in the investment_schedule child table
            let child_table = frappe.web_form.get_field('investment_schedule');
            child_table.df.data = [];

            // Calculate the monthly amount
            let monthly_amount = (interest_rate / 100) * amount / months_diff;
            let available_amount = principal_amount;

            // Utility function to format the date as 'DD-MM-YYYY'
            function formatDate(date) {
                let day = String(date.getDate()).padStart(2, '0');
                let month = String(date.getMonth() + 1).padStart(2, '0');
                let year = date.getFullYear();
                return `${day}-${month}-${year}`;
            }

            // Function to get the last day of a month (handling 28-day months)
            function getLastDayOfMonth(date) {
                let lastDay = new Date(date.getFullYear(), date.getMonth() + 1, 0);
                // If it's February, enforce 28 days (to cover the leap year case)
                if (lastDay.getMonth() === 1) {
                    lastDay.setDate(28);
                }
                return lastDay;
            }

            // Populate new rows for each month in the difference
            let new_rows = [];
            for (let i = 0; i < months_diff; i++) {
                // Calculate the scheduled start date for the current month
                let scheduled_start_date = frappe.datetime.add_months(start_date, i);

                // Ensure it's a Date object
                if (!(scheduled_start_date instanceof Date)) {
                    scheduled_start_date = new Date(scheduled_start_date);
                }

                // Increment available amount by the monthly amount for each month
                available_amount += monthly_amount;

                // Format the scheduled start date
                let formatted_start_date = formatDate(scheduled_start_date);

                // Calculate the end date as the last day of the current month (with 28-day months)
                let calculated_end_date = getLastDayOfMonth(scheduled_start_date);
                let formatted_end_date = formatDate(calculated_end_date);

                // Create a new row object
                let new_row = {
                    start_date: frappe.datetime.obj_to_str(scheduled_start_date),
                    end_date: formatted_end_date,  // Last day of the month or 28th day for February
                    principal_amount: i === 0 ? principal_amount : 0,  // Principal in the first month only
                    available_amount: available_amount,
                    amount: monthly_amount,
                };

                new_rows.push(new_row);
            }

            // Set the new rows in the child table
            child_table.df.data = new_rows;

            // Refresh the field to show the updated rows
            child_table.refresh();
        } else {
            // frappe.msgprint(__('Please make sure all required fields are filled.'));
        }
    }

});
