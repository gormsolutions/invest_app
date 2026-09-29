import frappe
import json

def get_or_create_number_card(label, doc_type, function, aggregate_based_on=None, filters=None):
    existing = frappe.db.get_value("Number Card", {"label": label}, "name")
    if existing:
        return existing
        
    card = frappe.new_doc("Number Card")
    card.label = label
    card.type = "Document Type"
    card.document_type = doc_type
    card.function = function
    if aggregate_based_on:
        card.aggregate_function_based_on = aggregate_based_on
    card.is_public = 1
    card.show_percentage_stats = 0
    if filters:
        card.filters_json = json.dumps(filters)
    card.insert(ignore_permissions=True)
    frappe.db.commit()
    return card.name

def setup_permissions():
    """Configure strict permissions: Finance team full operational/programming access, Investors read-only"""
    print("Configuring role permissions for Investment App and Member...")
    
    # 1. Clear existing Custom DocPerm for Investment App
    frappe.db.delete("Custom DocPerm", {"parent": "Investment App"})
    
    perms = [
        # Finance Leadership
        {"parent": "Investment App", "role": "Accounts Manager", "permlevel": 0, "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1, "report": 1, "export": 1, "print": 1, "email": 1},
        # Finance Staff
        {"parent": "Investment App", "role": "Accounts User", "permlevel": 0, "read": 1, "write": 1, "create": 1, "delete": 0, "submit": 1, "cancel": 0, "amend": 1, "report": 1, "export": 1, "print": 1, "email": 1},
        # Investment Operations
        {"parent": "Investment App", "role": "Investment User Staff", "permlevel": 0, "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1, "report": 1, "export": 1, "print": 1, "email": 1},
        # System Administration
        {"parent": "Investment App", "role": "System Manager", "permlevel": 0, "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1, "report": 1, "export": 1, "print": 1, "email": 1},
        # Investor Role: STRICTLY READ-ONLY (no create, no write, no submit, no cancel, no delete)
        {"parent": "Investment App", "role": "Investor", "permlevel": 0, "read": 1, "write": 0, "create": 0, "delete": 0, "submit": 0, "cancel": 0, "amend": 0, "report": 0, "export": 0, "print": 1, "email": 0}
    ]
    
    for idx, p in enumerate(perms, 1):
        dp = frappe.new_doc("Custom DocPerm")
        dp.update(p)
        dp.idx = idx
        dp.insert(ignore_permissions=True)

    # 2. Member Permissions (ensure Finance team can manage KYC & profiles, Investor is read-only)
    for role in ["Accounts Manager", "Accounts User"]:
        if not frappe.db.exists("Custom DocPerm", {"parent": "Member", "role": role}):
            dp = frappe.new_doc("Custom DocPerm")
            dp.parent = "Member"
            dp.role = role
            dp.permlevel = 0
            dp.read = 1
            dp.write = 1
            dp.create = 1
            dp.report = 1
            dp.insert(ignore_permissions=True)

    frappe.db.commit()
    print("Permissions updated: Finance team has full programming access; Investor is read-only.")

def setup_cards_and_workspace():
    # 1. Custom Number Card: Active AUM
    aum_card = get_or_create_number_card(
        label="Active AUM (Total Invested)",
        doc_type="Investment App",
        function="Sum"
    )
    card_doc = frappe.get_doc("Number Card", aum_card)
    card_doc.label = "Active AUM (Live Portfolio)"
    card_doc.type = "Custom"
    card_doc.method = "loan_investment_app.custom_api.desk.get_active_aum"
    card_doc.save(ignore_permissions=True)

    # 2. Custom Number Card: Active Contracts Count
    contracts_card = get_or_create_number_card(
        label="Active Investment Contracts",
        doc_type="Investment App",
        function="Count"
    )
    card_doc = frappe.get_doc("Number Card", contracts_card)
    card_doc.label = "Active Contracts Count"
    card_doc.type = "Custom"
    card_doc.method = "loan_investment_app.custom_api.desk.get_active_contracts_count"
    card_doc.save(ignore_permissions=True)

    # 3. Custom Number Card: Matured Capital
    matured_card = get_or_create_number_card(
        label="Matured Capital (Unsettled)",
        doc_type="Investment App",
        function="Sum"
    )
    card_doc = frappe.get_doc("Number Card", matured_card)
    card_doc.label = "Matured Portfolio (Unsettled)"
    card_doc.type = "Custom"
    card_doc.method = "loan_investment_app.custom_api.desk.get_matured_aum"
    card_doc.save(ignore_permissions=True)

    # 4. Custom Number Card: Maturing in 30 Days
    maturing_30_card = get_or_create_number_card(
        label="Maturing in 30 Days",
        doc_type="Investment App",
        function="Sum"
    )
    card_doc = frappe.get_doc("Number Card", maturing_30_card)
    card_doc.label = "Maturing in 30 Days"
    card_doc.type = "Custom"
    card_doc.method = "loan_investment_app.custom_api.desk.get_maturing_30_days"
    card_doc.save(ignore_permissions=True)

    # 5. Custom Number Card: Pending Payout Approvals
    payout_card = get_or_create_number_card(
        label="Pending Payout Requests",
        doc_type="Investment App",
        function="Count"
    )
    card_doc = frappe.get_doc("Number Card", payout_card)
    card_doc.label = "Pending Payout Approvals"
    card_doc.type = "Custom"
    card_doc.method = "loan_investment_app.custom_api.desk.get_pending_payouts_count"
    card_doc.save(ignore_permissions=True)

    # 6. Number Card: Open Inquiries
    inquiry_card = get_or_create_number_card(
        label="Open Investor Inquiries",
        doc_type="Issue",
        function="Count",
        filters=[
            ["Issue", "status", "in", ["Open", "Replied"], False],
            ["Issue", "subject", "like", "%Investor%", False]
        ]
    )

    print(f"Cards verified: {aum_card}, {contracts_card}, {matured_card}, {maturing_30_card}, {payout_card}, {inquiry_card}")

    # 5. Update Investment Workspace
    if frappe.db.exists("Workspace", "Investment"):
        ws = frappe.get_doc("Workspace", "Investment")
        ws.module = "Loan and Investment App"
        ws.icon = "bank"
        ws.public = 1
        ws.is_hidden = 0
        ws.set("roles", [])

        # Number cards child table (both number_card_name and label must match for Frappe UI customization persistence)
        ws.set("number_cards", [])
        for card_name in [aum_card, contracts_card, matured_card, maturing_30_card, payout_card, inquiry_card]:
            ws.append("number_cards", {"number_card_name": card_name, "label": card_name})
        
        # Shortcuts child table
        ws.set("shortcuts", [])
        shortcuts_data = [
            {"type": "DocType", "link_to": "Investment App", "label": "Investments", "doc_view": "List", "color": "Blue"},
            {"type": "DocType", "link_to": "Member", "label": "Member", "doc_view": "List", "color": "Grey"},
            {"type": "Report", "link_to": "Investment Report", "label": "Investments Report", "doc_view": "Report Builder", "color": "Green"},
            {"type": "Report", "link_to": "Investment Maturity and Rollover Report", "label": "Maturity & Rollover Report", "doc_view": "Report Builder", "color": "Red"}
        ]
        for sc in shortcuts_data:
            ws.append("shortcuts", sc)

        # Links child table (Card Breaks and DocType/Report Links)
        ws.set("links", [])
        links_data = [
            # Card 1: Operations & Transactions
            {"type": "Card Break", "label": "Operations & Transactions", "link_type": "DocType"},
            {"type": "Link", "label": "Investment Contracts", "link_to": "Investment App", "link_type": "DocType", "dependencies": "Investment App"},
            {"type": "Link", "label": "Investor Registry (Members)", "link_to": "Member", "link_type": "DocType", "dependencies": "Member"},
            {"type": "Link", "label": "Investment Settings", "link_to": "Investment Settings", "link_type": "DocType", "dependencies": "Investment Settings"},
            
            # Card 2: Reports & Financials
            {"type": "Card Break", "label": "Reports & Reconciliation", "link_type": "Report"},
            {"type": "Link", "label": "Investments Report", "link_to": "Investment Report", "link_type": "Report", "is_query_report": 1},
            {"type": "Link", "label": "General Ledger", "link_to": "General Ledger", "link_type": "Report", "is_query_report": 1},
            {"type": "Link", "label": "Accounts Payable Summary", "link_to": "Accounts Payable Summary", "link_type": "Report", "is_query_report": 1},
            
            # Card 3: Investor Relations & Support
            {"type": "Card Break", "label": "Investor Relations & Support", "link_type": "DocType"},
            {"type": "Link", "label": "Investor Support Tickets", "link_to": "Issue", "link_type": "DocType", "dependencies": "Issue"},
            {"type": "Link", "label": "Investor Self-Service Portal", "url": "/investment-app", "link_type": "DocType"}
        ]
        for lk in links_data:
            ws.append("links", lk)

        # Workspace Editor Content Blocks
        ws_content = [
            {"id": "hdr1", "type": "header", "data": {"text": "<span class='h4'><b>Portfolio Oversight & Capital Health</b></span>", "col": 12}},
            {"id": "c1", "type": "number_card", "data": {"number_card_name": aum_card, "col": 3}},
            {"id": "c2", "type": "number_card", "data": {"number_card_name": contracts_card, "col": 3}},
            {"id": "c3", "type": "number_card", "data": {"number_card_name": matured_card, "col": 3}},
            {"id": "c4", "type": "number_card", "data": {"number_card_name": maturing_30_card, "col": 3}},
            {"id": "sp1", "type": "spacer", "data": {"col": 12}},
            {"id": "hdr_ops", "type": "header", "data": {"text": "<span class='h4'><b>Operational Queues</b></span>", "col": 12}},
            {"id": "c5", "type": "number_card", "data": {"number_card_name": payout_card, "col": 3}},
            {"id": "c6", "type": "number_card", "data": {"number_card_name": inquiry_card, "col": 3}},
            {"id": "sp2", "type": "spacer", "data": {"col": 12}},
            {"id": "hdr2", "type": "header", "data": {"text": "<span class='h4'><b>Quick Shortcuts</b></span>", "col": 12}},
            {"id": "s1", "type": "shortcut", "data": {"shortcut_name": "Investment App", "col": 3}},
            {"id": "s2", "type": "shortcut", "data": {"shortcut_name": "Member", "col": 3}},
            {"id": "s3", "type": "shortcut", "data": {"shortcut_name": "Investments Report", "col": 3}},
            {"id": "s4", "type": "shortcut", "data": {"shortcut_name": "Investor Inquiries", "col": 3}},
            {"id": "sp3", "type": "spacer", "data": {"col": 12}},
            {"id": "hdr3", "type": "header", "data": {"text": "<span class='h4'><b>Masters & Transactions</b></span>", "col": 12}},
            {"id": "cd1", "type": "card", "data": {"card_name": "Operations & Transactions", "col": 4}},
            {"id": "cd2", "type": "card", "data": {"card_name": "Reports & Reconciliation", "col": 4}},
            {"id": "cd3", "type": "card", "data": {"card_name": "Investor Relations & Support", "col": 4}}
        ]
        ws.content = json.dumps(ws_content)
        ws.save(ignore_permissions=True)
        frappe.db.commit()
        print("Updated Investment Workspace with KPI number cards, shortcuts, card links, and sidebar module.")

def execute_all():
    setup_permissions()
    setup_cards_and_workspace()

if __name__ == "__main__":
    execute_all()
