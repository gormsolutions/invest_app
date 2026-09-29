import frappe
from frappe import _
from loan_investment_app.custom_api.user import get_investor_portal_data, get_investor_party_for_user

def get_context(context):
    context.no_cache = 1
    context.title = "AMGL Investor Portal"
    
    user = frappe.session.user
    if user == "Guest":
        context.is_guest = True
        context.login_url = f"/login?redirect-to=/investment-app"
        return context

    # Admin/Staff party switch
    requested_party = frappe.form_dict.get("party")
    data = get_investor_portal_data(requested_party)

    context.update(data)

    # If user is staff/admin, fetch list of all investors so they can view any investor portfolio
    if data.get("is_staff"):
        context.all_investors = frappe.db.sql("""
            SELECT name, member_name, email_id 
            FROM `tabMember` 
            WHERE name IN (SELECT DISTINCT party FROM `tabInvestment App` WHERE docstatus=1)
            ORDER BY member_name ASC
        """, as_dict=True)
        context.current_party = requested_party or data.get("profile", {}).get("member")

    return context
