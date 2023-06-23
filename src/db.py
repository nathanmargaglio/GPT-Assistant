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
        self.memory_dimension = 1536
        self.config_pool = ConnectionPool(DB_URI + "/config")
        self.bot_pools = {}
        self.setup_config_database()
        self.bot_configs = self.get_bot_configs()
        for bot_name in self.bot_configs:
            self.bot_pools[bot_name] = ConnectionPool(DB_URI + f"/{bot_name}")
            self.setup_bot_database(bot_name)

    def reinitialize(self):
        self.__init__()

    def setup_config_database(self):
        with self.config_pool.connection() as conn:
            with conn.cursor() as cur:
                logger.debug("DB: Setting up config database...")
                cur.execute(
                    f"CREATE TABLE IF NOT EXISTS bot (id int PRIMARY KEY, name varchar(255), config JSONB);"
                )
            conn.commit()

    def setup_bot_database(self, name):
        pool = self.bot_pools[name]
        with pool.connection() as conn:
            with conn.cursor() as cur:
                logger.debug(f"DB: Setting up bot '{name}' database...")
                cur.execute(f"CREATE EXTENSION IF NOT EXISTS vector;")
                cur.execute(
                    f"CREATE TABLE IF NOT EXISTS memory (id bigserial PRIMARY KEY, embedding vector({self.memory_dimension}), metadata JSONB);"
                )
            conn.commit()

    def get_bot_configs(self):
        with self.config_pool.connection() as conn:
            with conn.cursor() as cur:
                logger.debug("DB: Getting config...")
                cur.execute(f"SELECT id, name, config FROM bot;")
                results = cur.fetchall()
        configs = {}
        for result in results:
            configs[result[1]] = result[2]
        self.bot_configs = configs
        return configs

    def set_config(self, name, config):
        config = json.dumps(config, default=str)
        with self.config_pool.connection() as conn:
            with conn.cursor() as cur:
                logger.debug(f"DB: Setting config for {name}...")
                logger.debug(f"DB: config: {config}")
                cur.execute(
                    f"UPDATE bot SET config = %s WHERE name = %s;",
                    (config, name),
                )
            conn.commit()

    def insert_config(self, name, config):
        config = json.dumps(config, default=str)
        with self.config_pool.connection() as conn:
            with conn.cursor() as cur:
                logger.debug(f"DB: Inserting config for {name}...")
                cur.execute(
                    f"INSERT INTO bot (name, config) VALUES (%s, %s);",
                    (name, config),
                )
            conn.commit()

    def insert_memory(self, name, embedding, metadata):
        pool = self.bot_pools[name]
        metadata = json.dumps(metadata, default=str)
        with pool.connection() as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                logger.debug(f"DB: Inserting memory for {name}...")
                cur.execute(
                    f"INSERT INTO memory (embedding, metadata) VALUES (%s, %s);",
                    (embedding, metadata),
                )
            conn.commit()

    def recall_memory(self, name, vector, n=100):
        pool = self.bot_pools[name]
        with pool.connection() as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                logger.debug(f"DB: Recalling memory for {name}...")
                cur.execute(
                    f"""
                    SELECT
                        id,
                        embedding,
                        metadata,
                        1 - (embedding <-> CAST(%s AS vector)) AS score
                    FROM memory
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
