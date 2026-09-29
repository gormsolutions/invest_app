import frappe
from frappe import _

@frappe.whitelist()
def create_journal_entry(posting_date, amount, party_type, party, mode_of_payment, trans_type, remarks, company=None):
    """
    Create journal entries specifically for deposits.
    This function is called from the main InvestmentApp class for deposit transactions.
    """
    try:
        if trans_type != "Deposit":
            return {"error": _("This API endpoint is only for deposit transactions")}
            
        # Get company from Investment Settings
        company = frappe.db.get_single_value('Investment Settings', 'company')
        if not company:
            return {"error": _("Company not configured in Investment Settings")}
        
        # Fetch the default account from the Mode of Payment Account child table
        default_paid_to_account = frappe.db.get_value(
            "Mode of Payment Account", 
            {"parent": mode_of_payment, "company": company}, 
            "default_account"
        )
        
        if not default_paid_to_account:
            return {"error": _("No default account found for the selected mode of payment")}
            
        # Get investment account for deposits
        invest_settings = frappe.get_single('Investment Settings')
        if not invest_settings:
            return {"error": _("Investment Settings not found")}
            
        capital_account = invest_settings.capital_account
        if not capital_account:
            return {"error": _("Capital account not configured in Investment Settings")}
            
        # Create Journal Entry
        journal_entry = frappe.new_doc('Journal Entry')
        journal_entry.voucher_type = 'Journal Entry'
        journal_entry.company = company
        journal_entry.posting_date = posting_date
        journal_entry.user_remark = remarks
        journal_entry.custom_transaction_type = 'Deposit'
        
        # Credit capital account
        journal_entry.append('accounts', {       
            'account': capital_account,
            'debit_in_account_currency': 0,
            'credit_in_account_currency': amount,
            'party_type': party_type,
            'party': party,
            'user_remark': remarks
        })
        
        # Debit payment account
        journal_entry.append('accounts', {
            'account': default_paid_to_account,
            'debit_in_account_currency': amount,
            'credit_in_account_currency': 0,
            'party_type': party_type,
            'party': party,
            'user_remark': remarks
        })

        # Insert and submit
        journal_entry.insert()
        journal_entry.submit()
        
        frappe.msgprint(_("Deposit journal entry created successfully"))
        return {
            "message": _("Deposit processed successfully!"), 
            "name": journal_entry.name,
            "status": "success"
        }
        
    except Exception as e:
        frappe.log_error(message=str(e), title=_("Deposit Journal Entry Error"))
        return {
            "error": _("Failed to create deposit entry: {0}").format(str(e)),
            "status": "error"
        }
