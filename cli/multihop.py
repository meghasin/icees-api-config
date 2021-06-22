import json
import requests
import sys
from treelib import Tree
from colorama import init, Fore, Back
import pandas as pd

output_file_path = sys.argv[1]

init()

ids = ["MONDO:0005359", "SNOMEDCT:197358007", "MESH:D056487", "MESH:D006760", "NCIT:C26991"]

workflow = [
    {
        "name": "icees-dili",
        "url": "https://icees.renci.org:16341/query",
        "query": lambda id: {
            "nodes": {
                "n0": {
                    "name": "drug-induced liver injury",
                    "ids": [id]
                },
                "n1": {
                    "categories": [
                        "biolink:DiseaseOrPhenotypicFeature"
                    ],
                    "name": "Disease Or Phenotypic Feature"
                }
            },
            "edges": {
                "e0": {
                    "subject": "n0",
                    "object": "n1",
                    "predicates": [
                        "biolink:correlated_with"
                    ]
                }
            }
        },
        "result_node": "n1",
        "additional_properties": {
            "query_options": {
                "maximum_p_value": 0.1
            }
        }
    }, {
        "name": "arax",
        "url": "https://arax.ncats.io/api/arax/v1.1/query",
        "query": lambda id: {
            "nodes": {
                "n1": {
                    "ids": [id],
                    "name": "Disease Or Phenotypic Feature"
                },
                "n2": {
                    "categories": [
                        "biolink:Gene"
                    ],
                    "name": "Gene"
                },
                "n3": {
                    "categories": [
                        "biolink:ChemicalSubstance"
                    ],
                    "name": "Chemical Substance"
                }
            },
            "edges": {
                "e1": {
                    "subject": "n1",
                    "object": "n2",
                    "predicates": [
                        "biolink:condition_associated_with_gene"
                    ]
                },
                "e2": {
                    "subject": "n2",
                    "object": "n3",
                    "predicates": [
                        "biolink:related_to"
                    ]
                }
            }
        }
    }
]


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
    obj = query(id)
    qedges = list(obj["edges"].keys())
    qnodes = list(obj["nodes"].keys())
    message = {
        "message": {
            "query_graph": obj
        }, **additional_properties
    }
    if verbose:
        print(f"curl -XPOST {url} -H \"Content-Type: application/json\" -d '{json.dumps(message)}'")
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
                nodes = [get_ids(node_bindings[qnode]) for qnode in qnodes]
                edges_list.append(edges)
                nodes_list.append(nodes)

            results_df = pd.DataFrame([list(map(lambda a: "\n".join(sorted(list(set(a)))), nodes + edges)) for nodes, edges in zip(nodes_list, edges_list)], columns = [f"{depth}_{column}" for column in qnodes + qedges])
            results_df[f"step_{depth}"] = f"{name}:{id}"

            if result_node is not None:
                subprogress[key] = {}
                subsubprogress = subprogress[key]
                result_node_index = qnodes.index(result_node)
                result_node_id_lists = [nodes[result_node_index] for nodes in nodes_list]

                next_results_df_list = []
                
                for j, result_node_id_list in enumerate(result_node_id_lists):
                    subkey = f"result({str(j).rjust(len(str(len(result_node_id_lists)-1)))}:{result_node_id_list})"
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
    
runWorkflow(ids, workflow)
    


