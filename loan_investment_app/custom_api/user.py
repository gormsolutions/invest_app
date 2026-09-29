import frappe
from frappe import _
from frappe.utils import today, flt, getdate, format_date
from datetime import datetime

def get_investor_party_for_user(user=None):
    """Resolve the Member record linked to the given user or current session user"""
    if not user:
        user = frappe.session.user
    if not user or user == "Guest":
        return None

    # 1. Lookup Member by email_id
    member = frappe.db.get_value("Member", {"email_id": user}, "name")
    if member:
        return member

    # 2. Lookup Member by owner
    member = frappe.db.get_value("Member", {"owner": user}, "name")
    if member:
        return member

    # 3. Lookup Member in User Permission
    perm = frappe.db.get_value("User Permission", {"user": user, "allow": "Member"}, "for_value")
    if perm:
        return perm

    return None


@frappe.whitelist()
def get_logged_in_user_info(party=None):
    """Get investor info, profile details and calculated balances"""
    user = frappe.session.user
    current_date = today()

    user_info = {
        "email": user,
        "current_date": current_date
    }

    # Resolve party
    target_party = party or get_investor_party_for_user(user)

    member_name = None
    custom_investor_account_number = None
    custom_investor_account_name = None
    custom_investor_bank_name = None
    balance_portfolia = 0
    balance_withdrawal_payable = 0
    balance_deposit = 0
    balance_interest = 0
    email_id = None
    pan_number = None
    membership_type = None
    custom_member_id = None
    amount_in_wallet = 0

    if target_party:
        member_data = frappe.db.sql("""
            SELECT name, member_name, email_id, custom_resident, membership_type, 
                   custom_investor_account_name, custom_investor_account_number, custom_investor_bank_name
            FROM `tabMember`
            WHERE name = %s
        """, (target_party,), as_dict=True)

        if member_data:
            m = member_data[0]
            member_name = m.member_name
            custom_investor_account_number = m.custom_investor_account_number
            custom_investor_account_name = m.custom_investor_account_name
            custom_investor_bank_name = m.custom_investor_bank_name
            email_id = m.email_id
            pan_number = m.custom_resident
            membership_type = m.membership_type
            custom_member_id = m.name

        accounts = frappe.db.sql("""
            SELECT portfolio_account, investment_interest, capital_account, investor_withdrawal_payable_account
            FROM `tabInvestment Settings`
        """, as_dict=True)

        if accounts:
            portfolia = accounts[0].portfolio_account
            withdrawal_payable = accounts[0].investor_withdrawal_payable_account
            deposit = accounts[0].capital_account
            interest = accounts[0].investment_interest

            balance_data = frappe.db.sql("""
                SELECT 
                    SUM(CASE WHEN account = %s THEN credit ELSE 0 END) AS total_credit_portfolia,
                    SUM(CASE WHEN account = %s THEN debit ELSE 0 END) AS total_debit_portfolia,
                    SUM(CASE WHEN account = %s THEN credit ELSE 0 END) AS total_credit_withdrawal,
                    SUM(CASE WHEN account = %s THEN debit ELSE 0 END) AS total_debit_withdrawal,
                    SUM(CASE WHEN account = %s THEN credit ELSE 0 END) AS total_credit_deposit,
                    SUM(CASE WHEN account = %s THEN debit ELSE 0 END) AS total_debit_deposit,
                    SUM(CASE WHEN account = %s THEN credit ELSE 0 END) AS total_credit_interest,
                    SUM(CASE WHEN account = %s THEN debit ELSE 0 END) AS total_debit_interest
                FROM `tabGL Entry`
                WHERE party_type = 'Member' AND party = %s AND docstatus = 1 AND is_cancelled = 0
            """, (
                portfolia, portfolia,
                withdrawal_payable, withdrawal_payable,
                deposit, deposit,
                interest, interest,
                target_party
            ), as_dict=True)

            if balance_data:
                d = balance_data[0]
                balance_portfolia = (d.total_credit_portfolia or 0) - (d.total_debit_portfolia or 0)
                balance_withdrawal_payable = (d.total_credit_withdrawal or 0) - (d.total_debit_withdrawal or 0)
                balance_deposit = (d.total_credit_deposit or 0) - (d.total_debit_deposit or 0)
                balance_interest = (d.total_credit_interest or 0) - (d.total_debit_interest or 0)
                amount_in_wallet = balance_interest + balance_portfolia

    return {
        "member": target_party,
        "current_date": current_date,
        "member_name": member_name,
        "custom_investor_account_number": custom_investor_account_number,
        "custom_investor_account_name": custom_investor_account_name,
        "custom_investor_bank_name": custom_investor_bank_name,
        "email_id": email_id,
        "custom_member_id": custom_member_id,
        "custom_resident": pan_number,
        "membership_type": membership_type,
        "balance_portfolia": abs(balance_portfolia),
        "balance_withdrawal_payable": abs(balance_withdrawal_payable),
        "balance_deposit": abs(balance_deposit),
        "balance_interest": abs(balance_interest),
        "balance_amount_in_wallet": abs(amount_in_wallet),
    }


@frappe.whitelist()
def get_investor_portal_data(party=None):
    """Full data payload for the Investor Portal: Profile, Metrics, Active Contracts, Schedules, Transactions, Inquiries"""
    user = frappe.session.user
    if user == "Guest":
        return {"is_guest": True}

    # If party is provided and user is Admin/Staff, allow viewing
    roles = frappe.get_roles(user)
    is_staff = any(r in ["System Manager", "Accounts Manager", "Investment User Staff", "Administrator"] for r in roles)
    
    target_party = party if (party and is_staff) else get_investor_party_for_user(user)

    if not target_party and is_staff:
        # Pick the most recent member with investments as default for admin preview
        recent = frappe.db.get_value("Investment App", {"docstatus": 1}, "party")
        target_party = recent or frappe.db.get_value("Member", {"membership_type": "Investor"}, "name")

    if not target_party:
        return {
            "is_guest": False,
            "has_investor_profile": False,
            "user_email": user,
            "message": "No Investor profile linked to this user account."
        }

    # 1. Profile & Balances
    profile = get_logged_in_user_info(target_party)

    # 2. Investments (Active & Matured)
    today_date = getdate(today())
    investments_raw = frappe.get_all(
        "Investment App",
        filters={
            "party": target_party,
            "docstatus": 1,
            "transaction_type": ["in", ["Invest", "Re-invest"]]
        },
        fields=[
            "name", "posting_date", "start_date", "end_date", "amount", 
            "interest_rate", "investment_period", "percent_amount", 
            "withdral_amount", "investment_status", "transaction_type"
        ],
        order_by="start_date desc"
    )

    active_investments = []
    total_active_principal = 0
    total_expected_returns = 0
    next_maturity = None

    for inv in investments_raw:
        end_d = getdate(inv.end_date) if inv.end_date else None
        is_matured = bool(end_d and end_d <= today_date)
        status = "Matured" if is_matured else "Active"
        
        if not is_matured:
            total_active_principal += flt(inv.amount)
            total_expected_returns += flt(inv.percent_amount)
            if end_d and (not next_maturity or end_d < next_maturity.get("date")):
                next_maturity = {
                    "date": end_d,
                    "date_str": format_date(end_d),
                    "amount": flt(inv.amount) + flt(inv.percent_amount),
                    "name": inv.name
                }

        active_investments.append({
            "name": inv.name,
            "posting_date": format_date(inv.posting_date),
            "start_date": format_date(inv.start_date) if inv.start_date else "-",
            "end_date": format_date(inv.end_date) if inv.end_date else "-",
            "raw_end_date": str(inv.end_date),
            "amount": flt(inv.amount),
            "interest_rate": flt(inv.interest_rate),
            "investment_period": inv.investment_period or "-",
            "expected_return": flt(inv.percent_amount),
            "maturity_value": flt(inv.amount) + flt(inv.percent_amount),
            "status": status,
            "is_matured": is_matured,
            "transaction_type": inv.transaction_type
        })

    # 3. Monthly Interest Accrual Schedules
    schedules_raw = frappe.db.sql("""
        SELECT s.name, s.parent, s.start_date, s.end_date, s.amount, s.posted_status,
               inv.party_name, inv.interest_rate
        FROM `tabInvestment Schedule` s
        JOIN `tabInvestment App` inv ON s.parent = inv.name
        WHERE inv.party = %s AND inv.docstatus = 1
        ORDER BY s.start_date DESC
    """, (target_party,), as_dict=True)

    active_inv_names = [i["name"] for i in active_investments if not i["is_matured"]]

    schedules = []
    total_accrued_posted = 0
    active_accrued_posted = 0
    for s in schedules_raw:
        if s.posted_status == "Posted":
            total_accrued_posted += flt(s.amount)
            if s.parent in active_inv_names:
                active_accrued_posted += flt(s.amount)
        schedules.append({
            "name": s.name,
            "investment": s.parent,
            "start_date": format_date(s.start_date) if s.start_date else "-",
            "end_date": format_date(s.end_date) if s.end_date else "-",
            "amount": flt(s.amount),
            "posted_status": s.posted_status or "Pending",
            "rate": flt(s.interest_rate)
        })

    # Calculate pro-rata accrued return to date for active contracts
    active_prorata_accrued = 0
    for inv in investments_raw:
        end_d = getdate(inv.end_date) if inv.end_date else None
        start_d = getdate(inv.start_date) if inv.start_date else None
        is_matured = bool(end_d and end_d <= today_date)
        if not is_matured and start_d and end_d:
            days_active = max(0, (today_date - start_d).days)
            days_total = max(1, (end_d - start_d).days)
            active_prorata_accrued += min(flt(inv.percent_amount), flt(inv.percent_amount) * (days_active / days_total))

    active_accrued_returns = active_accrued_posted if active_accrued_posted > 0 else round(active_prorata_accrued, 2)

    # 4. Full Transactions History
    transactions_raw = frappe.get_all(
        "Investment App",
        filters={
            "party": target_party,
            "docstatus": 1
        },
        fields=[
            "name", "transaction_type", "posting_date", "amount", 
            "investment_status", "mode_of_payment", "start_date", "end_date"
        ],
        order_by="posting_date desc, creation desc"
    )

    transactions = []
    for t in transactions_raw:
        transactions.append({
            "name": t.name,
            "type": t.transaction_type,
            "date": format_date(t.posting_date),
            "amount": flt(t.amount),
            "status": t.investment_status,
            "mode": t.mode_of_payment or "Bank Transfer",
            "period": f"{format_date(t.start_date)} to {format_date(t.end_date)}" if (t.start_date and t.end_date) else "-"
        })

    # 5. Investor Support Inquiries (Issues raised by this user or for this party)
    inquiries_raw = frappe.get_all(
        "Issue",
        filters={"raised_by": user},
        fields=["name", "subject", "status", "priority", "creation", "resolution_details"],
        order_by="creation desc"
    )

    inquiries = []
    for i in inquiries_raw:
        inquiries.append({
            "name": i.name,
            "subject": i.subject,
            "status": i.status,
            "priority": i.priority,
            "date": format_date(i.creation),
            "response": i.resolution_details or "Under review by AMGL Investment & Treasury Team."
        })

    return {
        "is_guest": False,
        "has_investor_profile": True,
        "is_staff": is_staff,
        "profile": profile,
        "metrics": {
            "total_active_principal": total_active_principal,
            "active_accrued_returns": active_accrued_returns,
            "active_posted_returns": active_accrued_posted,
            "active_expected_returns": total_expected_returns,
            "active_prorata_accrued": round(active_prorata_accrued, 2),
            "total_accrued_returns": total_accrued_posted,
            "wallet_balance": profile.get("balance_withdrawal_payable", 0),
            "total_portfolio_value": total_active_principal + active_accrued_returns,
            "active_contracts_count": len([i for i in active_investments if not i["is_matured"]]),
            "next_maturity": next_maturity
        },
        "investments": active_investments,
        "schedules": schedules,
        "transactions": transactions,
        "inquiries": inquiries
    }


@frappe.whitelist()
def download_investment_certificate(investment_name):
    """Securely generate and stream the official Investment Certificate PDF"""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Please log in to download your investment certificate"), frappe.PermissionError)

    if not investment_name:
        frappe.throw(_("Investment ID is required"))

    doc = frappe.get_doc("Investment App", investment_name)

    # Permission verification
    roles = frappe.get_roles(user)
    is_staff = any(r in ["System Manager", "Accounts Manager", "Investment User Staff", "Administrator"] for r in roles)

    if not is_staff:
        user_party = get_investor_party_for_user(user)
        if doc.party != user_party and doc.owner != user:
            frappe.throw(_("Unauthorized: You do not have permission to download this certificate"), frappe.PermissionError)

    # Generate single-page PDF using 'Cert Print' format without external letterhead
    from frappe.utils.pdf import get_pdf
    html = frappe.get_print("Investment App", investment_name, print_format="Cert Print", as_pdf=False, no_letterhead=1)
    pdf = get_pdf(html)

    frappe.local.response.filename = f"AMGL_Investment_Certificate_{doc.name}.pdf"
    frappe.local.response.filecontent = pdf
    frappe.local.response.type = "pdf"


@frappe.whitelist()
def submit_investor_inquiry(subject, message, investment_name=None, category=None):
    """Allows an investor to submit a support request or request clarification on their investment"""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Please log in to submit a support request"), frappe.PermissionError)

    if not subject or not message:
        frappe.throw(_("Please provide both subject and message"))

    party = get_investor_party_for_user(user)
    member_name = frappe.db.get_value("Member", party, "member_name") if party else user

    # Create Issue
    issue = frappe.new_doc("Issue")
    issue.subject = f"[Investor Support] {subject}"
    issue.raised_by = user
    issue.priority = "Medium"
    issue.status = "Open"
    
    desc_lines = [
        f"<b>Investor:</b> {member_name} ({user})",
        f"<b>Member ID:</b> {party or 'N/A'}",
        f"<b>Category:</b> {category or 'General Inquiry'}",
        f"<b>Related Investment:</b> {investment_name or 'N/A'}",
        "<hr>",
        f"<b>Message:</b><br>{message}"
    ]
    issue.description = "<br>".join(desc_lines)
    issue.flags.ignore_mandatory = True
    issue.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "ticket_id": issue.name,
        "message": f"Your inquiry has been submitted successfully (Ticket: #{issue.name}). An AMGL investment specialist will respond shortly."
    }


@frappe.whitelist()
def get_party_name(party):
    member_name = ""
    if party:
        member_data = frappe.db.sql("""
            SELECT member_name FROM `tabMember` WHERE name = %s
        """, (party,), as_dict=True)
        if member_data and member_data[0].get('member_name'):
            member_name = member_data[0]['member_name']
    return {"member_name": member_name}


@frappe.whitelist()
def fetch_investment_schedule(start_date=None, end_date=None):
    user = frappe.session.user
    party = get_investor_party_for_user(user)
    if not party:
        return None

    member_data = frappe.db.sql("SELECT member_name, name FROM `tabMember` WHERE name = %s", (party,), as_dict=True)
    if not member_data:
        return None

    member_name = member_data[0].name
    investment_schedule_data = frappe.db.sql("""
        SELECT inv_schedule.*
        FROM `tabInvestment Schedule` inv_schedule
        JOIN `tabInvestment App` inv_app ON inv_schedule.parent = inv_app.name
        WHERE inv_app.party = %s
        AND inv_app.docstatus = 1
        AND inv_app.investment_status = 'Approved'
        AND inv_app.transaction_type IN ('Re-invest', 'Invest')
        ORDER BY inv_schedule.start_date ASC
    """, (member_name,), as_dict=True)

    total_percent_amount = 0
    if start_date and end_date:
        s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        e_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        for schedule in investment_schedule_data:
            sch_start = schedule['start_date']
            sch_end = schedule['end_date']
            if isinstance(sch_start, datetime):
                sch_start = sch_start.date()
            if isinstance(sch_end, datetime):
                sch_end = sch_end.date()
            if (s_date <= sch_end) and (e_date >= sch_start):
                total_percent_amount += flt(schedule.get('amount', 0))

    return {
        "member_name": member_name,
        "investment_schedule_data": investment_schedule_data,
        "total_percent_amount": total_percent_amount
    }


@frappe.whitelist()
def get_member_info(party):
    return get_logged_in_user_info(party)
