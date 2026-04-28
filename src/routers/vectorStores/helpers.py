"""
Shared helpers for the vectorStores router.
"""
from fastapi import HTTPException, status
from src.db.models import Credential
from src.db.service_name import ServiceName
from src.routers.credentials.encryption import get_credential_value
from src.utils.errors import handle_db_error


def get_pinecone_api_key(db, account_id: int) -> str:
    """
    Helper function to retrieve and decrypt the Pinecone API key for a given account.
    
    Args:
        db: Database session
        account_id: Account ID
        
    Returns:
        Decrypted Pinecone API key
        
    Raises:
        HTTPException: If credential not found
    """
    credential = db.query(Credential).filter(
        Credential.account_id == account_id,
        Credential.credential_type == ServiceName.PINECONE_API_KEY
    ).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pinecone API key not found. Please add your Pinecone API key in credentials."
        )
    
    try:
        api_key = get_credential_value(credential, "api_key")
        return api_key
    except Exception as e:
        raise handle_db_error(e, "[DECRYPT PINECONE API KEY]")
