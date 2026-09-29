# Copyright (c) 2024, paul and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class InvestmentSettings(Document):
	def validate(self):
		"""Validate Investment Settings"""
		self.validate_accounts()
		self.validate_tax_settings()
	
	def validate_accounts(self):
		"""Ensure all required accounts are set"""
		required_accounts = [
			'capital_account',
			'portfolio_account',
			'investment_interest',
			'percent_interest_amount_account',
			'investor_withdrawal_payable_account',
			'witholding_tax_payable'
		]
		
		for field in required_accounts:
			if not getattr(self, field):
				frappe.throw(f"Please set {field.replace('_', ' ').title()}")
	
	def validate_tax_settings(self):
		"""Validate tax and withdrawal settings"""
		if self.withholding_tax_percentage < 0 or self.withholding_tax_percentage > 100:
			frappe.throw("Withholding tax percentage must be between 0 and 100")
		
		if self.minimum_withdrawal_amount <= 0:
			frappe.throw("Minimum withdrawal amount must be greater than 0")
	
	def on_update(self):
		"""Clear cache when settings are updated"""
		frappe.cache().delete_value('investment_settings')

def get_investment_settings():
	"""Get investment settings with caching"""
	settings = frappe.cache().get_value('investment_settings')
	if not settings:
		settings = frappe.get_single('Investment Settings').__dict__
		frappe.cache().set_value('investment_settings', settings)
	return settings
