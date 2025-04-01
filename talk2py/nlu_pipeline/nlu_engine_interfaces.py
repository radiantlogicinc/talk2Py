"""Natural Language Understanding (NLU) engine interfaces for talk2py.

This module defines abstract interfaces for NLU engine components:
- IntentDetectionInterface: For classifying and clarifying user intent from message
- ParameterExtractionInterface: For extracting and validating command parameters
- ResponseGenerationInterface: For generating human-readable responses based on command execution
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

import talk2py


# pylint: disable=too-few-public-methods
class IntentDetectionInterface(ABC):
    """Interface that defines intent detection methods"""

    @abstractmethod
    def categorize_user_message(self, user_message: str) -> str:
        """Categorize user message as 'query', 'feedback', or 'abort'.

        Default implementation should return 'query'.
        """
        ...  # pylint: disable=unnecessary-ellipsis # Implementations should override this

    @abstractmethod
    def classify_intent(
        self, user_input: str, excluded_intents: Optional[List[str]] = None
    ) -> Tuple[str, float]:
        """Classify user intent, returning the intent name and confidence score.

        Default implementation should return ('unknown', 0.0).
        """
        ...  # pylint: disable=unnecessary-ellipsis # Implementations should override this

    @abstractmethod
    def clarify_intent(
        self, user_input: str, possible_intents: List[Tuple[str, float]]
    ) -> Optional[str]:
        """Clarify ambiguous intents, returning the selected intent or None if clarification needed.

        Default implementation should return the highest confidence intent or None.
        """
        ...  # pylint: disable=unnecessary-ellipsis # Implementations should override this


# pylint: disable=too-few-public-methods
class ParameterExtractionInterface(ABC):
    """Interface that defines parameter extraction related methods"""

    @abstractmethod
    def get_supplementary_prompt_instructions(self, command_key: str) -> str:
        """Return supplementary prompt instructions for aiding parameter extraction"""

    @abstractmethod
    def validate_parameters(
        self, cmd_parameters: BaseModel
    ) -> tuple[bool, Optional[str]]:
        """validate the command parameters and return true if valid.
        if false, return a string that clearly explains the error(s),
        ideally provide guidance on correcting the errors
        """

    @abstractmethod
    def identify_parameters(self, user_input: str, intent: str) -> Dict[str, Any]:
        """Extract parameters from user input for the given intent.

        Default implementation should return an empty dict.
        """
        ...  # pylint: disable=unnecessary-ellipsis # Implementations should override this


# pylint: disable=too-few-public-methods
class ResponseGenerationInterface(ABC):
    """Interface that defines response generation methods"""

    @abstractmethod
    def execute_code(self, action: talk2py.Action) -> dict[str, str]:
        """Execute the command specified by the action."""

    @abstractmethod
    def get_supplementary_prompt_instructions(self, command_key: str) -> str:
        """Return supplementary prompt instructions for aiding response text generation"""

    @abstractmethod
    def generate_response_text(
        self,
        command: str,
        execution_results: dict[str, str],
    ) -> str:
        """generate a human readable response text based on command execution results"""


# class CommandRouterInterface(ABC):
#     @abstractmethod
#     def route_command(
#         self,
#         workflow_session: 'talk2py.WorkflowSession',
#         command: str,
#     ) -> talk2py.CommandOutput:
#         pass

# class CommandExecutorInterface(ABC):
#     @abstractmethod
#     def invoke_command(
#         self,
#         workflow_session: 'talk2py.WorkflowSession',
#         command_name: str,
#         command: str,
#     ) -> talk2py.CommandOutput:
#         pass

#     @abstractmethod
#     def perform_action(
#         self,
#         session: talk2py.Session,
#         action: talk2py.Action,
#     ) -> talk2py.CommandOutput:
#         pass
