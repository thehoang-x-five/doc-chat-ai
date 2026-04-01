# OCR_Ink Frontend Documentation

**Last Updated:** 2026-01-20

## Overview

Thư mục này chứa tài liệu cho OCR_Ink frontend, tập trung vào Memori system integration.

## Documentation

### 🎨 [MEMORI-FRONTEND-GUIDE.md](./MEMORI-FRONTEND-GUIDE.md)
**Complete guide for Memori frontend integration**

Nội dung:
- **Components:**
  - MemorySidebar (in Chat)
  - MemoryManagement Page
  - FactManagementPanel
  - KnowledgeGraphView
  - MemoryStatsWidget
  - Statistics Tab

- **Styling System:**
  - Design Tokens
  - Dark Mode Support
  - Focus Effects

- **Internationalization:**
  - English + Vietnamese
  - 30+ translation keys

- **Custom Hooks:**
  - useMemori hook
  - API integration

- **User Experience:**
  - Chat integration scenarios
  - Manual fact management
  - Knowledge graph visualization

- **API Integration:**
  - 17 endpoints
  - API client methods

- **Testing:**
  - Manual testing checklist
  - Troubleshooting guide

- **Performance:**
  - Optimizations
  - Bundle size

**Khi nào đọc:**
- Làm việc với Memori UI
- Cần hiểu components
- Debug UI issues
- Add new features

---

## Quick Start

### For Developers:

1. **Read the Guide:**
   ```bash
   # Open in editor
   code docs/MEMORI-FRONTEND-GUIDE.md
   ```

2. **Check Components:**
   ```bash
   # Component files
   src/components/memori/
   src/routes/MemoryManagement.tsx
   ```

3. **Test Locally:**
   ```bash
   npm run dev
   # Open http://localhost:5173
   ```

### For Designers:

1. **Styling System:**
   - Check "Styling System" section
   - Review design tokens
   - Test dark mode

2. **Components:**
   - Check "Components" section
   - Review layouts
   - Test responsive design

### For QA:

1. **Testing:**
   - Check "Testing" section
   - Follow manual testing checklist
   - Report issues

---

## Component Overview

### MemorySidebar
- **Location:** Chat page (right side)
- **Purpose:** Display recalled facts
- **Features:** Auto-recall, toggle, read-only

### MemoryManagement
- **Location:** `/memory` route
- **Purpose:** Full memory management
- **Tabs:** Facts, Knowledge Graph, Statistics

### FactManagementPanel
- **Location:** Memory page (Facts tab)
- **Purpose:** CRUD operations for facts
- **Features:** Search, add, delete, importance

### KnowledgeGraphView
- **Location:** Memory page (Graph tab)
- **Purpose:** Visual graph of relationships
- **Features:** D3.js, zoom, colors, legend

### Statistics Tab
- **Location:** Memory page (Statistics tab)
- **Purpose:** Analytics and insights
- **Features:** 3 cards + 4 charts

---

## API Integration

### Backend Endpoints:
```
Facts:        /api/v1/memori/facts/{entityId}
Preferences:  /api/v1/memori/preferences/{entityId}
Attributes:   /api/v1/memori/attributes/{entityId}
Graph:        /api/v1/memori/knowledge-graph/{entityId}
Analytics:    /api/v1/memori/analytics/*
```

### API Client:
```typescript
// Location: src/lib/api/client.ts

// Methods:
recallFacts()
listFacts()
addFacts()
getMemoriStats()
getKnowledgeGraph()
getMemoriHealth()
getMemoriUsage()
getTopFacts()
```

---

## Styling Guide

### Design Tokens:
```typescript
// Colors
bg-card/50              // Background
border-border           // Borders
text-foreground         // Text
text-primary            // Primary

// Spacing
p-2, p-2.5, p-3        // Padding
gap-2, gap-1.5         // Gaps

// Typography
text-xl, text-sm, text-xs, text-[10px]

// Border Radius
rounded-xl, rounded-lg, rounded-full
```

### Dark Mode:
- All components support dark mode
- Automatic theme switching
- Smooth transitions

---

## i18n Guide

### Supported Languages:
- 🇬🇧 English
- 🇻🇳 Vietnamese

### Adding Translations:
1. Edit `src/lib/i18n/translations/en.ts`
2. Edit `src/lib/i18n/translations/vi.ts`
3. Use in component: `const { t } = useI18n()`

---

## Testing Guide

### Manual Testing:
1. Open `/memory` page
2. Test each tab
3. Test CRUD operations
4. Test dark mode
5. Test language switching

### Checklist:
- [ ] MemorySidebar opens/closes
- [ ] Facts can be added
- [ ] Search works
- [ ] Graph renders
- [ ] Statistics display
- [ ] Dark mode works
- [ ] i18n works

---

## Troubleshooting

### Common Issues:

**MemorySidebar not showing:**
- Check `currentQuery` prop
- Check workspace ID
- Check backend running

**Facts not adding:**
- Check content not empty
- Check workspace ID
- Check backend API

**Graph not rendering:**
- Check triples exist
- Check D3.js loaded
- Try refresh button

**Statistics not loading:**
- Check backend endpoints
- Check workspace ID
- Check data exists

---

## Performance

### Optimizations:
- Debounced auto-recall (500ms)
- Lazy loading components
- React.memo for expensive components

### Bundle Size:
- MemorySidebar: ~15KB
- FactManagementPanel: ~20KB
- KnowledgeGraphView: ~30KB
- Total: ~65KB (gzipped)

---

## Future Enhancements

### Planned:
- [ ] Inline fact editing
- [ ] Drag & drop reorder
- [ ] Export/import memories
- [ ] Advanced search filters

### Under Consideration:
- [ ] Voice input
- [ ] AI-suggested facts
- [ ] Timeline view
- [ ] Mobile app

---

## Additional Resources

### Backend Documentation:
- System Architecture: `RAG-Anything/docs/01-SYSTEM-ARCHITECTURE.md`
- Memori System: `RAG-Anything/docs/02-MEMORI-SYSTEM.md`

### Code Examples:
- Components: `src/components/memori/`
- Routes: `src/routes/MemoryManagement.tsx`
- Hooks: `src/hooks/useMemori.ts`

---

## Document History

### Version 1.0 (2026-01-20)
- Consolidated 15 MD files into 1 comprehensive guide
- Removed outdated content
- Added complete component documentation
- Improved navigation

### Previous Files (Archived):
All previous MD files have been consolidated. Check git history for specific historical information.

---

## Contributing

When updating documentation:
1. Keep guide comprehensive
2. Update "Last Updated" date
3. Add examples for new features
4. Update troubleshooting section

---

## Support

### Questions?
- Read the guide first
- Check code examples
- Test locally
- Ask in team chat

### Found an issue?
- Create GitHub issue
- Tag with "frontend" or "documentation"
- Provide screenshots

---

**Happy Coding! 🎨**
