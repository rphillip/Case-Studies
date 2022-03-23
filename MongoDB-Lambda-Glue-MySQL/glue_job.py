from pyspark import SparkContext
import sys
from awsglue.context import GlueContext
from awsglue.utils import getResolvedOptions
from awsglue.dynamicframe import DynamicFrame
from pyspark.sql.types import *
from pyspark.sql.functions import lit, last, udf, explode, col, split
from pyspark.sql import functions as F
from functools import reduce
from awsglue.job import Job
import json
import boto3
import re
import pymysql
#list of stopwords to exclude
stopwords = (set(["","a","as","able","about","above","according","accordingly","across","actually","after","afterwards","again","against","aint",
"all","allow","allows","almost","alone","along","already","also","although","always","am","among","amongst","an","and","another","any",
"anybody","anyhow","anyone","anything","anyway","anyways","anywhere","apart","appear","appreciate","appropriate","are","arent","around",
"as","aside","ask","asking","associated","at","available","away","awfully","b","be","became","because","become","becomes","becoming",
"been","before","beforehand","behind","being","believe","below","beside","besides","best","better","between","beyond","both","brief",
"but","by","c","cmon","cs","came","can","cant","cannot","cant","cause","causes","certain","certainly","changes","clearly","co","com",
"come","comes","concerning","consequently","consider","considering","contain","containing","contains","corresponding","could","couldnt",
"course","currently","d","definitely","described","despite","did","didnt","different","do","does","doesnt","doing","dont","done","down",
"downwards","during","e","each","edu","eg","eight","either","else","elsewhere","enough","entirely","especially","et","etc","even","ever",
"every","everybody","everyone","everything","everywhere","ex","exactly","example","except","f","far","few","fifth","first","five","followed",
"following","follows","for","former","formerly","forth","four","from","further","furthermore","g","get","gets","getting","given","gives",
"go","goes","going","gone","got","gotten","greetings","h","had","hadnt","happens","hardly","has","hasnt","have","havent","having","he",
"hes","hello","help","hence","her","here","heres","hereafter","hereby","herein","hereupon","hers","herself","hi","him","himself","his",
"hither","hopefully","how","howbeit","however","i","id","ill","im","ive","ie","if","ignored","immediate","in","inasmuch","inc","indeed",
"indicate","indicated","indicates","inner","insofar","instead","into","inward","is","isnt","it","itd","itll","its","its","itself","j",
"just","k","keep","keeps","kept","know","known","knows","l","last","lately","later","latter","latterly","least","less","lest","let","lets",
"like","liked","likely","little","look","looking","looks","ltd","m","mainly","many","may","maybe","me","mean","meanwhile","merely","might",
"more","moreover","most","mostly","much","must","my","myself","n","name","namely","nd","near","nearly","necessary","need","needs","neither",
"never","nevertheless","new","next","nine","no","nobody","non","none","noone","nor","normally","not","nothing","novel","now","nowhere","o",
"obviously","of","off","often","oh","ok","okay","old","on","once","one","ones","only","onto","or","other","others","otherwise","ought","our",
"ours","ourselves","out","outside","over","overall","own","p","particular","particularly","per","perhaps","placed","please","plus","possible",
"presumably","probably","provides","q","que","quite","qv","r","rather","rd","re","really","reasonably","regarding","regardless","regards",
"relatively","respectively","right","s","said","same","saw","say","saying","says","second","secondly","see","seeing","seem","seemed","seeming",
"seems","seen","self","selves","sensible","sent","serious","seriously","seven","several","shall","she","should","shouldnt","since","six","so",
"some","somebody","somehow","someone","something","sometime","sometimes","somewhat","somewhere","soon","sorry","specified","specify","specifying",
"still","sub","such","sup","sure","t","ts","take","taken","tell","tends","th","than","thank","thanks","thanx","that","thats","thats","the",
"their","theirs","them","themselves","then","thence","there","theres","thereafter","thereby","therefore","therein","theres","thereupon",
"these","they","theyd","theyll","theyre","theyve","think","third","this","thorough","thoroughly","those","though","three","through",
"throughout","thru","thus","to","together","too","took","toward","towards","tried","tries","truly","try","trying","twice","two","u","un",
"under","unfortunately","unless","unlikely","until","unto","up","upon","us","use","used","useful","uses","using","usually","uucp","v",
"value","various","very","via","viz","vs","w","want","wants","was","wasnt","way","we","wed","well","were","weve","welcome","well",
"went","were","werent","what","whats","whatever","when","whence","whenever","where","wheres","whereafter","whereas","whereby","wherein",
"whereupon","wherever","whether","which","while","whither","who","whos","whoever","whole","whom","whose","why","will","willing","wish",
"with","within","without","wont","wonder","would","wouldnt","x","y","yes","yet","you","youd","youll","youre","youve","your","yours",
"yourself","yourselves","youll","z","zero"]))
#list of flatten fields to look for
flatfields = {('accountAge', IntegerType(), True),
    ('age', IntegerType(), True),
    ('activity.action.type', StringType(), True),
    ('name', StringType(), True),
    ('content.comments', IntegerType(), True),
    ('content.title', StringType(), True),
    ('content.company.currentSubscribers', IntegerType(), True),
    ('member_id', StringType(), True),
    ('content.likes', IntegerType(), True),
    ('content.status', StringType(), True),
    ('content.views', IntegerType(), True),
    ('content.company.yearFounded', StringType(), True),
    ('subscribedTo', IntegerType(), True),
    ('content.company.name', StringType(), True),
    ('content.company.lastYearSubscribers', IntegerType(), True),
    ('activity.action.enabled', BooleanType(), True),
    ('activity.action.action_id', IntegerType(), True),
    ('id_tags.content_id', IntegerType(), True),
    ('activity.hotClickZone', BooleanType(), True),
    ('content.company.lastYearsRevenue', DoubleType(), True),
    ('id_tags.activity_id', IntegerType(), True)}
#list of mappings to rename flatten JSON file columns
mapping = [('`activity.action.action_id`', 'int', 'action_id', 'int'),
    ('`activity.action.enabled`', 'boolean', 'enabled', 'boolean'),
    ('`activity.action.type`', 'string','type', 'string'),
    ('`activity.hotClickZone`', 'boolean','hotClickZone', 'boolean'),
    ('`content.comments`', 'int','comments', 'int'),
    ('`content.company.currentSubscribers`', 'int','currentSubscribers', 'int'),
    ('`content.company.lastYearSubscribers`', 'int','lastYearSubscribers', 'int'),
    ('`content.company.lastYearsRevenue`', 'double','lastYearsRevenue', 'double'),
    ('`content.company.name`', 'string','company', 'string'),
    ('`content.company.yearFounded`', 'string','yearFounded', 'string'),
    ('`content.likes`', 'int', 'likes', 'int'),
    ('`content.status`', 'string', 'status', 'string'),
    ('`content.title`', 'string', 'title', 'string'),
    ('`content.views`', 'int', 'views', 'int'),
    ('`id_tags.activity_id`', 'int','activity_id', 'int'),
    ('`id_tags.content_id`', 'int','content_id', 'int'),
    ('accountAge', 'int','accountAge', 'int'),
    ('age', 'int', 'age', 'int'),
    ('member_id', 'string', 'member_id', 'int'),
    ('name', 'string', 'name', 'string'),
    ('subscribedTo', 'int', 'subscribedTo', 'int')
]
#we remove stopwords from title and return list of words (topics)
def removeStopwords(s):
    resultwords  = [word.lower() for word in re.split("\W+",s) if word.lower() not in stopwords]
    out = ' '.join(resultwords)
    return out
#we flatten the JSON file to remove nested structures and return it as dynamicframe
def flattenJSON(df, glueContext):
    #flattens df
    df.show()
    dfr = df.relationalize("root",tempdir)
    dfflat = dfr.select("root").toDF()
    inputfields = set((f.name, f.dataType, f.nullable) for f in dfflat.schema)
    #we fill in missing fields with null
    for l_name, l_type, l_nullable in flatfields.symmetric_difference(inputfields):
        #if column is wrong type
        if l_name in dfflat.columns:
            dfflat = dfflat.withColumn(l_name,col(l_name).cast(l_type))
        #if column is missing
        else:
            dfflat = dfflat.withColumn(l_name, lit(None).cast(l_type))
    df_out = DynamicFrame.fromDF(dfflat, glueContext, "flatten JSON transform")
    df1 = df_out.apply_mapping(mapping)
    return df1
#retrieves records from dataframe that has a null values in one of the fields
def getNulls(df):
    cols = [F.col(c) for c in df.columns]
    filter_expr = reduce(lambda a, b: a | b.isNull(), cols[1:], cols[0].isNull())
    return df.filter(filter_expr)
#remove duplicates from members by taking the last non null value (fills null if all values null)
def remDupMembers(df):
    out = (df.groupBy('id').agg(last('name',ignorenulls=True), last('age',ignorenulls=True),
        last('accountAge',ignorenulls=True), last('subscribedTo',ignorenulls=True), last('content_id',ignorenulls=True),
        last('activity_id',ignorenulls=True),last('restricted_user_access',ignorenulls=True)))
    oldcols = out.schema.names
    newcols = ['id','name','age','accountAge','subscribedTo','content_id','activity_id','restricted_user_access']
    out = reduce(lambda data, idx: data.withColumnRenamed(oldcols[idx],newcols[idx]), range(len(oldcols)), out)
    return out
#we merge the members table from sql with the input JSON file
def mergeMembers(input, members, glueContext):
    #merges frames, input frame overwrites existing record
    #removes id if null
    inputdf = input.toDF()
    inputdf = inputdf.withColumn('restricted_user_access', inputdf.age < 18).na.drop(subset=['id'])
    inputdf = remDupMembers(inputdf)
    membersdf = members.toDF()
    #here we fill in the nulls by retreiving the records with null values,then grouping/aggregating wiht the last function
    a=getNulls(inputdf)
    b= getNulls(membersdf)
    c = remDupMembers(a.union(b))
    #creates a clean input to merge into members
    filledin = DynamicFrame.fromDF(c,glueContext,"input filled in nulls")
    origin = DynamicFrame.fromDF(inputdf,glueContext,"original input")
    mergedinput = origin.mergeDynamicFrame(filledin,['id'])

    #we merge the clean input data to the members table
    #duplicates are overwritten (last one kept)
    merged = members.mergeDynamicFrame(mergedinput,['id'])
    return merged
#remove duplicates from content by taking the last non null value (fills null if all values null)
def remDupContent(df):
    out = (df.groupBy('id').agg(last('title',ignorenulls=True), last('company',ignorenulls=True),
        last('likes',ignorenulls=True), last('status',ignorenulls=True), last('views',ignorenulls=True),
        last('comments',ignorenulls=True)))
    oldcols = out.schema.names
    newcols = ['id','title','company','likes','status','views','comments']
    out = reduce(lambda data, idx: data.withColumnRenamed(oldcols[idx],newcols[idx]), range(len(oldcols)), out)
    return out
#we merge the content table from sql with the input JSON file
def mergeContent(input, content, glueContext):
    #merges frames, input frame overwrites existing record
    inputdf = input.toDF()
    inputdf = inputdf.na.drop(subset=['id'])
    inputdf = remDupContent(inputdf)
    contentdf = content.toDF()

    #here we fill in the nulls by retreiving the records with null values,then grouping/aggregating wiht the last function
    a=getNulls(inputdf)
    b= getNulls(contentdf)
    c = remDupContent(a.union(b))
    #creates a clean input to merge into content
    filledin = DynamicFrame.fromDF(c,glueContext,"input filled in nulls")
    origin = DynamicFrame.fromDF(inputdf,glueContext,"original input")
    mergedinput = origin.mergeDynamicFrame(filledin,['id'])

    #we merge the clean input data to the content table
    merged = content.mergeDynamicFrame(mergedinput,['id'])
    return merged
#remove duplicates from company by taking the last non null value (fills null if all values null)
def remDupCompany(df):
    out = (df.groupBy('company').agg(last('yearFounded',ignorenulls=True), last('currentSubscribers',ignorenulls=True),
        last('lastYearSubscribers',ignorenulls=True), last('lastYearsRevenue',ignorenulls=True), last('revenue_per_subscriber',ignorenulls=True)))
    oldcols = out.schema.names
    newcols = ['company','yearFounded','currentSubscribers','lastYearSubscribers','lastYearsRevenue','revenue_per_subscriber']
    out = reduce(lambda data, idx: data.withColumnRenamed(oldcols[idx],newcols[idx]), range(len(oldcols)), out)
    return out
#we merge the company table from sql with the input JSON file
def mergeCompany(input, company, glueContext):
    #merges frames, input frame overwrites existing record
    inputdf = input.toDF()
    inputdf = inputdf.na.drop(subset=['company'])\
        .withColumn('revenue_per_subscriber', (F.col('lastYearsRevenue')/F.col('lastYearSubscribers')))\
        .withColumn('yearFounded', F.col('yearFounded').cast(IntegerType()))
    inputdf = remDupCompany(inputdf)
    companydf = company.toDF()

    #here we fill in the nulls by retreiving the records with null values,then grouping/aggregating wiht the last function
    a=getNulls(inputdf)
    b= getNulls(companydf)
    c = remDupCompany(a.union(b))
    #creates a clean input to merge into company
    filledin = DynamicFrame.fromDF(c,glueContext,"input filled in nulls")
    origin = DynamicFrame.fromDF(inputdf,glueContext,"original input")
    mergedinput = origin.mergeDynamicFrame(filledin,['company'])

    #we merge the clean input data to the company table
    merged = company.mergeDynamicFrame(mergedinput,['company'])
    return merged
#remove duplicates from activity by taking the last non null value (fills null if all values null)
def remDupActivity(df):
    out = (df.groupBy('id').agg(last('action_id',ignorenulls=True), last('hotClickZone',ignorenulls=True)))
    oldcols = out.schema.names
    newcols = ['id','action_id','hotClickZone']
    out = reduce(lambda data, idx: data.withColumnRenamed(oldcols[idx],newcols[idx]), range(len(oldcols)), out)
    return out
#we merge the activity table from sql with the input JSON file
def mergeActivity(input, activity, glueContext):
    #merges frames, input frame overwrites existing record
    inputdf = input.toDF()
    inputdf = inputdf.na.drop(subset=['id'])
    inputdf = remDupActivity(inputdf)
    activitydf = activity.toDF()

    #here we fill in the nulls by retreiving the records with null values,then grouping/aggregating wiht the last function
    a=getNulls(inputdf)
    b= getNulls(activitydf)
    c = remDupActivity(a.union(b))
    #creates a clean input to merge into activity
    filledin = DynamicFrame.fromDF(c,glueContext,"input filled in nulls")
    origin = DynamicFrame.fromDF(inputdf,glueContext,"original input")
    mergedinput = origin.mergeDynamicFrame(filledin,['id'])

    #we merge the clean input data to the activity table
    merged = activity.mergeDynamicFrame(mergedinput,['id'])
    return merged
#remove duplicates from action by taking the last non null value (fills null if all values null)
def remDupAction(df):
    out = (df.groupBy('id').agg(last('type',ignorenulls=True), last('enabled',ignorenulls=True)))
    oldcols = out.schema.names
    newcols = ['id','type','enabled']
    out = reduce(lambda data, idx: data.withColumnRenamed(oldcols[idx],newcols[idx]), range(len(oldcols)), out)
    return out
#we merge the action table from sql with the input JSON file
def mergeAction(input, action, glueContext):
    #merges frames, input frame overwrites existing record
    inputdf = input.toDF()
    inputdf = inputdf.na.drop(subset=['id'])
    inputdf = remDupAction(inputdf)
    actiondf = action.toDF()

    #here we fill in the nulls by retreiving the records with null values,then grouping/aggregating wiht the last function
    a=getNulls(inputdf)
    b= getNulls(actiondf)
    c = remDupAction(a.union(b))
    #creates a clean input to merge into action
    filledin = DynamicFrame.fromDF(c,glueContext,"input filled in nulls")
    origin = DynamicFrame.fromDF(inputdf,glueContext,"original input")
    mergedinput = origin.mergeDynamicFrame(filledin,['id'])

    #we merge the clean input data to the action table
    merged = action.mergeDynamicFrame(mergedinput,['id'])
    return merged
#we merge the topics sql table to the derived input topics and remove duplicate topics
def mergeTopics(input, topics, glueContext):
    #remove nulls
    inputdf = input.toDF().select('title')
    inputdf = inputdf.na.drop(subset=['title'])
    #remove stopwords to get topic keywords
    gettopics_udf = udf(removeStopwords)
    inputdf1 = (inputdf.withColumn('keyword',gettopics_udf('title')).select(explode(split('keyword'," ")))
                        .withColumnRenamed('col','keyword'))
    topicsdf =topics.toDF()
    #remove duplicates by getting distinct keywords
    mergeddf = inputdf1.union(topicsdf).select('keyword').distinct()

    return DynamicFrame.fromDF(mergeddf,glueContext,"tasks keywords")
#we write dataframe to sql database
def writeDF(df, tablename):

    df.toDF().write.format("jdbc").option("url", "jdbc:mysql://tdicourse.clkrvvajsy5p.us-east-1.rds.amazonaws.com:3306/tdicourse") \
        .option("driver", "com.mysql.jdbc.Driver").option("dbtable", f"{tablename}") \
        .option("user", "tdirs").option("password", "tdirs123").mode("overwrite").save()
    return

tempdir = "s3://tdiminirs/temp/"

# adds misssing fields with null
session = boto3.session.Session(
    aws_access_key_id='AKIAXHBVJSDD6OW3WZB6',
    aws_secret_access_key='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',
    region_name='us-east-1'
)

args = getResolvedOptions(sys.argv, ["JOB_NAME"])
sc = SparkContext()
gc = GlueContext(sc)
spark = gc.spark_session
spark = spark.builder.config("spark.jars", "s3://tdiminirs/jdbc/mysql-connector-java-8.0.28.jar") \
    .master("local").appName("PySpark_MySQL_test").getOrCreate()
job = Job(gc)
job.init(args["JOB_NAME"], args)

#we retrive the input data from the s3 rds/ folder
AmazonS3= gc.create_dynamic_frame.from_options(
    format_options={"multiline": False},
    connection_type="s3",
    format="json",
    connection_options={"paths": ["s3://tdiminirs/rds/"], "recurse": True},
    transformation_ctx="AmazonS3",
)

s3_resource = session.resource('s3')
mybucketlist = s3_resource.Bucket('tdiminirs').objects.filter(Prefix="rds/", Delimiter='/')

#we process the jason files and flatten them to create the input tables
flatjson = flattenJSON(AmazonS3, gc)
flatjson.show()
members = flatjson.select_fields(['member_id','name','age','accountAge','subscribedTo', 'content_id', 'activity_id']).rename_field('member_id','id')
content = flatjson.select_fields(['content_id', 'title','company','upvotes','likes','status','views','comments']).rename_field('content_id','id')
company = flatjson.select_fields(['company','yearFounded','currentSubscribers','lastYearSubscribers','lastYearsRevenue'])
activity = flatjson.select_fields(['activity_id','action_id','hotClickZone']).rename_field('activity_id','id')
action = flatjson.select_fields(['action_id','type','enabled']).rename_field('action_id','id')

#we retrieve the tables from the sql database
memberssql = gc.create_dynamic_frame.from_catalog(
    database="tdicourse",
    table_name="tdicourse_members",
    transformation_ctx="memberssql",
)
contentsql =  gc.create_dynamic_frame.from_catalog(
    database="tdicourse",
    table_name="tdicourse_content",
    transformation_ctx="contentsql",
)
companysql =  gc.create_dynamic_frame.from_catalog(
    database="tdicourse",
    table_name="tdicourse_company",
    transformation_ctx="companysql",
)
activitysql =  gc.create_dynamic_frame.from_catalog(
    database="tdicourse",
    table_name="tdicourse_activity",
    transformation_ctx="activitysql",
)
actionsql =  gc.create_dynamic_frame.from_catalog(
    database="tdicourse",
    table_name="tdicourse_action",
    transformation_ctx="actionsql",
)
topicssql =  gc.create_dynamic_frame.from_catalog(
    database="tdicourse",
    table_name="tdicourse_topics",
    transformation_ctx="topicssql",
)

#we merge the input tables with the read sql tables
newmembers = mergeMembers(members, memberssql,gc)
newmembers.show()
newcontent = mergeContent(content,contentsql,gc)
newcontent.show()
newcompany = mergeCompany(company,companysql,gc)
newcompany.show()
newactivity = mergeActivity(activity,activitysql,gc)
newactivity.show()
newaction = mergeAction(action,actionsql,gc)
newaction.show()
newtopics = mergeTopics(newcontent, topicssql,gc)
newtopics.show()
#we write the new tables to the sql database
writeDF(newtopics, "topics")
writeDF(newaction, "action")
writeDF(newactivity, "activity")
writeDF(newcompany, "company")
writeDF(newcontent, "content")
writeDF(newmembers, "members")

#we delete the rds files
for bucket_object in mybucketlist:
    file = bucket_object
    file.delete()

job.commit()
