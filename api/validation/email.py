import email_validator
from decouple import config

email_validator.SPECIAL_USE_DOMAIN_NAMES.remove("test")
email_validator.CHECK_DELIVERABILITY = True


def is_dev_env():
    if config("ENVIROMENT") == "development":
        return True
    return False


def _validate_email(email):
    try:
        emailinfo = email_validator.validate_email(email, test_environment=is_dev_env())
        email = emailinfo.normalized
        return email, False

    except email_validator.EmailNotValidError as e:
        return str(e), True
