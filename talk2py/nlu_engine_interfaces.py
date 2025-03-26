"""Natural Language Understanding (NLU) engine interfaces for talk2py.

This module defines abstract interfaces for NLU engine components:
- UtterancesInterface: For handling user utterances and command metadata
- ParameterExtractionInterface: For extracting and validating command parameters
- ResponseGenerationInterface: For generating human-readable responses based on command execution
"""

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel


# pylint: disable=too-few-public-methods
class UtterancesInterface(ABC):
    """Interface that defines utterance related methods"""

    @abstractmethod
    def get_utterance_metadata(self, command_key: str) -> tuple[str, Optional[str]]:
        """return the function signature and optionally the docstring based on the command key"""


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


# pylint: disable=too-few-public-methods
class ResponseGenerationInterface(ABC):
    """Interface that defines response generation methods"""

    @abstractmethod
    def generate_response(
        self,
        command_key: str,
        command_parameters: BaseModel,
        execution_results: dict[str, str],
    ) -> str:
        """generate a human readable response based on command execution results"""


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
