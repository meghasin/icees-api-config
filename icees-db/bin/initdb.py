"""Initialize database."""
import logging
import os
import tempfile
from pathlib import Path

from icees_db.dbutils import create, insert, create_indices, read_headers
from icees_db.features import features_dict
from icees_db.model import generate_metadata

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def setup():
    table_columns = {}
    csvdir = os.environ.get("DATA_PATH", "db/data/")
    for t in os.listdir(csvdir):
      if t in features_dict:
          table_dir = csvdir + "/" + t
          if os.path.isdir(table_dir):
              logger.info(table_dir + " exists")
              for f in os.listdir(table_dir):
                  table = table_dir + "/" + f
                  logger.info("loading headers of " + table)
                  table_columns[t] = read_headers(table, t)
                  break

    metadata = generate_metadata(table_columns)

    create(metadata)
    for t in os.listdir(csvdir):
      if t in features_dict:
        table_dir = csvdir + "/" + t
        if os.path.isdir(table_dir):
            logger.info(table_dir + " exists")
            for f in os.listdir(table_dir):
                table = table_dir + "/" + f
                logger.info("loading " + table)
                insert(table, t)

    create_indices(metadata)


if __name__ == "__main__":
    setup()
