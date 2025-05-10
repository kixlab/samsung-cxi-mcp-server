# src/fastapi_server/model_factory.py

import os
import boto3
from langchain_openai import ChatOpenAI
from langchain_aws import ChatBedrock
from langchain_google_vertexai import ChatVertexAI
from langchain_google_genai import ChatGoogleGenerativeAI
from vertexai import init as vertexai_init

def get_model(model_name: str = None):
    """
    Return a LangChain-compatible chat model based on model_name.
    """
    if model_name is None:
        model_name = os.getenv("MODEL_NAME", "gpt-4o")  # default

    if model_name.startswith("gpt"):
        model_map = {
            "gpt-4o": "gpt-4o",
            "gpt-4.1": "gpt-4.1"
        }
        model_id = model_map.get(model_name)
        if not model_id:
            raise ValueError(f"Unsupported OpenAI model: {model_name}")

        return ChatOpenAI(
            model=model_name,
            temperature=0.7,
            max_tokens=1024,
        )

    elif model_name.startswith("claude"):
        bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
        model_map = {
            "claude-3-5-sonnet": "anthropic.claude-3-5-sonnet-20240620-v1:0",
            # "claude-3-opus": "anthropic.claude-3-opus-20240229-v1:0",
        }
        model_id = model_map.get(model_name)
        if not model_id:
            raise ValueError(f"Unsupported Claude model: {model_name}")

        return ChatBedrock(
            client=bedrock_client,
            model_id=model_id,
            model_kwargs={"temperature": 0.7, "max_tokens": 1024}
        )

    # elif model_name.startswith("gemini"):
        
    #     vertexai_init(project="prj-samsung-cxi", location="us-central1")
        
    #     return ChatVertexAI(
    #         model="gemini-2.5-pro-preview-05-06",
    #         model_kwargs={"temperature": 0.7, "max_tokens": 1024}
    #     )

    elif model_name.startswith("gemini"):
                
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            model_kwargs={"temperature": 0.7, "max_tokens": 1024}
        )


    else:
        raise ValueError(f"Unsupported model: {model_name}")
