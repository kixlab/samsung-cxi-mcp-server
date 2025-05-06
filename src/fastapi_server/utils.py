from langchain.schema.messages import AIMessage, HumanMessage, ToolMessage, message_to_dict
from base64 import b64encode

def jsonify_agent_response(response):
    """
    Convert the LangChain agent response to a structured JSON format for the frontend.
    
    Args:
        response: Response object from run_agent()
        
    Returns:
        dict: Structured data ready for JSON serialization
    """
    result = {
        "main_content": "",
        "messages": [],
        "images": []
    }
    
    # Handle different response formats
    if ("messages" in response) and isinstance(response["messages"], list):
        # Extract messages
        for msg in response["messages"]:
            message_data = {
                "role": message_type_to_role(msg),
                "content": "",
                "id": getattr(msg, "id", "")
            }
            
            # Extract content based on message type
            if isinstance(msg, (HumanMessage, AIMessage, ToolMessage)):
                message_data["content"] = message_to_dict(msg)
            result["messages"].append(message_data)

    # Handle simpler string response
    elif isinstance(response, str):
        result["main_content"] = response
    
    # Handle any other response format
    else:
        try:
            result["main_content"] = str(response)
            # Try to extract more structured data if possible
            if hasattr(response, "content"):
                result["main_content"] = response.content
        except Exception as e:
            result["error"] = f"Could not parse response: {str(e)}"
    
    return result

def message_type_to_role(message):
    """Convert a LangChain message type to a role string."""
    if isinstance(message, HumanMessage):
        return "user"
    elif isinstance(message, AIMessage):
        return "assistant"
    elif isinstance(message, ToolMessage):
        return "tool"
    else:
        return "system"