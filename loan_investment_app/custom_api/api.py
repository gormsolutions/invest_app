import frappe

@frappe.whitelist()
def get_amount_in_words(amount, currency=None):
    """Return amount in words, safe for client calls."""
    if not currency:
        company = frappe.db.get_single_value('Investment Settings', 'company')
        currency = frappe.db.get_value('Company', company, 'default_currency')
    return frappe.utils.money_in_words(amount, currency)