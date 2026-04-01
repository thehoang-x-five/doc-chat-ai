import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { useI18n } from '@/lib/i18n';
import { apiClient, Workspace, WorkspaceMember } from '@/lib/api';

const Workspaces = () => {
  const { t } = useI18n();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<Workspace | null>(null);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showMemberDialog, setShowMemberDialog] = useState(false);
  const [showSettingsDialog, setShowSettingsDialog] = useState(false);

  // Form states
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newPolicy, setNewPolicy] = useState<'strict' | 'balanced' | 'open'>('balanced');
  const [newThreshold, setNewThreshold] = useState(0.7);
  const [memberEmail, setMemberEmail] = useState('');
  const [memberRole, setMemberRole] = useState<'admin' | 'member' | 'viewer'>('member');

  useEffect(() => {
    loadWorkspaces();
  }, []);

  useEffect(() => {
    if (selectedWorkspace) {
      loadMembers(selectedWorkspace.id);
    }
  }, [selectedWorkspace]);

  const loadWorkspaces = async () => {
    try {
      setLoading(true);
      const data = await apiClient.getWorkspaces();
      setWorkspaces(data);
      if (data.length > 0 && !selectedWorkspace) {
        setSelectedWorkspace(data[0]);
      }
    } catch (error) {
      console.error('Failed to load workspaces:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadMembers = async (workspaceId: string) => {
    try {
      const data = await apiClient.getWorkspaceMembers(workspaceId);
      setMembers(data);
    } catch (error) {
      console.error('Failed to load members:', error);
    }
  };

  const handleCreateWorkspace = async () => {
    if (!newName.trim()) return;
    try {
      const workspace = await apiClient.createWorkspace({
        name: newName,
        description: newDescription,
        answerPolicy: newPolicy,
        confidenceThreshold: newThreshold,
      });
      setWorkspaces([workspace, ...workspaces]);
      setSelectedWorkspace(workspace);
      setShowCreateDialog(false);
      setNewName('');
      setNewDescription('');
    } catch (error) {
      console.error('Failed to create workspace:', error);
    }
  };

  const handleUpdateWorkspace = async () => {
    if (!selectedWorkspace) return;
    try {
      const updated = await apiClient.updateWorkspace(selectedWorkspace.id, {
        name: newName || selectedWorkspace.name,
        description: newDescription || selectedWorkspace.description,
        answerPolicy: newPolicy,
        confidenceThreshold: newThreshold,
      });
      setWorkspaces(workspaces.map(w => w.id === updated.id ? updated : w));
      setSelectedWorkspace(updated);
      setShowSettingsDialog(false);
    } catch (error) {
      console.error('Failed to update workspace:', error);
    }
  };

  const handleDeleteWorkspace = async (id: string) => {
    if (!confirm(t.workspace?.confirmDelete || 'Are you sure you want to delete this workspace?')) return;
    try {
      await apiClient.deleteWorkspace(id);
      setWorkspaces(workspaces.filter(w => w.id !== id));
      if (selectedWorkspace?.id === id) {
        setSelectedWorkspace(workspaces[0] || null);
      }
    } catch (error) {
      console.error('Failed to delete workspace:', error);
    }
  };

  const handleAddMember = async () => {
    if (!selectedWorkspace || !memberEmail.trim()) return;
    try {
      const member = await apiClient.addWorkspaceMember(selectedWorkspace.id, memberEmail, memberRole);
      setMembers([...members, member]);
      setShowMemberDialog(false);
      setMemberEmail('');
    } catch (error) {
      console.error('Failed to add member:', error);
    }
  };

  const handleRemoveMember = async (userId: string) => {
    if (!selectedWorkspace) return;
    if (!confirm(t.workspace?.confirmRemoveMember || 'Remove this member?')) return;
    try {
      await apiClient.removeWorkspaceMember(selectedWorkspace.id, userId);
      setMembers(members.filter(m => m.userId !== userId));
    } catch (error) {
      console.error('Failed to remove member:', error);
    }
  };

  const openSettingsDialog = () => {
    if (selectedWorkspace) {
      setNewName(selectedWorkspace.name);
      setNewDescription(selectedWorkspace.description || '');
      setNewPolicy(selectedWorkspace.answerPolicy);
      setNewThreshold(selectedWorkspace.confidenceThreshold);
      setShowSettingsDialog(true);
    }
  };

  const policyColors = {
    strict: 'bg-red-100 text-red-700 border-red-200',
    balanced: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    open: 'bg-green-100 text-green-700 border-green-200',
  };

  const roleColors = {
    owner: 'bg-purple-100 text-purple-700',
    admin: 'bg-blue-100 text-blue-700',
    member: 'bg-gray-100 text-gray-700',
    viewer: 'bg-gray-50 text-gray-500',
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t.workspace?.title || 'Workspaces'}</h1>
          <p className="text-muted-foreground">{t.workspace?.subtitle || 'Manage your workspaces and team members'}</p>
        </div>
        <button
          onClick={() => setShowCreateDialog(true)}
          className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          {t.workspace?.create || 'Create Workspace'}
        </button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Workspace List */}
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">{t.workspace?.yourWorkspaces || 'Your Workspaces'}</h2>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            </div>
          ) : workspaces.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border p-6 text-center text-muted-foreground">
              {t.workspace?.noWorkspaces || 'No workspaces yet. Create one to get started.'}
            </div>
          ) : (
            workspaces.map((ws) => (
              <motion.div
                key={ws.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`cursor-pointer rounded-xl border p-4 transition-all ${
                  selectedWorkspace?.id === ws.id
                    ? 'border-primary bg-primary/5 shadow-sm'
                    : 'border-border hover:border-primary/50 hover:bg-muted/50'
                }`}
                onClick={() => setSelectedWorkspace(ws)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium truncate">{ws.name}</h3>
                    {ws.description && (
                      <p className="text-sm text-muted-foreground truncate">{ws.description}</p>
                    )}
                  </div>
                  <span className={`ml-2 rounded-full border px-2 py-0.5 text-xs ${policyColors[ws.answerPolicy]}`}>
                    {ws.answerPolicy}
                  </span>
                </div>
                <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    {ws.memberCount || 1}
                  </span>
                  <span>•</span>
                  <span>{new Date(ws.createdAt).toLocaleDateString()}</span>
                </div>
              </motion.div>
            ))
          )}
        </div>

        {/* Workspace Details */}
        <div className="lg:col-span-2 space-y-4">
          {selectedWorkspace ? (
            <>
              {/* Workspace Info Card */}
              <div className="rounded-xl border border-border bg-card p-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-xl font-semibold">{selectedWorkspace.name}</h2>
                    <p className="text-muted-foreground">{selectedWorkspace.description || t.workspace?.noDescription || 'No description'}</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={openSettingsDialog}
                      className="rounded-lg border border-border p-2 hover:bg-muted"
                      title={t.common.edit}
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                    </button>
                    <button
                      onClick={() => handleDeleteWorkspace(selectedWorkspace.id)}
                      className="rounded-lg border border-red-200 p-2 text-red-600 hover:bg-red-50"
                      title={t.common.delete}
                    >
                      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>

                {/* Settings Summary */}
                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div className="rounded-lg bg-muted/50 p-3">
                    <div className="text-xs text-muted-foreground">{t.workspace?.answerPolicy || 'Answer Policy'}</div>
                    <div className="mt-1 flex items-center gap-2">
                      <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${policyColors[selectedWorkspace.answerPolicy]}`}>
                        {selectedWorkspace.answerPolicy.toUpperCase()}
                      </span>
                    </div>
                  </div>
                  <div className="rounded-lg bg-muted/50 p-3">
                    <div className="text-xs text-muted-foreground">{t.workspace?.confidenceThreshold || 'Confidence Threshold'}</div>
                    <div className="mt-1 font-medium">{(selectedWorkspace.confidenceThreshold * 100).toFixed(0)}%</div>
                  </div>
                </div>
              </div>

              {/* Members Card */}
              <div className="rounded-xl border border-border bg-card p-6">
                <div className="flex items-center justify-between">
                  <h3 className="font-medium">{t.workspace?.members || 'Members'}</h3>
                  <button
                    onClick={() => setShowMemberDialog(true)}
                    className="flex items-center gap-1 rounded-lg bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/20"
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    {t.workspace?.addMember || 'Add Member'}
                  </button>
                </div>

                <div className="mt-4 space-y-2">
                  {members.length === 0 ? (
                    <p className="text-sm text-muted-foreground">{t.workspace?.noMembers || 'No members yet'}</p>
                  ) : (
                    members.map((member) => (
                      <div key={member.userId} className="flex items-center justify-between rounded-lg border border-border p-3">
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-sm font-medium text-primary">
                            {member.name?.charAt(0).toUpperCase() || member.email.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <div className="font-medium">{member.name || member.email}</div>
                            <div className="text-xs text-muted-foreground">{member.email}</div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${roleColors[member.role]}`}>
                            {member.role}
                          </span>
                          {member.role !== 'owner' && (
                            <button
                              onClick={() => handleRemoveMember(member.userId)}
                              className="rounded p-1 text-muted-foreground hover:bg-red-50 hover:text-red-600"
                            >
                              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-border">
              <p className="text-muted-foreground">{t.workspace?.selectWorkspace || 'Select a workspace to view details'}</p>
            </div>
          )}
        </div>
      </div>

      {/* Create Workspace Dialog */}
      {showCreateDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="w-full max-w-md rounded-xl bg-card p-6 shadow-xl"
          >
            <h2 className="text-lg font-semibold">{t.workspace?.create || 'Create Workspace'}</h2>
            <p className="text-sm text-muted-foreground">{t.workspace?.createDesc || 'Create a new workspace for your team'}</p>

            <div className="mt-4 space-y-4">
              <div>
                <label className="text-sm font-medium">{t.workspace?.name || 'Name'}</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none"
                  placeholder={t.workspace?.namePlaceholder || 'My Workspace'}
                />
              </div>
              <div>
                <label className="text-sm font-medium">{t.workspace?.description || 'Description'}</label>
                <textarea
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none"
                  rows={2}
                  placeholder={t.workspace?.descriptionPlaceholder || 'Optional description...'}
                />
              </div>
              <div>
                <label className="text-sm font-medium">{t.workspace?.answerPolicy || 'Answer Policy'}</label>
                <select
                  value={newPolicy}
                  onChange={(e) => setNewPolicy(e.target.value as any)}
                  className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none"
                >
                  <option value="strict">STRICT - {t.workspace?.policyStrict || 'Refuse if low confidence'}</option>
                  <option value="balanced">BALANCED - {t.workspace?.policyBalanced || 'Fallback with disclaimer'}</option>
                  <option value="open">OPEN - {t.workspace?.policyOpen || 'Always answer'}</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{t.workspace?.confidenceThreshold || 'Confidence Threshold'}: {(newThreshold * 100).toFixed(0)}%</label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={newThreshold}
                  onChange={(e) => setNewThreshold(parseFloat(e.target.value))}
                  className="mt-1 w-full"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setShowCreateDialog(false)}
                className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-muted"
              >
                {t.common.cancel}
              </button>
              <button
                onClick={handleCreateWorkspace}
                disabled={!newName.trim()}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
              >
                {t.workspace?.create || 'Create'}
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {/* Add Member Dialog */}
      {showMemberDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="w-full max-w-md rounded-xl bg-card p-6 shadow-xl"
          >
            <h2 className="text-lg font-semibold">{t.workspace?.addMember || 'Add Member'}</h2>
            <p className="text-sm text-muted-foreground">{t.workspace?.addMemberDesc || 'Invite a team member to this workspace'}</p>

            <div className="mt-4 space-y-4">
              <div>
                <label className="text-sm font-medium">{t.auth.email}</label>
                <input
                  type="email"
                  value={memberEmail}
                  onChange={(e) => setMemberEmail(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none"
                  placeholder="member@example.com"
                />
              </div>
              <div>
                <label className="text-sm font-medium">{t.workspace?.role || 'Role'}</label>
                <select
                  value={memberRole}
                  onChange={(e) => setMemberRole(e.target.value as any)}
                  className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none"
                >
                  <option value="admin">Admin - {t.workspace?.roleAdmin || 'Full access'}</option>
                  <option value="member">Member - {t.workspace?.roleMember || 'Can edit documents'}</option>
                  <option value="viewer">Viewer - {t.workspace?.roleViewer || 'Read only'}</option>
                </select>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setShowMemberDialog(false)}
                className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-muted"
              >
                {t.common.cancel}
              </button>
              <button
                onClick={handleAddMember}
                disabled={!memberEmail.trim()}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50"
              >
                {t.workspace?.addMember || 'Add'}
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {/* Settings Dialog */}
      {showSettingsDialog && selectedWorkspace && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="w-full max-w-md rounded-xl bg-card p-6 shadow-xl"
          >
            <h2 className="text-lg font-semibold">{t.workspace?.settings || 'Workspace Settings'}</h2>

            <div className="mt-4 space-y-4">
              <div>
                <label className="text-sm font-medium">{t.workspace?.name || 'Name'}</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none"
                />
              </div>
              <div>
                <label className="text-sm font-medium">{t.workspace?.description || 'Description'}</label>
                <textarea
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none"
                  rows={2}
                />
              </div>
              <div>
                <label className="text-sm font-medium">{t.workspace?.answerPolicy || 'Answer Policy'}</label>
                <select
                  value={newPolicy}
                  onChange={(e) => setNewPolicy(e.target.value as any)}
                  className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none"
                >
                  <option value="strict">STRICT</option>
                  <option value="balanced">BALANCED</option>
                  <option value="open">OPEN</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">{t.workspace?.confidenceThreshold || 'Confidence Threshold'}: {(newThreshold * 100).toFixed(0)}%</label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={newThreshold}
                  onChange={(e) => setNewThreshold(parseFloat(e.target.value))}
                  className="mt-1 w-full"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setShowSettingsDialog(false)}
                className="rounded-lg border border-border px-4 py-2 text-sm hover:bg-muted"
              >
                {t.common.cancel}
              </button>
              <button
                onClick={handleUpdateWorkspace}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90"
              >
                {t.common.save}
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
};

export default Workspaces;
