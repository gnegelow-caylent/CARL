"""
CARL Architecture Conversation Handler

Manages multi-turn conversations with contextual questioning for architecture recommendations.
"""

import logging
import time
import boto3
from typing import Dict, Any, List, Optional
from knowledge.architecture_questions import ARCHITECTURE_QUESTIONS

logger = logging.getLogger(__name__)


class ArchitectConversationHandler:
    """Multi-turn architecture conversations with contextual questions."""

    def __init__(self, config_table_name: str):
        self.dynamodb = boto3.resource('dynamodb')
        self.config_table = self.dynamodb.Table(config_table_name)

    def start_conversation(self, user_id: str, workspace_id: str, category: str,
                          original_question: str) -> Dict[str, Any]:
        """Start contextual questioning flow."""

        # Validate category
        if category not in ARCHITECTURE_QUESTIONS:
            return {
                "response_type": "ephemeral",
                "text": f"❌ Unknown category: {category}\n\n"
                f"Available categories: {', '.join(ARCHITECTURE_QUESTIONS.keys())}"
            }

        # Save conversation state
        self._save_conversation_state(
            user_id=user_id,
            workspace_id=workspace_id,
            category=category,
            original_question=original_question,
            current_question_index=0,
            answers={}
        )

        # Ask first question
        return self.ask_next_question(user_id, workspace_id, category)

    def ask_next_question(self, user_id: str, workspace_id: str, category: str) -> Dict[str, Any]:
        """Ask the next contextual question."""

        # Get conversation state
        state = self._get_conversation_state(user_id, workspace_id)
        if not state:
            return {
                "response_type": "ephemeral",
                "text": "❌ Conversation state not found. Please start over with `/carl architect <question>`"
            }

        question_index = state.get('current_question_index', 0)
        questions = ARCHITECTURE_QUESTIONS[category]["questions"]

        # Check if done with questions
        if question_index >= len(questions):
            return self.give_recommendation(user_id, workspace_id, category)

        # Get current question
        question = questions[question_index]

        # Format as Slack blocks with buttons
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Question {question_index + 1} of {len(questions)}*\n\n{question['text']}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": option},
                        "value": f"{category}|{question['id']}|{option}",
                        "action_id": f"architect_answer_{question['id']}"
                    }
                    for option in question["options"]
                ]
            }
        ]

        # Add progress indicator
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"📊 Progress: {question_index + 1}/{len(questions)} questions"
                }
            ]
        })

        return {
            "response_type": "ephemeral",
            "blocks": blocks
        }

    def handle_answer(self, user_id: str, workspace_id: str, category: str,
                     question_id: str, answer: str) -> Dict[str, Any]:
        """Handle user's answer and continue conversation."""

        # Get current state
        state = self._get_conversation_state(user_id, workspace_id)
        if not state:
            return {
                "response_type": "ephemeral",
                "text": "❌ Conversation state not found."
            }

        # Save answer
        answers = state.get('answers', {})
        answers[question_id] = answer

        # Increment question index
        question_index = state.get('current_question_index', 0) + 1

        # Update state
        self._save_conversation_state(
            user_id=user_id,
            workspace_id=workspace_id,
            category=category,
            original_question=state['original_question'],
            current_question_index=question_index,
            answers=answers
        )

        # Continue to next question
        return self.ask_next_question(user_id, workspace_id, category)

    def give_recommendation(self, user_id: str, workspace_id: str, category: str) -> Dict[str, Any]:
        """Give final recommendation based on answers."""

        # Get conversation state
        state = self._get_conversation_state(user_id, workspace_id)
        if not state:
            return {
                "response_type": "ephemeral",
                "text": "❌ Conversation state not found."
            }

        answers = state.get('answers', {})
        original_question = state.get('original_question', '')

        # Calculate recommendation
        result = self.calculate_recommendation(category, answers)

        # Build response
        explanation = self.build_contextual_explanation(result, answers, original_question)

        # Clear conversation state
        self._clear_conversation_state(user_id, workspace_id)

        return {
            "response_type": "in_channel",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Architecture Recommendation*\n\n_{original_question}_"
                    }
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": explanation
                    }
                }
            ]
        }

    def calculate_recommendation(self, category: str, answers: Dict[str, str]) -> Dict[str, Any]:
        """Score all options based on user's answers using weighted scoring."""

        questions = ARCHITECTURE_QUESTIONS[category]["questions"]
        recommendation_logic = ARCHITECTURE_QUESTIONS[category]["recommendation_logic"]

        # Calculate scores for each option
        option_scores = {}

        for option_name, scoring_rules in recommendation_logic.items():
            score = 0

            # Calculate score based on answers
            for question_id, answer in answers.items():
                if question_id in scoring_rules:
                    question_scores = scoring_rules[question_id]

                    # Add score if this answer is relevant to this option
                    if answer in question_scores:
                        # Get question weight
                        question = next((q for q in questions if q["id"] == question_id), None)
                        weight = question.get("weight", 1) if question else 1

                        # Weighted score
                        score += question_scores[answer] * weight

            option_scores[option_name] = score

        # Sort by score
        sorted_options = sorted(option_scores.items(), key=lambda x: x[1], reverse=True)

        # Get top recommendation and alternatives
        top_option = sorted_options[0][0]
        alternatives = [opt[0] for opt in sorted_options[1:3]]  # Top 2 alternatives

        return {
            "recommended": top_option,
            "alternatives": alternatives,
            "scores": dict(sorted_options),
            "category": category
        }

    def build_contextual_explanation(self, result: Dict[str, Any], answers: Dict[str, str],
                                     original_question: str) -> str:
        """Build explanation that considers cost in context, not spam."""

        category = result["category"]
        recommended = result["recommended"]
        alternatives = result["alternatives"]

        # Get option details from architecture_questions
        options_map = ARCHITECTURE_QUESTIONS[category].get("options", {})
        recommended_details = options_map.get(recommended, {})

        # Build explanation focusing on WHY this fits
        explanation = f"### ✅ Recommended: **{recommended}**\n\n"

        # Why it works (focus on fit, not cost)
        explanation += "**Why this works for you:**\n"

        if "use_case" in answers:
            explanation += f"• Your use case ({answers['use_case']}) is a great match\n"

        if "data_volume" in answers:
            explanation += f"• Handles your data volume ({answers['data_volume']}) efficiently\n"

        if "budget" in answers:
            explanation += f"• Fits your budget expectations ({answers['budget']})\n"

        if "team_size" in answers:
            explanation += f"• Appropriate complexity for team size ({answers['team_size']})\n"

        # Cost in context (one line, not spam)
        cost_range = recommended_details.get("monthly_cost_range", "Contact AWS")
        if isinstance(cost_range, tuple):
            explanation += f"• Monthly cost: ${cost_range[0]:.2f} - ${cost_range[1]:.2f}\n"
        else:
            explanation += f"• Monthly cost: {cost_range}\n"

        explanation += "\n"

        # Key benefits
        if "pros" in recommended_details:
            explanation += "**Key benefits:**\n"
            for pro in recommended_details["pros"][:3]:  # Top 3
                explanation += f"• {pro}\n"
            explanation += "\n"

        # Watch out for
        if "cons" in recommended_details:
            explanation += "**Watch out for:**\n"
            for con in recommended_details["cons"][:2]:  # Top 2
                explanation += f"• {con}\n"
            explanation += "\n"

        # Alternatives (if needed)
        if alternatives:
            explanation += "**Alternatives to consider:**\n"
            for alt in alternatives:
                alt_details = options_map.get(alt, {})
                alt_cost = alt_details.get("monthly_cost_range", "Variable")
                if isinstance(alt_cost, tuple):
                    cost_str = f"${alt_cost[0]:.2f}-${alt_cost[1]:.2f}/mo"
                else:
                    cost_str = str(alt_cost)

                explanation += f"• **{alt}** ({cost_str}) - "
                explanation += f"{alt_details.get('description', 'Alternative option')}\n"

        return explanation

    def _save_conversation_state(self, user_id: str, workspace_id: str, category: str,
                                original_question: str, current_question_index: int,
                                answers: Dict[str, str]) -> None:
        """Save conversation state to DynamoDB."""
        try:
            self.config_table.put_item(
                Item={
                    'pk': f'USER#{user_id}',
                    'sk': f'CONVERSATION#{workspace_id}',
                    'category': category,
                    'original_question': original_question,
                    'current_question_index': current_question_index,
                    'answers': answers,
                    'timestamp': int(time.time()),
                    'ttl': int(time.time()) + 3600  # Expire after 1 hour
                }
            )
        except Exception as e:
            logger.error(f"Error saving conversation state: {e}")

    def _get_conversation_state(self, user_id: str, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation state from DynamoDB."""
        try:
            response = self.config_table.get_item(
                Key={
                    'pk': f'USER#{user_id}',
                    'sk': f'CONVERSATION#{workspace_id}'
                }
            )
            return response.get('Item')
        except Exception as e:
            logger.error(f"Error getting conversation state: {e}")
            return None

    def _clear_conversation_state(self, user_id: str, workspace_id: str) -> None:
        """Clear conversation state from DynamoDB."""
        try:
            self.config_table.delete_item(
                Key={
                    'pk': f'USER#{user_id}',
                    'sk': f'CONVERSATION#{workspace_id}'
                }
            )
        except Exception as e:
            logger.error(f"Error clearing conversation state: {e}")

    def is_in_conversation(self, user_id: str, workspace_id: str) -> bool:
        """Check if user is currently in a conversation."""
        state = self._get_conversation_state(user_id, workspace_id)
        return state is not None

    def cancel_conversation(self, user_id: str, workspace_id: str) -> Dict[str, Any]:
        """Cancel current conversation."""
        self._clear_conversation_state(user_id, workspace_id)
        return {
            "response_type": "ephemeral",
            "text": "✅ Conversation cancelled. You can start a new one with `/carl architect <question>`"
        }
