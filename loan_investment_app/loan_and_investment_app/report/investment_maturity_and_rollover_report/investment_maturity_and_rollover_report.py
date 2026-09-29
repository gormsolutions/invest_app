import frappe
from frappe import _
from frappe.utils import nowdate, getdate, flt, cint

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data)
    report_summary = get_report_summary(data)

    return columns, data, None, chart, report_summary

def get_columns():
    return [
        {
            "fieldname": "name",
            "label": _("Contract ID"),
            "fieldtype": "Link",
            "options": "Investment App",
            "width": 150
        },
        {
            "fieldname": "party_name",
            "label": _("Investor Name"),
            "fieldtype": "Data",
            "width": 210
        },
        {
            "fieldname": "party",
            "label": _("Member ID"),
            "fieldtype": "Link",
            "options": "Member",
            "width": 140
        },
        {
            "fieldname": "start_date",
            "label": _("Start Date"),
            "fieldtype": "Date",
            "width": 110
        },
        {
            "fieldname": "end_date",
            "label": _("Maturity Date"),
            "fieldtype": "Date",
            "width": 110
        },
        {
            "fieldname": "days_to_maturity",
            "label": _("Days to Maturity"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "maturity_status",
            "label": _("Status"),
            "fieldtype": "Data",
            "width": 140
        },
        {
            "fieldname": "investment_period",
            "label": _("Tenure"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "interest_rate",
            "label": _("Rate (% p.a.)"),
            "fieldtype": "Percent",
            "width": 100
        },
        {
            "fieldname": "amount",
            "label": _("Principal Invested"),
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "fieldname": "total_interest",
            "label": _("Expected Returns"),
            "fieldtype": "Currency",
            "width": 140
        },
        {
            "fieldname": "maturity_value",
            "label": _("Maturity Value"),
            "fieldtype": "Currency",
            "width": 160
        },
        {
            "fieldname": "investor_bank_name",
            "label": _("Bank"),
            "fieldtype": "Data",
            "width": 130
        },
        {
            "fieldname": "investor_account_number",
            "label": _("Account No."),
            "fieldtype": "Data",
            "width": 130
        }
    ]

def get_data(filters):
    today = nowdate()
    
    conditions = ["inv.docstatus = 1", "inv.transaction_type IN ('Invest', 'Re-invest')"]
    params = [today]

    if filters.get("party"):
        conditions.append("inv.party = %s")
        params.append(filters.get("party"))

    if filters.get("from_date"):
        conditions.append("inv.end_date >= %s")
        params.append(filters.get("from_date"))

    if filters.get("to_date"):
        conditions.append("inv.end_date <= %s")
        params.append(filters.get("to_date"))

    where_clause = " AND ".join(conditions)

    query = f"""
        SELECT 
            inv.name, inv.party_name, inv.party, inv.start_date, inv.end_date, 
            inv.investment_period, inv.amount, inv.interest_rate, 
            COALESCE(inv.percent_amount, 0) as total_interest,
            (inv.amount + COALESCE(inv.percent_amount, 0)) as maturity_value,
            inv.investor_bank_name, inv.investor_account_number,
            inv.investment_progression,
            DATEDIFF(inv.end_date, %s) as days_to_maturity
        FROM `tabInvestment App` inv
        WHERE {where_clause}
        ORDER BY inv.end_date ASC
    """

    raw_data = frappe.db.sql(query, tuple(params), as_dict=True)
    
    status_filter = filters.get("status")
    result = []

    for r in raw_data:
        days = cint(r.days_to_maturity)
        progression = r.investment_progression or ""

        if progression == "Withdrawn":
            mat_status = "Withdrawn"
        elif progression == "Rolled Over":
            mat_status = "Rolled Over"
        elif days < 0:
            mat_status = "Matured - Unsettled"
        elif days <= 30:
            mat_status = "Due in 30 Days"
        elif days <= 60:
            mat_status = "Due in 60 Days"
        elif days <= 90:
            mat_status = "Due in 90 Days"
        else:
            mat_status = "Active"

        r["maturity_status"] = mat_status

        # Filter handling
        if status_filter and status_filter != "All":
            if status_filter == "Active" and mat_status not in ["Active", "Due in 30 Days", "Due in 60 Days", "Due in 90 Days"]:
                continue
            elif status_filter == "Due in 30 Days" and mat_status != "Due in 30 Days":
                continue
            elif status_filter == "Due in 60 Days" and mat_status not in ["Due in 30 Days", "Due in 60 Days"]:
                continue
            elif status_filter == "Due in 90 Days" and mat_status not in ["Due in 30 Days", "Due in 60 Days", "Due in 90 Days"]:
                continue
            elif status_filter == "Matured - Unsettled" and mat_status != "Matured - Unsettled":
                continue
            elif status_filter == "Withdrawn" and mat_status != "Withdrawn":
                continue
            elif status_filter == "Rolled Over" and mat_status != "Rolled Over":
                continue

        result.append(r)

    return result

def get_chart_data(data):
    if not data:
        return None

    status_counts = {}
    for r in data:
        st = r.get("maturity_status")
        status_counts[st] = status_counts.get(st, 0) + 1

    labels = list(status_counts.keys())
    values = [status_counts[k] for k in labels]

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("Contracts"), "values": values}
            ]
        },
        "type": "donut",
        "colors": ["#10b981", "#f59e0b", "#ef4444", "#6b7280", "#8b5cf6"]
    }

def get_report_summary(data):
    if not data:
        return []

    active_sum = sum(flt(r.get("amount", 0)) for r in data if r.get("maturity_status") in ["Active", "Due in 30 Days", "Due in 60 Days", "Due in 90 Days"])
    matured_sum = sum(flt(r.get("amount", 0)) for r in data if r.get("maturity_status") == "Matured - Unsettled")
    due_30_sum = sum(flt(r.get("amount", 0)) for r in data if r.get("maturity_status") == "Due in 30 Days")

    return [
        {
            "value": active_sum,
            "label": _("Active Capital"),
            "datatype": "Currency",
            "indicator": "Green"
        },
        {
            "value": matured_sum,
            "label": _("Matured (Unsettled)"),
            "datatype": "Currency",
            "indicator": "Red"
        },
        {
            "value": due_30_sum,
            "label": _("Maturing in 30 Days"),
            "datatype": "Currency",
            "indicator": "Orange"
        },
        {
            "value": len(data),
            "label": _("Total Filtered Contracts"),
            "datatype": "Int",
            "indicator": "Blue"
        }
    ]
