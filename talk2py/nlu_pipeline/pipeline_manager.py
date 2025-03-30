import os
import json
import importlib
from typing import Dict, Any, Optional, Tuple, List, Type
from datetime import datetime
import logging # Assuming logging is used

from talk2py import CHAT_CONTEXT
from talk2py.types import ConversationArtifacts, NLUArtifacts
from talk2py.nlu_pipeline.models import NLUPipelineState, NLUPipelineContext, InteractionState
from talk2py.nlu_pipeline.interaction_models import ClarificationData, ValidationData, FeedbackData # Import specific data types
from talk2py.nlu_pipeline.interaction_handlers import (
    InteractionHandler, InteractionResult,
    ClarificationHandler, ValidationHandler, FeedbackHandler # Import concrete handlers
)
from talk2py.nlu_pipeline.utils import check_for_meta_commands, MetaCommandType
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

        # Instantiate and register interaction handlers
        self._interaction_handlers: Dict[InteractionState, InteractionHandler] = {
            InteractionState.CLARIFYING_INTENT: ClarificationHandler(),
            InteractionState.VALIDATING_PARAMETER: ValidationHandler(),
            InteractionState.AWAITING_FEEDBACK: FeedbackHandler(),
            # Add mappings for other handlers
        }

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

    def _reset_interaction(self, context: NLUPipelineContext) -> None:
        """Resets the interaction mode and data in the context."""
        logger.debug("Resetting interaction mode.")
        context.interaction_mode = None
        context.interaction_data = None

    def _get_nlu_context(self) -> NLUPipelineContext:
        """Get NLU context from ChatContext app_context."""
        context_data = CHAT_CONTEXT.app_context.get("nlu_context", {})
        try:
            # Use parse_obj for potentially incomplete data during migration
            return NLUPipelineContext.parse_obj(context_data)
        except Exception as e:
            logger.warning(f"Failed to parse stored NLU context: {e}. Resetting context.")
            return NLUPipelineContext() # Return default context on error

    def _save_nlu_context(self, context: NLUPipelineContext) -> None:
        """Save NLU context to ChatContext app_context."""
        # Store enum state as string value for better serialization
        context_dump = context.model_dump()
        context_dump["current_state"] = context.current_state.value
        try:
             # Convert Pydantic model to dict, handling potential custom types if needed
             # Using exclude_none=True might be useful to keep saved context clean
            CHAT_CONTEXT.app_context["nlu_context"] = context.dict(exclude_none=True)
        except Exception as e:
            logger.error(f"Failed to serialize NLU context for saving: {e}")

    def _transition_state(self, context: NLUPipelineContext, new_state: NLUPipelineState) -> None:
        """Helper to log and perform state transitions."""
        if context.current_state != new_state:
            logger.debug(f"Transitioning NLU state: {context.current_state.value} -> {new_state.value}")
            context.current_state = new_state
        else:
            logger.debug(f"Staying in NLU state: {context.current_state.value}")

    def _reset_pipeline(self, context: NLUPipelineContext) -> None:
        """Resets the pipeline state and interaction mode."""
        logger.warning("Resetting NLU pipeline state.")
        self._reset_interaction(context)
        context.current_state = NLUPipelineState.INTENT_CLASSIFICATION
        context.current_intent = None
        context.current_parameters = {}
        context.parameter_validation_errors = []
        context.confidence_score = 0.0
        context.excluded_intents = []
        context.last_user_message_for_response = None
        context.last_execution_results_for_response = None
        # Save the reset context immediately?
        self._save_nlu_context(context)

    async def process_message(self, user_message: str) -> str:
        """Process a user message through the NLU pipeline using modal interaction."""
        context = self._get_nlu_context()
        start_state = context.current_state
        response = "Sorry, I encountered an issue processing your request." # Default error response

        logger.info(f"NLU Pipeline START: Processing '{user_message[:50]}...' in state {start_state.value} (Interaction: {context.interaction_mode})")

        try:
            # 1. Meta-Command Check
            meta_command = check_for_meta_commands(user_message)
            if meta_command != MetaCommandType.NONE:
                logger.info(f"Meta command detected: {meta_command.name}")
                if meta_command == MetaCommandType.CANCEL:
                    # Reset full pipeline state for CANCEL, similar to RESET
                    self._reset_pipeline(context) # Call reset_pipeline, not just reset_interaction
                    response = "Okay, cancelling the current operation."
                elif meta_command == MetaCommandType.HELP:
                    # Provide help without changing state significantly
                    response = "Help: [Provide relevant help text based on state or mode if possible]"
                    # Don't reset interaction for help
                elif meta_command == MetaCommandType.RESET:
                    self._reset_pipeline(context) # Resets interaction too
                    response = "Okay, let's start over. What would you like to do?"

                # Save context changes after handling meta command
                self._save_nlu_context(context)
                return response


            # 2. Active Interaction Mode Handling
            if context.interaction_mode:
                handler = self._interaction_handlers.get(context.interaction_mode)
                if handler:
                    logger.debug(f"Handling input with: {type(handler).__name__}")
                    # Assuming handlers are synchronous for now
                    result: InteractionResult = handler.handle_input(user_message, context)

                    # Process result
                    if result.update_context:
                        logger.debug(f"Updating context with: {result.update_context}")
                        for key, value in result.update_context.items():
                            # Only update if the key exists in the model to avoid errors
                            if hasattr(context, key):
                                setattr(context, key, value)
                            else:
                                logger.warning(f"Attempted to update non-existent context field: {key}")

                    if result.exit_mode:
                        logger.debug(f"Exiting interaction mode: {context.interaction_mode.name}")
                        mode_exited = context.interaction_mode # Store before resetting
                        self._reset_interaction(context)
                        # If requested, proceed immediately by re-running logic (carefully)
                        if result.proceed_immediately:
                            logger.debug("Proceeding immediately after exiting mode.")
                            # Re-process based on the NEW context state.
                            # This recursively calls process_message with the *same* user message
                            # but the context is now updated (new state, intent, params etc.)
                            # Need safeguards against infinite loops!
                            # Option 1: Recurse (use with caution, max depth?)
                            # response = self.process_message(user_message) # DANGEROUS - Infinite loop risk if state doesn't advance

                            # Option 2: Transition to next logical state here & run that handler directly
                            # Determine next step based on what mode just finished
                            if mode_exited == InteractionState.CLARIFYING_INTENT:
                                # Intent clarified, move to param identification
                                self._transition_state(context, NLUPipelineState.PARAMETER_IDENTIFICATION)
                                response = await self._handle_state_logic(user_message, context) # Refactored logic
                            elif mode_exited == InteractionState.VALIDATING_PARAMETER:
                                # Params provided, re-validate or move to execution
                                self._transition_state(context, NLUPipelineState.PARAMETER_IDENTIFICATION) # Re-run param check
                                response = await self._handle_state_logic(user_message, context) # Refactored logic
                            else:
                                response = result.response # Fallback if no immediate action defined
                        else:
                            response = result.response
                    else:
                        # Still in interaction mode, return the handler's (re)prompt or error
                        response = result.response

                else:
                    logger.error(f"No handler found for interaction mode: {context.interaction_mode}")
                    self._reset_interaction(context) # Reset if handler is missing
                    response = "Sorry, an internal error occurred with the current interaction."

                # Save context changes after handling interaction
                self._save_nlu_context(context)
                return response


            # 3. Standard Pipeline Flow (No Active Interaction Mode)
            response = await self._handle_state_logic(user_message, context)


        except Exception as e:
            logger.exception(f"Unhandled error processing NLU state {start_state.value} (Interaction: {context.interaction_mode}): {e}")
            response = "I encountered an unexpected error. Please try again."
            # Attempt to reset state on unhandled exceptions
            try:
                self._reset_pipeline(context)
            except Exception as reset_e:
                 logger.exception(f"Failed to reset pipeline after error: {reset_e}")


        # --- Save Final Context and Log Transition ---
        # Ensure context is saved even if handled by interaction mode earlier (idempotent)
        self._save_nlu_context(context)

        # Log state transition if it happened
        end_state = context.current_state
        if start_state != end_state:
             logger.info(
                f"NLU Pipeline: State transition {start_state.value} -> {end_state.value}",
                extra={
                    "from_state": start_state.value,
                    "to_state": end_state.value,
                    "intent": context.current_intent,
                    "interaction_mode": context.interaction_mode.value if context.interaction_mode else None
                }
            )

        # --- Save Artifacts (if applicable) ---
        # This part might need adjustment based on where artifacts are generated
        # self._save_artifacts(context, start_state, user_message, response)


        logger.info(f"NLU Pipeline END: State={context.current_state.value} (Interaction: {context.interaction_mode}), Response='{response[:50]}...'")
        return response

    async def _handle_state_logic(self, user_message: str, context: NLUPipelineContext) -> str:
        """Handles the logic for the current state when not in an interaction mode."""
        current_state = context.current_state
        response = f"Unhandled state: {current_state.value}" # Default for unhandled states

        logger.debug(f"Executing standard logic for state: {current_state.value}")

        # --- Get current implementations ---
        # Note: Intent might be None initially
        param_impl = self._get_param_extraction(context.current_intent)
        resp_impl = self._get_response_generation(context.current_intent)

        # --- State-Specific Logic ---
        if current_state == NLUPipelineState.INTENT_CLASSIFICATION:
            # --- Intent Classification ---
            logger.debug("Classifying intent...")
            intents_result = []
            if self._has_method(resp_impl, "classify_intent"):
                 try:
                     # Assuming classify_intent consistently returns list of dicts [{ "name": str, "score": float }]
                     # or an empty list, or potentially a tuple (name, score) for backward compatibility.
                     raw_result = resp_impl.classify_intent(user_message, context.excluded_intents)

                     if isinstance(raw_result, list):
                         intents_result = raw_result # Already a list
                     elif isinstance(raw_result, tuple) and len(raw_result) == 2 and isinstance(raw_result[0], str) and isinstance(raw_result[1], (float, int)):
                         # Convert single tuple result (name, score) to list format if valid
                         if raw_result[0] != "unknown":
                             intents_result = [{"name": raw_result[0], "score": float(raw_result[1])}]
                     elif raw_result:
                          logger.warning(f"Unexpected classify_intent result format: {type(raw_result)}. Treating as no result.")
                          intents_result = []
                     # else: intents_result remains []

                 except Exception as e:
                     logger.exception(f"Error calling classify_intent: {e}") # Log full traceback
                     intents_result = []
            else:
                 logger.warning("Response generation implementation lacks classify_intent method.")
                 intents_result = []

            top_intent_name = None
            top_intent_score = 0.0
            is_ambiguous = False

            # --- Process results only if we got any valid ones ---
            if intents_result and isinstance(intents_result, list):
                # Clean/Validate results (ensure dicts with name/score)
                valid_results = []
                for item in intents_result:
                    if isinstance(item, dict) and "name" in item and "score" in item and isinstance(item["name"], str) and isinstance(item["score"], (float, int)):
                        valid_results.append({"name": item["name"], "score": float(item["score"])})
                    else:
                        logger.warning(f"Invalid item format in intent results: {item}")
                intents_result = valid_results # Replace with cleaned list

                # Sort by score descending if we still have results
                if intents_result:
                    try:
                        intents_result.sort(key=lambda x: x["score"], reverse=True)
                    except Exception as e: # Catch potential errors during sort
                         logger.error(f"Error sorting intent results: {e} - Results: {intents_result}")
                         # Don't trust results after sort error? Maybe clear intents_result?
                         # For now, proceed cautiously, the top item might still be usable if list isn't empty

                # Safely extract top intent details if list not empty after cleaning/sorting
                if intents_result:
                    top_intent_data = intents_result[0]
                    top_intent_name = top_intent_data.get("name") # Already validated as str
                    top_intent_score = top_intent_data.get("score") # Already validated as float

                    # Check for ambiguity (only if >1 result and scores are close)
                    ambiguity_threshold = 0.1 # Example threshold
                    if len(intents_result) > 1:
                         second_intent_score = intents_result[1].get("score", 0.0)
                         # Ensure second score is also float for comparison
                         if isinstance(second_intent_score, (float, int)):
                             if (top_intent_score - float(second_intent_score)) < ambiguity_threshold:
                                 is_ambiguous = True
                         else:
                              logger.warning(f"Second intent had invalid score type: {intents_result[1]}")

            # --- Decision Logic (Ambiguity > Low Confidence > Proceed) ---
            if not top_intent_name:
                 # Handle case where classification failed or returned no usable results
                 logger.warning("Intent classification yielded no usable intent name.")
                 response = "Sorry, I couldn't understand your request clearly."
                 # Reset? Or just go back to waiting?
                 self._transition_state(context, NLUPipelineState.RESPONSE_TEXT_GENERATION)
                 return response # Exit early

            elif is_ambiguous:
                 logger.info(f"Intent ambiguity detected ({len(intents_result)} options). Entering clarification mode.")
                 # Ensure options are extracted correctly from the *validated* list
                 options = [i["name"] for i in intents_result]
                 context.interaction_mode = InteractionState.CLARIFYING_INTENT
                 context.interaction_data = ClarificationData(
                     options=options,
                     original_query=user_message
                     # Uses default prompt from model
                 )
                 self._transition_state(context, NLUPipelineState.INTENT_CLARIFICATION)
                 handler = self._interaction_handlers[context.interaction_mode]
                 response = handler.get_initial_prompt(context)

            # CRITICAL: Ensure top_intent_score is actually a float before comparing!
            elif isinstance(top_intent_score, (float, int)) and float(top_intent_score) < 0.8: # Configurable threshold
                 logger.info(f"Low confidence ({top_intent_score:.2f}) for intent '{top_intent_name}'. Entering clarification mode.")
                 context.interaction_mode = InteractionState.CLARIFYING_INTENT
                 # Offer the single low-confidence option
                 context.interaction_data = ClarificationData(
                     options=[top_intent_name],
                     original_query=user_message,
                     prompt="I think you might mean this, but I'm not sure:" # Specific prompt for low confidence
                 )
                 self._transition_state(context, NLUPipelineState.INTENT_CLARIFICATION)
                 handler = self._interaction_handlers[context.interaction_mode]
                 response = handler.get_initial_prompt(context)

            elif isinstance(top_intent_score, (float, int)): # Check type before assuming proceed
                 # High confidence and not ambiguous -> Proceed
                 logger.info(f"Intent classified as: {top_intent_name} (Score: {top_intent_score:.2f})")
                 context.current_intent = top_intent_name
                 context.confidence_score = top_intent_score
                 # Ensure any previous interaction mode stuff is cleared if we proceed normally
                 self._reset_interaction(context)
                 self._transition_state(context, NLUPipelineState.PARAMETER_IDENTIFICATION)
                 # Proceed directly to parameter identification in the same call
                 response = await self._handle_state_logic(user_message, context)
            else:
                 # This case handles if top_intent_score was somehow not a valid number after all checks
                 logger.error(f"Could not proceed: top_intent_score has invalid type ({type(top_intent_score)}) for intent '{top_intent_name}'.")
                 response = "Sorry, I encountered an issue processing the intent confidence."
                 self._transition_state(context, NLUPipelineState.RESPONSE_TEXT_GENERATION)
                 return response

        elif current_state == NLUPipelineState.PARAMETER_IDENTIFICATION:
            # --- Parameter Identification & Initial Validation ---
            if not context.current_intent:
                 logger.error("Reached PARAMETER_IDENTIFICATION state without an intent.")
                 self._reset_pipeline(context)
                 return "An internal error occurred (missing intent). Resetting."

            logger.debug(f"Extracting parameters for intent: {context.current_intent}")
            # TODO: Replace dummy data with actual calls
            # extracted_params = await param_impl.extract_parameters(user_message, context.current_intent, ...) # Actual call
            # validation_errors = self._validate_parameters(extracted_params, context.current_intent) # Actual validation
            extracted_params = {}
            validation_errors = []
            validation_message = None # From validate_parameters
            if self._has_method(param_impl, "identify_parameters"):
                try:
                    # Pass necessary arguments
                    extracted_params = param_impl.identify_parameters(user_message, context.current_intent)
                except Exception as e:
                    logger.error(f"Error calling identify_parameters: {e}")
                    extracted_params = {}
            else:
                logger.warning("Parameter extraction implementation lacks identify_parameters method.")

            if self._has_method(param_impl, "validate_parameters"):
                 try:
                     # Pass intent and parameters
                     validation_passed, validation_message = param_impl.validate_parameters(
                         context.current_intent, extracted_params
                     )
                     if not validation_passed:
                         validation_errors = [validation_message or "Validation failed"]
                 except Exception as e:
                     logger.error(f"Error calling validate_parameters: {e}")
                     # Decide how to handle validation error - assume invalid?
                     validation_errors = ["Error during parameter validation"]
            else:
                 logger.warning("Parameter extraction implementation lacks validate_parameters method. Assuming valid.")
                 # validation_passed defaults to True implicitly if no errors found

            # --- End Remove Dummy Data ---

            context.current_parameters.update(extracted_params) # Update with extracted (even if potentially invalid)
            context.parameter_validation_errors = validation_errors # Store errors

            if validation_errors:
                logger.info("Parameter validation errors found. Entering validation mode.")
                # Handle first error for now - improve logic to handle multiple errors potentially
                error_msg = validation_errors[0]
                # Basic parsing to find param name - improve robustness
                param_name = self._extract_param_name_from_error(error_msg, "unknown_param")

                context.interaction_mode = InteractionState.VALIDATING_PARAMETER
                context.interaction_data = ValidationData(
                    parameter_name=param_name,
                    error_message=error_msg,
                    current_value=context.current_parameters.get(param_name)
                    # Prompt uses default template from model
                )
                self._transition_state(context, NLUPipelineState.PARAMETER_VALIDATION) # Mark state
                handler = self._interaction_handlers[context.interaction_mode]
                response = handler.get_initial_prompt(context)
            else:
                # All params valid, move to execution
                logger.info("Parameters identified and valid.")
                self._transition_state(context, NLUPipelineState.CODE_EXECUTION)
                response = await self._handle_state_logic(user_message, context) # Recurse carefully

        elif current_state == NLUPipelineState.CODE_EXECUTION:
            # --- Code Execution ---
            if not context.current_intent: # Added check for parameters removed as they might be optional
                 logger.error("Reached CODE_EXECUTION state without intent.")
                 self._reset_pipeline(context)
                 return "An internal error occurred (missing intent). Resetting."

            logger.debug(f"Executing code for intent '{context.current_intent}' with params: {context.current_parameters}")
            # TODO: Replace dummy data with actual execution call
            # execution_results = await self._execute_command(...) # Replace with actual execution logic
            try:
                # Placeholder for where execution would happen
                # Assume execution logic exists elsewhere, e.g., in CommandExecutor
                # We need to get the result here. For now, use dummy data.
                execution_results = {"status": "Success", "data": "Executed placeholder."}
                logger.info(f"Placeholder code execution complete. Results: {execution_results}")
            except Exception as e:
                logger.exception("Error during placeholder code execution:")
                execution_results = {"status": "Error", "error": str(e)}
            # --- End Remove Dummy Data ---
            context.last_execution_results_for_response = execution_results # Store results

            # Check execution status - maybe need interaction if it failed? (Future enhancement)
            if execution_results.get("status") != "Success":
                 logger.warning(f"Code execution failed or reported non-success: {execution_results}")
                 # Handle failure - maybe generate error response or try recovery
                 # For now, proceed to response generation with the failure info

            self._transition_state(context, NLUPipelineState.RESPONSE_TEXT_GENERATION)
            response = await self._handle_state_logic(user_message, context) # Recurse carefully

        elif current_state == NLUPipelineState.RESPONSE_TEXT_GENERATION:
            # --- Response Generation ---
            logger.debug("Generating final response.")
            # TODO: Replace dummy data with actual call to resp_impl
            # final_response = await resp_impl.generate_response(context) # Actual call
            final_response = "Default final response."
            if self._has_method(resp_impl, "generate_response"):
                try:
                    # Determine command description and results to pass
                    cmd_desc = context.current_intent or context.last_user_message_for_response or "Unknown command"
                    exec_res = context.last_execution_results_for_response or {}
                    final_response = resp_impl.generate_response(cmd_desc, exec_res)
                except Exception as e:
                    logger.error(f"Error calling generate_response: {e}")
                    final_response = "Error generating response."
            else:
                logger.warning("Response generation implementation lacks generate_response method.")
                # Use a generic response based on execution status if possible
                status = context.last_execution_results_for_response.get("status", "Unknown") if context.last_execution_results_for_response else "Unknown"
                if status == "Success":
                    final_response = "Task completed successfully."
                elif status == "Error":
                    final_response = "An error occurred executing the command."
                else:
                    final_response = "Processing complete."

            # --- End Remove Dummy Data ---

            context.last_user_message_for_response = user_message # Save for potential feedback

            # --- Optional Feedback Step ---
            ask_for_feedback = False # Configuration or logic to decide this
            if ask_for_feedback:
                logger.info("Requesting user feedback on the response.")
                context.interaction_mode = InteractionState.AWAITING_FEEDBACK
                context.interaction_data = FeedbackData(
                    response_text=final_response,
                    execution_results=context.last_execution_results_for_response
                    # Prompt uses default from model
                )
                # State remains RESPONSE_TEXT_GENERATION while awaiting feedback
                handler = self._interaction_handlers[context.interaction_mode]
                feedback_prompt = handler.get_initial_prompt(context)
                response = f"{final_response}\n\n{feedback_prompt}"
            else:
                # If not asking for feedback, the pipeline turn is complete.
                # State remains RESPONSE_TEXT_GENERATION, ready for the *next* message.
                response = final_response
                # Consider clearing transient data like execution results if appropriate here
                # context.last_execution_results_for_response = None


        # Handle states that are primarily markers for interaction modes
        elif current_state in [NLUPipelineState.INTENT_CLARIFICATION, NLUPipelineState.PARAMETER_VALIDATION]:
             # If we reach here, it means we are *not* in an interaction mode,
             # but the state suggests we should be. This might happen if an interaction
             # was cancelled or completed without immediately proceeding.
             logger.warning(f"Reached state {current_state.value} without an active interaction mode. Resetting to INTENT_CLASSIFICATION.")
             # Best recovery is likely to restart the process for the current message
             self._transition_state(context, NLUPipelineState.INTENT_CLASSIFICATION)
             response = await self._handle_state_logic(user_message, context) # Recurse carefully

        else:
            logger.error(f"Reached _handle_state_logic with unknown or unhandled state: {current_state.value}")
            self._reset_pipeline(context)
            response = "An internal error occurred due to an unknown state."

        return response

    def _extract_param_name_from_error(self, error_msg: str, default: str = "parameter") -> str:
        """Simple helper to extract parameter name from error messages (improve robustness)."""
        try:
            # Example: "Missing required parameter 'date'"
            parts = error_msg.split("'")
            if len(parts) >= 3:
                return parts[1] # Assumes name is between single quotes
        except Exception:
            pass # Ignore parsing errors
        return default

    # ... (Remove or adapt old state handler methods like _handle_intent_classification,
    #      _handle_intent_clarification, _handle_initial_param_id_and_validate, etc.
    #      Their logic is now incorporated into _handle_state_logic or the Interaction Handlers)

    # --- Artifact Saving (Adapt as needed) ---
    # def _save_artifacts(self, context: NLUPipelineContext, start_state: NLUPipelineState, user_message: str, response: str) -> None:
    #     """Saves NLU artifacts to the conversation history."""
    #     nlu_artifacts = NLUArtifacts(
    #         start_state=start_state.value,
    #         end_state=context.current_state.value,
    #         interaction_mode=context.interaction_mode.value if context.interaction_mode else None,
    #         intent=context.current_intent,
    #         parameters=context.current_parameters,
    #         validation_errors=context.parameter_validation_errors,
    #         confidence_score=context.confidence_score,
    #         excluded_intents=context.excluded_intents
    #     )
    #     artifacts = ConversationArtifacts(nlu=nlu_artifacts)
    #     CHAT_CONTEXT.append_to_conversation_history(user_message, response, artifacts)


# ... (Potentially keep old state handlers if they contain complex logic worth preserving/adapting,
#      or remove them cleanly if their logic is fully migrated)

# ... (Rest of the existing methods like _save_artifacts_and_log_transition, _reset_pipeline, etc.) ...
# ... (Keep the existing implementation of these methods) ...

# ... (Rest of the existing methods like _save_artifacts_and_log_transition, _reset_pipeline, etc.) ...
# ... (Keep the existing implementation of these methods) ... 