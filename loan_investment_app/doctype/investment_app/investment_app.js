function handle_transaction_type(frm) {
    // Hide all fields initially
    frm.toggle_display(['interest_rate', 'start_date', 'end_date', 'investment_period', 
        'schedule', 'investment_schedule', 'withhold_tax', 'total_interest_earned', 
        'total_amount_after_tax', 'amount_withrowned', 'interets_withrowned', 
        'withdral_amount', 'balance_walet', 'pay_to'], 0);

    if (!frm.doc.transaction_type) return;

    switch(frm.doc.transaction_type) {
        // ... other cases ...

        case 'Withdraw':
            // Show withdrawal-related fields
            frm.toggle_display(['withhold_tax', 'total_interest_earned', 
                'total_amount_after_tax', 'amount_withrowned', 'interets_withrowned', 
                'withdral_amount'], 1);
            if (!frm.doc.__notrigger) {
                frm.set_df_property('amount', 'label', 'Withdrawal Amount');
                frm.set_df_property('posting_date', 'reqd', 1);
                frm.set_df_property('amount_withrowned', 'reqd', 1);
                frm.set_df_property('total_interest_earned', 'reqd', 1);
                
                // Add field handlers for amount changes
                frm.fields_dict['amount_withrowned'].df.onchange = () => {
                    calculate_total_amount(frm);
                };
                frm.fields_dict['total_interest_earned'].df.onchange = () => {
                    calculate_total_amount(frm);
                };
            }
            break;

        // ... other cases ...
    }

    // Only refresh fields if not in notrigger mode
    if (!frm.doc.__notrigger) {
        frm.refresh_fields();
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

// ... rest of existing code ... 