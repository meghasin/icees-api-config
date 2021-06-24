import json
import requests
import sys
import argparse
from functools import partial
import urllib.parse
from treelib import Tree
from colorama import init, Fore, Back
import pandas as pd

init()

def replace(template, values):
    if isinstance(template, dict):
        return {key:replace(val, values) for key, val in template.items()}
    elif isinstance(template, list):
        return [replace(e, values) for e in template]
    elif isinstance(template, str):
        return values.get(template, template)
    else:
        return template
    

NODE_NORMALIZER_QUERY_URL ="https://nodenormalization-sri.renci.org/1.1/get_normalized_nodes"

def get_label(obj, identifier):
    eqid_attributes = obj.get(identifier)
    if eqid_attributes is None:
        return None
    id_label = "~ " + eqid_attributes["id"]["label"]
    id_attributes = [eqid for eqid in eqid_attributes["equivalent_identifiers"] if eqid["identifier"] == identifier]
    if len(id_attributes) == 0:
        return id_label
    return id_attributes[0].get("label", id_label)
        

def get_ids(binding):
    return [a["id"] for a in binding]


def to_tree(obj):
    tree = Tree()
    tree_node = "start"
    tree.create_node("start", tree_node)
    to_subtree(obj, tree, tree_node)
    return tree


def to_subtree(obj, tree, tree_node):
    if isinstance(obj, dict):
        for i, (key, val) in enumerate(obj.items()):
            subtree_node = f"{tree_node}::{i}"
            tree.create_node(f"{key}", subtree_node, parent=tree_node)
            to_subtree(val, tree, subtree_node)
    else:
        subtree_node = f"{tree_node}::0"
        tree.create_node(f"{obj}", subtree_node, parent=tree_node)

        
def runSteps(progress, subprogress, depth, ids, steps, verbose):
    results_list = [runStepsOnId(progress, subprogress, i, len(ids), depth, id, steps, verbose) for i, id in enumerate(ids)]
    return None if all(results is None for results in results_list) else pd.concat(results_list)


def label(obj, id):
    id_label = get_label(obj, id)
    return f"{id}, {id_label}" if id_label is not None else id


def add_synonyms(ids, knowledge_graph, verbose):
    all_ids = set(ids)
    for id in ids:
        all_ids |= {value for a in knowledge_graph["nodes"][id].get("attributes", []) if a["attribute_type_id"] == "biolink:synonym" for value in a["value"]}
    if verbose:
        print(f"found synonyms of {ids} are {all_ids}")
    return sorted(list(all_ids))


def runStepsOnId(progress, subprogress, i, n, depth, id, steps, verbose):
    step, *tail = steps
    name = step["name"]
    url = step["url"]
    query = step["query"]
    result_node = step.get("result_node")
    additional_properties = step.get("additional_properties", {})
    print(f"running {name} with {id}")
    key = f"{name}({str(i).rjust(len(str(n-1)))}:{id})"
    subprogress[key] = f"{Fore.BLUE}Running{Fore.RESET}"
    to_tree(progress).show()
    obj = replace(query, {"$id": [id]})
    qedges = list(obj["edges"].keys())
    qnodes = list(obj["nodes"].keys())
    message = {
        "message": {
            "query_graph": obj
        }, **additional_properties
    }
    curl_cmd = f"curl -XPOST {url} -H \"Content-Type: application/json\" -d '{json.dumps(message)}'"
    curl_cmd2 = None
    if verbose:
        print(curl_cmd)
    try:
        resp = requests.post(url, json=message)
        if resp.status_code != 200:
            subprogress[key] = f"{Fore.RED}Error{Fore.RESET} {resp.content if verbose else resp.status_code}"
            return None
        else:
            knowledge_graph = resp.json()["message"]["knowledge_graph"]
            if verbose:
                print(json.dumps(knowledge_graph, indent=4))
            results = resp.json()["message"]["results"]
            nodes_list = []
            edges_list = []
            result_node_list = []
            if len(results) == 0:
                subprogress[key] = f"{Fore.YELLOW}No Results{Fore.RESET}"
                return None
            else:
                for result in results:
                    edge_bindings = result["edge_bindings"]
                    node_bindings = result["node_bindings"]
                    edges = [get_ids(edge_bindings[qedge]) for qedge in qedges]
                    nodes = [add_synonyms(get_ids(node_bindings[qnode]), knowledge_graph, verbose) for qnode in qnodes]
                    edges_list.append(edges)
                    nodes_list.append(nodes)

                id_set = set()
                for nodes in nodes_list:
                    for node in nodes:
                        id_set |= set(node)
                for edges in edges_list:
                    for edge in edges:
                        id_set |= set(edge)

                input_obj = {
                    "curies": list(id_set)
                }
                resp = requests.post(NODE_NORMALIZER_QUERY_URL, headers={
                    "Content-Type": "application/json",
                    "Accept": "applicaton/json"
                }, json=input_obj)                    
                curl_cmd2 = f"curl -XPOST {NODE_NORMALIZER_QUERY_URL} -H \"Content-Type: application/json\" -d '{json.dumps(input_obj)}'"
                obj = resp.json()

                results_df = pd.DataFrame([list(map(lambda a: "\n".join(map(partial(label, obj), sorted(list(set(a))))), nodes + edges)) for nodes, edges in zip(nodes_list, edges_list)], columns = [f"{depth}_{column}" for column in qnodes + qedges])
                results_df[f"step_{depth}"] = f"{name}:{label(obj, id)}"

                if result_node is not None:
                    subprogress[key] = {}
                    subsubprogress = subprogress[key]
                    result_node_index = qnodes.index(result_node)
                    result_node_id_lists = [nodes[result_node_index] for nodes in nodes_list]

                    next_results_df_list = []

                    for j, result_node_id_list in enumerate(result_node_id_lists):
                        subkey = f"result({str(j).rjust(len(str(len(result_node_id_lists)-1)))}:{list(map(partial(label, obj), result_node_id_list))})"
                        subsubprogress[subkey] = {}
                        subsubsubprogress = subsubprogress[subkey]

                        df = runSteps(progress, subsubsubprogress, depth + 1, result_node_id_list, tail, verbose)
                        if df is not None:
                            df = results_df[j:j+1].merge(df, how="cross")
                            next_results_df_list.append(df)

                    return pd.concat(next_results_df_list) if len(next_results_df_list) > 0 else None
                else:
                    subprogress[key] = f"{Fore.GREEN}{len(results)} Result(s){Fore.RESET}"
                    return results_df
    except:
        print(curl_cmd)
        if curl_cmd2:
            print(curl_cmd2)
        raise

            
def runWorkflow(ids, workflow, verbose=False, columns=None):
    progress = {}
    df = runSteps(progress, progress, 0, ids, workflow, verbose)
    print(to_tree(progress))
    if df is None:
        print("No Results")
    else:
       if columns is not None:
           df = df[columns]
       df.to_csv(output_file_path, index=False)
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('input_file_path', type=str, help='an integer for the accumulator')
    parser.add_argument('output_file_path', type=str, help='an integer for the accumulator')
    parser.add_argument('-v', '--verbose', action='store_true', default=False, help='sum the integers (default: find the max)')

    args = parser.parse_args()
    input_file_path = args.input_file_path
    output_file_path = args.output_file_path
    verbose = args.verbose

    with open(input_file_path) as f:
        query = json.load(f)
    
    ids = query["ids"]
    workflow = query["steps"]
    columns = query.get("columns", None)

    runWorkflow(ids, workflow, verbose=verbose, columns=columns)
    


