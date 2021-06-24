#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jun 24 11:45:56 2021

@author: priyash
"""

import pandas as pd

from test_config_consistency import print_unique_values

dili = pd.read_csv('/Users/priyash/Documents/ICEES_Project/ebcr0_datasets/DILI/augmentin_ptlist_upto_3.10.21_v2_ICEES header_rev2_add_year.csv')
#covid = pd.read_csv('/Users/priyash/Documents/ICEES_Project/ebcr0_datasets/covid/patient.csv')


print_unique_values(dili)