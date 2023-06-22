import sys
import json
import logging

from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector

from config import DB_URI, LOG_LEVEL, LOG_TO_FILE

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL.upper())
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)

if LOG_TO_FILE:
    logger.debug("Logging to file...")
    handler = logging.FileHandler("bot.log")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class DB:
    def __init__(self):
        self.memory_table_name = "memory"
        self.config_table_name = "config"
        self.memory_dimension = 1536
        self.pool = ConnectionPool(DB_URI)
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                logger.debug("DB: Setting up DB...")
                cur.execute(f"CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute(
                    f"CREATE TABLE IF NOT EXISTS {self.memory_table_name} (id bigserial PRIMARY KEY, embedding vector({self.memory_dimension}), metadata JSONB);"
                )
                cur.execute(
                    f"CREATE TABLE IF NOT EXISTS {self.config_table_name} (id int PRIMARY KEY, key varchar(255), value varchar(255));"
                )
            conn.commit()
    
    def get_config(self, key):
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                logger.debug("DB: Getting config...")
                cur.execute(f"SELECT value FROM {self.config_table_name} WHERE key = %s;", (key,))
                result = cur.fetchone()
                if result:
                    return result[0]
                else:
                    return None
    
    def set_config(self, key, value):
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                logger.debug("DB: Setting config...")
                cur.execute(f"INSERT INTO {self.config_table_name} (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = %s;", (key, value, value))
            conn.commit()
    
    def insert_memory(self, embedding, metadata):
        metadata = json.dumps(metadata, default=str)
        with self.pool.connection() as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                logger.debug("DB: Inserting memory...")
                cur.execute(
                    f"INSERT INTO {self.memory_table_name} (embedding, metadata) VALUES (%s, %s);",
                    (embedding, metadata),
                )
            conn.commit()
    
    def recall_memory(self, vector, n=100):
        with self.pool.connection() as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                logger.debug("DB: Recalling memory...")
                cur.execute(
                    f"""
                    SELECT
                        id,
                        embedding,
                        metadata,
                        1 - (embedding <-> CAST(%s AS vector)) AS score
                    FROM {self.memory_table_name}
                    ORDER BY embedding <-> CAST(%s AS vector) LIMIT %s;
                """,
                    (vector, vector, n),
                )
                rows = cur.fetchall()
        message_response_pairs = []
        for row in rows:
            message_response_pairs.append(
                {"id": row[0], "embedding": row[1], "metadata": row[2], "score": row[3]}
            )
        return message_response_pairs