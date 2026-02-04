"""
Memory MCP Server for CARL
Provides a persistent knowledge graph for storing entities, relations, and observations.
Used by the learning system to remember patterns and improve over time.
"""

import os
import json
import uuid
from datetime import datetime
from typing import Optional, List
import boto3
from boto3.dynamodb.conditions import Key, Attr
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server


# Initialize MCP server
mcp = Server("memory-mcp")

# DynamoDB client
dynamodb = boto3.resource("dynamodb")
table_name = os.environ.get("KNOWLEDGE_GRAPH_TABLE", "carl-knowledge-graph")
table = dynamodb.Table(table_name)


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid.uuid4())[:8]


def now_iso() -> str:
    """Get current time in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


@mcp.tool()
def create_entity(name: str, entity_type: str, observations: Optional[List[str]] = None) -> str:
    """
    Create a new entity in the knowledge graph.

    Args:
        name: Unique name for the entity
        entity_type: Type of entity (e.g., 'user', 'resource', 'pattern', 'concept')
        observations: Initial observations about this entity

    Returns:
        JSON with created entity details
    """
    entity_id = generate_id()
    timestamp = now_iso()

    item = {
        "pk": f"ENTITY#{name}",
        "sk": f"METADATA",
        "entity_id": entity_id,
        "name": name,
        "entity_type": entity_type,
        "observations": observations or [],
        "created_at": timestamp,
        "updated_at": timestamp
    }

    table.put_item(Item=item)

    return json.dumps({
        "entity_id": entity_id,
        "name": name,
        "entity_type": entity_type,
        "observations": observations or [],
        "message": "Entity created successfully"
    }, indent=2)


@mcp.tool()
def add_observation(entity_name: str, observation: str) -> str:
    """
    Add an observation to an existing entity.

    Args:
        entity_name: Name of the entity
        observation: New observation to add

    Returns:
        JSON with updated entity
    """
    try:
        response = table.update_item(
            Key={"pk": f"ENTITY#{entity_name}", "sk": "METADATA"},
            UpdateExpression="SET observations = list_append(if_not_exists(observations, :empty), :obs), updated_at = :ts",
            ExpressionAttributeValues={
                ":obs": [observation],
                ":empty": [],
                ":ts": now_iso()
            },
            ReturnValues="ALL_NEW"
        )

        item = response["Attributes"]
        return json.dumps({
            "name": item["name"],
            "observations": item["observations"],
            "message": "Observation added successfully"
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def create_relation(
    from_entity: str,
    to_entity: str,
    relation_type: str,
    properties: Optional[dict] = None
) -> str:
    """
    Create a relation between two entities.

    Args:
        from_entity: Name of the source entity
        to_entity: Name of the target entity
        relation_type: Type of relation in active voice (e.g., 'uses', 'contains', 'requires')
        properties: Additional properties for the relation

    Returns:
        JSON with relation details
    """
    relation_id = generate_id()
    timestamp = now_iso()

    item = {
        "pk": f"ENTITY#{from_entity}",
        "sk": f"RELATION#{relation_type}#{to_entity}",
        "relation_id": relation_id,
        "from_entity": from_entity,
        "to_entity": to_entity,
        "relation_type": relation_type,
        "properties": properties or {},
        "created_at": timestamp
    }

    table.put_item(Item=item)

    return json.dumps({
        "relation_id": relation_id,
        "from": from_entity,
        "to": to_entity,
        "type": relation_type,
        "message": "Relation created successfully"
    }, indent=2)


@mcp.tool()
def get_entity(entity_name: str, include_relations: bool = True) -> str:
    """
    Retrieve an entity and optionally its relations.

    Args:
        entity_name: Name of the entity to retrieve
        include_relations: Whether to include relations (default: True)

    Returns:
        JSON with entity details and relations
    """
    # Get entity metadata
    pk = f"ENTITY#{entity_name}"

    response = table.query(
        KeyConditionExpression=Key("pk").eq(pk)
    )

    items = response.get("Items", [])
    if not items:
        return json.dumps({"error": f"Entity '{entity_name}' not found"}, indent=2)

    entity = None
    relations = []

    for item in items:
        if item["sk"] == "METADATA":
            entity = {
                "name": item["name"],
                "entity_type": item["entity_type"],
                "observations": item.get("observations", []),
                "created_at": item["created_at"],
                "updated_at": item.get("updated_at")
            }
        elif item["sk"].startswith("RELATION#") and include_relations:
            relations.append({
                "type": item["relation_type"],
                "to": item["to_entity"],
                "properties": item.get("properties", {})
            })

    if entity:
        entity["relations"] = relations

    return json.dumps(entity, indent=2)


@mcp.tool()
def search_entities(
    query: str,
    entity_type: Optional[str] = None,
    limit: int = 20
) -> str:
    """
    Search for entities by name or observation content.

    Args:
        query: Search query (searches names and observations)
        entity_type: Filter by entity type (optional)
        limit: Maximum results to return

    Returns:
        JSON list of matching entities
    """
    # Use scan with filter for flexible search
    filter_expr = Attr("sk").eq("METADATA") & (
        Attr("name").contains(query) |
        Attr("observations").contains(query)
    )

    if entity_type:
        filter_expr = filter_expr & Attr("entity_type").eq(entity_type)

    response = table.scan(
        FilterExpression=filter_expr,
        Limit=limit
    )

    results = [
        {
            "name": item["name"],
            "entity_type": item["entity_type"],
            "observations": item.get("observations", [])[:3]  # First 3 observations
        }
        for item in response.get("Items", [])
    ]

    return json.dumps(results, indent=2)


@mcp.tool()
def get_related_entities(entity_name: str, relation_type: Optional[str] = None) -> str:
    """
    Get all entities related to a given entity.

    Args:
        entity_name: Name of the source entity
        relation_type: Filter by relation type (optional)

    Returns:
        JSON list of related entities
    """
    pk = f"ENTITY#{entity_name}"

    if relation_type:
        key_condition = Key("pk").eq(pk) & Key("sk").begins_with(f"RELATION#{relation_type}#")
    else:
        key_condition = Key("pk").eq(pk) & Key("sk").begins_with("RELATION#")

    response = table.query(KeyConditionExpression=key_condition)

    relations = [
        {
            "to": item["to_entity"],
            "type": item["relation_type"],
            "properties": item.get("properties", {})
        }
        for item in response.get("Items", [])
    ]

    return json.dumps(relations, indent=2)


@mcp.tool()
def delete_entity(entity_name: str) -> str:
    """
    Delete an entity and all its relations.

    Args:
        entity_name: Name of the entity to delete

    Returns:
        JSON confirmation message
    """
    pk = f"ENTITY#{entity_name}"

    # Get all items for this entity (metadata + relations)
    response = table.query(KeyConditionExpression=Key("pk").eq(pk))

    deleted_count = 0
    for item in response.get("Items", []):
        table.delete_item(Key={"pk": pk, "sk": item["sk"]})
        deleted_count += 1

    return json.dumps({
        "message": f"Entity '{entity_name}' deleted",
        "items_deleted": deleted_count
    }, indent=2)


@mcp.tool()
def delete_observation(entity_name: str, observation_index: int) -> str:
    """
    Delete a specific observation from an entity.

    Args:
        entity_name: Name of the entity
        observation_index: Index of the observation to delete (0-based)

    Returns:
        JSON with updated entity
    """
    try:
        response = table.update_item(
            Key={"pk": f"ENTITY#{entity_name}", "sk": "METADATA"},
            UpdateExpression=f"REMOVE observations[{observation_index}]",
            ConditionExpression="attribute_exists(pk)",
            ReturnValues="ALL_NEW"
        )

        item = response["Attributes"]
        return json.dumps({
            "name": item["name"],
            "observations": item["observations"],
            "message": "Observation deleted"
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def delete_relation(from_entity: str, relation_type: str, to_entity: str) -> str:
    """
    Delete a specific relation between entities.

    Args:
        from_entity: Source entity name
        relation_type: Type of relation
        to_entity: Target entity name

    Returns:
        JSON confirmation message
    """
    table.delete_item(
        Key={
            "pk": f"ENTITY#{from_entity}",
            "sk": f"RELATION#{relation_type}#{to_entity}"
        }
    )

    return json.dumps({
        "message": f"Relation '{from_entity}' -> '{to_entity}' ({relation_type}) deleted"
    }, indent=2)


@mcp.tool()
def get_full_graph(limit: int = 100) -> str:
    """
    Retrieve the entire knowledge graph structure.

    Args:
        limit: Maximum entities to return

    Returns:
        JSON with all entities and their relations
    """
    # Get all entity metadata
    response = table.scan(
        FilterExpression=Attr("sk").eq("METADATA"),
        Limit=limit
    )

    entities = {}
    for item in response.get("Items", []):
        entities[item["name"]] = {
            "entity_type": item["entity_type"],
            "observations": item.get("observations", [])
        }

    # Get all relations
    response = table.scan(
        FilterExpression=Attr("sk").begins_with("RELATION#"),
        Limit=limit * 5  # Assume ~5 relations per entity
    )

    relations = [
        {
            "from": item["from_entity"],
            "to": item["to_entity"],
            "type": item["relation_type"]
        }
        for item in response.get("Items", [])
    ]

    return json.dumps({
        "entities": entities,
        "relations": relations,
        "entity_count": len(entities),
        "relation_count": len(relations)
    }, indent=2)


@mcp.tool()
def store_learning_pattern(
    pattern_name: str,
    question_pattern: str,
    effective_scans: List[str],
    resources_found: List[str],
    confidence: float
) -> str:
    """
    Store a learned pattern from user interactions.
    Used by CARL's learning system to remember what works.

    Args:
        pattern_name: Descriptive name for the pattern
        question_pattern: Type of question this applies to
        effective_scans: List of scan types that work well
        resources_found: Common resources found with this pattern
        confidence: Confidence score (0.0 to 1.0)

    Returns:
        JSON confirmation
    """
    # Create pattern entity
    create_entity(
        name=pattern_name,
        entity_type="learning_pattern",
        observations=[
            f"Question pattern: {question_pattern}",
            f"Effective scans: {', '.join(effective_scans)}",
            f"Confidence: {confidence:.2f}"
        ]
    )

    # Create relations to resources
    for resource in resources_found:
        create_relation(
            from_entity=pattern_name,
            to_entity=resource,
            relation_type="finds",
            properties={"learned_from": "user_interactions"}
        )

    return json.dumps({
        "pattern_name": pattern_name,
        "message": "Learning pattern stored successfully",
        "resources_linked": len(resources_found)
    }, indent=2)


# Run MCP server
if __name__ == "__main__":
    import asyncio
    asyncio.run(stdio_server(mcp))
