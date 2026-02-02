"""
LLM factory for creating language model instances based on agent config.

Supports:
- OpenAI (gpt-4o-mini, gpt-4o, etc.)
- Anthropic (claude-3-5-sonnet, claude-3-5-haiku, etc.)
- Ollama (llama3.2, mistral, etc.)
"""
from typing import Dict, Any, Optional, Tuple
from langchain_core.language_models.chat_models import BaseChatModel


# Default model configuration (used for v1 and v2 configs)
DEFAULT_MODEL_CONFIG = {
    "provider": "openai",
    "model": "gpt-4o-mini"
}


def get_model_config(agent_config: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract model configuration from agent config.
    
    Supports v1, v2, and v3 configs:
    - v1/v2: Returns default (OpenAI gpt-4o-mini)
    - v3: Returns the configured model
    
    Args:
        agent_config: The agent's config dict
        
    Returns:
        Dict with 'provider' and 'model' keys
    """
    version = agent_config.get('version', 1)
    
    if version >= 3:
        config_data = agent_config.get('data', {})
        model_config = config_data.get('model')
        if model_config:
            return {
                "provider": model_config.get('provider', 'openai'),
                "model": model_config.get('model', 'gpt-4o-mini')
            }
    
    # Default for v1/v2 or v3 without model config
    return DEFAULT_MODEL_CONFIG.copy()


def create_llm(
    model_config: Dict[str, str],
    credentials: Dict[str, str],
    streaming: bool = True,
    temperature: float = 0,
) -> Tuple[BaseChatModel, str]:
    """
    Create a LangChain LLM instance based on model configuration.
    
    Args:
        model_config: Dict with 'provider' and 'model' keys
        credentials: Dict mapping provider names to API keys
                    e.g., {'openai': 'sk-...', 'anthropic': 'sk-ant-...'}
        streaming: Whether to enable streaming
        temperature: Model temperature (0-1)
        
    Returns:
        Tuple of (LLM instance, provider name)
        
    Raises:
        ValueError: If provider is not supported or credentials are missing
    """
    provider = model_config.get('provider', 'openai')
    model = model_config.get('model', 'gpt-4o-mini')
    
    if provider == 'openai':
        return _create_openai_llm(model, credentials, streaming, temperature), provider
    elif provider == 'anthropic':
        return _create_anthropic_llm(model, credentials, streaming, temperature), provider
    elif provider == 'ollama':
        return _create_ollama_llm(model, streaming, temperature), provider
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def _create_openai_llm(
    model: str,
    credentials: Dict[str, str],
    streaming: bool,
    temperature: float
) -> BaseChatModel:
    """Create OpenAI LLM instance."""
    from langchain_openai import ChatOpenAI
    
    api_key = credentials.get('openai')
    if not api_key:
        raise ValueError("OpenAI API key not found. Please add your OpenAI API key in account settings.")
    
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        streaming=streaming,
        temperature=temperature,
        stream_usage=True,
    )


def _create_anthropic_llm(
    model: str,
    credentials: Dict[str, str],
    streaming: bool,
    temperature: float
) -> BaseChatModel:
    """Create Anthropic LLM instance."""
    from langchain_anthropic import ChatAnthropic
    
    api_key = credentials.get('anthropic')
    if not api_key:
        raise ValueError("Anthropic API key not found. Please add your Anthropic API key in account settings.")
    
    return ChatAnthropic(
        model=model,
        api_key=api_key,
        streaming=streaming,
        temperature=temperature,
    )


def _create_ollama_llm(
    model: str,
    streaming: bool,
    temperature: float
) -> BaseChatModel:
    """Create Ollama LLM instance."""
    from langchain_ollama import ChatOllama
    import os
    
    # Ollama base URL can be configured via environment variable
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    return ChatOllama(
        model=model,
        base_url=base_url,
        streaming=streaming,
        temperature=temperature,
    )


def get_required_credential_type(provider: str) -> Optional[str]:
    """
    Get the ServiceName credential type required for a provider.
    
    Args:
        provider: The LLM provider name
        
    Returns:
        ServiceName enum value, or None if no credential needed
    """
    from src.db.service_name import ServiceName
    
    provider_to_credential = {
        'openai': ServiceName.OPENAI_API_KEY,
        'anthropic': ServiceName.ANTHROPIC_API_KEY,
        'ollama': None,  # Ollama is self-hosted, no API key needed
    }
    
    return provider_to_credential.get(provider)
