import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Проверка возраста
def is_age_in_range(user_age: int, event_age_range: str) -> bool:
    if not event_age_range:
        return False

    try:
        if '-' in event_age_range:
            min_age, max_age = map(int, event_age_range.split('-'))
            return min_age <= user_age <= max_age
        elif event_age_range.endswith('+'):
            return user_age >= int(event_age_range[:-1])
        else:
            return int(event_age_range) == user_age
    except (ValueError, AttributeError):
        logger.error(f'Invalid age range format: {event_age_range}')
        return False
