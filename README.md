# icees-api-config

## How to run qc tool

The qc tool is under the `qctool` directory. The following commands are run in the `qctool` directory

### installation

```
pip install -r requirements.txt
```

### running

Example:

```
python src/qc.py \
    --a_type features \
    --a ../config/all_features.yaml \
    --b_type mapping \
    --b ../config/FHIR_mappings.yml \
    --update_a ../config/all_features_update.yaml \
    --update_b ../config/FHIR_mappings.yml \
    --number_entries 10 \
    --similarity_threshold 0.5 \
    --table patient visit \
    --ignore_suffix Table _flag_first _flag_last 
```

Usage:

```
python src/qc.py --help
```


