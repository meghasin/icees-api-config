"""
 Update the FHIR_mapping.yaml file.
    a) Create a dictionary to map "system" link for each feature using https://www.hl7.org/fhir/terminologies-systems.html
    b) Add all the entries for all the vocabs found in consistent_FHIR_mapping via Athena_find_consistent

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
system_links = {'LOINC' : 'http://loinc.org', 'ICD10CN' : 'ICD-10-CN', 'ICD10CM' : 'http://hl7.org/fhir/sid/icd-10-cm' , 'RxNorm' : 'http://www.nlm.nih.gov/research/umls/rxnorm', 'ICD9ProcCN': 'ICD-9-Proc-CN', 'ICD10GM': 'http://fhir.de/CodeSystem/dimdi/icd-10-gm', 'RxNorm Extension': 'RxNorm Extension', 'ICD9CM':'http://hl7.org/fhir/sid/icd-9-cm*', 'ICD10':'http://hl7.org/fhir/sid/icd-10', 'MESH':'http://terminology.hl7.org/CodeSystem/MSH', 'ICD10PCS':'ICD10PCS', 'HGNC':'http://www.genenames.org', 'ICD9Proc':'ICD9Proc'}

def add_dict(target, d):
    for key in d:
        target.setdefault(key, []).append(d[key])

with open(r'consistent_FHIR_mapping.yml') as file:
    consistent_identifier = yaml.full_load(file)
with open(r'../FHIR_mappings.yml') as file:
    FHIR_mappings = yaml.full_load(file)
test ={}
for key, value in consistent_identifier["dictitems"].items():
    domain_ls= {}
    for domain, domain_list in value.items():
        new_feature = {}
        for item in domain_list:
            item = str(item)
            vocab = item.rsplit(':', 1)[0]
            code = item.rsplit(':', 1)[1]
            domain_ls.setdefault(domain,[]).append({'system': system_links[vocab], 'code': code})
    #print(key)
    test[key]=domain_ls


for key1 in FHIR_mappings["FHIR"]:
    if key1 in test:
        d3={}
        add_dict(d3,FHIR_mappings["FHIR"][key1])
        add_dict(d3,test[key1])
        FHIR_mappings["FHIR"][key1] =d3
for key in test:
    if key not in FHIR_mappings["FHIR"]:
        print(key)
        FHIR_mappings["FHIR"][key] = test[key]

with open(r'updated_FHIR_mapping.yml', 'w') as file:
    documents = yaml.dump(FHIR_mappings, file)
