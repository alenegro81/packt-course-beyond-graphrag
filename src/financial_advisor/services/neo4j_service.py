from typing import Any, Dict, List, Optional

from neo4j import Driver, GraphDatabase

from financial_advisor.config import settings


class Neo4jService:
    def __init__(self) -> None:
        self.driver: Driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
            max_connection_pool_size=50,
        )
        self.database = settings.neo4j_database

    def close(self) -> None:
        if self.driver:
            self.driver.close()

    def run_query(
        self,
        cypher: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        db = database or self.database
        with self.driver.session(database=db) as session:
            result = session.run(cypher, parameters or {})
            return [r.data() for r in result]

    def check_connection(self) -> bool:
        try:
            records = self.run_query("RETURN 1 AS ok LIMIT 1")
            ok = bool(records and records[0].get("ok") == 1)
            if ok:
                print(f"[neo4j] connected — database: {self.database}")
            else:
                print("[neo4j] connection check returned unexpected result")
            return ok
        except Exception as exc:
            print(f"[neo4j] connection failed: {exc}")
            return False


neo4j_service = Neo4jService()
