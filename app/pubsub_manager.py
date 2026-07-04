import os
import json
import asyncio
import logging
import threading
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NeatyPubSub")

# Global task state management
# Mapping of task_id -> asyncio.Event
pending_tasks: Dict[str, asyncio.Event] = {}
# Mapping of task_id -> dict (status, report, destination_dir, error)
task_results: Dict[str, Dict[str, Any]] = {}

# Try to import GCP Pub/Sub
try:
    from google.cloud import pubsub_v1
    from google.api_core.exceptions import AlreadyExists

    GCP_PUBSUB_AVAILABLE = True
except ImportError:
    GCP_PUBSUB_AVAILABLE = False


class PubSubManager:
    def __init__(self):
        self.use_gcp = False
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.topic_id = os.getenv("PUBSUB_TOPIC", "neaty-tasks")
        self.subscription_id = os.getenv("PUBSUB_SUBSCRIPTION", "neaty-tasks-sub")

        # Local queue fallback
        self.local_queue: Optional[asyncio.Queue] = None
        self.loop = None

        # Detect whether to use GCP Pub/Sub or Local Fallback
        # We use GCP if GCP Pub/Sub is available, GOOGLE_CLOUD_PROJECT is set, and GOOGLE_GENAI_USE_ENTERPRISE is true or we explicitly enable it
        enable_gcp_pubsub = os.getenv("ENABLE_GCP_PUBSUB", "").upper() == "TRUE"
        use_enterprise = os.getenv("GOOGLE_GENAI_USE_ENTERPRISE", "").upper() == "TRUE"

        if (
            GCP_PUBSUB_AVAILABLE
            and self.project_id
            and (enable_gcp_pubsub or use_enterprise)
        ):
            self.use_gcp = True
            logger.info(f"Initialized Pub/Sub in GCP Mode (Project: {self.project_id})")
        else:
            self.use_gcp = False
            logger.info("Initialized Pub/Sub in Local Fallback Mode (In-Memory Queue)")

    def setup_gcp_resources(self):
        """Creates GCP Pub/Sub Topic and Subscription if they don't exist."""
        if not self.use_gcp:
            return

        try:
            publisher = pubsub_v1.PublisherClient()
            subscriber = pubsub_v1.SubscriberClient()

            topic_path = publisher.topic_path(self.project_id, self.topic_id)
            subscription_path = subscriber.subscription_path(
                self.project_id, self.subscription_id
            )

            # Try to create Topic
            try:
                publisher.create_topic(request={"name": topic_path})
                logger.info(f"Created GCP Pub/Sub Topic: {topic_path}")
            except AlreadyExists:
                logger.info(f"GCP Pub/Sub Topic already exists: {topic_path}")

            # Try to create Subscription
            try:
                subscriber.create_subscription(
                    request={"name": subscription_path, "topic": topic_path}
                )
                logger.info(f"Created GCP Pub/Sub Subscription: {subscription_path}")
            except AlreadyExists:
                logger.info(
                    f"GCP Pub/Sub Subscription already exists: {subscription_path}"
                )
        except Exception as e:
            logger.error(
                f"Error setting up GCP Pub/Sub resources: {e}. Falling back to Local Mode."
            )
            self.use_gcp = False

    async def initialize(self, loop=None):
        """Initializes queues or cloud connections."""
        self.loop = loop or asyncio.get_running_loop()
        if self.use_gcp:
            # Setup GCP resources in a background thread to prevent blocking
            await asyncio.to_thread(self.setup_gcp_resources)

        if not self.use_gcp:
            # Local async queue
            self.local_queue = asyncio.Queue()
            logger.info("Local fallback queue initialized successfully.")

    async def publish(self, task_id: str, source_dir: str, destination_dir: str):
        """Publishes an organization task to the Pub/Sub topic or local queue."""
        payload = {
            "task_id": task_id,
            "source_dir": source_dir,
            "destination_dir": destination_dir,
        }
        message_bytes = json.dumps(payload).encode("utf-8")

        if self.use_gcp:
            try:
                publisher = pubsub_v1.PublisherClient()
                topic_path = publisher.topic_path(self.project_id, self.topic_id)
                # Publish to GCP Pub/Sub in thread pool
                future = await asyncio.to_thread(
                    publisher.publish, topic_path, message_bytes
                )
                logger.info(
                    f"Published task {task_id} to GCP Topic. Message ID: {future.result()}"
                )
                return
            except Exception as e:
                logger.error(
                    f"Failed to publish to GCP Pub/Sub: {e}. Falling back to local queue publishing."
                )
                # If cloud fails, fall back to local queue
                if self.local_queue is None:
                    self.local_queue = asyncio.Queue()

        # Local Queue Publish
        if self.local_queue is not None:
            await self.local_queue.put(payload)
            logger.info(f"Published task {task_id} to Local Queue.")
        else:
            raise RuntimeError("No active Pub/Sub queue available to publish to.")

    async def start_worker(self):
        """Starts the background subscriber/worker to listen and run tasks."""
        if self.use_gcp:
            # Start GCP streaming pull in a background thread
            threading.Thread(target=self._gcp_subscriber_thread, daemon=True).start()
            logger.info("GCP background subscriber thread started.")
        else:
            # Start local async consumer task
            asyncio.create_task(self._local_async_worker())
            logger.info("Local background async worker task started.")

    async def _process_task(self, payload: dict):
        """Helper to run the ADK workflow node and save the resulting report."""
        task_id = payload.get("task_id")
        source_dir = payload.get("source_dir")
        destination_dir = payload.get("destination_dir")

        logger.info(
            f"Worker processing task {task_id}: organizing {source_dir} -> {destination_dir}"
        )

        try:
            # Dynamically import runner inside worker to avoid circular dependency
            from neaty_agent import app as adk_app, WorkflowInput
            from google.adk.runners import InMemoryRunner

            # Setup runner and run
            runner = InMemoryRunner(app=adk_app)
            workflow_input = WorkflowInput(
                source_dir=source_dir, destination_dir=destination_dir
            )

            # Run ADK graph workflow
            result = await runner.run_debug(workflow_input.model_dump_json())

            # Read organization report from destination_dir
            report_path = os.path.join(destination_dir, "ORGANIZATION_REPORT.md")
            report_content = ""
            if os.path.exists(report_path):
                with open(report_path, "r", encoding="utf-8") as f:
                    report_content = f.read()

            # Save successful result
            task_results[task_id] = {
                "status": "success",
                "message": "Files organized successfully!",
                "destination_dir": destination_dir,
                "report": report_content,
                "result_summary": str(result),
            }
            logger.info(f"Task {task_id} organized successfully!")

        except Exception as e:
            import traceback

            error_trace = traceback.format_exc()
            logger.error(f"Error processing task {task_id}: {e}")
            task_results[task_id] = {
                "status": "error",
                "error": str(e),
                "trace": error_trace,
            }
        finally:
            # Signal the waiting HTTP response that the task is finished
            if task_id in pending_tasks:
                # Call set() thread-safely in case we are in GCP thread
                self.loop.call_soon_threadsafe(pending_tasks[task_id].set)

    async def _local_async_worker(self):
        """Infinite loop consuming tasks from the local asyncio queue."""
        while True:
            try:
                payload = await self.local_queue.get()
                await self._process_task(payload)
                self.local_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in local worker loop: {e}")
                await asyncio.sleep(1)

    def _gcp_subscriber_thread(self):
        """Thread that runs GCP Subscriber and processes streaming pull messages."""
        subscriber = pubsub_v1.SubscriberClient()
        subscription_path = subscriber.subscription_path(
            self.project_id, self.subscription_id
        )

        def callback(message):
            try:
                # Decode message
                payload = json.loads(message.data.decode("utf-8"))
                logger.info(f"GCP Subscriber received message: {payload}")

                # We need to run the async processing in the main event loop
                asyncio.run_coroutine_threadsafe(self._process_task(payload), self.loop)

                # Acknowledge the message
                message.ack()
            except Exception as e:
                logger.error(f"Error in GCP subscriber callback: {e}")
                # Nack so the message gets retried
                message.nack()

        streaming_pull_future = subscriber.subscribe(
            subscription_path, callback=callback
        )
        logger.info(f"Listening for GCP messages on: {subscription_path}")

        try:
            # Keep the subscriber thread alive
            streaming_pull_future.result()
        except Exception as e:
            logger.error(f"GCP subscriber thread error: {e}")
            streaming_pull_future.cancel()


# Instantiate global pubsub manager
pubsub_manager = PubSubManager()
