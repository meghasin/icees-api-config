import json
import requests
import sys
import argparse
from functools import partial
import urllib.parse
from treelib import Tree
from colorama import init, Fore, Back
import pandas as pd
import traceback
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    to_subtree(obj, tree, None)
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

        
def label(obj, id):
    id_label = get_label(obj, id)
    return f"{id}, {id_label}" if id_label is not None else id


def add_synonyms(ids, knowledge_graph, verbose):
    all_ids = set(ids)
    for id in ids:
        all_ids |= {value for a in knowledge_graph["nodes"][id].get("attributes", []) if a["attribute_type_id"] == "biolink:synonym" for value in a["value"]}
    if verbose["debug"]:
        logger.info(f"found synonyms of {ids} are {all_ids}")
    return sorted(list(all_ids))


def prefix_of(node_id):
    return node_id.split(":")[0]


def filter_node_ids_by_prefix(prefixes, node_ids):
    return [node_id for node_id in node_ids if prefix_of(node_id) in prefixes] if prefixes is not None else node_ids


def get_supported_prefixes(step, verbose):
    metadata_url = step["metadata_url"]
    curl_cmd = f"curl -XGET {metadata_url}"
    if verbose["curl"]:
        logger.info(curl_cmd)
    try:
        resp = requests.get(metadata_url)
        if verbose["response"]:
            logger.info(resp.content)
        if resp.status_code != 200:
            logger.info(f"{curl_cmd}")
            logger.info(f"error: cannot get meta kg {resp}")
            return None
        metakg = resp.json()
        return [prefix for node in metakg["nodes"].values() for prefix in node["id_prefixes"]]
    except Exception as e:
        logger.info(f"{curl_cmd}")
        logger.info(f"error: cannot get meta kg {traceback.format_exc()}")
        return None


def run_query(step, subprogress, key, ids, verbose):
    url = step["url"]
    query = step["query"]
    additional_properties = step.get("additional_properties", {})
    obj = replace(query, {"$id": ids})
    message = {
        "message": {
            "query_graph": obj
        }, **additional_properties
    }
    curl_cmd = f"curl -XPOST {url} -H \"Content-Type: application/json\" -d '{json.dumps(message)}'"
    if verbose["curl"]:
        logger.info(curl_cmd)
    try:
        resp = requests.post(url, json=message)
        if resp.status_code != 200:
            subprogress[key] = f"{Fore.RED}Error{Fore.RESET} {resp if verbose['response'] else resp.status_code}"
            return None
        else:
            return resp.json()
    except Exception as e:
        subprogress[key] = f"{Fore.RED}Error{Fore.RESET} {traceback.format_exc() if verbose['response'] else e}"
        return None


def parse_resp(step, resp_obj, verbose):
    query = step["query"]
    qedges = query["edges"].keys()
    qnodes = query["nodes"].keys()
    knowledge_graph = resp_obj["message"]["knowledge_graph"]
    if verbose["debug"]:
        logger.info(json.dumps(knowledge_graph, indent=4))
    results = resp_obj["message"]["results"]
    nodes_list = []
    edges_list = []
    result_node_list = []

    for result in results:
        edge_bindings = result["edge_bindings"]
        node_bindings = result["node_bindings"]
        edges = [get_ids(edge_bindings[qedge]) for qedge in qedges]
        nodes = [add_synonyms(get_ids(node_bindings[qnode]), knowledge_graph, verbose) for qnode in qnodes]
        edges_list.append(edges)
        nodes_list.append(nodes)

    if len(results) == 0:
        return None, None

    return nodes_list, edges_list


def get_id_set(l):
    id_set = set()
    for nodes in l:
        id_set |= set(nodes)
    return id_set


def get_equivalent_ids(id_set, verbose):
    input_obj = {
        "curies": list(id_set)
    }
    curl_cmd = f"curl -XPOST {NODE_NORMALIZER_QUERY_URL} -H \"Content-Type: application/json\" -d '{json.dumps(input_obj)}'"
    if verbose["curl"]:
        logger.info(curl_cmd)
    try:
        resp = requests.post(NODE_NORMALIZER_QUERY_URL, headers={
            "Content-Type": "application/json",
            "Accept": "applicaton/json"
        }, json=input_obj)
        if resp.status_code != 200:
            logger.info(curl_cmd)
            logger.info(f"error: node normalization {resp.content}")
            return None
        obj = resp.json()
        return obj
    except Exception as e:
        logger.info(curl_cmd)
        logger.info(f"error: node normalization {traceback.format_exc()}")
        return None


def truncate(s, verbose):
    if not verbose["no_truncate"] and len(s) > 80:
        return s[:77] + "..."
    else:
        return s
    
def create_results_df(ids, nodes_list, edges_list, equivalent_ids, step, depth, verbose):
    if nodes_list is None:
        return None
    query = step["query"]
    qedges = list(query["edges"].keys())
    qnodes = list(query["nodes"].keys())
    name = step["name"]
    results_df = pd.DataFrame([list(map(lambda a: "\n".join(map(partial(label, equivalent_ids), sorted(list(set(a))))), nodes + edges)) for nodes, edges in zip(nodes_list, edges_list)], columns = [f"{depth}_{column}" for column in qnodes + qedges])
    results_df[f"step_{depth}"] = f"{name}:{json.dumps([label(equivalent_ids, id) for id in ids], indent=4)}"
    return results_df


def format_integer(i, n):
    return str(i).rjust(len(str(n-1)))


def runSteps(progress, subprogress, key, depth, ids_list, steps, verbose):
    if len(steps) == 0:
        subprogress[key] = f"{Fore.GREEN}{len(ids_list)} Result(s){Fore.RESET}"
        return [pd.DataFrame([[]])]
    else:
        step, *tail = steps
        supported_prefixes = get_supported_prefixes(step, verbose)
        id_set = get_id_set(ids_list)
        equivalent_ids = get_equivalent_ids(id_set, verbose)
        if equivalent_ids is None:
            equivalent_ids = {}
    
        next_results_df_list = []
        subkey = truncate(f"{len(ids_list)} results(s) {[list(map(partial(label, equivalent_ids), ids)) for ids in ids_list]}", verbose)
        subprogress[key] = {subkey: {}}
        subsubprogress = subprogress[key][subkey]
        for i, ids in enumerate(ids_list):
            subsubkey = truncate(f"{format_integer(i, len(ids_list))}: {len(ids)} Identifier(s) {ids}", verbose)
            subsubprogress[subsubkey] = {}
            subsubsubprogress = subsubprogress[subsubkey]
            df = runStepsWithIds(progress, subsubsubprogress, equivalent_ids, depth, filter_node_ids_by_prefix(supported_prefixes, ids), step, tail, verbose)
            next_results_df_list.append(df)

        return next_results_df_list

    
def runStepsWithIds(progress, subprogress, equivalent_ids, depth, ids, step, tail, verbose):
    name = step["name"]
    query = step["query"]
    qnodes = list(query["nodes"].keys())
    result_node = step.get("result_node")
    logger.info(f"running {name} with {ids}")
    key = truncate(f"{len(ids)} Identifier(s) {name}({ids})", verbose)
    if len(ids) == 0:
        subprogress[key] = f"{Fore.YELLOW}No supported identifiers{Fore.RESET}"
        return None
    subprogress[key] = f"{Fore.BLUE}Running{Fore.RESET}"
    to_tree(progress).show()

    resp_obj = run_query(step, subprogress, key, ids, verbose)

    if resp_obj is not None:
        nodes_list, edges_list = parse_resp(step, resp_obj, verbose)

        if nodes_list is None:
            subprogress[key] = f"{Fore.YELLOW}No Results{Fore.RESET}"
            return None
        
        results_df = create_results_df(ids, nodes_list, edges_list, equivalent_ids, step, depth, verbose)

        if result_node is None:
            subprogress[key] = f"{Fore.GREEN}{len(nodes_list)} Result(s){Fore.RESET}"
            return results_df
        else:
            result_node_index = qnodes.index(result_node)
            result_node_id_lists = [nodes[result_node_index] for nodes in nodes_list]

            df_list = runSteps(progress, subprogress, key, depth + 1, result_node_id_lists, tail, verbose)

            next_results_df_list = []
            for i, df in enumerate(df_list):
                if df is not None:
                    next_results_df_list.append(results_df[i:i+1].merge(df, how="cross"))

            return pd.concat(next_results_df_list) if len(next_results_df_list) > 0 else None
    else:
        return None

            
def runWorkflow(ids, workflow, verbose=False, columns=None):
    progress = {"start": {}}
    df_list = runSteps(progress, progress, "start", 0, ids, workflow, verbose)
    logger.info(to_tree(progress))
    next_results_df_list = []
    for df in df_list:
        if df is not None:
            if columns is not None:
                df = df[columns]
                
            next_results_df_list.append(df)

    if len(next_results_df_list) > 0:
        pd.concat(next_results_df_list).to_csv(output_file_path, index=False)
    else:
        logger.info("No Results")

        
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run multihop query.')
    parser.add_argument('input_file_path', type=str, help='input file')
    parser.add_argument('output_file_path', type=str, help='output file')
    parser.add_argument('-r', '--response', action='store_true', default=False, help='print request response')
    parser.add_argument('-n', '--no_truncate', action='store_true', default=False, help='no truncation of node names')
    parser.add_argument('-c', '--curl', action='store_true', default=False, help='print curl command')
    parser.add_argument('-d', '--debug', action='store_true', default=False, help='print debug')

    args = parser.parse_args()
    input_file_path = args.input_file_path
    output_file_path = args.output_file_path
    verbose = {
        "no_truncate": args.no_truncate,
        "curl": args.curl,
        "debug": args.debug,
        "response": args.response
    }

    with open(input_file_path) as f:
        query = json.load(f)
    
    ids = query["ids"]
    workflow = query["steps"]
    columns = query.get("columns", None)

    runWorkflow(ids, workflow, verbose=verbose, columns=columns)
    


