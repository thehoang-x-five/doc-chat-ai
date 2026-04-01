# Development Documentation

Internal documentation cho development team về implementation details, analysis, và technical decisions.

## 📁 Files

### Memori System

#### `MEMORI_INTEGRATION.md`
Chi tiết về việc tích hợp Memori system vào RAG-Anything.

**Topics:**
- Integration architecture
- API endpoints
- Database schema
- Service implementation
- Frontend integration

#### `MEMORI_SETUP_COMPLETE.md`
Checklist và status của Memori setup.

**Topics:**
- Setup steps completed
- Configuration details
- Testing results
- Known issues
- Next steps

#### `MEMORI_REMAINING_ISSUES_AND_SOLUTIONS.md`
Outstanding issues và proposed solutions.

**Topics:**
- Current issues
- Root cause analysis
- Proposed solutions
- Implementation plan
- Priority ranking

### Graphiti Analysis

#### `GRAPHITI_ANALYSIS_AND_IMPROVEMENTS.md`
Analysis của Graphiti library và improvements made.

**Topics:**
- Graphiti overview
- Performance analysis
- Improvements implemented
- Benchmarks
- Future enhancements

### Implementation

#### `IMPLEMENTATION_PLAN.md`
Detailed implementation plan cho major features.

**Topics:**
- Feature requirements
- Technical design
- Implementation phases
- Timeline
- Resources needed

#### `IMPLEMENTATION_STATUS.md`
Current status của ongoing implementations.

**Topics:**
- Completed features
- In-progress features
- Blocked items
- Timeline updates
- Next milestones

## 🎯 Purpose

These documents are for:
- **Development Team:** Understanding implementation details
- **Technical Decisions:** Documenting why choices were made
- **Troubleshooting:** Reference for debugging
- **Onboarding:** New developers understanding system evolution
- **Planning:** Future development roadmap

## 📝 Document Guidelines

When adding new development docs:

1. **Clear Title:** Descriptive filename
2. **Date:** Include creation/update date
3. **Context:** Explain why document was created
4. **Technical Details:** Be specific and detailed
5. **Status:** Mark as draft/complete/archived
6. **Links:** Reference related docs and code

## 🔄 Document Lifecycle

### Active Documents:
- Regularly updated
- Reflect current state
- Used for decision making

### Archived Documents:
- Historical reference
- Completed implementations
- Lessons learned

## 📚 Related Documentation

### User Documentation:
- [System Architecture](../01-SYSTEM-ARCHITECTURE.md)
- [Memori System](../02-MEMORI-SYSTEM.md)
- [Performance Optimization](../03-PERFORMANCE-OPTIMIZATION.md)
- [Deployment Guide](../04-DEPLOYMENT-GUIDE.md)

### Code:
- [Server Code](../../server/app/)
- [Scripts](../../server/scripts/)
- [Tests](../../server/tests/)

## 🤝 Contributing

When working on features:

1. **Document Decisions:** Add to relevant dev doc
2. **Update Status:** Keep IMPLEMENTATION_STATUS.md current
3. **Share Knowledge:** Document learnings
4. **Link Code:** Reference PRs and commits
5. **Review:** Have team review technical docs

## 📧 Questions?

For questions about these documents:
- Check related user documentation first
- Review code comments
- Ask in team chat
- Create issue for clarification

---

**Note:** These are internal development documents. For user-facing documentation, see parent `docs/` directory.
