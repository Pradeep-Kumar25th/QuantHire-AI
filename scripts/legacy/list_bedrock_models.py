import boto3
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
project_root = Path(__file__).parent.resolve()
load_dotenv(project_root / ".env", override=True)

def list_models():
    print("Listing available Bedrock models...")
    try:
        api_key = os.getenv("AWS_BEARER_TOKEN_BEDROCK") or os.getenv("BEDROCK_API_KEY")
        region = os.getenv("AWS_REGION", "us-east-1")
        
        session = boto3.Session()
        from botocore.config import Config
        config = Config(signature_version='bearer', region_name=region)
        
        bedrock = session.client(
            service_name='bedrock',
            region_name=region,
            config=config
        )
        # Inject bearer token
        bedrock._request_signer._credentials = type('Credentials', (), {'token': api_key})()
        
        response = bedrock.list_foundation_models()
        for model in response['modelSummaries']:
            print(f"- {model['modelId']} ({model['modelName']})")
    except Exception as e:
        print(f"Failed to list models: {e}")

if __name__ == "__main__":
    list_models()
