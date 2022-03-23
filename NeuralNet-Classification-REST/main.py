from fastapi import FastAPI, Query, Request
import uvicorn
import skorch
import pickle
from skorch import NeuralNetBinaryClassifier
import torch
import torch.nn as nn
import numpy as np
import pandas as pd
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import joblib
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, classification_report
from sklearn.pipeline import Pipeline
from sklearn.base import TransformerMixin, BaseEstimator
from pydantic import BaseModel
from classes import MyModule

model = NeuralNetBinaryClassifier(
    MyModule(dropoutrate = 0.2),
    max_epochs=40,
    lr=0.01,
    batch_size=128,
    # Shuffle training data on each epoch
    iterator_train__shuffle=True,
)
class Item(BaseModel):
    LIMIT_BAL: int
    SEX: int
    EDUCATION: int = None
    MARRIAGE: int
    AGE: int
    PAY_0: int
    PAY_2: int
    PAY_3: int
    PAY_4: int
    PAY_5: int
    PAY_6: int
    BILL_AMT1: int
    BILL_AMT2: int
    BILL_AMT3: int
    BILL_AMT4: int
    BILL_AMT5: int
    BILL_AMT6: int
    PAY_AMT1: int
    PAY_AMT2: int
    PAY_AMT3: int
    PAY_AMT4: int
    PAY_AMT5: int
    PAY_AMT6: int

class Items(BaseModel):
    itemlist: list
def willpredict(data):
    input = pd.DataFrame(data, index=[0])
    print(input)
    out = model1.predict(input)
    return out
with open('model1.pkl', 'rb') as f:
    model1 = joblib.load(f)

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}
@app.post('/predict')
async def predict(item: Item):

    out = willpredict(item.dict())
    print(out[0])
    return {
        "status" : "SUCCESS",
        "prediction" : int(out[0])
    }
@app.post('/predict')
