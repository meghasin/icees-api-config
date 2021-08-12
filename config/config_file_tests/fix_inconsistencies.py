import yaml
import json
import requests
import csv
import pandas as pd
from tempfile import NamedTemporaryFile
import shutil


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
    # print(obj)
    for key, value in obj.items():
        id_exists = value
        # print(id_exists)
    return id_exists


def extract_identifiers(document):
    a = []
    for table, feature in document.items():
        for feature_name, identifier_list in feature.items():
            # print(table, ":", feature_name, ":", identifier_list)
            for identifier in identifier_list:
                a.append(identifier)
    print(len(a))
    a = pd.unique(a).tolist()
    print(len(a))
    return a

def check_inconsistency(identifiers):
    with open("inconsistencies.csv", 'w') as f:
        writer = csv.writer(f, lineterminator='\n')
        for item in identifiers:
            if not checkIdExits(item):
                print(item)
                writer.writerow([item])

def update_identifiers(document):
    b = []
    filename = 'inconsistencies.csv'
    with open(filename, 'r') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            row = str(row)[2:-2]
            b.append(row)
            print(row)
    #print(b)
    for table, feature in document.items():
        for feature_name, identifier_list in feature.items():
            #print(table, ":", feature_name, ":", identifier_list)
            for identifier in identifier_list:
                #print(identifier)
                if identifier in b:
                    #print(identifier)
                    identifier_list.remove(identifier)
    return document

with open(r'../identifiers.yml') as file:
    document = yaml.full_load(file)
#identifiers = extract_identifiers(document)
#check_inconsistency(identifiers)
d = update_identifiers(document)
with open(r'consistent_identifiers.yml', 'w') as file:
    documents = yaml.dump(d, file)
