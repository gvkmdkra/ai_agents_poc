"""
Async Call Processing Tasks
Handles high-volume call initiation and webhook processing
"""
import asyncio
from typing import Dict, Any, Optional
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


def run_async(coro):
    """Helper to run async code in Celery tasks"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(
    bind=True,
    name="app.tasks.call_tasks.initiate_call_task",
    max_retries=3,
    default_retry_delay=5,
    rate_limit="100/m",  # 100 calls per minute per worker
    queue="calls"
)
def initiate_call_task(
    self,
    phone_number: str,
    system_prompt: Optional[str] = None,
    greeting_message: Optional[str] = None,
    tenant_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Async task to initiate a call
    Allows parallel processing of many calls
    """
    logger.info(f"Initiating call to {phone_number} (task_id: {self.request.id})")

    try:
        async def _initiate():
            from app.services.call_manager import get_call_manager
            manager = get_call_manager()

            result = await manager.initiate_call(
                phone_number=phone_number,
                system_prompt=system_prompt,
                greeting_message=greeting_message,
                tenant_id=tenant_id
            )
            return result

        result = run_async(_initiate())

        logger.info(f"Call initiated successfully: {result.get('call_id')}")
        return {
            "status": "success",
            "call_id": result.get("call_id"),
            "task_id": self.request.id,
            "phone_number": phone_number
        }

    except Exception as e:
        logger.error(f"Failed to initiate call: {e}")

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "status": "failed",
            "error": str(e),
            "task_id": self.request.id,
            "phone_number": phone_number
        }


@shared_task(
    bind=True,
    name="app.tasks.call_tasks.process_webhook_task",
    max_retries=5,
    default_retry_delay=2,
    rate_limit="500/m",  # 500 webhooks per minute
    queue="webhooks"
)
def process_webhook_task(
    self,
    webhook_type: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Async task to process webhooks
    Handles Twilio and Ultravox callbacks
    """
    logger.info(f"Processing {webhook_type} webhook (task_id: {self.request.id})")

    try:
        async def _process():
            from app.services.call_manager import get_call_manager
            manager = get_call_manager()

            if webhook_type == "twilio_status":
                call_sid = payload.get("CallSid")
                status = payload.get("CallStatus")
                await manager.handle_twilio_status(call_sid, status)

            elif webhook_type == "ultravox_event":
                call_id = payload.get("call_id")
                event_type = payload.get("event_type")
                await manager.handle_ultravox_event(call_id, event_type, payload)

            return {"processed": True}

        result = run_async(_process())

        return {
            "status": "success",
            "webhook_type": webhook_type,
            "task_id": self.request.id
        }

    except Exception as e:
        logger.error(f"Failed to process webhook: {e}")

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)

        return {
            "status": "failed",
            "error": str(e),
            "task_id": self.request.id
        }


@shared_task(
    name="app.tasks.call_tasks.batch_initiate_calls",
    queue="calls"
)
def batch_initiate_calls(
    phone_numbers: list,
    system_prompt: Optional[str] = None,
    greeting_message: Optional[str] = None,
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Batch initiate multiple calls in parallel
    Useful for campaign-style calling
    """
    logger.info(f"Batch initiating {len(phone_numbers)} calls")

    # Create a group of tasks for parallel execution
    from celery import group

    tasks = group(
        initiate_call_task.s(
            phone_number=number,
            system_prompt=system_prompt,
            greeting_message=greeting_message,
            tenant_id=tenant_id
        )
        for number in phone_numbers
    )

    # Execute all tasks in parallel
    result = tasks.apply_async()

    return {
        "status": "batch_queued",
        "total_calls": len(phone_numbers),
        "group_id": str(result.id)
    }
