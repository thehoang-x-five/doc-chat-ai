@startuml
!theme plain
title ERD (DB) - Hệ thống RAG cho Sinh viên 
left to right direction
hide circle
skinparam linetype ortho

entity "users" as users {
  id : UUID <<PK>>
  --
  email : varchar(255) <<UQ>>
  password_hash : varchar(255)
  full_name : varchar(255)
  role_global : varchar(50)
  created_at : timestamptz
  updated_at : timestamptz
  last_login_at : timestamptz
}

entity "refresh_tokens" as refresh_tokens {
  id : UUID <<PK>>
  --
  user_id : UUID <<FK>>
  token_hash : varchar(255)
  expires_at : timestamptz
  created_at : timestamptz
  revoked_at : timestamptz
  ip_address : varchar(45)
}

entity "workspaces" as workspaces {
  id : UUID <<PK>>
  --
  name : varchar(255)
  owner_id : UUID <<FK>>
  plan : varchar(50)
  answer_policy : varchar(20)
  evidence_threshold : float
  created_at : timestamptz
}

entity "workspace_users" as workspace_users {
  workspace_id : UUID <<PK,FK>>
  user_id : UUID <<PK,FK>>
  --
  role : varchar(20)
  joined_at : timestamptz
}

entity "document_categories" as document_categories {
  id : UUID <<PK>>
  --
  workspace_id : UUID <<FK>>
  name : varchar(255)
  slug : varchar(255)
  description : text
  content_summary : text
  keywords : text[]
  icon : varchar(50)
  color : varchar(20)
  display_order : int
  is_auto_generated : bool
  created_at : timestamptz
  updated_at : timestamptz
  UNIQUE(workspace_id, slug) : <<UQ>>
}

entity "documents" as documents {
  id : UUID <<PK>>
  --
  workspace_id : UUID <<FK>>
  category_id : UUID <<FK>> ' nullable
  title : varchar(500)
  doc_type : varchar(50)
  source : varchar(50)
  tags : text[]
  status : varchar(20)
  processing_progress : int
  processing_step : varchar(100)
  content_summary : text
  main_headings : text[]
  created_by : UUID <<FK>>
  created_at : timestamptz
  updated_at : timestamptz
}

entity "document_versions" as document_versions {
  id : UUID <<PK>>
  --
  document_id : UUID <<FK>>
  version : int
  original_file_key : varchar(500)
  mime_type : varchar(100)
  size_bytes : bigint
  checksum_sha256 : varchar(64)
  parser : varchar(50)
  parse_method : varchar(20)
  language_detected : varchar(10)
  page_count : int
  extracted_text_key : varchar(500)
  extracted_md_key : varchar(500)
  structured_json_key : varchar(500)
  created_at : timestamptz
  UNIQUE(document_id, version) : <<UQ>>
}

entity "chunks" as chunks {
  id : UUID <<PK>>
  --
  document_version_id : UUID <<FK>>
  chunk_index : int
  content : text
  token_count : int
  page_start : int
  page_end : int
  bbox_json : jsonb
  section_title : varchar(500)
  hash : varchar(64)
  chunk_type : varchar(50)
  entities : text[]
  topics : text[]
  summary : varchar(500)
  importance_score : float
  embedding : vector(768)
  created_at : timestamptz
  UNIQUE(document_version_id, chunk_index) : <<UQ>>
}

entity "conversations" as conversations {
  id : UUID <<PK>>
  --
  workspace_id : UUID <<FK>>
  title : varchar(500)
  scope_tags : text[]
  created_by : UUID <<FK>>
  created_at : timestamptz
  updated_at : timestamptz
  deleted_at : timestamptz
}

entity "messages" as messages {
  id : UUID <<PK>>
  --
  conversation_id : UUID <<FK>>
  role : varchar(20)
  content : text
  provider : varchar(50)
  model : varchar(100)
  prompt_tokens : int
  completion_tokens : int
  latency_ms : int
  policy_mode : varchar(20)
  best_retrieval_score : float
  fallback_used : bool
  created_at : timestamptz
}

entity "citations" as citations {
  id : UUID <<PK>>
  --
  message_id : UUID <<FK>>
  chunk_id : UUID <<FK>>
  score : float
  quote : text
  page : int
  created_at : timestamptz
}

entity "jobs" as jobs {
  id : UUID <<PK>>
  --
  workspace_id : UUID <<FK>>
  document_version_id : UUID <<FK>> ' nullable
  type : varchar(20)
  status : varchar(20)
  progress : int
  step : varchar(100)
  error_message : text
  config_json : jsonb
  started_at : timestamptz
  finished_at : timestamptz
  created_at : timestamptz
}

entity "ai_usage" as ai_usage {
  id : UUID <<PK>>
  --
  workspace_id : UUID <<FK>>
  job_id : UUID <<FK>> ' nullable
  message_id : UUID <<FK>> ' nullable
  provider : varchar(50)
  model : varchar(100)
  tokens_in : int
  tokens_out : int
  cost_usd : numeric(12,6)
  created_at : timestamptz
}

entity "embedding_models" as embedding_models {
  id : UUID <<PK>>
  --
  name : varchar(255) <<UQ>>
  provider : varchar(50)
  dimension : int
  is_active : bool
  is_default : bool
  config_json : jsonb
  created_at : timestamptz
}

entity "chunk_embeddings" as chunk_embeddings {
  id : UUID <<PK>>
  --
  chunk_id : UUID <<FK>>
  embedding_model_id : UUID <<FK>>
  embedding : vector(768)
  created_at : timestamptz
  UNIQUE(chunk_id, embedding_model_id) : <<UQ>>
}

entity "memori_entities" as memori_entities {
  id : serial <<PK>>
  --
  external_id : varchar(255) <<UQ>>
  workspace_id : UUID <<FK>>
  created_at : timestamptz
  updated_at : timestamptz
}

entity "memori_entity_facts" as memori_entity_facts {
  id : serial <<PK>>
  --
  entity_id : int <<FK>>
  content : text
  content_embedding : bytea
  conversation_id : UUID <<FK>> ' nullable
  importance_score : float
  last_accessed_at : timestamptz
  created_at : timestamptz
}

entity "memori_knowledge_graph" as memori_knowledge_graph {
  id : serial <<PK>>
  --
  entity_id : int <<FK>>
  subject_name : varchar(255)
  subject_type : varchar(100)
  predicate : varchar(255)
  object_name : varchar(255)
  object_type : varchar(100)
  conversation_id : UUID <<FK>> ' nullable
  confidence : float
  created_at : timestamptz
  valid_at : timestamptz
  invalid_at : timestamptz
  expired_at : timestamptz
}

' Relationships
users ||--o{ refresh_tokens
users ||--o{ workspaces
users ||--o{ workspace_users
workspaces ||--o{ workspace_users
workspaces ||--o{ document_categories
workspaces ||--o{ documents
document_categories ||--o{ documents
users ||--o{ documents
documents ||--o{ document_versions
document_versions ||--o{ chunks
workspaces ||--o{ conversations
users ||--o{ conversations
conversations ||--o{ messages
messages ||--o{ citations
chunks ||--o{ citations
workspaces ||--o{ jobs
document_versions ||--o{ jobs
workspaces ||--o{ ai_usage
jobs ||--o{ ai_usage
messages ||--o{ ai_usage
embedding_models ||--o{ chunk_embeddings
chunks ||--o{ chunk_embeddings
workspaces ||--o{ memori_entities
memori_entities ||--o{ memori_entity_facts
conversations ||--o{ memori_entity_facts
memori_entities ||--o{ memori_knowledge_graph
conversations ||--o{ memori_knowledge_graph

@enduml