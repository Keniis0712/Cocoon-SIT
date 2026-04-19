# Backend Services

This index mirrors the current service layout under `backend/app/services/` and `backend/app/worker/`.

## Root Services

- [Bootstrap Compatibility Wrapper](./bootstrap.md)

## Access

- [AuthSessionService](./access/auth-session-service.md)
- [UserService](./access/user-service.md)
- [RoleService](./access/role-service.md)
- [GroupService](./access/group-service.md)
- [InviteService](./access/invite-service.md)

## Audit

- [AuditService](./audit/audit-service.md)
- [AuditRunService](./audit/audit-run-service.md)
- [AuditArtifactService](./audit/audit-artifact-service.md)
- [AuditLinkService](./audit/audit-link-service.md)
- [AuditCleanupService](./audit/audit-cleanup-service.md)

## Bootstrap

- [BootstrapService](./bootstrap/bootstrap-service.md)
- [BootstrapAccessSeedService](./bootstrap/bootstrap-access-seed-service.md)
- [BootstrapCatalogSeedService](./bootstrap/bootstrap-catalog-seed-service.md)
- [BootstrapWorkspaceSeedService](./bootstrap/bootstrap-workspace-seed-service.md)

## Catalog

- [ProviderService](./catalog/provider-service.md)
- [ProviderCredentialService](./catalog/provider-credential-service.md)
- [ModelCatalogService](./catalog/model-catalog-service.md)
- [EmbeddingProviderService](./catalog/embedding-provider-service.md)
- [CharacterService](./catalog/character-service.md)
- [PromptTemplateAdminService](./catalog/prompt-template-admin-service.md)
- [TagService](./catalog/tag-service.md)

## Jobs

- [ChatDispatchQueue](./jobs/chat-dispatch-queue.md)
- [ChatDispatchCodec](./jobs/chat-dispatch-codec.md)
- [InMemoryChatDispatchQueue](./jobs/in-memory-chat-dispatch-queue.md)
- [RedisChatDispatchQueue](./jobs/redis-chat-dispatch-queue.md)
- [DurableJobService](./jobs/durable-job-service.md)

## Memory

- [MemoryService](./memory/memory-service.md)

## Observability

- [AuditQueryService](./observability/audit-query-service.md)
- [ArtifactAdminService](./observability/artifact-admin-service.md)
- [InsightQueryService](./observability/insight-query-service.md)

## Prompts

- [PromptTemplateService](./prompts/prompt-template-service.md)
- [PromptVariableService](./prompts/prompt-variable-service.md)
- [PromptRevisionService](./prompts/prompt-revision-service.md)
- [PromptRenderService](./prompts/prompt-render-service.md)
- [Prompt Registry](./prompts/prompt-registry.md)
- [Prompt Renderer](./prompts/prompt-renderer.md)

## Providers

- [ProviderRegistry](./providers/provider-registry.md)
- [ModelSelectionService](./providers/model-selection-service.md)
- [ProviderRuntimeConfigService](./providers/provider-runtime-config-service.md)
- [ProviderFactory](./providers/provider-factory.md)
- [ChatProvider Family](./providers/chat-provider.md)
- [OpenAI Compatible Provider](./providers/openai-compatible-provider.md)

## Realtime

- [RealtimeBackplane Family](./realtime/realtime-backplane.md)
- [ConnectionManager](./realtime/connection-manager.md)
- [EventDeliveryService](./realtime/event-delivery-service.md)
- [RealtimeHub](./realtime/realtime-hub.md)

## Runtime

- [ChatRuntime](./runtime/chat-runtime.md)
- [ContextBuilder](./runtime/context-builder.md)
- [Runtime Prompting Helpers](./runtime/prompting.md)
- [RoundPreparationService](./runtime/round-preparation-service.md)
- [RoundCleanupService](./runtime/round-cleanup-service.md)
- [StatePatchService](./runtime/state-patch-service.md)
- [ReplyDeliveryService](./runtime/reply-delivery-service.md)
- [SchedulerNode](./runtime/scheduler-node.md)
- [SideEffects](./runtime/side-effects.md)
- [MessageWindowService](./runtime/context/message-window-service.md)
- [ExternalContextService](./runtime/context/external-context-service.md)
- [MetaNode](./runtime/meta/meta-node.md)
- [GeneratorNode](./runtime/generation/generator-node.md)
- [PromptAssemblyService](./runtime/generation/prompt-assembly-service.md)

## Security

- [TokenService](./security/token-service.md)
- [TokenAuthenticationService](./security/token-authentication-service.md)
- [SecretCipher](./security/secret-cipher.md)
- [RBAC Helpers](./security/rbac.md)

## Storage

- [ArtifactStore](./storage/artifact-store.md)
- [FilesystemArtifactStore](./storage/filesystem-artifact-store.md)

## Worker

- [WorkerRuntime](./worker/worker-runtime.md)
- [ChatDispatchWorkerService](./worker/chat-dispatch-worker-service.md)
- [DurableJobWorkerService](./worker/durable-job-worker-service.md)
- [RuntimeActionService](./worker/runtime-action-service.md)
- [RollbackJobService](./worker/rollback-job-service.md)
- [CompactionJobService](./worker/compaction-job-service.md)
- [ArtifactCleanupJobService](./worker/artifact-cleanup-job-service.md)
- [RuntimeJobService](./worker/runtime-job-service.md)

## Workspace

- [CocoonTreeService](./workspace/cocoon-tree-service.md)
- [MessageDispatchService](./workspace/message-dispatch-service.md)
- [CocoonTagService](./workspace/cocoon-tag-service.md)
- [WorkspaceRealtimeService](./workspace/workspace-realtime-service.md)
