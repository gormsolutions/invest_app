import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, flt, today, add_days, now, now_datetime, get_datetime
from datetime import timedelta

@frappe.whitelist()
def get_cached_balances(party=None):
	"""Get cached balances for a party, with fallback to fresh calculation"""
	try:
		if not party:
			return {
				"portifolia_account": 0,
				"balance_walet": 0
			}

		# Try to get from cache
		cache_key = f"investment_balances:{party}"
		cached_data = frappe.cache().get_value(cache_key)
		
		if cached_data:
			try:
				cached_balances = frappe.parse_json(cached_data)
				last_updated = get_datetime(cached_balances.get("last_updated"))
				
				# Return cached values if less than 5 minutes old
				if now_datetime() - last_updated < timedelta(minutes=5):
					return {
						"portifolia_account": cached_balances.get("portfolio", 0),
						"balance_walet": cached_balances.get("wallet", 0)
					}
			except Exception:
				frappe.log_error("Error parsing cached balances")
		
		# Calculate fresh balances
		portfolio = get_portfolio_balance(party) if frappe.db.exists("GL Entry", {"party": party}) else 0
		wallet = get_wallet_balance(party) if frappe.db.exists("GL Entry", {"party": party}) else 0
		
		# Update cache
		frappe.cache().set_value(
			key=cache_key,
			val=frappe.as_json({
				"portfolio": portfolio,
				"wallet": wallet,
				"last_updated": str(now())
			}),
			expires_in_sec=3600
		)
		
		return {
			"portifolia_account": portfolio,
			"balance_walet": wallet
		}
	except Exception as e:
		frappe.log_error(f"Error getting cached balances: {str(e)}")
		return {
			"portifolia_account": 0,
			"balance_walet": 0
		}

def get_portfolio_balance(party):
	"""Get total portfolio balance for a party"""
	try:
		# Get settings
		settings = frappe.get_single('Investment Settings')
		if not settings.portfolio_account:
			return 0

		# Get balance from GL entries
		portfolio_balance = frappe.db.sql("""
			SELECT sum(debit_in_account_currency) - sum(credit_in_account_currency) as balance
			FROM `tabGL Entry`
			WHERE account = %s 
			AND party = %s 
			AND is_cancelled = 0
		""", (settings.portfolio_account, party), as_dict=True)
		
		return flt(portfolio_balance[0].balance if portfolio_balance else 0)
		
	except Exception as e:
		frappe.log_error(f"Error getting portfolio balance: {str(e)}")
		return 0

def get_wallet_balance(party):
	"""Get wallet balance for a party"""
	try:
		# Get settings
		settings = frappe.get_single('Investment Settings')
		if not settings.investor_withdrawal_payable_account:
			return 0

		# Get balance from GL entries
		wallet_balance = frappe.db.sql("""
			SELECT sum(debit_in_account_currency) - sum(credit_in_account_currency) as balance
			FROM `tabGL Entry`
			WHERE account = %s 
			AND party = %s 
			AND is_cancelled = 0
		""", (settings.investor_withdrawal_payable_account, party), as_dict=True)
		
		return flt(wallet_balance[0].balance if wallet_balance else 0)
		
	except Exception as e:
		frappe.log_error(f"Error getting wallet balance: {str(e)}")
		return 0

def get_current_date():
	"""Get the current date in user's timezone"""
	return getdate(frappe.utils.get_datetime_str(now_datetime()))

def post_monthly_interest():
	"""
	Scheduled method to post monthly interest for investment schedules.
	Only handles interest postings, principal is already posted at investment submission.
	This should be scheduled to run daily.
	"""
	current_date = get_current_date()
	
	# Get all investment schedules that are pending and due
	schedules = frappe.get_all(
		'Investment Schedule',
		filters={
			'posted_status': 'Pending',
			'start_date': ('<=', current_date),
			'amount': ('>', 0)  # Only get schedules with interest amount
		},
		fields=['name', 'parent', 'start_date', 'amount', 'end_date']
	)
	
	for schedule in schedules:
		try:
			investment = frappe.get_doc('Investment App', schedule.parent)
			
			# Skip if investment is not approved or submitted
			if (investment.docstatus != 1 or 
				investment.investment_status != 'Approved' or
				investment.transaction_type == "Withdraw"):
				frappe.logger().info(f"Skipping interest posting for {investment.name} - Status: {investment.investment_status}, Type: {investment.transaction_type}")
				continue
			
			# Create journal entry for interest
			accounts = investment.get_investment_accounts()
			
			# Check if a journal entry already exists for this schedule
			existing_entry = frappe.get_all(
				'Journal Entry',
				filters={
					'custom_investmet_id': investment.name,
					'posting_date': schedule.start_date,
					'custom_transaction_type': 'Interest',
					'docstatus': 1
				}
			)
			
			if existing_entry:
				frappe.logger().info(f"Journal entry already exists for schedule {schedule.name}")
				frappe.db.set_value('Investment Schedule', schedule.name, 'posted_status', 'Posted')
				frappe.db.commit()
				continue
			
			journal_entry = frappe.new_doc('Journal Entry')
			journal_entry.voucher_type = 'Journal Entry'
			journal_entry.company = accounts['company_set']
			journal_entry.posting_date = schedule.start_date
			journal_entry.user_remark = f"Monthly Interest Posting for {investment.name} - Period: {schedule.start_date} to {schedule.end_date}"
			journal_entry.custom_transaction_type = 'Interest'
			journal_entry.custom_investmet_id = investment.name
			
			# Add journal entry rows
			journal_entry.append('accounts', {
				'account': accounts['investment_interest'],
				'debit_in_account_currency': 0,
				'credit_in_account_currency': schedule.amount,  # Credit interest payable
				'party_type': "Member",
				'party': investment.party,
				'cost_center': accounts['cost_center'],
				'user_remark': journal_entry.user_remark
			})
			
			journal_entry.append('accounts', {
				'account': accounts['percent_interest_account'],
				'debit_in_account_currency': schedule.amount,  # Debit interest income
				'credit_in_account_currency': 0,
				'party_type': "Member",
				'party': investment.party,
				'cost_center': accounts['cost_center'],
				'user_remark': journal_entry.user_remark
			})
			
			# Insert and submit journal entry
			journal_entry.insert()
			journal_entry.submit()
			
			# Update schedule status to posted
			frappe.db.set_value('Investment Schedule', schedule.name, 'posted_status', 'Posted')
			frappe.db.commit()
			
			frappe.logger().info(f"Posted interest of {schedule.amount} for investment {investment.name}")
			
		except Exception as e:
			frappe.log_error(
				message=f"Failed to post interest for schedule {schedule.name}: {str(e)}",
				title="Monthly Interest Posting Error"
			)

@frappe.whitelist()
def fetch_account_balances(doc):
	"""Fetch portfolio and wallet account balances from a document instance"""
	if isinstance(doc, str):
		doc = frappe.get_doc('Investment App', doc)
	return doc.fetch_account_balances()


@frappe.whitelist()
def get_total_deposits(party):
	"""Get total deposits and investments for a party"""
	try:
		# Get all approved deposits
		deposits = frappe.get_all(
			"Investment App",
			filters={
				"party": party,
				"transaction_type": "Deposit",
				"docstatus": 1,
				"investment_status": "Approved"
			},
			fields=["amount"]
		)
		
		# Get all approved investments
		investments = frappe.get_all(
			"Investment App",
			filters={
				"party": party,
				"transaction_type": "Invest",
				"docstatus": 1,
				"investment_status": "Approved"
			},
			fields=["amount"]
		)
		
		total_deposits = sum(dep.amount for dep in deposits)
		total_investments = sum(inv.amount for inv in investments)
		
		return {
			"total_deposits": total_deposits,
			"total_investments": total_investments
		}
	except Exception as e:
		frappe.log_error(f"Error getting deposit totals: {str(e)}")
		return {
			"total_deposits": 0,
			"total_investments": 0
		}

class InvestmentApp(Document):

	def validate(self):
		# Ensure transaction type is set
		# if not self.transaction_type:
		#     frappe.throw(_("Please select the transaction type of your choice."))

		# Ensure that the amount is not negative or None
		if self.amount is None:
			frappe.throw(_("The transaction amount cannot be empty."))

		if self.amount <= 0:
			frappe.throw(_("The transaction amount should be a positive value."))

		# Validate investment amount against deposits
		if self.transaction_type == "Invest":
			deposit_info = get_total_deposits(self.party)
			available_for_investment = deposit_info["total_deposits"] - deposit_info["total_investments"]
			
			if self.amount > available_for_investment:
				frappe.throw(_(
					"You can only invest up to {0}. Current deposits: {1}, Already invested: {2}"
				).format(
					frappe.format_value(available_for_investment, {"fieldtype": "Currency"}),
					frappe.format_value(deposit_info["total_deposits"], {"fieldtype": "Currency"}),
					frappe.format_value(deposit_info["total_investments"], {"fieldtype": "Currency"})
				))

		# Set amount in words
		self.set_amount_in_words()

		# Fetch account balances for all transaction types
		self.fetch_account_balances()

		# Validate based on transaction type
		if self.transaction_type == "Re-invest":
			if not self.balance_walet:
				frappe.throw(_("Wallet balance is not available. Please check your account settings."))
				
			if flt(self.amount) > flt(self.balance_walet):
				frappe.throw(_("The amount {0} cannot exceed the available amount {1} in the Wallet Account.").format(
					flt(self.amount), flt(self.balance_walet)
				))
		elif self.transaction_type == "Request for Payments":
			self.validate_payment_request()
		elif self.transaction_type == "Withdraw":
			self.validate_withdrawal()

		# Set default investment status if not already set
		if not self.investment_status:
			self.investment_status = "Received"

		# Additional validation for submission
		if self._action == "submit":
			self.validate_on_submit()
			
	def set_amount_in_words(self):
		"""Server-side only – never whitelisted"""
		try:
			if self.amount:
				company = frappe.db.get_single_value('Investment Settings', 'company')
				currency = frappe.db.get_value('Company', company, 'default_currency')
				self.amount_in_words = frappe.utils.money_in_words(self.amount, currency)
		except Exception as e:
			frappe.log_error(f"Error setting amount in words: {str(e)}")

	def validate_on_submit(self):
		"""Additional validations when submitting the document"""
		accounts = self.get_investment_accounts()
		if not accounts:
			frappe.throw(_("Investment accounts not configured. Please check Investment Settings."))

		if self.transaction_type == "Re-invest":
			if not self.balance_walet:
				frappe.throw(_("Cannot submit: Wallet balance is not available."))
			if flt(self.amount) > flt(self.balance_walet):
				frappe.throw(_("Cannot submit: Amount exceeds available wallet balance."))
		elif self.transaction_type == "Withdraw":
			if not self.total_amount_after_tax:
				frappe.throw(_("Cannot submit: Total amount after tax is not calculated."))
			if flt(self.amount) > flt(self.total_amount_after_tax):
				frappe.throw(_("Cannot submit: Withdrawal amount exceeds total amount after tax."))

	def validate_payment_request(self):
		"""Validate payment request amount against the wallet balance."""
		if self.amount > self.balance_walet:  # Ensure 'balance_wallet' is used correctly
			frappe.throw(_("The requested payment amount cannot exceed the balance in the wallet."))

	def validate_withdrawal(self):
		"""Validate withdrawal amount and investment end dates."""
		try:
			# Use get_current_date() for consistent date handling
			current_date = get_current_date()
			if getdate(self.posting_date) > current_date:
				frappe.throw(_("You cannot withdraw funds beyond today's date ({0}).").format(
					frappe.format_value(current_date, {"fieldtype": "Date"})
				))

			# Validate withdrawal amounts
			if self.transaction_type == "Withdraw":
				# Validate required fields
				if not flt(self.amount_withrowned):
					frappe.throw(_("Principal Amount Withdrawn is required"))
				if not flt(self.total_interest_earned):
					frappe.throw(_("Total Interest Earned is required"))
				
				# Set derived values
				self.interets_withrowned = flt(self.total_interest_earned)
				self.total_amount_after_tax = flt(self.amount_withrowned) + flt(self.total_interest_earned)

			# Get the logged-in user
			user = frappe.session.user

			# Skip validation for users without the "Investor" role and administrators
			if not "Investor" in frappe.get_roles(user) or "Administrator" in frappe.get_roles(user):
				frappe.logger().debug(f"User {user} is either not an Investor or is an Administrator, skipping investment validation")
				return

			# Fetch investments for validation
			investments = self.fetch_investments_for_party()
			if not investments:
				frappe.throw(_("No approved investments found for withdrawal."))

			# Extract posting date details
			posting_date = getdate(self.posting_date)
			posting_year = posting_date.year
			posting_month = posting_date.month

			# Flag to track valid investment found
			valid_investment_found = False

			# Validate against investment end dates
			for investment in investments:
				investment_end_date = getdate(investment["end_date"])
				if (investment_end_date.year == posting_year and 
					investment_end_date.month == posting_month and 
					posting_date >= investment_end_date):
					valid_investment_found = True
					break

			if not valid_investment_found:
				frappe.throw(_(
					"No valid investments found for withdrawal on {0}. Please ensure your withdrawal date matches an investment's end date."
				).format(frappe.format_value(posting_date, {"fieldtype": "Date"})))

		except Exception as e:
			frappe.logger().error(f"Withdrawal validation error: {str(e)}")
			frappe.throw(_("Error validating withdrawal: {0}").format(str(e)))

	def fetch_investments_for_party(self):
		# Get the logged-in user
		user = frappe.session.user

		# Get the member name associated with the user
		# party = frappe.db.get_value("Member", {"owner": user}, "name")
		party = frappe.db.get_value("Member", {"email_id": user}, "name")

		
		# If no party is found, return an empty list or handle accordingly
		if not party:
			return []

		# Fetch investments related to the specific party
		return frappe.get_list(
			'Investment App',
			fields=['name', 'end_date', 'posting_date', 'amount', 'party_name'],
			filters={
				'party': party,  # Filter by the specific party
				'transaction_type': ['in', ['Re-invest', 'Invest']],
				'docstatus': ['!=', 2],  # Exclude canceled records
				'investment_status': 'Approved'
			}
		)

	# @frappe.whitelist()
	# def fetch_account_balances(self):
	# 	"""Fetch portfolio and wallet account balances"""
	# 	try:
	# 		# Return early if document is submitted
	# 		if self.docstatus != 0:  # 0 = Draft, 1 = Submitted, 2 = Cancelled
	# 			return {
	# 				'portifolia_account': self.portifolia_account or 0,
	# 				'balance_walet': self.balance_walet or 0,
	# 				'message': 'Document is already submitted. Using saved values.'
	# 			}

	# 		if not self.party:
	# 			return {
	# 				'portifolia_account': 0,
	# 				'balance_walet': 0
	# 			}

	# 		accounts = self.get_investment_accounts()
	# 		if not accounts:
	# 			frappe.logger().error("Investment accounts not configured properly")
	# 			return {
	# 				'portifolia_account': 0,
	# 				'balance_walet': 0,
	# 				'error': 'Investment accounts not configured properly'
	# 			}
				
	# 		# Get portfolio account balance is_cancelled
	# 		portfolio_balance = frappe.db.sql("""
	# 			SELECT sum(debit_in_account_currency) - sum(credit_in_account_currency) as balance
	# 			FROM `tabGL Entry`
	# 			WHERE account = %s AND party = %s AND is_cancelled = 1
	# 		""", (accounts['portfolio_account'], self.party), as_dict=True)
			
	# 		portfolio_amount = flt(portfolio_balance[0].balance if portfolio_balance else 0)
			
	# 		# Get wallet balance
	# 		wallet_balance = frappe.db.sql("""
	# 			SELECT sum(debit_in_account_currency) - sum(credit_in_account_currency) as balance
	# 			FROM `tabGL Entry`
	# 			WHERE account = %s AND party = %s AND is_cancelled = 1
	# 		""", (accounts['withdrawal_payable_account'], self.party), as_dict=True)
			
	# 		wallet_amount = flt(wallet_balance[0].balance if wallet_balance else 0)
			
	# 		frappe.logger().debug(f"Fetched balances for {self.party}: Portfolio={portfolio_amount}, Wallet={wallet_amount}")
			
	# 		# Update document fields since we're in draft state
	# 		self.portifolia_account = portfolio_amount
	# 		# self.balance_walet = wallet_amount
			
	# 		return {
	# 			'portifolia_account': portfolio_amount,
	# 			'balance_walet': wallet_amount
	# 		}
				
	# 	except Exception as e:
	# 		frappe.logger().error(f"Error fetching account balances: {str(e)}")
	# 		return {
	# 			'portifolia_account': 0,
	# 			'balance_walet': 0,
	# 			'error': str(e)
	# 		}

	@frappe.whitelist()
	def fetch_account_balances(self):
		"""Fetch portfolio and wallet account balances (always positive)"""
		try:
			if self.docstatus != 0:
				return {
					'portifolia_account': abs(self.portifolia_account or 0),
					'balance_walet': abs(self.balance_walet or 0),
					'message': 'Document is already submitted. Using saved values.'
				}

			if not self.party:
				return {
					'portifolia_account': 0,
					'balance_walet': 0
				}

			accounts = self.get_investment_accounts()
			if not accounts:
				frappe.logger().error("Investment accounts not configured properly")
				return {
					'portifolia_account': 0,
					'balance_walet': 0,
					'error': 'Investment accounts not configured properly'
				}

			# Portfolio balance
			portfolio_balance = frappe.db.sql("""
				SELECT SUM(debit_in_account_currency) - SUM(credit_in_account_currency) AS balance
				FROM `tabGL Entry`
				WHERE account = %s AND party = %s AND is_cancelled = 0
			""", (accounts['portfolio_account'], self.party), as_dict=True)

			portfolio_amount = abs(flt(portfolio_balance[0].balance if portfolio_balance else 0))

			# Wallet balance
			wallet_balance = frappe.db.sql("""
				SELECT SUM(debit_in_account_currency) - SUM(credit_in_account_currency) AS balance
				FROM `tabGL Entry`
				WHERE account = %s AND party = %s AND is_cancelled = 0
			""", (accounts['withdrawal_payable_account'], self.party), as_dict=True)

			wallet_amount = abs(flt(wallet_balance[0].balance if wallet_balance else 0))

			frappe.logger().debug(f"Fetched balances for {self.party}: Portfolio={portfolio_amount}, Wallet={wallet_amount}")

			# Update fields (only in draft)
			self.portifolia_account = portfolio_amount
			self.balance_walet = wallet_amount

			return {
				'portifolia_account': portfolio_amount,
				'balance_walet': wallet_amount
			}

		except Exception as e:
			frappe.logger().error(f"Error fetching account balances: {str(e)}")
			return {
				'portifolia_account': 0,
				'balance_walet': 0,
				'error': str(e)
			}



	def on_submit(self):
		"""Handle submission including backdated interest postings"""
		try:
			# Get current date for comparison
			current_date = get_current_date()
			
			# First update all schedule statuses that need backdated postings
			past_schedules = []
			for schedule in self.investment_schedule:
				if getdate(schedule.end_date) < current_date and schedule.posted_status == "Pending":
					schedule.posted_status = "Posted"
					past_schedules.append(schedule)
			
			# Save the document to persist schedule status changes BEFORE submission
			if past_schedules:
				self.save()
				
			# Now create the initial journal entry for principal
			self.create_journal_entry()
			
			if self.transaction_type in ["Invest", "Re-invest"] and past_schedules:
				# Get accounts for interest posting
				accounts = self.get_investment_accounts()
				
				for schedule in past_schedules:
					# Create journal entry for each past month's interest
					journal_entry = frappe.new_doc('Journal Entry')
					journal_entry.voucher_type = 'Journal Entry'
					journal_entry.company = accounts['company_set']
					journal_entry.posting_date = schedule.end_date
					journal_entry.user_remark = f"Backdated Interest Posting for {self.name} - Period: {schedule.start_date} to {schedule.end_date}"
					journal_entry.custom_transaction_type = 'Interest'
					journal_entry.custom_investmet_id = self.name
					
					# Add journal entry rows for interest
					journal_entry.append('accounts', {
						'account': accounts['investment_interest'],
						'debit_in_account_currency': 0,
						'credit_in_account_currency': schedule.amount,
						'party_type': "Member",
						'party': self.party,
						'cost_center': accounts['cost_center'],
						'user_remark': journal_entry.user_remark
					})
					
					journal_entry.append('accounts', {
						'account': accounts['percent_interest_account'],
						'debit_in_account_currency': schedule.amount,
						'credit_in_account_currency': 0,
						'party_type': "Member",
						'party': self.party,
						'cost_center': accounts['cost_center'],
						'user_remark': journal_entry.user_remark
					})
					
					# Insert and submit journal entry
					journal_entry.insert()
					journal_entry.submit()
				
				# Show message about backdated entries
				frappe.msgprint(_(
					"Created and posted {0} backdated interest entries for previous months"
				).format(len(past_schedules)))
			
			# Update investment status
			self.investment_status = "Approved"
			
		except Exception as e:
			frappe.log_error(message=f"Error in on_submit for {self.name}: {str(e)}", title="Investment Submission Error")
			frappe.throw(_("Failed to process investment submission: {0}").format(str(e)))

	def update_withdrawal_amounts_for_specific_investments(self):
		# Fetch Investment App documents with filters
		investments = frappe.get_all(
			"Investment App",
			filters={
				"party": self.party,  # Match party with the current instance's party
				"end_date": self.posting_date,  # Match end_date with posting_date from the current instance
				"transaction_type": ["in", ["Re-invest", "Invest"]]  # Match transaction type
			},
			fields=["name", "posting_date", "end_date", "withdral_amount", "amount", "party", "transaction_type"]
		)

		for investment in investments:
			investment_doc = frappe.get_doc("Investment App", investment.name)
			
			total_amount = flt(self.amount_withrowned) + flt(self.interets_withrowned)

			# Calculate the new withdrawal_amount
			new_withdrawal_amount = flt(investment_doc.withdral_amount) - total_amount  # Ensure calculations are float

			# Ensure withdrawal_amount does not go below zero
			if new_withdrawal_amount < 0:
				frappe.throw(_("Withdrawal amount cannot be negative for {0}. Current amount: {1}, Deduction: {2}").format(
					investment_doc.name, investment_doc.withdral_amount, investment_doc.amount))

			# Update the withdrawal_amount
			investment_doc.withdral_amount = new_withdrawal_amount

			# Set or retain the party field
			if not investment_doc.party:  # If party is not set, assign a default value
				investment_doc.party = self.party  # Retain the current party

			# Save the updated document
			investment_doc.save(ignore_permissions=True)

			# Show a message to the user
			frappe.msgprint(_("Withdrawal amount updated to {0} for {1}. Party set to {2}.").format(
				new_withdrawal_amount, investment_doc.name, investment_doc.party))         
 
	def create_deposit_journal_entry(self):
		"""Delegate deposit journal entries to the custom API"""
		from loan_investment_app.custom_api.journal_entry import create_journal_entry
		return create_journal_entry(
			posting_date=self.posting_date,
			amount=self.amount,
			party_type="Member",
			party=self.party,
			mode_of_payment=self.mode_of_payment,
			trans_type="Deposit",
			remarks=self.remarks
		)

	@frappe.whitelist()
	def create_journal_entry(self):
		try:
			if self.transaction_type == "Deposit":
				return self.create_deposit_journal_entry()

			# For other transaction types, use internal logic
			company, default_paid_to_account = self.get_default_company_and_account()
			accounts = self.get_investment_accounts()

			journal_entry = frappe.new_doc('Journal Entry')
			journal_entry.voucher_type = 'Journal Entry'
			journal_entry.company = accounts['company_set']
			journal_entry.posting_date = self.posting_date
			journal_entry.user_remark = self.remarks
			journal_entry.custom_transaction_type = self.transaction_type
			journal_entry.custom_investmet_id = self.name

			if self.transaction_type == "Invest":
				# Only post principal movement
				self.add_journal_entry_row(journal_entry, accounts['capital_account'], self.amount, 0, cost_center=accounts['cost_center'])
				self.add_journal_entry_row(journal_entry, accounts['portfolio_account'], 0, self.amount, cost_center=accounts['cost_center'])
				frappe.msgprint(_("Principal amount posted successfully. Interest will be posted monthly according to schedule."))

			elif self.transaction_type == "Re-invest":
				# Only post principal movement for reinvestment
				self.add_journal_entry_row(journal_entry, accounts['withdrawal_payable_account'], self.amount, 0, cost_center=accounts['cost_center'])
				self.add_journal_entry_row(journal_entry, accounts['portfolio_account'], 0, self.amount, cost_center=accounts['cost_center'])
				frappe.msgprint(_("Principal amount posted successfully. Interest will be posted monthly according to schedule."))

			elif self.transaction_type == "Withdraw":
				# Handle withdrawal with updated amounts
				# 1. Credit Investor Withdrawal Payable Account with total amount (Principal + Interest)
				self.add_journal_entry_row(journal_entry, accounts['withdrawal_payable_account'], 0, self.total_amount_after_tax, cost_center=accounts['cost_center'])
				
				# 2. Debit Investment Portfolio Account with Principal amount
				self.add_journal_entry_row(journal_entry, accounts['portfolio_account'], self.amount_withrowned, 0, cost_center=accounts['cost_center'])
				
				# 3. Debit Interest on Investment Payable Account with Interest amount
				if self.total_interest_earned:
					self.add_journal_entry_row(journal_entry, accounts['investment_interest'], self.total_interest_earned, 0, cost_center=accounts['cost_center'])

			elif self.transaction_type == "Request for Payments":
				self.add_journal_entry_row(journal_entry, accounts['withdrawal_payable_account'], self.amount, 0, cost_center=accounts['cost_center'])
				self.add_journal_entry_row(journal_entry, self.pay_to, 0, self.amount, cost_center=accounts['cost_center'])

			else:
				frappe.throw(_("Invalid transaction type: {0}").format(self.transaction_type))

			journal_entry.insert()
			journal_entry.submit()
			return {"message": _("Journal Entry created successfully!"), "name": journal_entry.name}

		except Exception as e:
			frappe.log_error(message=str(e), title=_("Failed to create Journal Entry"))
			frappe.throw(_("Failed to create Journal Entry: {0}").format(str(e)))

	@frappe.whitelist()
	def create_schedule_journal_entries(self):
		"""Modified to not post entries immediately"""
		try:
			if self.transaction_type == "Invest" or self.transaction_type == "Re-invest":
				# Just validate the accounts exist
				self.get_investment_accounts()
				return True
			
		except Exception as e:
			frappe.log_error(message=str(e), title=_("Failed to validate Investment Schedule"))
			frappe.throw(_("Failed to validate Investment Schedule: {0}").format(str(e)))

	def get_default_company_and_account(self):
		# Get company from Investment Settings
		company = frappe.db.get_single_value('Investment Settings', 'company')
		if not company:
			frappe.throw(_("Company not configured in Investment Settings."))

		default_paid_to_account = frappe.db.get_value(
			"Mode of Payment Account", 
			{"parent": self.mode_of_payment, "company": company}, 
			"default_account"
		)
		if not default_paid_to_account:
			frappe.throw(_("Default account for the mode of payment not found. Please check the configuration."))

		return company, default_paid_to_account

	def get_investment_accounts(self):
		investment_account = frappe.db.sql("""
			SELECT capital_account, investment_interest, percent_interest_amount_account,
			portfolio_account, company, witholding_tax_payable,cost_center,investor_withdrawal_payable_account
			FROM `tabInvestment Settings`
			LIMIT 1
		""", as_dict=True)
		
		if not investment_account:
			frappe.throw(_("Investment account details not found in Investment Settings."))

		return {
			'capital_account': investment_account[0]['capital_account'],
			'company_set': investment_account[0]['company'],
			'witholding_tax_payable': investment_account[0]['witholding_tax_payable'],
			'cost_center': investment_account[0]['cost_center'],
			'portfolio_account': investment_account[0]['portfolio_account'],
			'investment_interest': investment_account[0]['investment_interest'],
			'withdrawal_payable_account': investment_account[0]['investor_withdrawal_payable_account'],
			'percent_interest_account': investment_account[0]['percent_interest_amount_account']
		}

	def add_journal_entry_row(self, journal_entry, account, debit, credit, cost_center=None):
		journal_entry.append('accounts', {
			'account': account,
			'debit_in_account_currency': debit,
			'credit_in_account_currency': credit,
			'party_type': "Member",
			'party': self.party,
			'cost_center': cost_center,
			'user_remark': self.remarks
		})

def cleanup_failed_interest_postings():
	"""
	Cleanup and retry failed interest postings.
	Runs daily to ensure no interest postings are missed.
	"""
	try:
		# Get failed postings from the last 7 days
		seven_days_ago = add_days(today(), -7)
		failed_logs = frappe.get_all(
			"Error Log",
			filters={
				"creation": [">=", seven_days_ago],
				"title": "Monthly Interest Posting Error"
			},
			fields=["name", "error"]
		)
		
		if failed_logs:
			# Send notification about failed postings
			frappe.sendmail(
				recipients=[frappe.get_value("Investment Settings", None, "error_report_email")],
				subject="Failed Interest Postings Report",
				message=f"The following interest postings failed:\n\n" + 
						"\n".join([f"- {log.error}" for log in failed_logs])
			)
			
			# Attempt to repost
			post_monthly_interest()
			
	except Exception as e:
		frappe.log_error(
			message=f"Failed to cleanup interest postings: {str(e)}",
			title="Interest Posting Cleanup Error"
		)

def update_investment_balances():
	"""
	Hourly update of investment balances.
	Updates cached balances for quick retrieval.
	"""
	try:
		# Get all active investments
		investments = frappe.get_all(
			"Investment App",
			filters={
				"docstatus": 1,
				"investment_status": "Approved",
				"transaction_type": ["in", ["Invest", "Re-invest"]]
			},
			fields=["name", "party"]
		)
		
		for inv in investments:
			try:
				balances = get_cached_balances(inv.party)
				if not balances:
					continue
					
				# Store cache as a single string value
				cache_key = f"investment_balances:{inv.party}"
				frappe.cache().set_value(
					key=cache_key,
					val=frappe.as_json({
						"portfolio": balances.get("portifolia_account", 0),
						"wallet": balances.get("balance_walet", 0),
						"last_updated": str(now())
					}),
					expires_in_sec=3600
				)
				
			except Exception as e:
				frappe.log_error(
					message=f"Failed to update balance for investment {inv.name}: {str(e)}",
					title="Balance Update Error"
				)
				
	except Exception as e:
		frappe.log_error(
			message=f"Failed to run balance updates: {str(e)}",
			title="Balance Update Error"
		)

def update_balances_on_change(doc, method=None):
	"""Update balances when investment document changes"""
	try:
		if not doc.party:
			return
			
		balances = get_cached_balances(doc.party)
		if not balances:
			return
			
		# Store cache as a single string value
		cache_key = f"investment_balances:{doc.party}"
		frappe.cache().set_value(
			key=cache_key,
			val=frappe.as_json({
				"portfolio": balances.get("portifolia_account", 0),
				"wallet": balances.get("balance_walet", 0),
				"last_updated": str(now())
			}),
			expires_in_sec=3600
		)
		
		# Trigger client-side refresh
		frappe.publish_realtime(
			'investment_balance_updated',
			{
				"party": doc.party,
				"balances": balances
			},
			after_commit=True
		)
		
	except Exception as e:
		frappe.log_error(
			message=f"Failed to update balances for {doc.name}: {str(e)}",
			title="Balance Update Error"
		)




def update_balances_after_je(doc, method=None):
	"""Update investment balances after journal entry submission/cancellation"""
	try:
		if doc.custom_investmet_id:
			investment = frappe.get_doc("Investment App", doc.custom_investmet_id)
			if investment and investment.party:
				update_balances_on_change(investment)
			
	except Exception as e:
		frappe.log_error(
			message=f"Failed to update balances after JE {doc.name}: {str(e)}",
			title="Balance Update Error"
		)
