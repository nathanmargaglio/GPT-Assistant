import json

from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector

from config import DB_URI, get_logger

logger = get_logger(__name__)

class DB:
    def __init__(self):
        self.disabled = DB_URI is None
        if self.disabled:
            logger.warning("DB: DB_URI is not set, disabling database...")
            return
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
                    f"""
                        CREATE TABLE IF NOT EXISTS memory (
                            id bigserial PRIMARY KEY,
                            partition varchar(255) DEFAULT null,
                            embedding vector({self.memory_dimension}),
                            metadata JSONB
                        );
                    """
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

    def insert_memory(self, name, embedding, metadata, partition=None):
        pool = self.bot_pools[name]
        metadata = json.dumps(metadata, default=str)
        with pool.connection() as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                logger.debug(f"DB: Inserting memory for {name}...")
                cur.execute(
                    f"INSERT INTO memory (embedding, metadata, partition) VALUES (%s, %s, %s);",
                    (embedding, metadata, partition),
                )
            conn.commit()

    def recall_memory(self, name, vector, n=100, partition=None):
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
                        1 - (embedding <-> CAST(%s AS vector)) AS score,
                        partition
                    FROM memory
                    WHERE partition = %s
                    ORDER BY embedding <-> CAST(%s AS vector) LIMIT %s;
                """,
                    (vector, partition, vector, n),
                )
                rows = cur.fetchall()
        message_response_pairs = []
        for row in rows:
            message_response_pairs.append(
                {"id": row[0], "embedding": row[1], "metadata": row[2], "score": row[3], "partition": row[4]}
            )
        return message_response_pairs
