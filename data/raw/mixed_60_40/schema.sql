CREATE INDEX idx_alias_norm ON product_aliases(normalized_alias);

CREATE INDEX idx_products_origin ON products(data_origin,is_synthetic);

CREATE INDEX idx_rag_origin ON rag_documents(source_kind,is_mock);

CREATE INDEX idx_regional_product ON regional_profiles(product_id,district_name);

CREATE TABLE agronomic_summaries(
      product_id TEXT PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
      seasons_json TEXT NOT NULL,
      planting_periods_json TEXT NOT NULL,
      growth_periods_json TEXT NOT NULL,
      harvest_periods_json TEXT NOT NULL,
      temperature_profiles_json TEXT NOT NULL,
      humidity_profiles_json TEXT NOT NULL,
      summary_text TEXT NOT NULL,
      data_origin TEXT NOT NULL,
      evidence_note TEXT NOT NULL,
      safe_for_prescriptive_advice INTEGER NOT NULL
    );

CREATE TABLE codebase_crop_mapping(
      product_id TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
      codebase_crop_id TEXT NOT NULL,
      mapping_type TEXT NOT NULL,
      enabled_for_planning INTEGER NOT NULL,
      PRIMARY KEY(product_id,codebase_crop_id)
    );

CREATE TABLE fertilizer_summaries(
      product_id TEXT PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
      source_table_id TEXT,
      recommendation_context TEXT,
      season_context TEXT,
      yield_goal_raw TEXT,
      units_raw TEXT,
      rates_json TEXT NOT NULL,
      source_page INTEGER,
      data_origin TEXT NOT NULL,
      interpretation_warning TEXT NOT NULL,
      safe_for_prescriptive_advice INTEGER NOT NULL
    );

CREATE TABLE metadata(key TEXT PRIMARY KEY, value_json TEXT NOT NULL);

CREATE TABLE product_aliases(
      alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
      product_id TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
      alias_text TEXT NOT NULL,
      normalized_alias TEXT NOT NULL,
      language_code TEXT,
      script TEXT,
      alias_type TEXT NOT NULL,
      data_origin TEXT NOT NULL,
      is_ambiguous INTEGER NOT NULL DEFAULT 0,
      UNIQUE(product_id, normalized_alias, alias_type)
    );

CREATE VIRTUAL TABLE product_search_fts USING fts5(
      product_id UNINDEXED, canonical_name_en, canonical_name_bn, aliases, category, description,
      tokenize='unicode61 remove_diacritics 2'
    );

CREATE TABLE 'product_search_fts_config'(k PRIMARY KEY, v) WITHOUT ROWID;

CREATE TABLE 'product_search_fts_content'(id INTEGER PRIMARY KEY, c0, c1, c2, c3, c4, c5);

CREATE TABLE 'product_search_fts_data'(id INTEGER PRIMARY KEY, block BLOB);

CREATE TABLE 'product_search_fts_docsize'(id INTEGER PRIMARY KEY, sz BLOB);

CREATE TABLE 'product_search_fts_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID;

CREATE TABLE product_source_links(
      product_id TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
      source_id TEXT NOT NULL REFERENCES sources(source_id),
      relationship TEXT NOT NULL,
      PRIMARY KEY(product_id,source_id,relationship)
    );

CREATE TABLE product_varieties(
      variety_id INTEGER PRIMARY KEY AUTOINCREMENT,
      product_id TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
      variety_name TEXT NOT NULL,
      season_context TEXT,
      yield_goal_raw TEXT,
      data_origin TEXT NOT NULL,
      source_record_id TEXT,
      source_page INTEGER,
      safe_for_prescriptive_advice INTEGER NOT NULL,
      UNIQUE(product_id,variety_name,source_record_id)
    );

CREATE TABLE products(
      product_id TEXT PRIMARY KEY,
      canonical_name_en TEXT UNIQUE NOT NULL,
      canonical_name_bn TEXT,
      scientific_name TEXT,
      category TEXT,
      subcategory TEXT,
      description TEXT NOT NULL,
      data_origin TEXT NOT NULL CHECK(data_origin IN ('real_authentic','synthetic_made_up')),
      is_synthetic INTEGER NOT NULL CHECK(is_synthetic IN (0,1)),
      evidence_level TEXT NOT NULL,
      safe_for_identity_lookup INTEGER NOT NULL,
      safe_for_prescriptive_advice INTEGER NOT NULL,
      eligible_for_recommendation INTEGER NOT NULL,
      source_confidence REAL NOT NULL,
      created_at TEXT NOT NULL
    );

CREATE TABLE rag_documents(
      document_id TEXT PRIMARY KEY,
      product_id TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
      title TEXT NOT NULL,
      content TEXT NOT NULL,
      source TEXT NOT NULL,
      source_kind TEXT NOT NULL,
      is_mock INTEGER NOT NULL,
      crop_id TEXT,
      crop_group TEXT,
      district TEXT,
      upazila TEXT,
      knowledge_type TEXT NOT NULL,
      metadata_json TEXT NOT NULL,
      safe_for_prescriptive_advice INTEGER NOT NULL
    );

CREATE TABLE regional_profiles(
      profile_id TEXT PRIMARY KEY,
      product_id TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
      district_name TEXT,
      upazila_name TEXT,
      metric_type TEXT NOT NULL,
      metric_value REAL,
      metric_unit TEXT,
      profile_json TEXT NOT NULL,
      data_origin TEXT NOT NULL,
      source_record_id TEXT,
      safe_for_prescriptive_advice INTEGER NOT NULL
    );

CREATE TABLE sources(
      source_id TEXT PRIMARY KEY, title TEXT NOT NULL, publisher TEXT, publication_date TEXT,
      source_url TEXT, doi TEXT, license TEXT, local_filename TEXT, sha256 TEXT,
      evidence_class TEXT NOT NULL, metadata_json TEXT NOT NULL
    );

CREATE TABLE synthetic_lineage(
      product_id TEXT PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
      generation_seed INTEGER NOT NULL,
      template_family TEXT NOT NULL,
      fictional_traits_json TEXT NOT NULL,
      intended_use TEXT NOT NULL,
      prohibition TEXT NOT NULL
    );

CREATE TABLE validation_metrics(metric TEXT PRIMARY KEY, value_json TEXT NOT NULL);