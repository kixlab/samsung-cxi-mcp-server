import boto3
import uuid

def read_image(image_path):
    with open(image_path, "rb") as f:
        return f.read()


def converse_with_model(model_id, image, user_message):
    bedrock_runtime = boto3.client("bedrock-runtime")
    messages = [
        {
            "role": "user",
            "content": [
                {"image": {"format": "png", "source": {"bytes": image}}},
                {"text": user_message},
            ],
        }
    ]
    response = bedrock_runtime.converse(
        modelId=model_id,
        messages=messages,
    )
    return response["output"]["message"]["content"][0]["text"]


def create_inference_profile(profile_name, model_source_arn, description, project_tag):
    client = boto3.client("bedrock", region_name="us-east-1")
    response = client.create_inference_profile(
        inferenceProfileName=profile_name,
        modelSource={"copyFrom": model_source_arn},
        description=description,
        clientRequestToken=str(uuid.uuid4()),  # ensure idempotency
        tags=[{"key": "project", "value": project_tag}]
    )
    return response["inferenceProfileArn"]


if __name__ == "__main__":
    IMAGE_NAME = "/home/seooyxx/kixlab/samsung-cxi-mcp-server/datasets/mock/id-8-2-gpt4o.png"
    MODEL_ID = "us.meta.llama3-2-90b-instruct-v1:0"
    USER_MESSAGE = "Based on this chart, which countries in Europe have the highest share?"

    # Read image
    image_data = read_image(IMAGE_NAME)

    # Converse with model
    response_text = converse_with_model(MODEL_ID, image_data, USER_MESSAGE)
    print(response_text)

    # Create inference profile
    PROFILE_NAME = "LLaMA3-11B-Profile"
    MODEL_SOURCE_ARN = "arn:aws:bedrock:us-east-1::foundation-model/meta.llama3-2-11b-instruct-v1:0"
    DESCRIPTION = "Inference profile for LLaMA3-11B"
    PROJECT_TAG = "CanvasBench"

    inference_profile_arn = create_inference_profile(PROFILE_NAME, MODEL_SOURCE_ARN, DESCRIPTION, PROJECT_TAG)
    print(inference_profile_arn)
