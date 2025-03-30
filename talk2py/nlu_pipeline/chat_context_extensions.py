"""Extension functions for ChatContext to support NLU pipeline."""

from typing import Optional, Dict, Any

from talk2py import CHAT_CONTEXT
from talk2py.nlu_pipeline.models import NLUPipelineContext, NLUPipelineState
from talk2py.utils.logging import logger

def get_nlu_context() -> NLUPipelineContext:
    """Get the current NLU pipeline context from ChatContext app_context."""
    context_data = CHAT_CONTEXT.app_context.get("nlu_pipeline")
    if not context_data:
        logger.debug("NLU context not found in app_context, initializing.")
        context = NLUPipelineContext()
        CHAT_CONTEXT.app_context["nlu_pipeline"] = context.model_dump()
        return context
    
    # Ensure loaded context is validated against the model
    try:
        # Convert state string back to Enum if necessary
        if isinstance(context_data.get("current_state"), str):
             try:
                  context_data["current_state"] = NLUPipelineState(context_data["current_state"])
             except ValueError:
                  logger.warning(f"Invalid state value '{context_data['current_state']}' found in context, resetting state.")
                  context_data["current_state"] = NLUPipelineState.RESPONSE_TEXT_GENERATION
                  
        return NLUPipelineContext.model_validate(context_data)
    except Exception as e:
        logger.warning(f"Failed to validate NLU context, resetting: {e}")
        context = NLUPipelineContext()
        CHAT_CONTEXT.app_context["nlu_pipeline"] = context.model_dump()
        return context

def set_nlu_context(context: NLUPipelineContext) -> None:
    """Set the NLU pipeline context in ChatContext app_context."""
    # Store enum state as string value for better serialization
    context_dump = context.model_dump()
    context_dump["current_state"] = context.current_state.value
    CHAT_CONTEXT.app_context["nlu_pipeline"] = context_dump

def reset_nlu_pipeline() -> None:
    """Reset the NLU pipeline to its initial state in ChatContext app_context."""
    classroom_mode = get_nlu_context().classroom_mode # Preserve classroom mode
    context = NLUPipelineContext(classroom_mode=classroom_mode)
    set_nlu_context(context)
    logger.info("NLU Pipeline reset to initial state (via extension function).")
    
def set_nlu_pipeline_state(state: NLUPipelineState) -> None:
    """Set the NLU pipeline state in ChatContext app_context."""
    context = get_nlu_context()
    context.current_state = state
    set_nlu_context(context)

def get_nlu_metrics() -> Dict[str, Any]:
    """Get NLU pipeline metrics from ChatContext app_context."""
    return CHAT_CONTEXT.app_context.get("nlu_pipeline_metrics", {})

def set_nlu_metrics(metrics: Dict[str, Any]) -> None:
    """Set NLU pipeline metrics in ChatContext app_context."""
    CHAT_CONTEXT.app_context["nlu_pipeline_metrics"] = metrics 