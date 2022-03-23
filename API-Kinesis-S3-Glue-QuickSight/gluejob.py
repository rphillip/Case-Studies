import sys
from pyspark.sql.types import *
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
import pyspark.sql.functions as F
from pyspark.sql.functions import col, size, split, lower
from pyspark.sql import DataFrame, Row
import datetime
from awsglue import DynamicFrame

args = getResolvedOptions(sys.argv, ["JOB_NAME"])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)



# read kinesis stream from data catalog
dataframe_KinesisStream_node1 = glueContext.create_data_frame.from_catalog(
    database="reddit",
    table_name="redditstream",
    additional_options={"startingPosition": "earliest", "inferSchema": "false"},
    transformation_ctx="dataframe_KinesisStream_node1",
)

def processBatch(data_frame, batchId):
    if data_frame.count() > 0:
        #add additional columns
        df1 = (data_frame.withColumn("length_title", F.length("title"))
            .withColumn("length_selftext", F.length("selftext"))
            .withColumn('python_mentions', F.size(F.split(F.lower(F.col("title")), r"python")) - 1 +
                F.size(F.split(F.lower(F.col("selftext")), r"python")) - 1)
            )
        KinesisStream_node1 = DynamicFrame.fromDF(
            df1, glueContext, "from_data_frame"
        )
        #apply corerct data types
        apply_mapping = ApplyMapping.apply(frame = KinesisStream_node1, mappings = [ \
            ("subreddit", "string", "subreddit", "string"), \
            ("title", "string", "title", "string"), \
            ("selftext", "string", "selftext", "string"), \
            ("upvote_ratio", "double", "upvote_ratio", "double"), \
            ("ups", "double", "ups", "integer"), \
            ("downs", "double", "downs", "integer"), \
            ("score", "double", "score", "integer"), \
            ("created_utc", "string", "screated_utc", "string"), \
            ("id", "string", "id", "string"), \
            ("kind", "string", "kind", "string"), \
            ("length_title", "integer", "length_title", "integer"), \
            ("length_selftext", "integer", "length_selftext", "integer"), \
            ("python_mentions", "integer", "python_mentions", "integer")],\
            transformation_ctx = "apply_mapping")
        df2 = apply_mapping.toDF()
        #add ingestion time to separate into s3 ingestion folders
        KinesisStream_node2 =(DynamicFrame.fromDF(
            glueContext.add_ingestion_time_columns(df2, "hour"),
            glueContext,
            "from_data_frame",)
            )

        S3bucket_node3_path = "s3://datalakeminirs/"
        #create Data sink
        S3bucket_node3 = glueContext.getSink(
            path=S3bucket_node3_path,
            connection_type="s3",
            updateBehavior="LOG",
            partitionKeys=["ingest_year", "ingest_month", "ingest_day", "ingest_hour"],
            enableUpdateCatalog=True,
            transformation_ctx="S3bucket_node3",
        )

        S3bucket_node3.setCatalogInfo(
            catalogDatabase="reddit", catalogTableName="output"
        )
        S3bucket_node3.setFormat("json")
        S3bucket_node3.writeFrame(KinesisStream_node2)


glueContext.forEachBatch(
    frame=dataframe_KinesisStream_node1,
    batch_function=processBatch,
    options={
        "windowSize": "100 seconds",
        "checkpointLocation": args["TempDir"] + "/" + args["JOB_NAME"] + "/checkpoint/",
    },
)
job.commit()
