import yaml
import json
import requests
import csv
import pandas as pd

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
        writer = csv.writer(f, delimiter='\t', lineterminator='\n', )
        for table, feature in document.items():
            for feature_name, identifier_list in feature.items():
                for identifier in identifier_list:
                    if not checkIdExits(identifier):
                        print(identifier)
                        writer.writerow([identifier])

with open(r'identifiers.yml') as file:
    document = yaml.full_load(file)
identifiers = extract_identifiers(document)
check_inconsistency(identifiers)
