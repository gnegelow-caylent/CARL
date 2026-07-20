"""
AWS Bedrock AgentCore Client

Handles invocation of CARL AgentCore agents.
"""
import os
import json
import uuid
import logging
import boto3
from botocore.config import Config
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def get_boto_session() -> boto3.Session:
    """Get configured boto3 session with user's AWS credentials."""
    profile = os.getenv("AWS_PROFILE")
    region = os.getenv("AWS_REGION", "us-east-1")

    if profile:
        session = boto3.Session(profile_name=profile, region_name=region)
        logger.info(f"Using AWS profile: {profile}, region: {region}")
    else:
        session = boto3.Session(region_name=region)
        logger.info(f"Using default AWS credentials, region: {region}")

    return session

async def invoke_agentcore_agent(
    runtime_arn: str,
    payload: Dict[str, Any],
    session_id: Optional[str] = None,
    max_retries: int = 1
) -> str:
    """
    Invoke an AgentCore agent runtime.

    Args:
        runtime_arn: AgentCore runtime ARN
        payload: Payload to send to agent (must be JSON serializable)
        session_id: Optional session ID for conversation continuity
        max_retries: Number of retries on timeout (default 1 for cold start)

    Returns:
        Agent response as string

    Raises:
        Exception if invocation fails
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    logger.info(f"Invoking AgentCore: {runtime_arn}")
    logger.debug(f"Session: {session_id}, Payload: {payload}")

    last_error = None

    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                logger.info(f"Retry attempt {attempt}/{max_retries} (agent may be cold starting...)")

            # Get boto3 client with increased timeout
            session = get_boto_session()
            config = Config(
                read_timeout=300,  # 5 minutes for cold starts
                connect_timeout=60
            )
            client = session.client('bedrock-agentcore', config=config)

            # Invoke agent runtime
            response = client.invoke_agent_runtime(
                agentRuntimeArn=runtime_arn,
                runtimeSessionId=session_id,
                payload=json.dumps(payload).encode('utf-8')
            )

            # Parse streaming response
            full_response = ""
            event_stream = response.get('responseStream')

            if event_stream:
                for event in event_stream:
                    # AgentCore returns chunks
                    if 'chunk' in event:
                        chunk_data = event['chunk']
                        if 'bytes' in chunk_data:
                            chunk_text = chunk_data['bytes'].decode('utf-8')
                            full_response += chunk_text

            # Also check for direct response body
            if not full_response and 'body' in response:
                body = response['body'].read().decode('utf-8')
                result = json.loads(body)
                full_response = result.get('result', body)

            if not full_response:
                if attempt < max_retries:
                    logger.warning(f"Empty response on attempt {attempt + 1}, retrying...")
                    last_error = "Empty response (possible cold start)"
                    continue
                else:
                    logger.warning("AgentCore returned empty response after all retries")
                    return f"⚠️ Agent timeout - this usually happens on first use (cold start).\n\nPlease try again - the agent should respond quickly now that it's warmed up."

            logger.info(f"AgentCore response: {len(full_response)} characters")
            return full_response

        except client.exceptions.ValidationException as e:
            logger.error(f"Validation error: {e}")
            return f"❌ Configuration Error: {e}\n\nCheck that AgentCore runtime ARN is correct."

        except client.exceptions.ResourceNotFoundException as e:
            logger.error(f"AgentCore runtime not found: {e}")
            return f"❌ AgentCore Runtime Not Found: {runtime_arn}\n\nPlease deploy CARL infrastructure first:\ncd carl-infrastructure/mcp-deployment\nterraform apply"

        except client.exceptions.AccessDeniedException as e:
            logger.error(f"Access denied: {e}")
            return f"❌ Access Denied: {e}\n\nEnsure your AWS credentials have:\n- bedrock:InvokeAgentRuntime permission\n- Access to runtime: {runtime_arn}"

        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"Invocation failed on attempt {attempt + 1}: {e}, retrying...")
                last_error = str(e)
                continue
            else:
                logger.exception(f"AgentCore invocation failed after all retries: {e}")
                raise

    # Should never reach here, but just in case
    if last_error:
        return f"⚠️ Agent failed after {max_retries + 1} attempts: {last_error}\n\nPlease try again."
    return "⚠️ Unexpected error - please try again."
