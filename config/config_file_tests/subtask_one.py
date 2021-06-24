# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

from test_config_consistency import test_config_consistency



#dili = pd.read_csv('/Users/priyash/Documents/ICEES_Project/ebcr0_datasets/DILI/augmentin_ptlist_upto_3.10.21_v2_ICEES header_rev2_add_year.csv')
#covid = pd.read_csv('/Users/priyash/Documents/ICEES_Project/ebcr0_datasets/covid/patient.csv')

yamlfile = '/Users/priyash/Documents/GitHub/icees-api-config/config/all_features.yaml'

test_config_consistency(yamlfile)
