#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 23 17:29:06 2021

@author: priyash

This module flags the inconsistent enumeration and attributes for given feature.yaml files for any usecase. 
The output is the incorrect enumerated features. You can modify to print bith correct and incorrect enumerated features. 

"""


import yaml


def test_config_consistency(yamlfile):
    
    with open(yamlfile) as f:
    
        # open and read yam files
        data = yaml.load(f, Loader=yaml.FullLoader)
    

        for item, doc in data.items():
            # looping through each table
            for ft in doc:
                
                # looping through every feature and checking the conditions below
                # correct conditions would be:
                # if key enum exists enum values should be string (even if they are in a list) and then the 'type' values should be a string
                # if key min and/or max exists then values should be integer then the 'type' values should be an integer 
                
                if ('enum' in doc[ft].keys()) and (doc[ft]['type'] == 'string'):
                    #if (isinstance(doc[ft]['enum'][0],str)):
                    pass#print(ft,'correct')#print(ft, "correct: enum is a srting and type is string")
                elif ('maximum' in doc[ft].keys()) and (doc[ft]['type'] == 'integer'):
                    pass#print(ft,'correct')#print(ft, "correct: maximum is a integer and type is integer")
                elif ('enum' not in doc[ft].keys()) and ('maximum' not in doc[ft].keys()):
                    pass
                else:
                    #print(ft,'incorrect',list(doc[ft].keys())[1],':',list(doc[ft].values())[1], 'type:', doc[ft]['type'])
                    print('incorrect:', ft, ':', doc[ft].items())

def print_unique_values(df):
    
    for col in df.columns:
        print(col)
        print(df[col].unique())

if __name__ == "__main__": 
    test_config_consistency() 
    print_unique_values()

