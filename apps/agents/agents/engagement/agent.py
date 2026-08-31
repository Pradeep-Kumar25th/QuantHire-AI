"""Engagement agent for candidate chatbot interactions."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from agents.base.agent import AgentConfig, BaseAgent
from agents.base.result import AgentResult


class ChatMessage(BaseModel):
    """Chat message model."""

    role: str  # "user" or "assistant"
    content: str


class EngagementAgent(BaseAgent):
    """Agent for engaging with candidates via chatbot."""

    def __init__(self):
        """Initialize engagement agent."""
        config = AgentConfig(
            name="EngagementAgent",
            description="Engages with candidates, collects information, answers questions",
            temperature=0.7,  # Friendly, conversational
        )
        super().__init__(config)

    def _get_system_prompt(self, context: Dict[str, Any]) -> str:
        """Get system prompt for engagement.
        
        Args:
            context: Context about candidate and job
            
        Returns:
            System prompt
        """
        candidate_name = context.get("candidate_name", "there")
        job_title = context.get("job_title", "this position")
        company_name = context.get("company_name", "our company")
        
        return f"""You are a friendly, professional virtual recruiter for {company_name}.

You are chatting with {candidate_name} about the {job_title} position.

Your goals:
1. Answer questions about the role, company, and hiring process
2. Collect any missing information from the candidate
3. Provide updates on application status
4. Schedule interviews if requested
5. Address concerns and maintain positive engagement

Guidelines:
- Be warm, professional, and helpful
- Keep responses concise but informative
- If you don't know something, say so and offer to connect them with a recruiter
- Collect information naturally in conversation
- Respect candidate's time
- Be encouraging and positive

Missing information to collect: {context.get('missing_fields', 'None')}

Do not:
- Make promises about hiring decisions
- Share confidential information
- Pressure the candidate
- Use overly formal or robotic language"""

    async def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """Process chat interaction.
        
        Args:
            input_data: Dictionary with:
                - message: User's message
                - conversation_history: List of previous messages
                - context: Context about candidate/job
                
        Returns:
            AgentResult with bot response
        """
        message = input_data.get("message", "")
        history = input_data.get("conversation_history", [])
        context = input_data.get("context", {})
        
        if not message:
            return self._create_result(
                output={"response": "Hello! How can I help you today?"},
                confidence=1.0,
            )

        try:
            # Build conversation
            system_prompt = self._get_system_prompt(context)
            
            # Format history for LLM
            conversation = "\n".join([
                f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
                for msg in history[-10:]  # Last 10 messages for context
            ])
            
            user_prompt = f"""Previous conversation:
{conversation}

User: {message}

Respond naturally and helpfully:"""

            # Generate response
            llm_response = await self.llm_client.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            
            response_text = llm_response.content.strip()
            
            # Detect intents (simple keyword matching, could be enhanced with NLP)
            intents = []
            if any(word in message.lower() for word in ["schedule", "interview", "meeting", "time"]):
                intents.append("schedule_interview")
            if any(word in message.lower() for word in ["status", "application", "where", "stage"]):
                intents.append("check_status")
            if any(word in message.lower() for word in ["salary", "compensation", "pay", "benefits"]):
                intents.append("compensation_inquiry")
            
            return self._create_result(
                output={
                    "response": response_text,
                    "intents": intents,
                },
                confidence=0.85,
                metadata={
                    "tokens_used": llm_response.total_tokens,
                    "cost_usd": llm_response.cost_usd,
                },
            )

        except Exception as e:
            return self._create_result(
                output={"response": "I apologize, but I'm having trouble right now. Please try again or contact our recruiting team directly."},
                success=False,
                error=str(e),
            )

    async def generate_greeting(self, context: Dict[str, Any]) -> str:
        """Generate personalized greeting message.
        
        Args:
            context: Context about candidate
            
        Returns:
            Greeting message
        """
        candidate_name = context.get("candidate_name", "there")
        job_title = context.get("job_title", "a position")
        
        result = await self.execute({
            "message": "",
            "conversation_history": [],
            "context": context,
        })
        
        if result.success:
            return result.output.get("response", f"Hi {candidate_name}! Thanks for your interest in the {job_title} role. How can I help you today?")
        
        return f"Hi {candidate_name}! Thanks for your interest in the {job_title} role. How can I help you today?"

