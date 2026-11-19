import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import {
  appendSkillVersion,
  compareSkillVersions,
  createA2ACredential,
  createA2APeer,
  createAgent,
  createSkill,
  getOrganizationRunEvents,
  listA2APeers,
  listAgents,
  listOrganizationRuns,
  listSkills,
  listSkillVersions,
  restoreSkillVersion,
  rotateA2APeerCredential,
  setAgentPublished,
  updateAgent,
  type A2APeer,
  type AgentDefinition,
  type AgentRun,
  type SkillDefinition,
  type SkillRevision,
} from '@/api/agents'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'

/** 渲染组织范围内的 Agent、Skill 管理与 A2A 登记界面。 */
export function Agents() {
  const { t } = useTranslation()
  const [agents, setAgents] = useState<AgentDefinition[]>([])
  const [skills, setSkills] = useState<SkillDefinition[]>([])
  const [peers, setPeers] = useState<A2APeer[]>([])
  const [runs, setRuns] = useState<AgentRun[]>([])
  const [selectedSkillId, setSelectedSkillId] = useState('')
  const [revisions, setRevisions] = useState<SkillRevision[]>([])
  const [comparison, setComparison] = useState<{
    before: string
    after: string
  } | null>(null)
  const [runEvents, setRunEvents] = useState<unknown[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [agentForm, setAgentForm] = useState({
    name: '',
    description: '',
    instructions: '',
    model_name: '',
    skill_id: '',
    peer_ids: [] as string[],
  })
  const [skillForm, setSkillForm] = useState({
    name: '',
    description: '',
    body: '',
  })
  const [revisionBody, setRevisionBody] = useState('')
  const [peerForm, setPeerForm] = useState({
    name: '',
    card_url: '',
    endpoint_url: '',
    credential_env_alias: '',
  })
  const [credentialResult, setCredentialResult] = useState('')
  const approvedPeers = peers.filter((peer) => peer.is_approved && peer.is_enabled)

  /** 从 API 刷新当前组织的 Agent、Skill、A2A 目标与运行记录，并同步错误横幅。 */
  const refresh = async () => {
    try {
      const [agentItems, skillItems, peerItems, runItems] = await Promise.all([
        listAgents(),
        listSkills(),
        listA2APeers(),
        listOrganizationRuns(),
      ])
      setAgents(agentItems)
      setSkills(skillItems)
      setPeers(peerItems)
      setRuns(runItems)
      setSelectedSkillId((currentId) => currentId || skillItems[0]?.id || '')
      setError('')
    } catch {
      setError(String(t('agents.loadFailed')))
    }
  }

  useEffect(() => {
    let cancelled = false
    Promise.all([
      listAgents(),
      listSkills(),
      listA2APeers(),
      listOrganizationRuns(),
    ])
      .then(([agentItems, skillItems, peerItems, runItems]) => {
        if (cancelled) return
        setAgents(agentItems)
        setSkills(skillItems)
        setPeers(peerItems)
        setRuns(runItems)
        setSelectedSkillId(skillItems[0]?.id ?? '')
        setError('')
      })
      .catch(() => {
        if (!cancelled) setError(String(t('agents.loadFailed')))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [t])

  useEffect(() => {
    if (!selectedSkillId) return
    let cancelled = false
    listSkillVersions(selectedSkillId)
      .then((skillRevisions) => {
        if (!cancelled) {
          setRevisions(skillRevisions)
          setError('')
        }
      })
      .catch(() => {
        if (!cancelled) setError(String(t('agents.loadVersionsFailed')))
      })
    return () => {
      cancelled = true
    }
  }, [selectedSkillId, skills, t])

  /** 根据表单创建尚未发布的 Agent。 */
  const submitAgent = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    try {
      await createAgent({
        ...agentForm,
        model_name: agentForm.model_name || null,
        skill_id: agentForm.skill_id || null,
        peer_ids: agentForm.peer_ids,
      })
      setAgentForm({
        name: '',
        description: '',
        instructions: '',
        model_name: '',
        skill_id: '',
        peer_ids: [],
      })
      await refresh()
      toast.success(t('agents.agentCreated'))
    } catch {
      toast.error(t('agents.actionFailed'))
    }
  }

  /** 创建 Skill 并加载其初始不可变版本。 */
  const submitSkill = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    try {
      const createdSkill = await createSkill(skillForm)
      setSkillForm({ name: '', description: '', body: '' })
      setSelectedSkillId(createdSkill.id)
      setRevisions([])
      await refresh()
      toast.success(t('agents.skillCreated'))
    } catch {
      toast.error(t('agents.actionFailed'))
    }
  }

  /** 调用不可变版本接口追加 Skill 新版本。 */
  const submitRevision = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selectedSkillId || !revisionBody.trim()) return
    try {
      await appendSkillVersion(selectedSkillId, revisionBody)
      setRevisionBody('')
      setSkills(await listSkills())
      setRevisions(await listSkillVersions(selectedSkillId))
      toast.success(t('agents.versionAdded'))
    } catch {
      toast.error(t('agents.actionFailed'))
    }
  }

  /** 通过 API 比较历史版本与当前版本。 */
  const compareRevision = async (version: number) => {
    if (!selectedSkillId) return
    try {
      const currentVersion =
        skills.find((skill) => skill.id === selectedSkillId)?.current_version ??
        version
      const compared = await compareSkillVersions(
        selectedSkillId,
        version,
        currentVersion
      )
      setComparison({
        before: compared.from_version.body,
        after: compared.to_version.body,
      })
    } catch {
      toast.error(t('agents.compareFailed'))
    }
  }

  /** 复制历史版本内容并创建新的当前版本。 */
  const restoreRevision = async (version: number) => {
    if (
      !selectedSkillId ||
      !window.confirm(t('agents.restoreConfirm', { version }))
    )
      return
    try {
      await restoreSkillVersion(selectedSkillId, version)
      setSkills(await listSkills())
      setRevisions(await listSkillVersions(selectedSkillId))
      toast.success(t('agents.versionRestored'))
    } catch {
      toast.error(t('agents.actionFailed'))
    }
  }

  /** 登记外部 A2A 目标，且不回显已保存的凭据。 */
  const submitPeer = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    try {
      await createA2APeer(peerForm)
      setPeerForm({
        name: '',
        card_url: '',
        endpoint_url: '',
        credential_env_alias: '',
      })
      setPeers(await listA2APeers())
      toast.success(t('agents.peerRegistered'))
    } catch {
      toast.error(t('agents.actionFailed'))
    }
  }

  /** Rotate a peer credential using a server-side environment variable alias. */
  const rotatePeerCredential = async (peer: A2APeer) => {
    const credentialAlias = window.prompt(t('agents.credentialAlias'))
    if (!credentialAlias?.trim()) return
    try {
      await rotateA2APeerCredential(peer.id, credentialAlias.trim())
      toast.success(t('agents.credentialRotated'))
    } catch {
      toast.error(t('agents.actionFailed'))
    }
  }

  /** Create a one-time inbound token so a trusted A2A client can call this Agent. */
  const issueCredential = async (agent: AgentDefinition) => {
    try {
      const credential = await createA2ACredential(
        agent.id,
        `${agent.name} client`
      )
      setCredentialResult(credential.token)
      toast.success(t('agents.credentialCreated'))
    } catch {
      toast.error(t('agents.actionFailed'))
    }
  }

  /** Load sanitized event metadata for the selected organization's run. */
  const inspectRun = async (runId: string) => {
    try {
      setRunEvents((await getOrganizationRunEvents(runId)).items)
    } catch {
      toast.error(t('agents.runTraceFailed'))
    }
  }

  /** Publish or unpublish an Agent to the organization's members. */
  const togglePublished = async (agent: AgentDefinition) => {
    try {
      await setAgentPublished(agent.id, !agent.is_published)
      await refresh()
    } catch {
      toast.error(t('agents.actionFailed'))
    }
  }

  /** Disable an Agent without deleting its history. */
  const toggleEnabled = async (agent: AgentDefinition) => {
    try {
      await updateAgent(agent, !agent.is_enabled)
      await refresh()
    } catch {
      toast.error(t('agents.actionFailed'))
    }
  }

  if (loading)
    return (
      <Main>
        <p className='p-6'>{t('common.loading')}</p>
      </Main>
    )

  return (
    <>
      <Header fixed>
        <div className='ml-auto flex items-center gap-4'>
          <ProfileDropdown />
        </div>
      </Header>
      <Main>
        <div className='mb-6'>
          <h1 className='text-2xl font-bold tracking-tight'>
            {t('agents.title')}
          </h1>
          <p className='text-muted-foreground'>{t('agents.description')}</p>
          {error && (
            <p role='alert' className='mt-2 text-sm text-destructive'>
              {error}
            </p>
          )}
        </div>

        <div className='grid gap-6 xl:grid-cols-2'>
          <Card>
            <CardHeader>
              <CardTitle>{t('agents.agentManagement')}</CardTitle>
            </CardHeader>
            <CardContent className='space-y-5'>
              <form
                className='grid gap-3'
                onSubmit={(event) => void submitAgent(event)}
              >
                <Input
                  aria-label={t('agents.name')}
                  placeholder={t('agents.name')}
                  required
                  value={agentForm.name}
                  onChange={(event) =>
                    setAgentForm({ ...agentForm, name: event.target.value })
                  }
                />
                <Input
                  aria-label={t('agents.descriptionField')}
                  placeholder={t('agents.descriptionField')}
                  value={agentForm.description}
                  onChange={(event) =>
                    setAgentForm({
                      ...agentForm,
                      description: event.target.value,
                    })
                  }
                />
                <Input
                  aria-label={t('agents.model')}
                  placeholder={t('agents.model')}
                  value={agentForm.model_name}
                  onChange={(event) =>
                    setAgentForm({
                      ...agentForm,
                      model_name: event.target.value,
                    })
                  }
                />
                <label className='grid gap-2 text-sm font-medium'>
                  {t('agents.selectSkill')}
                  <select
                    aria-label={t('agents.selectSkill')}
                    className='h-10 rounded-md border bg-background px-3'
                    value={agentForm.skill_id}
                    onChange={(event) =>
                      setAgentForm({ ...agentForm, skill_id: event.target.value })
                    }
                  >
                    <option value=''>{t('agents.noSkill')}</option>
                    {skills.map((skill) => (
                      <option key={skill.id} value={skill.id}>
                        {skill.name} · v{skill.current_version}
                      </option>
                    ))}
                  </select>
                </label>
                <Textarea
                  aria-label={t('agents.instructions')}
                  placeholder={t('agents.instructions')}
                  required
                  rows={3}
                  value={agentForm.instructions}
                  onChange={(event) =>
                    setAgentForm({
                      ...agentForm,
                      instructions: event.target.value,
                    })
                  }
                />
                <fieldset className='grid gap-2 rounded-md border p-3'>
                  <legend className='px-1 text-sm font-medium'>
                    {t('agents.outboundPeers')}
                  </legend>
                  <p
                    id='agent-peer-selection-help'
                    className='text-xs text-muted-foreground'
                  >
                    {t('agents.peerBindingHelp')}
                  </p>
                  {approvedPeers.length > 0 ? (
                    approvedPeers.map((peer) => (
                      <label
                        key={peer.id}
                        htmlFor={`agent-peer-${peer.id}`}
                        className='flex items-center gap-2 text-sm'
                      >
                        <Checkbox
                          id={`agent-peer-${peer.id}`}
                          data-testid={`agent-peer-${peer.id}`}
                          aria-describedby='agent-peer-selection-help'
                          checked={agentForm.peer_ids.includes(peer.id)}
                          onCheckedChange={(checked) =>
                            setAgentForm((currentForm) => ({
                              ...currentForm,
                              peer_ids:
                                checked === true
                                  ? [...new Set([...currentForm.peer_ids, peer.id])]
                                  : currentForm.peer_ids.filter(
                                      (peerId) => peerId !== peer.id
                                    ),
                            }))
                          }
                        />
                        <span>{peer.name}</span>
                      </label>
                    ))
                  ) : (
                    <p className='text-sm text-muted-foreground'>
                      {t('agents.noApprovedPeers')}
                    </p>
                  )}
                </fieldset>
                <Button type='submit'>{t('agents.createAgent')}</Button>
              </form>
              <div className='space-y-3'>
                {agents.map((agent) => (
                  <div
                    key={agent.id}
                    data-testid={`managed-agent-${agent.id}`}
                    className='flex flex-wrap items-center justify-between gap-3 rounded-md border p-3'
                  >
                    <div className='min-w-0'>
                      <strong>{agent.name}</strong>
                      <p className='text-xs text-muted-foreground'>
                        {agent.is_published
                          ? t('agents.published')
                          : t('agents.draft')}{' '}
                        ·{' '}
                        {agent.is_runnable
                          ? t('agents.ready')
                          : agent.unavailable_reason}
                      </p>
                      <p className='text-xs text-muted-foreground'>
                        {t('agents.allowedPeers')}:{' '}
                        {agent.allowed_peer_ids.length > 0
                          ? agent.allowed_peer_ids
                              .map(
                                (peerId) =>
                                  peers.find((peer) => peer.id === peerId)?.name ??
                                  peerId
                              )
                              .join(', ')
                          : t('agents.none')}
                      </p>
                      <p className='font-mono text-[10px] break-all text-muted-foreground'>
                        {agent.id}
                      </p>
                      {agent.a2a_card_url && (
                        <a
                          className='mt-1 block break-all text-xs text-primary underline underline-offset-2'
                          href={agent.a2a_card_url}
                          rel='noreferrer'
                          target='_blank'
                        >
                          {t('agents.agentCardAddress')}: {agent.a2a_card_url}
                        </a>
                      )}
                    </div>
                    <div className='flex flex-wrap gap-2'>
                      <Button
                        size='sm'
                        variant='outline'
                        onClick={() => void togglePublished(agent)}
                      >
                        {agent.is_published
                          ? t('agents.unpublish')
                          : t('agents.publish')}
                      </Button>
                      <Button
                        size='sm'
                        variant='outline'
                        onClick={() => void toggleEnabled(agent)}
                      >
                        {agent.is_enabled
                          ? t('agents.disable')
                          : t('agents.enable')}
                      </Button>
                      {agent.is_published && (
                        <Button
                          size='sm'
                          onClick={() => void issueCredential(agent)}
                        >
                          {t('agents.issueCredential')}
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
                {agents.length === 0 && (
                  <p className='text-sm text-muted-foreground'>
                    {t('agents.noAgents')}
                  </p>
                )}
              </div>
              {credentialResult && (
                <div className='rounded-md border border-primary/40 bg-primary/5 p-3'>
                  <p className='text-sm font-medium'>{t('agents.tokenOnce')}</p>
                  <code className='mt-2 block text-xs break-all'>
                    {credentialResult}
                  </code>
                  <Button
                    className='mt-2'
                    size='sm'
                    variant='outline'
                    onClick={() => setCredentialResult('')}
                  >
                    {t('common.dismiss')}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('agents.skillGovernance')}</CardTitle>
            </CardHeader>
            <CardContent className='space-y-5'>
              <form
                className='grid gap-3'
                onSubmit={(event) => void submitSkill(event)}
              >
                <Input
                  aria-label={t('agents.skillName')}
                  placeholder={t('agents.skillName')}
                  required
                  value={skillForm.name}
                  onChange={(event) =>
                    setSkillForm({ ...skillForm, name: event.target.value })
                  }
                />
                <Input
                  aria-label={t('agents.descriptionField')}
                  placeholder={t('agents.descriptionField')}
                  value={skillForm.description}
                  onChange={(event) =>
                    setSkillForm({
                      ...skillForm,
                      description: event.target.value,
                    })
                  }
                />
                <Textarea
                  aria-label={t('agents.skillBody')}
                  placeholder={t('agents.skillBody')}
                  required
                  rows={3}
                  value={skillForm.body}
                  onChange={(event) =>
                    setSkillForm({ ...skillForm, body: event.target.value })
                  }
                />
                <Button type='submit'>{t('agents.createSkill')}</Button>
              </form>
              <label className='grid gap-2 text-sm font-medium'>
                {t('agents.selectSkill')}
                <select
                  className='h-10 rounded-md border bg-background px-3'
                  value={selectedSkillId}
                  onChange={(event) => {
                    setRevisions([])
                    setSelectedSkillId(event.target.value)
                  }}
                >
                  {skills.map((skill) => (
                    <option key={skill.id} value={skill.id}>
                      {skill.name} · v{skill.current_version}
                    </option>
                  ))}
                </select>
              </label>
              {selectedSkillId && (
                <form
                  className='grid gap-3'
                  onSubmit={(event) => void submitRevision(event)}
                >
                  <Textarea
                    aria-label={t('agents.nextVersion')}
                    placeholder={t('agents.nextVersion')}
                    rows={3}
                    value={revisionBody}
                    onChange={(event) => setRevisionBody(event.target.value)}
                  />
                  <Button type='submit' disabled={!revisionBody.trim()}>
                    {t('agents.addVersion')}
                  </Button>
                </form>
              )}
              <div className='space-y-2'>
                {revisions.map((revision) => (
                  <div
                    key={revision.id}
                    data-testid={`skill-revision-${revision.version}`}
                    className='flex items-center justify-between gap-2 rounded border p-2 text-sm'
                  >
                    <span>
                      v{revision.version}{' '}
                      <code className='text-xs text-muted-foreground'>
                        {revision.checksum.slice(0, 10)}
                      </code>
                    </span>
                    <span className='flex gap-2'>
                      <Button
                        size='sm'
                        variant='outline'
                        onClick={() => void compareRevision(revision.version)}
                      >
                        {t('agents.compare')}
                      </Button>
                      {revision.version <
                        (skills.find((skill) => skill.id === selectedSkillId)
                          ?.current_version ?? 0) && (
                        <Button
                          size='sm'
                          variant='outline'
                          onClick={() => void restoreRevision(revision.version)}
                        >
                          {t('agents.restore')}
                        </Button>
                      )}
                    </span>
                  </div>
                ))}
              </div>
              {comparison && (
                <div className='grid gap-2 md:grid-cols-2'>
                  <pre className='max-h-48 overflow-auto rounded bg-muted p-3 text-xs whitespace-pre-wrap'>
                    {comparison.before}
                  </pre>
                  <pre className='max-h-48 overflow-auto rounded bg-muted p-3 text-xs whitespace-pre-wrap'>
                    {comparison.after}
                  </pre>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('agents.a2aDirectory')}</CardTitle>
            </CardHeader>
            <CardContent className='space-y-4'>
              <form
                className='grid gap-3'
                onSubmit={(event) => void submitPeer(event)}
              >
                <Input
                  aria-label={t('agents.peerName')}
                  placeholder={t('agents.peerName')}
                  required
                  value={peerForm.name}
                  onChange={(event) =>
                    setPeerForm({ ...peerForm, name: event.target.value })
                  }
                />
                <Input
                  aria-label={t('agents.cardUrl')}
                  placeholder={t('agents.cardUrl')}
                  required
                  type='url'
                  value={peerForm.card_url}
                  onChange={(event) =>
                    setPeerForm({ ...peerForm, card_url: event.target.value })
                  }
                />
                <Input
                  aria-label={t('agents.endpointUrl')}
                  placeholder={t('agents.endpointUrl')}
                  required
                  type='url'
                  value={peerForm.endpoint_url}
                  onChange={(event) =>
                    setPeerForm({
                      ...peerForm,
                      endpoint_url: event.target.value,
                    })
                  }
                />
                <Input
                  aria-label={t('agents.credentialAlias')}
                  placeholder={t('agents.credentialAlias')}
                  value={peerForm.credential_env_alias}
                  onChange={(event) =>
                    setPeerForm({
                      ...peerForm,
                      credential_env_alias: event.target.value,
                    })
                  }
                />
                <Button type='submit'>{t('agents.registerPeer')}</Button>
              </form>
              <p className='text-xs text-muted-foreground'>
                {t('agents.peerApprovalHelp')}
              </p>
              {peers.map((peer) => (
                <div key={peer.id} className='rounded border p-3 text-sm'>
                  <strong>{peer.name}</strong> ·{' '}
                  {peer.is_approved
                    ? t('agents.approved')
                    : t('agents.pending')}
                  <p className='mt-1 text-xs break-all text-muted-foreground'>
                    {peer.card_url}
                  </p>
                  <Button
                    className='mt-2'
                    size='sm'
                    variant='outline'
                    onClick={() => void rotatePeerCredential(peer)}
                  >
                    {t('agents.rotateCredential')}
                  </Button>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('agents.recentRuns')}</CardTitle>
            </CardHeader>
            <CardContent className='space-y-2'>
              {runs.map((run) => (
                <button
                  key={run.id}
                  className='w-full rounded border p-3 text-left hover:bg-muted/50'
                  onClick={() => void inspectRun(run.id)}
                  type='button'
                >
                  <strong>{run.agent_name}</strong> · {run.status}
                  <span className='mt-1 block font-mono text-xs text-muted-foreground'>
                    {run.id} · {run.event_count} events
                  </span>
                </button>
              ))}
              {runEvents.length > 0 && (
                <pre className='max-h-56 overflow-auto rounded bg-muted p-3 text-xs'>
                  {JSON.stringify(runEvents, null, 2)}
                </pre>
              )}
            </CardContent>
          </Card>
        </div>
      </Main>
    </>
  )
}
