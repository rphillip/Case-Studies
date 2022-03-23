from datetime import datetime, timedelta
import time
import requests
import os
import json
import glob
import pandas as pd
import boto3
from os import listdir
from os.path import isfile, join
from airflow import DAG
from airflow.operators.bash_operator import BashOperator
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.amazon.aws.sensors.s3 import S3PrefixSensor
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.engine import Connection
import config
default_args = {
    'owner': 'airflow',
    'wait_for_downstream': True,
    'max_active_runs': 1,
    'depends_on_past': True, # determines execution based off previous DAGRun
}
BUCKET_NAME = "airflowrs"

"""
Here in getRecipe we:
Parameters = recipe: response data
1. make a output data frame with not nested columns
2. make an equipment dataframe from the nested column with recipe id as reference
3. make an indgredients dataframe from the nested column with recipe id as reference
4. join equipment and ingredients dataframe to output dataframe
5. return output dataframe
"""
def getRecipe(recipe):
    if recipe:
        recipelist = pd.DataFrame(recipe)
        recipeout = recipelist[['id','title','servings','summary','diets']]
        recipesteps = pd.DataFrame(recipelist[['id','analyzedInstructions']])

        #get equipment values
        recipesteps= recipesteps.explode('analyzedInstructions').dropna()
        recipesteps['analyzedInstructions'] = recipesteps['analyzedInstructions'].apply(lambda x: x['steps'])
        recipesteps= recipesteps.explode('analyzedInstructions').dropna()
        recipesteps['equipment']= recipesteps['analyzedInstructions'].apply(lambda x: x['equipment'])
        recipeequip = recipesteps[['id','equipment']].explode('equipment').dropna()
        recipeequip['equipment'] = recipeequip['equipment'].apply(lambda x: x['name'])
        recipeequip = recipeequip.groupby("id").agg(lambda x: set(x)).reset_index()
        recipeequip['equipment']= recipeequip['equipment'].apply(lambda x: list(x))

        #get ingredient values
        recipesteps['ingredients']= recipesteps['analyzedInstructions'].apply(lambda x: x['ingredients'])
        recipeingr = recipesteps[['id','ingredients']].explode('ingredients').dropna()
        recipeingr['ingredients']= recipeingr['ingredients'].apply(lambda x: x['name'])
        recipeingr = recipeingr.groupby("id").agg(lambda x: set(x)).reset_index()
        recipeingr['ingredients']= recipeingr['ingredients'].apply(lambda x: list(x))

        #create recipe dataframe
        recipeout = (recipeout.join(recipeequip.set_index("id"), on="id")
                            .join(recipeingr.set_index("id"), on="id"))
        return recipeout
    else:
        return None
"""
Here in upload_to_bucket we:
1. get the list of jsons from local disc
2. add data to stack to and check if duplicate
3. check if stack = 20 then we upload to raw/
4. restart stack to 0 and redo data add
5. delete uploaded raw files
"""
def upload_to_bucket():
    #get list of user files in directory
    filelist = glob.glob('user-*.json')
    stack = []
    stacklist = []
    stacklistadded = []
    s3_hook = S3Hook(aws_conn_id='aws_default')
    sent = False
    #uploads 20 at a time
    #checks if 20 are available to be sent
    while sent == False:
        for file in filelist:
            stacklist.append(file)
            f = open(file)
            data = json.load(f)
            #check for blanks
            if data not in stack:
                stack.append(data)
                stacklistadded.append(file)
            if len(stack) == 20:
                #send to s3 20 at a time
                for j in stacklistadded:
                    try:
                        s3_hook.load_file(
                            filename=j,
                            key=''.join(["raw/",j]),
                            bucket_name=BUCKET_NAME,
                        )
                    except Exception as e:
                        print(e)
                #delete files
                for j in stacklist:
                    os.remove(j)
                #reset stacks
                sent=True
                stack = []
                stacklist = []
                stacklistadded = []

"""
Here in get_recipes we:
1. get the list of keys from raw/
2. get the search parameters and call the spoonacular API
3. get the response from the API and add it to a recipe DataFrame
4. add the user info from the key to user Dataframe
5. upload the user dataframe and recipe dataframe to storage
6. Delete read keys from raw/
"""
def get_recipes():
    s3_hook = S3Hook(aws_conn_id='aws_default')
    base = 'https://api.spoonacular.com/recipes/complexSearch'
    recipeparams = {
    'apiKey': '6980d1ba951a438982534beaedb41e6f',
    'addRecipeInformation': True
    }
    columnsrecipe = ["id","title","servings","summary","diets","equipment", "ingredients"]
    dfrecipe = pd.DataFrame(columns=columnsrecipe)
    columnsuser = ["name","address","description","recipes"]
    dfusers  = pd.DataFrame(columns=columnsuser)
    #get the list of keys from raw/
    keylist = s3_hook.list_keys(bucket_name=BUCKET_NAME, prefix="raw/")
    jsons = []
    for key in keylist:
        object = s3_hook.get_key(bucket_name=BUCKET_NAME, key=key).get()['Body'].read().decode('utf-8')
        data = json.loads(object)
        #get the search parameters and call the spoonacular API
        if "includeIngredients" in data["pantry"].keys():
            recipeparams["includeIngredients"] = data["pantry"]["includeIngredients"]
        if "excludeIngredients" in data["pantry"].keys():
            recipeparams["excludeIngredients"] = data["pantry"]["excludeIngredients"]
        if "intolerances" in data["pantry"].keys():
            recipeparams["intolerances"] = data["pantry"]["intolerances"]
        response = requests.get(base, recipeparams)
        #get the response from the API and add it to a recipe DataFrame
        #check if recipes are returned
        if response.json()['results']:
            dfrecipe = pd.concat([dfrecipe, getRecipe(response.json()['results'])], ignore_index=True)
            dfrecipe = dfrecipe.drop_duplicates(subset=['id'], keep='last')
        #add the user info from the key to user Dataframe
        user = data['user']
        user['recipes'] = dfrecipe['id'].to_list()
        dfusers = pd.concat([dfusers,pd.DataFrame.from_dict(user)])
        dfusers = dfusers.drop_duplicates(subset=['name'], keep='last')
    #upload the user dataframe and recipe dataframe to stage
    userdata = bytes(json.dumps(dfusers.to_dict(orient="records")).encode('UTF-8'))
    try:
        file = 'user-{}.json'.format(datetime.now())
        s3_hook.load_bytes(
            bytes_data = userdata,
            key=''.join(["stage/",file]),
            bucket_name=BUCKET_NAME,
            replace=True,
        )
    except Exception as e:
        print(e)
    recipedata = bytes(json.dumps(dfrecipe.to_dict(orient="records")).encode('UTF-8'))
    try:
        file = 'recipe-{}.json'.format(datetime.now())
        s3_hook.load_bytes(
            bytes_data = recipedata,
            key=''.join(["stage/",file]),
            bucket_name=BUCKET_NAME,
            replace=True,
        )
    except Exception as e:
        print(e)
        #export user info to s3
    #Delete read keys from raw/
    s3_hook.delete_objects(
        bucket = BUCKET_NAME,
        keys=keylist
    )
"""
Here in to_sql we:
1. create a connection to the postgres server
2. get the recipes from stage/
3. get recipe table from postgres and add stage/ recipes then write to postgres
2. get the users from stage/
3. get users table from postgres and add stage/ users then write to postgres
5. close server connections and delete stage/ keys
"""
def to_sql():

    #create a connection to the postgres server
    path = "postgresql://{}:{}@{}:{}/{}".format(config.username,config.passwd,config.hostname,config.portnum,config.dbname)
    engine = create_engine(path)
    conn = engine.connect()
    s3_hook = S3Hook(aws_conn_id='aws_default')
    #get the recipes from stage/
    recipelist = s3_hook.list_keys(bucket_name=BUCKET_NAME, prefix="stage/recipe-")
    jsons = []
    for key in recipelist:
        object = s3_hook.get_key(bucket_name=BUCKET_NAME, key=key).get()['Body'].read().decode('utf-8')
        data = json.loads(object)
        jsons.extend(data)
    recipes = pd.DataFrame(jsons).drop_duplicates(subset=['id'], keep='last')
    print(recipes)
    #get recipe table from postgres and add stage/ recipes then write to postgres
    check=engine.has_table("recipe")
    if not check:
        recipes.to_sql('recipe',conn, if_exists='replace')
    else:
        columnsrecipe = ["id","title","servings","summary","diets","equipment", "ingredients"]
        recipesql = pd.read_sql_table("recipe",conn, columns=columnsrecipe)
        print(recipesql)
        out = pd.concat([recipesql,recipes]).drop_duplicates(subset=['id'], keep='last')
        out.to_sql('recipe',conn, if_exists='replace', index=False)
    #get the users from stage/
    userlist = s3_hook.list_keys(bucket_name=BUCKET_NAME, prefix="stage/user-")
    jsons = []
    for key in userlist:
        object = s3_hook.get_key(bucket_name=BUCKET_NAME, key=key).get()['Body'].read().decode('utf-8')
        data = json.loads(object)
        jsons.extend(data)
    users = pd.DataFrame(jsons).drop_duplicates(subset=['name'], keep='last')
    print(users)
    #get users table from postgres and add stage/ users then write to postgres
    check=engine.has_table("users")
    if not check:
        users.to_sql('users',conn, if_exists='replace')
    else:
        columnsuser = ["name","address","description","recipes"]
        usersql = pd.read_sql_table("users",conn,columns=columnsuser)
        print(usersql)
        out = pd.concat([usersql,users]).drop_duplicates(subset=['name'], keep='last')
        print(out)
        out.to_sql('users',conn, if_exists='replace', index=False)
    #close server connections and delete stage/ keys
    conn.close()
    engine.dispose()
    s3_hook.delete_objects(
        bucket = BUCKET_NAME,
        keys=userlist
    )
    s3_hook.delete_objects(
        bucket = BUCKET_NAME,
        keys=recipelist
    )

dag = DAG(
    dag_id='simple_dag',
    default_args=default_args,
    start_date=datetime.now(),
    end_date=datetime.now() + timedelta(minutes=5),
    #schedule_interval='@once',
    schedule_interval='*/1 * * * *', # every minute
    catchup=True # default
)

with dag:
    #upload to s3
    s3_raw = PythonOperator(
        task_id='upload_to_bucket',
        python_callable= upload_to_bucket,
    )
    #check if raw/ exists
    s3_sensor = S3PrefixSensor(
        task_id='s3_sensor',
        bucket_name=BUCKET_NAME,
        prefix ="raw/",
        aws_conn_id='aws_default',
    )
    #get recipes from raw/ and put data into stage, delete raw/ files
    s3_stage = PythonOperator(
        task_id='get_recipes',
        python_callable= get_recipes,
    )
    #check if stage/ exists
    s3_sensor2 = S3PrefixSensor(
        task_id='s3_sensor2',
        bucket_name=BUCKET_NAME,
        prefix ="stage/",
        aws_conn_id='aws_default',
    )
    #send data from stage/ to Postgresql server, delete stage/ files
    s3_sql = PythonOperator(
        task_id='to_sql',
        python_callable= to_sql,
    )

s3_raw >> s3_sensor  >> s3_stage >> s3_sensor2 >> s3_sql
#s3_sql
