import frappe
from frappe.utils import nowdate, add_days, flt, cint

@frappe.whitelist()
def get_active_aum(filters=None):
    """Returns the total principal invested in active contracts (end_date >= today)"""
    today = nowdate()
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM `tabInvestment App`
        WHERE docstatus = 1
          AND transaction_type IN ('Invest', 'Re-invest')
          AND investment_status = 'Approved'
          AND end_date >= %s
    """, (today,), as_dict=True)
    val = flt(result[0].total) if result else 0.0
    return {
        "value": val,
        "fieldtype": "Currency",
        "route": ["List", "Investment App"],
        "route_options": {
            "docstatus": 1,
            "transaction_type": ["in", ["Invest", "Re-invest"]],
            "investment_progression": "Active"
        }
    }

@frappe.whitelist()
def get_active_contracts_count(filters=None):
    """Returns the count of active contracts (end_date >= today)"""
    today = nowdate()
    result = frappe.db.sql("""
        SELECT COUNT(*) as count
        FROM `tabInvestment App`
        WHERE docstatus = 1
          AND transaction_type IN ('Invest', 'Re-invest')
          AND investment_status = 'Approved'
          AND end_date >= %s
    """, (today,), as_dict=True)
    count = cint(result[0].count) if result else 0
    return {
        "value": count,
        "fieldtype": "Int",
        "route": ["List", "Investment App"],
        "route_options": {
            "docstatus": 1,
            "transaction_type": ["in", ["Invest", "Re-invest"]],
            "investment_progression": "Active"
        }
    }

@frappe.whitelist()
def get_matured_aum(filters=None):
    """Returns the total principal in matured contracts (end_date < today)"""
    today = nowdate()
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM `tabInvestment App`
        WHERE docstatus = 1
          AND transaction_type IN ('Invest', 'Re-invest')
          AND investment_status = 'Approved'
          AND end_date < %s
    """, (today,), as_dict=True)
    val = flt(result[0].total) if result else 0.0
    return {
        "value": val,
        "fieldtype": "Currency",
        "route": ["List", "Investment App"],
        "route_options": {
            "docstatus": 1,
            "transaction_type": ["in", ["Invest", "Re-invest"]],
            "investment_progression": "Matured"
        }
    }

@frappe.whitelist()
def get_maturing_30_days(filters=None):
    """Returns principal maturing within the next 30 days"""
    today = nowdate()
    future_30 = add_days(today, 30)
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM `tabInvestment App`
        WHERE docstatus = 1
          AND transaction_type IN ('Invest', 'Re-invest')
          AND investment_status = 'Approved'
          AND end_date >= %s
          AND end_date <= %s
    """, (today, future_30), as_dict=True)
    val = flt(result[0].total) if result else 0.0
    return {
        "value": val,
        "fieldtype": "Currency",
        "route": ["query-report", "Investment Maturity and Rollover Report"],
        "route_options": {
            "status": "Due in 30 Days"
        }
    }

@frappe.whitelist()
def get_pending_payouts_count(filters=None):
    """Returns count of unapproved draft withdrawal and payout requests (docstatus = 0)"""
    result = frappe.db.sql("""
        SELECT COUNT(*) as count
        FROM `tabInvestment App`
        WHERE docstatus = 0
          AND transaction_type IN ('Request for Payments', 'Withdraw')
    """, as_dict=True)
    count = cint(result[0].count) if result else 0
    return {
        "value": count,
        "fieldtype": "Int",
        "route": ["List", "Investment App"],
        "route_options": {
            "docstatus": 0,
            "transaction_type": ["in", ["Request for Payments", "Withdraw"]]
        }
    }

@frappe.whitelist()
def sync_contract_lifecycle():
    """
    Evaluates all submitted contracts against end_date and updates investment_progression:
    - 'Active' if end_date >= today
    - 'Matured' if end_date < today (and not already withdrawn/rolled over)
    Can be run daily via hooks.py or triggered manually.
    """
    today = nowdate()
    contracts = frappe.get_all(
        "Investment App",
        filters={
            "docstatus": 1,
            "transaction_type": ["in", ["Invest", "Re-invest"]]
        },
        fields=["name", "end_date", "investment_progression"]
    )
    
    updated_active = 0
    updated_matured = 0
    
    for c in contracts:
        if not c.end_date:
            continue
            
        current_progression = c.investment_progression or ""
        if current_progression in ["Withdrawn", "Rolled Over"]:
            continue
            
        new_status = "Matured" if str(c.end_date) < str(today) else "Active"
        
        if current_progression != new_status:
            frappe.db.set_value("Investment App", c.name, "investment_progression", new_status, update_modified=False)
            if new_status == "Active":
                updated_active += 1
            else:
                updated_matured += 1
                
    frappe.db.commit()
    return {
        "status": "success",
        "updated_active": updated_active,
        "updated_matured": updated_matured,
        "total_evaluated": len(contracts)
    }
