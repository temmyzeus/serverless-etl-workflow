import json
import logging
import os
import urllib.parse
from enum import Enum
from typing import Any

import awswrangler as wr

logging.basicConfig(level=logging.INFO)

# TARGET_GLUE_DATABASE: str = os.environ["TARGET_GLUE_DATABASE"]
# TARGET_GLUE_TABLE: str = os.environ["TARGET_GLUE_TABLE"]
SUPPORTED_TYPES: set[str] = {".csv", ".json", ".xlsx"}
MAX_FILE_SIZE: int = 2097152000 # in bytes ... approx 2gb

class Target(Enum):
    TARGET_S3_BUCKET_PATH: str = os.environ["TARGET_S3_BUCKET_PATH"]
    # GLUE_DATABASE: str = os.environ["TARGET_GLUE_DATABASE"]
    # GLUE_TABLE: str = os.environ["TARGET_GLUE_TABLE"]


class FileTypeError(Exception):
    """Exception type for incorrect file type"""

    pass

class FileSizeError(Exception):
    """Exception type for unacceptable file size"""
    
    pass

def trigger_handler(event, context) -> Any:
    print("Event: ", json.dumps(event), "\n")
    print("Context: ", context)

    for (i, record) in enumerate(event["Records"], start=1):
        # Incase an unexpected error, so it doesn't stop the loop
        try:
            # Get the object from the event and show its content type
            body = json.loads(record["body"])
            bucket = body["Records"][0]["s3"]["bucket"]["name"]
            key = urllib.parse.unquote_plus(body["Records"][0]["s3"]["object"]["key"])
            filename_no_ext = os.path.splitext(os.path.basename(key))[0]
            file_type = os.path.splitext(key)[-1] or None
            file_size = body["Records"][0]["s3"]["object"]["size"]  # in what?? MB, Bytes??

            if file_type not in SUPPORTED_TYPES:
                raise FileTypeError(
                    f"Supported Types are: `{', '.join(SUPPORTED_TYPES)}`, not {file_type}"
                )

            # Max lambda ephemeral space is 512 mb, so let's 300 mb seems a reasonanle number
            if file_size > MAX_FILE_SIZE:
                raise FileSizeError(f"File size limit is {MAX_FILE_SIZE}, {file_type} is too large to process.")

            try:
                logging.info("Start reading %s file type from S3" % file_type)
                s3_path: str = os.path.join("s3://", bucket, key)
                logging.info("Reading data from %s" % s3_path)

                if file_type == ".csv":
                    df = wr.s3.read_csv(path=s3_path, dataset=False)
                elif file_type == ".json":
                    df = wr.s3.read_json(path=s3_path, dataset=False)
                elif file_type == ".xlsx":
                    df = wr.s3.read_excel(path=s3_path, dataset=False)
                logging.info("File read successfully")
            except Exception as e:
                logging.error(e)

            save_key = filename_no_ext + ".parquet"

            try:
                response = wr.s3.to_parquet(
                    df=df.copy(),
                    path=os.path.join(Target.TARGET_S3_BUCKET_PATH.value, save_key),
                    index=False,
                    compression="snappy",
                    dataset=False,
                )
            except Exception as e:
                logging.error(e)

            response_msg = {
                "status": 200,
                "body": f"{key} converted to parquet and loaded to parquet as {save_key} and saved to bucket:{Target.TARGET_S3_BUCKET_PATH.value}",
            }
        except Exception as e:
            logging.error(e)
