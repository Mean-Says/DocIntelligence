from arq.connections import RedisSettings
from app.config import settings
from app.workers.tasks import process_document, run_learning_loop


class WorkerSettings:
    functions = [process_document, run_learning_loop]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 120  # segundos
    keep_result = 3600  # guarda resultado por 1h para polling
