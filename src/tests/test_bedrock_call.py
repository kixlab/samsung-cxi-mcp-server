# 📄 tools/CanvasBench/src/tests/test_bedrock_call.py

import boto3
from langchain_community.chat_models import BedrockChat  # Claude 3 계열
from langchain_community.llms import Bedrock             # LLaMA 계열

def get_bedrock_model(model_name: str):
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")

    model_map = {
        "claude-3-5-sonnet": "anthropic.claude-3-5-sonnet-20240620-v1:0",
        "claude-3-opus": "anthropic.claude-3-opus-20240229-v1:0",
        "llama-11b": "meta.llama3-2-11b-instruct-v1:0",
        "llama-90b": "meta.llama3-2-90b-instruct-v1:0",
    }

    model_id = model_map.get(model_name)
    if model_id is None:
        raise ValueError(f"Unsupported model name: {model_name}")

    if model_name.startswith("claude"):
        return BedrockChat(
            client=bedrock_client,
            model_id=model_id,
            model_kwargs={"temperature": 0.7, "max_tokens": 1024},
        )
    elif model_name.startswith("llama"):
        return Bedrock(
            client=bedrock_client,
            model_id=model_id,
            model_kwargs={"temperature": 0.7, "max_gen_len": 512},
        )

def test_model(model_name, prompt):
    print(f"\n🔹 Testing model: {model_name}")
    model = get_bedrock_model(model_name)
    response = model.invoke(prompt)
    print("✅ Response:\n", response)

if __name__ == "__main__":
    test_model("claude-3-5-sonnet", "Explain the purpose of the AWS Well-Architected Framework.")
    test_model("llama-11b", "Suggest improvements to a mobile login screen.")
