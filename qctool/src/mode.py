from typing import Dict, List, Optional
from dataclasses import dataclass, field
from file import YAMLFile

@dataclass
class CacheTables:
    tables: Dict[str, list] = field(default_factory=dict)
    table_names: List[str] = field(default_factory=list)
    current_table: Optional[int] = 0

    def update_tables(self, config, tables):
        self.tables = tables
        if self.current_table >= len(config.table_names):
            self.current_table = len(config.table_names) - 1
            if self.current_table < 0:
                self.current_table = 0

            
@dataclass
class CacheFile:
    filename: str
    typ: str
    update : Optional[str] = None
    fil: Optional[YAMLFile] = None
    old_key : Optional[str] = None

    def update_file(self, fil):
        self.fil = fil
        self.old_key = None

@dataclass
class DiffMode:
    a_cache_file : CacheFile
    b_cache_file : CacheFile
    cache_tables : CacheTables = field(default_factory=CacheTables)

    def update_files(self, config, a_file, b_file, tables):
        self.a_cache_file.update_file(a_file)
        self.b_cache_file.update_file(b_file)
        self.cache_tables.update_tables(config, tables)

@dataclass
class FocusedMode:
    a_focused: bool
    cache_file: CacheFile
    cache_tables: CacheTables = field(default_factory=CacheTables)

    def update_file(self, config, fil, tables):
        self.cache_file.update_file(fil)
        self.cache_tables.update_tables(config, tables)

        
@dataclass
class Config:
    a_filename: str
    b_filename: str
    a_type: str
    b_type: str
    a_only: bool
    b_only: bool
    table_names: List[str]
    similarity_threshold: float
    max_entries: int
    ignore_suffix: List[str]
    a_updated: bool
    b_updated: bool
    a_update: Optional[str]
    b_update: Optional[str]
