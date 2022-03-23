import requests
import pandas as pd
from datetime import datetime
import mycredentials
import json
import time
import numpy as np
from kinesis_helper import KinesisStream
import uuid

# we use this function to convert responses to dataframes
def df_from_response(res):
    # initialize temp dataframe for batch of data in response
    df = pd.DataFrame()

    # loop through each post pulled from res and append to df
    for post in res.json()['data']['children']:
        df = df.append({
            'subreddit': post['data']['subreddit'],
            'title': post['data']['title'],
            'selftext': post['data']['selftext'],
            'upvote_ratio': post['data']['upvote_ratio'],
            'ups': post['data']['ups'],
            'downs': post['data']['downs'],
            'score': post['data']['score'],
            'created_utc': datetime.fromtimestamp(post['data']['created_utc']).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'id': post['data']['id'],
            'kind': post['kind']
        }, ignore_index=True)

    return df

# authenticate API
# authorization after creating reddit application
auth = requests.auth.HTTPBasicAuth(mycredentials.redditclient, mycredentials.redditsecret)

# provide information for access token
data = {
    'grant_type': 'password',
    'username': mycredentials.reddituser,
    'password': mycredentials.redditpass
}
headers = {
    'User-Agent': 'streamtest/0.0.1',
}

# send our request for access token
res = (requests.post('https://www.reddit.com/api/v1/access_token', auth=auth,
    headers=headers, data=data))
# convert response to JSON and pull 'access_token' value
TOKEN = res.json()['access_token']
# add authorization to header
headers = {**headers, **{'Authorization': f'bearer {TOKEN}'}}

# Token is valid for two hours - keep it that way
requests.get('https://oauth.reddit.com/api/v1/me', headers=headers)

# initialize dataframe and parameters for pulling data in loop
new_df = pd.DataFrame()
params = {'limit': 100}
stream = KinesisStream('redditstream')


# we stream the newests posts
while True:

    # make request
    res = requests.get("https://oauth.reddit.com/r/python/new",
                       headers=headers,
                       params=params)

    # get dataframe from response
    new_df = df_from_response(res)
    if not new_df.empty:
        # take the final row (newest entry)
        row = new_df.iloc[0]
        # create fullname
        fullname = row['kind'] + '_' + row['id']
        # add/update fullname in params
        #we use before to get newest submissions
        params['before'] = fullname
        new_df['Data'] = new_df.apply(lambda x: json.dumps(x.to_dict(), separators= (',',':')), axis=1)
        new_df['PartitionKey'] = [str(uuid.uuid4()) for _ in range(len(new_df.index))]
        datadf = new_df[['Data','PartitionKey']].to_dict(orient="records")
        result = stream.send_stream(data=datadf)
        print(datadf, result)
        #add sleep time to limit api calls and prevent timeouts
        time.sleep(1)
    #wait for new posts.
    else:
        time.sleep(10)
        print("waiting for new posts")
