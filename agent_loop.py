"""
Custom Agent Loop Implementation
Provides orchestration for multi-agent fact checking without CrewAI dependency
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Task:
    """
    Represents a task to be executed by an agent.

    Attributes:
        id: Unique task identifier
        description: Task description (becomes the prompt)
        agent: The agent that will execute this task
        depends_on: List of task IDs this task depends on
        async_execution: Whether this task can run in parallel with others
        expected_output: Description of expected output (for documentation)
        context_keys: Keys from execution context this task needs
    """

    id: str
    description: str
    agent: "BaseAgent"
    depends_on: List[str] = field(default_factory=list)
    async_execution: bool = False
    expected_output: str = ""
    context_keys: List[str] = field(default_factory=list)


@dataclass
class ExecutionContext:
    """
    Shared state between agents during execution.

    Attributes:
        state: Dict storing results from completed tasks
        metadata: Dict for tracking metadata (iteration count, timestamps, etc.)
        original_text: The original text being fact-checked
    """

    state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    original_text: str = ""

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from state with default fallback."""
        return self.state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value in state."""
        self.state[key] = value

    def update(self, updates: Dict[str, Any]) -> None:
        """Update multiple values in state."""
        self.state.update(updates)


@dataclass
class ExecutionResult:
    """
    Result of orchestrator execution.

    Attributes:
        success: Whether execution completed successfully
        report: The final FactCheckReport (if successful)
        error: Error message (if failed)
        execution_time: Total execution time in seconds
        task_results: Dict of results from each task
    """

    success: bool
    report: Any = None
    error: str = ""
    execution_time: float = 0.0
    task_results: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """
    Abstract base class for all agents.

    Each agent represents a specialized role in the fact-checking process.
    """

    def __init__(
        self,
        name: str,
        role: str,
        goal: str,
        backstory: str = "",
        max_retries: int = 3,
        verbose: bool = True,
    ):
        """
        Initialize base agent.

        Args:
            name: Agent name (e.g., "claim_extractor")
            role: Agent role description
            goal: What the agent aims to accomplish
            backstory: Agent's context and expertise
            max_retries: Maximum number of retry attempts
            verbose: Whether to log detailed information
        """
        self.name = name
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.max_retries = max_retries
        self.verbose = verbose

    @abstractmethod
    async def execute(self, task: Task, context: ExecutionContext) -> Any:
        """
        Execute the task assigned to this agent.

        Args:
            task: The task to execute
            context: Shared execution context

        Returns:
            Result of task execution (format depends on agent)
        """
        pass

    def log(self, message: str, level: str = "info") -> None:
        """Log message if verbose is enabled."""
        if self.verbose:
            log_func = getattr(logger, level, logger.info)
            log_func(f"[{self.name}] {message}")


class AgentOrchestrator:
    """
    Orchestrates execution of tasks by agents.

    Handles:
    - Task dependency resolution
    - Parallel execution where possible
    - Error handling and retries
    - Progress tracking
    """

    def __init__(
        self,
        verbose: bool = True,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize orchestrator.

        Args:
            verbose: Whether to log detailed execution info
            progress_callback: Optional callback for progress updates
        """
        self.verbose = verbose
        self.progress_callback = progress_callback

    def log(self, message: str, level: str = "info") -> None:
        """Log message and call progress callback if set."""
        if self.verbose:
            log_func = getattr(logger, level, logger.info)
            log_func(message)

        if self.progress_callback:
            self.progress_callback(message)

    async def run(
        self, tasks: List[Task], context: Optional[ExecutionContext] = None
    ) -> ExecutionResult:
        """
        Execute all tasks in the correct order.

        Args:
            tasks: List of tasks to execute
            context: Optional execution context (creates new if not provided)

        Returns:
            ExecutionResult with final report or error
        """
        start_time = datetime.now()
        context = context or ExecutionContext()

        try:
            self.log("🚀 Starting agent orchestration")

            # Build dependency graph
            task_map = {t.id: t for t in tasks}
            self._validate_dependencies(tasks, task_map)

            # Execute tasks in topological order
            completed_tasks = set()
            task_results = {}

            while len(completed_tasks) < len(tasks):
                # Find tasks ready to execute
                ready_tasks = [
                    t
                    for t in tasks
                    if t.id not in completed_tasks
                    and all(dep in completed_tasks for dep in t.depends_on)
                ]

                if not ready_tasks:
                    raise RuntimeError("Circular dependency detected in task graph")

                # Separate async and sync tasks
                async_tasks = [t for t in ready_tasks if t.async_execution]
                sync_tasks = [t for t in ready_tasks if not t.async_execution]

                # Execute async tasks in parallel
                if async_tasks:
                    self.log(
                        f"⚡ Executing {len(async_tasks)} tasks in parallel: {[t.id for t in async_tasks]}"
                    )
                    results = await asyncio.gather(
                        *[self._execute_task(t, context) for t in async_tasks],
                        return_exceptions=True,
                    )

                    for task, result in zip(async_tasks, results, strict=False):
                        if isinstance(result, Exception):
                            raise result
                        task_results[task.id] = result
                        context.set(task.id, result)
                        completed_tasks.add(task.id)

                # Execute sync tasks sequentially
                for task in sync_tasks:
                    self.log(f"🔄 Executing task: {task.id}")
                    result = await self._execute_task(task, context)
                    task_results[task.id] = result
                    context.set(task.id, result)
                    completed_tasks.add(task.id)

            # Get final report (should be in the last task's result)
            final_task_id = tasks[-1].id
            report = task_results.get(final_task_id)

            execution_time = (datetime.now() - start_time).total_seconds()
            self.log(f"✅ Orchestration completed in {execution_time:.2f}s")

            return ExecutionResult(
                success=True,
                report=report,
                execution_time=execution_time,
                task_results=task_results,
            )

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self.log(f"❌ Orchestration failed: {str(e)}", level="error")
            return ExecutionResult(
                success=False,
                error=str(e),
                execution_time=execution_time,
                task_results=task_results if "task_results" in locals() else {},
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _execute_task(self, task: Task, context: ExecutionContext) -> Any:
        """
        Execute a single task with retry logic.

        Args:
            task: Task to execute
            context: Execution context

        Returns:
            Task execution result
        """
        try:
            self.log(f"📝 Agent {task.agent.name} starting task: {task.id}")

            # Prepare context for task
            task_context = ExecutionContext(
                state=context.state.copy(),
                metadata=context.metadata.copy(),
                original_text=context.original_text,
            )

            # Execute task
            result = await task.agent.execute(task, task_context)

            self.log(f"✅ Agent {task.agent.name} completed task: {task.id}")
            return result

        except Exception as e:
            self.log(
                f"❌ Agent {task.agent.name} failed task {task.id}: {str(e)}",
                level="error",
            )
            raise

    def _validate_dependencies(
        self, tasks: List[Task], task_map: Dict[str, Task]
    ) -> None:
        """
        Validate that all task dependencies exist.

        Args:
            tasks: List of all tasks
            task_map: Dict mapping task IDs to tasks

        Raises:
            ValueError: If invalid dependencies are found
        """
        for task in tasks:
            for dep in task.depends_on:
                if dep not in task_map:
                    raise ValueError(
                        f"Task '{task.id}' depends on non-existent task '{dep}'"
                    )

                # Check for self-dependency
                if dep == task.id:
                    raise ValueError(f"Task '{task.id}' cannot depend on itself")


def create_task(
    task_id: str,
    description: str,
    agent: BaseAgent,
    depends_on: List[str] = None,
    async_execution: bool = False,
    expected_output: str = "",
) -> Task:
    """
    Factory function to create a Task.

    Args:
        task_id: Unique identifier for the task
        description: Task description/prompt
        agent: Agent that will execute the task
        depends_on: List of task IDs this depends on
        async_execution: Whether task can run in parallel
        expected_output: Description of expected output

    Returns:
        Configured Task instance
    """
    return Task(
        id=task_id,
        description=description,
        agent=agent,
        depends_on=depends_on or [],
        async_execution=async_execution,
        expected_output=expected_output,
    )
