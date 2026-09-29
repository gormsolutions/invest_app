import frappe
from frappe.utils import today, nowdate, getdate, flt

@frappe.whitelist()
def get_logged_in_user_info():
    user = frappe.get_doc("User", frappe.session.user)
    current_date = today()
    
    user_info = {
        "email": user.email,
        "current_date": current_date
    }
    
    # Fetch user permissions related to the investment account where 'allow' is 'Member'
    investment_account = frappe.db.sql("""
        SELECT for_value, allow, user
        FROM `tabUser Permission`
        WHERE user = %s AND allow = 'Member'
    """, (user_info["email"],), as_dict=True)

    # Initialize member_name as None
    member_name = None

    # Fetch member name if an investment account was found
    if investment_account:
        member_data = frappe.db.sql("""
            SELECT member_name
            FROM `tabMember`
            WHERE name = %s
        """, (investment_account[0].for_value,), as_dict=True)

        # Check if member_data is found and set member_name
        if member_data:
            member_name = member_data[0].member_name

    user_info2 = {
        "member": investment_account[0].for_value if investment_account else None,
        "current_date": current_date,
        "member_name": member_name
    }

    return user_info2

def get_context(context, posting_date=None):
    # Get the logged-in user's information
    user_info = get_logged_in_user_info()
    specific_party = user_info['member']  # Filter by the logged-in user's member
    
    frappe.logger().debug(f"User Info: {user_info}")
    frappe.logger().debug(f"Specific Party: {specific_party}")

    # Fetch report data from the 'Investment App' doctype for the specific party
    investments = frappe.get_list(
        'Investment App',
        fields=['name', 'party_name', 'party', 'posting_date', 'transaction_type', 'amount'],
        filters={
            'party': specific_party,
            'transaction_type': ['in', ['Re-invest', 'Invest']],
            'docstatus': ['!=', 2],  # Exclude canceled records
            'investment_status': 'Approved'
        },
        limit_page_length=50
    )
    
    frappe.logger().debug(f"Found Investments: {investments}")

    total_interest = 0
    total_available = 0
    total_principal = 0

    current_date = nowdate()
    frappe.logger().debug(f"Current Date: {current_date}")

    # Fetch investment schedule for each investment
    for investment in investments:
        schedules = frappe.get_all(
            'Investment Schedule',
            fields=['start_date', 'end_date', 'principal_amount', 'amount', 'available_amount', 'posted_status'],
            filters={
                'parent': investment['name'],
                'posted_status': ['in', ['Posted', 'Pending']]  # Only fetch posted schedules
            }
        )
        frappe.logger().debug(f"Found posted schedules for {investment['name']}: {schedules}")

        # Add all posted schedules
        investment['investment_schedule'] = []
        for schedule in schedules:
            try:
                investment['investment_schedule'].append(schedule)
                total_interest += flt(schedule['amount'])
                total_available += flt(schedule['available_amount'])
                total_principal += flt(schedule['principal_amount'])
            except Exception as e:
                frappe.logger().error(f"Error processing schedule: {str(e)}")

        frappe.logger().debug(f"Added posted schedules for {investment['name']}: {investment['investment_schedule']}")

    available_amount = total_principal + total_interest
    
    
    frappe.logger().debug(f"Totals - Principal: {total_principal}, Interest: {total_interest}, Available: {available_amount}")

    context.report_data = investments
    context.total_interest = total_interest
    context.total_available = available_amount
    context.total_principal = total_principal
    context.title = "Investment Schedule Report"
