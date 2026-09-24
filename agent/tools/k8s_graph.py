import os

from neo4j import GraphDatabase


def get_ownership(service: str) -> dict:
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        return {"error": "NEO4J_PASSWORD environment variable is required"}

    query = (
        "MATCH (s:Service {name: $service})<-[:OWNS]-(t:Team) "
        "OPTIONAL MATCH (t)-[:ON_CALL]->(p:Person) "
        "RETURN t.name AS team, collect(p.name) AS on_call"
    )

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        try:
            with driver.session() as session:
                record = session.execute_read(
                    lambda tx: tx.run(query, service=service).single()
                )
        finally:
            driver.close()
    except Exception as exc:
        return {"error": str(exc)}

    if record is None:
        return {"service": service, "team": None, "on_call": []}

    on_call = [name for name in record["on_call"] if name is not None]
    return {"service": service, "team": record["team"], "on_call": on_call}
