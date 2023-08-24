import email_validator
email_validator.SPECIAL_USE_DOMAIN_NAMES.remove("test")
email_validator.CHECK_DELIVERABILITY=True
from decouple import config


def is_dev_env():
	if config('ENVIROMENT') == "development":
		return True;
	return False;

def _validate_email(email):
	try:
		emailinfo = email_validator.validate_email(email,test_environment=is_dev_env())
		email = emailinfo.normalized
		return email, False

	except email_validator.EmailNotValidError as e:
		return str(e), True