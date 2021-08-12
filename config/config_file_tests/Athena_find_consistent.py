"""
 Steps
  1. Created a dictionary with keys as features and values as a list of identifiers (vocab:code).
    a) changing "NCIt" to "NCIT"
    b) changing "MeSH" to "MESH"
    c) changing "SNOMED" to "SCTID" and re-converting back after checking in node-normalizer
  2. Adding all the identifiers whose vocabs are in the expected list:
    allowedVocabs = ['ICD10', 'ICD10CM', 'ICD10CN', 'ICD10GM', 'ICD10PCS', 'ICD9CM', 'ICD9Proc', 'ICD9ProcCN', 'LOINC', 'RxNorm', 'RxNorm Extension']
  3. For the rest, running the check_valid function to check if identifiers (vocab:code) exists in Node-Normalizer and adding them in the dictionary.

"""

import yaml
import json
import requests
import csv
import numpy as np
import pandas as pd
import glob
import os
from collections import defaultdict

path = r'../Athena_data_v5/*.csv'
#dict = {}
dict = defaultdict(list)
#a = []
allowedVocabs = ['ICD10', 'ICD10CM', 'ICD10CN', 'ICD10GM', 'ICD10PCS', 'ICD9CM',
 'ICD9Proc', 'ICD9ProcCN', 'LOINC', 'RxNorm', 'RxNorm Extension']



def checkIdExits(ID):
    node_normalizer_url = "https://nodenormalization-sri.renci.org/1.1/get_normalized_nodes"
    id_exists = None
    input_obj = {
        "curies": [ID]
    }
    curl_cmd = f"curl -XPOST {node_normalizer_url} -H \"Content-Type: application/json\" -d '{json.dumps(input_obj)}'"

    resp = requests.post(node_normalizer_url, headers={
        "Content-Type": "application/json",
        "Accept": "applicaton/json"
    }, json=input_obj)

    obj = resp.json()
    for key, value in obj.items():
        id_exists = value
    return id_exists

def check_consistency(identifier):
   if checkIdExits(identifier):
      return True
   else:
      return False

for fname in glob.glob(path):
   feature = (os.path.splitext(os.path.basename(fname))[0])
   print(feature)
   consistent_id_df = pd.DataFrame([])
   df = pd.read_csv(fname, sep='\t')
   df['Vocab'].replace({"SNOMED": "SCTID"}, inplace=True)
   df['Vocab'].replace({"NCIt": "NCIT"}, inplace=True)
   df['Vocab'].replace({"MeSH": "MESH"}, inplace=True)
   df['Identifier'] = df['Vocab'].astype(str) + ":" + df['Code'].astype(str)
   #print(df)
   index_names = df['Vocab'].isin(allowedVocabs)
   consistent_id_df = consistent_id_df.append(df[index_names])
   notallowedvocabs_df = df[~index_names]
   for i, v in notallowedvocabs_df.iterrows():
       if check_consistency(v['Identifier'])==True:
           consistent_id_df = consistent_id_df.append(v)
   print(consistent_id_df)
   dict[feature] = consistent_id_df.groupby('Domain')['Identifier'].apply(list).to_dict()


#print(dict)
with open(r'consistent_FHIR_mapping.yml', 'w') as file:
    documents = yaml.dump(dict, file)

