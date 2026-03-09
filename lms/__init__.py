__version__ = "2.44.0"


# Monkey patch other apps' permission functions to hide them from apps page
def _patch_app_permissions():
	"""Patch permission functions of other apps to hide them"""
	try:
		import erpnext
		erpnext.check_app_permission = lambda: False
	except Exception:
		pass

	try:
		import hrms.hr.utils
		hrms.hr.utils.check_app_permission = lambda: False
	except Exception:
		pass

	try:
		import insights.permissions
		insights.permissions.check_app_permission = lambda: False
	except Exception:
		pass


# Apply patches on module import
_patch_app_permissions()
