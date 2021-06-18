"""Database utilities."""
import argparse
import csv
from contextlib import contextmanager
import io
import logging
import os
from pathlib import Path
import sqlite3
import sys

import pandas as pd
import psycopg2
from sqlalchemy import Index

from .db import DBConnection
from .features import features

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(name)s:%(levelname)s:%(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


def createargs(args):
    create()


def create(metadata):
    """Build database schema."""
    with DBConnection() as conn:
        with conn.begin() as trans:
            metadata.create_all(conn)


def read_headers(file_path, table_name):
    with open(file_path, "r") as stream:
        reader = csv.DictReader(stream)

        index = table_name[0].upper() + table_name[1:] + "Id"
        row = next(reader)
        return [
            col if col != "index" else index
            for col in row.keys()
        ]


def create_indices(metadata):
    """Build database indexes."""
    tables = metadata.tables
    itrunc = 0
    def truncate(a, length=63):
        logger.info("creating index " + a)
        nonlocal itrunc
        prefix = "index" + str(itrunc)
        itrunc += 1
        return prefix + a[:63-len(prefix)]
    with DBConnection() as conn:
        with conn.begin() as trans:

            for table, table_features in tables.items():
              if table not in ["cohort", "name"]:
                id_col = table[0].upper() + table[1:] + "Id"
                Index(truncate(table + "_" + id_col), tables[table].c[id_col]).create(conn)
                Index(truncate(table + "_year"), tables[table].c.year).create(conn)
                cols = list(map(lambda a : a.name, table_features.c))
                for feature in cols:
                    Index(truncate(table + "_" + feature), tables[table].c[feature]).create(conn)
                    Index(truncate(table + "_year_" + feature), tables[table].c.year, tables[table].c[feature]).create(conn)
#                    for feature2 in cols:
#                        Index(truncate(table + "_year_" + feature + "_" + feature2), tables[table].c.year, tables[table].c[feature], tables[table].c[feature2]).create(conn)

    
def insertargs(args):
    insert(args.input_file, args.table_name)


type_dict = {
    "integer": lambda s : s.astype(pd.Int64Dtype()),
    "string": lambda s : s.astype(str, skipna=True)
}

db_ = os.environ.get("ICEES_DB", "sqlite")


@contextmanager
def db_connections():
    """Database connection context manager."""
    if db_ == "sqlite":
        con = sqlite3.connect(Path(os.environ["DB_PATH"]) / "example.db")
    elif db_ == "postgres":
        con = psycopg2.connect(
            host=os.environ["ICEES_HOST"],
            database="icees_database",
            user="icees_dbuser",
            password="icees_dbpass",
        )
    else:
        raise ValueError(f"Unsupported database '{db_}'")

    yield con

    con.commit()
    con.close()


def insert(file_path, table_name):
    """Insert data from file into table."""
    with db_connections() as con:
        with open(file_path, "r") as stream:
            _insert(table_name, con, stream)


def removeDotZero(s):
    if s.endswith(".0"):
        return s[:-2]
    else:
        return s


def emptyStringToNone(s):
    return s if s != "" else None


def _insert(table_name, con: sqlite3.Connection, stream: io.TextIOBase):
    """Insert data from file into table."""
    reader = csv.DictReader(stream)
    to_db = []
    columns = None
    index = table_name[0].upper() + table_name[1:] + "Id"
    for row in reader:
        if not columns:
            columns = [
                col if col != "index" else index
                for col in row.keys()
            ]
        to_db.append(tuple(
            emptyStringToNone(removeDotZero(row.get(col if col != index else "index")))
            for col in columns
        ))

    cur = con.cursor()
    if db_ == "sqlite":
        placeholders = ", ".join("?" for _ in columns)
    else:
        placeholders = ", ".join("%s" for _ in columns)
    query = "INSERT INTO {0} ({1}) VALUES ({2});".format(
        table_name,
        ", ".join(f"\"{col}\"" for col in columns),
        placeholders,
    )
    cur.executemany(query, to_db)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='ICEES DB Utilities')
    subparsers = parser.add_subparsers(help='subcommands')
    # create the parser for the "create" command
    parser_create = subparsers.add_parser('create', help='create tables')
    parser_create.set_defaults(func=createargs)
    
    # create the parser for the "insert" command
    parser_insert = subparsers.add_parser('insert', help='insert data into database')
    parser_insert.add_argument('input_file', type=str, help='csv file')
    parser_insert.add_argument('table_name', type=str, help='table name')
    parser_insert.set_defaults(func=insertargs)
    
    args = parser.parse_args(sys.argv[1:])
    args.func(args)
