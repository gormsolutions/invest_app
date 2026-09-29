import frappe
def validate_withdrawal(self):
    """Validate withdrawal amount and investment end dates."""
    try:
        # Use get_current_date() for consistent date handling
        current_date = get_current_date()
        if getdate(self.posting_date) > current_date:
            frappe.throw(_("You cannot withdraw funds beyond today's date ({0}).").format(
                frappe.format_value(current_date, {"fieldtype": "Date"})
            ))

        # Validate withdrawal amounts
        if self.transaction_type == "Withdraw":
            # Validate required fields
            if not flt(self.amount_withrowned):
                frappe.throw(_("Principal Amount Withdrawn is required"))
            if not flt(self.total_interest_earned):
                frappe.throw(_("Total Interest Earned is required"))
            
            # Set derived values
            self.interets_withrowned = flt(self.total_interest_earned)
            self.total_amount_after_tax = flt(self.amount_withrowned) + flt(self.total_interest_earned)

        # Get the logged-in user
        user = frappe.session.user

        # Skip validation for users without the "Investor" role and administrators
        if not "Investor" in frappe.get_roles(user) or "Administrator" in frappe.get_roles(user):
            frappe.logger().debug(f"User {user} is either not an Investor or is an Administrator, skipping investment validation")
            return

        # Fetch investments for validation
        investments = self.fetch_investments_for_party()
        if not investments:
            frappe.throw(_("No approved investments found for withdrawal."))

        # Extract posting date details
        posting_date = getdate(self.posting_date)
        posting_year = posting_date.year
        posting_month = posting_date.month

        # Flag to track valid investment found
        valid_investment_found = False

        # Validate against investment end dates
        for investment in investments:
            investment_end_date = getdate(investment["end_date"])
            if (investment_end_date.year == posting_year and 
                investment_end_date.month == posting_month and 
                posting_date >= investment_end_date):
                valid_investment_found = True
                break

        if not valid_investment_found:
            frappe.throw(_(
                "No valid investments found for withdrawal on {0}. Please ensure your withdrawal date matches an investment's end date."
            ).format(frappe.format_value(posting_date, {"fieldtype": "Date"})))

    except Exception as e:
        frappe.logger().error(f"Withdrawal validation error: {str(e)}")
        frappe.throw(_("Error validating withdrawal: {0}").format(str(e)))

def create_journal_entry(self):
    try:
        if self.transaction_type == "Deposit":
            return self.create_deposit_journal_entry()

        # For other transaction types, use internal logic
        company, default_paid_to_account = self.get_default_company_and_account()
        accounts = self.get_investment_accounts()

        journal_entry = frappe.new_doc('Journal Entry')
        journal_entry.voucher_type = 'Journal Entry'
        journal_entry.company = accounts['company_set']
        journal_entry.posting_date = self.posting_date
        journal_entry.user_remark = self.remarks
        journal_entry.custom_transaction_type = self.transaction_type
        journal_entry.custom_investmet_id = self.name

        if self.transaction_type == "Invest":
            # Only post principal movement
            self.add_journal_entry_row(journal_entry, accounts['capital_account'], self.amount, 0, cost_center=accounts['cost_center'])
            self.add_journal_entry_row(journal_entry, accounts['portfolio_account'], 0, self.amount, cost_center=accounts['cost_center'])
            frappe.msgprint(_("Principal amount posted successfully. Interest will be posted monthly according to schedule."))

        elif self.transaction_type == "Re-invest":
            # Only post principal movement for reinvestment
            self.add_journal_entry_row(journal_entry, accounts['withdrawal_payable_account'], self.amount, 0, cost_center=accounts['cost_center'])
            self.add_journal_entry_row(journal_entry, accounts['portfolio_account'], 0, self.amount, cost_center=accounts['cost_center'])
            frappe.msgprint(_("Principal amount posted successfully. Interest will be posted monthly according to schedule."))

        elif self.transaction_type == "Withdraw":
            # Handle withdrawal with updated amounts
            # 1. Credit Investor Withdrawal Payable Account with total amount (Principal + Interest)
            self.add_journal_entry_row(journal_entry, accounts['withdrawal_payable_account'], 0, self.total_amount_after_tax, cost_center=accounts['cost_center'])
            
            # 2. Debit Investment Portfolio Account with Principal amount
            self.add_journal_entry_row(journal_entry, accounts['portfolio_account'], self.amount_withrowned, 0, cost_center=accounts['cost_center'])
            
            # 3. Debit Interest on Investment Payable Account with Interest amount
            if self.total_interest_earned:
                self.add_journal_entry_row(journal_entry, accounts['investment_interest'], self.total_interest_earned, 0, cost_center=accounts['cost_center'])

        elif self.transaction_type == "Request for Payments":
            self.add_journal_entry_row(journal_entry, accounts['withdrawal_payable_account'], self.amount, 0, cost_center=accounts['cost_center'])
            self.add_journal_entry_row(journal_entry, self.pay_to, 0, self.amount, cost_center=accounts['cost_center'])

        else:
            frappe.throw(_("Invalid transaction type: {0}").format(self.transaction_type))

        journal_entry.insert()
        journal_entry.submit()
        return {"message": _("Journal Entry created successfully!"), "name": journal_entry.name}

    except Exception as e:
        frappe.log_error(message=str(e), title=_("Failed to create Journal Entry"))
        frappe.throw(_("Failed to create Journal Entry: {0}").format(str(e)))

def validate(self):
    # Ensure transaction type is set
    if not self.transaction_type:
        frappe.throw(_("Please select the transaction type of your choice."))

    # Ensure that the amount is not negative or None
    if self.amount is None:
        frappe.throw(_("The transaction amount cannot be empty."))

    if self.amount <= 0:
        frappe.throw(_("The transaction amount should be a positive value."))

    # Validate investment amount against deposits
    if self.transaction_type == "Invest":
        deposit_info = get_total_deposits(self.party)
        available_for_investment = deposit_info["total_deposits"] - deposit_info["total_investments"]
        
        if self.amount > available_for_investment:
            frappe.throw(_(
                "You can only invest up to {0}. Current deposits: {1}, Already invested: {2}"
            ).format(
                frappe.format_value(available_for_investment, {"fieldtype": "Currency"}),
                frappe.format_value(deposit_info["total_deposits"], {"fieldtype": "Currency"}),
                frappe.format_value(deposit_info["total_investments"], {"fieldtype": "Currency"})
            ))

    # Set amount in words
    self.set_amount_in_words()

    # Fetch account balances for all transaction types
    self.fetch_account_balances()

    # Validate based on transaction type
    if self.transaction_type == "Re-invest":
        if not self.balance_walet:
            frappe.throw(_("Wallet balance is not available. Please check your account settings."))
            
        if flt(self.amount) > flt(self.balance_walet):
            frappe.throw(_("The amount {0} cannot exceed the available amount {1} in the Wallet Account.").format(
                flt(self.amount), flt(self.balance_walet)
            ))
    elif self.transaction_type == "Request for Payments":
        self.validate_payment_request()
    elif self.transaction_type == "Withdraw":
        # Validate withdrawal amounts
        if not flt(self.amount_withrowned):
            frappe.throw(_("Principal Amount Withdrawn is required"))
        if not flt(self.total_interest_earned):
            frappe.throw(_("Total Interest Earned is required"))
        
        # Set derived values
        self.interets_withrowned = flt(self.total_interest_earned)
        self.total_amount_after_tax = flt(self.amount_withrowned) + flt(self.total_interest_earned)
        
        # Validate withdrawal dates and investments
        current_date = get_current_date()
        if getdate(self.posting_date) > current_date:
            frappe.throw(_("You cannot withdraw funds beyond today's date ({0}).").format(
                frappe.format_value(current_date, {"fieldtype": "Date"})
            ))

        # Get the logged-in user
        user = frappe.session.user

        # Skip validation for users without the "Investor" role and administrators
        if not "Investor" in frappe.get_roles(user) or "Administrator" in frappe.get_roles(user):
            frappe.logger().debug(f"User {user} is either not an Investor or is an Administrator, skipping investment validation")
            return

        # Fetch investments for validation
        investments = self.fetch_investments_for_party()
        if not investments:
            frappe.throw(_("No approved investments found for withdrawal."))

        # Extract posting date details
        posting_date = getdate(self.posting_date)
        posting_year = posting_date.year
        posting_month = posting_date.month

        # Flag to track valid investment found
        valid_investment_found = False

        # Validate against investment end dates
        for investment in investments:
            investment_end_date = getdate(investment["end_date"])
            if (investment_end_date.year == posting_year and 
                investment_end_date.month == posting_month and 
                posting_date >= investment_end_date):
                valid_investment_found = True
                break

        if not valid_investment_found:
            frappe.throw(_(
                "No valid investments found for withdrawal on {0}. Please ensure your withdrawal date matches an investment's end date."
            ).format(frappe.format_value(posting_date, {"fieldtype": "Date"})))

    # Set default investment status if not already set
    if not self.investment_status:
        self.investment_status = "Received"

    # Additional validation for submission
    if self._action == "submit":
        self.validate_on_submit() 