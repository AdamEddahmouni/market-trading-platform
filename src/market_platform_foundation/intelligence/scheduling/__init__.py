"""BUILD 10 inference scheduler public API."""

from .batching import jobs_batch_compatible, plan_batches
from .errors import (
    SchedulerAdmissionError,
    SchedulerConfigurationError,
    SchedulerDispatchError,
    SchedulerError,
    SchedulerResourceError,
    SchedulerStateTransitionError,
)
from .executor import (
    DispatchReceipt,
    InferenceDispatchBatch,
    InferenceExecutor,
    RecordingInferenceExecutor,
)
from .identity import INFERENCE_JOB_IDENTITY_VERSION, derive_dispatch_batch_id, derive_inference_job_id
from .models import (
    AdapterAction,
    CancellationReason,
    QueueOrderingKey,
    ResidencyAction,
    ResidencyPlan,
    SchedulerJobRuntime,
    SchedulerJobState,
    SchedulerPassResult,
    SchedulerStateSummary,
    SubmitRouteResult,
)
from .observer import SchedulerEvent, SchedulerEventKind, SchedulerObserver
from .policy import PRIORITY_RANK, SchedulerPolicyV1, priority_rank
from .profiles import (
    DEFAULT_EXECUTION_PROFILE_REGISTRY,
    ExecutionProfileRegistry,
    InferenceExecutionProfile,
    ResourceClass,
)
from .residency import plan_residency, residency_affinity_rank
from .resources import (
    ConfiguredResourceProvider,
    ResourceProvider,
    ResourceSnapshot,
    StaticResourceProvider,
    default_resource_snapshot,
)
from .scheduler import InferenceScheduler

__all__ = [
    "DEFAULT_EXECUTION_PROFILE_REGISTRY",
    "AdapterAction",
    "CancellationReason",
    "ConfiguredResourceProvider",
    "DispatchReceipt",
    "ExecutionProfileRegistry",
    "INFERENCE_JOB_IDENTITY_VERSION",
    "InferenceDispatchBatch",
    "InferenceExecutionProfile",
    "InferenceExecutor",
    "InferenceScheduler",
    "PRIORITY_RANK",
    "QueueOrderingKey",
    "RecordingInferenceExecutor",
    "ResidencyAction",
    "ResidencyPlan",
    "ResourceClass",
    "ResourceProvider",
    "ResourceSnapshot",
    "SchedulerAdmissionError",
    "SchedulerConfigurationError",
    "SchedulerDispatchError",
    "SchedulerError",
    "SchedulerEvent",
    "SchedulerEventKind",
    "SchedulerJobRuntime",
    "SchedulerJobState",
    "SchedulerObserver",
    "SchedulerPassResult",
    "SchedulerPolicyV1",
    "SchedulerResourceError",
    "SchedulerStateSummary",
    "SchedulerStateTransitionError",
    "StaticResourceProvider",
    "SubmitRouteResult",
    "default_resource_snapshot",
    "derive_dispatch_batch_id",
    "derive_inference_job_id",
    "jobs_batch_compatible",
    "plan_batches",
    "plan_residency",
    "priority_rank",
    "residency_affinity_rank",
]
