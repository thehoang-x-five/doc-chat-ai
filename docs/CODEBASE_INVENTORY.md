# ??? TheDocAI Codebase Inventory

This document contains an exhaustive list of all source files and their exported functions/classes.

## ?? Backend (Python)

### server\app\api\deps.py
- **Standalone Functions:**
  - get_redis, get_current_user, get_current_user_optional, get_storage_path, get_max_file_size, resolve_workspace_id, get_workspace_id

### server\app\api\v1\analytics.py
- **Standalone Functions:**
  - get_usage_summary, get_usage_by_provider, get_usage_by_model, get_daily_usage, get_dashboard_stats, get_recent_activity, get_cost_breakdown

### server\app\api\v1\apikeys.py
- **Classes:**
  - ApiKeyInfo
  - SaveApiKeyRequest
  - TestApiKeyResponse
- **Standalone Functions:**
  - get_api_keys, save_api_key, delete_api_key, test_api_key, _test_provider_key, get_user_api_key

### server\app\api\v1\auth.py
- **Standalone Functions:**
  - get_client_ip, register, login, refresh_token, logout, request_otp, verify_otp, forgot_password, change_password, get_current_user_info

### server\app\api\v1\categories.py
- **Classes:**
  - CategoryCreate
  - CategoryUpdate
  - CategoryResponse
  - CategoryListResponse
  - SetCategoryRequest
- **Standalone Functions:**
  - list_categories, create_category, update_category, delete_category, refresh_category_summary, categorize_document, set_document_category

### server\app\api\v1\chat.py
- **Standalone Functions:**
  - _check_rate_limit, _release_stream, check_workspace_access, get_conversation_message_count, create_conversation, list_conversations, get_conversation, update_conversation, delete_conversation, get_messages, get_message_citations, send_message, stateless_query, stream_query, orchestrated_query, direct_chat, get_conversation_stats

### server\app\api\v1\cloudcode.py
- **Classes:**
  - OAuthUrlResponse
  - OAuthStartResponse
  - OAuthStatusResponse
  - OAuthCallbackRequest
  - AddRefreshTokenRequest
  - AccountResponse
  - AccountListResponse
  - StatisticsResponse
  - GenerateRequest
  - GenerateResponse
- **Standalone Functions:**
  - start_oauth, _process_oauth_callback, check_oauth_status, cancel_oauth, get_oauth_url, oauth_callback, add_account_from_refresh_token, list_accounts, add_account, remove_account, set_default_account, refresh_account, get_account_details, refresh_all_accounts, get_statistics, generate_content, list_available_models, reload_accounts

### server\app\api\v1\compare.py
- **Standalone Functions:**
  - compare_documents, compare_versions, get_compare_result, _extract_text_from_source

### server\app\api\v1\convert.py
- **Standalone Functions:**
  - create_txt_file, create_md_file, create_json_file, create_pdf_file, create_docx_file, convert_text, get_supported_formats

### server\app\api\v1\dashboard.py
- **Classes:**
  - DashboardRequest
  - PatternDashboardRequest
  - ComparisonDashboardRequest
  - ChartDataResponse
  - AlertResponse
  - DashboardResponse
- **Standalone Functions:**
  - get_pattern_dashboard, get_system_dashboard, get_comparison_dashboard, export_pattern_dashboard_json, export_pattern_dashboard_html, export_system_dashboard_json, export_system_dashboard_html, get_health_summary, list_patterns

### server\app\api\v1\documents.py
- **Standalone Functions:**
  - get_current_user_with_token, get_document_tags, upload_document, upload_from_url, list_documents, get_document, confirm_presigned_upload_url, update_document, delete_document, archive_document, restore_document, reindex_document, get_document_versions, get_document_chunks, get_document_text, download_document

### server\app\api\v1\extraction.py
- **Standalone Functions:**
  - create_template, list_templates, get_template, update_template, delete_template, extract_data, batch_extract_data, list_results, get_result, export_results

### server\app\api\v1\feedback.py
- **Classes:**
  - LikeFeedbackRequest
  - DislikeFeedbackRequest
  - ReportFeedbackRequest
  - FeedbackResponse
  - FeedbackSummaryResponse
- **Standalone Functions:**
  - _get_feedback_collector, like_response, dislike_response, report_response, get_feedback_summary

### server\app\api\v1\health.py
- **Classes:**
  - ComponentHealth
  - ProviderHealthInfo
  - HealthResponse
  - DetailedHealthResponse
  - ReadinessResponse
  - LivenessResponse
- **Standalone Functions:**
  - set_startup_time, get_uptime, check_database, check_redis, check_minio, check_celery, get_provider_health_info, health_check, detailed_health_check, readiness_probe, liveness_probe, provider_health, provider_health_history

### server\app\api\v1\images.py
- **Classes:**
  - ImageGenerateRequest
  - ImageGenerateResponse
  - ImageModelInfo
  - ImageModelsResponse
- **Standalone Functions:**
  - generate_image, get_image_models

### server\app\api\v1\jobs.py
- **Standalone Functions:**
  - list_jobs, get_job, cancel_job, job_events

### server\app\api\v1\memori.py
- **Classes:**
  - FactCreate
  - FactResponse
  - TripleCreate
  - TripleResponse
  - RecallRequest
  - RecallResponse
  - MemoryStatsResponse
  - PreferenceCreate
  - PreferenceResponse
  - AttributeCreate
  - AttributeResponse
  - HealthScoreResponse
  - UsageAnalyticsResponse
- **Standalone Functions:**
  - recall_facts, list_facts, add_facts, add_triples, get_knowledge_graph, get_memory_stats, delete_fact, cleanup_facts, add_preferences, get_preferences, update_preference, delete_preference, add_attributes, get_attributes, update_attribute, delete_attribute, get_health_score, get_usage_analytics, get_top_facts, update_fact_importance, pin_fact

### server\app\api\v1\models.py
- **Classes:**
  - ModelInfo
  - ModelsListResponse
- **Standalone Functions:**
  - list_all_models, list_available_models, list_models_by_provider, list_models_by_type

### server\app\api\v1\oauth.py
- **Classes:**
  - OAuthCallbackResponse
- **Standalone Functions:**
  - google_login, google_callback, list_accounts

### server\app\api\v1\ocr.py
- **Standalone Functions:**
  - extract_ocr, get_ocr_status

### server\app\api\v1\process.py
- **Classes:**
  - DocumentCanceledError
- **Standalone Functions:**
  - _check_canceled, process_document_sync, process_all_pending, process_document

### server\app\api\v1\providers.py
- **Classes:**
  - AccountDetailResponse
  - ProviderStatsResponse
  - CloudCodeAccountResponse
- **Standalone Functions:**
  - get_provider_statistics, list_provider_accounts, enable_account, disable_account, list_cloudcode_accounts, get_cloudcode_statistics, get_cloudcode_available_models

### server\app\api\v1\rag.py
- **Standalone Functions:**
  - ingest_document, query_rag, get_rag_status

### server\app\api\v1\search.py
- **Classes:**
  - ChunkIndex
  - SearchQueryParams (Methods: validate_query, validate_limit)
  - TimelineItemSchema
  - ChunkDetail
  - GetDetailsRequest
- **Standalone Functions:**
  - search_index, get_timeline, get_details

### server\app\api\v1\summarize.py
- **Standalone Functions:**
  - create_summary, list_summaries, get_summary, delete_summary

### server\app\api\v1\tools.py
- **Classes:**
  - DocumentCountResponse
  - DocumentListItem
  - DocumentListResponse
  - DocumentStatsResponse
  - StorageUsageResponse
  - ChatStatsResponse
  - MostCitedDocument
  - MostCitedResponse
- **Standalone Functions:**
  - count_documents, list_documents, get_document_stats, search_documents_by_name, get_recent_uploads, get_largest_documents, get_documents_by_type, search_by_date_range, get_documents_without_tags, get_chat_statistics, get_most_cited_documents, get_storage_usage

### server\app\api\v1\workspaces.py
- **Standalone Functions:**
  - create_workspace, list_workspaces, get_workspace, update_workspace, delete_workspace, add_member, remove_member, update_member_role, list_members, create_presigned_upload_url, upload_document_to_workspace, list_workspace_documents

### server\app\core\config.py
- **Classes:**
  - Settings

### server\app\core\email.py
- **Classes:**
  - EmailService (Methods: __init__, _create_connection, send_email, send_otp_email)

### server\app\core\engines\ocr.py
- **Classes:**
  - DocumentEngine (Methods: __init__, _extract_layout_from_docling, _extract_bbox, _build_lines_from_text, _extract_picture_info, _decode_text_bytes, _extract_rtf_text, _extract_odt_text, _extract_text_like_file, _process_text_file, _detect_document_type)

### server\app\core\engines\surya_engine.py
- **Classes:**
  - SuryaEngine (Methods: __init__, _ensure_initialized, _assemble_output, _find_lines_in_region, _build_layout_pages, _calc_avg_confidence, _bbox_overlap)
- **Standalone Functions:**
  - should_use_surya

### server\app\core\engines\paddleocr_engine.py
- **Classes:**
  - PaddleOCREngine (Methods: __init__, _ensure_initialized, process_document, _predict_structure, ocr_image, _predict_ocr, process_crops)
- **Standalone Functions:**
  - should_use_paddleocr

### server\app\core\engines\pdf_routing.py
- **Standalone Functions:**
  - detect_pdf_content_type

### server\app\core\jobs.py
- **Classes:**
  - JobStatus
  - JobStep
  - Job (Methods: __init__, update, to_dict)
  - JobStore (Methods: __init__, create_job, get_job, update_job, delete_job, cleanup_old_jobs, cleanup_all)

### server\app\core\ollama_client.py
- **Classes:**
  - OllamaClient (Methods: __init__)
- **Standalone Functions:**
  - check_ollama_connection

### server\app\core\processors\vietnamese.py
- **Classes:**
  - VietnameseProcessor (Methods: __init__, has_vietnamese_chars, is_vietnamese_text, restore_tones_basic, normalize_vietnamese, tokenize, process_vietnamese_text)

### server\app\core\security.py
- **Classes:**
  - TokenPayload
  - TokenPair
- **Standalone Functions:**
  - _prepare_password, hash_password, verify_password, create_access_token, create_refresh_token, verify_access_token, verify_refresh_token_hash, generate_otp, hash_otp, verify_otp_hash, create_token_pair

### server\app\db\models.py
- **Classes:**
  - Base
  - User
  - RefreshToken
  - Workspace
  - WorkspaceUser
  - DocumentCategory
  - Document
  - DocumentVersion
  - Chunk
  - Job
  - Conversation
  - Message
  - Citation
  - AIUsage
  - UserRole
  - WorkspaceRole
  - DocumentStatus
  - JobType
  - JobStatus
  - AnswerPolicy
  - MessageRole
  - EmbeddingModel
  - ChunkEmbedding
  - EmbeddingProvider
  - ExtractionTemplate
  - ExtractionResult
  - ConversationSummary
  - Summary
  - FunctionCallLog
  - FunctionCallStatus
  - MemoriEntity
  - MemoriEntityFact
  - MemoriEntityPreference
  - MemoriEntityAttribute
  - MemoriKnowledgeGraph
  - MemoriProcess
  - MemoriProcessAttribute
  - MemoriSession
  - MemoriConversation
  - MemoriConversationMessage
  - PatternFeedback
  - PatternMetricsAggregate
  - RoutingAdjustmentRecord
  - MetaPatternUsage

### server\app\db\repos\base.py
- **Classes:**
  - BaseRepository (Methods: __init__)

### server\app\db\session.py
- **Standalone Functions:**
  - get_db

### server\app\main.py
- **Standalone Functions:**
  - lifespan, health_check

### server\app\middleware\error_handler.py
- **Classes:**
  - APIError (Methods: __init__)
  - NotFoundError (Methods: __init__)
  - ValidationError (Methods: __init__)
  - AuthenticationError (Methods: __init__)
  - AuthorizationError (Methods: __init__)
  - RateLimitError (Methods: __init__)
  - ServiceUnavailableError (Methods: __init__)
- **Standalone Functions:**
  - create_error_response, setup_error_handlers

### server\app\middleware\logging.py
- **Classes:**
  - RequestLoggingMiddleware
  - CorrelationIDFilter (Methods: filter)
- **Standalone Functions:**
  - get_correlation_id, setup_logging

### server\app\middleware\rate_limit.py
- **Classes:**
  - RateLimitConfig (Methods: get_limit)
  - RateLimiter (Methods: __init__, _get_key)
  - RateLimitMiddleware (Methods: __init__, _default_get_identifier)
- **Standalone Functions:**
  - get_rate_limiter, check_rate_limit

### server\app\models\enums.py
- **Classes:**
  - ProviderName
  - ProviderConfig
  - ProviderStatus
  - EnhancementResult
  - TestResult

### server\app\models\schemas.py
- **Classes:**
  - PreprocessSettings
  - ExtractSettings
  - OcrSettings
  - OCRRequest
  - BoundingBox
  - LayoutWord
  - LayoutLine
  - LayoutBlock
  - LayoutPage
  - Layout
  - Page
  - Structured
  - Timings
  - Meta
  - OcrResult
  - JobResponse
  - AsyncJobResponse
  - PdfOptions
  - ConvertRequest
  - RagIngestRequest
  - RagQueryRequest
  - RagQueryResponse
  - HealthResponse

### server\app\queue\tasks\convert.py
- **Standalone Functions:**
  - process_convert, _convert_to_txt, _convert_to_markdown, _convert_to_json, _convert_to_pdf, _convert_to_docx, _convert_to_html, _convert_to_rtf, _escape_html, _escape_rtf

### server\app\queue\tasks\enrichment.py
- **Standalone Functions:**
  - _get_sync_session, _get_worker_event_loop, process_enrichment

### server\app\queue\tasks\index.py
- **Standalone Functions:**
  - _make_sync_session, process_index

### server\app\queue\tasks\memori_tasks.py
- **Standalone Functions:**
  - extract_memori_facts_task, _extract_memori_async, _determine_preference_category, _determine_attribute_category

### server\app\queue\tasks\normalize.py
- **Standalone Functions:**
  - _detect_language, _split_markdown_sections, normalize_parser_output, quality_check

### server\app\queue\tasks\ocr.py
- **Standalone Functions:**
  - _safe_enhanced_text, _get_sync_session, _load_pdf_page_images, _decode_text_bytes, _extract_rtf_text, _extract_odt_text, _extract_direct_text, _extract_image_text_tesseract, _extract_mixed_pdf_page_ocr, process_ocr

### server\app\schemas\analytics.py
- **Classes:**
  - UsagePeriod
  - UsageTotals
  - UsageSummaryResponse
  - ProviderUsage
  - ModelUsage
  - DailyUsage
  - UsageByProviderResponse
  - UsageByModelResponse
  - DailyUsageResponse
  - DocumentStats
  - JobStats
  - ConversationStats
  - MessageStats
  - Usage24h
  - DashboardStatsResponse
  - ActivityItem
  - RecentActivityResponse
  - CostBreakdownResponse

### server\app\schemas\auth.py
- **Classes:**
  - RegisterRequest
  - LoginRequest
  - RefreshRequest
  - OTPRequestRequest
  - OTPVerifyRequest
  - ForgotPasswordRequest
  - ChangePasswordRequest
  - UserResponse
  - AuthTokenResponse
  - RegisterResponse
  - OTPResponse
  - OTPVerifyResponse

### server\app\schemas\chat.py
- **Classes:**
  - ConversationCreate
  - ConversationUpdate
  - ConversationResponse
  - ConversationListResponse
  - CitationResponse
  - MessageCreate
  - MessageResponse
  - MessageListResponse
  - SendMessageResponse
  - StatelessQueryRequest
  - DirectChatRequest
  - DirectChatResponse
  - StatelessQueryCitation
  - PolicyEvaluationResponse
  - StatelessQueryResponse
  - ConversationStatsResponse

### server\app\schemas\common.py
- **Classes:**
  - ErrorResponse
  - SuccessResponse

### server\app\schemas\compare.py
- **Classes:**
  - CompareSourceType
  - ChangeType
  - ChangeCategory
  - CompareSource
  - DiffChange
  - CompareStatistics
  - SourceInfo
  - CompareResult
  - CompareRequest
  - CompareVersionsRequest
  - CompareResponse

### server\app\schemas\document.py
- **Classes:**
  - UploadFromUrlRequest
  - PresignedUploadRequest
  - UpdateDocumentRequest
  - DocumentFilters
  - PresignedUploadResponse
  - DocumentVersionResponse
  - ChunkResponse
  - DocumentResponse
  - DocumentDetailResponse
  - DocumentListResponse

### server\app\schemas\extraction.py
- **Classes:**
  - FieldType
  - ValidationRule
  - TemplateField
  - ExtractionTemplate
  - ExtractedField
  - ExtractionResult
  - TemplateCreateRequest
  - TemplateUpdateRequest
  - TemplateResponse
  - TemplateListResponse
  - ExtractRequest
  - BatchExtractRequest
  - ExtractResponse
  - BatchExtractResponse
  - ExportFormat
  - ExportRequest
  - ExportResponse

### server\app\schemas\job.py
- **Classes:**
  - JobResponse
  - JobListResponse
  - JobCancelRequest

### server\app\schemas\summarize.py
- **Classes:**
  - SummaryAudience
  - SummaryFormat
  - SummaryCitation
  - SummarizeRequest
  - SummaryResult
  - SummaryListResponse

### server\app\schemas\workspace.py
- **Classes:**
  - CreateWorkspaceRequest
  - UpdateWorkspaceRequest
  - AddMemberRequest
  - UpdateMemberRoleRequest
  - MemberResponse
  - WorkspaceResponse
  - WorkspaceDetailResponse
  - WorkspaceListResponse

### server\app\services\analytics\analytics_service.py
- **Classes:**
  - AnalyticsService (Methods: __init__)

### server\app\services\analytics\job_service.py
- **Classes:**
  - JobServiceError
  - JobNotFoundError
  - JobService (Methods: __init__, update_status_sync, get_sync)

### server\app\services\analytics\learning_pipeline_service.py
- **Classes:**
  - AdjustmentStatus
  - RoutingAdjustment (Methods: to_dict)
  - PatternAnalysis (Methods: to_dict)
  - LearningPipeline (Methods: __init__, _generate_adjustment, is_in_test_group, get_pattern_priority, get_active_tests, get_adjustment)

### server\app\services\analytics\metrics_collector_service.py
- **Classes:**
  - MetricType
  - ExecutionMetric
  - PatternMetrics (Methods: to_dict)
  - AnomalyResult
  - MetricsCollector (Methods: __init__, record_execution, get_metrics, detect_anomaly, get_all_patterns, get_trend, _percentile)

### server\app\services\analytics\workspace_service.py
- **Classes:**
  - WorkspaceServiceError
  - WorkspaceNotFoundError
  - PermissionDeniedError
  - MemberExistsError
  - WorkspaceService (Methods: __init__)

### server\app\services\auth\api_key_service.py
- **Classes:**
  - AccountStatus
  - ModelQuota (Methods: update_usage, is_low)
  - KeyStatus (Methods: is_available, overall_quota_percentage, mark_error, mark_success)
  - APIKeyManager (Methods: __init__, _load_keys, _parse_keys, get_key, get_best_key, mark_success, mark_error, get_stats, get_account_details)
- **Standalone Functions:**
  - get_key_manager

### server\app\services\auth\auth_service.py
- **Classes:**
  - AuthServiceError
  - UserExistsError
  - InvalidCredentialsError
  - InvalidTokenError
  - OTPRequiredError
  - OTPCooldownError
  - OTPMaxAttemptsError
  - AuthService (Methods: __init__)

### server\app\services\auth\oauth_callback_server.py
- **Classes:**
  - OAuthCallbackServer (Methods: __init__, _success_html, _error_html)
- **Standalone Functions:**
  - start_oauth_flow, wait_for_oauth_code, cancel_oauth_flow, get_oauth_redirect_uri

### server\app\services\conversation\chat_pipeline.py
- **Classes:**
  - StreamEventType
  - StreamEvent (Methods: to_sse)
  - ProgressData
  - TokenData
  - MetadataData
  - ChatPipeline (Methods: __init__, cancel)

### server\app\services\conversation\conversation_service.py
- **Classes:**
  - ConversationService (Methods: __init__)

### server\app\services\conversation\dedup_cache.py
- **Classes:**
  - DedupCache (Methods: __init__, _hash_query, _make_key)

### server\app\services\conversation\intent_cache.py
- **Classes:**
  - IntentCache (Methods: __init__, _get_key)
- **Standalone Functions:**
  - get_intent_cache

### server\app\services\conversation\intent_detector.py
- **Classes:**
  - QueryIntent
  - IntentResult
  - IntentResultWithMetrics
  - IntentMetrics
  - IntentDetector (Methods: __init__, set_category_context, set_category_context_string, set_document_context, get_metrics, add_vietnamese_patterns, _classify_by_semantic, _build_classification_prompt, _parse_llm_response)
- **Standalone Functions:**
  - get_intent_detector

### server\app\services\conversation\memory_cache.py
- **Classes:**
  - MemoryCacheManager (Methods: __init__, _hash_query)

### server\app\services\conversation\memory_service.py
- **Classes:**
  - Entity
  - FactWithEntities
  - PruningResult
  - MemoryEntry
  - ConversationMemory (Methods: to_context_string)
  - MemoryManager (Methods: __init__, _estimate_tokens, _get_nlp_model, _get_embedder, deduplicate_facts, prune_memory, _score_with_heuristics, truncate_to_budget)

### server\app\services\conversation\parallel_executor.py
- **Classes:**
  - ParallelMemoryExecutor (Methods: __init__)

### server\app\services\conversation\semantic_router.py
- **Classes:**
  - RouteMatch
  - SemanticRouter (Methods: __init__, _initialize, _cosine_similarity, classify, get_greeting_response, get_chitchat_response)
- **Standalone Functions:**
  - get_semantic_router

### server\app\services\core\base_service.py
- **Classes:**
  - BaseService (Methods: __init__, __repr__)
  - BaseLLMService (Methods: __init__)
  - BaseCacheService (Methods: __init__)
  - BaseAsyncService (Methods: __init__)

### server\app\services\core\context_budget.py
- **Classes:**
  - AllocatedContext (Methods: __init__)
  - ContextBudgetManager (Methods: __init__, allocate_context, _select_within_budget, _estimate_tokens)
- **Standalone Functions:**
  - get_context_budget_manager

### server\app\services\core\embedding_service.py
- **Classes:**
  - EmbeddingModelInfo (Methods: __init__)
  - EmbeddingService (Methods: __init__, ensure_model_loaded, _compute_cache_key, get_model_info, register_model, embed_text, embed_text_simple, embed_batch, embed_batch_simple, _get_st_model, _embed_with_st, _embed_batch_with_st, _embed_with_ollama, _embed_batch_with_ollama, _embed_with_openai, _embed_batch_with_openai, delete_document_vectors, clear_cache, cache_size, default_model_info)
- **Standalone Functions:**
  - get_embedding_service, init_embedding_service, embedding_service

### server\app\services\core\latency_budget_service.py
- **Classes:**
  - QueryComplexity
  - UserTier
  - BudgetAllocation
  - BudgetConfig
  - LatencyBudgetManager (Methods: __init__, allocate_budget, adjust_for_user_tier, check_budget, get_remaining_budget, _distribute_budget, update_node_budget, get_budget_summary)

### server\app\services\core\rag\factory.py
- **Standalone Functions:**
  - initialize_raganything, initialize_patterns, initialize_orchestration

### server\app\services\core\rag\service.py
- **Classes:**
  - RAGService (Methods: __new__, __init__)

### server\app\services\core\rag\types.py
- **Classes:**
  - PolicyEvaluationResult
  - Citation
  - RAGResponse

### server\app\services\core\rag\utils.py
- **Standalone Functions:**
  - convert_to_response

### server\app\services\core\rag\wrappers.py
- **Standalone Functions:**
  - create_llm_wrapper, create_vision_wrapper, create_embedding_wrapper, create_retriever_wrapper

### server\app\services\core\reranker_service.py
- **Classes:**
  - RerankerService (Methods: __init__, _load_model)
- **Standalone Functions:**
  - get_reranker_service

### server\app\services\core\retriever_service.py
- **Classes:**
  - RetrievalResult
  - RetrieverService (Methods: __init__)

### server\app\services\core\service_registry.py
- **Classes:**
  - ServiceRegistry (Methods: register, get_class, get_instance, list_services, clear, unregister)
- **Standalone Functions:**
  - register_core_services, register_conversation_services, register_document_services, register_all_services

### server\app\services\documents\category_service.py
- **Classes:**
  - CategorySuggestion
  - DocumentSummary
  - CategoryService (Methods: __init__, _slugify)

### server\app\services\documents\chunking_service.py
- **Classes:**
  - ChunkingStrategy
  - ChunkMetadata
  - TextChunk
  - ChunkingService (Methods: __init__, _estimate_tokens, _tokenize, _detokenize, _compute_hash, _extract_section_title, chunk_text, chunk_by_paragraphs, _clean_text, _find_page_range, chunk_semantic, _split_sentences, _find_semantic_boundaries, _cosine_similarity, _create_chunks_from_boundaries, chunk_by_sentences, _normalize_chunk, chunk_content_list, chunk_adaptive)

### server\app\services\documents\document_service.py
- **Classes:**
  - DocumentServiceError
  - DocumentNotFoundError
  - InvalidFileError
  - DocumentService (Methods: __init__)

### server\app\services\documents\extraction_service.py
- **Classes:**
  - ExtractionService (Methods: __init__, _is_required, _build_extraction_prompt, _convert_value, _validate_field, _export_json, _export_csv, _export_excel)
- **Standalone Functions:**
  - get_extraction_service

### server\app\services\generation\compare_service.py
- **Classes:**
  - CompareService (Methods: __init__, get_result, _align_sections, _compute_diff, _categorize_change, _calculate_similarity, _calculate_statistics)
- **Standalone Functions:**
  - get_compare_service

### server\app\services\generation\image_generation_service.py
- **Classes:**
  - ImageGenerationResult
  - ImageGenerationService (Methods: __init__, _get_dimensions, get_supported_models)
- **Standalone Functions:**
  - get_image_generation_service

### server\app\services\generation\prompt_builder.py
- **Classes:**
  - PromptType
  - Citation (Methods: to_string)
  - PromptContext
  - PromptBuilder (Methods: __init__, get_system_prompt, build_rag_prompt, build_ocr_prompt, build_compare_prompt, build_extract_prompt, build_summarize_prompt, format_citations, estimate_tokens)

### server\app\services\generation\response_formatter.py
- **Classes:**
  - ResponseType
  - FormattedCitation
  - FormattedResponse
  - FormattedChunk
  - Source
  - ResponseFormatter (Methods: __init__, format_ocr_result, format_compare_result, format_extract_result, format_summary_result, format_rag_response, format_table, format_image_metadata, format_citations, format_table_export, _export_to_csv, _export_to_excel, format_image_with_lazy_loading, _generate_responsive_sizes, _clean_text, _text_to_html, _markdown_to_html, _highlight_quotes)

### server\app\services\generation\summarize_service.py
- **Classes:**
  - SummarizeService (Methods: __init__, _build_prompt, _generate_fallback_summary, _extract_citations, _find_relevant_excerpt, _format_output)
- **Standalone Functions:**
  - get_summarize_service

### server\app\services\infrastructure\ai_providers\base_provider.py
- **Classes:**
  - ProviderException
  - QuotaExceededException
  - RateLimitException
  - BaseAIProvider (Methods: __init__, supports_vision, get_name)

### server\app\services\infrastructure\ai_providers\cloudcode.py
- **Classes:**
  - CloudCodeProvider (Methods: __init__, supports_vision, get_name)

### server\app\services\infrastructure\ai_providers\cloudcode_provider_service.py
- **Classes:**
  - CloudCodeModel
  - ModelQuota (Methods: is_available, from_dict)
  - GoogleToken (Methods: is_expired, to_dict, from_dict)
  - CloudCodeAccount (Methods: is_available, get_model_quota, has_quota_for_model, get_best_available_model, update_quota_after_use)
  - CloudCodeResponse
  - GoogleOAuth (Methods: get_auth_url)
  - CloudCodeClient (Methods: __init__, _convert_messages_to_gemini, _extract_content)
  - CloudCodeProviderManager (Methods: __init__, remove_account, list_accounts, _parse_antigravity_account, _parse_local_account, _get_best_account_for_model, _get_best_account_any_model, _detect_request_type, resolve_model, get_statistics, get_available_models)
- **Standalone Functions:**
  - get_cloudcode_manager, init_cloudcode_manager

### server\app\services\infrastructure\ai_providers\config_loader.py
- **Classes:**
  - AIProviderConfigLoader (Methods: load_provider_configs, _parse_priorities, validate_config)

### server\app\services\infrastructure\ai_providers\deepseek.py
- **Classes:**
  - DeepSeekProvider (Methods: __init__, _create_client, _rotate_key, _detect_code_document, supports_vision, get_name)

### server\app\services\infrastructure\ai_providers\gemini.py
- **Classes:**
  - GeminiProvider (Methods: __init__, _rotate_key, _convert_messages_to_gemini_format, supports_vision, get_name)

### server\app\services\infrastructure\ai_providers\groq.py
- **Classes:**
  - GroqProvider (Methods: __init__, _create_client, _rotate_key, supports_vision, get_name)

### server\app\services\infrastructure\ai_providers\manager.py
- **Classes:**
  - AIProviderManager (Methods: __init__, _load_providers, _create_provider, get_specific_provider, _create_enhancement_prompt, _create_vision_prompt, _detect_improvements, _get_available_providers, _mark_provider_quota_exceeded, _mark_provider_rate_limited, _mark_provider_error, get_active_provider)

### server\app\services\infrastructure\ai_providers\ollama.py
- **Classes:**
  - OllamaProvider (Methods: __init__, supports_vision, get_name)

### server\app\services\infrastructure\config_loader.py
- **Classes:**
  - ConfigChange
  - ConfigValidationError
  - PipelineConfigLoader (Methods: __init__, load_config, reload_if_changed, get, set, save_config, is_enabled, add_change_listener, remove_change_listener, get_change_history, _validate_config, _detect_changes, _record_change, _notify_listeners, _start_auto_reload, _get_nested, _get_default_config)
- **Standalone Functions:**
  - get_config_loader, set_config_loader

### server\app\services\infrastructure\health_monitor.py
- **Classes:**
  - HealthCheckResult
  - HealthMonitor (Methods: __init__, _record_result, get_status, get_history)
- **Standalone Functions:**
  - get_health_monitor, start_health_monitor, stop_health_monitor

### server\app\services\infrastructure\logging_service.py
- **Classes:**
  - LogEntry
  - PerformanceMetrics
  - LoggingService (Methods: __init__, generate_correlation_id, should_log, log_stage, log_error, trace_stage, track_performance, emit_performance_alert, get_metrics_summary, _sanitize_data, export_metrics_prometheus)
- **Standalone Functions:**
  - get_logging_service, set_logging_service

### server\app\services\infrastructure\phoenix_tracer.py
- **Classes:**
  - Span (Methods: duration_ms, to_dict)
  - Anomaly
  - PhoenixTracer (Methods: __init__, start_trace, trace_span, trace_llm_call, trace_retrieval, _check_span_anomalies, _record_anomaly, get_trace, get_stats, export_traces, clear_traces, end_trace)

### server\app\services\infrastructure\redis_manager.py
- **Classes:**
  - RedisManager (Methods: __new__, is_connected)
- **Standalone Functions:**
  - get_redis

### server\app\services\infrastructure\retry_handler.py
- **Classes:**
  - RetryExhaustedError (Methods: __init__)
  - RetryHandler (Methods: __init__, get_delay, is_retryable, last_attempt_count, last_total_time)
- **Standalone Functions:**
  - with_retry

### server\app\services\infrastructure\trace_collector.py
- **Classes:**
  - SpanKind
  - SpanStatus
  - SpanEvent
  - Span
  - Trace (Methods: add_span, get_total_latency_ms, get_spans_by_kind, to_dict)
  - TraceCollector (Methods: __init__, _generate_id, start_span, add_event, set_attribute, set_status, _add_completed_trace, get_trace, get_recent_traces, get_traces_summary, clear_traces)
  - OpenTelemetryExporter (Methods: __init__, _init_tracer, export, _map_span_kind)
  - LangSmithExporter (Methods: __init__, _init_client, export)

### server\app\services\memori\__init__.py
- **Standalone Functions:**
  - __getattr__

### server\app\services\memori\analytics_service.py
- **Classes:**
  - MemoriAnalytics (Methods: __init__, _generate_recommendations, _classify_activity)

### server\app\services\memori\augmentation_processors_service.py
- **Classes:**
  - FactAugmentationProcessor (Methods: __init__)
  - PreferenceAugmentationProcessor
  - AttributeAugmentationProcessor
  - AugmentationPipeline (Methods: __init__)

### server\app\services\memori\augmentation_service.py
- **Classes:**
  - WriteTask (Methods: __post_init__)
  - AugmentationContext (Methods: __init__, add_write)
  - DbWriterRuntime (Methods: __init__, configure, ensure_started, stop, enqueue_write, _run_loop, _collect_batch, _process_batch)
  - AugmentationRuntime (Methods: __init__, ensure_started, _run_loop)
  - AugmentationManager (Methods: __init__, start, enqueue, _handle_result, wait)
- **Standalone Functions:**
  - get_db_writer, get_runtime

### server\app\services\memori\auto_cognify_service.py
- **Classes:**
  - AutoCognifyService (Methods: __init__, _extract_facts_rule_based)

### server\app\services\memori\entity_resolver_service.py
- **Classes:**
  - EntityResolver (Methods: __init__)

### server\app\services\memori\extraction.py
- **Classes:**
  - LLMService
  - FactExtractor (Methods: __init__, calculate_importance)
- **Standalone Functions:**
  - format_embedding_for_db, parse_embedding_from_db, embed_texts_sync, embed_texts_async

### server\app\services\memori\graph_search_service.py
- **Classes:**
  - SearchType
  - SearchResult (Methods: to_dict)
  - GraphSearchService (Methods: __init__, format_results_for_prompt)

### server\app\services\memori\manager_service.py
- **Classes:**
  - MemoriManager (Methods: __init__, format_recalled_facts)

### server\app\services\memori\memify_service.py
- **Classes:**
  - EnrichmentResult (Methods: to_dict)
  - MemifyService (Methods: __init__)

### server\app\services\memori\models.py
- **Classes:**
  - SemanticTriple
  - Conversation (Methods: __init__, configure_from_advanced_augmentation)
  - Entity (Methods: __init__, configure_from_advanced_augmentation, _parse_semantic_triple)
  - Process (Methods: __init__, configure_from_advanced_augmentation)
  - Memories (Methods: __init__, configure_from_advanced_augmentation)
  - RecalledFact
  - AugmentationInput
  - MemoriCache
  - MemoriEmbeddings
  - MemoriConfig (Methods: reset_cache, is_test_mode, from_conversation)
- **Standalone Functions:**
  - normalize_predicate, validate_predicate, get_allowed_predicates, suggest_predicate

### server\app\services\memori\recall_service.py
- **Classes:**
  - MemoriRecall (Methods: __init__, _apply_decay_and_boosting, format_facts_for_prompt)

### server\app\services\memori\search.py
- **Standalone Functions:**
  - find_similar_embeddings, _find_similar_numpy, _tokenize, _lexical_scores_for_ids, _rerank_by_lexical_overlap, search_entity_facts

### server\app\services\memori\temporal_operations.py
- **Classes:**
  - EdgeDates
  - ContradictedFacts
- **Standalone Functions:**
  - extract_edge_dates, get_edge_contradictions, invalidate_contradicted_edges

### server\app\services\memori\triple_validator_service.py
- **Classes:**
  - TripleAction
  - TripleDecision
  - TripleValidator (Methods: __init__, is_literal_attribute, apply_decisions, filter_invalid_triples, deduplicate_triples)

### server\app\services\quality\confidence_scorer.py
- **Classes:**
  - ConfidenceComponents (Methods: to_dict)
  - ConfidenceResult (Methods: to_dict)
  - ConfidenceScorer (Methods: __init__, compute_confidence, compute_from_validation, should_retry, get_confidence_level)

### server\app\services\quality\deepeval_tester.py
- **Classes:**
  - DeepEvalMetric
  - DeepEvalTestCase
  - DeepEvalResult (Methods: to_dict)
  - DeepEvalTester (Methods: __init__, _check_deepeval_available, _fallback_test, create_test_cases_from_samples, get_summary_report)

### server\app\services\quality\evaluation_service.py
- **Classes:**
  - TestCase
  - EvaluationReport
  - EvaluationMetrics
  - Alert
  - TimeSeriesMetrics
  - EvaluationService (Methods: __init__, create_test_case, _store_metrics, get_metrics_timeseries, set_alert_callback, get_alerts)

### server\app\services\quality\fact_checker.py
- **Classes:**
  - NumericalClaim
  - FactCheckResult (Methods: to_dict)
  - SafeExpressionEvaluator (Methods: __init__, evaluate, _eval_node)
  - FactChecker (Methods: __init__, verify_numerical_claims, _extract_claims, _verify_match, _approximately_equal, verify_expression)

### server\app\services\quality\feedback_collector.py
- **Classes:**
  - FeedbackType
  - IssueType
  - FeedbackEntry (Methods: to_dict)
  - FeedbackSummary
  - FeedbackStorage
  - InMemoryFeedbackStorage (Methods: __init__)
  - FeedbackCollector (Methods: __init__, _generate_id)

### server\app\services\quality\grounding_verifier_service.py
- **Classes:**
  - GroundingResult
  - EnhancedGroundingResult
  - EntailmentResult
  - GroundingVerifier (Methods: __init__, _get_embedder, _get_nli_model, verify, _extract_tokens)
- **Standalone Functions:**
  - get_grounding_verifier

### server\app\services\quality\guardrails_service.py
- **Classes:**
  - GuardrailViolation
  - GuardrailResult
  - GuardrailsService (Methods: __init__, reload_config, _get_default_config, _check_jailbreak, _check_pii, _check_topic, _check_prompt_injection, _check_sql_injection, _check_toxicity, _check_bias, _check_factuality, _check_pii_leakage, _check_hallucination, _get_error_message, get_violations_log, get_stats)

### server\app\services\quality\hallucination_checker.py
- **Classes:**
  - EntailmentResult
  - HallucinationCheckResult (Methods: to_dict)
  - HallucinationChecker (Methods: __init__, _check_with_heuristic, _split_sentences)

### server\app\services\quality\policy_service.py
- **Classes:**
  - AnswerPolicy
  - PolicyEvaluation
  - PolicyDecision
  - ThresholdAdjustment
  - PolicyConfig
  - ABTestResult
  - PolicyService (Methods: __init__, evaluate, _evaluate_strict, _evaluate_balanced, _evaluate_open, from_workspace_settings, evaluate_with_dynamic_thresholds, adjust_thresholds, track_accuracy, get_workspace_threshold, get_threshold_history, get_policy_decisions, log_policy_decision, run_ab_test, record_ab_test_result, _calculate_statistical_significance, get_ab_test_status, notify_threshold_change, set_notification_callback, _send_notification)

### server\app\services\quality\ragas_evaluator.py
- **Classes:**
  - RagasMetric
  - RagasSample
  - RagasResult (Methods: to_dict)
  - RagasEvaluator (Methods: __init__, _check_ragas_available, _fallback_evaluation, get_summary_report)

### server\app\services\quality\result_validator.py
- **Classes:**
  - ValidationStatus
  - HallucinationType
  - ValidationIssue
  - ValidationResult (Methods: is_valid, to_dict)
  - ResultValidator (Methods: __init__, _calculate_retrieval_confidence, _detect_hallucination, _calculate_relevance, _calculate_groundedness, _calculate_answer_confidence, _calculate_overall_confidence, _parse_llm_scores)

### server\app\services\quality\safety_checker.py
- **Classes:**
  - PIIType
  - ToxicityLevel
  - ToneType
  - PIIMatch
  - PIIResult (Methods: to_dict)
  - ToxicityResult (Methods: to_dict)
  - ToneResult (Methods: to_dict)
  - SafetyCheckResult (Methods: to_dict)
  - SafetyChecker (Methods: __init__, check_all, check_pii, _redact_text, check_toxicity, _keyword_toxicity_check, check_tone)

### server\app\services\rag_patterns\monitoring.py
- **Classes:**
  - MetricType
  - AlertSeverity
  - MetricSnapshot
  - Alert
  - ChartData
  - Dashboard
  - PatternMonitor (Methods: __new__, __init__, record_query, get_snapshot, get_health_summary, clear)
  - DashboardGenerator (Methods: __init__, generate_pattern_dashboard, generate_system_overview, generate_comparison_dashboard, export_to_json, export_to_html)
- **Standalone Functions:**
  - get_monitor, get_dashboard_generator

### server\app\services\rag_patterns\orchestration\analyzer.py
- **Classes:**
  - RoutingMode
  - QueryComplexity
  - ExecutionStrategy
  - QueryDomain
  - QueryIntent
  - QueryCharacteristics
  - QueryAnalysisResult
  - QueryAnalyzer (Methods: __init__, analyze, _detect_code, _detect_technical_terms, _detect_numbers, _classify_domain, _classify_complexity, _classify_intent, _requires_accuracy, _requires_speed, _requires_cost_optimization, _requires_multimodal, _requires_conversation_context, _calculate_confidence, _generate_reasoning, recommend_patterns, analyze_with_routing, _rewrite_query_if_needed, _determine_routing_mode, _check_composition_need, _assign_sla_budget, _recommend_strategy)

### server\app\services\rag_patterns\orchestration\combinations.py
- **Classes:**
  - CombinationType
  - CombinationMetadata
- **Standalone Functions:**
  - recommend_combination, get_combination, list_combinations, validate_combination, get_execution_order, estimate_latency, estimate_cost

### server\app\services\rag_patterns\orchestration\orchestrator.py
- **Classes:**
  - ExecutionStrategy
  - PatternExecution
  - OrchestrationResult
  - PatternOrchestrator (Methods: __init__, _should_execute_pattern, _is_critical_failure, _aggregate_results, _select_best_result, select_optimal_strategy, _aggregate_dag_results, get_trace_collector, set_trace_collector)

### server\app\services\rag_patterns\orchestration\planner.py
- **Classes:**
  - WorkflowNode
  - WorkflowPlan
  - PlannerConfig
  - WorkflowPlanner (Methods: __init__, plan, _plan_from_meta_pattern, _matches_meta_pattern, _create_plan_from_combination, _select_patterns_by_rules, _build_dag, _create_nodes, _allocate_budgets, _add_fallback_nodes, _validate_dag, _has_cycle, _calculate_max_depth, _find_entry_nodes, _find_exit_nodes, _estimate_metrics, _create_fallback_plan)

### server\app\services\rag_patterns\orchestration\registry.py
- **Classes:**
  - PatternCapability
  - PatternDomain
  - PatternComplexity
  - PatternMetadata
  - PatternRegistry (Methods: __init__, _register_builtin_patterns, register_pattern, get_pattern, list_patterns, find_by_capability, find_by_domain, are_compatible, check_requirements, get_conflicts, validate_combination, estimate_combination_metrics)
- **Standalone Functions:**
  - get_registry

### server\app\services\rag_patterns\orchestration\router.py
- **Classes:**
  - RoutingDecision
  - RouterConfig
  - SmartRouter (Methods: __init__, route, _match_meta_pattern, _matches_meta_pattern, _select_patterns_by_rules, _rank_by_heuristics, _determine_strategy, _estimate_metrics, _calculate_confidence, _generate_reasoning)

### server\app\services\rag_patterns\patterns\accuracy\corrective.py
- **Classes:**
  - RelevanceScorer
  - ConflictResolver (Methods: __init__, resolve_conflicts)
  - WebSearchFallback
  - CorrectiveRAGService (Methods: __init__, get_audit_trail)

### server\app\services\rag_patterns\patterns\accuracy\models.py
- **Classes:**
  - Document
  - CorrectionStep
  - CorrectedRetrievalResult
  - HallucinationCheck
  - RefinementStep
  - QualityDelta
  - SelfRAGResult
- **Standalone Functions:**
  - compute_similarity, docs_to_context, get_doc_content

### server\app\services\rag_patterns\patterns\accuracy\self_rag.py
- **Classes:**
  - QualityChecker (Methods: __init__)
  - ResponseRefiner (Methods: track_iteration, calculate_quality_delta)
  - QueryRewriter
  - SelfRAGService (Methods: __init__, get_refinement_summary)

### server\app\services\rag_patterns\patterns\hybrid.py
- **Classes:**
  - HybridRAGService (Methods: __init__, _build_system_prompt, _build_messages)

### server\app\services\rag_patterns\patterns\optimization\adaptive.py
- **Classes:**
  - ConfidenceAssessor (Methods: __init__)
  - StrategySelector (Methods: __init__, select_retrieval_strategy)
  - QueryRouter (Methods: __init__)
  - AdaptiveRAGService (Methods: __init__)

### server\app\services\rag_patterns\patterns\optimization\corag.py
- **Classes:**
  - Chunk
  - OptimizationStep
  - OptimizationMetrics
  - CORAGResult
  - MCTSNode (Methods: __init__, is_terminal, get_total_tokens, ucb1)
  - UtilityOptimizer (Methods: __init__, compute_utility, compute_utilities)
  - ChunkSelector (Methods: __init__, greedy_selection)
  - MCTSSearch (Methods: __init__, _select, _expand, _simulate, _backpropagate)
  - CORAGService (Methods: __init__, _track_optimization)
- **Standalone Functions:**
  - normalize_token_count

### server\app\services\rag_patterns\patterns\optimization\models.py
- **Classes:**
  - ConfidenceAssessment
  - RetrievalStrategy
  - AdaptiveRAGResult
  - Draft
  - VerificationResult
  - SpeculativeRAGResult
  - Chunk
  - OptimizationStep
  - OptimizationMetrics
  - CORAGResult
  - Sentence
  - SemanticHighlightResult
  - SemanticFragment
  - HighlightResult
- **Standalone Functions:**
  - estimate_confidence_heuristic, calculate_latency_savings, calculate_token_savings

### server\app\services\rag_patterns\patterns\optimization\semantic.py
- **Classes:**
  - Sentence
  - CompressionMetrics
  - SemanticHighlightResult
  - SentenceSplitter (Methods: __init__, split, _split_multilingual, _split_with_regex, _preprocess_text, _postprocess_text)
  - SemanticScorer (Methods: __init__, _get_query_embedding, _get_sentence_embeddings, _calculate_similarities, _normalize_scores)
  - EvidenceSelector (Methods: __init__, select)
  - ContextCompressor (Methods: __init__, _count_tokens, compress)
  - SemanticHighlightRAGService (Methods: __init__, _create_fallback_result)

### server\app\services\rag_patterns\patterns\optimization\speculative.py
- **Classes:**
  - Timer (Methods: __init__)
  - Drafter (Methods: __init__, estimate_baseline_time)
  - Verifier (Methods: __init__, _parse_verification, select_best_draft)
  - Merger (Methods: __init__, _apply_corrections)
  - SpeculativeRAGService (Methods: __init__, _prepare_context, get_config)
- **Standalone Functions:**
  - run_parallel, count_tokens_simple, estimate_cost, calculate_speedup, calculate_cost_savings

### server\app\services\rag_patterns\patterns\specialized\code_rag.py
- **Classes:**
  - CodeParser (Methods: parse_file, _detect_language, _extract_signature, _extract_imports)
  - SymbolResolver (Methods: __init__, add_symbols, resolve_symbol, find_related_symbols, clear)
  - DocExtractor (Methods: extract_from_symbol, extract_code_examples, summarize_documentation)
  - CodeRAGService (Methods: __init__, _find_relevant_symbols, _format_context_for_generation, _generate_default_answer, _calculate_confidence, clear_cache)

### server\app\services\rag_patterns\patterns\specialized\coral.py
- **Classes:**
  - ContextManager (Methods: __init__, get_or_create_context, get_context, add_turn, delete_context, get_active_conversations, get_context_stats)
  - HistoryManager (Methods: __init__, get_context_for_generation)
  - ConversationRetriever (Methods: __init__)
  - CORALService (Methods: __init__, _format_context_for_generation, _estimate_coherence, get_conversation_context, delete_conversation, get_active_conversations)

### server\app\services\rag_patterns\patterns\specialized\models.py
- **Classes:**
  - TurnType
  - ContextPruningStrategy
  - Turn (Methods: __post_init__)
  - ConversationContext (Methods: add_turn, get_recent_turns)
  - CORALResult
  - ModalityType
  - VisualContext
  - TextContext
  - MultimodalResult (Methods: total_results)
  - REVEALResult (Methods: is_multimodal)
  - FusionConfig
  - SymbolType
  - Symbol
  - CodeContext
  - CodeAnalysis
  - CodeRAGResult

### server\app\services\rag_patterns\patterns\specialized\reveal.py
- **Classes:**
  - FusionStrategy
  - VisionEncoder (Methods: __init__, extract_visual_features, encode_images)
  - MultimodalRetrieval (Methods: __init__, retrieve_multimodal)
  - VisualTextFusion (Methods: __init__, fuse_results, fuse_hybrid, _late_fusion, _early_fusion, _hybrid_fusion)
  - REVEALService (Methods: __init__, query, _generate_response, _determine_modality_type, _calculate_confidence)

### server\app\services\rag_patterns\pipeline\batch.py
- **Classes:**
  - BatchProcessingResult (Methods: success_count, failure_count, success_rate, summary)
  - BatchParser (Methods: __init__, _get_parser, get_supported_extensions, is_supported_file, filter_supported_files, _parse_single_file, process_batch)
  - BatchProcessor (Methods: __post_init__, _get_batch_parser, get_supported_extensions, filter_supported_files, process_documents_batch)

### server\app\services\rag_patterns\pipeline\callbacks.py
- **Classes:**
  - ProcessingEvent (Methods: to_dict)
  - ProcessingCallback (Methods: on_parse_start, on_parse_complete, on_parse_error, on_text_insert_start, on_text_insert_complete, on_multimodal_start, on_multimodal_item_complete, on_multimodal_complete, on_query_start, on_query_complete, on_query_error, on_document_complete, on_document_error, on_batch_start, on_batch_complete)
  - MetricsCallback (Methods: __init__, on_parse_complete, on_text_insert_complete, on_multimodal_complete, on_document_complete, on_document_error, on_query_complete, on_query_error, summary, reset)
  - CallbackManager (Methods: __init__, register, unregister, enable_event_log, event_log, clear_event_log, dispatch)

### server\app\services\rag_patterns\pipeline\config.py
- **Classes:**
  - RAGConfig (Methods: storage_dir, default_device, default_lang, ollama_base_url, ollama_vision_model, ollama_embed_model, __post_init__, from_server_settings, to_dict)

### server\app\services\rag_patterns\pipeline\parsers.py
- **Classes:**
  - MineruExecutionError (Methods: __init__)
  - BaseParser (Methods: __init__, supports_format, check_installation, get_file_extension, convert_office_to_pdf, convert_text_to_pdf, convert_image_format)
  - MineruParser (Methods: _read_output_files, supports_format, check_installation)
  - DoclingParser (Methods: _read_output_files, _read_from_block_recursive, _read_from_block, supports_format, check_installation)
  - ParserFactory (Methods: create_parser, get_best_parser_for_file)

### server\app\services\rag_patterns\pipeline\pipeline.py
- **Classes:**
  - RAGPipeline (Methods: __post_init__, _get_parser, check_parser_installation, _get_file_reference, _generate_cache_key, _generate_content_based_doc_id, _create_context_config, _create_context_extractor, _initialize_processors, set_content_source_for_context, _process_image_paths_for_vlm, _build_vlm_messages_with_images, get_processor_info)
- **Standalone Functions:**
  - compute_mdhash_id

### server\app\services\rag_patterns\pipeline\processors.py
- **Classes:**
  - ContextConfig (Methods: __post_init__)
  - ContextExtractor (Methods: __init__, extract_context, _extract_from_content_list, _extract_page_context, _extract_chunk_context, _extract_text_from_item, _extract_from_dict_source, _extract_from_text_source, _extract_from_text_chunks, _truncate_context)
  - BaseModalProcessor (Methods: __init__, set_content_source, _get_context_for_item, supports_type, _encode_image_to_base64, _robust_json_parse, _extract_all_json_candidates, _try_parse_json, _basic_json_cleanup, _progressive_quote_fix, _extract_fields_with_regex, _parse_response)
  - ImageModalProcessor (Methods: supports_type, format_chunk)
  - TableModalProcessor (Methods: supports_type, format_chunk)
  - EquationModalProcessor (Methods: supports_type, format_chunk)
  - GenericModalProcessor (Methods: supports_type, format_chunk)
  - ProcessorFactory (Methods: create_processor, create_all_processors, get_processor_for_content)
- **Standalone Functions:**
  - compute_hash_id

### server\app\services\rag_patterns\pipeline\prompt_manager.py
- **Classes:**
  - PromptManager (Methods: __init__, register_language, switch_language, get_current_language)
- **Standalone Functions:**
  - initialize_prompts

### server\app\services\rag_patterns\pipeline\prompts.py
- **Classes:**
  - PromptRegistry (Methods: __init__, swap, snapshot, __getitem__, __setitem__, __delitem__, __contains__, __iter__, __len__, get, keys, items, values, __repr__)

### server\app\services\rag_patterns\pipeline\resilience.py
- **Classes:**
  - CircuitBreaker (Methods: __init__, state, record_success, record_failure, _acquire_permission, __call__, async_call)
- **Standalone Functions:**
  - retry, async_retry

### server\app\services\rag_patterns\pipeline\types.py
- **Classes:**
  - DocStatus
  - ContentType
  - ParserType
  - ParseMethod
  - ProcessingResult
  - ModalContent
  - BatchProcessingResult

### server\app\services\rag_patterns\pipeline\utils.py
- **Standalone Functions:**
  - separate_content, insert_text_content, insert_text_content_with_multimodal_content, get_processor_for_type, get_processor_supports, encode_image_to_base64, validate_image_file, get_image_mime_type, compute_mdhash_id, compute_file_hash, get_file_extension, get_file_basename, ensure_directory, is_supported_document, truncate_text, clean_text, count_tokens_approximate

### server\app\services\search\hybrid_retriever_service.py
- **Classes:**
  - ExpandedQuery
  - QueryExpander (Methods: __init__, _detect_language)
  - BM25Result
  - BM25Index (Methods: __init__, _get_tokenizer, tokenize)
  - HybridResult
  - HybridRetriever (Methods: __init__, _reciprocal_rank_fusion, to_retrieval_results)

### server\app\services\search\query_rewriter_service.py
- **Classes:**
  - RewriteStrategy
  - RewriteResult
  - QueryRewriterService (Methods: __init__, _detect_language, _parse_lines)

### server\app\services\search\rag_cache_service.py
- **Classes:**
  - RAGCache (Methods: initialize, get, set, clear)

### server\app\services\search\search_cache_service.py
- **Classes:**
  - SearchCache (Methods: __init__, _make_key)
- **Standalone Functions:**
  - get_search_cache

### server\app\services\search\timeline_service.py
- **Classes:**
  - TimelineItem (Methods: __init__)
  - TimelineService (Methods: __init__)

### server\app\services\tools\function_calling_service.py
- **Classes:**
  - FunctionCallingService (Methods: __init__)
- **Standalone Functions:**
  - _llm_confirm_tool_use, _workspace_allows_tools

### server\app\services\tools\function_registry.py
- **Classes:**
  - FunctionStatus
  - FunctionParameter
  - FunctionDefinition (Methods: to_openai_schema, to_claude_schema)
  - FunctionCall
  - FunctionCallResult
  - FunctionRegistry (Methods: __init__, register, register_decorator, unregister, get_function, list_functions, get_schemas_for_provider, _add_to_history, get_call_history, clear_history)
- **Standalone Functions:**
  - get_function_registry, register_builtin_functions, _builtin_search_documents, _builtin_get_document_info, _builtin_calculate, _builtin_get_current_time, _builtin_format_text

### server\app\services\tools\tools_service_v2.py
- **Classes:**
  - CountDocumentsInput
  - CountDocumentsOutput
  - ListDocumentsInput
  - DocumentInfo
  - ListDocumentsOutput
  - ToolsServiceV2 (Methods: __init__, _get_models)
- **Standalone Functions:**
  - get_tools_definitions, execute_tool

### server\app\storage\object_store.py
- **Classes:**
  - ObjectStoreError
  - LocalFileStore (Methods: __init__, _get_path, upload, download, download_to_file, delete, exists)
  - ObjectStore (Methods: __init__, _init_storage, client, ensure_bucket, upload, download, download_to_file, delete, exists, get_presigned_url, get_presigned_upload_url, generate_key, compute_checksum)

### server\app\utils\files.py
- **Standalone Functions:**
  - validate_file_extension, validate_file_size, get_job_storage_path, get_job_input_path, get_job_output_path, save_uploaded_file, cleanup_job_files, get_file_info

### server\app\utils\rag_logger.py
- **Classes:**
  - RAGLogger (Methods: log_query, log_feedback)

### server\app\utils\text.py
- **Classes:**
  - QueryExpansion
  - ProcessingQuality
  - EnhancedTextProcessor (Methods: __init__, spell_check, preserve_technical_terms, expand_query, process_query)
- **Standalone Functions:**
  - clean_text, preserve_layout_text, text_to_markdown, extract_metadata_from_text, format_confidence_score, split_text_by_pages, sanitize_filename, create_text_summary

### server\app\utils\validation.py
- **Classes:**
  - FileValidationError
  - SecurityViolation
  - PIIMatch
  - ValidationResult
- **Standalone Functions:**
  - get_file_extension, validate_file_type, validate_file_size, detect_mime_type, get_document_type, validate_file, detect_sql_injection, detect_prompt_injection, detect_and_mask_pii, validate_text_input

## ?? Frontend (TypeScript/React)

### frontend\src\components\auth\ForgotPasswordForm.tsx
- **Exports (Components/Functions/Stores):**
  - ForgotPasswordForm

### frontend\src\components\auth\OtpVerificationModal.tsx
- **Exports (Components/Functions/Stores):**
  - OtpVerificationModal

### frontend\src\components\auth\ProtectedRoute.tsx
- **Exports (Components/Functions/Stores):**
  - ProtectedRoute

### frontend\src\components\chat\CitationNote.tsx
- **Exports (Components/Functions/Stores):**
  - MessageActions, FeedbackButtons, CitationNote

### frontend\src\components\chat\TokenUsageDisplay.tsx
- **Exports (Components/Functions/Stores):**
  - TokenUsageDisplay

### frontend\src\components\common\DocumentViewer.tsx
- **Exports (Components/Functions/Stores):**
  - FILE_INPUT_ACCEPT, DocumentViewer, SUPPORTED_EXTENSIONS

### frontend\src\components\memori\FactManagementPanel.tsx
- **Exports (Components/Functions/Stores):**
  - FactManagementPanel

### frontend\src\components\memori\InlineFactDisplay.tsx
- **Exports (Components/Functions/Stores):**
  - InlineFactDisplay

### frontend\src\components\memori\KnowledgeGraphView.tsx
- **Exports (Components/Functions/Stores):**
  - KnowledgeGraphView

### frontend\src\components\memori\MemorySidebar.tsx
- **Exports (Components/Functions/Stores):**
  - MemorySidebar

### frontend\src\components\memori\MemoryStatsWidget.tsx
- **Exports (Components/Functions/Stores):**
  - MemoryStatsWidget

### frontend\src\components\search\ProgressiveSearchUI.tsx
- **Exports (Components/Functions/Stores):**
  - ProgressiveSearchUI

### frontend\src\components\ui\toaster.tsx
- **Exports (Components/Functions/Stores):**
  - Toaster

### frontend\src\hooks\use-mobile.tsx
- **Exports (Components/Functions/Stores):**
  - useIsMobile

### frontend\src\hooks\use-toast.ts
- **Exports (Components/Functions/Stores):**
  - reducer

### frontend\src\hooks\useMemori.ts
- **Exports (Components/Functions/Stores):**
  - useMemori

### frontend\src\hooks\useToastQueue.ts
- **Exports (Components/Functions/Stores):**
  - useToastQueue

### frontend\src\lib\api.ts
- **Exports (Components/Functions/Stores):**
  - getKnowledgeGraph, startAsyncOcrJob, getSummaries, pollJobStatus, exportExtractionResults, batchExtractData, convertTextToFile, cleanupFacts, readTextFile, getExtractionTemplates, getExtractionResult, createExtractionTemplate, getSummary, deleteSummary, apiClient, updateExtractionTemplate, api, createBatchJobs, getMemoryStats, addFacts, deleteFact, getExtractionTemplate, recallFacts, getJobs, uploadAndExtractText, deleteExtractionTemplate, getExtractionResults, createSummary, addTriples, createBatchJobsWithBackend, extractData

### frontend\src\lib\auth.tsx
- **Exports (Components/Functions/Stores):**
  - AuthProvider, useAuth

### frontend\src\lib\authStore.ts
- **Exports (Components/Functions/Stores):**
  - useAuthStore

### frontend\src\lib\hooks\useCitations.ts
- **Exports (Components/Functions/Stores):**
  - useCitations

### frontend\src\lib\hooks\useConversations.ts
- **Exports (Components/Functions/Stores):**
  - useConversations

### frontend\src\lib\hooks\useMessages.ts
- **Exports (Components/Functions/Stores):**
  - useMessages

### frontend\src\lib\i18n\index.tsx
- **Exports (Components/Functions/Stores):**
  - useI18n, I18nProvider, useTranslation

### frontend\src\lib\i18n\translations\en.ts
- **Exports (Components/Functions/Stores):**
  - en

### frontend\src\lib\i18n\translations\vi.ts
- **Exports (Components/Functions/Stores):**
  - vi

### frontend\src\lib\queryClient.ts
- **Exports (Components/Functions/Stores):**
  - queryClient, QUERY_KEYS

### frontend\src\lib\utils.ts
- **Exports (Components/Functions/Stores):**
  - cn

### frontend\src\routes\Accounts.tsx
- **Exports (Components/Functions/Stores):**
  - Accounts

### frontend\src\routes\ApiKeys.tsx
- **Exports (Components/Functions/Stores):**
  - ApiKeys

### frontend\src\routes\Chat.tsx
- **Exports (Components/Functions/Stores):**
  - Chat

### frontend\src\routes\Compare.tsx
- **Exports (Components/Functions/Stores):**
  - Compare

### frontend\src\routes\Extraction.tsx
- **Exports (Components/Functions/Stores):**
  - Extraction

### frontend\src\routes\KnowledgeBase.tsx
- **Exports (Components/Functions/Stores):**
  - KnowledgeBase

### frontend\src\routes\Login.tsx
- **Exports (Components/Functions/Stores):**
  - Login

### frontend\src\routes\MemoryManagement.tsx
- **Exports (Components/Functions/Stores):**
  - MemoryManagement

### frontend\src\routes\Models.tsx
- **Exports (Components/Functions/Stores):**
  - Models

### frontend\src\routes\Register.tsx
- **Exports (Components/Functions/Stores):**
  - Register

### frontend\src\routes\Summarize.tsx
- **Exports (Components/Functions/Stores):**
  - Summarize

### frontend\src\types.ts
- **Exports (Components/Functions/Stores):**
  - ALLOWED_TYPES, MAX_FILE_SIZE, ALLOWED_EXTENSIONS

### frontend\src\utils\file.ts
- **Exports (Components/Functions/Stores):**
  - findMatches, formatBytes, downloadBlob, validateFile, isPdfFile, revokeObjectUrl, isImageFile, createObjectUrl, readFileAsText, getFileExtension, generateId

