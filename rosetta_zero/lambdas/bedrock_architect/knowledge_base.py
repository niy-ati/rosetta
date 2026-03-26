"""Bedrock Knowledge Base integration for legacy language documentation.

Requirements: 5.1, 5.2, 5.3, 5.4
"""

import json
from typing import List, Dict, Any

from rosetta_zero.models.logic_map import LogicMap, EntryPoint, SideEffect
from rosetta_zero.utils.logging import logger
from rosetta_zero.utils.retry import with_retry, TransientError


def query_language_docs(
    bedrock_agent_client,
    knowledge_base_id: str,
    logic_map: LogicMap,
    language: str
) -> str:
    """
    Query Bedrock Knowledge Base for legacy language documentation.
    
    Args:
        bedrock_agent_client: Boto3 Bedrock Agent Runtime client
        knowledge_base_id: Knowledge Base ID for the language
        logic_map: Logic Map to extract semantic queries from
        language: Language name (COBOL, FORTRAN, MAINFRAME)
        
    Returns:
        Concatenated documentation context relevant to the Logic Map
    """
    # Generate semantic queries from Logic Map
    queries = _generate_semantic_queries(logic_map, language)
    
    # Query Knowledge Base for each semantic question
    documentation_chunks = []
    for query in queries:
        try:
            docs = _query_knowledge_base(
                bedrock_agent_client,
                knowledge_base_id,
                query
            )
            documentation_chunks.extend(docs)
        except Exception as e:
            logger.warning(
                f"Failed to query Knowledge Base for: {query}",
                extra={"error": str(e), "language": language}
            )
    
    # Combine and deduplicate documentation
    combined_docs = _combine_documentation(documentation_chunks)
    
    logger.info(
        f"Retrieved {len(documentation_chunks)} documentation chunks for {language}",
        extra={
            "language": language,
            "queries": len(queries),
            "total_length": len(combined_docs),
        }
    )
    
    return combined_docs


def _generate_semantic_queries(logic_map: LogicMap, language: str) -> List[str]:
    """Generate semantic queries from Logic Map."""
    queries = []
    
    # Query for entry point semantics
    for entry_point in logic_map.entry_points:
        queries.append(
            f"What are the semantics of {entry_point.name} in {language}?"
        )
        
        # Query for parameter types
        for param in entry_point.parameters:
            queries.append(
                f"How does {language} handle {param.type.value} data type?"
            )
    
    # Query for side effect semantics
    for side_effect in logic_map.side_effects:
        queries.append(
            f"How does {language} implement {side_effect.operation_type.value} operations?"
        )
    
    # Query for arithmetic precision
    if logic_map.arithmetic_precision.fixed_point_operations:
        queries.append(
            f"How does {language} handle fixed-point arithmetic?"
        )
    
    if logic_map.arithmetic_precision.floating_point_precision:
        queries.append(
            f"What is the floating-point precision in {language}?"
        )
    
    if logic_map.arithmetic_precision.rounding_modes:
        queries.append(
            f"What rounding modes does {language} support?"
        )
    
    # Query for control flow
    queries.append(
        f"How does {language} implement conditional branching and loops?"
    )
    
    # Query for data structures
    for data_structure in logic_map.data_structures:
        queries.append(
            f"How does {language} define and access data structure {data_structure.name}?"
        )
    
    return queries


@with_retry(max_retries=3, base_delay_seconds=2)
def _query_knowledge_base(
    bedrock_agent_client,
    knowledge_base_id: str,
    query: str
) -> List[str]:
    """Query Bedrock Knowledge Base with retry."""
    try:
        response = bedrock_agent_client.retrieve(
            knowledgeBaseId=knowledge_base_id,
            retrievalQuery={
                'text': query
            },
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': 5  # Top 5 relevant chunks
                }
            }
        )
        
        # Extract text from retrieval results
        docs = []
        for result in response.get('retrievalResults', []):
            content = result.get('content', {})
            text = content.get('text', '')
            if text:
                docs.append(text)
        
        return docs
        
    except Exception as e:
        error_str = str(e).lower()
        if any(indicator in error_str for indicator in ['throttling', 'timeout', '503', '500']):
            raise TransientError(f"Transient error querying Knowledge Base: {e}")
        raise


def _combine_documentation(chunks: List[str]) -> str:
    """Combine and deduplicate documentation chunks."""
    if not chunks:
        return ""
    
    # Deduplicate chunks
    unique_chunks = []
    seen = set()
    
    for chunk in chunks:
        # Use first 100 characters as deduplication key
        key = chunk[:100]
        if key not in seen:
            seen.add(key)
            unique_chunks.append(chunk)
    
    # Combine with separators
    combined = "\n\n---\n\n".join(unique_chunks)
    
    # Limit total length to avoid token limits
    max_length = 50000  # ~12k tokens
    if len(combined) > max_length:
        combined = combined[:max_length] + "\n\n[Documentation truncated for length]"
    
    return combined


def create_knowledge_base_for_cobol(
    bedrock_agent_client,
    s3_bucket: str,
    s3_prefix: str,
    knowledge_base_name: str = "rosetta-zero-cobol-docs"
) -> str:
    """
    Create Bedrock Knowledge Base for COBOL documentation.
    
    This function would be called during infrastructure setup to create
    the Knowledge Base and ingest COBOL language documentation.
    
    Args:
        bedrock_agent_client: Boto3 Bedrock Agent client
        s3_bucket: S3 bucket containing COBOL documentation
        s3_prefix: S3 prefix for COBOL docs
        knowledge_base_name: Name for the Knowledge Base
        
    Returns:
        Knowledge Base ID
    """
    # Note: This is a placeholder for the actual Knowledge Base creation
    # In practice, Knowledge Bases are created via CDK/CloudFormation
    logger.info(
        f"Creating Knowledge Base for COBOL: {knowledge_base_name}",
        extra={
            "s3_bucket": s3_bucket,
            "s3_prefix": s3_prefix,
        }
    )
    
    # Knowledge Base creation would happen via CDK
    # This function documents the expected structure
    return "kb-cobol-placeholder"


def create_knowledge_base_for_fortran(
    bedrock_agent_client,
    s3_bucket: str,
    s3_prefix: str,
    knowledge_base_name: str = "rosetta-zero-fortran-docs"
) -> str:
    """
    Create Bedrock Knowledge Base for FORTRAN documentation.
    
    Args:
        bedrock_agent_client: Boto3 Bedrock Agent client
        s3_bucket: S3 bucket containing FORTRAN documentation
        s3_prefix: S3 prefix for FORTRAN docs
        knowledge_base_name: Name for the Knowledge Base
        
    Returns:
        Knowledge Base ID
    """
    logger.info(
        f"Creating Knowledge Base for FORTRAN: {knowledge_base_name}",
        extra={
            "s3_bucket": s3_bucket,
            "s3_prefix": s3_prefix,
        }
    )
    
    return "kb-fortran-placeholder"


def create_knowledge_base_for_mainframe(
    bedrock_agent_client,
    s3_bucket: str,
    s3_prefix: str,
    knowledge_base_name: str = "rosetta-zero-mainframe-docs"
) -> str:
    """
    Create Bedrock Knowledge Base for mainframe system documentation.
    
    Args:
        bedrock_agent_client: Boto3 Bedrock Agent client
        s3_bucket: S3 bucket containing mainframe documentation
        s3_prefix: S3 prefix for mainframe docs
        knowledge_base_name: Name for the Knowledge Base
        
    Returns:
        Knowledge Base ID
    """
    logger.info(
        f"Creating Knowledge Base for mainframe: {knowledge_base_name}",
        extra={
            "s3_bucket": s3_bucket,
            "s3_prefix": s3_prefix,
        }
    )
    
    return "kb-mainframe-placeholder"
