import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useOutletContext } from 'react-router-dom';
import { useI18n } from '@/lib/i18n';
import { apiClient, type Document, type Category } from '@/lib/api';
import type { AppOutletContext } from '@/App';
import DocumentViewer, { FILE_INPUT_ACCEPT } from '@/components/common/DocumentViewer';

// Upload progress state
interface UploadState {
  isUploading: boolean;
  currentFile: string;
  currentIndex: number;
  totalFiles: number;
  uploadPercent: number;
  stage: 'uploading' | 'categorizing' | 'done' | 'error';
  error?: string;
}

export default function KnowledgeBase() {
  const { t } = useI18n();
  const { pushToast } = useOutletContext<AppOutletContext>();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [uploadState, setUploadState] = useState<UploadState>({
    isUploading: false,
    currentFile: '',
    currentIndex: 0,
    totalFiles: 0,
    uploadPercent: 0,
    stage: 'done',
  });
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [newCategoryDescription, setNewCategoryDescription] = useState('');
  const [workspaceId, setWorkspaceId] = useState<string>('');
  const [processingDocs, setProcessingDocs] = useState<Set<string>>(new Set());
  const [processingDocsInfo, setProcessingDocsInfo] = useState<Map<string, Document>>(new Map());
  const pollingRef = useRef<NodeJS.Timeout | null>(null);

  // --- New states for enhancements ---
  const [viewMode, setViewMode] = useState<'active' | 'archived'>('active');
  const [deletePopoverId, setDeletePopoverId] = useState<string | null>(null);
  const [deleteCatPopoverId, setDeleteCatPopoverId] = useState<string | null>(null);
  const [deletingDocIds, setDeletingDocIds] = useState<Set<string>>(new Set());
  const [deletingCatId, setDeletingCatId] = useState<string | null>(null);
  const [viewDocId, setViewDocId] = useState<string | null>(null);
  const [viewDocMimeType, setViewDocMimeType] = useState<string>('');
  const [viewDocName, setViewDocName] = useState<string>('');
  const [openCategoryDropdown, setOpenCategoryDropdown] = useState<string | null>(null);
  const [cardMenuOpenId, setCardMenuOpenId] = useState<string | null>(null);

  // --- Sort state ---
  const [sortBy, setSortBy] = useState<'date' | 'name' | 'size' | 'status'>('date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [showSortMenu, setShowSortMenu] = useState(false);

  // --- Batch selection state ---
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [showBatchDeleteConfirm, setShowBatchDeleteConfirm] = useState(false);

  // --- Queue dropdown states ---
  const [showUploadQueue, setShowUploadQueue] = useState(false);
  const [showDownloadQueue, setShowDownloadQueue] = useState(false);
  const [downloadQueue, setDownloadQueue] = useState<Map<string, { name: string; progress: number; status: 'downloading' | 'done' | 'error' }>>(new Map());
  // On mount, clear any stale download queue from session (don't restore stuck items)
  useEffect(() => {
    sessionStorage.removeItem('ocr_ink_download_queue');
  }, []);
  const [showDownloadHistory, setShowDownloadHistory] = useState(false);
  const [downloadHistory, setDownloadHistory] = useState<Array<{ id: string; name: string; time: Date }>>(() => {
    try {
      const saved = localStorage.getItem('ocr_ink_download_history');
      if (saved) {
        return JSON.parse(saved).map((item: any) => ({
          ...item,
          time: new Date(item.time)
        }));
      }
    } catch (e) {
      console.error('Failed to parse download history', e);
    }
    return [];
  });

  // Persist download history
  useEffect(() => {
    localStorage.setItem('ocr_ink_download_history', JSON.stringify(downloadHistory));
  }, [downloadHistory]);

  // Download queue is ephemeral — no session persistence (downloads die on F5)

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // NOTE: Removed pre-fetch logic that caused 500/CORS errors when files don't exist on disk.
  // Documents are loaded on-demand when the user opens the viewer.

  // Load workspace on mount
  useEffect(() => {
    const loadWorkspace = async () => {
      try {
        const workspaces = await apiClient.getWorkspaces();
        if (workspaces.length > 0) {
          setWorkspaceId(workspaces[0].id);
        }
      } catch (error) {
        console.error('Failed to load workspaces:', error);
      }
    };
    loadWorkspace();
  }, []);

  const loadData = useCallback(async () => {
    if (!workspaceId) return;

    try {
      setIsLoading(true);
      const includeArchived = viewMode === 'archived';
      const [docs, cats] = await Promise.all([
        apiClient.getDocuments(workspaceId, {
          tags: selectedTags.length > 0 ? selectedTags : undefined,
          includeArchived,
        }),
        apiClient.getCategories(workspaceId),
      ]);
      setDocuments(docs);
      setCategories(cats);

      // Track processing documents with their info
      const processing = new Set<string>();
      const processingInfo = new Map<string, Document>();
      docs.forEach(doc => {
        if (doc.status === 'NEW' || doc.status === 'INDEXING' || doc.status === 'processing') {
          processing.add(doc.id);
          processingInfo.set(doc.id, doc);
        }
      });
      setProcessingDocs(processing);
      setProcessingDocsInfo(processingInfo);

    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId, selectedTags, viewMode]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Prevent background scrolling when popovers or modals are active
  useEffect(() => {
    const contentArea = document.getElementById('kb-content-area');
    const isOverlayOpen = !!(
      cardMenuOpenId ||
      openCategoryDropdown ||
      showDownloadHistory ||
      deletePopoverId ||
      deleteCatPopoverId ||
      showCategoryModal ||
      viewDocId
    );

    if (isOverlayOpen) {
      document.body.style.overflow = 'hidden';
      if (contentArea) contentArea.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
      if (contentArea) contentArea.style.overflow = 'auto';
    }
    return () => {
      document.body.style.overflow = '';
      if (contentArea) contentArea.style.overflow = 'auto';
    };
  }, [
    cardMenuOpenId,
    openCategoryDropdown,
    showDownloadHistory,
    deletePopoverId,
    deleteCatPopoverId,
    showCategoryModal,
    viewDocId
  ]);

  // Poll for processing documents
  useEffect(() => {
    if (processingDocs.size > 0) {
      pollingRef.current = setInterval(async () => {
        const stillProcessing = new Set<string>();
        const updatedInfo = new Map<string, Document>();
        let hasCompleted = false;

        for (const docId of processingDocs) {
          try {
            const doc = await apiClient.getDocument(docId);
            if (doc.status === 'NEW' || doc.status === 'INDEXING' || doc.status === 'processing') {
              stillProcessing.add(docId);
              updatedInfo.set(docId, doc);
            } else {
              hasCompleted = true;
            }
          } catch {
            hasCompleted = true;
          }
        }

        if (hasCompleted) {
          loadData();
        } else {
          setProcessingDocs(stillProcessing);
          setProcessingDocsInfo(updatedInfo);
        }
      }, 3000);
    } else {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    }

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, [processingDocs.size, loadData]);

  // --- Download a single document ---
  const handleDownloadDoc = async (docId: string, docName: string) => {
    // Use actual document name from the found document object
    const doc = documents.find(d => d.id === docId);
    const realName = doc?.name || doc?.originalName || doc?.title || docName;
    const key = docId;
    setDownloadQueue(prev => {
      const next = new Map(prev);
      next.set(key, { name: realName, progress: 50, status: 'downloading' });
      return next;
    });
    try {
      // Use attachment URL — forces browser to save file, not display it
      const url = apiClient.getDocumentAttachmentUrl(docId);
      const a = document.createElement('a');
      a.href = url;
      a.download = realName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      setDownloadQueue(prev => {
        const next = new Map(prev);
        next.set(key, { name: realName, progress: 100, status: 'done' });
        return next;
      });
      // Save to download history with REAL filename
      setDownloadHistory(prev => [{ id: docId, name: realName, time: new Date() }, ...prev].slice(0, 50));
      pushToast({ type: 'success', message: `${t.kb?.downloaded || 'Downloaded'}: ${realName}` });
      // Auto-remove from active queue after 3s
      setTimeout(() => {
        setDownloadQueue(prev => {
          const next = new Map(prev);
          next.delete(key);
          return next;
        });
      }, 3000);
    } catch (error: any) {
      console.error('Download failed:', error);
      setDownloadQueue(prev => {
        const next = new Map(prev);
        next.set(key, { name: realName, progress: 0, status: 'error' });
        return next;
      });
      pushToast({ type: 'error', message: `${t.kb?.downloadFailed || 'Download failed'}: ${realName}` });
      // Auto-remove error from queue after 5s
      setTimeout(() => {
        setDownloadQueue(prev => {
          const next = new Map(prev);
          next.delete(key);
          return next;
        });
      }, 5000);
    }
  };

  // --- Upload: auto-assign to selected category ---
  const handleUpload = async (files: FileList) => {
    if (!workspaceId) return;

    const fileArray = Array.from(files);
    const validFiles = fileArray.filter(f => f.size > 0);
    const skippedCount = fileArray.length - validFiles.length;

    if (skippedCount > 0) {
      pushToast({ type: 'error', message: t.kb?.emptyFileSkipped || `${skippedCount} empty file(s) skipped (0 bytes)` });
    }

    if (validFiles.length === 0) return;

    setUploadState({
      isUploading: true,
      currentFile: validFiles[0]?.name || '',
      currentIndex: 0,
      totalFiles: validFiles.length,
      uploadPercent: 0,
      stage: 'uploading',
    });

    let successCount = 0;
    let skipCount = 0;
    let completedCount = 0;
    let currentIndex = 0;

    const uploadNext = async (): Promise<void> => {
      if (currentIndex >= validFiles.length) return;

      const file = validFiles[currentIndex++];

      try {
        const doc = await apiClient.uploadDocument(workspaceId, file);
        successCount++;

        // Auto-assign to selected category if one is selected
        if (selectedCategory && selectedCategory !== 'uncategorized') {
          apiClient.setDocumentCategory(doc.id, selectedCategory).catch(e =>
            console.warn('Auto-assign category failed:', e)
          );
        }

        // Fire-and-forget auto-categorize (DON'T await — this was causing 95% stuck!)
        apiClient.categorizeDocument(doc.id).catch(e =>
          console.warn('Auto-categorize pending:', e)
        );
      } catch (error) {
        skipCount++;
        const rawMsg = error instanceof Error ? error.message : 'Upload failed';
        // Translate common backend errors to i18n
        let msg = rawMsg;
        if (/not allowed|executable|forbidden/i.test(rawMsg)) {
          msg = t.kb?.unsupportedFileType || `File type not supported`;
        }
        pushToast({ type: 'error', message: `${file.name}: ${msg}` });
        console.warn(`Skipped file ${file.name}:`, rawMsg);
      } finally {
        completedCount++;
        setUploadState(prev => ({
          ...prev,
          currentFile: file.name,
          currentIndex: completedCount - 1,
          uploadPercent: Math.floor((completedCount / validFiles.length) * 100),
          stage: 'uploading',
        }));
        await uploadNext();
      }
    };

    // Start MAX 3 concurrent upload workers
    const workers = [];
    for (let i = 0; i < Math.min(3, validFiles.length); i++) {
      workers.push(uploadNext());
    }
    await Promise.all(workers);

    setUploadState(prev => ({ ...prev, stage: 'done', isUploading: false, uploadPercent: 100 }));
    await loadData();

    if (successCount > 0) {
      pushToast({ type: 'success', message: `${successCount} ${t.kb?.filesUploaded || 'file(s) uploaded successfully'}` });
    }

    setTimeout(() => {
      setUploadState({
        isUploading: false,
        currentFile: '',
        currentIndex: 0,
        totalFiles: 0,
        uploadPercent: 0,
        stage: 'uploading',
      });
    }, 3000);
  };

  // --- Delete with popover (supports concurrent deletions) ---
  const handleDelete = (docId: string) => {
    setDeletePopoverId(null);
    // Add to deleting set immediately for instant UI feedback
    setDeletingDocIds(prev => new Set(prev).add(docId));

    // Also remove from processing panel immediately so it doesn't show as ghost
    setProcessingDocs(prev => {
      const next = new Set(prev);
      next.delete(docId);
      return next;
    });
    setProcessingDocsInfo(prev => {
      const next = new Map(prev);
      next.delete(docId);
      return next;
    });

    // Fire-and-forget async deletion (non-blocking)
    (async () => {
      try {
        const doc = documents.find(d => d.id === docId);
        const wasProcessing = doc && (doc.status === 'NEW' || doc.status === 'INDEXING');
        await apiClient.deleteDocument(docId);
        if (wasProcessing) {
          pushToast({ type: 'info', message: t.kb?.canceledProcessing || 'Processing canceled and document deleted' });
        }
        // Remove from local list immediately for snappy UI
        setDocuments(prev => prev.filter(d => d.id !== docId));
      } catch (error) {
        console.error('Delete failed:', error);
        pushToast({ type: 'error', message: 'Delete failed' });
      } finally {
        setDeletingDocIds(prev => {
          const next = new Set(prev);
          next.delete(docId);
          return next;
        });
        loadData();
      }
    })();
  };

  // --- Batch delete handler ---
  const handleBatchDelete = () => {
    setShowBatchDeleteConfirm(false);
    const idsToDelete = Array.from(selectedDocIds);
    // Immediately add all to deleting state
    setDeletingDocIds(prev => {
      const next = new Set(prev);
      idsToDelete.forEach(id => next.add(id));
      return next;
    });
    setSelectedDocIds(new Set());

    // Fire-and-forget concurrent deletes
    idsToDelete.forEach(docId => {
      (async () => {
        try {
          await apiClient.deleteDocument(docId);
          setDocuments(prev => prev.filter(d => d.id !== docId));
        } catch (error) {
          console.error(`Batch delete failed for ${docId}:`, error);
          pushToast({ type: 'error', message: t.kb?.batchDeleteFailed || 'Delete failed for a document' });
        } finally {
          setDeletingDocIds(prev => {
            const next = new Set(prev);
            next.delete(docId);
            return next;
          });
        }
      })();
    });

    pushToast({ type: 'info', message: t.kb?.batchDeleting || `Deleting ${idsToDelete.length} document(s)...` });
    // Refresh after a short delay
    setTimeout(() => loadData(), 2000);
  };

  // --- Toggle selection ---
  const toggleDocSelection = (docId: string) => {
    setSelectedDocIds(prev => {
      const next = new Set(prev);
      if (next.has(docId)) {
        next.delete(docId);
      } else {
        next.add(docId);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedDocIds.size === filteredDocuments.length) {
      setSelectedDocIds(new Set());
    } else {
      setSelectedDocIds(new Set(filteredDocuments.map(d => d.id)));
    }
  };

  // --- Archive ---
  const handleArchive = async (docId: string) => {
    try {
      await apiClient.archiveDocument(docId);
      await loadData();
    } catch (error) {
      console.error('Archive failed:', error);
    }
  };

  // --- Restore ---
  const handleRestore = async (docId: string) => {
    try {
      await apiClient.restoreDocument(docId);
      await loadData();
    } catch (error) {
      console.error('Restore failed:', error);
    }
  };

  // --- View document (opens DocumentViewer modal) ---
  const handleViewDocument = (docId: string) => {
    const doc = documents.find(d => d.id === docId);
    setViewDocId(docId);
    setViewDocName(doc?.name || doc?.originalName || doc?.title || 'document');
    setViewDocMimeType(doc?.mimeType || '');
  };

  const closeDocViewer = () => {
    setViewDocId(null);
    setViewDocMimeType('');
    setViewDocName('');
  };

  const handleCreateCategory = async () => {
    if (!workspaceId || !newCategoryName.trim()) return;
    try {
      await apiClient.createCategory(workspaceId, {
        name: newCategoryName.trim(),
        description: newCategoryDescription.trim() || undefined,
      });
      setNewCategoryName('');
      setNewCategoryDescription('');
      setShowCategoryModal(false);
      await loadData();
    } catch (error) {
      console.error('Create category failed:', error);
    }
  };

  const handleDeleteCategory = async (categoryId: string) => {
    try {
      setDeleteCatPopoverId(null);
      setDeletingCatId(categoryId);
      await apiClient.deleteCategory(categoryId);
      if (selectedCategory === categoryId) {
        setSelectedCategory(null);
      }
      await loadData();
    } catch (error) {
      console.error('Delete category failed:', error);
    } finally {
      setDeletingCatId(null);
    }
  };

  const handleMoveToCategory = async (docId: string, categoryId: string | null) => {
    try {
      setDocuments(prev => prev.map(doc =>
        doc.id === docId ? { ...doc, categoryId: categoryId || undefined } : doc
      ));
      await apiClient.setDocumentCategory(docId, categoryId);
      setOpenCategoryDropdown(null);
      await loadData();
    } catch (error) {
      console.error('Move to category failed:', error);
      await loadData();
    }
  };

  const formatSize = (bytes: number) => {
    if (!bytes || bytes === 0) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getStatusInfo = (status: string) => {
    switch (status) {
      case 'READY':
      case 'READY_BASIC':
      case 'indexed':
        return { color: 'bg-green-500/20 text-green-700 dark:text-green-400', label: 'Ready', icon: '✓' };
      case 'READY_ENRICHED':
        return { color: 'bg-purple-500/20 text-purple-700 dark:text-purple-400', label: 'Enriched', icon: '⚡' };
      case 'INDEXING':
      case 'processing':
        return { color: 'bg-blue-500/20 text-blue-700 dark:text-blue-400', label: 'Processing', icon: '⟳' };
      case 'NEW':
        return { color: 'bg-yellow-500/20 text-yellow-700 dark:text-yellow-400', label: 'Queued', icon: '⏳' };
      case 'FAILED':
      case 'error':
        return { color: 'bg-red-500/20 text-red-700 dark:text-red-400', label: 'Error', icon: '✗' };
      case 'DELETED':
        return { color: 'bg-gray-500/20 text-gray-500', label: 'Deleted', icon: '🗑' };
      case 'ARCHIVED':
        return { color: 'bg-amber-500/20 text-amber-700 dark:text-amber-400', label: t.kb?.archived || 'Archived', icon: '📦' };
      default:
        return { color: 'bg-gray-500/20 text-gray-700 dark:text-gray-400', label: status, icon: '?' };
    }
  };

  const isProcessing = (status: string) => {
    return status === 'NEW' || status === 'INDEXING' || status === 'processing';
  };

  // Filter documents: category + client-side search + active/archived + sort
  const filteredDocuments = useMemo(() => {
    let filtered = documents;

    // Filter by archived mode
    if (viewMode === 'archived') {
      filtered = filtered.filter(d => d.status === 'ARCHIVED');
    } else {
      filtered = filtered.filter(d => d.status !== 'ARCHIVED' && d.status !== 'DELETED');
    }

    // Filter by category
    if (selectedCategory === 'uncategorized') {
      filtered = filtered.filter(d => !d.categoryId);
    } else if (selectedCategory) {
      filtered = filtered.filter(d => d.categoryId === selectedCategory);
    }

    // Client-side search filter
    if (debouncedSearch) {
      const q = debouncedSearch.toLowerCase();
      filtered = filtered.filter(d =>
        (d.title?.toLowerCase().includes(q)) ||
        (d.name?.toLowerCase().includes(q)) ||
        (d.originalName?.toLowerCase().includes(q)) ||
        (d.tags?.some(tag => tag.toLowerCase().includes(q)))
      );
    }

    // Sort
    const sorted = [...filtered].sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case 'name':
          cmp = (a.name || a.title || '').localeCompare(b.name || b.title || '');
          break;
        case 'date':
          cmp = new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
          break;
        case 'size':
          cmp = (a.size || 0) - (b.size || 0);
          break;
        case 'status':
          cmp = (a.status || '').localeCompare(b.status || '');
          break;
      }
      return sortOrder === 'asc' ? cmp : -cmp;
    });

    return sorted;
  }, [documents, selectedCategory, debouncedSearch, viewMode, sortBy, sortOrder]);

  // Count documents respecting active/archived tab
  const tabDocuments = viewMode === 'archived'
    ? documents.filter(d => d.status === 'ARCHIVED')
    : documents.filter(d => d.status !== 'DELETED' && d.status !== 'ARCHIVED');
  const uncategorizedCount = tabDocuments.filter(d => !d.categoryId).length;

  return (
    <div className="flex h-[calc(100vh-88px)] gap-1.5 overflow-hidden">
      {/* Categories Sidebar */}
      <div className="w-60 flex flex-col gap-1.5">
        {/* Categories Header */}
        <div className="flex items-center justify-between rounded-xl border border-border bg-card/50 p-2">
          <h2 className="font-semibold">{t.kb?.categories || 'Categories'}</h2>
          <button
            onClick={() => setShowCategoryModal(true)}
            className="p-1.5 rounded-lg hover:bg-muted transition"
            title={t.kb?.addCategory || 'Add Category'}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </div>

        {/* Categories List */}
        <div className="flex-1 flex flex-col gap-1 rounded-xl border border-border bg-card/50 p-2 overflow-hidden">
          <div className="space-y-1 flex-1 overflow-y-auto scrollbar-thin pr-1">
            <button
              onClick={() => setSelectedCategory(null)}
              className={`w-full text-left px-2.5 py-2 rounded-lg text-sm transition flex items-center justify-between ${selectedCategory === null ? 'bg-primary/10 text-primary font-medium' : 'hover:bg-muted'
                }`}
            >
              <span className="flex items-center gap-2">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                </svg>
                {t.kb?.allDocuments || 'All Documents'}
              </span>
              <span className="text-xs bg-muted px-2 py-0.5 rounded-full">{tabDocuments.length}</span>
            </button>

            {/* Category List */}
            {categories.map((cat) => {
              const isDeletingCat = deletingCatId === cat.id;
              return (
                <div
                  key={cat.id}
                  className={`group rounded-lg transition relative ${selectedCategory === cat.id ? 'bg-primary/10' : 'hover:bg-muted'
                    } ${isDeletingCat ? 'opacity-50 pointer-events-none' : ''}`}
                >
                  <button
                    onClick={() => setSelectedCategory(cat.id)}
                    className={`w-full text-left px-3 py-2.5 text-sm flex items-center justify-between ${selectedCategory === cat.id ? 'text-primary font-medium' : ''
                      }`}
                  >
                    <span className="flex items-center gap-2 flex-1 min-w-0">
                      <span
                        className="w-3 h-3 rounded-sm flex-shrink-0"
                        style={{ backgroundColor: cat.color || '#6366f1' }}
                      />
                      <span className="truncate">{cat.name}</span>
                    </span>
                    <span className="flex items-center gap-1">
                      {isDeletingCat ? (
                        <svg className="w-4 h-4 animate-spin text-destructive mr-1" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                      ) : (
                        <>
                          <span className="text-xs bg-muted px-2 py-0.5 rounded-full">{tabDocuments.filter(d => d.categoryId === cat.id).length}</span>
                          <button
                            onClick={(e) => { e.stopPropagation(); setDeleteCatPopoverId(cat.id); }}
                            className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive transition"
                            title={t.kb?.deleteCategory || 'Delete category'}
                          >
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        </>
                      )}
                    </span>
                  </button>
                  {cat.description && selectedCategory === cat.id && (
                    <p className="px-3 pb-2 text-xs text-muted-foreground">{cat.description}</p>
                  )}

                  {/* Delete Category Popover */}
                  {deleteCatPopoverId === cat.id && (
                    <>
                      <div className="fixed inset-0 z-40" onClick={(e) => { e.stopPropagation(); setDeleteCatPopoverId(null); }} />
                      <div className="absolute left-0 right-0 top-full z-50 mt-1 p-3 rounded-xl border border-destructive/30 bg-card shadow-lg animate-in fade-in slide-in-from-top-1 duration-200">
                        <p className="text-xs text-muted-foreground mb-2">{t.kb?.confirmDeleteCategory || 'Delete this category? Documents will become uncategorized.'}</p>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleDeleteCategory(cat.id)}
                            className="flex-1 px-2 py-1.5 text-xs font-medium rounded-lg bg-destructive text-destructive-foreground hover:bg-destructive/90 transition"
                          >
                            {t.common?.delete || 'Delete'}
                          </button>
                          <button
                            onClick={() => setDeleteCatPopoverId(null)}
                            className="flex-1 px-2 py-1.5 text-xs font-medium rounded-lg border border-border bg-background hover:bg-muted transition"
                          >
                            {t.common?.cancel || 'Cancel'}
                          </button>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )
            })}

            {/* Uncategorized */}
            <button
              onClick={() => setSelectedCategory('uncategorized')}
              className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition flex items-center justify-between ${selectedCategory === 'uncategorized' ? 'bg-primary/10 text-primary font-medium' : 'hover:bg-muted text-muted-foreground'
                }`}
            >
              <span className="flex items-center gap-2">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
                </svg>
                {t.kb?.uncategorized || 'Uncategorized'}
              </span>
              <span className="text-xs bg-muted px-2 py-0.5 rounded-full">{uncategorizedCount}</span>
            </button>
          </div>

          {/* Category Summary - FIXED AT BOTTOM */}
          {selectedCategory && selectedCategory !== 'uncategorized' && (
            <div className="flex-shrink-0 mt-0 p-3 rounded-xl border border-border bg-card/50">
              {(() => {
                const cat = categories.find(c => c.id === selectedCategory);
                if (!cat) return null;
                return (
                  <div className="text-xs space-y-2">
                    {cat.contentSummary && cat.contentSummary.trim() !== '' ? (
                      <div className="max-h-[160px] overflow-y-auto pr-1 text-muted-foreground scrollbar-thin">
                        <p>{cat.contentSummary}</p>
                      </div>
                    ) : (
                      <p className="text-muted-foreground italic">{t.kb?.noSummary || 'No summary available for this category.'}</p>
                    )}
                    {cat.keywords && cat.keywords.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {cat.keywords.slice(0, 5).map((kw, i) => (
                          <span key={i} className="bg-muted px-2 py-0.5 rounded-full">{kw}</span>
                        ))}
                      </div>
                    )}
                    <button
                      onClick={async () => {
                        try {
                          setCategories(prev => prev.map(c =>
                            c.id === selectedCategory ? { ...c, contentSummary: `⏳ ${t.kb?.generatingSummary || 'Generating summary...'}` } : c
                          ));
                          const result = await apiClient.refreshCategorySummary(selectedCategory);
                          if (result?.summary) {
                            setCategories(prev => prev.map(c =>
                              c.id === selectedCategory ? { ...c, contentSummary: result.summary } : c
                            ));
                          }
                          await loadData();
                        } catch (error) {
                          console.error('Refresh summary failed:', error);
                          setCategories(prev => prev.map(c =>
                            c.id === selectedCategory ? { ...c, contentSummary: `❌ ${t.kb?.summaryFailed || 'Could not generate summary.'}` } : c
                          ));
                        }
                      }}
                      className="w-full mt-2 px-2 py-2 rounded-lg text-xs font-medium text-center bg-primary/10 text-primary hover:bg-primary/20 transition flex items-center justify-center gap-1.5"
                      title={t.kb?.createAiSummary || 'Generate AI summary'}
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                      {cat.contentSummary && !cat.contentSummary.startsWith('⏳') ? (t.kb?.refreshSummary || 'Refresh summary') : (t.kb?.createAiSummary || 'Generate AI summary')}
                    </button>
                  </div>
                );
              })()}
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col gap-2 overflow-hidden">
        {/* Header Section */}
        <div className="flex items-center justify-between flex-shrink-0">
          <div>
            <h1 className="text-xl font-bold">{t.kb?.title || 'Knowledge Base'}</h1>
            <p className="text-xs text-muted-foreground">
              {selectedCategory === 'uncategorized'
                ? t.kb?.documentsWithoutCategory || 'Documents without category'
                : selectedCategory
                  ? categories.find(c => c.id === selectedCategory)?.name
                  : t.kb?.subtitle || 'Manage your documents'}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {/* Upload Queue Indicator */}
            {(uploadState.isUploading || processingDocsInfo.size > 0) && (
              <div className="relative">
                <button
                  onClick={() => { setShowUploadQueue(!showUploadQueue); setShowDownloadQueue(false); }}
                  className="relative p-2 rounded-xl border border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/50 transition"
                  title={t.kb?.uploadQueue || 'Upload queue'}
                >
                  <svg className="w-4 h-4 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-blue-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                    {uploadState.isUploading ? uploadState.totalFiles : processingDocsInfo.size}
                  </span>
                </button>

                {/* Upload Queue Dropdown */}
                {showUploadQueue && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setShowUploadQueue(false)} />
                    <div className="absolute right-0 top-full z-50 mt-2 w-80 rounded-xl border border-border bg-card shadow-xl animate-in fade-in slide-in-from-top-2 duration-200">
                      <div className="p-3 border-b border-border flex items-center gap-2">
                        <svg className="w-4 h-4 text-blue-500 animate-spin" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        <span className="text-sm font-medium">{t.kb?.uploadQueue || 'Upload & Processing Queue'}</span>
                      </div>
                      <div className="max-h-64 overflow-auto p-2 space-y-2">
                        {/* Current upload */}
                        {uploadState.isUploading && (
                          <div className="p-2.5 rounded-lg bg-primary/5 border border-primary/20 space-y-1.5">
                            <div className="flex items-center justify-between text-[12px]">
                              <span className="truncate font-medium">{uploadState.currentFile}</span>
                              <span className="text-primary font-medium">{uploadState.uploadPercent}%</span>
                            </div>
                            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                              <div className="h-full bg-primary transition-all duration-300" style={{ width: `${uploadState.uploadPercent}%` }} />
                            </div>
                            <div className="text-[11px] text-muted-foreground">
                              {uploadState.currentIndex + 1} / {uploadState.totalFiles} • {uploadState.stage === 'uploading' ? (t.kb?.uploading || 'Uploading') : (t.kb?.categorizing || 'Categorizing')}
                            </div>
                          </div>
                        )}
                        {/* Processing docs */}
                        {Array.from(processingDocsInfo.values()).map((doc) => {
                          const progress = doc.processingProgress || 0;
                          const step = doc.processingStep || (doc.status === 'NEW' ? (t.kb?.waitingInQueue || 'Waiting...') : (t.kb?.processingStatus || 'Processing...'));
                          return (
                            <div key={doc.id} className="p-2.5 rounded-lg bg-muted/50 space-y-1.5">
                              <div className="flex items-center justify-between text-[12px]">
                                <span className="truncate font-medium">{doc.title || doc.name || doc.originalName}</span>
                                <span className="text-blue-500 font-medium">{progress}%</span>
                              </div>
                              <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                                <div className={`h-full transition-all duration-500 ${doc.status === 'NEW' ? 'bg-yellow-400' : 'bg-blue-500'}`} style={{ width: `${Math.max(progress, 2)}%` }} />
                              </div>
                              <div className="text-[11px] text-muted-foreground truncate">{step}</div>
                            </div>
                          );
                        })}
                        {!uploadState.isUploading && processingDocsInfo.size === 0 && (
                          <p className="text-xs text-muted-foreground text-center py-3">{t.kb?.noActiveUploads || 'No active uploads'}</p>
                        )}
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* Download Queue Indicator */}
            {downloadQueue.size > 0 && (
              <div className="relative">
                <button
                  onClick={() => { setShowDownloadQueue(!showDownloadQueue); setShowUploadQueue(false); }}
                  className="relative p-2 rounded-xl border border-green-300 dark:border-green-700 bg-green-50 dark:bg-green-900/30 text-green-600 dark:text-green-400 hover:bg-green-100 dark:hover:bg-green-900/50 transition"
                  title={t.kb?.downloadQueue || 'Download queue'}
                >
                  <svg className="w-4 h-4 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-green-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                    {downloadQueue.size}
                  </span>
                </button>

                {/* Download Queue Dropdown */}
                {showDownloadQueue && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setShowDownloadQueue(false)} />
                    <div className="absolute right-0 top-full z-50 mt-2 w-72 rounded-xl border border-border bg-card shadow-xl animate-in fade-in slide-in-from-top-2 duration-200">
                      <div className="p-3 border-b border-border flex items-center gap-2">
                        <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                        <span className="text-sm font-medium">{t.kb?.downloadQueue || 'Download Queue'}</span>
                      </div>
                      <div className="max-h-48 overflow-auto p-2 space-y-2">
                        {Array.from(downloadQueue.entries()).map(([id, info]) => (
                          <div key={id} className="p-2 rounded-lg bg-muted/50 space-y-1">
                            <div className="flex items-center justify-between text-[12px]">
                              <span className="truncate font-medium">{info.name}</span>
                              <span className={info.status === 'done' ? 'text-green-500' : info.status === 'error' ? 'text-destructive' : 'text-blue-500'}>
                                {info.status === 'done' ? '✓' : info.status === 'error' ? '✗' : `${info.progress}%`}
                              </span>
                            </div>
                            <div className="h-1 bg-muted rounded-full overflow-hidden">
                              <div className={`h-full transition-all duration-300 ${info.status === 'done' ? 'bg-green-500' : info.status === 'error' ? 'bg-destructive' : 'bg-blue-500'}`} style={{ width: `${info.progress}%` }} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* Upload Button */}
            <label className={`cursor-pointer rounded-xl px-4 py-2 text-sm font-semibold transition flex items-center gap-2 ${uploadState.isUploading
              ? 'bg-primary/50 text-primary-foreground cursor-wait'
              : 'bg-primary text-primary-foreground hover:bg-primary/90'
              }`}>
              <input
                type="file"
                multiple
                accept={FILE_INPUT_ACCEPT}
                className="hidden"
                onChange={(e) => {
                  if (e.target.files) handleUpload(e.target.files);
                  e.target.value = ''; // Reset so same file can trigger onChange again
                }}
                disabled={uploadState.isUploading}
              />
              {uploadState.isUploading ? (
                <>
                  <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  {t.kb?.uploading || 'Uploading'}...
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                  {t.kb?.upload || 'Upload Documents'}
                </>
              )}
            </label>

            {/* Download History Button (always visible) */}
            <div className="relative">
              <button
                onClick={() => { setShowDownloadHistory(!showDownloadHistory); setShowUploadQueue(false); setShowDownloadQueue(false); }}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-green-300 dark:border-green-700 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 hover:bg-green-100 dark:hover:bg-green-900/40 transition text-sm font-medium"
                title={t.kb?.downloadHistory || 'Download history'}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3M3 17V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
                </svg>
                {t.kb?.downloadHistory || 'Downloads'}
                {downloadHistory.length > 0 && (
                  <span className="w-5 h-5 bg-green-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                    {downloadHistory.length}
                  </span>
                )}
              </button>

              {/* Download History Popover */}
              {showDownloadHistory && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowDownloadHistory(false)} />
                  <div className="absolute right-0 top-full z-50 mt-2 w-80 rounded-xl border border-border bg-card shadow-xl animate-in fade-in slide-in-from-top-2 duration-200">
                    <div className="p-3 border-b border-border flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <svg className="w-4 h-4 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3M3 17V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
                        </svg>
                        <span className="text-sm font-medium">{t.kb?.downloadHistory || 'Download History'}</span>
                      </div>
                      {downloadHistory.length > 0 && (
                        <button
                          onClick={() => setDownloadHistory([])}
                          className="text-[13px] text-muted-foreground hover:text-destructive transition"
                        >
                          {t.common?.clearAll || 'Clear all'}
                        </button>
                      )}
                    </div>
                    <div className="max-h-64 overflow-auto p-2 space-y-1">
                      {downloadHistory.length === 0 ? (
                        <p className="text-xs text-muted-foreground text-center py-4">{t.kb?.noDownloads || 'No download history yet'}</p>
                      ) : (
                        downloadHistory.map((item, idx) => (
                          <div key={`${item.id}-${idx}`} className="flex items-center gap-2 p-2 rounded-lg hover:bg-muted/50 transition">
                            <svg className="w-3.5 h-3.5 text-green-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium truncate">{item.name}</p>
                              <p className="text-[12px] text-muted-foreground">
                                {item.time.toLocaleTimeString()} — {item.time.toLocaleDateString()}
                              </p>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Search Bar + Sort + Archive Toggle */}
        <div className="flex gap-2 flex-shrink-0 items-center">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t.kb?.searchPlaceholder || 'Search documents...'}
            className="flex-1 rounded-xl border border-border bg-background px-4 py-2 text-sm focus:border-primary focus:outline-none"
          />

          {/* Sort Dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowSortMenu(!showSortMenu)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-border bg-background hover:bg-muted text-sm transition"
              title="Sort documents"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
              </svg>
              <span className="hidden sm:inline">{sortBy === 'date' ? (t.kb?.sortDate || 'Date') : sortBy === 'name' ? (t.kb?.sortName || 'Name') : sortBy === 'size' ? (t.kb?.sortSize || 'Size') : (t.kb?.sortStatus || 'Status')}</span>
              <svg className={`w-3 h-3 transition-transform ${sortOrder === 'asc' ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {showSortMenu && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowSortMenu(false)} />
                <div className="absolute right-0 top-full z-50 mt-1 w-44 rounded-xl border border-border bg-card shadow-lg py-1 animate-in fade-in slide-in-from-top-1 duration-150">
                  {(['date', 'name', 'size', 'status'] as const).map((key) => (
                    <button
                      key={key}
                      onClick={() => {
                        if (sortBy === key) {
                          setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
                        } else {
                          setSortBy(key);
                          setSortOrder(key === 'name' ? 'asc' : 'desc');
                        }
                        setShowSortMenu(false);
                      }}
                      className={`w-full text-left px-3 py-2 text-xs hover:bg-muted transition flex items-center justify-between ${sortBy === key ? 'bg-primary/10 text-primary font-medium' : ''}`}
                    >
                      <span>{key === 'date' ? `📅 ${t.kb?.sortDate || 'Date created'}` : key === 'name' ? `🔤 ${t.kb?.sortName || 'Name'}` : key === 'size' ? `📦 ${t.kb?.sortSize || 'File size'}` : `🏷️ ${t.kb?.sortStatus || 'Status'}`}</span>
                      {sortBy === key && (
                        <span className="text-[10px]">{sortOrder === 'asc' ? '↑' : '↓'}</span>
                      )}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>

          <div className="flex rounded-xl border border-border overflow-hidden">
            <button
              onClick={() => setViewMode('active')}
              className={`px-3 py-2 text-sm font-medium transition ${viewMode === 'active'
                ? 'bg-primary text-primary-foreground'
                : 'bg-background hover:bg-muted text-muted-foreground'
                }`}
            >
              {t.kb?.activeDocuments || 'Active'}
            </button>
            <button
              onClick={() => setViewMode('archived')}
              className={`px-3 py-2 text-sm font-medium transition flex items-center gap-1 ${viewMode === 'archived'
                ? 'bg-amber-600 text-white'
                : 'bg-background hover:bg-muted text-muted-foreground'
                }`}
            >
              📦 {t.kb?.archivedDocuments || 'Archive'}
            </button>
          </div>
        </div>

        {/* Batch Selection Toolbar */}
        {selectedDocIds.size > 0 && (
          <div className="flex items-center gap-3 px-4 py-2 rounded-xl border border-primary/30 bg-primary/5 flex-shrink-0 animate-in fade-in slide-in-from-top-1 duration-200">
            <button
              onClick={toggleSelectAll}
              className="flex items-center gap-2 text-sm font-medium text-primary hover:underline"
            >
              <input
                type="checkbox"
                checked={selectedDocIds.size === filteredDocuments.length}
                readOnly
                className="rounded border-primary accent-primary"
              />
              {selectedDocIds.size === filteredDocuments.length ? (t.kb?.deselectAll || 'Deselect all') : (t.kb?.selectAll || 'Select all')}
            </button>
            <span className="text-sm text-muted-foreground">
              {selectedDocIds.size} {t.kb?.selected || 'selected'}
            </span>
            <div className="flex-1" />
            <button
              onClick={() => setShowBatchDeleteConfirm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-destructive text-destructive-foreground hover:bg-destructive/90 transition"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              {t.kb?.deleteSelected || 'Delete'} {selectedDocIds.size}
            </button>
            <button
              onClick={() => setSelectedDocIds(new Set())}
              className="p-1.5 rounded-lg hover:bg-muted transition text-muted-foreground"
              title={t.kb?.cancelSelection || 'Cancel selection'}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        {/* Batch Delete Confirmation Modal */}
        {showBatchDeleteConfirm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-card border border-destructive/30 rounded-2xl p-6 w-96 shadow-xl animate-in fade-in zoom-in-95 duration-200">
              <div className="w-10 h-10 rounded-full bg-destructive/10 text-destructive flex items-center justify-center mx-auto mb-3">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-center mb-2">{t.kb?.batchDeleteTitle || 'Delete documents?'} ({selectedDocIds.size})</h3>
              <p className="text-sm text-muted-foreground text-center mb-4">
                {t.kb?.batchDeleteMessage || 'This action is permanent and cannot be undone. All data including OCR text and embeddings will be removed.'}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setShowBatchDeleteConfirm(false)}
                  className="flex-1 px-4 py-2 rounded-lg text-sm font-medium border border-border bg-background hover:bg-muted transition"
                >
                  {t.common?.cancel || 'Cancel'}
                </button>
                <button
                  onClick={handleBatchDelete}
                  className="flex-1 px-4 py-2 rounded-lg text-sm font-medium bg-destructive text-destructive-foreground hover:bg-destructive/90 transition"
                >
                  {t.kb?.batchDeleteConfirm || 'Delete all'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Bordered Content Area */}
        <div id="kb-content-area" className="flex-1 rounded-xl border border-border bg-card/50 p-3 overflow-auto space-y-3">


          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <svg className="h-8 w-8 animate-spin text-primary" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            </div>
          ) : filteredDocuments.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border bg-card/50 p-12 text-center">
              <svg className="mx-auto h-12 w-12 text-muted-foreground opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="mt-4 text-muted-foreground">{viewMode === 'archived'
                ? (t.kb?.noDocuments || 'No archived documents.')
                : (t.kb?.noDocuments || 'No documents yet. Upload some to get started.')}</p>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {filteredDocuments.map(doc => {
                const statusInfo = getStatusInfo(doc.status);
                const processing = isProcessing(doc.status) || processingDocsInfo.has(doc.id);
                const isDeletingDoc = deletingDocIds.has(doc.id);

                // Helper for smart filename truncation
                const docNameStr = doc.name || doc.originalName || 'document';
                const lastDot = docNameStr.lastIndexOf('.');
                const nameBase = lastDot > 0 ? docNameStr.substring(0, lastDot) : docNameStr;
                const nameExt = lastDot > 0 ? docNameStr.substring(lastDot) : '';

                const isSelected = selectedDocIds.has(doc.id);

                return (
                  <div
                    key={doc.id}
                    className={`relative rounded-2xl border bg-card p-4 transition hover:shadow-md group cursor-pointer ${isSelected ? 'border-primary ring-2 ring-primary/20' : ''} ${isDeletingDoc ? 'border-destructive/30 bg-destructive/5 pointer-events-none' :
                      processing ? 'border-blue-200 dark:border-blue-800 bg-blue-50/30 dark:bg-blue-900/10' :
                        doc.status === 'ARCHIVED' ? 'border-amber-200 dark:border-amber-800 bg-amber-50/20 dark:bg-amber-900/10' :
                          'border-border'
                      }`}
                    onClick={(e) => {
                      // Only toggle selection if clicking on the card body (not on buttons/dropdowns)
                      const target = e.target as HTMLElement;
                      if (target.closest('button') || target.closest('select') || target.closest('input') || target.closest('[role="menu"]')) return;
                      toggleDocSelection(doc.id);
                    }}
                  >
                    {/* Selection checkbox — only visible when in selection mode */}
                    {selectedDocIds.size > 0 && (
                      <div className="absolute top-2.5 left-2.5 z-10">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleDocSelection(doc.id)}
                          className="w-4 h-4 rounded border-border accent-primary cursor-pointer"
                        />
                      </div>
                    )}
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <h3 className="flex font-medium text-[15px]" title={docNameStr}>
                          <span className="truncate">{nameBase}</span>
                          <span className="flex-shrink-0">{nameExt}</span>
                        </h3>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {formatSize(doc.size)} • {doc.mimeType?.split('/')[1] || 'file'}
                        </p>
                      </div>
                      <span className={`ml-2 rounded-full px-2 py-0.5 text-xs flex items-center gap-1 ${isDeletingDoc ? 'bg-destructive/10 text-destructive' : statusInfo.color}`}>
                        {isDeletingDoc ? (
                          <>
                            <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                            <span>{t.kb?.deleting || 'Deleting...'}</span>
                          </>
                        ) : processing ? (
                          <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24" fill="none">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                        ) : (
                          <span>{statusInfo.icon}</span>
                        )}
                        {!isDeletingDoc && statusInfo.label}
                      </span>
                    </div>

                    {doc.tags && doc.tags.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {doc.tags.map((tag) => (
                          <span key={tag} className="rounded-full bg-muted px-2 py-0.5 text-xs">{tag}</span>
                        ))}
                      </div>
                    )}

                    <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                      <span>{doc.chunkCount || 0} {t.kb?.chunks || 'chunks'}</span>
                      <span>{new Date(doc.createdAt).toLocaleDateString()}</span>
                    </div>

                    <div className="mt-3 flex items-center gap-1.5">
                      {/* Custom Category Combobox */}
                      <div className="relative flex-1 min-w-0">
                        <button
                          onClick={() => setOpenCategoryDropdown(openCategoryDropdown === doc.id ? null : doc.id)}
                          disabled={doc.status === 'DELETED' || doc.status === 'ARCHIVED'}
                          className="w-full rounded-xl border border-border bg-background px-3 py-1.5 text-xs text-left flex items-center justify-between gap-1 hover:border-primary/50 transition disabled:opacity-50"
                        >
                          <span className="truncate">
                            {doc.categoryId
                              ? categories.find(c => c.id === doc.categoryId)?.name || (t.kb?.noCategory || 'No Category')
                              : (t.kb?.noCategory || 'No Category')}
                          </span>
                          <svg className="w-3 h-3 flex-shrink-0 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </button>

                        {openCategoryDropdown === doc.id && (
                          <>
                            <div className="fixed inset-0 z-40" onClick={(e) => { e.stopPropagation(); setOpenCategoryDropdown(null); }} />
                            <div className="absolute left-0 right-0 top-full z-50 mt-1 rounded-xl border border-border bg-card shadow-lg py-1 max-h-44 overflow-auto animate-in fade-in slide-in-from-top-1 duration-150">
                              <button
                                onClick={() => handleMoveToCategory(doc.id, null)}
                                className={`w-full text-left px-3 py-2 text-xs hover:bg-muted transition ${!doc.categoryId ? 'bg-primary/10 text-primary font-medium' : ''}`}
                              >
                                {t.kb?.noCategory || 'No Category'}
                              </button>
                              {categories.map((cat) => (
                                <button
                                  key={cat.id}
                                  onClick={() => handleMoveToCategory(doc.id, cat.id)}
                                  className={`w-full text-left px-3 py-2 text-xs hover:bg-muted transition flex items-center gap-2 ${doc.categoryId === cat.id ? 'bg-primary/10 text-primary font-medium' : ''}`}
                                >
                                  <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ backgroundColor: cat.color || '#6366f1' }} />
                                  <span className="truncate">{cat.name}</span>
                                </button>
                              ))}
                            </div>
                          </>
                        )}
                      </div>

                      {/* ⋯ Kebab Action Menu */}
                      <div className="relative flex-shrink-0">
                        <button
                          onClick={() => setCardMenuOpenId(cardMenuOpenId === doc.id ? null : doc.id)}
                          className="rounded-xl border border-border px-2 py-1.5 text-xs transition hover:bg-muted"
                          title="Actions"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h.01M12 12h.01M19 12h.01M6 12a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0zm7 0a1 1 0 11-2 0 1 1 0 012 0z" />
                          </svg>
                        </button>

                        {cardMenuOpenId === doc.id && (
                          <>
                            <div className="fixed inset-0 z-40" onClick={(e) => { e.stopPropagation(); setCardMenuOpenId(null); }} />
                            <div className="absolute right-0 top-full z-50 mt-1 w-48 rounded-xl border border-border bg-card shadow-lg py-1 animate-in fade-in slide-in-from-top-1 duration-150">
                              {/* View (opens tab-based viewer with Original + OCR tabs) */}
                              <button
                                onClick={() => { setCardMenuOpenId(null); handleViewDocument(doc.id); }}
                                disabled={doc.status === 'DELETED' || processing}
                                className="w-full text-left px-3 py-2.5 text-[12px] hover:bg-muted transition flex items-center gap-2 disabled:opacity-50"
                              >
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                </svg>
                                {t.kb?.viewDocument || 'View document'}
                              </button>
                              {/* Download */}
                              <button
                                onClick={() => { setCardMenuOpenId(null); handleDownloadDoc(doc.id, doc.name || doc.originalName || 'document'); }}
                                disabled={doc.status === 'DELETED' || processing}
                                className="w-full text-left px-3 py-2.5 text-[12px] hover:bg-muted transition flex items-center gap-2 disabled:opacity-50"
                              >
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                </svg>
                                {t.kb?.downloadFile || 'Download file'}
                              </button>
                              {/* Archive / Restore */}
                              {viewMode === 'archived' ? (
                                <button
                                  onClick={() => { setCardMenuOpenId(null); handleRestore(doc.id); }}
                                  className="w-full text-left px-3 py-2.5 text-[12px] hover:bg-muted transition flex items-center gap-2 text-green-700 dark:text-green-400"
                                >
                                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                  </svg>
                                  {t.kb?.restore || 'Restore'}
                                </button>
                              ) : (
                                <button
                                  onClick={() => { setCardMenuOpenId(null); handleArchive(doc.id); }}
                                  disabled={doc.status === 'DELETED' || processing}
                                  className="w-full text-left px-3 py-2.5 text-[12px] hover:bg-muted transition flex items-center gap-2 text-amber-700 dark:text-amber-400 disabled:opacity-50"
                                >
                                  <span className="text-sm">📦</span>
                                  {t.kb?.archive || 'Archive'}
                                </button>
                              )}
                              {/* Divider */}
                              <div className="my-1 border-t border-border" />
                              {/* Delete */}
                              <button
                                onClick={() => { setCardMenuOpenId(null); setDeletePopoverId(doc.id); }}
                                disabled={doc.status === 'DELETED'}
                                className="w-full text-left px-3 py-2.5 text-[12px] hover:bg-destructive/10 transition flex items-center gap-2 text-destructive disabled:opacity-50"
                              >
                                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                                {t.kb?.delete || 'Delete'}
                              </button>
                            </div>
                          </>
                        )}
                      </div>

                      {/* Full-card Delete Popover overlay */}
                      {deletePopoverId === doc.id && (
                        <>
                          <div className="fixed inset-0 z-[60]" onClick={(e) => { e.stopPropagation(); setDeletePopoverId(null); }} />
                          <div className="absolute inset-0 z-[61] flex flex-col items-center justify-center p-4 rounded-2xl bg-background/95 backdrop-blur-sm border-2 border-destructive shadow-lg animate-in fade-in zoom-in-95 duration-200">
                            <div className="relative z-50 text-center space-y-3 w-full max-w-[260px]">
                              <div className="w-8 h-8 rounded-full bg-destructive/10 text-destructive flex items-center justify-center mx-auto">
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                              </div>
                              <p className="text-sm text-muted-foreground leading-snug">{t.kb?.confirmDeletePermanent || 'Delete permanently? Data removed from DB.'}</p>
                              <div className="flex gap-2">
                                <button
                                  onClick={(e) => { e.stopPropagation(); handleDelete(doc.id); }}
                                  className="flex-1 px-2 py-1.5 text-xs font-medium rounded-lg bg-destructive text-destructive-foreground hover:bg-destructive/90 transition"
                                >
                                  {t.kb?.deleteConfirm || 'Confirm delete'}
                                </button>
                                <button
                                  onClick={(e) => { e.stopPropagation(); setDeletePopoverId(null); }}
                                  className="flex-1 px-2 py-1.5 text-xs font-medium rounded-lg border border-border bg-background hover:bg-muted transition"
                                >
                                  {t.common?.cancel || 'Cancel'}
                                </button>
                              </div>
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Create Category Modal — with border for dark theme */}
      {showCategoryModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-2xl p-6 w-96 shadow-xl">
            <h3 className="text-lg font-semibold mb-4">{t.kb?.createCategory || 'Create Category'}</h3>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-muted-foreground">{t.kb?.categoryName || 'Name'}</label>
                <input
                  type="text"
                  value={newCategoryName}
                  onChange={(e) => setNewCategoryName(e.target.value)}
                  placeholder={t.kb?.categoryNamePlaceholder || 'e.g., Contracts, Reports...'}
                  className="w-full mt-1 rounded-xl border border-border bg-background px-4 py-2 text-sm focus:border-primary focus:outline-none"
                  autoFocus
                />
              </div>
              <div>
                <label className="text-sm text-muted-foreground">{t.kb?.categoryDescription || 'Description (optional)'}</label>
                <textarea
                  value={newCategoryDescription}
                  onChange={(e) => setNewCategoryDescription(e.target.value)}
                  placeholder={t.kb?.categoryDescriptionPlaceholder || 'Brief description of this category...'}
                  rows={2}
                  className="w-full mt-1 rounded-xl border border-border bg-background px-4 py-2 text-sm focus:border-primary focus:outline-none resize-none"
                />
              </div>
            </div>
            <div className="flex gap-2 justify-end mt-6">
              <button
                onClick={() => { setShowCategoryModal(false); setNewCategoryName(''); setNewCategoryDescription(''); }}
                className="px-4 py-2 rounded-lg text-sm hover:bg-muted transition"
              >
                {t.kb?.cancel || 'Cancel'}
              </button>
              <button
                onClick={handleCreateCategory}
                disabled={!newCategoryName.trim()}
                className="px-4 py-2 rounded-lg text-sm bg-primary text-primary-foreground hover:bg-primary/90 transition disabled:opacity-50"
              >
                {t.kb?.create || 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══ Tab-based Document Viewer (Original + OCR Text) ═══ */}
      {viewDocId && (
        <DocumentViewer
          documentId={viewDocId}
          documentName={viewDocName}
          mimeType={viewDocMimeType}
          downloadUrl={apiClient.getDocumentDownloadUrl(viewDocId)}
          attachmentUrl={apiClient.getDocumentAttachmentUrl(viewDocId)}
          fetchOcrText={() => apiClient.getDocumentContent(viewDocId)}
          onClose={closeDocViewer}
          t={t}
        />
      )}
    </div>
  );
}
