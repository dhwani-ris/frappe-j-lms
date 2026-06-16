# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class EmployeeFeedbackSession(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		feedback: DF.TextEditor | None
		meeting_datetime: DF.Datetime | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		recorded: DF.Check
		recorded_by: DF.Link | None
		recorded_on: DF.Datetime | None
	# end: auto-generated types

	pass
