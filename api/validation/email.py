from email_validator import validate_email, EmailNotValidError
from decouple import config


def _validate_email(email):
	try:
		emailinfo = validate_email(email,check_deliverability=False)
		email = emailinfo.normalized
		return email, False

	except EmailNotValidError as e:
		return str(e), True