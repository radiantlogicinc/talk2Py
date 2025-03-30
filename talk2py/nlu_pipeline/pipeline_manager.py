import os
import json
import importlib
from typing import Dict, Any, Optional, Tuple, List, Type
from datetime import datetime

from talk2py import CHAT_CONTEXT
from talk2py.types import ConversationArtifacts, NLUArtifacts
from talk2py.nlu_pipeline.models import NLUPipelineState, NLUPipelineContext
from talk2py.nlu_pipeline.nlu_engine_interfaces import (
    ParameterExtractionInterface,
    ResponseGenerationInterface
)
from talk2py.nlu_pipeline.default_param_extraction import DefaultParameterExtraction
from talk2py.nlu_pipeline.default_response_generation import DefaultResponseGeneration
from talk2py.utils.logging import logger
from talk2py.code_parsing_execution.command_registry import CommandRegistry

class NLUPipelineManager:
    """Manages NLU pipeline execution and state transitions."""

    def __init__(self):
        """Initialize the NLU pipeline manager."""
        # Implementations are loaded dynamically based on context
        self._param_extraction_impl: Optional[ParameterExtractionInterface] = None
        self._response_generation_impl: Optional[ResponseGenerationInterface] = None
        self._current_command_key_for_impl: Optional[str] = None

    def _load_implementation(self, command_key: str, interface_type: str) -> Any:
        """Loads the appropriate implementation (default or override)."""
        # Check if app folder path is set
        if not CHAT_CONTEXT.current_app_folderpath:
            logger.warning("Cannot load NLU implementation: current_app_folderpath not set.")
            return (
                DefaultParameterExtraction() if interface_type == "param_extraction"
                else DefaultResponseGeneration()
            )
            
        # Construct path to NLU metadata file
        nlu_metadata_path = os.path.join(
            CHAT_CONTEXT.current_app_folderpath,
            "___command_info",
            "nlu_engine_metadata.json"
        )

        nlu_metadata = {}
        if os.path.exists(nlu_metadata_path):
            try:
                with open(nlu_metadata_path, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    nlu_metadata = loaded_data.get("map_commandkey_2_nluengine_metadata", {})
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Failed to load or parse NLU metadata file {nlu_metadata_path}: {e}")
                nlu_metadata = {}

        command_metadata = nlu_metadata.get(command_key, {})

        # Determine the correct class name and module path
        if interface_type == "param_extraction":
            metadata_key = "param_extraction_class"
            default_class = DefaultParameterExtraction
        elif interface_type == "response_generation":
            metadata_key = "response_generation_class"
            default_class = DefaultResponseGeneration
        else:
            raise ValueError(f"Unknown interface type: {interface_type}")

        impl_path = command_metadata.get(metadata_key)

        if impl_path:
            try:
                module_name, class_name = impl_path.rsplit('.', 1)
                # Ensure the module path is relative to the workspace root if needed
                # This might require adjustment based on how overrides are structured
                if module_name.startswith("nlu_interface_overrides."):
                    # Assumes overrides are directly under the app folder
                    pass # Keep module_name as is
                
                module = importlib.import_module(module_name)
                impl_class = getattr(module, class_name)
                logger.debug(f"Loaded NLU override implementation for {command_key}: {impl_path}")
                return impl_class()
            except (ImportError, AttributeError, ValueError) as e:
                logger.error(f"Failed to load NLU override {impl_path} for {command_key}: {e}. Using default.")
                return default_class()
        else:
            logger.debug(f"Using default NLU {interface_type} implementation for {command_key}")
            return default_class()

    def _get_implementation(self, interface_type: str, command_key: Optional[str]) -> Any:
        """Gets or loads the correct implementation based on command_key."""
        current_impl = getattr(self, f"_{interface_type}_impl", None)
        default_class = (
            DefaultParameterExtraction if interface_type == "param_extraction"
            else DefaultResponseGeneration
        )

        # If we have a command key and it's different from the last one, or no impl loaded
        if command_key and (self._current_command_key_for_impl != command_key or current_impl is None):
            logger.debug(f"Loading NLU {interface_type} implementation for command: {command_key}")
            new_impl = self._load_implementation(command_key, interface_type)
            setattr(self, f"_{interface_type}_impl", new_impl)
            self._current_command_key_for_impl = command_key # Update tracked command key
            return new_impl
        # If no command key, ensure a default is loaded if none exists
        elif not command_key and current_impl is None:
             logger.debug(f"No command key, ensuring default NLU {interface_type} implementation.")
             default_impl = default_class()
             setattr(self, f"_{interface_type}_impl", default_impl)
             self._current_command_key_for_impl = None # Reset tracked command key
             return default_impl
        # Otherwise, return the cached implementation
        elif current_impl:
            return current_impl
        # Final fallback (shouldn't normally be reached) 
        else:
             logger.warning(f"Could not determine NLU {interface_type} implementation, using default.")
             return default_class()

    def _get_param_extraction(self, command_key: Optional[str]) -> ParameterExtractionInterface:
        """Get the parameter extraction implementation."""
        return self._get_implementation("param_extraction", command_key)

    def _get_response_generation(self, command_key: Optional[str]) -> ResponseGenerationInterface:
        """Get the response generation implementation."""
        return self._get_implementation("response_generation", command_key)

    def _has_method(self, obj: Any, method_name: str) -> bool:
        """Check if an object has a specific method."""
        return hasattr(obj, method_name) and callable(getattr(obj, method_name))

    def process_message(self, user_message: str) -> str:
        """Process a user message through the NLU pipeline.
        
        This method now processes one state transition per call based on the 
        current context state and user message.
        """
        context = self._get_nlu_context()
        start_state = context.current_state
        response = "An error occurred processing your request." # Default error response
        transition_occurred = False

        logger.info(f"NLU Pipeline START: Processing '{user_message}' in state {start_state.value}")

        try:
            # --- Get current implementations --- 
            param_impl = self._get_param_extraction(context.current_intent)
            resp_impl = self._get_response_generation(context.current_intent)

            # --- Universal Checks (Abort/Feedback) --- 
            # Always categorize first to catch universal commands like abort
            category = "query" # Default
            if self._has_method(resp_impl, "categorize_user_message"):
                category = resp_impl.categorize_user_message(user_message)
                logger.debug(f"Message categorized as: {category}")
            else:
                logger.warning("Response generation implementation missing 'categorize_user_message'. Cannot detect abort/feedback.")
            
            # Handle Abort universally
            if category == "abort":
                response = "Okay, cancelling the current operation."
                self._reset_pipeline(context)
                self._save_artifacts_and_log_transition(context, start_state, user_message, response)
                return response

            # --- State-Specific Logic --- 
            # State: RESPONSE_TEXT_GENERATION (Handling Query or Feedback)
            if start_state == NLUPipelineState.RESPONSE_TEXT_GENERATION:
                # --- Reset context from previous turn BEFORE processing new input ---                
                # Check if this is the start of a new interaction (not refinement feedback)
                # We need to be careful not to clear intent if we are handling intent feedback
                if category != "feedback": # If it's a new query or abort
                    logger.debug("Resetting NLU context fields for new query in RESPONSE_TEXT_GENERATION state.")
                    context.current_intent = None
                    context.current_parameters = {}
                    context.parameter_validation_errors = []
                    context.confidence_score = 0.0
                    context.excluded_intents = [] 
                    # Keep last_... fields for potential feedback on the *previous* response
                # --- End context reset --- 
                    
                # Abort is handled above
                if category == "query":
                    self._transition_state(context, NLUPipelineState.INTENT_CLASSIFICATION)
                    response = self._handle_intent_classification(context, user_message, resp_impl)
                elif category == "feedback":
                    response = self._handle_response_generation_feedback(context, user_message, resp_impl)
                else: # Handle unknown category if needed (though abort handled)
                     logger.warning(f"Unknown or unhandled message category in RESPONSE_TEXT_GENERATION: {category}")
                     response = "I'm not sure how to handle that type of message."
                     self._transition_state(context, NLUPipelineState.RESPONSE_TEXT_GENERATION)

            # State: INTENT_CLASSIFICATION
            # If we start in this state, it means the previous turn ended here (e.g., after reset feedback)
            # We should proceed to classify the current user_message.
            elif start_state == NLUPipelineState.INTENT_CLASSIFICATION:
                logger.debug(f"Processing message received in state: {start_state.value}")
                response = self._handle_intent_classification(context, user_message, resp_impl)

            # State: INTENT_CLARIFICATION (Waiting for user clarification)
            elif start_state == NLUPipelineState.INTENT_CLARIFICATION:
                 # NOTE: If the user says 'abort' here, it was already caught above
                response = self._handle_intent_clarification(context, user_message, resp_impl)

            # State: PARAMETER_IDENTIFICATION (Entered after intent confirmed)
            elif start_state == NLUPipelineState.PARAMETER_IDENTIFICATION:
                 # NOTE: Abort already caught
                 # This state handler now performs the *initial* identification and validation attempt
                 response = self._handle_initial_param_id_and_validate(context, user_message, param_impl)

            # State: PARAMETER_VALIDATION (Waiting for more params)
            elif start_state == NLUPipelineState.PARAMETER_VALIDATION:
                # NOTE: Abort already caught
                # This state handler is for subsequent attempts after initial validation failed
                response = self._handle_subsequent_param_validation(context, user_message, param_impl)

            # State: CODE_EXECUTION (Entered after params are valid)
            elif start_state == NLUPipelineState.CODE_EXECUTION:
                # NOTE: Abort already caught (though unlikely user input occurs here)
                response = self._handle_code_execution(context, user_message, resp_impl)
            
            else:
                logger.error(f"Reached process_message with unknown state: {start_state.value}")
                self._reset_pipeline(context)
                response = "An internal error occurred. Resetting state."

        except Exception as e:
            logger.exception(f"Unhandled error processing NLU state {start_state.value}: {e}")
            response = "I encountered an unexpected error. Please try again."
            self._reset_pipeline(context)

        # --- Save Context and Artifacts --- 
        self._save_artifacts_and_log_transition(context, start_state, user_message, response)

        logger.info(f"NLU Pipeline END: State={context.current_state.value}, Response='{response[:50]}...'")
        return response
        
    # --- Helper methods for each state's logic --- 
    
    def _handle_response_generation_feedback(self, context: NLUPipelineContext, user_message: str, resp_impl: ResponseGenerationInterface) -> str:
        """Handles feedback received in the RESPONSE_TEXT_GENERATION state."""
        is_intent_feedback = "meant" in user_message.lower() or "wrong intent" in user_message.lower()
        
        if is_intent_feedback and context.last_user_message_for_response:
            logger.info("Feedback identified as intent misinterpretation.")
            if context.current_intent: # Use the intent that generated the last response
                    context.excluded_intents.append(context.current_intent)
                    logger.debug(f"Excluding intent: {context.current_intent}")
            # Reset fields and transition to re-classify the *new* message
            context.current_intent = None
            context.current_parameters = {}
            context.parameter_validation_errors = []
            context.confidence_score = 0.0
            context.last_user_message_for_response = None
            context.last_execution_results_for_response = None
            self._transition_state(context, NLUPipelineState.INTENT_CLASSIFICATION)
            # Re-run classification immediately with the feedback message
            return self._handle_intent_classification(context, user_message, resp_impl)
        elif context.classroom_mode:
            logger.info("Feedback identified as response refinement in classroom mode.")
            if self._has_method(resp_impl, "generate_response") and context.last_user_message_for_response:
                refined_command_desc = f"Original command: {context.last_user_message_for_response}\nFeedback: {user_message}"
                try:
                    response = resp_impl.generate_response(
                        refined_command_desc, 
                        context.last_execution_results_for_response or {}
                    )
                    logger.info(f"Generated refined response: {response}")
                    # Update last response context
                    context.last_user_message_for_response = refined_command_desc
                    # Stay in RESPONSE_TEXT_GENERATION
                    self._transition_state(context, NLUPipelineState.RESPONSE_TEXT_GENERATION)
                    return response
                except Exception as gen_e:
                    logger.exception(f"Error generating refined response: {gen_e}")
                    self._transition_state(context, NLUPipelineState.RESPONSE_TEXT_GENERATION)
                    return "I understand the feedback, but couldn't refine the response."
            else:
                self._transition_state(context, NLUPipelineState.RESPONSE_TEXT_GENERATION)
                return "Thank you for the feedback. (Refinement not available)"
        else: # Non-classroom mode, non-intent-specific feedback
            logger.info("Generic feedback received, resetting pipeline.")
            self._reset_pipeline(context)
            # Transition to INTENT_CLASSIFICATION to prompt user again
            self._transition_state(context, NLUPipelineState.INTENT_CLASSIFICATION)
            return "My apologies. Could you please rephrase your request?" # Default feedback response
            
    def _command_requires_parameters(self, command_key: str) -> bool:
        """Check command registry metadata if a command requires parameters."""
        if not command_key:
            return False
        try:
            registry = CHAT_CONTEXT.get_registry(CHAT_CONTEXT.current_app_folderpath)
            metadata = registry.command_metadata.get("map_commandkey_2_metadata", {}).get(command_key, {})
            parameters = metadata.get("parameters", [])
            # Consider parameters excluding 'self' or 'cls' if they exist
            required_params = [p for p in parameters if p.get("name") not in ["self", "cls"]]
            return len(required_params) > 0
        except Exception as e:
            logger.error(f"Failed to check parameter requirement for {command_key}: {e}")
            return True # Assume parameters might be needed if check fails
            
    def _handle_intent_classification(self, context: NLUPipelineContext, user_message: str, resp_impl: ResponseGenerationInterface) -> str:
        """Handles logic for the INTENT_CLASSIFICATION state."""
        logger.debug("Handling INTENT_CLASSIFICATION")
        # Use the currently loaded response_impl for classification
        if self._has_method(resp_impl, "classify_intent"):
                # Ensure excluded_intents is passed correctly (as positional)
                intent, confidence = resp_impl.classify_intent(
                    user_message, context.excluded_intents
                )
        else:
                logger.warning("Response generation implementation missing 'classify_intent'. Defaulting to unknown.")
                intent, confidence = "unknown", 0.0

        context.current_intent = intent
        context.confidence_score = confidence
        logger.info(f"Intent classified: {intent} (Confidence: {confidence:.2f})")

        threshold_high = 0.8 
        threshold_medium = 0.5

        if intent == "unknown" or confidence < threshold_medium:
            self._transition_state(context, NLUPipelineState.RESPONSE_TEXT_GENERATION)
            context.current_intent = None # Clear uncertain intent
            context.excluded_intents = [] # Reset exclusions
            return "Sorry, I couldn't understand that. Could you please rephrase?"
        elif confidence < threshold_high:
            # Transition to clarification and wait for next message
            self._transition_state(context, NLUPipelineState.INTENT_CLARIFICATION)
            return f"I think you mean '{intent}', is that correct? Or maybe something else?"
        else: # High confidence
            context.parameter_validation_errors = []
            context.excluded_intents = [] # Clear exclusions
            # Load specific implementations *now* for the confirmed intent
            param_impl = self._get_param_extraction(context.current_intent)
            resp_impl = self._get_response_generation(context.current_intent)

            # Check if parameters are needed
            if self._command_requires_parameters(context.current_intent):
                self._transition_state(context, NLUPipelineState.PARAMETER_IDENTIFICATION)
                # Attempt identification immediately
                return self._handle_initial_param_id_and_validate(context, user_message, param_impl)
            else:
                # No parameters needed, attempt execution or go straight to response
                logger.info(f"Intent {context.current_intent} requires no parameters. Skipping identification/validation.")
                # TODO: Determine if code execution is needed
                needs_code_execution = False # Placeholder
                if needs_code_execution:
                    self._transition_state(context, NLUPipelineState.CODE_EXECUTION)
                    return self._handle_code_execution(context, user_message, resp_impl)
                else:
                    self._transition_state(context, NLUPipelineState.RESPONSE_TEXT_GENERATION)
                    return self._handle_final_response_generation(context, user_message, resp_impl)
            
    def _handle_intent_clarification(self, context: NLUPipelineContext, user_message: str, resp_impl: ResponseGenerationInterface) -> str:
        """Handles logic for the INTENT_CLARIFICATION state."""
        logger.debug("Handling INTENT_CLARIFICATION")
        potential_intents = [(context.current_intent, context.confidence_score)] if context.current_intent else []
        
        if self._has_method(resp_impl, "clarify_intent"):
            clarified_intent = resp_impl.clarify_intent(user_message, potential_intents)
        else:
            logger.warning("Response generation implementation missing 'clarify_intent'. Assuming user confirmed.")
            clarified_intent = context.current_intent if "no" not in user_message.lower() else None
            
        if clarified_intent:
            logger.info(f"Intent clarified to: {clarified_intent}")
            context.current_intent = clarified_intent
            context.excluded_intents = [] 
            context.parameter_validation_errors = []
            # Load specific implementations
            param_impl = self._get_param_extraction(context.current_intent)
            resp_impl = self._get_response_generation(context.current_intent)
            
            # Check if parameters are needed
            if self._command_requires_parameters(context.current_intent):
                self._transition_state(context, NLUPipelineState.PARAMETER_IDENTIFICATION)
                # Attempt identification immediately
                return self._handle_initial_param_id_and_validate(context, user_message, param_impl)
            else:
                # No parameters needed, attempt execution or go straight to response
                logger.info(f"Intent {context.current_intent} requires no parameters. Skipping identification/validation.")
                # TODO: Determine if code execution is needed
                needs_code_execution = False # Placeholder
                if needs_code_execution:
                    self._transition_state(context, NLUPipelineState.CODE_EXECUTION)
                    return self._handle_code_execution(context, user_message, resp_impl)
                else:
                    self._transition_state(context, NLUPipelineState.RESPONSE_TEXT_GENERATION)
                    return self._handle_final_response_generation(context, user_message, resp_impl)
        else:
            self._reset_pipeline(context)
            return "Okay, let's try again. What would you like to do?"

    def _handle_initial_param_id_and_validate(self, context: NLUPipelineContext, user_message: str, param_impl: ParameterExtractionInterface) -> str:
        """Handles the first attempt at parameter identification and validation."""
        logger.debug("Handling initial PARAMETER_IDENTIFICATION and VALIDATION attempt")
        if not context.current_intent:
             logger.error("Attempted parameter handling without a confirmed intent.")
             self._reset_pipeline(context)
             return "Error: Cannot process parameters without a clear intent."

        # 1. Identify Parameters
        if self._has_method(param_impl, "identify_parameters"):
                identified_params = param_impl.identify_parameters(user_message, context.current_intent)
                context.current_parameters.update(identified_params) # Merge params
                logger.info(f"Parameters identified: {context.current_parameters}")
        else:
                logger.warning("Parameter extraction implementation missing 'identify_parameters'. Skipping identification.")
        
        # 2. Validate Parameters
        validation_passed = False
        validation_message = None
        if self._has_method(param_impl, "validate_parameters"):
                # Pass only intent and parameters
                validation_passed, validation_message = param_impl.validate_parameters(
                    context.current_intent, context.current_parameters
                )
                # Store error message as a list
                context.parameter_validation_errors = [] if validation_passed else [validation_message] if validation_message else ["Validation failed"]
                logger.info(f"Parameter validation result: Passed={validation_passed}, Message={validation_message}")
        else:
                logger.warning("Parameter extraction implementation missing 'validate_parameters'. Assuming parameters are valid.")
                validation_passed = True # Assume valid if no validator

        # 3. Transition based on validation
        if validation_passed:
            logger.info("Parameter validation passed. Moving to execution/response.")
            # TODO: Determine if code execution is needed
            needs_code_execution = False # Placeholder
            if needs_code_execution:
                self._transition_state(context, NLUPipelineState.CODE_EXECUTION)
                return self._handle_code_execution(context, user_message, self._get_response_generation(context.current_intent))
            else:
                self._transition_state(context, NLUPipelineState.RESPONSE_TEXT_GENERATION)
                return self._handle_final_response_generation(context, user_message, self._get_response_generation(context.current_intent))
        else:
            logger.info("Parameter validation failed. Moving to PARAMETER_VALIDATION state.")
            self._transition_state(context, NLUPipelineState.PARAMETER_VALIDATION)
            return validation_message or "Please provide the required information." # Return error message to user

    def _handle_subsequent_param_validation(self, context: NLUPipelineContext, user_message: str, param_impl: ParameterExtractionInterface) -> str:
        """Handles subsequent parameter validation attempts when state is PARAMETER_VALIDATION."""
        logger.debug("Handling subsequent PARAMETER_VALIDATION attempt")
        if not context.current_intent:
             logger.error("Attempted parameter handling without a confirmed intent.")
             self._reset_pipeline(context)
             return "Error: Cannot process parameters without a clear intent."

        # Re-attempt identification using the new user message, merging with existing params
        if self._has_method(param_impl, "identify_parameters"):
                # Pass existing params so the impl can potentially refine or just add new ones
                identified_params = param_impl.identify_parameters(
                    user_message, context.current_intent
                )
                context.current_parameters.update(identified_params) # Merge new params
                logger.info(f"Parameters updated after user input: {context.current_parameters}")
        else:
             logger.warning("Parameter extraction implementation missing 'identify_parameters'. Cannot refine parameters.")

        # Re-validate with potentially updated parameters
        validation_passed = False
        validation_message = None
        if self._has_method(param_impl, "validate_parameters"):
                # Pass only intent and parameters
                validation_passed, validation_message = param_impl.validate_parameters(
                    context.current_intent, context.current_parameters
                )
                # Store error message as a list
                context.parameter_validation_errors = [] if validation_passed else [validation_message] if validation_message else ["Validation failed"]
                logger.info(f"Parameter validation result: Passed={validation_passed}, Message={validation_message}")
        else:
                logger.warning("Parameter extraction implementation missing 'validate_parameters'. Assuming parameters are valid.")
                validation_passed = True

        # Transition based on re-validation
        if validation_passed:
            logger.info("Parameter validation passed. Moving to execution/response.")
            # TODO: Determine if code execution is needed
            needs_code_execution = False # Placeholder
            if needs_code_execution:
                self._transition_state(context, NLUPipelineState.CODE_EXECUTION)
                return self._handle_code_execution(context, user_message, self._get_response_generation(context.current_intent))
            else:
                self._transition_state(context, NLUPipelineState.RESPONSE_TEXT_GENERATION)
                return self._handle_final_response_generation(context, user_message, self._get_response_generation(context.current_intent))
        else:
            logger.info("Parameter validation failed again. Staying in PARAMETER_VALIDATION state.")
            self._transition_state(context, NLUPipelineState.PARAMETER_VALIDATION) # Stay in this state
            return validation_message or "I still need more information. Could you please provide the details?" # Return error message

    def _handle_code_execution(self, context: NLUPipelineContext, user_message: str, resp_impl: ResponseGenerationInterface) -> str:
        """Handles logic for the CODE_EXECUTION state."""
        logger.debug("Handling CODE_EXECUTION")
        # TODO: Implement actual command execution
        execution_results = {"status": "success", "result": "Placeholder execution result"}
        context.current_parameters["execution_results"] = execution_results
        logger.info(f"Code execution completed. Results: {execution_results}")
        self._transition_state(context, NLUPipelineState.RESPONSE_TEXT_GENERATION)
        # Immediately generate final response
        return self._handle_final_response_generation(context, user_message, resp_impl)
        
    def _handle_final_response_generation(self, context: NLUPipelineContext, user_message: str, resp_impl: ResponseGenerationInterface) -> str:
        """Handles the final response generation after execution or validation."""
        logger.debug("Handling final RESPONSE_TEXT_GENERATION")
        response = "Task completed successfully." # Default success response
        
        if self._has_method(resp_impl, "generate_response"):
            cmd_desc = context.current_intent or user_message # Use intent if known
            exec_res = context.current_parameters.get("execution_results", {})                    
            # Store context *before* potentially clearing intent below
            context.last_user_message_for_response = cmd_desc
            context.last_execution_results_for_response = exec_res
            try:
                response = resp_impl.generate_response(cmd_desc, exec_res)
                logger.info(f"Generated final response: {response}")
            except Exception as gen_e:
                    logger.exception(f"Error during final response generation: {gen_e}")
                    response = "I completed the task, but had trouble generating a summary."
        else:
            logger.warning("Response generation implementation missing 'generate_response'. Using default.")
            
        # DO NOT Reset context fields here; moved to start of RESPONSE_TEXT_GENERATION state handling
        # context.current_intent = None
        # context.current_parameters = {}
        # context.parameter_validation_errors = {}
        # context.confidence_score = 0.0
        # context.excluded_intents = [] # Clear exclusions after success
        
        # Transition to ensure state remains RESPONSE_TEXT_GENERATION
        self._transition_state(context, NLUPipelineState.RESPONSE_TEXT_GENERATION)
        return response

    def _get_nlu_context(self) -> NLUPipelineContext:
        """Get NLU context from ChatContext app_context."""
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

    def _save_nlu_context(self, context: NLUPipelineContext) -> None:
        """Save NLU context to ChatContext app_context."""
        # Store enum state as string value for better serialization
        context_dump = context.model_dump()
        context_dump["current_state"] = context.current_state.value
        CHAT_CONTEXT.app_context["nlu_pipeline"] = context_dump

    def _transition_state(self, context: NLUPipelineContext, new_state: NLUPipelineState) -> None:
        """Helper to transition state and log it."""
        # Note: Logging is now done within process_message after state processing
        context.current_state = new_state
        # Do not save context here; saved once at the end of process_message
        
    def _reset_pipeline(self, context: NLUPipelineContext) -> None:
        """Resets the pipeline state, keeping classroom mode."""
        classroom_mode = context.classroom_mode # Preserve classroom mode
        new_context_dict = NLUPipelineContext(classroom_mode=classroom_mode).model_dump()
        # Update the passed context object directly for immediate effect within process_message
        context.current_state = NLUPipelineState(new_context_dict["current_state"])
        context.excluded_intents = new_context_dict["excluded_intents"]
        context.current_intent = new_context_dict["current_intent"]
        context.current_parameters = new_context_dict["current_parameters"]
        context.parameter_validation_errors = new_context_dict["parameter_validation_errors"] # Should be []
        context.confidence_score = new_context_dict["confidence_score"]
        # Also reset the last response context
        context.last_user_message_for_response = None 
        context.last_execution_results_for_response = None
        # Saving happens at the end of process_message
        logger.info("NLU Pipeline reset to initial state.") 

    def _save_artifacts_and_log_transition(self, context: NLUPipelineContext, start_state: NLUPipelineState, user_message: str, response: str) -> None:
        """Save artifacts and log state transition."""
        # Save NLU context
        self._save_nlu_context(context)

        # Create NLUArtifacts object
        nlu_artifacts = NLUArtifacts(
            state=start_state.value if start_state else None,
            intent=context.current_intent,
            parameters=context.current_parameters,
            excluded_intents=context.excluded_intents,
            confidence_score=context.confidence_score
        )
        
        # Create ConversationArtifacts with nested NLU data
        artifacts = ConversationArtifacts(nlu=nlu_artifacts)

        CHAT_CONTEXT.append_to_conversation_history(
            user_message, response, artifacts
        )

        end_state = context.current_state
        if start_state != end_state:
             logger.info(
                f"NLU Pipeline: State transition {start_state.value} → {end_state.value}",
                extra={
                    "from_state": start_state.value,
                    "to_state": end_state.value,
                    "intent": context.current_intent
                }
            ) 