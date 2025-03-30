"""Integration tests for the NLU Pipeline using the todo_list example."""

import pytest
import os
import sys
from pathlib import Path
from unittest import mock # Import mock

# Ensure the project root is in sys.path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from talk2py import CHAT_CONTEXT
from talk2py.nlu_pipeline.pipeline_manager import NLUPipelineManager
from talk2py.nlu_pipeline.models import NLUPipelineState
from talk2py.nlu_pipeline.chat_context_extensions import get_nlu_context, reset_nlu_pipeline, set_nlu_context
from talk2py.types import ConversationArtifacts

# Fixtures from conftest.py will be automatically used: 
# temp_todo_app, todolist_registry, todolist_executor, _chat_context_reset

@pytest.mark.usefixtures("_chat_context_reset", "temp_todo_app")
class TestNLUPipelineIntegration:
    """Test suite for NLU pipeline integration with the todo_list app."""

    def setup_method(self, method):
        """Set up the test method by getting the pipeline manager."""
        # Initialization of app state/objects if needed, but not ChatContext registration
        from examples.todo_list.todo_list import init_todolist_app
        init_todolist_app() 
        
        self.pipeline = NLUPipelineManager()
        self.app_path = f"{project_root}/tests/tmp/todo_list" # Store app path

        # Mock dspy.Predict globally for this test class to avoid external calls
        self.mock_dspy_predict_patcher = mock.patch('talk2py.nlu_pipeline.default_response_generation.dspy.Predict')
        self.mock_dspy_predict = self.mock_dspy_predict_patcher.start()
        # Configure a default return value for the mock predictor call
        prediction_mock = mock.MagicMock()
        prediction_mock.result_summary = "Mocked LLM Response"
        self.mock_dspy_predict.return_value.return_value = prediction_mock

    def teardown_method(self, method):
        """Stop the global mock patcher."""
        self.mock_dspy_predict_patcher.stop()

    def _register_and_reset(self):
        """Helper to register the app context and reset NLU state within a test."""
        CHAT_CONTEXT.register_app(self.app_path)
        # Reset NLU state *after* app path is set
        reset_nlu_pipeline()
        # Re-initialize app object in context if needed after registration/reset
        from examples.todo_list.todo_list import init_todolist_app
        init_todolist_app()
        # Force loading of default NLU implementations before mocks are applied
        # We need a command key to load; use a common one from the app
        common_command_key = "todo_list.TodoList.add_todo" 
        self.pipeline._get_param_extraction(common_command_key) 
        self.pipeline._get_response_generation(common_command_key)
        # Verify they are loaded (optional assertion for debugging)
        assert self.pipeline._param_extraction_impl is not None
        assert self.pipeline._response_generation_impl is not None

    def test_simple_add_todo_command(self, mocker):
        """Test processing a simple 'add_todo' command."""
        self._register_and_reset() # Register and reset NLU at the start
        user_message = "add todo buy groceries"
        intent_to_test = "todo_list.TodoList.add_todo"
        expected_params = {'description': 'buy groceries'}

        # Mock identify_parameters since the default impl might not extract correctly
        mocker.patch.object(
            self.pipeline._param_extraction_impl,
            'identify_parameters',
            return_value=expected_params
        )

        # Process the message
        response = self.pipeline.process_message(user_message)

        # Assertions
        nlu_context = get_nlu_context()
        # The pipeline should classify, identify parameters (as add_todo requires them),
        # validate (default pass), and generate response all due to immediate calls
        assert nlu_context.current_state == NLUPipelineState.RESPONSE_TEXT_GENERATION
        history = CHAT_CONTEXT.get_conversation_history()
        assert len(history) == 1
        _query, _resp, artifacts = history[0]

        assert artifacts is not None
        assert artifacts.nlu is not None # Check the nested nlu object
        assert artifacts.nlu.state == NLUPipelineState.RESPONSE_TEXT_GENERATION.value
        # Check if intent was classified correctly now
        assert artifacts.nlu.intent == intent_to_test
        # Check parameters were identified by the identification step
        assert artifacts.nlu.parameters == expected_params # Use expected_params

        # The response generation uses the globally mocked predictor
        assert response == "Mocked LLM Response"

    def test_abort_command(self):
        """Test processing an 'abort' command."""
        self._register_and_reset() # Register and reset NLU at the start
        user_message = "nevermind, abort the request"
        
        # Set a state other than the initial one to see the reset effect
        nlu_context_before = get_nlu_context()
        nlu_context_before.current_state = NLUPipelineState.PARAMETER_VALIDATION
        nlu_context_before.current_intent = "some_intent"
        set_nlu_context(nlu_context_before) 
        
        # Process the message
        response = self.pipeline.process_message(user_message)
        
        # Assertions
        nlu_context_after = get_nlu_context()
        assert nlu_context_after.current_state == NLUPipelineState.RESPONSE_TEXT_GENERATION
        assert nlu_context_after.current_intent is None
        assert nlu_context_after.current_parameters == {}
        assert response == "Okay, cancelling the current operation."

    def test_ambiguous_intent_clarification(self, mocker):
        """Test Example 2: Ambiguous intent clarification flow."""
        self._register_and_reset() # Register and reset NLU at the start
        # Mock classify_intent to return medium confidence
        mocker.patch.object(
            self.pipeline._response_generation_impl, 
            'classify_intent', 
            return_value=("todo_list.TodoList.get_active_todos", 0.6)
        )
        # Mock clarify_intent to return the confirmed intent after user input
        mock_clarify = mocker.patch.object(
            self.pipeline._response_generation_impl, 
            'clarify_intent',
            # Simulate user confirms the proposed intent
            return_value="todo_list.TodoList.get_active_todos" 
        )

        # 1. Initial ambiguous message
        user_message_1 = "show my todos"
        response_1 = self.pipeline.process_message(user_message_1)
        nlu_context_1 = get_nlu_context()

        # Should transition to INTENT_CLARIFICATION and return the clarification prompt
        assert nlu_context_1.current_state == NLUPipelineState.INTENT_CLARIFICATION
        assert "I think you mean 'todo_list.TodoList.get_active_todos'" in response_1
        assert nlu_context_1.current_intent == "todo_list.TodoList.get_active_todos"

        # 2. User provides clarification (e.g., "Yes")
        user_message_2 = "Yes, that one"
        response_2 = self.pipeline.process_message(user_message_2)
        nlu_context_2 = get_nlu_context()

        # clarify_intent should have been called with the new message and previous context
        mock_clarify.assert_called_once_with(user_message_2, [("todo_list.TodoList.get_active_todos", 0.6)])
        # Since get_active_todos requires no parameters, it should bypass identification/validation
        assert nlu_context_2.current_state == NLUPipelineState.RESPONSE_TEXT_GENERATION
        # Intent should NOT be cleared after successful execution/response
        # It is cleared only at the start of the *next* query processing
        assert nlu_context_2.current_intent == "todo_list.TodoList.get_active_todos"
        # Check response (mocked)
        assert response_2 == "Mocked LLM Response"

    def test_parameter_validation_flow(self, mocker):
        """Test Example 3: Parameter identification and validation loop."""
        self._register_and_reset() # Register and reset NLU at the start
        intent_to_test = "todo_list.TodoList.add_todo"
        mocker.patch.object(
            self.pipeline._response_generation_impl, 
            'classify_intent', 
            return_value=(intent_to_test, 0.95)
        )
        # Mock identify_parameters on the class - initially returns nothing, then returns description
        mock_identify = mocker.patch(
            # Patch the class method directly
            'talk2py.nlu_pipeline.default_param_extraction.DefaultParameterExtraction.identify_parameters',
            side_effect=[
                {}, # First call returns empty dict
                {'description': 'buy milk'} # Second call extracts the description
            ]
        )
        # Mock validate_parameters - fails first, then succeeds
        mock_validate = mocker.patch.object(
            self.pipeline._param_extraction_impl, 
            'validate_parameters', 
            side_effect=[
                (False, "Missing required parameter: description"), # First call fails
                (True, None) # Second call succeeds
            ]
        )

        # 1. Initial message, intent classified, needs params
        user_message_1 = "add a task"
        response_1 = self.pipeline.process_message(user_message_1)
        nlu_context_1 = get_nlu_context()

        # Should go through IDENTIFICATION to VALIDATION and fail
        assert nlu_context_1.current_state == NLUPipelineState.PARAMETER_VALIDATION
        assert nlu_context_1.current_intent == intent_to_test
        assert "Missing required parameter: description" in response_1
        # Initial identification called once
        mock_identify.assert_called_once_with(user_message_1, intent_to_test)
        # Validation fails, so validate_parameters is called once
        mock_validate.assert_called_once()

        # 2. User provides the missing parameter
        user_message_2 = "buy milk"
        # No need to update mock_identify.return_value, it will be called again by the validation step
        response_2 = self.pipeline.process_message(user_message_2)
        nlu_context_2 = get_nlu_context()

        # Should call identify again (in validation step), then validate successfully
        assert mock_identify.call_count == 2 
        # Validate called again
        assert mock_validate.call_count == 2
        # Should end in RESPONSE_TEXT_GENERATION after successful validation
        assert nlu_context_2.current_state == NLUPipelineState.RESPONSE_TEXT_GENERATION
        # Intent should NOT be cleared after completion, it persists until the next *new* query
        assert nlu_context_2.current_intent == intent_to_test
        # Check parameters were captured in the final successful step's artifacts
        history = CHAT_CONTEXT.get_conversation_history()
        assert len(history) == 2
        artifacts_step2 = history[1][2] # Artifacts from the step processing "buy milk"
        assert artifacts_step2 is not None and artifacts_step2.nlu is not None
        # Check the *context* parameters *before* saving artifacts, as they are used for the call
        assert nlu_context_2.current_parameters == {'description': 'buy milk'} 
        # Check artifacts parameters (which reflect context *before* reset)
        assert artifacts_step2.nlu.parameters == {'description': 'buy milk'}
        assert response_2 == "Mocked LLM Response"

    def test_intent_misinterpretation_reset(self, mocker):
        """Test Example 4: Resetting pipeline after intent misinterpretation feedback."""
        self._register_and_reset() # Register and reset NLU at the start
        wrong_intent = "todo_list.TodoList.get_closed_todos"
        correct_intent = "todo_list.TodoList.get_active_todos"
    
        # Mock classify_intent with a specific sequence of return values
        mock_classify_intent = mocker.patch.object(
            self.pipeline._response_generation_impl,
            'classify_intent',
            side_effect=[
                (wrong_intent, 0.9),    # Call 1 (user_message_1)
                (correct_intent, 0.9),  # Call 2 (user_message_2 -> reclassification)
                (correct_intent, 0.9)   # Call 3 (user_message_4 -> after reset)
            ]
        )
        # Mock categorize_user_message to detect feedback
        mock_categorize = mocker.patch.object(
            self.pipeline._response_generation_impl, 
            'categorize_user_message', 
            return_value="query" # Default to query
        )
        # Mock generate_response to give different results based on intent
        def mock_generate(*args, **kwargs):
            cmd_desc = args[0]
            if wrong_intent in cmd_desc:
                return "Showing closed todos."
            elif correct_intent in cmd_desc:
                 return "Showing active todos."
            return "Default response."
        mocker.patch.object(
             self.pipeline._response_generation_impl, 
            'generate_response', 
            side_effect=mock_generate
        )

        # 1. Initial message, wrong intent classified
        user_message_1 = "show my tasks"
        response_1 = self.pipeline.process_message(user_message_1)
        nlu_context_1 = get_nlu_context()
        
        assert nlu_context_1.current_state == NLUPipelineState.RESPONSE_TEXT_GENERATION
        assert response_1 == "Showing closed todos."
        mock_classify_intent.assert_called_once()
        # Check artifacts for wrong intent
        hist1 = CHAT_CONTEXT.get_conversation_history()
        assert hist1[0][2].nlu.intent == wrong_intent

        # 2. User gives feedback
        user_message_2 = "No, I meant the active ones"
        # Configure categorize to return feedback for this specific message
        mock_categorize.return_value = "feedback"
        response_2 = self.pipeline.process_message(user_message_2)
        nlu_context_2 = get_nlu_context()

        # Assert feedback was detected and pipeline reset/reclassified
        mock_categorize.assert_called_with(user_message_2)
        # Should reclassify using the feedback message, excluding the wrong intent
        assert mock_classify_intent.call_count == 2
        # Check that the second call excluded the wrong intent
        args, kwargs = mock_classify_intent.call_args
        # Check positional argument directly
        assert len(args) > 1 and args[1] == [wrong_intent]
        # Optionally check kwargs (should be empty or not contain excluded_intents)
        assert kwargs.get('excluded_intents') is None
        
        # Check the state after re-classification (should be RESPONSE_TEXT_GENERATION as get_active_todos has no params)
        assert nlu_context_2.current_state == NLUPipelineState.RESPONSE_TEXT_GENERATION
        # The response should be generated based on the *correct* intent
        assert response_2 == "Showing active todos."
        # Check artifacts for correct intent in the second step
        hist2 = CHAT_CONTEXT.get_conversation_history()
        assert len(hist2) == 2
        assert hist2[1][2].nlu.intent == correct_intent

        # 3. User provides negative feedback
        user_message_3 = "No, that's not what I wanted."
        mock_categorize.return_value = "feedback" # Change mock to return feedback
        response_3 = self.pipeline.process_message(user_message_3)
        nlu_context_3 = get_nlu_context()

        # Feedback detected, should reset pipeline state and ask for clarification again
        assert nlu_context_3.current_state == NLUPipelineState.INTENT_CLASSIFICATION
        assert nlu_context_3.current_intent is None # Reset
        assert response_3 == "My apologies. Could you please rephrase your request?" # Default feedback response

        # 4. User rephrases the request
        user_message_4 = "Show me what I need to do today"
        mock_categorize.return_value = "query" # Back to query
        response_4 = self.pipeline.process_message(user_message_4)
        nlu_context_4 = get_nlu_context()

        # classify_intent should be called again, this time excluding the wrong intent
        # Check the *third* call to classify_intent (after user_message_4)
        assert mock_classify_intent.call_count == 3
        # Assert the last call was made with the message and empty excluded_intents (positional)
        mock_classify_intent.assert_called_with(user_message_4, [])

        # Pipeline should now classify correctly and generate the right response
        assert nlu_context_4.current_state == NLUPipelineState.RESPONSE_TEXT_GENERATION
        assert nlu_context_4.current_intent == correct_intent # Correct intent set
        assert response_4 == "Showing active todos." # Correct response generated

    def test_classroom_mode_feedback_loop(self, mocker):
        """Test Example 5: Feedback on response in classroom mode."""
        self._register_and_reset() # Register and reset NLU at the start
        intent_to_test = "todo_list.TodoList.get_active_todos"
        # Set classroom mode
        context = get_nlu_context()
        context.classroom_mode = True
        set_nlu_context(context)
        
        mocker.patch.object(
            self.pipeline._response_generation_impl, 
            'classify_intent', 
            return_value=(intent_to_test, 0.95)
        )
        # Mock generate_response - return different responses
        mock_generate = mocker.patch.object(
            self.pipeline._response_generation_impl, 
            'generate_response', 
            side_effect=["Initial list of active todos.", "Formatted list of active todos."]
        )
        # Mock categorize_user_message to detect feedback
        mock_categorize = mocker.patch.object(
            self.pipeline._response_generation_impl, 
            'categorize_user_message', 
            return_value="query" # Default
        )

        # 1. Initial command
        user_message_1 = "show active todos"
        response_1 = self.pipeline.process_message(user_message_1)
        nlu_context_1 = get_nlu_context()

        assert nlu_context_1.current_state == NLUPipelineState.RESPONSE_TEXT_GENERATION
        assert response_1 == "Initial list of active todos."
        assert mock_generate.call_count == 1

        # 2. User gives feedback on the response
        user_message_2 = "format that better please"
        # Configure categorize to return feedback
        mock_categorize.return_value = "feedback"
        response_2 = self.pipeline.process_message(user_message_2)
        nlu_context_2 = get_nlu_context()

        # Assert state remains RESPONSE_TEXT_GENERATION in classroom mode
        mock_categorize.assert_called_with(user_message_2)
        assert nlu_context_2.current_state == NLUPipelineState.RESPONSE_TEXT_GENERATION
        # Check that generate_response was called twice (initial + refinement)
        assert mock_generate.call_count == 2
        # Check that the second response is the refined one
        assert response_2 == "Formatted list of active todos."

    def test_abort_during_parameter_validation(self, mocker):
        """Test Example 6: Abort command during parameter validation."""
        self._register_and_reset() # Register and reset NLU at the start
        intent_to_test = "todo_list.TodoList.add_todo"
        mocker.patch.object(
            self.pipeline._response_generation_impl, 
            'classify_intent', 
            return_value=(intent_to_test, 0.95)
        )
        mocker.patch.object(
            self.pipeline._param_extraction_impl, 
            'identify_parameters',
            return_value={}
        )
        mocker.patch.object(
            self.pipeline._param_extraction_impl, 
            'validate_parameters', 
            return_value=(False, "Missing description")
        ) 
        # Mock categorize_user_message to detect abort
        mock_categorize = mocker.patch.object(
            self.pipeline._response_generation_impl, 
            'categorize_user_message', 
            return_value="query" # Default
        )

        # 1. Initial message -> leads to PARAMETER_VALIDATION
        user_message_1 = "add task"
        response_1 = self.pipeline.process_message(user_message_1)
        nlu_context_1 = get_nlu_context()
        
        assert nlu_context_1.current_state == NLUPipelineState.PARAMETER_VALIDATION
        assert "Missing description" in response_1

        # 2. User sends abort message
        user_message_2 = "actually, cancel that"
        mock_categorize.return_value = "abort" # Set mock for this specific call
        response_2 = self.pipeline.process_message(user_message_2)
        nlu_context_2 = get_nlu_context()

        # Assert pipeline resets
        mock_categorize.assert_called_with(user_message_2)
        assert nlu_context_2.current_state == NLUPipelineState.RESPONSE_TEXT_GENERATION
        assert nlu_context_2.current_intent is None
        assert nlu_context_2.current_parameters == {}
        assert response_2 == "Okay, cancelling the current operation."

    # TODO: Add more tests:
    # - Test intent clarification flow (might need mocking or specific setup)
    # - Test parameter identification/validation flow
    # - Test feedback handling
    # - Test state persistence across multiple messages
    # - Test interaction with CommandExecutor (might require a separate test class or more complex fixture)
    # - Test with NLU overrides for the todo_list app

    # Add more test methods as needed 