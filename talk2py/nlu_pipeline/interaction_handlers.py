"""Handlers for different NLU pipeline interaction modes (clarification, validation, feedback)."""

# New file
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Type

# Import the specific data models
from .interaction_models import (
    BaseInteractionData,
    ClarificationData,
    FeedbackData,
    ValidationData,
)
from .models import NLUPipelineContext


@dataclass
class InteractionResult:
    """Structured result from an interaction handler."""

    response: str  # Message for the user
    exit_mode: bool = False  # Should the manager exit this interaction mode?
    proceed_immediately: bool = (
        False  # Should the manager re-run core logic after exiting?
    )
    update_context: Optional[Dict[str, Any]] = field(
        default_factory=dict
    )  # NLUPipelineContext fields to update
    error_message: Optional[str] = None  # For reporting input processing errors


class InteractionHandler(ABC):
    """Abstract Base Class for interaction mode handlers."""

    # Optional: Define expected data type for validation/casting
    expected_data_type: Optional[Type[BaseInteractionData]] = None

    def _get_typed_data(
        self, context: NLUPipelineContext
    ) -> Optional[BaseInteractionData]:
        """Safely retrieves and potentially validates interaction data."""
        if not context.interaction_data:
            # Log error: Handler called with no interaction data
            return None
        if self.expected_data_type and not isinstance(
            context.interaction_data, self.expected_data_type
        ):  # pylint: disable=isinstance-second-argument-not-valid-type
            # Log error: Handler called with wrong data type
            return None
        return context.interaction_data

    @abstractmethod
    def get_initial_prompt(self, context: NLUPipelineContext) -> str:
        """Generates the first prompt when entering this mode. Assumes interaction_data is set."""

    @abstractmethod
    def handle_input(
        self, user_message: str, context: NLUPipelineContext
    ) -> InteractionResult:
        """Processes user input while in this mode. Assumes interaction_data is set."""


# --- Concrete Handler Implementations (Placeholders) ---


class ClarificationHandler(InteractionHandler):
    """Handles intent clarification."""

    expected_data_type = ClarificationData

    def get_initial_prompt(self, context: NLUPipelineContext) -> str:
        data = self._get_typed_data(context)
        if not data or not isinstance(data, ClarificationData):
            return "Sorry, there was an error retrieving clarification options."  # Fallback

        options_text = "\n".join(
            f"{i + 1}. {opt}" for i, opt in enumerate(data.options)
        )
        return f"{data.prompt}\n{options_text}"

    def handle_input(
        self, user_message: str, context: NLUPipelineContext
    ) -> InteractionResult:
        data = self._get_typed_data(context)
        if not data or not isinstance(data, ClarificationData):
            return InteractionResult(
                response="Error processing clarification.", exit_mode=True
            )

        # Placeholder Logic: Try to map input (e.g., number) to an option
        try:
            choice_index = int(user_message.strip()) - 1
            if 0 <= choice_index < len(data.options):
                chosen_intent = data.options[choice_index]
                # Success! Update context and exit mode
                return InteractionResult(
                    response=f"Okay, proceeding with intent: {chosen_intent}",
                    exit_mode=True,
                    proceed_immediately=True,  # Indicate pipeline should continue
                    update_context={"current_intent": chosen_intent},
                )
            # else: # Removed else
            # Invalid number
            return InteractionResult(
                response=f"Please enter a number between 1 and {len(data.options)}.\n{self.get_initial_prompt(context)}"
            )
        except ValueError:
            # Input wasn't a number, could add fuzzy matching later
            return InteractionResult(
                response=f"Please enter the number corresponding to your choice.\n{self.get_initial_prompt(context)}"
            )


class ValidationHandler(InteractionHandler):
    """Handles parameter validation."""

    expected_data_type = ValidationData

    def get_initial_prompt(self, context: NLUPipelineContext) -> str:
        data = self._get_typed_data(context)
        if not data or not isinstance(data, ValidationData):
            return "Sorry, there was an error requesting parameter information."  # Fallback

        prompt = data.prompt.format(parameter_name=data.parameter_name)
        return f"{data.error_message}\n{prompt}"

    def handle_input(
        self, user_message: str, context: NLUPipelineContext
    ) -> InteractionResult:
        data = self._get_typed_data(context)
        if not data or not isinstance(data, ValidationData):
            return InteractionResult(
                response="Error processing validation.", exit_mode=True
            )

        # Placeholder Logic: Assume any non-empty input is the validated value
        # In reality, this would call a specific validation function based on the parameter type
        provided_value = user_message.strip()
        if provided_value:
            # Update the specific parameter in the context's parameter dict
            updated_params = context.current_parameters.copy()
            updated_params[data.parameter_name] = (
                provided_value  # Needs proper type conversion later!
            )
            return InteractionResult(
                response=f"Okay, I've updated {data.parameter_name}.",
                exit_mode=True,
                proceed_immediately=True,  # Continue pipeline (e.g., re-check parameters or execute)
                update_context={"current_parameters": updated_params},
            )
        # else: # Removed else
        # Empty input
        return InteractionResult(
            response="Please provide a value."
        )  # Re-prompt implicitly via manager


class FeedbackHandler(InteractionHandler):
    """Handles user feedback on the response."""

    expected_data_type = FeedbackData

    def get_initial_prompt(self, context: NLUPipelineContext) -> str:
        data = self._get_typed_data(context)
        if not data or not isinstance(data, FeedbackData):
            return "Could I get your feedback on the previous response?"  # Fallback

        # Maybe truncate long responses for the prompt
        response_snippet = (
            data.response_text[:200] + "..."
            if len(data.response_text) > 200
            else data.response_text
        )
        return f"Regarding the response:\n---\n{response_snippet}\n---\n{data.prompt}"

    def handle_input(
        self, user_message: str, context: NLUPipelineContext
    ) -> InteractionResult:
        data = self._get_typed_data(context)
        if not data or not isinstance(data, FeedbackData):
            return InteractionResult(
                response="Error processing feedback.", exit_mode=True
            )

        # Placeholder Logic: Just acknowledge feedback and exit mode
        feedback = user_message.strip().lower()
        # Here you would log the feedback, potentially adjust future responses, etc.
        print(f"Received feedback: {feedback}")  # Replace with logging

        response_message = "Thanks for the feedback!"
        if feedback in ["no", "incorrect", "wrong"]:
            # Could trigger a re-generation attempt or ask for more details
            response_message = "Thanks for letting me know. Can you provide more details on what was wrong?"
            # Decide if we should exit mode or ask clarifying question here. For now, exit.

        return InteractionResult(
            response=response_message,
            exit_mode=True,
            proceed_immediately=False,  # Usually don't proceed automatically after feedback
        )


# Add other handlers as needed
