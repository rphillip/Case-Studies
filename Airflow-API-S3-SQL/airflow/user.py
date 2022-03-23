import os
import time
import requests as r
import glob
import json
from datetime import datetime, timedelta
import pprint as pp

while True:
    response = r.get('http://user-ingredients.herokuapp.com/')
    json_data = response.json()
    filename = f'user-{datetime.now()}.json'
        # is there a better way then using datetime.now()? Yes -templating
    with open(filename, 'w') as json_file:
        json.dump(json_data, json_file)
    time.sleep(2)

print(glob.glob('user-*.json'))
