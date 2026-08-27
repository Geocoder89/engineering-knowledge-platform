from datetime import datetime, timedelta

MAX_PROCESSING_ATTEMPTS = 3
PROCESSING_RETRY_BASE_DELAY_SECONDS = 30


class ProcessingJobNotRetryable(ValueError):
    def __init__(self, current_status: str) -> None:
        super().__init__(
            "Only failed processing jobs can be retried; "
            f"current status is '{current_status}'"
        )


class ProcessingJobRetryLimitExceeded(ValueError):
    def __init__(self) -> None:
        super().__init__("Processing job has reached the maximum of 3 attempts ")


def validate_processing_job_retry(
    *,
    status: str,
    attempt_count: int,
) -> None:
    if status != "failed":
        raise ProcessingJobNotRetryable(status)
    if attempt_count >= MAX_PROCESSING_ATTEMPTS:
        raise ProcessingJobRetryLimitExceeded()


def calculate_processing_job_retry_at(
    *,
    attempted_at: datetime,
    attempt_count: int,
) -> datetime:
    if attempt_count <= 0:
        raise ValueError("Processing job attempt count must be greater than zero")

    if attempt_count >= MAX_PROCESSING_ATTEMPTS:
        raise ProcessingJobRetryLimitExceeded()

    delay_seconds = PROCESSING_RETRY_BASE_DELAY_SECONDS * 2 ** (attempt_count - 1)

    return attempted_at + timedelta(
        seconds=delay_seconds,
    )
