import enum
import logging

from sqlalchemy import (
    Table, Column, Float, Integer, String, MetaData, Sequence,
    Index, DateTime, Text, LargeBinary, Enum,
)

from .features import features

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_metadata(table_columns):

  metadata = MetaData()

  def table_id(table):
      """Generate table id."""
      return table[0].upper() + table[1:] + "Id"


  def sql_type(ty):
      """Generate SQL type."""
      if ty is int:
          return Integer
      elif ty is str:
          return String
      elif ty is float:
          return Float
      elif isinstance(ty, enum.Enum):
          return Enum(ty)
      else:
          raise RuntimeError(f"not sql type for {ty}")


  table_cols = {
      table: [
          Column(table_id(table), Integer),
          Column("year", Integer),
      ] + [
          Column(feature.name, sql_type(feature._type))
          for feature in features[table]
          if feature.name in columns
      ]
      for table, columns in table_columns.items()
  }

  tables = {
      table : Table(table, metadata, *tab_cols)
      for table, tab_cols in table_cols.items()
  }

  name_table = Table(
      "name",
      metadata,
      Column("name", String, primary_key=True),
      Column("cohort_id", String),
      Column("table", String),
  )

  cohort_cols = [
      Column("cohort_id", String, primary_key=True),
      Column("table", String),
      Column("year", Integer),
      Column("size", Integer),
      Column("features", String)
  ]

  cohort = Table("cohort", metadata, *cohort_cols)

  cohort_id_seq = Sequence('cohort_id_seq', metadata=metadata)

  return metadata

  # association_cols = [
  #     Column("digest", LargeBinary),
  #     Column("table", String),
  #     Column("cohort_features", String),
  #     Column("cohort_year", Integer),
  #     Column("feature_a", String),
  #     Column("feature_b", String),
  #     Column("association", Text),
  #     Column("access_time", DateTime)
  # ]

  # cache = Table("cache", metadata, *association_cols)

  # Index("cache_index", cache.c.digest)

  # count_cols = [
  #     Column("digest", LargeBinary),
  #     Column("table", String),
  #     Column("cohort_features", String),
  #     Column("cohort_year", Integer),
  #     Column("feature_a", String),
  #     Column("count", Text),
  #     Column("access_time", DateTime)
  # ]

  # cache_count = Table("cache_count", metadata, *count_cols)

  # Index("cache_count_index", cache_count.c.digest)
