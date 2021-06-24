import sys
import yaml

mappings_file_path, identifiers_file_path, new_mappings_file_path, new_value_sets_file_path = sys.argv[1:]

with open(mappings_file_path) as mappings_file:
    old_mappings = yaml.safe_load(mappings_file)

with open(identifiers_file_path) as identifiers_file:
    old_identifiers = yaml.safe_load(identifiers_file)

# merge tables

mappings = {}

value_sets = {}

for table, table_mappings in old_mappings.items():
    for column, column_mapping in table_mappings.items():
        if column in mappings:
            pass
        else:
            categories = column_mapping["categories"]
            if len(categories) == 0:
                print("no biolinkType, default to NameThing")
                categories = ["NamedThing"]
            ty = column_mapping["type"]
            mappings[column] = {
                "categories": categories,
                "identifiers": old_identifiers[table].get(column, []),
                "type": ty
            }
            maximum = column_mapping.get("maximum")
            minimum = column_mapping.get("minimum")
            enum = column_mapping.get("enum")
            if maximum is not None and minimum is not None:
                value_sets[column] = list(range(minimum, maximum+1))
            elif enum is not None:
                value_sets[column] = [item.strip() if isinstance(item, str) else item for item in enum]

with open(new_mappings_file_path, "w") as new_mappings_file:
    yaml.dump(mappings, new_mappings_file)

with open(new_value_sets_file_path, "w") as new_value_sets_file:
    yaml.dump(value_sets, new_value_sets_file)


            
    
