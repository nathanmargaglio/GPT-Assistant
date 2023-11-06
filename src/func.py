import json
from lqs.client import Client
from config import get_logger

logger = get_logger(__name__)

class LogQS:
    def __init__(self):
        self.lqs = Client(
            api_url="https://logqs-cloud.com/lqs/92fda1fd-7c80-4f51-9df4-4ba6e7356afe/api",
            api_key_id="admin",
            api_key_secret="admin",
            retry_count=0,
        )
    
    def trim_data(self, data):
        fields_to_keep = [
            "data", "log", "topics", "count", "id", "name", "note", "type_name", "statement", "columns"
        ]
        rows = None
        if "rows" in data:
            rows = data["rows"]
        def trim_data(obj):
            if isinstance(obj, dict):
                for key in list(obj.keys()):
                    if key not in fields_to_keep:
                        del obj[key]
                    else:
                        trim_data(obj[key])
            elif isinstance(obj, list):
                for item in obj:
                    trim_data(item)
        trim_data(data)
        if rows is not None:
            data["rows"] = rows
    
    def fetch_log(self, log_id):
        log = self.lqs.fetch.log(log_id)["data"]
        topics = self.lqs.list.topics(log_id=log_id)["data"]
        return {
            "log": log,
            "topics": topics,
        }
    
    def query(self, log_id, statement):
        query = self.lqs.create.query(log_id=log_id, statement=statement)["data"]
        return query

    def call_function(self, function_name, **kwargs):
        logger.info(f"Calling function {function_name} with arguments {kwargs}")
        function = {
            "fetch_log": self.fetch_log,
            "list_logs": self.lqs.list.logs,
            "fetch_record_image": self.lqs.fetch.record_image,
            "query": self.query,
        }[function_name]
        results = function(**kwargs)
        if function_name == "fetch_record_image":
            return results # raw bytes
        self.trim_data(results)
        return json.dumps(results)

    def get_function_schemas(self):
        explain_description = """
            A brief description of why you're calling this function.  This will be displayed to the user.
            It should be written in a way which sounds like you're explaining your thought process to a human.  For example:
                - "I'm fetching the log with ID {log_id}."
                - "I'm querying to find where average speed of the vehicle."
                - "I'm fetching the image for the record with timestamp {timestamp} and topic ID {topic_id}."
        """
        return [
            {
                "name": "fetch_log",
                "description": "Fetch details for a log and it's topics.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "log_id": {
                            "type": ["string"],
                            "description": "The UUID of the log to fetch."
                        },
                        "explain": {
                            "type": ["string"],
                            "description": explain_description
                        }
                    },
                    "required": ["log_id", "explain"],
                }
            },
            {
                "name": "list_logs",
                "description": "List logs.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name_like": {
                            "type": ["string"],
                            "description": "The name of the log to fuzzy search for."
                        },
                        "limit": {
                            "type": ["integer"],
                            "default": 10,
                            "description": "The maximum number of logs to return."
                        },
                        "explain": {
                            "type": ["string"],
                            "description": explain_description
                        }
                    },
                    "required": ["explain"],
                }
            },
            {
                "name": "fetch_record_image",
                "description": """
                    Fetch an image for a record and display it. The record's topic's type must be sensor_msgs/Image.
                    The timestamp needs to come from a record from the correct topic, i.e., using the timestamp from
                    a record from a different topic will not work.
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic_id": {
                            "type": ["integer"],
                            "description": "The UUID of the Image topic to fetch an image for."
                        },
                        "timestamp": {
                            "type": ["integer"],
                            "description": "The timestamp of the record FROM THE IMAGE TOPIC to fetch an image for."
                        },
                        "explain": {
                            "type": ["string"],
                            "description": explain_description
                        }
                    },
                    "required": ["topic_id", "timestamp", "explain"],
                }
            },
            {
                "name": "query",
                "description": "Query record data from LogQS.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "log_id": {
                            "type": ["string"],
                            "description": "The UUID of the log from which to query records."
                        },
                        "statement": {
                            "type": ["string"],
                            "description": """
                            A PostgreSQL SELECT statement to query records from the log.
                            The statement must select only from the 'record' table.
                            Do not use wildcards in the SELECT clause.
                            The following columns appear in the table:
                                - topic_id      (UUID): The UUID of the topic to which the record belongs.
                                - timestamp   (bigint): The timestamp of the record in nanoeconds since the epoch.
                                - message_data (jsonb): The message data of the record.
                            The message data is a JSON object with fields corresponding to the ROS message of the topic.
                            For example, if the topic is a sensor_msgs/Imu, the message data will have the following fields:
                                - header:
                                    - seq (integer)
                                    - stamp:
                                        - secs (integer)
                                        - nsecs (integer)
                                    - frame_id (string)
                                - child_frame_id (string)
                                - pose:
                                    - pose:
                                        - position:
                                            - x (float)
                                            - y (float)
                                            - z (float)
                                        - orientation:
                                            - x (float)
                                            - y (float)
                                            - z (float)
                                            - w (float)
                                    - covariance (float[36])
                            ...and so on.
                            These can be queried using the PostgreSQL JSON operators.  For example:
                                SELECT * FROM record WHERE (message_data->'pose'->'pose'->'position'->>'x')::FLOAT > 0.0 LIMIT 10;
                            Be sure to explicitly cast the JSON values to the correct type.  Here are some operators:
                                jsonb -> integer → jsonb
                                jsonb -> text → jsonb
                                jsonb ->> integer → text
                                jsonb #> text[] → jsonb
                            Common table expressions (WITH), grouping (GROUP BY), and other advanced features are supported.
                            Responses are limited to 256KB payload limits, so be selective with your queries.
                            When applicable, it's a good idea to return the timestamp and topic_id columns
                            so that you can fetch the full record or it's image (if available) later.
                            When you query the record table, this will include records across all topics.  If you're looking
                            for records for a specific topic, be sure to include the topic_id in your WHERE clause.
                            If a user asks when something occurred, this should correspond to the timestamp of the record.
                            """
                        },
                        "explain": {
                            "type": ["string"],
                            "description": explain_description
                        }
                    },
                    "required": ["log_id", "explain"],
                }
            }
        ]