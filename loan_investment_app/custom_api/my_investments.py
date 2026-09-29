import frappe
from frappe import _

@frappe.whitelist()
def fetch_investments_for_party():
    # Get the logged-in user
    user = frappe.session.user

    # Check if the logged-in user has the "Investor" role
    if "Investor" in frappe.get_roles(user):
        # Get the member name associated with the user
        party = frappe.db.get_value("Member", {"owner": user}, "name")
        
        # If no party is found, return an empty list or handle accordingly
        if not party:
            return []

        # Fetch investments related to the specific party
        return frappe.get_list(
            'Investment App',
            fields=['name', 'end_date', 'posting_date', 'amount','party_name'],  # Added 'amount' field
            filters={
                'party': party,  # Filter by the specific party
                'transaction_type': ['in', ['Re-invest', 'Invest']],
                'docstatus': ['!=', 2],  # Exclude canceled records
                'investment_status': 'Approved'
            }
        )

    # If the user does not have the "Investor" role, return an empty list
    return []


@frappe.whitelist()
def fetch_investments_for_party_amount(end_date):
    # Get the logged-in user
    user = frappe.session.user

    # Check if the logged-in user has the "Investor" role
    if "Investor" in frappe.get_roles(user):
        # Get the member name associated with the user
        party = frappe.db.get_value("Member", {"email_id": user}, "name")
        
        # If no party is found, return an empty list or handle accordingly
        if not party:
            return {
                "investments": [],
                "total_amount": 0,
                "total_percent_amount": 0,
                "grand_total": 0,
                'withdral_amount':0
            }

        # Define filters for the query
        filters = {
            'party': party,  # Filter by the specific party
            'transaction_type': ['in', ['Re-invest', 'Invest']],
            'docstatus': ['!=', 2],  # Exclude canceled records
            'investment_status': 'Approved'
        }

        # Add exact end_date filter if provided
        if end_date:
            filters['end_date'] = end_date  # Filter investments with exact end_date match

        # Fetch investments related to the specific party with exact end_date
        investments = frappe.get_list(
            'Investment App',
            fields=['name', 'end_date', 'posting_date', 'amount','withdral_amount', 'percent_amount', 'party_name'],
            filters=filters
        )

        # Calculate the total amount of investments and percent amounts
        total_amount = sum(investment['amount'] for investment in investments)
        total_percent_amount = sum(investment['percent_amount'] for investment in investments)
        withdral_amount = sum(investment['withdral_amount'] for investment in investments)

        # Calculate the grand total (total_amount + total_percent_amount)
        grand_total = total_amount + total_percent_amount

        # Return the list of investments, total amount, total percent amount, and grand total
        return {
            "investments": investments,
            "total_amount": total_amount,
            "total_percent_amount": total_percent_amount,
            "grand_total": grand_total,
            "withdral_amount": withdral_amount
        }

    # If the user does not have the "Investor" role, return an empty list and zero amounts
    return {
        "investments": [],
        "total_amount": 0,
        "total_percent_amount": 0,
        "grand_total": 0
    }


@frappe.whitelist()
def fetch_investments_party_amount(party=None, end_date=None):
    # If no party is provided, return an empty response
    if not party:
        return {
            "investments": [],
            "total_amount": 0,
            "total_percent_amount": 0,
            "grand_total": 0,
            "withdral_amount": 0
        }

    # Define filters for the query
    filters = {
        'party': party,
        'transaction_type': ['in', ['Re-invest', 'Invest']],
        'docstatus': 1,  # Only submitted
        'investment_status': 'Approved'
    }

    # Add end_date filter if provided
    if end_date:
        filters['end_date'] = end_date

    # Fetch investments related to the specific party with optional end_date
    investments = frappe.get_list(
        'Investment App',
        fields=['name', 'end_date', 'posting_date', 'amount', 'withdral_amount', 'percent_amount', 'party_name'],
        filters=filters
    )

    # Calculate totals
    total_amount = sum(investment['amount'] for investment in investments)
    total_percent_amount = sum(investment['percent_amount'] for investment in investments)
    withdral_amount = sum(investment['withdral_amount'] for investment in investments)

    grand_total = total_amount + total_percent_amount

    # Return the results
    return {
        "investments": investments,
        "total_amount": total_amount,
        "total_percent_amount": total_percent_amount,
        "grand_total": grand_total,
        "withdral_amount": withdral_amount
    }
