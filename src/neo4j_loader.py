import logging
from neo4j import GraphDatabase
from src.config import config

# 配置基础日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Neo4jLoader:
    def __init__(self):
        self.uri = config.neo4j_uri
        self.user = config.neo4j_user
        self.password = config.neo4j_password
        self.driver = None

    def connect(self):
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self.driver.verify_connectivity()
            logger.info("Successfully connected to Neo4j.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed.")

    def clear_database(self):
        """清空数据库中的所有节点和关系"""
        query = "MATCH (n) DETACH DELETE n"
        with self.driver.session(database=config.neo4j_db) as session:
            session.run(query)
        logger.info("Database cleared.")

    def create_constraints(self):
        """创建节点唯一性约束，防止后续导入时产生重复数据"""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Disease) REQUIRE d.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Medicine) REQUIRE m.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (i:Insurance) REQUIRE i.name IS UNIQUE"
        ]
        with self.driver.session(database=config.neo4j_db) as session:
            for query in constraints:
                session.run(query)
        logger.info("Constraints created successfully.")

if __name__ == "__main__":
    # 成员B 周验收验证：测试连通、清库与建约束
    loader = Neo4jLoader()
    try:
        loader.connect()
        loader.clear_database()
        loader.create_constraints()
    finally:
        loader.close()