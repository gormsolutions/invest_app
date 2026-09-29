import frappe

@frappe.whitelist()
def update_workflow_to_active(workflow_name, is_active=1):
    try:
        # Fetch the workflow document
        workflow = frappe.get_doc('Workflow', workflow_name)

        # Check if the workflow was found
        if workflow:
            # Check if the current status is already the desired status f"Workflow '{workflow_name}' is already set to {'active' if is_active else 'inactive'}."
            if workflow.is_active == is_active:
                return 

            # Set is_active based on the provided argument (1 for active, 0 for inactive)
            workflow.is_active = is_active
            workflow.save()  # Save the changes
            frappe.db.commit() # Commit the transaction to the database
            
            # Notify the user about the updatef"Workflow '{workflow_name}' updated to {'active' if is_active else 'inactive'} successfully."
            return 
        else:
            # If workflow is not found, create a new inactive workflow f"Workflow '{workflow_name}' is set to inactive as it does not exist."
            # frappe.msgprint(f"Workflow '{workflow_name}' not found. Setting to inactive.")
            new_workflow = frappe.get_doc({
                'doctype': 'Workflow',
                'workflow_name': workflow_name,
                'is_active': 0
            })
            new_workflow.insert()
            frappe.db.commit()
            return 
    
    except frappe.DoesNotExistError:
        return f"Workflow '{workflow_name}' does not exist. Setting to inactive."
    except Exception as e:
        return f"An error occurred: {e}"
