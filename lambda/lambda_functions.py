import json
import os
import urllib.parse

import awswrangler as wr
import boto3
import pandas as pd

print("Loading function")

TARGET_PATH: str = os.environ["TARGET_PATH"]
GLUE_DATABASE: str = os.environ["GLUE_DATABASE"]
GLUE_TABLE: str = os.environ["GLUE_TABLE"]

s3 = boto3.client("s3")

def trigger_handler(event, context):
    # print("Received event: " + json.dumps(event, indent=2))

    # Get the object from the event and show its content type
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(event["Records"][0]["s3"]["object"]["key"])
    try:
        print("Reading file with AWS Wrangler")
        s3_path: str = f"s3://{bucket}/{key}"
        print(s3_path)
        df = wr.s3.read_csv(path=s3_path, dataset=False)

        df["date_of_visits"] = pd.to_datetime(df["date_of_visits"])
        df["year"] = df["date_of_visits"].dt.year
        df["month"] = df["date_of_visits"].dt.month
        df["day"] = df["date_of_visits"].dt.day

        data_types = {
            "uuid": "string",
            "first_name": "string",
            "last_name": "string",
            "email_address": "string",
            "number_of_visits": "tinyint",
            "time_spent": "double",
            "amount_spent": "double",
            "date": "date"
        }
        partition_by = ["year", "month", "day"]

        response = wr.s3.to_parquet(
            df=df.copy(),
            path=TARGET_PATH,
            compression="snappy",
            index=False,
            dataset=True,
            mode="append",
            database=GLUE_DATABASE,
            table=GLUE_TABLE,
            dtype=data_types,
            partition_cols=partition_by
        )
        return {
            "status": 200,
            "body": f"{s3_path} loaded to parquet and saved to target bucket -> {TARGET_PATH}",
        }
    except Exception as e:
        print(e)
        print(
            "Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function".format(
                key, bucket
            )
        )
        raise e
