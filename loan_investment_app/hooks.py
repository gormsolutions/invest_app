# -*- coding: utf-8 -*-
from . import __version__ as app_version

app_name = "loan_investment_app"
app_title = "Loan and Investment App"
app_publisher = "paul"
app_description = "Loan and Investment App"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "paul@gmail.com"
app_license = "MIT"
# required_apps = []

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/loan_investment_app/css/loan_investment_app.css"
# app_include_js = "/assets/loan_investment_app/js/loan_investment_app.js"

# include js, css files in header of web template
# web_include_css = "/assets/loan_investment_app/css/loan_investment_app.css"
# web_include_js = "/assets/loan_investment_app/js/loan_investment_app.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "loan_investment_app/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "loan_investment_app/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

website_route_rules = [
	{"from_route": "/investment-app", "to_route": "investor_portal"},
]

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "loan_investment_app.utils.jinja_methods",
# 	"filters": "loan_investment_app.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "loan_investment_app.install.before_install"
# after_install = "loan_investment_app.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "loan_investment_app.uninstall.before_uninstall"
# after_uninstall = "loan_investment_app.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "loan_investment_app.utils.before_app_install"
# after_app_install = "loan_investment_app.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "loan_investment_app.utils.before_app_uninstall"
# after_app_uninstall = "loan_investment_app.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "loan_investment_app.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Investment App": {
		"on_update": "loan_investment_app.loan_and_investment_app.doctype.investment_app.investment_app.update_balances_on_change",
		"on_submit": [
			"loan_investment_app.loan_and_investment_app.doctype.investment_app.investment_app.update_balances_on_change",
			"metro_custom_app.custom_api.termii_sms.notify_investment_approved_sms",
			"metro_custom_app.custom_api.termii_sms.notify_payout_request_sms"
		],
		"on_cancel": "loan_investment_app.loan_and_investment_app.doctype.investment_app.investment_app.update_balances_on_change"
	},
	"Journal Entry": {
		"on_submit": "loan_investment_app.loan_and_investment_app.doctype.investment_app.investment_app.update_balances_after_je",
		"on_cancel": "loan_investment_app.loan_and_investment_app.doctype.investment_app.investment_app.update_balances_after_je"
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"loan_investment_app.loan_and_investment_app.doctype.investment_app.investment_app.post_monthly_interest",
		"loan_investment_app.custom_api.desk.sync_contract_lifecycle",
		"loan_investment_app.custom_api.desk.send_maturity_reminders"
	],
	"daily_long": [
		"loan_investment_app.loan_and_investment_app.doctype.investment_app.investment_app.cleanup_failed_interest_postings"
	],
	"hourly": [
		"loan_investment_app.loan_and_investment_app.doctype.investment_app.investment_app.update_investment_balances"
	]
}

# Testing
# -------

# before_tests = "loan_investment_app.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "loan_investment_app.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "loan_investment_app.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["loan_investment_app.utils.before_request"]
# after_request = ["loan_investment_app.utils.after_request"]

# Job Events
# ----------
# before_job = ["loan_investment_app.utils.before_job"]
# after_job = ["loan_investment_app.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [
            ["module", "=", "Loan and Investment App"]
        ]
    },
    {
        "doctype": "Client Script",
        "filters": [
            ["module", "=", "Loan and Investment App"]
        ]
    }
]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"loan_investment_app.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Error Notifications
error_report_email = "admin@example.com"

