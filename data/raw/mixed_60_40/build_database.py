from __future__ import annotations

import csv
import gzip
import hashlib
import json
import random
import shutil
import sqlite3
import textwrap
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path('/mnt/data')
MASTER_DB = ROOT / 'bangladesh_agri_master_database_v1' / 'bangladesh_agri_master.db'
OUT = ROOT / 'bangladesh_agri_60_real_40_synthetic_v3'
DB_PATH = OUT / 'bangladesh_agri_60_40.db'
CODEBASE_SOURCE = ROOT / 'work_codebase' / 'sandbox'
PATCHED_CODEBASE = ROOT / 'AgriSense_60_40_DB_Integrated'

REAL_IDS = [
    'rice','maize','wheat','potato','jute','sugarcane','mustard','soybean','lentil','mungbean',
    'black_gram','chickpea','groundnut','sesame','sunflower','onion','garlic','ginger','turmeric','chilli',
    'tomato','brinjal','okra','cabbage','cauliflower','carrot','radish','cucumber','bitter_gourd','pointed_gourd',
    'sponge_gourd','sweet_gourd','ash_gourd','watermelon','pumpkin','country_bean','cowpea','pea','french_bean','banana',
    'mango','jackfruit','guava','papaya','pineapple','coconut','lemon','malta','jambura','litchi',
    'boroi','amra','tamarind','dragon_fruit','strawberry','tea','betelnut','cotton','mesta','sweet_potato'
]

SYNTHETIC_PRODUCTS = [
    ('synthetic_padma_pearl_grain','Synthetic Padma Pearl Grain','কাল্পনিক পদ্মা পার্ল শস্য','Cereal simulation'),
    ('synthetic_meghna_mist_millet','Synthetic Meghna Mist Millet','কাল্পনিক মেঘনা মিস্ট মিলেট','Cereal simulation'),
    ('synthetic_barind_silver_wheat','Synthetic Barind Silver Wheat','কাল্পনিক বরেন্দ্র সিলভার গম','Cereal simulation'),
    ('synthetic_haor_cloud_rice','Synthetic Haor Cloud Rice','কাল্পনিক হাওর ক্লাউড ধান','Cereal simulation'),
    ('synthetic_delta_amber_maize','Synthetic Delta Amber Maize','কাল্পনিক ডেল্টা অ্যাম্বার ভুট্টা','Cereal simulation'),
    ('synthetic_sundarban_saltbean','Synthetic Sundarban Saltbean','কাল্পনিক সুন্দরবন সল্টবিন','Pulse simulation'),
    ('synthetic_tista_blue_lentil','Synthetic Tista Blue Lentil','কাল্পনিক তিস্তা ব্লু মসুর','Pulse simulation'),
    ('synthetic_jamuna_gold_gram','Synthetic Jamuna Gold Gram','কাল্পনিক যমুনা গোল্ড ডাল','Pulse simulation'),
    ('synthetic_madhupur_velvet_bean','Synthetic Madhupur Velvet Bean','কাল্পনিক মধুপুর ভেলভেট বিন','Pulse simulation'),
    ('synthetic_surma_ruby_pea','Synthetic Surma Ruby Pea','কাল্পনিক সুরমা রুবি মটর','Pulse simulation'),
    ('synthetic_padma_sun_oilseed','Synthetic Padma Sun Oilseed','কাল্পনিক পদ্মা সান তেলবীজ','Oilseed simulation'),
    ('synthetic_barind_copper_mustard','Synthetic Barind Copper Mustard','কাল্পনিক বরেন্দ্র কপার সরিষা','Oilseed simulation'),
    ('synthetic_delta_moon_sesame','Synthetic Delta Moon Sesame','কাল্পনিক ডেল্টা মুন তিল','Oilseed simulation'),
    ('synthetic_meghna_crystal_soy','Synthetic Meghna Crystal Soy','কাল্পনিক মেঘনা ক্রিস্টাল সয়া','Oilseed simulation'),
    ('synthetic_haor_glow_groundnut','Synthetic Haor Glow Groundnut','কাল্পনিক হাওর গ্লো চিনাবাদাম','Oilseed simulation'),
    ('synthetic_sonar_leaf_jute','Synthetic Sonar Leaf Jute','কাল্পনিক সোনার লিফ পাট','Fibre simulation'),
    ('synthetic_delta_soft_cotton','Synthetic Delta Soft Cotton','কাল্পনিক ডেল্টা সফট তুলা','Fibre simulation'),
    ('synthetic_tista_red_mesta','Synthetic Tista Red Mesta','কাল্পনিক তিস্তা রেড মেস্তা','Fibre simulation'),
    ('synthetic_haor_sweet_root','Synthetic Haor Sweet Root','কাল্পনিক হাওর সুইট রুট','Root simulation'),
    ('synthetic_barind_glass_potato','Synthetic Barind Glass Potato','কাল্পনিক বরেন্দ্র গ্লাস আলু','Root simulation'),
    ('synthetic_padma_golden_onion','Synthetic Padma Golden Onion','কাল্পনিক পদ্মা গোল্ডেন পেঁয়াজ','Spice simulation'),
    ('synthetic_meghna_mild_chilli','Synthetic Meghna Mild Chilli','কাল্পনিক মেঘনা মাইল্ড মরিচ','Spice simulation'),
    ('synthetic_surma_white_garlic','Synthetic Surma White Garlic','কাল্পনিক সুরমা হোয়াইট রসুন','Spice simulation'),
    ('synthetic_delta_blue_ginger','Synthetic Delta Blue Ginger','কাল্পনিক ডেল্টা ব্লু আদা','Spice simulation'),
    ('synthetic_madhupur_sweet_turmeric','Synthetic Madhupur Sweet Turmeric','কাল্পনিক মধুপুর সুইট হলুদ','Spice simulation'),
    ('synthetic_haor_sky_tomato','Synthetic Haor Sky Tomato','কাল্পনিক হাওর স্কাই টমেটো','Vegetable simulation'),
    ('synthetic_padma_pearl_brinjal','Synthetic Padma Pearl Brinjal','কাল্পনিক পদ্মা পার্ল বেগুন','Vegetable simulation'),
    ('synthetic_barind_crisp_okra','Synthetic Barind Crisp Okra','কাল্পনিক বরেন্দ্র ক্রিস্প ঢেঁড়স','Vegetable simulation'),
    ('synthetic_meghna_snow_cabbage','Synthetic Meghna Snow Cabbage','কাল্পনিক মেঘনা স্নো বাঁধাকপি','Vegetable simulation'),
    ('synthetic_tista_sun_cauliflower','Synthetic Tista Sun Cauliflower','কাল্পনিক তিস্তা সান ফুলকপি','Vegetable simulation'),
    ('synthetic_delta_rain_cucumber','Synthetic Delta Rain Cucumber','কাল্পনিক ডেল্টা রেইন শসা','Vegetable simulation'),
    ('synthetic_surma_star_gourd','Synthetic Surma Star Gourd','কাল্পনিক সুরমা স্টার লাউ','Vegetable simulation'),
    ('synthetic_haor_moon_melon','Synthetic Haor Moon Melon','কাল্পনিক হাওর মুন মেলন','Fruit simulation'),
    ('synthetic_padma_crystal_mango','Synthetic Padma Crystal Mango','কাল্পনিক পদ্মা ক্রিস্টাল আম','Fruit simulation'),
    ('synthetic_meghna_silver_guava','Synthetic Meghna Silver Guava','কাল্পনিক মেঘনা সিলভার পেয়ারা','Fruit simulation'),
    ('synthetic_barind_honey_papaya','Synthetic Barind Honey Papaya','কাল্পনিক বরেন্দ্র হানি পেঁপে','Fruit simulation'),
    ('synthetic_tista_blue_banana','Synthetic Tista Blue Banana','কাল্পনিক তিস্তা ব্লু কলা','Fruit simulation'),
    ('synthetic_delta_ruby_pineapple','Synthetic Delta Ruby Pineapple','কাল্পনিক ডেল্টা রুবি আনারস','Fruit simulation'),
    ('synthetic_sundarban_mist_coconut','Synthetic Sundarban Mist Coconut','কাল্পনিক সুন্দরবন মিস্ট নারিকেল','Plantation simulation'),
    ('synthetic_sylhet_amber_tea','Synthetic Sylhet Amber Tea','কাল্পনিক সিলেট অ্যাম্বার চা','Plantation simulation'),
]

SUPPORTED_MAP = {
    'rice':['rice_boro','rice_aman'], 'maize':['maize'], 'wheat':['wheat'], 'potato':['potato'],
    'jute':['jute'], 'sugarcane':['sugarcane'], 'mustard':['mustard'], 'soybean':['soybean'],
    'lentil':['lentil'], 'mungbean':['mungbean'], 'onion':['onion'], 'garlic':['garlic'],
    'chilli':['chilli'], 'tomato':['tomato'], 'brinjal':['brinjal']
}

DISTRICT_SAMPLE = ['Rangpur','Rajshahi','Bogura','Jashore','Cumilla','Mymensingh','Sylhet','Khulna','Barishal','Gazipur']
MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December']


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(text: str) -> str:
    return ' '.join(text.lower().replace('_',' ').replace('-',' ').split())


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def ensure_clean() -> None:
    for p in (OUT, PATCHED_CODEBASE):
        if p.exists():
            shutil.rmtree(p)
        p.mkdir(parents=True, exist_ok=True)


def create_schema(con: sqlite3.Connection) -> None:
    con.executescript('''
    PRAGMA foreign_keys=ON;
    PRAGMA journal_mode=WAL;
    CREATE TABLE metadata(key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
    CREATE TABLE sources(
      source_id TEXT PRIMARY KEY, title TEXT NOT NULL, publisher TEXT, publication_date TEXT,
      source_url TEXT, doi TEXT, license TEXT, local_filename TEXT, sha256 TEXT,
      evidence_class TEXT NOT NULL, metadata_json TEXT NOT NULL
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
    CREATE TABLE product_source_links(
      product_id TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
      source_id TEXT NOT NULL REFERENCES sources(source_id),
      relationship TEXT NOT NULL,
      PRIMARY KEY(product_id,source_id,relationship)
    );
    CREATE TABLE codebase_crop_mapping(
      product_id TEXT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
      codebase_crop_id TEXT NOT NULL,
      mapping_type TEXT NOT NULL,
      enabled_for_planning INTEGER NOT NULL,
      PRIMARY KEY(product_id,codebase_crop_id)
    );
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
    CREATE TABLE synthetic_lineage(
      product_id TEXT PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
      generation_seed INTEGER NOT NULL,
      template_family TEXT NOT NULL,
      fictional_traits_json TEXT NOT NULL,
      intended_use TEXT NOT NULL,
      prohibition TEXT NOT NULL
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
    CREATE TABLE validation_metrics(metric TEXT PRIMARY KEY, value_json TEXT NOT NULL);
    CREATE VIRTUAL TABLE product_search_fts USING fts5(
      product_id UNINDEXED, canonical_name_en, canonical_name_bn, aliases, category, description,
      tokenize='unicode61 remove_diacritics 2'
    );
    CREATE INDEX idx_products_origin ON products(data_origin,is_synthetic);
    CREATE INDEX idx_alias_norm ON product_aliases(normalized_alias);
    CREATE INDEX idx_rag_origin ON rag_documents(source_kind,is_mock);
    CREATE INDEX idx_regional_product ON regional_profiles(product_id,district_name);
    ''')


def copy_sources(src: sqlite3.Connection, dst: sqlite3.Connection) -> None:
    wanted = ['barc_crop_zoning','frg_2024','spas_bd','curated_parser_support']
    for sid in wanted:
        r = src.execute('SELECT * FROM dataset_sources WHERE source_id=?',(sid,)).fetchone()
        if not r:
            continue
        evidence = 'official_or_peer_reviewed' if sid != 'curated_parser_support' else 'normalization_only'
        dst.execute('''INSERT INTO sources VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(
            r['source_id'],r['title'],r['publisher'],r['publication_date'],r['source_url'],r['doi'],r['license'],
            r['local_filename'],r['sha256'],evidence,r['metadata_json']))
    dst.execute('''INSERT INTO sources VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(
        'synthetic_generator_v3','AgriSense 60/40 synthetic simulation layer','Generated for hackathon testing',
        now_iso()[:10],None,None,None,'build_database.py',None,'synthetic_only',
        json_dumps({'rule':'All generated products and agronomy values are fictional and non-prescriptive.'})))


def first_bn_alias(src: sqlite3.Connection, crop_id: str) -> str | None:
    r = src.execute("SELECT alias_text FROM crop_aliases WHERE crop_id=? AND language='bn' ORDER BY alias_type='bangladesh_common' DESC, alias_id LIMIT 1",(crop_id,)).fetchone()
    return r['alias_text'] if r else None


def product_source_presence(src: sqlite3.Connection, crop_id: str) -> dict[str,int]:
    return {
        'fertilizer_tables': src.execute('SELECT COUNT(*) FROM fertilizer_crop_tables WHERE crop_id=?',(crop_id,)).fetchone()[0],
        'profiles': src.execute('SELECT COUNT(*) FROM crop_profiles WHERE crop_id=?',(crop_id,)).fetchone()[0],
        'suitability_records': src.execute('SELECT COUNT(*) FROM suitability_zones WHERE crop_id=?',(crop_id,)).fetchone()[0],
        'varieties': src.execute('SELECT COUNT(*) FROM crop_varieties WHERE crop_id=?',(crop_id,)).fetchone()[0],
    }


def insert_real_product(src: sqlite3.Connection, dst: sqlite3.Connection, crop_id: str) -> None:
    c = src.execute('SELECT * FROM crops WHERE crop_id=?',(crop_id,)).fetchone()
    if not c:
        raise RuntimeError(f'Missing crop {crop_id}')
    bn = first_bn_alias(src,crop_id)
    presence = product_source_presence(src,crop_id)
    desc = (f"Authentic Bangladesh agricultural product identity derived from supplied BARC/SPAS datasets. "
            f"Coverage: {presence['fertilizer_tables']} fertilizer table(s), {presence['profiles']} agronomic profile(s), "
            f"{presence['suitability_records']} suitability record(s), and {presence['varieties']} listed variety record(s).")
    dst.execute('''INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
        crop_id,c['canonical_name'],bn,c['scientific_name'],c['crop_group'],None,desc,'real_authentic',0,
        'source_derived',1,0,1 if crop_id in SUPPORTED_MAP else 0,0.98,now_iso()))

    aliases = src.execute('''SELECT alias_text,normalized_alias,language,script,alias_type,is_ambiguous
                             FROM crop_aliases WHERE crop_id=?
                             ORDER BY CASE alias_type WHEN 'bangladesh_common' THEN 0 WHEN 'canonical' THEN 1 ELSE 2 END, alias_id LIMIT 12''',(crop_id,)).fetchall()
    seen=set()
    for a in aliases:
        key=(a['normalized_alias'],a['alias_type'])
        if key in seen: continue
        seen.add(key)
        dst.execute('''INSERT OR IGNORE INTO product_aliases(product_id,alias_text,normalized_alias,language_code,script,alias_type,data_origin,is_ambiguous)
                       VALUES(?,?,?,?,?,?,?,?)''',(crop_id,a['alias_text'],a['normalized_alias'],a['language'],a['script'],a['alias_type'],'real_authentic',a['is_ambiguous']))
    if not aliases:
        dst.execute('''INSERT INTO product_aliases(product_id,alias_text,normalized_alias,language_code,script,alias_type,data_origin,is_ambiguous)
                       VALUES(?,?,?,?,?,?,?,0)''',(crop_id,c['canonical_name'],norm(c['canonical_name']),'en','Latin','canonical','real_authentic'))

    varieties = src.execute('''SELECT variety_name,season_context,yield_goal_raw,source_record_id,source_page,source_id
                               FROM crop_varieties WHERE crop_id=? ORDER BY variety_id LIMIT 20''',(crop_id,)).fetchall()
    for v in varieties:
        dst.execute('''INSERT OR IGNORE INTO product_varieties(product_id,variety_name,season_context,yield_goal_raw,data_origin,source_record_id,source_page,safe_for_prescriptive_advice)
                       VALUES(?,?,?,?,?,?,?,0)''',(crop_id,v['variety_name'],v['season_context'],v['yield_goal_raw'],'real_authentic',v['source_record_id'],v['source_page']))
        dst.execute('''INSERT OR IGNORE INTO product_source_links VALUES(?,?,?)''',(crop_id,v['source_id'],'variety_listing'))

    for sid, rel in [('frg_2024','fertilizer_and_variety_reference'),('curated_parser_support','alias_normalization')]:
        dst.execute('INSERT OR IGNORE INTO product_source_links VALUES(?,?,?)',(crop_id,sid,rel))
    if presence['profiles']:
        dst.execute('INSERT OR IGNORE INTO product_source_links VALUES(?,?,?)',(crop_id,'spas_bd','agronomic_profile'))
    if presence['suitability_records']:
        dst.execute('INSERT OR IGNORE INTO product_source_links VALUES(?,?,?)',(crop_id,'barc_crop_zoning','location_suitability'))

    for cb in SUPPORTED_MAP.get(crop_id,[]):
        dst.execute('INSERT INTO codebase_crop_mapping VALUES(?,?,?,1)',(crop_id,cb,'direct_or_cycle_mapping'))

    p = src.execute('SELECT * FROM crop_profiles WHERE crop_id=? ORDER BY profile_id LIMIT 1',(crop_id,)).fetchone()
    if p:
        seasons=p['seasons_json']; planting=p['planting_periods_json']; growth=p['growth_periods_json']; harvest=p['harvest_periods_json']
        temps=p['temperature_profiles_json']; humidity=p['humidity_profiles_json']
        summary=(f"Source-derived crop profile for {c['canonical_name']}. Seasons {seasons}; planting {planting}; "
                 f"growth {growth}; harvest {harvest}. Climate arrays are preserved from the uploaded SPAS restructuring.")
        evidence_note='SPAS profile values are preserved as source-derived observations; verify before field prescription.'
    else:
        seasons=planting=growth=harvest=temps=humidity='[]'
        summary=f"No SPAS crop profile was present for {c['canonical_name']}; product identity and fertilizer-table evidence remain available."
        evidence_note='Absence of a profile is preserved and must not be filled with invented agronomy.'
    dst.execute('''INSERT INTO agronomic_summaries VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(
        crop_id,seasons,planting,growth,harvest,temps,humidity,summary,'real_authentic',evidence_note,0))

    ft = src.execute('SELECT * FROM fertilizer_crop_tables WHERE crop_id=? ORDER BY table_id LIMIT 1',(crop_id,)).fetchone()
    rates=[]
    if ft:
        for rr in src.execute('''SELECT condition_text,rate_kind,nutrient_symbol,raw_value,numeric_value,min_value,max_value,plus_minus
                                 FROM fertilizer_rates WHERE table_id=? ORDER BY condition_text,rate_kind,nutrient_symbol''',(ft['table_id'],)):
            rates.append(dict(rr))
        dst.execute('''INSERT INTO fertilizer_summaries VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(
            crop_id,ft['table_id'],ft['recommendation_context'],ft['season_context'],ft['yield_goal_raw'],ft['units_raw'],
            json_dumps(rates),ft['source_page'],'real_authentic',
            'Not a blanket recommendation: use the exact soil-test condition, unit, crop context and source page before application.',0))
    else:
        dst.execute('''INSERT INTO fertilizer_summaries VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(
            crop_id,None,None,None,None,None,'[]',None,'real_authentic',
            'No fertilizer table was found for this selected authentic product.',0))

    # Preserve up to five genuine location records where available.
    regional=[]
    for rr in src.execute('''SELECT record_id,district_id,upazila_key,weighted_score,dominant_classes_json,very_suitable_percent,suitable_percent
                             FROM suitability_zones WHERE crop_id=? ORDER BY weighted_score DESC LIMIT 5''',(crop_id,)):
        d=src.execute('SELECT district_name FROM districts WHERE district_id=?',(rr['district_id'],)).fetchone()
        u=src.execute('SELECT upazila_name FROM upazilas WHERE upazila_key=?',(rr['upazila_key'],)).fetchone()
        regional.append(('suitability_score',rr['weighted_score'],'score_0_100',dict(rr),rr['record_id'],d['district_name'] if d else None,u['upazila_name'] if u else None))
    if not regional:
        for rr in src.execute('''SELECT s.record_id,d.district_name,s.yield_tonnes_per_acre,s.raw_json
                                 FROM district_crop_statistics s JOIN districts d ON d.district_id=s.district_id
                                 WHERE s.crop_id=? ORDER BY s.yield_tonnes_per_acre DESC LIMIT 5''',(crop_id,)):
            regional.append(('yield',rr['yield_tonnes_per_acre'],'metric_tonnes_per_acre',json.loads(rr['raw_json']),rr['record_id'],rr['district_name'],None))
    for i,(mt,mv,mu,payload,srid,district,upazila) in enumerate(regional,1):
        dst.execute('''INSERT INTO regional_profiles VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(
            f'real::{crop_id}::{i}',crop_id,district,upazila,mt,mv,mu,json_dumps(payload),'real_authentic',srid,0))


def synthetic_profile(index: int) -> dict[str,Any]:
    rng=random.Random(60040+index)
    start=rng.randrange(12); duration=rng.randint(3,6); harvest=(start+duration)%12
    tmin=round(rng.uniform(12,24),1); tmax=round(tmin+rng.uniform(8,16),1)
    hmin=rng.randint(45,70); hmax=min(95,hmin+rng.randint(15,25))
    nutrients={n:{'min':rng.randint(10,70),'max':rng.randint(80,180),'unit':'kg/ha','status':'synthetic'} for n in rng.sample(['N','P','K','S','Zn','B'],4)}
    return {
        'season': rng.choice(['Rabi simulation','Kharif-1 simulation','Kharif-2 simulation','Year-round simulation']),
        'planting':[MONTHS[start]], 'growth':[f'{MONTHS[start]} to {MONTHS[(start+duration-1)%12]}'],
        'harvest':[MONTHS[harvest]], 'temp':[{'minimum':tmin,'maximum':tmax}],
        'humidity':[{'minimum':hmin,'maximum':hmax}], 'nutrients':nutrients,
        'cycle_days':rng.randint(65,220)
    }


def insert_synthetic_product(dst: sqlite3.Connection, idx: int, row: tuple[str,str,str,str]) -> None:
    pid,en,bn,category=row; profile=synthetic_profile(idx)
    dst.execute('''INSERT INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
        pid,en,bn,None,category,'fictional test entity',
        'Entirely fictional product created to test retrieval, filtering, hallucination resistance and UI badges. It must never be represented as a real crop.',
        'synthetic_made_up',1,'fictional_simulation',1,0,0,0.0,now_iso()))
    aliases=[en,en.replace('Synthetic ','').lower(),pid.replace('synthetic_','').replace('_',' '),bn,f'sim crop {idx:02d}']
    for j,a in enumerate(aliases):
        lang='bn' if j==3 else 'en'
        script='Bengali' if lang=='bn' else 'Latin'
        dst.execute('''INSERT OR IGNORE INTO product_aliases(product_id,alias_text,normalized_alias,language_code,script,alias_type,data_origin,is_ambiguous)
                       VALUES(?,?,?,?,?,?,?,0)''',(pid,a,norm(a),lang,script,'synthetic_alias','synthetic_made_up'))
    for v in range(1,4):
        dst.execute('''INSERT INTO product_varieties(product_id,variety_name,season_context,yield_goal_raw,data_origin,source_record_id,source_page,safe_for_prescriptive_advice)
                       VALUES(?,?,?,?,?,?,?,0)''',(pid,f'{en} Simulation Line {v}',profile['season'],f"Synthetic target {2+v*0.5:.1f} t/ha",'synthetic_made_up',f'synthetic::{pid}::{v}',None))
    dst.execute('INSERT INTO product_source_links VALUES(?,?,?)',(pid,'synthetic_generator_v3','fictional_generation'))
    dst.execute('''INSERT INTO agronomic_summaries VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(
        pid,json_dumps([profile['season']]),json_dumps(profile['planting']),json_dumps(profile['growth']),json_dumps(profile['harvest']),
        json_dumps(profile['temp']),json_dumps(profile['humidity']),
        f"Synthetic agronomic profile with a {profile['cycle_days']}-day fictional cycle.",
        'synthetic_made_up','Generated with deterministic seed; not observational data and not farming advice.',0))
    dst.execute('''INSERT INTO fertilizer_summaries VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(
        pid,None,'fictional simulation',profile['season'],'Synthetic yield target','kg/ha',json_dumps(profile['nutrients']),None,
        'synthetic_made_up','Fictional nutrient values for software testing only. Never apply in a field.',0))
    rng=random.Random(70000+idx)
    for j,district in enumerate(rng.sample(DISTRICT_SAMPLE,5),1):
        payload={'suitability_score_0_100':rng.randint(25,95),'cycle_days':profile['cycle_days'],'simulated_output_range_t_ha':[round(rng.uniform(1,4),2),round(rng.uniform(4.5,9),2)]}
        dst.execute('''INSERT INTO regional_profiles VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(
            f'synthetic::{pid}::{j}',pid,district,None,'simulated_suitability',payload['suitability_score_0_100'],'score_0_100',
            json_dumps(payload),'synthetic_made_up',f'synthetic::{pid}::{district}',0))
    dst.execute('''INSERT INTO synthetic_lineage VALUES(?,?,?,?,?,?)''',(
        pid,60040+idx,category,json_dumps(profile),
        'Hackathon retrieval/filtering, adversarial tests and UI demonstrations.',
        'Do not present as authentic, do not recommend cultivation, and do not merge into official evidence.'))


def build_rag_docs(dst: sqlite3.Connection) -> None:
    products=dst.execute('SELECT * FROM products ORDER BY product_id').fetchall()
    for p in products:
        pid=p['product_id']; is_mock=p['is_synthetic']; origin=p['data_origin']
        aliases=[r['alias_text'] for r in dst.execute('SELECT alias_text FROM product_aliases WHERE product_id=? ORDER BY alias_id',(pid,))]
        varieties=[r['variety_name'] for r in dst.execute('SELECT variety_name FROM product_varieties WHERE product_id=? ORDER BY variety_id LIMIT 12',(pid,))]
        agr=dst.execute('SELECT * FROM agronomic_summaries WHERE product_id=?',(pid,)).fetchone()
        fert=dst.execute('SELECT * FROM fertilizer_summaries WHERE product_id=?',(pid,)).fetchone()
        maps=[r['codebase_crop_id'] for r in dst.execute('SELECT codebase_crop_id FROM codebase_crop_mapping WHERE product_id=?',(pid,))]
        source_kind='authentic_mixed_catalog_60' if not is_mock else 'synthetic_mixed_catalog_40'
        source='BARC/SPAS supplied datasets' if not is_mock else 'AgriSense deterministic synthetic generator v3'
        crop_id=maps[0] if len(maps)==1 else (pid if pid in SUPPORTED_MAP else None)
        common_meta={'product_id':pid,'data_origin':origin,'is_synthetic':bool(is_mock),'safe_for_prescriptive_advice':False,'codebase_crop_ids':maps}
        docs=[
          (f'mixed60_40::{pid}::identity',f"{p['canonical_name_en']} identity and aliases",
           f"Product: {p['canonical_name_en']}. Bangla name: {p['canonical_name_bn'] or 'not available'}. Scientific name: {p['scientific_name'] or 'not assigned'}. Category: {p['category']}. Data origin: {origin}. Description: {p['description']} Aliases: {', '.join(aliases)}.",'product_identity'),
          (f'mixed60_40::{pid}::agronomy',f"{p['canonical_name_en']} agronomic profile",
           f"Data origin: {origin}. {agr['summary_text']} Seasons: {agr['seasons_json']}. Planting: {agr['planting_periods_json']}. Growth: {agr['growth_periods_json']}. Harvest: {agr['harvest_periods_json']}. Temperature profiles: {agr['temperature_profiles_json']}. Humidity profiles: {agr['humidity_profiles_json']}. Warning: {agr['evidence_note']}",'agronomic_summary'),
          (f'mixed60_40::{pid}::fertilizer',f"{p['canonical_name_en']} fertilizer evidence",
           f"Data origin: {origin}. Context: {fert['recommendation_context']}. Season: {fert['season_context']}. Yield goal: {fert['yield_goal_raw']}. Units: {fert['units_raw']}. Rates: {fert['rates_json']}. Warning: {fert['interpretation_warning']}. Varieties: {', '.join(varieties)}.",'fertilizer_evidence'),
        ]
        for doc_id,title,content,kt in docs:
            meta=dict(common_meta); meta['knowledge_type']=kt
            dst.execute('''INSERT INTO rag_documents VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
                doc_id,pid,title,content,source,source_kind,is_mock,crop_id,pid,None,None,kt,json_dumps(meta),0))


def populate_fts(dst: sqlite3.Connection) -> None:
    for p in dst.execute('SELECT * FROM products'):
        aliases=' | '.join(r['alias_text'] for r in dst.execute('SELECT alias_text FROM product_aliases WHERE product_id=?',(p['product_id'],)))
        dst.execute('INSERT INTO product_search_fts VALUES(?,?,?,?,?,?)',(
            p['product_id'],p['canonical_name_en'],p['canonical_name_bn'] or '',aliases,p['category'] or '',p['description']))


def export_files(dst: sqlite3.Connection) -> None:
    exports=OUT/'exports'; exports.mkdir(exist_ok=True)
    for table in ['products','product_aliases','product_varieties','agronomic_summaries','fertilizer_summaries','regional_profiles','rag_documents']:
        rows=dst.execute(f'SELECT * FROM {table}').fetchall()
        if rows:
            with (exports/f'{table}.csv').open('w',newline='',encoding='utf-8') as f:
                w=csv.writer(f); w.writerow(rows[0].keys()); w.writerows([tuple(r) for r in rows])
    with (OUT/'rag_documents.jsonl').open('w',encoding='utf-8') as f:
        for r in dst.execute('SELECT * FROM rag_documents ORDER BY document_id'):
            payload={k:r[k] for k in r.keys() if k not in {'safe_for_prescriptive_advice'}}
            f.write(json.dumps(payload,ensure_ascii=False)+'\n')
    catalog={
        'metadata':{r['key']:json.loads(r['value_json']) for r in dst.execute('SELECT * FROM metadata')},
        'products':[dict(r) for r in dst.execute('SELECT * FROM products ORDER BY product_id')]
    }
    with gzip.open(OUT/'catalog.json.gz','wt',encoding='utf-8') as f: json.dump(catalog,f,ensure_ascii=False)


def validate(dst: sqlite3.Connection) -> dict[str,Any]:
    integrity=dst.execute('PRAGMA integrity_check').fetchone()[0]
    fk=[tuple(r) for r in dst.execute('PRAGMA foreign_key_check')]
    total=dst.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    real=dst.execute("SELECT COUNT(*) FROM products WHERE data_origin='real_authentic'").fetchone()[0]
    synthetic=dst.execute("SELECT COUNT(*) FROM products WHERE data_origin='synthetic_made_up'").fetchone()[0]
    rag_real=dst.execute('SELECT COUNT(*) FROM rag_documents WHERE is_mock=0').fetchone()[0]
    rag_syn=dst.execute('SELECT COUNT(*) FROM rag_documents WHERE is_mock=1').fetchone()[0]
    unsafe=dst.execute("SELECT COUNT(*) FROM products WHERE is_synthetic=1 AND (safe_for_prescriptive_advice=1 OR eligible_for_recommendation=1)").fetchone()[0]
    overlap=dst.execute("SELECT COUNT(*) FROM products WHERE data_origin='real_authentic' AND canonical_name_en LIKE 'Synthetic %'").fetchone()[0]
    supported=dst.execute('SELECT COUNT(DISTINCT product_id) FROM codebase_crop_mapping WHERE enabled_for_planning=1').fetchone()[0]
    report={
        'generated_at_utc':now_iso(),'sqlite_integrity':integrity,'foreign_key_violations':len(fk),
        'products_total':total,'real_authentic_products':real,'synthetic_made_up_products':synthetic,
        'real_percent':real/total*100,'synthetic_percent':synthetic/total*100,
        'rag_real_documents':rag_real,'rag_synthetic_documents':rag_syn,
        'rag_real_percent':rag_real/(rag_real+rag_syn)*100,
        'synthetic_safety_violations':unsafe,'real_named_synthetic_overlap':overlap,
        'products_mapped_to_existing_planner':supported,
        'status':'PASS' if integrity=='ok' and not fk and total==100 and real==60 and synthetic==40 and unsafe==0 else 'FAIL'
    }
    for k,v in report.items():
        dst.execute('INSERT OR REPLACE INTO validation_metrics VALUES(?,?)',(k,json_dumps(v)))
    return report


def write_docs(report: dict[str,Any]) -> None:
    readme=f'''# Bangladesh Agriculture 60/40 Mixed Database v3

This package contains an exact **60% real/authentic + 40% made-up** product catalog designed for AgriSense.

## Composition

- 100 product entities
- 60 authentic crop/horticulture products taken from the supplied BARC/SPAS-derived master database
- 40 entirely fictional products generated for testing
- 300 RAG documents: 180 authentic and 120 synthetic, preserving the same 60/40 ratio
- Synthetic records are blocked from prescriptive advice and crop recommendation
- {report['products_mapped_to_existing_planner']} authentic products map to the current Tier-0 planning crop enum

## Important safety rule

`data_origin`, `is_synthetic`, `safe_for_prescriptive_advice`, and `eligible_for_recommendation` are mandatory filters. Synthetic records may be used for UI, retrieval and adversarial tests only.

## Files

- `bangladesh_agri_60_40.db` — normalized SQLite database
- `rag_documents.jsonl` — codebase-compatible RAG export
- `catalog.json.gz` — compressed product catalog
- `exports/` — CSV exports
- `INTEGRATION_GUIDE.md` — detailed codebase integration process
- `schema.sql` — SQL schema
- `build_database.py` — reproducible builder
- `validation_report.json` — integrity and ratio checks
- `AgriSense_60_40_DB_Integrated.zip` — patched runnable codebase, delivered separately

## Authentic-data interpretation

The authentic side preserves source-derived identity, aliases, varieties, crop profiles, fertilizer table context and available location evidence. Fertilizer values are not blanket prescriptions: they depend on the source table's crop context, units, soil-test condition, AEZ and yield goal.

## Synthetic-data interpretation

All fictional products begin with `Synthetic` and carry `data_origin='synthetic_made_up'`. Their calendars, climate ranges, fertilizer values and district scores are deterministic simulation values, not observations.
'''
    (OUT/'README.md').write_text(readme,encoding='utf-8')

    guide='''# AgriSense database integration guide

## 1. What the existing codebase does

The uploaded project uses FastAPI, a runtime SQLite database for users/sessions, and a separate SQLite hybrid RAG database. `scripts/build_rag.py` calls `app.services.ingestion.build_rag()`. That function converts source records into documents and inserts them into `data/processed/rag.sqlite3`. Retrieval uses FTS5 plus deterministic 384-dimensional hash embeddings.

Do not replace `data/runtime/agrisense.sqlite3` with this catalog. Runtime memory and agricultural knowledge are different databases.

## 2. Integration architecture

```text
bangladesh_agri_60_40.db
  ├─ products / aliases / varieties
  ├─ agronomic and fertilizer summaries
  ├─ real/synthetic provenance and safety fields
  └─ rag_documents
           │
           ▼
app/services/mixed_catalog.py
           │ yields existing RAG document dictionaries
           ▼
app/services/ingestion.py::build_rag()
           │
           ▼
data/processed/rag.sqlite3
           │
           ├─ /v1/rag/search
           ├─ recommendation evidence retrieval
           └─ planner evidence retrieval
```

## 3. Files added to the patched codebase

- `data/raw/mixed_60_40/bangladesh_agri_60_40.db`
- `app/services/mixed_catalog.py`
- `tests/test_mixed_catalog.py`
- `docs/MIXED_DATABASE_INTEGRATION.md`

Files changed:

- `app/config.py`: adds `mixed_catalog_db_path`
- `app/services/ingestion.py`: inserts mixed-catalog RAG documents
- `app/dependencies.py`: exposes a catalog repository
- `app/api/routes.py`: adds catalog endpoints and source-policy labels

## 4. Rebuild sequence

```bash
cd sandbox
source .venv/bin/activate
python scripts/build_rag.py --force
pytest -q
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The builder reads the mixed catalog, marks authentic records as `is_mock=0`, marks fictional records as `is_mock=1`, and records counts in `rag_metadata`.

## 5. API usage

### Catalog stats

```bash
curl http://localhost:8000/v1/catalog/stats
```

### Search authentic products only — default

```bash
curl 'http://localhost:8000/v1/catalog/products?query=begun&limit=10'
```

### Include fictional test entities

```bash
curl 'http://localhost:8000/v1/catalog/products?query=synthetic&include_synthetic=true&limit=10'
```

### RAG search excluding made-up data

```bash
curl -X POST http://localhost:8000/v1/rag/search \
  -H 'content-type: application/json' \
  -d '{"query":"brinjal fertilizer evidence","top_k":8,"include_mock":false}'
```

### RAG search including made-up test data

```bash
curl -X POST http://localhost:8000/v1/rag/search \
  -H 'content-type: application/json' \
  -d '{"query":"synthetic crop simulation","top_k":8,"include_mock":true}'
```

## 6. Recommendation-layer rule

Only products in `codebase_crop_mapping` with `enabled_for_planning=1` may enter the current `CropRecommender`. The 40 fictional products have no mapping and `eligible_for_recommendation=0`. This prevents a retrieved fictional document from becoming a cultivation recommendation.

The current planner supports 16 crop-cycle IDs. The catalog can contain more authentic products for lookup and RAG without automatically expanding the planner. To support a new real crop in planning, add all of these together:

1. `crop_master.jsonl`
2. crop calendar
3. suitability rules
4. fertilizer plan
5. irrigation plan
6. economics assumptions
7. stage plan
8. pest/disease rows
9. `CROP_DURATIONS`
10. source-to-planner mapping
11. deterministic tests

Do not add a crop to the planner merely because its name exists in the catalog.

## 7. Frontend integration

Use the catalog API for autocomplete and badges:

```javascript
const response = await fetch(
  `/v1/catalog/products?query=${encodeURIComponent(input)}&include_synthetic=false&limit=8`
);
const { products } = await response.json();
```

Show these fields:

- `canonical_name_en`
- `canonical_name_bn`
- `data_origin`
- `is_synthetic`
- `eligible_for_recommendation`
- `aliases`

Recommended badges:

- Authentic source-derived
- Synthetic test data
- Planner-supported
- Lookup only

Never hide the synthetic badge when `is_synthetic=true`.

## 8. Production migration

SQLite is suitable for the hackathon. For production PostgreSQL:

1. Recreate normalized tables with UUID/text primary keys.
2. Keep provenance and safety fields `NOT NULL`.
3. Add trigram indexes for aliases.
4. Move embeddings to pgvector or Qdrant.
5. Keep the runtime user/session database logically separate.
6. Add versioned dataset releases and immutable source hashes.
7. Add an approval workflow before any record can set `safe_for_prescriptive_advice=true`.

## 9. Update workflow

```text
new source files
  -> staging tables
  -> normalization and alias review
  -> source hash and provenance
  -> validation
  -> release database
  -> rebuild RAG
  -> regression tests
  -> deploy
```

Never overwrite authentic rows with synthetic gap fills. Store missing values as missing, and add synthetic alternatives as separate records with explicit origin fields.

## 10. Required tests

- exact 60/40 product ratio
- exact 60/40 RAG-document ratio
- synthetic products absent when `include_synthetic=false`
- synthetic documents absent when `include_mock=false`
- no synthetic product is planner-eligible
- Bangla and Banglish alias lookup
- SQLite integrity and foreign keys
- RAG rebuild count and health endpoint
- regression test for all existing 16 planning crops
'''
    (OUT/'INTEGRATION_GUIDE.md').write_text(guide,encoding='utf-8')


def write_schema(con: sqlite3.Connection) -> None:
    sql='\n\n'.join(r[0]+';' for r in con.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type,name"))
    (OUT/'schema.sql').write_text(sql,encoding='utf-8')


def patch_codebase() -> None:
    shutil.copytree(CODEBASE_SOURCE,PATCHED_CODEBASE,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.venv','.pytest_cache','__pycache__','*.pyc','*.sqlite3-shm','*.sqlite3-wal'))
    mixed_dir=PATCHED_CODEBASE/'data/raw/mixed_60_40'; mixed_dir.mkdir(parents=True,exist_ok=True)
    shutil.copy2(DB_PATH,mixed_dir/'bangladesh_agri_60_40.db')

    service=(PATCHED_CODEBASE/'app/services/mixed_catalog.py')
    service.write_text('''from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable


class MixedCatalogRepository:
    def __init__(self, path: Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        con.row_factory = sqlite3.Row
        return con

    def stats(self) -> dict[str, Any]:
        with self.connect() as con:
            total = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            rows = con.execute("SELECT data_origin, COUNT(*) count FROM products GROUP BY data_origin").fetchall()
            rag = con.execute("SELECT is_mock, COUNT(*) count FROM rag_documents GROUP BY is_mock").fetchall()
        return {"products": total, "by_origin": [dict(r) for r in rows], "rag_documents": [dict(r) for r in rag]}

    def search_products(self, query: str, *, include_synthetic: bool = False, limit: int = 20) -> list[dict[str, Any]]:
        query = query.strip()
        with self.connect() as con:
            filters = [] if include_synthetic else ["p.is_synthetic=0"]
            params: list[Any] = []
            if query:
                filters.append("product_search_fts MATCH ?")
                params.append(" OR ".join(f'\"{token}\"' for token in query.lower().split() if token))
                sql = """
                    SELECT p.* FROM product_search_fts f
                    JOIN products p ON p.product_id=f.product_id
                """
            else:
                sql = "SELECT p.* FROM products p"
            if filters:
                sql += " WHERE " + " AND ".join(filters)
            sql += " ORDER BY p.is_synthetic, p.canonical_name_en LIMIT ?"
            params.append(max(1, min(limit, 100)))
            rows = con.execute(sql, params).fetchall()
            result=[]
            for row in rows:
                item=dict(row)
                item['aliases']=[r[0] for r in con.execute("SELECT alias_text FROM product_aliases WHERE product_id=? ORDER BY alias_id LIMIT 12",(row['product_id'],))]
                item['codebase_crop_ids']=[r[0] for r in con.execute("SELECT codebase_crop_id FROM codebase_crop_mapping WHERE product_id=? AND enabled_for_planning=1",(row['product_id'],))]
                result.append(item)
            return result

    def get_product(self, product_id: str) -> dict[str, Any] | None:
        with self.connect() as con:
            row=con.execute("SELECT * FROM products WHERE product_id=?",(product_id,)).fetchone()
            if not row: return None
            item=dict(row)
            item['aliases']=[dict(r) for r in con.execute("SELECT * FROM product_aliases WHERE product_id=? ORDER BY alias_id",(product_id,))]
            item['varieties']=[dict(r) for r in con.execute("SELECT * FROM product_varieties WHERE product_id=? ORDER BY variety_id",(product_id,))]
            agr=con.execute("SELECT * FROM agronomic_summaries WHERE product_id=?",(product_id,)).fetchone()
            fert=con.execute("SELECT * FROM fertilizer_summaries WHERE product_id=?",(product_id,)).fetchone()
            item['agronomic_summary']=dict(agr) if agr else None
            item['fertilizer_summary']=dict(fert) if fert else None
            item['codebase_crop_ids']=[r[0] for r in con.execute("SELECT codebase_crop_id FROM codebase_crop_mapping WHERE product_id=? AND enabled_for_planning=1",(product_id,))]
            return item


def iter_rag_documents(path: Path) -> Iterable[dict[str, Any]]:
    if not Path(path).exists():
        return
    con=sqlite3.connect(path)
    con.row_factory=sqlite3.Row
    try:
        for row in con.execute("SELECT * FROM rag_documents ORDER BY document_id"):
            yield {
                "document_id": row["document_id"], "title": row["title"], "content": row["content"],
                "source": row["source"], "source_kind": row["source_kind"], "is_mock": bool(row["is_mock"]),
                "crop_id": row["crop_id"], "crop_group": row["crop_group"], "district": row["district"],
                "upazila": row["upazila"], "knowledge_type": row["knowledge_type"], "metadata_json": row["metadata_json"],
            }
    finally:
        con.close()
''',encoding='utf-8')

    config=PATCHED_CODEBASE/'app/config.py'
    txt=config.read_text(encoding='utf-8')
    txt=txt.replace("    raw_mock_kb_dir: Path = BASE_DIR / \"data/raw/mock_agri_kb\"\n", "    raw_mock_kb_dir: Path = BASE_DIR / \"data/raw/mock_agri_kb\"\n    mixed_catalog_db_path: Path = BASE_DIR / \"data/raw/mixed_60_40/bangladesh_agri_60_40.db\"\n")
    config.write_text(txt,encoding='utf-8')

    ingestion=PATCHED_CODEBASE/'app/services/ingestion.py'
    txt=ingestion.read_text(encoding='utf-8')
    txt=txt.replace('from app.services.rag import initialize_rag_schema, insert_documents\n','from app.services.rag import initialize_rag_schema, insert_documents\nfrom app.services.mixed_catalog import iter_rag_documents as mixed_catalog_documents\n')
    txt=txt.replace('        generated_count = insert_documents(connection, generated_documents(settings))\n', '        generated_count = insert_documents(connection, generated_documents(settings))\n        mixed_catalog_count = insert_documents(connection, mixed_catalog_documents(settings.mixed_catalog_db_path))\n')
    txt=txt.replace('            "generated_mock_gap_documents": str(generated_count),\n', '            "generated_mock_gap_documents": str(generated_count),\n            "mixed_catalog_documents": str(mixed_catalog_count),\n')
    txt=txt.replace('        "generated_mock_gap_documents": generated_count,\n', '        "generated_mock_gap_documents": generated_count,\n        "mixed_catalog_documents": mixed_catalog_count,\n')
    ingestion.write_text(txt,encoding='utf-8')

    deps=PATCHED_CODEBASE/'app/dependencies.py'
    txt=deps.read_text(encoding='utf-8')
    txt=txt.replace('from app.services.memory import MemoryService\n','from app.services.memory import MemoryService\nfrom app.services.mixed_catalog import MixedCatalogRepository\n')
    txt=txt.replace('    memory: MemoryService\n','    memory: MemoryService\n    catalog: MixedCatalogRepository\n')
    txt=txt.replace('        memory=memory,\n','        memory=memory,\n        catalog=MixedCatalogRepository(settings.mixed_catalog_db_path),\n')
    deps.write_text(txt,encoding='utf-8')

    routes=PATCHED_CODEBASE/'app/api/routes.py'
    txt=routes.read_text(encoding='utf-8')
    marker='\n\n@router.post("/v1/auth/signup", response_model=AuthResponse)\n'
    addition='''

@router.get("/v1/catalog/stats")
def mixed_catalog_stats() -> dict[str, Any]:
    return get_services().catalog.stats()


@router.get("/v1/catalog/products")
def mixed_catalog_search(
    query: str = Query(default="", max_length=200),
    include_synthetic: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    products = get_services().catalog.search_products(query, include_synthetic=include_synthetic, limit=limit)
    return {"query": query, "include_synthetic": include_synthetic, "products": products}


@router.get("/v1/catalog/products/{product_id}")
def mixed_catalog_product(product_id: str) -> dict[str, Any]:
    product = get_services().catalog.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
'''
    txt=txt.replace(marker,addition+marker)
    txt=txt.replace('        "generated_mock_gap": "Synthetic missing fields generated by this sandbox and always tagged mock.",\n', '        "generated_mock_gap": "Synthetic missing fields generated by this sandbox and always tagged mock.",\n        "authentic_mixed_catalog_60": "Source-derived product catalog records; lookup/RAG evidence, not automatic prescriptions.",\n        "synthetic_mixed_catalog_40": "Fictional test records; excluded when include_mock=false and never planner-eligible.",\n')
    routes.write_text(txt,encoding='utf-8')

    tests=PATCHED_CODEBASE/'tests/test_mixed_catalog.py'
    tests.write_text('''from app.config import get_settings
from app.services.mixed_catalog import MixedCatalogRepository, iter_rag_documents


def test_mixed_catalog_ratio_and_safety():
    repo=MixedCatalogRepository(get_settings().mixed_catalog_db_path)
    stats=repo.stats()
    assert stats["products"] == 100
    origins={row["data_origin"]: row["count"] for row in stats["by_origin"]}
    assert origins == {"real_authentic": 60, "synthetic_made_up": 40}
    assert all(not item["is_synthetic"] for item in repo.search_products("", include_synthetic=False, limit=100))


def test_rag_export_ratio():
    docs=list(iter_rag_documents(get_settings().mixed_catalog_db_path))
    assert len(docs) == 300
    assert sum(not d["is_mock"] for d in docs) == 180
    assert sum(d["is_mock"] for d in docs) == 120
''',encoding='utf-8')
    docs=PATCHED_CODEBASE/'docs/MIXED_DATABASE_INTEGRATION.md'
    docs.write_text((OUT/'INTEGRATION_GUIDE.md').read_text(encoding='utf-8'),encoding='utf-8')
    # Add README note.
    readme=PATCHED_CODEBASE/'README.md'
    rtxt=readme.read_text(encoding='utf-8')
    rtxt += '\n\n## 60/40 mixed product catalog\n\nThis build includes `data/raw/mixed_60_40/bangladesh_agri_60_40.db`: 60 authentic product identities and 40 explicitly fictional test products. Use `/v1/catalog/*` for lookup and `include_mock=false` to exclude all fictional RAG documents. See `docs/MIXED_DATABASE_INTEGRATION.md`.\n'
    readme.write_text(rtxt,encoding='utf-8')


def package_codebase() -> Path:
    zip_path=ROOT/'AgriSense_60_40_DB_Integrated.zip'
    if zip_path.exists(): zip_path.unlink()
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
        for p in PATCHED_CODEBASE.rglob('*'):
            if p.is_file(): z.write(p,p.relative_to(PATCHED_CODEBASE.parent))
    return zip_path


def package_database() -> Path:
    zip_path=ROOT/'bangladesh_agri_60_real_40_synthetic_v3.zip'
    if zip_path.exists(): zip_path.unlink()
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
        for p in OUT.rglob('*'):
            if p.is_file(): z.write(p,p.relative_to(OUT.parent))
    return zip_path


def main() -> None:
    ensure_clean()
    if not MASTER_DB.exists(): raise FileNotFoundError(MASTER_DB)
    src=sqlite3.connect(MASTER_DB); src.row_factory=sqlite3.Row
    dst=sqlite3.connect(DB_PATH); dst.row_factory=sqlite3.Row
    try:
        create_schema(dst); copy_sources(src,dst)
        for cid in REAL_IDS: insert_real_product(src,dst,cid)
        for i,row in enumerate(SYNTHETIC_PRODUCTS,1): insert_synthetic_product(dst,i,row)
        build_rag_docs(dst); populate_fts(dst)
        meta={
            'dataset_id':'bangladesh_agri_60_real_40_synthetic_v3',
            'title':'Bangladesh agriculture mixed catalog: 60 authentic and 40 synthetic products',
            'generated_at_utc':now_iso(),'ratio_basis':'product entities and equal document count per product',
            'real_product_count':60,'synthetic_product_count':40,
            'real_definition':'Source-derived identity and evidence from supplied BARC/SPAS datasets.',
            'synthetic_definition':'Fictional products and deterministic simulated values for software testing only.',
            'safety_policy':'Synthetic records are never planner eligible and never safe for prescriptive advice.'
        }
        for k,v in meta.items(): dst.execute('INSERT INTO metadata VALUES(?,?)',(k,json_dumps(v)))
        report=validate(dst); dst.commit()
        write_schema(dst); export_files(dst)
    finally:
        dst.close(); src.close()
    (OUT/'validation_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copy2(Path(__file__),OUT/'build_database.py')
    write_docs(report)
    patch_codebase()
    code_zip=package_codebase(); db_zip=package_database()
    print(json.dumps({'database_zip':str(db_zip),'codebase_zip':str(code_zip),'report':report},indent=2))

if __name__=='__main__':
    main()
