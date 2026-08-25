MAX_PROCESSING_ATTEMPTS = 3


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
