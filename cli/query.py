import sys
import time
import requests
import argparse
import json
from colorama import Fore, Back, Style, init
from treelib import Tree

init()

# server_url = "https://ars-dev.transltr.io"
default_server_url = "https://ars.transltr.io"

def retrieve_result_url(server_url, pk):
    return f"{server_url}/ars/api/messages/{pk}?trace=y"

def submit_query_url(server_url):
    return f"{server_url}/ars/api/submit"

def workflow_query(file_path):
    with open(file_path) as f:
        obj = json.load(f)
        
    return obj


def post_query(file_path, server_url):
    res = requests.post(submit_query_url(server_url), json=workflow_query(file_path))
    try:
        obj = res.json()
        pk = obj["pk"]
        print(pk)
        status = obj["fields"]["status"]
        return pk
    except:
        text = res.text
        print(text)
        return None


def retrieve_result(pk, server_url):
    try:
        res = requests.get(retrieve_result_url(server_url, pk))
        obj = res.json()
        status = obj["status"]
        return status, obj
    except:
        text = res.text
        print(text)
        return None, None


def retrieve_result_print(pk, server_url):
    status, obj = retrieve_result(pk, server_url)
    print(obj)


def wait_result(pk, interval, server_url):

    obj = None
    while True:
        status, obj = retrieve_result(pk, server_url)
        print(format_status(status))
        if status == "Running":
            print(f"sleep for {interval} seconds")
            time.sleep(60)
        else:
            break

    return obj


def wait_result_print(pk, interval, server_url):
    obj = wait_result(pk, interval, server_url)
    tree, _ = format_result(obj)
    tree.show()


def format_result(obj):
    tree = Tree()
    node_dict = {}
    generate_tree(tree, 0, obj, node_dict)
    return tree, node_dict


def format_status(status):
    if status == "Running":
        return Fore.BLUE + status + Fore.RESET
    elif status == "Error":
        return Fore.RED + status + Fore.RESET
    elif status == "Done":
        return Fore.GREEN + status + Fore.RESET
    elif status == "Unknown":
        return Fore.YELLOW + status + Fore.RESET
    else:
        return Fore.YELLOW + status + Fore.RESET


def generate_tree(tree, index, obj, node_dict, parent=None):
    node_id = obj["message"]
    node_dict[index] = node_id
    tree.create_node(f'{index:0>2}: {obj["actor"]["agent"]}, {format_status(obj["status"])}', node_id, parent=parent)
    index += 1
    for subobj in obj["children"]:
        index = generate_tree(tree, index, subobj, node_dict, node_id)
    return index


def navigate_result(pk, server_url):
    status, obj = retrieve_result(pk, server_url)
    while True:
        tree, node_dict = format_result(obj)
        tree.show()
        i = input("""please choose a node to navigate to or quit (q): """)
        if i == "q":
            return
        else:
            try:
                index = int(i)
                status, obj2 = retrieve_result(node_dict[index], server_url)
                jsonstr = json.dumps(obj2, indent=4)
                print(jsonstr)
            except Exception as e:
                print(e)
    

def post_query_wait_result(file_path, interval, server_url):
    pk = post_query(file_path, server_url)
    wait_result(pk, interval, server_url)


def post_query_navigate_result(file_path, interval, server_url):
    pk = post_query(file_path, server_url)
    wait_result(pk, interval, server_url)
    navigate_result(pk, server_url)


def wait_navigate(pk, interval, server_url):
    wait_result(pk, interval, server_url)
    navigate_result(pk, server_url)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--server_url", type=str, default=default_server_url)
    subparsers = parser.add_subparsers(help='sub-command help')
    parser_a = subparsers.add_parser('send', help='a help')
    parser_a.add_argument('file_path', type=str, help='bar help')
    parser_a.set_defaults(func=post_query)
    parser_b = subparsers.add_parser('recv', help='b help')
    parser_b.add_argument('pk', type=str, help='baz help')
    parser_b.set_defaults(func=retrieve_result_print)
    parser_c = subparsers.add_parser('wait', help='b help')
    parser_c.add_argument('pk', type=str, help='baz help')
    parser_c.add_argument('-i', '--interval', type=int, default=60, help='baz help')
    parser_c.set_defaults(func=wait_result_print)
    parser_e = subparsers.add_parser('nav', help='b help')
    parser_e.add_argument('pk', type=str, help='baz help')
    parser_e.set_defaults(func=navigate_result)
    parser_d = subparsers.add_parser('send_and_wait', help='b help')
    parser_d.add_argument('file_path', type=str, help='bar help')
    parser_d.add_argument('-i', '--interval', type=int, default=60, help='baz help')
    parser_d.set_defaults(func=post_query_wait_result)
    parser_f = subparsers.add_parser('send_and_nav', help='b help')
    parser_f.add_argument('file_path', type=str, help='bar help')
    parser_f.add_argument('-i', '--interval', type=int, default=60, help='baz help')
    parser_f.set_defaults(func=post_query_navigate_result)
    parser_g = subparsers.add_parser('wait_and_nav', help='b help')
    parser_g.add_argument('pk', type=str, help='baz help')
    parser_g.add_argument('-i', '--interval', type=int, default=60, help='baz help')
    parser_g.set_defaults(func=wait_navigate)

    args = parser.parse_args()

    func = args.func
    del args.func
    func(**vars(args))

    

    
                    
