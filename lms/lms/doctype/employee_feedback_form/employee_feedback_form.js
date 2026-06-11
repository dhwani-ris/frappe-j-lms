// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Feedback Form", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		const api = "lms.lms.custom.employee_feedback";

		if (frm.doc.status !== "Completed") {
			frm.add_custom_button(__("Complete & Submit"), () => {
				frappe.call({
					method: `${api}.complete_feedback`,
					args: { name: frm.doc.name },
					freeze: true,
					callback: () => frm.reload_doc(),
				});
			}).addClass("btn-primary");
		} else {
			frm.add_custom_button(__("Reopen for Corrections"), () => {
				frappe.call({
					method: `${api}.reopen_feedback`,
					args: { name: frm.doc.name },
					freeze: true,
					callback: () => frm.reload_doc(),
				});
			});
		}
	},
});
