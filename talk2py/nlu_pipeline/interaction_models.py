# New file
from pydantic import BaseModel
from typing import List, Optional, Any, Dict

class BaseInteractionData(BaseModel):
    """Base model for data stored during interaction modes."""
    class Config:
        extra = 'allow' # Allow extra fields if needed, or use 'forbid'

class ClarificationData(BaseInteractionData):
    """Data needed for intent clarification."""
    options: List[str] # List of intent names or descriptions to choose from
    original_query: str
    prompt: str = "Please choose one of the following options:" # Default prompt

class ValidationData(BaseInteractionData):
    """Data needed for parameter validation."""
    parameter_name: str
    error_message: str
    current_value: Optional[Any] = None
    prompt: str = "Please provide a valid value for {parameter_name}:" # Default prompt template

class FeedbackData(BaseInteractionData):
    """Data needed for response feedback."""
    response_text: str
    execution_results: Optional[Dict[str, Any]] = None
    prompt: str = "Was this response helpful? (yes/no/details)" # Default prompt

# Add other interaction data models as needed 