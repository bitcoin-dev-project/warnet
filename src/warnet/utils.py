import time
import functools

def exponential_backoff(max_retries=5, base_delay=1, max_delay=32):
    """
    A decorator for exponential backoff.

    Parameters:
    - max_retries: Maximum number of retries before giving up.
    - base_delay: Initial delay in seconds.
    - max_delay: Maximum delay in seconds.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print(f"rpc error:\n\t{e}")
                    retries += 1
                    if retries == max_retries:
                        raise e
                    delay = min(base_delay * (2 ** retries), max_delay)
                    print(f"retry in {delay} seconds...")
                    time.sleep(delay)
        return wrapper
    return decorator
