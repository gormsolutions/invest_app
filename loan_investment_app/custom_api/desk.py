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


# ==============================================================================
# INVESTORS MODULE MATURITY REMINDERS (30, 15, 7, 3 DAYS) FOR FINANCE MANAGERS
# ==============================================================================

MILESTONES_CONFIG = {
    30: {
        "days": 30,
        "name": "INVESTMENT NOTIFICATION ( 30 DAYS TO THE END OF THE INVESTMENT PERIOD )",
        "subject": "[Maturity: 30 Days] Investment Contract {{ doc.name }} - {{ doc.party_name }}",
        "badge_text": "30 Days Notice",
        "badge_bg": "#eff6ff",
        "badge_color": "#1d4ed8",
        "theme_color": "#2563eb",
        "action_advice": "This investment contract is due to mature in 30 days. Please reach out to the investor to confirm rollover preference or prepare settlement allocation."
    },
    15: {
        "days": 15,
        "name": "INVESTMENT NOTIFICATION ( 15 DAYS TO THE END OF THE INVESTMENT PERIOD )",
        "subject": "[Maturity: 15 Days] Investment Contract {{ doc.name }} - {{ doc.party_name }}",
        "badge_text": "15 Days Notice",
        "badge_bg": "#fef3c7",
        "badge_color": "#b45309",
        "theme_color": "#d97706",
        "action_advice": "This investment contract is due to mature in 15 days. Please confirm the investor's rollover instructions or finalize liquidity planning."
    },
    7: {
        "days": 7,
        "name": "INVESTMENT NOTIFICATION ( 7 DAYS TO THE END OF THE INVESTMENT PERIOD )",
        "subject": "[Maturity: 7 Days] Investment Contract {{ doc.name }} - {{ doc.party_name }}",
        "badge_text": "7 Days Notice",
        "badge_bg": "#ffedd5",
        "badge_color": "#c2410c",
        "theme_color": "#ea580c",
        "action_advice": "This investment contract is due to mature in 7 days. Please verify the investor's settlement bank details and obtain required management disbursement approvals."
    },
    3: {
        "days": 3,
        "name": "INVESTMENT NOTIFICATION ( 3 DAYS TO THE END OF THE INVESTMENT PERIOD )",
        "subject": "[URGENT: 3 Days] Investment Contract {{ doc.name }} - {{ doc.party_name }}",
        "badge_text": "CRITICAL: 3 Days Notice",
        "badge_bg": "#fee2e2",
        "badge_color": "#b91c1c",
        "theme_color": "#dc2626",
        "action_advice": "URGENT ACTION REQUIRED: The investment contract matures in 3 calendar days (72 hours). Payout liquidation or rollover clearance must be finalized immediately."
    }
}

def get_maturity_html_template(days, badge_text, badge_bg, badge_color, theme_color, action_advice):
    """Generates corporate styled responsive HTML notification template."""
    return f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
    <div style="background-color: #0f172a; padding: 24px 28px; text-align: left;">
        <span style="display: inline-block; background-color: {badge_bg}; color: {badge_color}; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; padding: 4px 10px; border-radius: 12px; margin-bottom: 10px;">{badge_text}</span>
        <h2 style="margin: 0; color: #ffffff; font-size: 19px; font-weight: 700;">Investment Maturity Reminder</h2>
        <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 13px;">Metro Group Portfolio Management &bull; Finance Team Alert</p>
    </div>
    
    <div style="padding: 24px 28px;">
        <div style="background-color: #f8fafc; border-left: 4px solid {theme_color}; padding: 12px 16px; border-radius: 4px; margin-bottom: 20px;">
            <p style="margin: 0; font-size: 14px; line-height: 1.5; color: #334155;">
                <strong>Notice for Finance Managers:</strong> {action_advice}
            </p>
        </div>

        <h3 style="margin: 0 0 12px 0; font-size: 14px; color: #0f172a; text-transform: uppercase; letter-spacing: 0.03em;">Contract Details</h3>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 13px;">
            <tr>
                <td style="padding: 8px 0; color: #64748b; border-bottom: 1px solid #f1f5f9; width: 40%;">Contract ID</td>
                <td style="padding: 8px 0; font-weight: 600; color: #0f172a; border-bottom: 1px solid #f1f5f9; text-align: right;">{{{{ doc.name }}}}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #64748b; border-bottom: 1px solid #f1f5f9;">Investor Name</td>
                <td style="padding: 8px 0; font-weight: 600; color: #0f172a; border-bottom: 1px solid #f1f5f9; text-align: right;">{{{{ doc.party_name }}}}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #64748b; border-bottom: 1px solid #f1f5f9;">Member ID</td>
                <td style="padding: 8px 0; font-weight: 600; color: #0f172a; border-bottom: 1px solid #f1f5f9; text-align: right;">{{{{ doc.party }}}}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #64748b; border-bottom: 1px solid #f1f5f9;">Tenure / Period</td>
                <td style="padding: 8px 0; font-weight: 600; color: #0f172a; border-bottom: 1px solid #f1f5f9; text-align: right;">{{{{ doc.investment_period or '-' }}}}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #64748b; border-bottom: 1px solid #f1f5f9;">Start Date</td>
                <td style="padding: 8px 0; font-weight: 600; color: #0f172a; border-bottom: 1px solid #f1f5f9; text-align: right;">{{{{ doc.get_formatted("start_date") }}}}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #64748b; border-bottom: 1px solid #f1f5f9;">Maturity Date</td>
                <td style="padding: 8px 0; font-weight: 700; color: {theme_color}; border-bottom: 1px solid #f1f5f9; text-align: right;">{{{{ doc.get_formatted("end_date") }}}}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; color: #64748b; border-bottom: 1px solid #f1f5f9;">Interest Rate (% p.a.)</td>
                <td style="padding: 8px 0; font-weight: 600; color: #0f172a; border-bottom: 1px solid #f1f5f9; text-align: right;">{{{{ doc.interest_rate }}}}%</td>
            </tr>
        </table>

        <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 14px 18px; margin-bottom: 20px;">
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <tr>
                    <td style="color: #166534; padding: 4px 0;">Principal Invested:</td>
                    <td style="font-weight: 600; color: #166534; text-align: right; padding: 4px 0;">{{{{ doc.get_formatted("amount") }}}}</td>
                </tr>
                <tr>
                    <td style="color: #166534; padding: 4px 0;">Expected Interest Returns:</td>
                    <td style="font-weight: 600; color: #166534; text-align: right; padding: 4px 0;">{{{{ doc.get_formatted("percent_amount") }}}}</td>
                </tr>
                <tr style="border-top: 1px solid #86efac;">
                    <td style="color: #14532d; font-weight: 700; padding: 8px 0 2px 0; font-size: 14px;">Total Maturity Value:</td>
                    <td style="color: #14532d; font-weight: 800; text-align: right; padding: 8px 0 2px 0; font-size: 16px;">{{{{ frappe.format_value((doc.amount or 0) + (doc.percent_amount or 0), {{"fieldtype": "Currency"}}) }}}}</td>
                </tr>
            </table>
        </div>

        <h3 style="margin: 0 0 10px 0; font-size: 14px; color: #0f172a; text-transform: uppercase; letter-spacing: 0.03em;">Settlement Banking Details</h3>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 24px; font-size: 13px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px;">
            <tr>
                <td style="padding: 8px 12px; color: #64748b; width: 40%; border-bottom: 1px solid #e2e8f0;">Bank Name:</td>
                <td style="padding: 8px 12px; font-weight: 600; color: #0f172a; border-bottom: 1px solid #e2e8f0; text-align: right;">{{{{ doc.investor_bank_name or '-' }}}}</td>
            </tr>
            <tr>
                <td style="padding: 8px 12px; color: #64748b; border-bottom: 1px solid #e2e8f0;">Account Number:</td>
                <td style="padding: 8px 12px; font-weight: 600; color: #0f172a; border-bottom: 1px solid #e2e8f0; text-align: right; font-family: monospace; font-size: 14px;">{{{{ doc.investor_account_number or '-' }}}}</td>
            </tr>
            <tr>
                <td style="padding: 8px 12px; color: #64748b;">Account Name:</td>
                <td style="padding: 8px 12px; font-weight: 600; color: #0f172a; text-align: right;">{{{{ doc.investor_account_name or '-' }}}}</td>
            </tr>
        </table>

        <div style="text-align: center; margin: 24px 0 10px 0;">
            <a href="{{{{ frappe.utils.get_url_to_form(doc.doctype, doc.name) }}}}" style="display: inline-block; background-color: #0284c7; color: #ffffff !important; text-decoration: none; padding: 10px 20px; border-radius: 5px; font-weight: 600; font-size: 13px; margin-right: 8px;">View Contract in ERPNext</a>
            <a href="{{{{ frappe.utils.get_url() }}}}/app/query-report/Investment%20Maturity%20and%20Rollover%20Report" style="display: inline-block; background-color: #f1f5f9; color: #334155 !important; text-decoration: none; padding: 10px 18px; border-radius: 5px; font-weight: 600; font-size: 13px; border: 1px solid #cbd5e1;">Maturity Report</a>
        </div>
    </div>

    <div style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 14px 28px; font-size: 11px; color: #94a3b8; text-align: center;">
        Automated alert for users with the <strong>Finance Manager</strong> role &bull; Metro Group ERPNext
    </div>
</div>"""

@frappe.whitelist()
def setup_maturity_notifications():
    """
    Configures and synchronizes the 4 standard Frappe Notification records in ERPNext
    for 30, 15, 7, and 3 days maturity reminders targeting the Finance Manager role.
    Also ensures Finance Manager role has necessary Custom DocPerm on Investment App.
    """
    # 1. Handle legacy renaming
    if frappe.db.exists("Notification", "INVESTMENT NOTIFICATION ( 14 DAYS TO THE END OF THE INVESTMENT PERIOD )"):
        frappe.rename_doc(
            "Notification",
            "INVESTMENT NOTIFICATION ( 14 DAYS TO THE END OF THE INVESTMENT PERIOD )",
            "INVESTMENT NOTIFICATION ( 15 DAYS TO THE END OF THE INVESTMENT PERIOD )",
            force=True
        )
    if frappe.db.exists("Notification", "INVESTMENT NOTIFICATION ( 7 DAYS TO THE END OF THE INVESTMENT PERIOD    "):
        frappe.rename_doc(
            "Notification",
            "INVESTMENT NOTIFICATION ( 7 DAYS TO THE END OF THE INVESTMENT PERIOD    ",
            "INVESTMENT NOTIFICATION ( 7 DAYS TO THE END OF THE INVESTMENT PERIOD )",
            force=True
        )

    condition_code = (
        'doc.docstatus == 1 and doc.investment_status == "Approved" and '
        'doc.transaction_type in ["Invest", "Re-invest"] and '
        '(doc.investment_progression or "") not in ["Withdrawn", "Rolled Over"]'
    )

    results = []

    for days, cfg in MILESTONES_CONFIG.items():
        doc_name = cfg["name"]
        if frappe.db.exists("Notification", doc_name):
            notif = frappe.get_doc("Notification", doc_name)
        else:
            notif = frappe.new_doc("Notification")
            notif.name = doc_name

        notif.document_type = "Investment App"
        notif.event = "Days Before"
        notif.date_changed = "end_date"
        notif.days_in_advance = cfg["days"]
        notif.channel = "Email"
        notif.send_system_notification = 1
        notif.enabled = 1
        notif.condition = condition_code
        notif.subject = cfg["subject"]
        notif.message = get_maturity_html_template(
            cfg["days"],
            cfg["badge_text"],
            cfg["badge_bg"],
            cfg["badge_color"],
            cfg["theme_color"],
            cfg["action_advice"]
        )

        # Clear old recipients and bind to Finance Manager role
        notif.recipients = []
        notif.append("recipients", {
            "receiver_by_role": "Finance Manager"
        })

        notif.save(ignore_permissions=True)
        results.append({
            "name": notif.name,
            "days_in_advance": notif.days_in_advance,
            "role": "Finance Manager",
            "enabled": notif.enabled
        })

    # 2. Grant Finance Manager access on Investment App & Member
    if not frappe.db.exists("Custom DocPerm", {"parent": "Investment App", "role": "Finance Manager"}):
        dp = frappe.new_doc("Custom DocPerm")
        dp.parent = "Investment App"
        dp.role = "Finance Manager"
        dp.permlevel = 0
        dp.read = 1
        dp.write = 1
        dp.create = 1
        dp.delete = 0
        dp.submit = 1
        dp.cancel = 0
        dp.amend = 1
        dp.report = 1
        dp.export = 1
        dp.print = 1
        dp.email = 1
        dp.insert(ignore_permissions=True)

    if not frappe.db.exists("Custom DocPerm", {"parent": "Member", "role": "Finance Manager"}):
        dp_m = frappe.new_doc("Custom DocPerm")
        dp_m.parent = "Member"
        dp_m.role = "Finance Manager"
        dp_m.permlevel = 0
        dp_m.read = 1
        dp_m.write = 1
        dp_m.create = 1
        dp_m.report = 1
        dp_m.insert(ignore_permissions=True)

    frappe.db.commit()
    return {
        "status": "success",
        "message": "Configured maturity notifications for 30, 15, 7, and 3 days for Finance Manager",
        "notifications": results
    }

def get_finance_managers():
    """Returns active users assigned the 'Finance Manager' role."""
    return frappe.db.sql("""
        SELECT DISTINCT u.name, u.email, u.full_name
        FROM `tabUser` u
        JOIN `tabHas Role` hr ON hr.parent = u.name
        WHERE hr.role = 'Finance Manager'
          AND u.enabled = 1
    """, as_dict=True)

@frappe.whitelist()
def send_maturity_reminders(milestones=None, test_days=None, force=False):
    """
    Evaluates active investment contracts and sends maturity reminders to Finance Managers
    for contracts maturing in 30, 15, 7, and 3 days.
    
    Channels:
    - Realtime In-App Notification Log (for the Desk notification bell)
    - Corporate HTML Email via frappe.sendmail
    
    Parameters:
    - milestones: list of integer days (default: [30, 15, 7, 3])
    - test_days: integer day milestone to evaluate/simulate (e.g. 16)
    - force: boolean, if True bypasses same-day deduplication
    """
    today = nowdate()
    
    if test_days is not None:
        target_milestones = [cint(test_days)]
    elif milestones:
        target_milestones = [cint(m) for m in milestones]
    else:
        target_milestones = [30, 15, 7, 3]

    finance_managers = get_finance_managers()
    if not finance_managers:
        frappe.log_error("No active users found with 'Finance Manager' role", "Investment Maturity Reminder")
        return {"status": "skipped", "reason": "No active Finance Managers found"}

    email_recipients = [
        fm.email for fm in finance_managers
        if fm.email and "@" in fm.email and not fm.email.endswith("@example.com")
    ]

    placeholders = ",".join(["%s"] * len(target_milestones))
    query = f"""
        SELECT 
            inv.name,
            inv.party,
            inv.party_name,
            inv.amount,
            inv.interest_rate,
            COALESCE(inv.percent_amount, 0) as percent_amount,
            inv.start_date,
            inv.end_date,
            inv.investment_period,
            inv.investor_bank_name,
            inv.investor_account_number,
            inv.investor_account_name,
            inv.investment_progression,
            DATEDIFF(inv.end_date, %s) as days_to_maturity
        FROM `tabInvestment App` inv
        WHERE inv.docstatus = 1
          AND inv.transaction_type IN ('Invest', 'Re-invest')
          AND inv.investment_status = 'Approved'
          AND COALESCE(inv.investment_progression, '') NOT IN ('Withdrawn', 'Rolled Over')
          AND inv.end_date IS NOT NULL
          AND DATEDIFF(inv.end_date, %s) IN ({placeholders})
        ORDER BY inv.end_date ASC
    """
    
    params = [today, today] + target_milestones
    contracts = frappe.db.sql(query, tuple(params), as_dict=True)

    reminders_sent = 0
    skipped_count = 0
    sent_details = []

    for c in contracts:
        days = cint(c.days_to_maturity)
        cfg = MILESTONES_CONFIG.get(days)
        if not cfg:
            cfg = {
                "days": days,
                "name": f"INVESTMENT NOTIFICATION ({days} DAYS)",
                "subject": f"[Maturity: {days} Days] Investment Contract {{{{ doc.name }}}} - {{{{ doc.party_name }}}}",
                "badge_text": f"{days} Days Notice",
                "badge_bg": "#fef3c7" if days <= 15 else "#eff6ff",
                "badge_color": "#b45309" if days <= 15 else "#1d4ed8",
                "theme_color": "#dc2626" if days <= 3 else ("#ea580c" if days <= 7 else ("#d97706" if days <= 15 else "#2563eb")),
                "action_advice": f"This investment contract is due to mature in {days} days. Please verify investor instructions and liquidity requirements."
            }

        # Deduplication check: check if an alert for this contract and milestone was already created today
        if not force:
            already_sent = frappe.db.sql("""
                SELECT name FROM `tabNotification Log`
                WHERE document_type = 'Investment App'
                  AND document_name = %s
                  AND (subject LIKE %s OR subject LIKE %s)
                  AND DATE(creation) = %s
                LIMIT 1
            """, (c.name, f"%{days} Days%", f"%{days} days%", today))
            
            if already_sent:
                skipped_count += 1
                continue

        doc = frappe.get_doc("Investment App", c.name)
        subject = frappe.render_template(cfg["subject"], {"doc": doc, "frappe": frappe})
        html_content = frappe.render_template(
            get_maturity_html_template(
                cfg["days"],
                cfg["badge_text"],
                cfg["badge_bg"],
                cfg["badge_color"],
                cfg["theme_color"],
                cfg["action_advice"]
            ),
            {"doc": doc, "frappe": frappe}
        )

        # 1. Dispatch in-app Notification Log to each Finance Manager
        for fm in finance_managers:
            try:
                notif = frappe.new_doc("Notification Log")
                notif.for_user = fm.name
                notif.type = "Alert"
                notif.document_type = "Investment App"
                notif.document_name = c.name
                notif.subject = subject
                notif.email_content = html_content
                notif.from_user = "Administrator"
                notif.insert(ignore_permissions=True)
            except Exception as e:
                frappe.log_error(f"Failed to create Notification Log for {fm.name}: {str(e)}", "Investment Maturity Reminder")

        # 2. Dispatch Corporate Email to Finance Managers
        if email_recipients:
            try:
                frappe.sendmail(
                    recipients=email_recipients,
                    subject=subject,
                    message=html_content,
                    reference_doctype="Investment App",
                    reference_name=c.name,
                    delayed=False
                )
            except Exception as e:
                frappe.log_error(f"Failed to send email alert for {c.name}: {str(e)}", "Investment Maturity Reminder")

        # 3. For critical 3-day milestone, dispatch SMS (N-Alert to Finance Managers, Metro Homes to Investor)
        if days == 3:
            try:
                from metro_custom_app.custom_api.termii_sms import notify_investment_3day_sms
                notify_investment_3day_sms(c.name)
            except Exception as e:
                frappe.log_error(f"Failed to dispatch 3-day SMS for {c.name}: {str(e)}", "Investment 3-Day SMS Alert")

        reminders_sent += 1
        sent_details.append({
            "contract": c.name,
            "investor": c.party_name,
            "days_to_maturity": days,
            "maturity_date": str(c.end_date),
            "amount": flt(c.amount)
        })

    frappe.db.commit()
    return {
        "status": "success",
        "reminders_sent": reminders_sent,
        "skipped_already_sent": skipped_count,
        "finance_managers_count": len(finance_managers),
        "recipients": email_recipients,
        "details": sent_details
    }

