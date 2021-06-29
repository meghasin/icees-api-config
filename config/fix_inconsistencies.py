import yaml
import json
import requests
import csv

def checkIdExits(ID):
    NODE_NORMALIZER_QUERY_URL = "https://nodenormalization-sri.renci.org/1.1/get_normalized_nodes"
    idExists = None
    input_obj = {
        "curies": [ID]
    }
    curl_cmd = f"curl -XPOST {NODE_NORMALIZER_QUERY_URL} -H \"Content-Type: application/json\" -d '{json.dumps(input_obj)}'"

    resp = requests.post(NODE_NORMALIZER_QUERY_URL, headers={
        "Content-Type": "application/json",
        "Accept": "applicaton/json"
    }, json=input_obj)

    obj = resp.json()
    # print(obj)
    for key, value in obj.items():
        idExists = value
        # print(idExists)
    return idExists

def check_inconsistency(document):
    with open("inconsistencies.csv", 'w') as f:
        writer = csv.writer(f, delimiter='\t', lineterminator='\n',)
        for table, feature in document.items():
            for feature_name, identifier_list in feature.items():
                # print(table, ":", feature_name, ":", identifier_list)
                for identifier in identifier_list:
                    # print(identifier)
                    if not checkIdExits(identifier):
                        print(identifier)
                        writer.writerow(iter(identifier))

with open(r'identifiers.yml') as file:
    document = yaml.full_load(file)
check_inconsistency(document)