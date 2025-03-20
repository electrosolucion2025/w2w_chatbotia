import logging
from .openai_service import OpenAIService

logger = logging.getLogger(__name__)

class ConversationService:
    """Service for managing conversations with users"""
    
    def __init__(self, max_context_length=30):
        self.openai_service = OpenAIService()
        self.conversations = {}  # Store conversations in memory for now
        self.max_context_length = max_context_length
    
    def get_conversation(self, user_id):
        """Get or create a conversation for a user"""
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        return self.conversations[user_id]
    
    def add_message(self, user_id, message, is_from_user=True):
        """Add a message to a user's conversation history"""
        conversation = self.get_conversation(user_id)
        
        # Add the new message
        role = "user" if is_from_user else "assistant"
        conversation.append({"role": role, "content": message})
        
        # Trim conversation if it's too long
        if len(conversation) > self.max_context_length:
            # Keep the most recent messages
            conversation = conversation[-self.max_context_length:]
            self.conversations[user_id] = conversation
    
    def generate_response(self, user_id, message, company_info=None):
        """Generate a response for a user message"""
        # Check if this is the first message from this user
        is_first_message = user_id not in self.conversations or len(self.conversations[user_id]) == 0
        
        # Add the user message to the conversation
        self.add_message(user_id, message, is_from_user=True)
        
        # Get the conversation context
        conversation = self.get_conversation(user_id)
        
        # Generate a response, indicating if it's the first message
        response = self.openai_service.generate_response(
            message=message,
            context=conversation,
            company_info=company_info,
            is_first_message=is_first_message
        )
        
        # Add the assistant's response to the conversation
        self.add_message(user_id, response, is_from_user=False)
        
        return response
    
    def clear_conversation(self, user_id):
        """Clear a user's conversation history"""
        self.conversations[user_id] = []