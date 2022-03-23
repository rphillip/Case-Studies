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
class toTensor(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        return self
    def transform(self, X):
        return torch.FloatTensor(X)
class MyModule(nn.Module):
    def __init__(self, num_units=128, dropoutrate = 0.5):
        super(MyModule, self).__init__()
        self.dropoutrate = dropoutrate
        self.layer1 = nn.Linear(23, num_units)
        self.nonlin = nn.ReLU()
        self.dropout1 = nn.Dropout(self.dropoutrate)
        self.dropout2 = nn.Dropout(self.dropoutrate)
        self.layer2 = nn.Linear(num_units, num_units)
        self.output = nn.Linear(num_units,1)
        self.batchnorm1 = nn.BatchNorm1d(128)
        self.batchnorm2 = nn.BatchNorm1d(128)

    def forward(self, X, **kwargs):
        X = self.nonlin(self.layer1(X))
        X = self.batchnorm1(X)
        X = self.dropout1(X)
        X = self.nonlin(self.layer2(X))
        X = self.batchnorm2(X)
        X = self.dropout2(X)
        X = self.output(X)
        return X
